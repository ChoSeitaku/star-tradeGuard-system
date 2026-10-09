"""AI 风险解读层（DeepSeek，OpenAI 兼容协议 + JSON 输出）。

设计要点：
* 凭据只从环境变量读取，不写进源码；未配置凭据或调用失败时自动回落规则模板文案，主流程不中断；
* 输入是规则引擎已经算好的「特征快照 + 命中规则 + 评分结论」，模型只负责解读成因与给出处置建议，
  不参与评分、不改变决策结论（评分与最终 decision 始终由规则引擎产出）；
* 解读结果落库到 ``risk_ai_notes``（每次评估一条，assessment_id 唯一），GET 查询直接复用，
  避免重复消耗 token；如需重新生成，调用 ``POST /api/risk/assessments/{id}/ai-explain``。

环境变量：
    DEEPSEEK_API_KEY / AI_API_KEY      凭据；缺失则本层整体降级为规则模板文案
    DEEPSEEK_BASE_URL / AI_BASE_URL    默认 https://api.deepseek.com
    DEEPSEEK_MODEL / AI_MODEL          默认 deepseek-flash
    AI_MAX_TOKENS                      默认 2048
    AI_TIMEOUT_SECONDS                 默认 60
    AI_TEMPERATURE                     默认 0.2
    AI_REASONING_EFFORT                默认 low
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.request
from datetime import datetime
from typing import Any, Optional

SYSTEM = (
    "你是电商交易风控团队的 AI 风险分析助手。你的任务是把规则引擎已经算好的结果解释清楚，"
    "并给出可执行的处置建议。硬性要求：\n"
    "1. 风险评分、风险等级和处理结论由规则引擎给出，你只能引用，不得修改，也不得另给一套结论；\n"
    "2. 说明风险成因时必须结合命中规则与特征快照里的具体数值；\n"
    "3. 处置建议必须可落地（校验方式、审核动作、留痕要求、时效），不要空泛口号；\n"
    "4. 全部使用简体中文，措辞客观，不做超出数据的推断。"
)

SCHEMA = """{
  "summary": "一到两句话的结论：本次检查的风险成因与判定依据（引用评分与命中规则）",
  "key_factors": ["关键风险点1（含具体数值）", "关键风险点2"],
  "handling_steps": ["处置动作1", "处置动作2"],
  "risk_note": "给风控运营的提醒（误伤可能性、需补充核实的信息等）"
}"""

_TABLE_SQL = """CREATE TABLE IF NOT EXISTS risk_ai_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    model TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
)"""

_ensured = False


# ---------------------------------------------------------------- 环境变量

def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(_env(name) or default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except (TypeError, ValueError):
        return default


def _cred() -> str:
    return _env("AI_API_KEY") or _env("DEEPSEEK_API_KEY")


def _base() -> str:
    return (_env("AI_BASE_URL") or _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")).rstrip("/")


def model_name() -> str:
    return _env("AI_MODEL") or _env("DEEPSEEK_MODEL", "deepseek-flash")


def configured() -> bool:
    """是否配置了大模型凭据（未配置时本层使用规则模板文案）。"""
    return bool(_cred())


# ---------------------------------------------------------------- 文本工具

def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "value", "content", "desc", "detail"):
            if key in value:
                return _text(value[key])
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "；".join(x for x in (_text(v) for v in value) if x)
    return str(value)


def _text_list(value: Any, limit: int = 6) -> list:
    if isinstance(value, (str, dict)):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        text = _text(item)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _brief(payload: Any, limit: int = 6000) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…(已截断)"


def _parse_json(raw: str) -> Any:
    """容错解析：支持裸 JSON、```json 围栏、以及前后夹带说明文字。"""
    text = (raw or "").strip()
    if not text:
        return None
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        end = max(text.rfind("}"), text.rfind("]"))
        if starts and end > starts[0]:
            try:
                return json.loads(text[starts[0]: end + 1])
            except ValueError:
                return None
        return None


# ---------------------------------------------------------------- 上下文

def context_from_detail(detail: dict) -> dict:
    """把 build_assessment_detail 的返回值压成喂给模型的上下文。"""
    snapshot = detail.get("feature_snapshot") or {}
    if isinstance(snapshot, dict):
        snapshot = {str(k): _text(v)[:200] for k, v in list(snapshot.items())[:60]}
    else:
        snapshot = {"snapshot": _text(snapshot)[:800]}
    return {
        "event_type": detail.get("event_type"),
        "event_type_label": detail.get("event_type_label"),
        "user_id": detail.get("user_id"),
        "order_id": detail.get("order_id"),
        "risk_score": detail.get("risk_score"),
        "risk_level": detail.get("risk_level"),
        "risk_level_label": detail.get("risk_level_label"),
        "decision": detail.get("decision"),
        "decision_label": detail.get("decision_label"),
        "hit_rules": [
            {
                "rule": _text(h.get("rule_name")),
                "score": h.get("hit_score"),
                "message": _text(h.get("hit_message")),
            }
            for h in (detail.get("rule_hits") or [])
        ],
        "feature_snapshot": snapshot,
    }


# ---------------------------------------------------------------- 模型调用

def _normalize(data: Any) -> Optional[dict]:
    if not isinstance(data, dict):
        return None
    summary = _text(data.get("summary")) or _text(data.get("conclusion"))
    steps = _text_list(data.get("handling_steps") or data.get("steps"))
    if not summary or not steps:
        return None
    return {
        "summary": summary,
        "key_factors": _text_list(data.get("key_factors") or data.get("factors"), 6),
        "handling_steps": steps,
        "risk_note": _text(data.get("risk_note") or data.get("note")),
    }


def _post(body: dict) -> str:
    req = urllib.request.Request(
        _base() + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + _cred())
    with urllib.request.urlopen(req, timeout=_env_int("AI_TIMEOUT_SECONDS", 60)) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choice = (data.get("choices") or [{}])[0]
    return ((choice.get("message") or {}).get("content") or "").strip()


def explain(context: dict) -> Optional[dict]:
    """调用大模型生成风险解读；任何异常（含超时、限流、解析失败）返回 None。"""
    if not configured():
        return None
    user = (
        "请解读下面这次风险检查，输出风险成因、关键风险点与处置建议。\n"
        "注意：risk_score / risk_level / decision 是规则引擎的最终结论，直接引用即可。\n\n"
        "【输出要求】只输出一个 JSON 对象，不要解释、不要 Markdown 围栏。字段结构：\n"
        + SCHEMA
        + "\n\n【本次检查数据】\n"
        + _brief(context)
    )
    body = {
        "model": model_name(),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": _env_float("AI_TEMPERATURE", 0.2),
    }
    body["max_" + "tokens"] = _env_int("AI_MAX_TOKENS", 2048)
    effort = _env("AI_REASONING_EFFORT", "low")
    if effort:
        body["reasoning_effort"] = effort
    try:
        return _normalize(_parse_json(_post(body)))
    except Exception:
        return None


# ---------------------------------------------------------------- 规则模板回落

_FALLBACK_STEPS = {
    "low": [
        "按正常流程放行，不新增人工介入成本。",
        "把该用户 / 设备指纹 / 收货信息保留在观察名单，后续再次触发时升级处理。",
        "关注同类事件是否聚集出现，出现批量聚集时同步风控策略同学复盘规则阈值。",
    ],
    "medium": [
        "对用户做一次二次校验（短信验证码或人脸核身），确认是本人操作。",
        "转人工复核订单信息（收货信息、支付方式、历史行为），先审后放。",
        "复核期间暂缓发货，复核结论与操作人写入案件留痕。",
    ],
    "high": [
        "立即拦截 / 冻结该笔交易与账号下单能力，避免资损扩大。",
        "转人工审核并主动联系用户核实身份与交易意图，无法确认则维持拦截。",
        "完整留存证据（事件入参、特征快照、命中规则）以备申诉与审计。",
        "同一来源 / 设备 / 地址的关联账号一并排查，防止团伙化攻击。",
    ],
}


def rule_fallback(context: dict) -> dict:
    """未配置模型或调用失败时使用的确定性文案，保证接口始终有解读内容。"""
    level = (context.get("risk_level") or "low")
    label = context.get("risk_level_label") or level
    hits = context.get("hit_rules") or []
    factors = []
    for hit in hits[:6]:
        message = _text(hit.get("message"))
        if message:
            factors.append(f"{_text(hit.get('rule')) or '命中规则'}：{message}（+{hit.get('score')}分）")
    if not factors:
        factors = ["本次检查未命中任何规则，特征快照未发现明显异常。"]
    summary = (
        f"本次{context.get('event_type_label') or '交易'}检查命中 {len(hits)} 条规则，"
        f"累计风险分 {context.get('risk_score')}，判定为{label}，处理建议为"
        f"{context.get('decision_label') or context.get('decision')}。"
        f"主要风险点：{'；'.join(f.split('：', 1)[-1] for f in factors[:2])}"
    )
    return {
        "summary": summary,
        "key_factors": factors,
        "handling_steps": list(_FALLBACK_STEPS.get(level, _FALLBACK_STEPS["low"])),
        "risk_note": "本解读由规则模板生成（未配置大模型凭据或模型调用失败），评分与决策结论以规则引擎为准。",
    }


# ---------------------------------------------------------------- 落库

def ensure_table(conn: sqlite3.Connection) -> None:
    """惰性建表（幂等），避免依赖 seed 脚本重建数据库。"""
    global _ensured
    if _ensured:
        return
    try:
        conn.execute(_TABLE_SQL)
        conn.commit()
        _ensured = True
    except sqlite3.Error:
        pass


def save_note(conn: sqlite3.Connection, assessment_id: int, payload: dict, source: str) -> None:
    ensure_table(conn)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO risk_ai_notes (assessment_id, provider, model, payload_json, created_at)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(assessment_id) DO UPDATE SET"
        " provider=excluded.provider, model=excluded.model,"
        " payload_json=excluded.payload_json, created_at=excluded.created_at",
        (assessment_id, source, model_name() if source == "deepseek" else None,
         json.dumps(payload, ensure_ascii=False), now),
    )
    conn.commit()


def load_note(conn: sqlite3.Connection, assessment_id: int) -> Optional[dict]:
    """读取已落库的解读；表不存在或数据非法时返回 None（不影响主流程）。"""
    try:
        row = conn.execute(
            "SELECT provider, model, payload_json, created_at FROM risk_ai_notes WHERE assessment_id=?",
            (assessment_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    try:
        payload = json.loads(row[2])
    except (ValueError, TypeError):
        payload = {}
    return {
        "provider": row[0],
        "source": row[0],
        "model": row[1],
        "created_at": row[3],
        "payload": payload,
    }


def generate_for_assessment(conn: sqlite3.Connection, assessment_id: int, context: dict) -> dict:
    """生成 + 落库；模型不可用时回落规则模板文案。返回最终解读字典。"""
    data = explain(context)
    source = "deepseek" if data else "rule_engine"
    payload = data or rule_fallback(context)
    payload["provider"] = source
    try:
        save_note(conn, assessment_id, payload, source)
    except sqlite3.Error:
        pass
    return payload
