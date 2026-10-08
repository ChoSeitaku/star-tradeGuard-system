"""黑名单模块：列表查询、新增、删除、批量导入。

黑名单在风险检查中实时生效（user / address / ip 三类参与特征计算），
因此增删黑名单会直接影响后续风险检查的评分结果。
"""
import sqlite3
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

import db as db_module
from config import BLACKLIST_TYPE_LABELS, BLACKLIST_TYPES
from schemas import BlacklistCreateRequest, BlacklistDeleteRequest

router = APIRouter(prefix="/api/risk/blacklists", tags=["黑名单模块"])


def _to_dict(row: dict) -> dict:
    row["blacklist_type_label"] = BLACKLIST_TYPE_LABELS.get(row["blacklist_type"], row["blacklist_type"])
    row["status_label"] = "生效中" if row["status"] == "active" else "已停用"
    return row


@router.get("", summary="查询黑名单列表")
@router.get("/", include_in_schema=False)
def list_blacklists(page: int = 1, page_size: int = 20, blacklist_type: Optional[str] = None,
                    keyword: Optional[str] = None, status: Optional[str] = None,
                    conn: sqlite3.Connection = Depends(db_module.get_db)):
    where, params = " WHERE 1=1", []
    if blacklist_type:
        where += " AND blacklist_type=?"
        params.append(blacklist_type)
    if status:
        where += " AND status=?"
        params.append(status)
    if keyword:
        where += " AND (blacklist_value LIKE ? OR remark LIKE ?)"
        params += [f"%{keyword}%"] * 2

    total = db_module.query_scalar(conn, f"SELECT COUNT(*) FROM blacklists{where}", params, 0)
    rows = db_module.query_all(
        conn, f"SELECT * FROM blacklists{where} ORDER BY status='active' DESC, id DESC LIMIT ? OFFSET ?",
        params + [page_size, (page - 1) * page_size])
    type_stat = {t: db_module.query_scalar(
        conn, "SELECT COUNT(*) FROM blacklists WHERE blacklist_type=? AND status='active'", (t,), 0)
        for t in BLACKLIST_TYPES}
    return {"total": total, "page": page, "page_size": page_size,
            "list": [_to_dict(r) for r in rows], "type_stat": type_stat,
            "types": [{"value": t, "label": BLACKLIST_TYPE_LABELS[t]} for t in BLACKLIST_TYPES]}


def _insert_one(conn: sqlite3.Connection, item: BlacklistCreateRequest, now: str) -> int:
    if item.blacklist_type not in BLACKLIST_TYPES:
        raise HTTPException(status_code=400, detail=f"blacklist_type 仅支持：{'、'.join(BLACKLIST_TYPES)}")
    if not item.blacklist_value or not str(item.blacklist_value).strip():
        raise HTTPException(status_code=400, detail="blacklist_value 不能为空")
    if item.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="status 仅支持 active / disabled")

    exists = db_module.query_one(
        conn, "SELECT id FROM blacklists WHERE blacklist_type=? AND blacklist_value=?",
        (item.blacklist_type, str(item.blacklist_value).strip()))
    if exists:
        raise HTTPException(status_code=400,
                            detail=f"黑名单已存在：{BLACKLIST_TYPE_LABELS[item.blacklist_type]} {item.blacklist_value}")
    return db_module.insert_returning_id(
        conn,
        "INSERT INTO blacklists (blacklist_type, blacklist_value, remark, status, created_at) VALUES (?,?,?,?,?)",
        (item.blacklist_type, str(item.blacklist_value).strip(), item.remark, item.status, now),
    )


@router.post("", summary="新增黑名单")
@router.post("/", include_in_schema=False)
def create_blacklist(payload: BlacklistCreateRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_id = _insert_one(conn, payload, now)
    return {"id": new_id, "message": f"黑名单新增成功：{payload.blacklist_value}"}


@router.post("/delete", summary="删除黑名单")
def delete_blacklist(payload: BlacklistDeleteRequest, conn: sqlite3.Connection = Depends(db_module.get_db)):
    item = db_module.query_one(conn, "SELECT * FROM blacklists WHERE id=?", (payload.id,))
    if not item:
        raise HTTPException(status_code=404, detail=f"黑名单 {payload.id} 不存在")
    db_module.execute(conn, "DELETE FROM blacklists WHERE id=?", (payload.id,))
    return {"id": payload.id,
            "message": f"黑名单已删除：{item['blacklist_value']}（后续风险检查将不再命中该条目）"}


@router.post("/batch", summary="批量导入黑名单")
def batch_import(payload: Any = Body(...), conn: sqlite3.Connection = Depends(db_module.get_db)):
    """支持两种入参：
       {"items":[{"blacklist_type":"user","blacklist_value":"U2001","remark":"..."}]}
       {"text":"user,U2001,备注\\nip,1.2.3.4,备注"}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    items: list[BlacklistCreateRequest] = []

    if isinstance(payload, dict) and payload.get("text"):
        for lineno, raw in enumerate(str(payload["text"]).splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.replace("\t", ",").split(",")]
            if len(parts) < 2:
                raise HTTPException(status_code=400, detail=f"第 {lineno} 行格式错误，应为：类型,值,备注")
            items.append(BlacklistCreateRequest(
                blacklist_type=parts[0], blacklist_value=parts[1],
                remark=parts[2] if len(parts) > 2 else "批量导入"))
    elif isinstance(payload, dict) and payload.get("items"):
        items = [BlacklistCreateRequest(**it) for it in payload["items"]]
    else:
        raise HTTPException(status_code=400, detail="请提供 items 数组或 text 文本")

    if not items:
        raise HTTPException(status_code=400, detail="没有可导入的数据")

    success, skipped = 0, []
    for item in items:
        try:
            _insert_one(conn, item, now)
            success += 1
        except HTTPException as exc:
            skipped.append(f"{item.blacklist_type}:{item.blacklist_value} - {exc.detail}")
    return {"success_count": success, "skipped_count": len(skipped), "skipped": skipped,
            "message": f"批量导入完成：成功 {success} 条，跳过 {len(skipped)} 条"}
