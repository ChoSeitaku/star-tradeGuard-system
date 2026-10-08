"""SQLite 访问层：连接管理 + 常用查询辅助函数。

演示环境使用 Python 标准库 sqlite3，无需安装数据库服务。
生产环境可替换为 MySQL（见 sql/schema.sql），接口层无需改动。
"""
import sqlite3
from typing import Any, Iterable, Optional

from config import DB_PATH, DATA_DIR


def get_conn() -> sqlite3.Connection:
    """创建一个新的数据库连接（每个请求一个，避免线程问题）。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI 依赖：请求级连接，自动关闭。"""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def query_all(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def query_one(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> Optional[dict]:
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def query_scalar(conn: sqlite3.Connection, sql: str, params: Iterable = (), default: Any = 0) -> Any:
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None or row[0] is None:
        return default
    return row[0]


def execute(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur


def insert_returning_id(conn: sqlite3.Connection, sql: str, params: Iterable = ()) -> int:
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return int(cur.lastrowid)
