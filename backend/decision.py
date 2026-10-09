"""决策模块：风险检查主链路（事件接入 → 特征 → 规则匹配 → 评分 → 决策 → 自动建案）。

POST /api/risk/check 处理流程：
    1. 校验入参（事件类型合法、用户与订单存在）
    2. 写入 risk_events（保存原始入参）
    3. 计算 25 个风险特征并写入 feature_snapshots（特征快照）
    4. 按优先级匹配启用中的规则，写入 rule_hits（命中规则）
    5. 汇总评分、输出风险等级与处理建议，写入 risk_assessments
    6. 高风险 / 需人工审核时自动创建 risk_cases 并记录 review_logs
"""
import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

import db as db_module
import features as features_module
import rules as rules_module
import ai_explainer as ai_module
from config import (AUTO_CASE_DECISIONS, CASE_STATUS_BY_DECISION, CASE_STATUS_LABELS, DECISION_LABELS,
                    EVENT_TYPES, EVENT_TYPE_LABELS, LEVEL_DECISION_MAP, LEVEL_HIGH_THRESHOLD,
                    LEVEL_MEDIUM_THRESHOLD, RISK_LEVEL_LABELS, SCORE_CAP)
from schemas import RiskCheckRequest

router = APIRouter(prefix="/api/risk", tags=["事件模块 / 决策模块"])


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_level(score: int) -> str:
    if score >= LEVEL_HIGH_THRESHOLD:
        return "high"
    if score >= LEVEL_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def build_assessment_detail(conn: sqlite3.Connection, assessment_id: int) -> dict:
    """组装单次风险检查的完整结果（评分 + 命中规则 + 特征快照）。"""
    assessment = db_module.query_one(
        conn,
        "SELECT a.*, e.event_type, e.source_id, e.user_id AS event_user_id, e.order_id AS event_order_id,"
        " e.event_payload_json FROM risk_assessments a"
        " LEFT JOIN risk_events e ON e.id = a.event_id WHERE a.id=?",
        (assessment_id,),
    )
    if not assessment:
        raise HTTPException(status_code=404, detail=f"风险检查结果 {assessment_id} 不存在")

    # 命中规则：rule_hits 保留历史留痕，规则被删除后回退展示命中信息
    hits = db_module.query_all(
        conn,
        "SELECT h.id, h.rule_id, h.hit_score, h.hit_message, h.created_at,"
        " r.rule_code, r.rule_name, r.priority"
        " FROM rule_hits h LEFT JOIN risk_rules r ON r.id = h.rule_id"
        " WHERE h.assessment_id=? ORDER BY COALESCE(r.priority, 999) ASC, h.id ASC",
        (assessment_id,),
    )
    for hit in hits:
        if not hit.get("rule_name"):
            # 规则已被删除，从命中描述中还原规则名
            message = hit.get("hit_message") or ""
            name = message.split("】：")[0].replace("命中规则【", "") if "】：" in message else "已删除规则"
            hit["rule_name"] = name
            hit["rule_code"] = hit.get("rule_code") or "-"

    snapshot_row = db_module.query_one(
        conn, "SELECT feature_json, created_at FROM feature_snapshots WHERE assessment_id=?", (assessment_id,))
    feature_snapshot = {}
    if snapshot_row:
        try:
            feature_snapshot = json.loads(snapshot_row["feature_json"])
        except json.JSONDecodeError:
            feature_snapshot = {}

    # AI 风险解读：读取首次生成时落库的结果，GET 查询不重复调用大模型
    ai_note = ai_module.load_note(conn, assessment_id)

    case = db_module.query_one(
        conn, "SELECT id, case_status, reviewer_id, review_result FROM risk_cases WHERE assessment_id=?",
        (assessment_id,))

    return {
        "assessment_id": assessment["id"],
        "event_id": assessment["event_id"],
        "event_type": assessment["event_type"],
        "event_type_label": EVENT_TYPE_LABELS.get(assessment["event_type"], assessment["event_type"]),
        "source_id": assessment["source_id"],
        "user_id": assessment["event_user_id"],
        "order_id": assessment["event_order_id"],
        "risk_score": assessment["risk_score"],
        "risk_level": assessment["risk_level"],
        "risk_level_label": RISK_LEVEL_LABELS.get(assessment["risk_level"], ""),
        "decision": assessment["decision"],
        "decision_label": DECISION_LABELS.get(assessment["decision"], ""),
        "assessment_status": assessment["assessment_status"],
        "created_at": assessment["created_at"],
        "rule_hits": hits,
        "hit_count": len(hits),
        "feature_snapshot": feature_snapshot,
        "case_id": case["id"] if case else None,
        "case_status": case["case_status"] if case else None,
        "case_status_label": CASE_STATUS_LABELS.get(case["case_status"], "") if case else None,
        "reviewer_id": case["reviewer_id"] if case else None,
        "review_result": case["review_result"] if case else None,
        "ai_enabled": ai_module.configured(),
        "ai_provider": (ai_note or {}).get("provider"),
        "ai_model": (ai_note or {}).get("model"),
        "ai_generated_at": (ai_note or {}).get("created_at"),
        "ai_explanation": (ai_note or {}).get("payload"),
    }


@router.post("/check", summary="发起风险检查")
def risk_check(payload: RiskCheckRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    # ---------- 1. 入参校验 ----------
    if payload.event_type not in EVENT_TYPES:
        raise HTTPException(status_code=400,
                            detail=f"event_type 仅支持：{'、'.join(EVENT_TYPES)}")

    user = db_module.query_one(conn, "SELECT * FROM users WHERE user_no=?", (payload.user_id,)) \
        if payload.user_id else None
    if payload.user_id and not user:
        raise HTTPException(status_code=404, detail=f"用户 {payload.user_id} 不存在")

    order = db_module.query_one(conn, "SELECT * FROM orders WHERE order_no=?", (payload.order_id,)) \
        if payload.order_id else None
    if payload.order_id and not order:
        raise HTTPException(status_code=404, detail=f"订单 {payload.order_id} 不存在")

    if not user and not order:
        raise HTTPException(status_code=400, detail="user_id 与 order_id 至少提供一个有效值")

    # ---------- 2. 写入事件记录（保留原始入参） ----------
    now = _now()
    payload_json = {
        "event_type": payload.event_type,
        "source_id": payload.source_id,
        "user_id": payload.user_id,
        "order_id": payload.order_id,
        "event_payload": payload.event_payload or {},
        # 附带业务上下文，便于问题排查
        "context": {
            "order_amount": order["amount"] if order else None,
            "order_category": order["category"] if order else None,
            "address_id": order["address_id"] if order else None,
            "device_ip": order["device_ip"] if order else None,
            "received_at": now,
        },
    }
    event_id = db_module.insert_returning_id(
        conn,
        "INSERT INTO risk_events (event_type, source_id, user_id, order_id, event_payload_json, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (payload.event_type, payload.source_id, payload.user_id, payload.order_id,
         json.dumps(payload_json, ensure_ascii=False), now),
    )

    # ---------- 3. 特征计算 + 快照 ----------
    snapshot = features_module.compute_features(conn, payload.event_type, payload.user_id, payload.order_id)

    # ---------- 4. 规则匹配 ----------
    hits = rules_module.match_rules(conn, snapshot)

    # ---------- 5. 评分 / 等级 / 处理建议 ----------
    risk_score = min(SCORE_CAP, sum(h["hit_score"] for h in hits))
    risk_level = resolve_level(risk_score)
    decision = LEVEL_DECISION_MAP[risk_level]

    assessment_id = db_module.insert_returning_id(
        conn,
        "INSERT INTO risk_assessments (event_id, risk_score, risk_level, decision, assessment_status, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (event_id, risk_score, risk_level, decision, "completed", now),
    )
    db_module.execute(
        conn,
        "INSERT INTO feature_snapshots (assessment_id, feature_json, created_at) VALUES (?,?,?)",
        (assessment_id, json.dumps(snapshot, ensure_ascii=False, default=str), now),
    )
    if hits:
        conn.executemany(
            "INSERT INTO rule_hits (assessment_id, rule_id, hit_score, hit_message, created_at) VALUES (?,?,?,?,?)",
            [(assessment_id, h["rule_id"], h["hit_score"], h["hit_message"], now) for h in hits],
        )
        conn.commit()

    # ---------- 6. 自动建案 ----------
    case_id, case_status = None, None
    if risk_level == "high" or decision in AUTO_CASE_DECISIONS:
        case_status = CASE_STATUS_BY_DECISION[decision]
        case_id = db_module.insert_returning_id(
            conn,
            "INSERT INTO risk_cases (assessment_id, user_id, order_id, case_status, reviewer_id, review_result,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (assessment_id, payload.user_id, payload.order_id, case_status, None, None, now, now),
        )
        db_module.execute(
            conn,
            "INSERT INTO review_logs (case_id, operator_id, action_type, action_remark, created_at) VALUES (?,?,?,?,?)",
            (case_id, "系统", "create",
             f"风险等级 {RISK_LEVEL_LABELS[risk_level]}（评分 {risk_score}），处理建议"
             f"{DECISION_LABELS[decision]}，系统自动创建案件", now),
        )

    detail = build_assessment_detail(conn, assessment_id)

    # ---------- 7. AI 风险解读（只做解读与处置建议，不改动评分与决策结论） ----------
    # 未配置大模型凭据或调用失败时，本步骤自动回落规则模板文案，不影响主流程
    ai_module.generate_for_assessment(conn, assessment_id, ai_module.context_from_detail(detail))
    detail = build_assessment_detail(conn, assessment_id)
    detail["message"] = f"风险检查完成：评分 {risk_score}，风险等级 {RISK_LEVEL_LABELS[risk_level]}"
    return detail


@router.get("/assessments/{assessment_id}", summary="查询风险检查结果")
def get_assessment(assessment_id: int, conn: sqlite3.Connection = Depends(db_module.get_db)):
    return build_assessment_detail(conn, assessment_id)


@router.post("/assessments/{assessment_id}/ai-explain", summary="重新生成 AI 风险解读")
def refresh_ai_explanation(assessment_id: int,
                           conn: sqlite3.Connection = Depends(db_module.get_db)):
    """按需重新调用大模型解读（默认 GET 复用首次落库结果，不重复消耗 token）。"""
    detail = build_assessment_detail(conn, assessment_id)
    ai_module.generate_for_assessment(conn, assessment_id, ai_module.context_from_detail(detail))
    return build_assessment_detail(conn, assessment_id)


@router.get("/events", summary="查询风险事件列表")
def list_events(page: int = 1, page_size: int = 20, event_type: Optional[str] = None,
                user_id: Optional[str] = None, risk_level: Optional[str] = None,
                conn: sqlite3.Connection = Depends(db_module.get_db)):
    """事件接入记录查询，支持按事件类型 / 用户 / 风险等级过滤。"""
    where, params = " WHERE 1=1", []
    if event_type:
        where += " AND e.event_type=?"
        params.append(event_type)
    if user_id:
        where += " AND e.user_id=?"
        params.append(user_id)
    if risk_level:
        where += " AND a.risk_level=?"
        params.append(risk_level)

    base = ("FROM risk_events e LEFT JOIN risk_assessments a ON a.event_id = e.id" + where)
    total = db_module.query_scalar(conn, f"SELECT COUNT(*) {base}", params, 0)
    rows = db_module.query_all(
        conn,
        "SELECT e.id, e.event_type, e.source_id, e.user_id, e.order_id, e.created_at,"
        " a.id AS assessment_id, a.risk_score, a.risk_level, a.decision"
        f" {base} ORDER BY e.id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    )
    for row in rows:
        row["event_type_label"] = EVENT_TYPE_LABELS.get(row["event_type"], row["event_type"])
        row["risk_level_label"] = RISK_LEVEL_LABELS.get(row["risk_level"], "")
        row["decision_label"] = DECISION_LABELS.get(row["decision"], "")
    return {"total": total, "page": page, "page_size": page_size, "list": rows}
