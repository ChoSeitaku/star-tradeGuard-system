"""特征模块：根据业务数据生成风险特征快照（共 25 个特征）。

维度划分：
    用户维度 9 个 / 订单维度 8 个 / 地址维度 7 个 / 事件维度 1 个

约定：
    * 无法计算的项（例如未支付订单的支付特征、无历史订单的金额比值）返回 None，
      规则引擎中 None 一律判定为「不命中」，避免误伤。
    * user_rejected_count 统计该用户历史「拒绝」处置次数时排除当前订单，
      防止同一订单被反复检查后自我强化、导致评分持续上涨。
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

# 特征元信息：key -> (中文名, 维度)，用于前端特征快照的标签渲染
FEATURE_META = {
    # ---- 用户维度 ----
    "user_age_days": ("账号注册天数", "user"),
    "user_orders_30d": ("近30天下单数", "user"),
    "user_paid_amount_30d": ("近30天实付金额", "user"),
    "user_refund_ratio": ("历史退款占比", "user"),
    "user_complaints_90d": ("近90天投诉次数", "user"),
    "user_rejected_count": ("历史拒绝处置次数", "user"),
    "user_blacklisted": ("是否命中用户黑名单", "user"),
    "user_first_order_flag": ("是否首单", "user"),
    "user_login_ip_count_24h": ("24小时登录IP数", "user"),
    # ---- 订单维度 ----
    "order_amount": ("订单金额", "order"),
    "order_items_count": ("订单商品件数", "order"),
    "order_pay_hour": ("支付小时(0-23)", "order"),
    "order_pay_gap_seconds": ("下单到支付秒数", "order"),
    "order_amount_ratio": ("金额与历史均价倍数", "order"),
    "order_after_sale_count": ("本单售后次数", "order"),
    "order_category": ("商品类目", "order"),
    "order_status": ("订单状态", "order"),
    # ---- 地址维度 ----
    "address_blacklisted": ("是否命中地址黑名单", "address"),
    "address_ip_blacklisted": ("是否命中IP黑名单", "address"),
    "address_change_count_7d": ("近7天收货地址数", "address"),
    "address_shared_user_count": ("同地址关联用户数", "address"),
    "address_phone_shared_count": ("同手机号关联用户数", "address"),
    "address_is_new_for_user": ("是否该用户新地址", "address"),
    "address_ip_user_count": ("同IP关联用户数", "address"),
    # ---- 事件维度 ----
    "event_type": ("业务事件类型", "event"),
}

FEATURE_KEYS = list(FEATURE_META.keys())
DIMENSION_LABELS = {"user": "用户维度", "order": "订单维度", "address": "地址维度", "event": "事件维度"}

ABSOLUTE_ZERO = "1970-01-01 00:00:00"


def _q1(conn: sqlite3.Connection, sql: str, params=(), default: Any = None) -> Any:
    row = conn.execute(sql, tuple(params)).fetchone()
    if row is None or row[0] is None:
        return default
    return row[0]


def _cutoff(**kwargs) -> str:
    return (datetime.now() - timedelta(**kwargs)).strftime("%Y-%m-%d %H:%M:%S")


def _parse(ts_value: Optional[str]) -> Optional[datetime]:
    if not ts_value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts_value, fmt)
        except ValueError:
            continue
    return None


def _blacklist_hit(conn: sqlite3.Connection, bl_type: str, value: Optional[str]) -> int:
    """判断某个值是否命中生效中的黑名单。"""
    if value is None or value == "":
        return 0
    return 1 if _q1(
        conn,
        "SELECT id FROM blacklists WHERE blacklist_type=? AND blacklist_value=? AND status='active' LIMIT 1",
        (bl_type, str(value)),
    ) else 0


def compute_features(conn: sqlite3.Connection, event_type: str, user_no: Optional[str],
                     order_no: Optional[str]) -> dict:
    """计算 25 个风险特征，返回键值对字典（特征快照）。"""
    features: dict[str, Any] = {k: None for k in FEATURE_KEYS}
    features["event_type"] = event_type

    user = conn.execute("SELECT * FROM users WHERE user_no=?", (user_no,)).fetchone() if user_no else None
    order = conn.execute("SELECT * FROM orders WHERE order_no=?", (order_no,)).fetchone() if order_no else None
    address = None
    if order is not None and order["address_id"]:
        address = conn.execute("SELECT * FROM addresses WHERE id=?", (order["address_id"],)).fetchone()

    # ================= 用户维度 =================
    if user is not None:
        uid = user["id"]
        registered = _parse(user["registered_at"])
        features["user_age_days"] = max((datetime.now() - registered).days, 0) if registered else None

        features["user_orders_30d"] = _q1(
            conn, "SELECT COUNT(*) FROM orders WHERE user_id=? AND created_at>=?", (uid, _cutoff(days=30)), 0)
        features["user_paid_amount_30d"] = round(float(_q1(
            conn, "SELECT SUM(amount) FROM payments WHERE user_id=? AND paid_at>=?", (uid, _cutoff(days=30)), 0.0)), 2)

        total_orders = _q1(conn, "SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,), 0)
        refund_cnt = _q1(conn, "SELECT COUNT(*) FROM refunds WHERE user_id=?", (uid,), 0)
        features["user_refund_ratio"] = round(refund_cnt / max(1, total_orders), 4)

        features["user_complaints_90d"] = _q1(
            conn, "SELECT COUNT(*) FROM complaints WHERE user_id=? AND created_at>=?",
            (uid, _cutoff(days=90)), 0)
        features["user_login_ip_count_24h"] = _q1(
            conn, "SELECT COUNT(DISTINCT ip) FROM user_logins WHERE user_id=? AND login_time>=?",
            (uid, _cutoff(hours=24)), 0)

        # 黑名单统一按「业务编号」匹配
        features["user_blacklisted"] = _blacklist_hit(conn, "user", user["user_no"])

        if order is not None:
            others = _q1(
                conn,
                "SELECT COUNT(*) FROM orders WHERE user_id=? AND id!=? AND created_at<=?",
                (uid, order["id"], order["created_at"]), 0)
            features["user_first_order_flag"] = 1 if others == 0 else 0

        # 历史拒绝处置次数（排除当前订单，避免同单反复检查造成评分自我强化）
        params: list[Any] = [user["user_no"]]
        sql = ("SELECT COUNT(DISTINCT a.id) FROM risk_assessments a "
               "JOIN risk_events e ON e.id = a.event_id "
               "WHERE e.user_id=? AND a.decision='reject'")
        if order_no:
            sql += " AND (e.order_id IS NULL OR e.order_id!=?)"
            params.append(order_no)
        features["user_rejected_count"] = _q1(conn, sql, params, 0)

    # ================= 订单维度 =================
    if order is not None:
        uid = order["user_id"]
        features["order_amount"] = round(float(order["amount"]), 2)
        features["order_items_count"] = order["items_count"]
        features["order_category"] = order["category"]
        features["order_status"] = order["status"]
        features["order_after_sale_count"] = _q1(
            conn, "SELECT COUNT(*) FROM refunds WHERE order_id=?", (order["id"],), 0)

        payment = conn.execute(
            "SELECT paid_at FROM payments WHERE order_id=? ORDER BY paid_at LIMIT 1", (order["id"],)).fetchone()
        if payment is not None:
            paid_at = _parse(payment["paid_at"])
            created_at = _parse(order["created_at"])
            if paid_at is not None:
                features["order_pay_hour"] = paid_at.hour
            if paid_at is not None and created_at is not None:
                features["order_pay_gap_seconds"] = int((paid_at - created_at).total_seconds())

        # 与本用户其它已支付订单的均价比值（无可比订单时为 None）
        avg_other = _q1(
            conn,
            "SELECT AVG(amount) FROM payments WHERE user_id=? AND order_id!=?",
            (uid, order["id"]))
        if avg_other and float(avg_other) > 0:
            features["order_amount_ratio"] = round(float(order["amount"]) / float(avg_other), 2)

    # ================= 地址维度 =================
    if address is not None:
        detail = address["detail"]
        # 地址黑名单同时支持「详细地址」与「省市+详细地址」两种写法
        addr_hit = _blacklist_hit(conn, "address", detail)
        if not addr_hit:
            full = f"{address['province'] or ''}{address['city'] or ''}{detail}"
            addr_hit = _blacklist_hit(conn, "address", full)
        features["address_blacklisted"] = addr_hit

        if order is not None:
            features["address_ip_blacklisted"] = _blacklist_hit(conn, "ip", order["device_ip"])
            features["address_change_count_7d"] = _q1(
                conn, "SELECT COUNT(DISTINCT address_id) FROM orders WHERE user_id=? AND created_at>=?",
                (order["user_id"], _cutoff(days=7)), 0)
            features["address_is_new_for_user"] = 1 if _q1(
                conn, "SELECT COUNT(*) FROM orders WHERE user_id=? AND address_id=? AND id!=?",
                (order["user_id"], address["id"], order["id"]), 0) == 0 else 0
            if order["device_ip"]:
                features["address_ip_user_count"] = _q1(
                    conn, "SELECT COUNT(DISTINCT user_id) FROM orders WHERE device_ip=?",
                    (order["device_ip"],), 0)

        features["address_shared_user_count"] = _q1(
            conn, "SELECT COUNT(DISTINCT user_id) FROM addresses WHERE detail=?", (detail,), 0)
        if address["phone"]:
            features["address_phone_shared_count"] = _q1(
                conn, "SELECT COUNT(DISTINCT user_id) FROM addresses WHERE phone=?", (address["phone"],), 0)

    return features


def feature_definitions() -> list[dict]:
    """返回 25 个特征的元信息，供前端渲染特征快照标签。"""
    return [{"feature_key": k, "feature_name": v[0], "dimension": v[1],
             "dimension_label": DIMENSION_LABELS[v[1]]} for k, v in FEATURE_META.items()]
