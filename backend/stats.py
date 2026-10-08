"""统计模块：运营看板指标计算（总量、占比、处理效率、排行、趋势）。"""
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

import db as db_module
from config import (CASE_STATUS_LABELS, CASE_STATUSES, DECISION_LABELS, EVENT_TYPES, EVENT_TYPE_LABELS,
                    RISK_LEVEL_LABELS)

router = APIRouter(prefix="/api/risk", tags=["统计模块"])


def _date_list(days: int = 7) -> list[str]:
    today = datetime.now().date()
    return [(today - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days - 1, -1, -1)]


@router.get("/dashboard", summary="查询运营看板统计")
def dashboard(days: int = 7, conn: sqlite3.Connection = Depends(db_module.get_db)):
    # ---------- 风险事件总数（按事件类型） ----------
    total_events = db_module.query_scalar(conn, "SELECT COUNT(*) FROM risk_events", (), 0)
    type_rows = db_module.query_all(
        conn, "SELECT event_type, COUNT(*) AS cnt FROM risk_events GROUP BY event_type")
    type_map = {r["event_type"]: r["cnt"] for r in type_rows}
    event_type_stat = [{"event_type": t, "label": EVENT_TYPE_LABELS[t], "count": type_map.get(t, 0)}
                       for t in EVENT_TYPES]

    # ---------- 风险等级与处理建议分布 ----------
    total_assessments = db_module.query_scalar(conn, "SELECT COUNT(*) FROM risk_assessments", (), 0)
    level_rows = db_module.query_all(
        conn, "SELECT risk_level, COUNT(*) AS cnt FROM risk_assessments GROUP BY risk_level")
    level_map = {r["risk_level"]: r["cnt"] for r in level_rows}
    risk_level_stat = [{"risk_level": lv, "label": RISK_LEVEL_LABELS[lv], "count": level_map.get(lv, 0)}
                       for lv in ("high", "medium", "low")]

    decision_rows = db_module.query_all(
        conn, "SELECT decision, COUNT(*) AS cnt FROM risk_assessments GROUP BY decision")
    decision_map = {r["decision"]: r["cnt"] for r in decision_rows}
    decision_stat = [{"decision": d, "label": DECISION_LABELS[d], "count": decision_map.get(d, 0)}
                     for d in ("pass", "manual_review", "reject")]

    high_count = level_map.get("high", 0)
    high_ratio = round(high_count / total_assessments * 100, 1) if total_assessments else 0.0
    avg_score = db_module.query_scalar(conn, "SELECT AVG(risk_score) FROM risk_assessments", (), 0) or 0

    # ---------- 案件处理效率 ----------
    total_cases = db_module.query_scalar(conn, "SELECT COUNT(*) FROM risk_cases", (), 0)
    case_status_rows = db_module.query_all(
        conn, "SELECT case_status, COUNT(*) AS cnt FROM risk_cases GROUP BY case_status")
    case_status_map = {r["case_status"]: r["cnt"] for r in case_status_rows}
    case_status_stat = [{"case_status": s, "label": CASE_STATUS_LABELS[s], "count": case_status_map.get(s, 0)}
                        for s in CASE_STATUSES]
    handled_cases = sum(case_status_map.get(s, 0) for s in ("approved", "rejected", "resolved"))
    handled_ratio = round(handled_cases / total_cases * 100, 1) if total_cases else 0.0
    avg_hours = db_module.query_scalar(
        conn,
        "SELECT AVG((julianday(updated_at) - julianday(created_at)) * 24.0) FROM risk_cases"
        " WHERE reviewer_id IS NOT NULL AND updated_at > created_at", (), 0) or 0
    review_action_count = db_module.query_scalar(
        conn, "SELECT COUNT(*) FROM review_logs WHERE action_type IN ('review','resolve')", (), 0)

    # ---------- 规则命中排行 ----------
    rule_rank = db_module.query_all(
        conn,
        "SELECT COALESCE(r.rule_code, '-') AS rule_code,"
        " COALESCE(r.rule_name, '已删除规则') AS rule_name,"
        " COUNT(*) AS hit_count, SUM(h.hit_score) AS total_score"
        " FROM rule_hits h LEFT JOIN risk_rules r ON r.id = h.rule_id"
        " GROUP BY h.rule_id, rule_code, rule_name"
        " ORDER BY hit_count DESC, total_score DESC LIMIT 10",
    )
    max_hit = max([r["hit_count"] for r in rule_rank], default=0)
    for item in rule_rank:
        item["ratio"] = round(item["hit_count"] / max_hit * 100, 1) if max_hit else 0.0

    # ---------- 黑名单命中次数 ----------
    blacklist_hit_count = db_module.query_scalar(
        conn,
        "SELECT COUNT(*) FROM rule_hits h JOIN risk_rules r ON r.id = h.rule_id"
        " WHERE r.rule_code LIKE 'R_BLACKLIST%'", (), 0)
    blacklist_by_rule = db_module.query_all(
        conn,
        "SELECT r.rule_name, COUNT(*) AS hit_count FROM rule_hits h JOIN risk_rules r ON r.id = h.rule_id"
        " WHERE r.rule_code LIKE 'R_BLACKLIST%' GROUP BY r.id, r.rule_name ORDER BY hit_count DESC",
    )
    blacklist_total = db_module.query_scalar(
        conn, "SELECT COUNT(*) FROM blacklists WHERE status='active'", (), 0)

    # ---------- 近 N 天趋势 ----------
    dates = _date_list(days)
    since = dates[0]
    trend_rows = db_module.query_all(
        conn,
        "SELECT date(created_at) AS d, COUNT(*) AS total,"
        " SUM(CASE WHEN risk_level='high' THEN 1 ELSE 0 END) AS high,"
        " SUM(CASE WHEN risk_level='medium' THEN 1 ELSE 0 END) AS medium,"
        " SUM(CASE WHEN risk_level='low' THEN 1 ELSE 0 END) AS low"
        " FROM risk_assessments WHERE date(created_at) >= ? GROUP BY date(created_at)", (since,))
    trend_map = {r["d"]: r for r in trend_rows}
    trend = [{
        "date": d,
        "total": (trend_map.get(d) or {}).get("total", 0) or 0,
        "high": (trend_map.get(d) or {}).get("high", 0) or 0,
        "medium": (trend_map.get(d) or {}).get("medium", 0) or 0,
        "low": (trend_map.get(d) or {}).get("low", 0) or 0,
    } for d in dates]

    return {
        "overview": {
            "total_events": total_events,
            "total_assessments": total_assessments,
            "high_risk_count": high_count,
            "high_risk_ratio": high_ratio,
            "avg_risk_score": round(float(avg_score), 1),
            "total_cases": total_cases,
            "handled_cases": handled_cases,
            "handled_ratio": handled_ratio,
            "avg_handle_hours": round(float(avg_hours), 2),
            "review_action_count": review_action_count,
            "blacklist_hit_count": blacklist_hit_count,
            "active_blacklist_count": blacklist_total,
        },
        "event_type_stat": event_type_stat,
        "risk_level_stat": risk_level_stat,
        "decision_stat": decision_stat,
        "case_status_stat": case_status_stat,
        "rule_rank": rule_rank,
        "blacklist_stat": {
            "total_hit": blacklist_hit_count,
            "active_count": blacklist_total,
            "by_rule": blacklist_by_rule,
        },
        "trend": trend,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
