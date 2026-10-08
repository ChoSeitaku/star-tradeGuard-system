"""画像模块：用户画像聚合查询（历史订单、退款、投诉、地址、风险事件、关联案件）。"""
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

import db as db_module
from config import CASE_STATUS_LABELS, DECISION_LABELS, EVENT_TYPE_LABELS, RISK_LEVEL_LABELS

router = APIRouter(prefix="/api/risk/users", tags=["画像模块"])


def _cutoff(**kwargs) -> str:
    return (datetime.now() - timedelta(**kwargs)).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/{user_id}/profile", summary="查询用户画像")
def get_profile(user_id: str, conn: sqlite3.Connection = Depends(db_module.get_db)):
    # 兼容 user_no（U1001）与自增主键（1）两种查询方式
    user = db_module.query_one(conn, "SELECT * FROM users WHERE user_no=?", (user_id,))
    if not user and str(user_id).isdigit():
        user = db_module.query_one(conn, "SELECT * FROM users WHERE id=?", (int(user_id),))
    if not user:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

    uid, uno = user["id"], user["user_no"]

    orders = db_module.query_all(
        conn,
        "SELECT o.order_no, o.category, o.amount, o.items_count, o.device_ip, o.status, o.created_at,"
        " a.detail AS address_detail"
        " FROM orders o LEFT JOIN addresses a ON a.id = o.address_id"
        " WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT 10", (uid,))
    total_orders = db_module.query_scalar(conn, "SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), 0)
    refund_count = db_module.query_scalar(conn, "SELECT COUNT(*) FROM refunds WHERE user_id=?", (uid,), 0)
    complaint_count = db_module.query_scalar(conn, "SELECT COUNT(*) FROM complaints WHERE user_id=?", (uid,), 0)
    address_count = db_module.query_scalar(conn, "SELECT COUNT(*) FROM addresses WHERE user_id=?", (uid,), 0)
    paid_total = db_module.query_scalar(conn, "SELECT SUM(amount) FROM payments WHERE user_id=?", (uid,), 0.0) or 0.0
    login_ip_count = db_module.query_scalar(
        conn, "SELECT COUNT(DISTINCT ip) FROM user_logins WHERE user_id=? AND login_time>=?",
        (uid, _cutoff(days=30)), 0)

    # 最近风险事件
    risk_events = db_module.query_all(
        conn,
        "SELECT e.id AS event_id, e.event_type, e.source_id, e.order_id, e.created_at,"
        " a.id AS assessment_id, a.risk_score, a.risk_level, a.decision,"
        " (SELECT COUNT(*) FROM rule_hits h WHERE h.assessment_id = a.id) AS hit_count"
        " FROM risk_events e LEFT JOIN risk_assessments a ON a.event_id = e.id"
        " WHERE e.user_id=? ORDER BY e.id DESC LIMIT 10", (uno,))
    for ev in risk_events:
        ev["event_type_label"] = EVENT_TYPE_LABELS.get(ev["event_type"], ev["event_type"])
        ev["risk_level_label"] = RISK_LEVEL_LABELS.get(ev["risk_level"], "")
        ev["decision_label"] = DECISION_LABELS.get(ev["decision"], "")

    # 关联案件
    cases = db_module.query_all(
        conn,
        "SELECT c.id AS case_id, c.order_id, c.case_status, c.reviewer_id, c.review_result,"
        " c.created_at, c.updated_at, a.risk_level, a.risk_score"
        " FROM risk_cases c LEFT JOIN risk_assessments a ON a.id = c.assessment_id"
        " WHERE c.user_id=? ORDER BY c.id DESC LIMIT 10", (uno,))
    for case in cases:
        case["case_status_label"] = CASE_STATUS_LABELS.get(case["case_status"], case["case_status"])
        case["risk_level_label"] = RISK_LEVEL_LABELS.get(case["risk_level"], "")

    refund_ratio = round(refund_count / max(1, total_orders), 4)
    rejected_count = db_module.query_scalar(
        conn,
        "SELECT COUNT(*) FROM risk_assessments a JOIN risk_events e ON e.id = a.event_id"
        " WHERE e.user_id=? AND a.decision='reject'", (uno,), 0)

    registered = user["registered_at"][:10] if user["registered_at"] else ""
    return {
        "user_id": uno,
        "username": user["username"],
        "phone": user["phone"],
        "email": user["email"],
        "level": user["level"],
        "status": user["status"],
        "registered_at": registered,
        "summary": {
            "total_orders": total_orders,
            "refund_count": refund_count,
            "complaint_count": complaint_count,
            "address_count": address_count,
            "paid_amount_total": round(float(paid_total), 2),
            "login_ip_count_30d": login_ip_count,
            "refund_ratio": refund_ratio,
            "rejected_count": rejected_count,
        },
        # 画像雷达图指标（value/max 便于前端归一化）
        "profile_metrics": [
            {"key": "total_orders", "label": "历史订单数", "value": total_orders, "max": max(total_orders, 12)},
            {"key": "refund_count", "label": "退款次数", "value": refund_count, "max": max(refund_count, 8)},
            {"key": "complaint_count", "label": "投诉次数", "value": complaint_count, "max": max(complaint_count, 5)},
            {"key": "address_count", "label": "收货地址数", "value": address_count, "max": max(address_count, 6)},
            {"key": "login_ip_count_30d", "label": "登录IP数", "value": login_ip_count, "max": max(login_ip_count, 6)},
            {"key": "rejected_count", "label": "历史拒绝次数", "value": rejected_count, "max": max(rejected_count, 4)},
        ],
        "recent_orders": orders,
        "recent_risk_events": risk_events,
        "related_cases": cases,
    }
