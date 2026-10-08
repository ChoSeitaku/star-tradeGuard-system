"""规则模块：条件求值引擎 + 规则增删改查 / 启停用接口。

condition_json 结构：
    {
      "all": [ {"op": "gte", "feature": "order_amount", "value": 5000}, ... ],
      "any": [ {"op": "eq",  "feature": "order_status", "value": "已退款"}, ... ]
    }
    * all：全部叶子命中才算命中（与）
    * any：任意叶子命中即算命中（或）
    * 两者同时存在时，需同时满足 all 组与 any 组
    * 叶子亦可嵌套子条件组，实现多层与或组合

支持的运算符：gt / gte / lt / lte / eq / neq / contains
    contains 语义为「列表成员判断」，如 order_category ∈ ["虚拟卡券","数码3C"]
"""
import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

import db as db_module
from features import FEATURE_META
from schemas import RuleDeleteRequest, RuleStatusRequest, RuleUpdateRequest, RuleUpsertRequest

router = APIRouter(prefix="/api/risk/rules", tags=["规则模块"])

OPERATORS = ["gt", "gte", "lt", "lte", "eq", "neq", "contains"]
OPERATOR_LABELS = {"gt": "大于", "gte": "大于等于", "lt": "小于", "lte": "小于等于",
                   "eq": "等于", "neq": "不等于", "contains": "包含"}


# ============================================================================
# 条件求值引擎
# ============================================================================
def _as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def evaluate_leaf(leaf: dict, features: dict) -> bool:
    """对单个条件叶子求值。特征值为 None（数据缺失）时一律不命中。"""
    op = leaf.get("op")
    key = leaf.get("feature")
    expected = leaf.get("value")
    actual = features.get(key)

    if actual is None:
        return False

    if op == "contains":
        candidates = expected if isinstance(expected, list) else [expected]
        if isinstance(actual, (list, tuple, set)):
            return any(item in candidates for item in actual)
        return actual in candidates

    if op == "eq":
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return float(actual) == float(expected)
        return str(actual) == str(expected)

    if op == "neq":
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return float(actual) != float(expected)
        return str(actual) != str(expected)

    left, right = _as_number(actual), _as_number(expected)
    if left is None or right is None:
        return False
    if op == "gt":
        return left > right
    if op == "gte":
        return left >= right
    if op == "lt":
        return left < right
    if op == "lte":
        return left <= right
    return False


def evaluate_group(node: Any, features: dict) -> bool:
    """递归求值条件组。"""
    if isinstance(node, list):
        return all(evaluate_group(item, features) for item in node)
    if not isinstance(node, dict):
        return False

    if "op" in node and "feature" in node:
        return evaluate_leaf(node, features)

    results = []
    if "all" in node:
        group = node["all"]
        group = group if isinstance(group, list) else [group]
        results.append(all(evaluate_group(item, features) for item in group))
    if "any" in node:
        group = node["any"]
        group = group if isinstance(group, list) else [group]
        results.append(any(evaluate_group(item, features) for item in group))
    return all(results) if results else False


def parse_condition(condition_json: Any) -> dict:
    if isinstance(condition_json, str):
        try:
            return json.loads(condition_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"condition_json 不是合法 JSON：{exc}") from exc
    return condition_json or {}


def validate_condition(condition: Any, errors: list) -> None:
    """校验条件结构，便于管理页给出明确报错。"""
    if isinstance(condition, list):
        for item in condition:
            validate_condition(item, errors)
        return
    if not isinstance(condition, dict):
        errors.append("条件必须是对象或数组")
        return
    if "feature" in condition:
        if condition["feature"] not in FEATURE_META:
            errors.append(f"未知特征：{condition['feature']}")
        if condition.get("op") not in OPERATORS:
            errors.append(f"不支持的运算符：{condition.get('op')}")
        return
    if "all" not in condition and "any" not in condition:
        errors.append("条件组必须包含 all 或 any")
        return
    for key in ("all", "any"):
        if key in condition:
            group = condition[key]
            if not isinstance(group, list):
                errors.append(f"{key} 必须是数组")
                continue
            for item in group:
                validate_condition(item, errors)


def match_rules(conn: sqlite3.Connection, features: dict) -> list[dict]:
    """按优先级顺序匹配所有启用规则，返回命中列表。"""
    rules = db_module.query_all(
        conn,
        "SELECT * FROM risk_rules WHERE rule_status='enabled' ORDER BY priority ASC, id ASC",
    )
    hits = []
    for rule in rules:
        try:
            condition = json.loads(rule["condition_json"])
        except json.JSONDecodeError:
            continue
        if evaluate_group(condition, features):
            hits.append({
                "rule_id": rule["id"],
                "rule_code": rule["rule_code"],
                "rule_name": rule["rule_name"],
                "hit_score": rule["score"],
                "hit_message": build_hit_message(rule, condition, features),
            })
    return hits


_VALUE_LABELS = {"event_type": "事件类型", "order_status": "订单状态", "order_category": "商品类目"}


def _fmt_number(value: Any) -> Any:
    """整数浮点去掉多余小数位，让命中原因更易读（6000.0 → 6000）。"""
    if isinstance(value, bool) or not isinstance(value, float):
        return value
    return int(value) if value.is_integer() else value


def _describe_leaf(leaf: dict, features: dict) -> str:
    key = leaf.get("feature")
    label = FEATURE_META.get(key, (key, ""))[0]
    actual = _fmt_number(features.get(key))
    op = leaf.get("op")
    expected = _fmt_number(leaf.get("value"))
    if op == "contains":
        expected = "、".join(expected if isinstance(expected, list) else [expected])
        return f"{label}={actual} 属于 [{expected}]"
    if op == "eq":
        return f"{label}={actual}"
    if op == "neq":
        return f"{label}={actual}（不为 {expected}）"
    return f"{label}={actual} {OPERATOR_LABELS.get(op, op)} {expected}"


def build_hit_message(rule: dict, condition: Any, features: dict) -> str:
    """生成可读的命中原因：规则名 + 命中条件明细。"""
    details: list[str] = []

    def walk(node: Any, joiner: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, joiner)
            return
        if not isinstance(node, dict):
            return
        if "feature" in node:
            if evaluate_leaf(node, features):
                details.append(_describe_leaf(node, features))
            return
        if "all" in node:
            walk(node["all"], "且")
        if "any" in node:
            walk(node["any"], "或")

    walk(condition, "且")
    detail_text = "；".join(details) if details else "条件命中"
    return f"命中规则【{rule['rule_name']}】：{detail_text}"


# ============================================================================
# 规则管理接口
# ============================================================================
def _rule_to_dict(rule: dict) -> dict:
    item = dict(rule)
    try:
        item["condition"] = json.loads(rule["condition_json"])
    except (json.JSONDecodeError, TypeError):
        item["condition"] = {}
    item["rule_status_label"] = "启用" if rule["rule_status"] == "enabled" else "停用"
    item["hit_count"] = rule.get("hit_count", 0)
    return item


@router.get("", summary="查询规则列表")
@router.get("/", include_in_schema=False)
def list_rules(keyword: Optional[str] = None, rule_status: Optional[str] = None,
               conn: sqlite3.Connection = Depends(db_module.get_db)):
    sql = ("SELECT r.*, (SELECT COUNT(*) FROM rule_hits h WHERE h.rule_id = r.id) AS hit_count "
           "FROM risk_rules r WHERE 1=1")
    params: list[Any] = []
    if keyword:
        sql += " AND (r.rule_name LIKE ? OR r.rule_code LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if rule_status:
        sql += " AND r.rule_status = ?"
        params.append(rule_status)
    sql += " ORDER BY r.priority ASC, r.id ASC"
    rules = [_rule_to_dict(r) for r in db_module.query_all(conn, sql, params)]
    return {"total": len(rules), "list": rules,
            "operators": [{"op": op, "label": OPERATOR_LABELS[op]} for op in OPERATORS],
            "features": [{"feature_key": k, "feature_name": v[0], "dimension_label": v[1]}
                         for k, v in FEATURE_META.items()]}


@router.post("", summary="新增规则")
@router.post("/", include_in_schema=False)
def create_rule(payload: RuleUpsertRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    condition = parse_condition(payload.condition_json)
    errors: list = []
    validate_condition(condition, errors)
    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))

    if db_module.query_one(conn, "SELECT id FROM risk_rules WHERE rule_code=?", (payload.rule_code,)):
        raise HTTPException(status_code=400, detail=f"规则编码 {payload.rule_code} 已存在")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rule_id = db_module.insert_returning_id(
        conn,
        "INSERT INTO risk_rules (rule_code, rule_name, rule_status, priority, score, condition_json, description, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (payload.rule_code, payload.rule_name, payload.rule_status, payload.priority, payload.score,
         json.dumps(condition, ensure_ascii=False), payload.description, now),
    )
    return {"id": rule_id, "message": "规则创建成功"}


@router.post("/update", summary="更新规则")
def update_rule(payload: RuleUpdateRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    if not db_module.query_one(conn, "SELECT id FROM risk_rules WHERE id=?", (payload.id,)):
        raise HTTPException(status_code=404, detail=f"规则 {payload.id} 不存在")

    condition = parse_condition(payload.condition_json)
    errors: list = []
    validate_condition(condition, errors)
    if errors:
        raise HTTPException(status_code=400, detail="；".join(errors))

    dup = db_module.query_one(conn, "SELECT id FROM risk_rules WHERE rule_code=? AND id!=?",
                              (payload.rule_code, payload.id))
    if dup:
        raise HTTPException(status_code=400, detail=f"规则编码 {payload.rule_code} 已被其它规则占用")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_module.execute(
        conn,
        "UPDATE risk_rules SET rule_code=?, rule_name=?, rule_status=?, priority=?, score=?,"
        " condition_json=?, description=?, updated_at=? WHERE id=?",
        (payload.rule_code, payload.rule_name, payload.rule_status, payload.priority, payload.score,
         json.dumps(condition, ensure_ascii=False), payload.description, now, payload.id),
    )
    return {"id": payload.id, "message": "规则更新成功"}


@router.post("/status", summary="启用/停用规则")
def update_rule_status(payload: RuleStatusRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    if payload.rule_status not in ("enabled", "disabled"):
        raise HTTPException(status_code=400, detail="rule_status 仅支持 enabled / disabled")
    rule = db_module.query_one(conn, "SELECT * FROM risk_rules WHERE id=?", (payload.id,))
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {payload.id} 不存在")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_module.execute(conn, "UPDATE risk_rules SET rule_status=?, updated_at=? WHERE id=?",
                      (payload.rule_status, now, payload.id))
    action = "启用" if payload.rule_status == "enabled" else "停用"
    return {"id": payload.id, "rule_status": payload.rule_status, "message": f"规则【{rule['rule_name']}】已{action}"}


@router.post("/delete", summary="删除规则")
def delete_rule(payload: RuleDeleteRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    rule = db_module.query_one(conn, "SELECT * FROM risk_rules WHERE id=?", (payload.id,))
    if not rule:
        raise HTTPException(status_code=404, detail=f"规则 {payload.id} 不存在")
    # 规则删除后，历史命中记录（rule_hits）保留作为留痕；rule_id 置空以保持引用完整性
    db_module.execute(conn, "UPDATE rule_hits SET rule_id=NULL WHERE rule_id=?", (payload.id,))
    db_module.execute(conn, "DELETE FROM risk_rules WHERE id=?", (payload.id,))
    return {"id": payload.id, "message": f"规则【{rule['rule_name']}】已删除，历史命中记录保留"}
