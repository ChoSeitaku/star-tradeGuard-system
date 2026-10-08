"""案件模块：案件列表、案件详情、人工审核、审核日志留痕。"""
import sqlite3
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

import db as db_module
from config import (CASE_STATUS_LABELS, CASE_STATUSES, DECISION_LABELS, EVENT_TYPE_LABELS,
                    REVIEW_RESULT_CASE_STATUS, RISK_LEVEL_LABELS)
from decision import build_assessment_detail
from schemas import CaseReviewRequest

router = APIRouter(prefix="/api/risk/cases", tags=["案件模块"])

REVIEW_RESULT_LABELS = {"approve": "审核通过", "reject": "审核拒绝", "resolve": "结案归档"}


@router.get("", summary="查询案件列表")
@router.get("/", include_in_schema=False)
def list_cases(page: int = 1, page_size: int = 20, case_status: Optional[str] = None,
               risk_level: Optional[str] = None, user_id: Optional[str] = None,
               order_id: Optional[str] = None, keyword: Optional[str] = None,
               conn: sqlite3.Connection = Depends(db_module.get_db)):
    where, params = " WHERE 1=1", []
    if case_status:
        where += " AND c.case_status=?"
        params.append(case_status)
    if risk_level:
        where += " AND a.risk_level=?"
        params.append(risk_level)
    if user_id:
        where += " AND c.user_id=?"
        params.append(user_id)
    if order_id:
        where += " AND c.order_id=?"
        params.append(order_id)
    if keyword:
        where += " AND (c.user_id LIKE ? OR c.order_id LIKE ? OR c.reviewer_id LIKE ?)"
        params += [f"%{keyword}%"] * 3

    base = ("FROM risk_cases c"
            " LEFT JOIN risk_assessments a ON a.id = c.assessment_id"
            " LEFT JOIN risk_events e ON e.id = a.event_id" + where)
    total = db_module.query_scalar(conn, f"SELECT COUNT(*) {base}", params, 0)
    rows = db_module.query_all(
        conn,
        "SELECT c.id, c.assessment_id, c.user_id, c.order_id, c.case_status, c.reviewer_id,"
        " c.review_result, c.created_at, c.updated_at,"
        " a.risk_score, a.risk_level, a.decision, e.event_type"
        f" {base} ORDER BY c.id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size],
    )
    for row in rows:
        row["case_status_label"] = CASE_STATUS_LABELS.get(row["case_status"], row["case_status"])
        row["risk_level_label"] = RISK_LEVEL_LABELS.get(row["risk_level"], "")
        row["decision_label"] = DECISION_LABELS.get(row["decision"], "")
        row["event_type_label"] = EVENT_TYPE_LABELS.get(row["event_type"], row["event_type"] or "")

    status_stat = {s: db_module.query_scalar(
        conn, "SELECT COUNT(*) FROM risk_cases WHERE case_status=?", (s,), 0) for s in CASE_STATUSES}
    return {"total": total, "page": page, "page_size": page_size, "list": rows, "status_stat": status_stat}


@router.get("/{case_id}", summary="查询案件详情")
def get_case(case_id: int, conn: sqlite3.Connection = Depends(db_module.get_db)):
    case = db_module.query_one(conn, "SELECT * FROM risk_cases WHERE id=?", (case_id,))
    if not case:
        raise HTTPException(status_code=404, detail=f"案件 {case_id} 不存在")

    detail = build_assessment_detail(conn, case["assessment_id"])

    logs = db_module.query_all(
        conn,
        "SELECT id, case_id, operator_id, action_type, action_remark, created_at"
        " FROM review_logs WHERE case_id=? ORDER BY id ASC",
        (case_id,),
    )
    action_labels = {"create": "创建案件", "review": "人工审核", "resolve": "结案归档"}
    for log in logs:
        log["action_type_label"] = action_labels.get(log["action_type"], log["action_type"])

    user = db_module.query_one(
        conn, "SELECT user_no, username, phone, level, status FROM users WHERE user_no=?", (case["user_id"],))

    return {
        "case_id": case["id"],
        "case_status": case["case_status"],
        "case_status_label": CASE_STATUS_LABELS.get(case["case_status"], case["case_status"]),
        "reviewer_id": case["reviewer_id"],
        "review_result": case["review_result"],
        "review_result_label": REVIEW_RESULT_LABELS.get(case["review_result"], case["review_result"] or ""),
        "created_at": case["created_at"],
        "updated_at": case["updated_at"],
        "user_id": case["user_id"],
        "order_id": case["order_id"],
        "user_info": user,
        # 风险结果 + 命中规则 + 特征快照
        "assessment": detail,
        # 审核记录（处理结论留痕）
        "review_logs": logs,
    }


@router.post("/review", summary="提交人工审核")
def review_case(payload: CaseReviewRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    case = db_module.query_one(conn, "SELECT * FROM risk_cases WHERE id=?", (payload.case_id,))
    if not case:
        raise HTTPException(status_code=404, detail=f"案件 {payload.case_id} 不存在")

    if payload.review_result not in REVIEW_RESULT_CASE_STATUS:
        raise HTTPException(status_code=400,
                            detail="review_result 仅支持 approve（通过）/ reject（拒绝）/ resolve（结案）")

    if case["case_status"] in ("resolved",):
        raise HTTPException(status_code=400, detail="该案件已结案，无法重复处理")

    new_status = REVIEW_RESULT_CASE_STATUS[payload.review_result]
    operator = payload.reviewer_id or "风控审核员"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db_module.execute(
        conn,
        "UPDATE risk_cases SET case_status=?, reviewer_id=?, review_result=?, updated_at=? WHERE id=?",
        (new_status, operator, payload.review_result, now, payload.case_id),
    )
    db_module.execute(
        conn,
        "INSERT INTO review_logs (case_id, operator_id, action_type, action_remark, created_at) VALUES (?,?,?,?,?)",
        (payload.case_id, operator,
         "resolve" if payload.review_result == "resolve" else "review",
         payload.review_remark or REVIEW_RESULT_LABELS[payload.review_result], now),
    )
    return {
        "case_id": payload.case_id,
        "case_status": new_status,
        "case_status_label": CASE_STATUS_LABELS.get(new_status, new_status),
        "reviewer_id": operator,
        "review_result": payload.review_result,
        "message": f"案件 {payload.case_id} 已{REVIEW_RESULT_LABELS[payload.review_result]}",
    }
