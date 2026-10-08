"""全局配置：路径、风险等级阈值、评分与决策常量。"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "tradeguard.db"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# ---- 风险评分模型 ----
# risk_score = min(SCORE_CAP, sum(命中规则分值))
SCORE_CAP = 100
LEVEL_HIGH_THRESHOLD = 70   # score >= 70 -> high
LEVEL_MEDIUM_THRESHOLD = 30  # score >= 30 -> medium，其余 low

# 处理建议映射：风险等级 -> 处理建议
LEVEL_DECISION_MAP = {
    "high": "reject",
    "medium": "manual_review",
    "low": "pass",
}

# 自动建案条件：风险等级为 high，或处理建议为 manual_review / reject
AUTO_CASE_DECISIONS = {"manual_review", "reject"}

# 处理建议 -> 自动建案初始状态
CASE_STATUS_BY_DECISION = {
    "reject": "reviewing",
    "manual_review": "pending",
}

# ---- 枚举取值 ----
EVENT_TYPES = ["order_create", "order_pay", "after_sale_apply", "logistics_complaint"]
RISK_LEVELS = ["low", "medium", "high"]
DECISIONS = ["pass", "manual_review", "reject"]
CASE_STATUSES = ["pending", "reviewing", "approved", "rejected", "resolved"]
BLACKLIST_TYPES = ["user", "order", "address", "ip", "phone"]

# 中文展示映射（接口同时返回英文枚举与中文文案，前端直接渲染）
EVENT_TYPE_LABELS = {
    "order_create": "下单",
    "order_pay": "支付",
    "after_sale_apply": "售后申请",
    "logistics_complaint": "物流投诉",
}
RISK_LEVEL_LABELS = {"low": "低", "medium": "中", "high": "高"}
DECISION_LABELS = {"pass": "放行", "manual_review": "人工审核", "reject": "拒绝"}
CASE_STATUS_LABELS = {
    "pending": "待审核",
    "reviewing": "审核中",
    "approved": "已通过",
    "rejected": "已拒绝",
    "resolved": "已结案",
}
BLACKLIST_TYPE_LABELS = {
    "user": "用户",
    "order": "订单",
    "address": "收货地址",
    "ip": "设备IP",
    "phone": "手机号",
}

# 审核动作 -> 案件状态
REVIEW_RESULT_CASE_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "resolve": "resolved",
}
