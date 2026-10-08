"""数据库初始化脚本：建表 + 24 条风险规则 + 示例业务数据。

用法：
    python scripts/init_db.py            # 幂等：库已存在则跳过
    python scripts/init_db.py --force    # 删除重建（推荐用于演示前重置）

演示环境使用 SQLite（Python 标准库，零依赖）。MySQL 版本脚本见 sql/schema.sql
与 sql/sample_data.sql，两者表结构与数据口径保持一致。
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import features as features_module  # noqa: E402
from config import DB_PATH, DATA_DIR  # noqa: E402

# Windows 控制台默认 GBK，避免中文输出乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

NOW = datetime.now()


def ts(days_ago=0, hours_ago=0, minutes_ago=0, at_hour=None, at_minute=0):
    """生成相对当前时间的 'YYYY-MM-DD HH:MM:SS' 时间戳。"""
    if at_hour is not None:
        base = NOW - timedelta(days=days_ago)
        base = base.replace(hour=at_hour, minute=at_minute, second=0, microsecond=0)
    else:
        base = NOW - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
    return base.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================================
# 一、表结构（8 张规范表 + 8 张业务表）
# ============================================================================
SCHEMA_SQL = """
-- ---------- 业务数据表（风险特征计算的数据来源） ----------
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    user_no       TEXT NOT NULL UNIQUE,
    username      TEXT NOT NULL,
    phone         TEXT,
    email         TEXT,
    level         TEXT,
    status        TEXT,
    registered_at TEXT NOT NULL
);

CREATE TABLE user_logins (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    ip         TEXT,
    login_time TEXT NOT NULL
);

CREATE TABLE addresses (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    receiver_name TEXT,
    phone         TEXT,
    province      TEXT,
    city          TEXT,
    detail        TEXT NOT NULL,
    is_default    INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    order_no    TEXT NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL,
    address_id  INTEGER,
    category    TEXT,
    amount      REAL NOT NULL,
    items_count INTEGER DEFAULT 1,
    device_ip   TEXT,
    status      TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE payments (
    id       INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    amount   REAL NOT NULL,
    channel  TEXT,
    paid_at  TEXT NOT NULL
);

CREATE TABLE refunds (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    amount     REAL NOT NULL,
    reason     TEXT,
    status     TEXT,
    applied_at TEXT NOT NULL
);

CREATE TABLE complaints (
    id             INTEGER PRIMARY KEY,
    order_id       INTEGER,
    user_id        INTEGER NOT NULL,
    complaint_type TEXT,
    description    TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE logistics (
    id          INTEGER PRIMARY KEY,
    order_id    INTEGER NOT NULL,
    status      TEXT,
    description TEXT,
    updated_at  TEXT NOT NULL
);

-- ---------- 风控规范表 ----------
CREATE TABLE risk_events (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type         TEXT NOT NULL,
    source_id          TEXT,
    user_id            TEXT,
    order_id           TEXT,
    event_payload_json TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE risk_assessments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id          INTEGER NOT NULL,
    risk_score        INTEGER NOT NULL DEFAULT 0,
    risk_level        TEXT NOT NULL,
    decision          TEXT NOT NULL,
    assessment_status TEXT NOT NULL DEFAULT 'completed',
    created_at        TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES risk_events (id)
);

CREATE TABLE feature_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    feature_json  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
);

CREATE TABLE risk_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_code      TEXT NOT NULL UNIQUE,
    rule_name      TEXT NOT NULL,
    rule_status    TEXT NOT NULL DEFAULT 'enabled',
    priority       INTEGER NOT NULL DEFAULT 100,
    score          INTEGER NOT NULL DEFAULT 10,
    condition_json TEXT NOT NULL,
    description    TEXT,
    updated_at     TEXT NOT NULL
);

CREATE TABLE rule_hits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    rule_id       INTEGER,
    hit_score     INTEGER NOT NULL DEFAULT 0,
    hit_message   TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
);

CREATE TABLE risk_cases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    user_id       TEXT,
    order_id      TEXT,
    case_status   TEXT NOT NULL DEFAULT 'pending',
    reviewer_id   TEXT,
    review_result TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
);

CREATE TABLE blacklists (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    blacklist_type  TEXT NOT NULL,
    blacklist_value TEXT NOT NULL,
    remark          TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL
);

CREATE TABLE review_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       INTEGER NOT NULL,
    operator_id   TEXT,
    action_type   TEXT,
    action_remark TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES risk_cases (id)
);

-- ---------- 索引 ----------
CREATE INDEX idx_events_user ON risk_events (user_id);
CREATE INDEX idx_events_type ON risk_events (event_type);
CREATE INDEX idx_assess_event ON risk_assessments (event_id);
CREATE INDEX idx_assess_level ON risk_assessments (risk_level);
CREATE INDEX idx_snapshot_assess ON feature_snapshots (assessment_id);
CREATE INDEX idx_hits_assess ON rule_hits (assessment_id);
CREATE INDEX idx_hits_rule ON rule_hits (rule_id);
CREATE INDEX idx_cases_user ON risk_cases (user_id);
CREATE INDEX idx_cases_status ON risk_cases (case_status);
CREATE INDEX idx_logs_case ON review_logs (case_id);
CREATE INDEX idx_blacklist_type ON blacklists (blacklist_type, blacklist_value);
CREATE INDEX idx_orders_user ON orders (user_id);
CREATE INDEX idx_payments_user ON payments (user_id);
CREATE INDEX idx_refunds_user ON refunds (user_id);
CREATE INDEX idx_complaints_user ON complaints (user_id);
CREATE INDEX idx_logins_user ON user_logins (user_id);
"""


def cond(*leaves, any_of=None):
    """构造 condition_json 字典。leaves 归入 all 组，any_of 归入 any 组。"""
    node = {}
    if leaves:
        node["all"] = list(leaves)
    if any_of:
        node["any"] = list(any_of)
    return node


def leaf(op, feature, value=None):
    return {"op": op, "feature": feature, "value": value}


# ============================================================================
# 二、24 条风险规则
# ============================================================================
RULES = [
    dict(rule_code="R_BLACKLIST_USER", rule_name="用户黑名单命中", priority=1, score=40,
         condition_json=cond(leaf("eq", "user_blacklisted", 1)),
         description="用户编号命中黑名单且状态为生效，直接高风险"),
    dict(rule_code="R_BLACKLIST_ADDRESS", rule_name="收货地址黑名单", priority=2, score=35,
         condition_json=cond(leaf("eq", "address_blacklisted", 1)),
         description="收货地址命中黑名单，常见于虚假地址刷单"),
    dict(rule_code="R_BLACKLIST_IP", rule_name="设备IP黑名单", priority=3, score=30,
         condition_json=cond(leaf("eq", "address_ip_blacklisted", 1)),
         description="下单设备IP命中黑名单，疑似团伙作案设备"),
    dict(rule_code="R_NEW_USER_BIG_ORDER", rule_name="新注册大额下单", priority=4, score=30,
         condition_json=cond(leaf("eq", "user_first_order_flag", 1), leaf("lte", "user_age_days", 7),
                             leaf("gte", "order_amount", 5000)),
         description="注册 7 天内首单金额超过 5000 元"),
    dict(rule_code="R_AMOUNT_SPIKE", rule_name="订单金额突增", priority=5, score=25,
         condition_json=cond(leaf("gte", "order_amount_ratio", 5), leaf("gte", "order_amount", 3000)),
         description="本单金额超过该用户历史已支付订单均价的 5 倍"),
    dict(rule_code="R_REFUND_ABUSER", rule_name="退款狂魔", priority=6, score=25,
         condition_json=cond(leaf("gte", "user_refund_ratio", 0.5), leaf("gte", "user_orders_30d", 5),
                             leaf("gte", "user_paid_amount_30d", 5000)),
         description="近 30 天下单 5 笔以上且退款占比超过 50%"),
    dict(rule_code="R_COMPLAINT_ABUSER", rule_name="投诉惯犯", priority=7, score=20,
         condition_json=cond(leaf("gte", "user_complaints_90d", 3)),
         description="近 90 天投诉次数达到 3 次以上"),
    dict(rule_code="R_LATE_NIGHT_PAY", rule_name="深夜支付", priority=8, score=10,
         condition_json=cond(any_of=[leaf("gte", "order_pay_hour", 23), leaf("lte", "order_pay_hour", 4)]),
         description="支付时间落在 23 点至次日 4 点之间"),
    dict(rule_code="R_LATE_NIGHT_HIGH_AMOUNT", rule_name="深夜大额支付", priority=9, score=30,
         condition_json=cond(leaf("gte", "order_pay_hour", 22), leaf("gte", "order_amount", 8000)),
         description="22 点后支付且订单金额超过 8000 元"),
    dict(rule_code="R_MULTI_ADDRESS_7D", rule_name="短时多收货地址", priority=10, score=25,
         condition_json=cond(leaf("gte", "address_change_count_7d", 3)),
         description="近 7 天使用 3 个以上不同收货地址"),
    dict(rule_code="R_ADDRESS_SHARED", rule_name="收货地址多人共用", priority=11, score=20,
         condition_json=cond(leaf("gte", "address_shared_user_count", 3)),
         description="同一收货地址被 3 个以上用户使用，疑似刷单窝点"),
    dict(rule_code="R_PHONE_SHARED", rule_name="收货手机号多人共用", priority=12, score=15,
         condition_json=cond(leaf("gte", "address_phone_shared_count", 3)),
         description="同一收货手机号被 3 个以上用户使用"),
    dict(rule_code="R_IP_MULTI_USER", rule_name="单IP多用户下单", priority=13, score=20,
         condition_json=cond(leaf("gte", "address_ip_user_count", 3)),
         description="同一个设备 IP 关联 3 个以上用户"),
    dict(rule_code="R_MULTI_IP_LOGIN", rule_name="短时多IP登录", priority=14, score=25,
         condition_json=cond(leaf("gte", "user_login_ip_count_24h", 3)),
         description="24 小时内使用 3 个以上 IP 登录，疑似账号被盗"),
    dict(rule_code="R_FLASH_PAY", rule_name="秒级支付", priority=15, score=10,
         condition_json=cond(leaf("lte", "order_pay_gap_seconds", 10)),
         description="下单后 10 秒内完成支付，疑似脚本批量操作"),
    dict(rule_code="R_VIRTUAL_CATEGORY_BIG", rule_name="高敏类目大额下单", priority=16, score=20,
         condition_json=cond(leaf("contains", "order_category", ["虚拟卡券", "数码3C"]),
                             leaf("gte", "order_amount", 3000), leaf("gte", "order_items_count", 3)),
         description="虚拟卡券/数码3C 等易变现类目大额多件下单"),
    dict(rule_code="R_ORDER_STATUS_REFUNDED", rule_name="已退款订单再次申请售后", priority=17, score=5,
         condition_json=cond(leaf("eq", "order_status", "已退款")),
         description="订单已退款仍发起售后申请"),
    dict(rule_code="R_HIGH_RISK_AFTER_SALE", rule_name="高频售后退款用户", priority=18, score=20,
         condition_json=cond(leaf("eq", "event_type", "after_sale_apply"), leaf("gte", "order_amount", 1000),
                             leaf("gte", "user_refund_ratio", 0.3), leaf("gte", "order_after_sale_count", 1)),
         description="售后申请 + 订单金额较高 + 历史退款占比超过 30%"),
    dict(rule_code="R_COMPLAINT_NEW_USER", rule_name="低活跃用户投诉", priority=19, score=15,
         condition_json=cond(leaf("eq", "event_type", "logistics_complaint"), leaf("lte", "user_orders_30d", 2)),
         description="下单量很少却频繁发起物流投诉"),
    dict(rule_code="R_PRIOR_REJECTED", rule_name="历史被拒用户", priority=20, score=15,
         condition_json=cond(leaf("neq", "user_rejected_count", 0)),
         description="该用户历史风险检查存在拒绝处置记录"),
    dict(rule_code="R_NEW_ADDRESS_HIGH_AMOUNT", rule_name="新收货地址大额下单", priority=21, score=25,
         condition_json=cond(leaf("eq", "address_is_new_for_user", 1), leaf("gte", "order_amount", 6000)),
         description="首次使用的收货地址且订单金额超过 6000 元"),
    dict(rule_code="R_LOW_ACTIVITY_HIGH_AMOUNT", rule_name="低活跃老用户大额下单", priority=22, score=20,
         condition_json=cond(leaf("lte", "user_orders_30d", 1), leaf("gte", "order_amount", 4000),
                             leaf("gt", "user_age_days", 7)),
         description="注册超过 7 天但近 30 天几乎无下单，突然大额下单"),
    dict(rule_code="R_AMOUNT_ABNORMAL_HIGH", rule_name="订单金额异常超大", priority=23, score=30,
         condition_json=cond(leaf("gt", "order_amount", 20000)),
         description="单笔订单金额超过 20000 元"),
    dict(rule_code="R_AFTER_SALE_QUICK_REFUND", rule_name="秒付秒退", priority=24, score=15,
         condition_json=cond(leaf("eq", "event_type", "after_sale_apply"), leaf("lt", "order_pay_gap_seconds", 300)),
         description="支付后 5 分钟内即发起售后申请"),
]


# ============================================================================
# 三、业务示例数据
# ============================================================================
# (id, user_no, username, phone, email, level, status, 注册距今天数)
USERS = [
    (1, "U1001", "张伟", "13800001001", "zhangwei@demo.com", "普通会员", "正常", 400),
    (2, "U1002", "李娜", "13800001002", "lina@demo.com", "普通会员", "正常", 3),
    (3, "U1003", "王强", "13800001003", "wangqiang@demo.com", "黄金会员", "正常", 500),
    (4, "U1004", "刘洋", "13800001004", "liuyang@demo.com", "普通会员", "正常", 2),
    (5, "U1005", "陈静", "13800001005", "chenjing@demo.com", "普通会员", "正常", 350),
    (6, "U1006", "赵磊", "13800001006", "zhaolei@demo.com", "普通会员", "正常", 300),
    (7, "U1007", "孙丽", "13800001007", "sunli@demo.com", "普通会员", "正常", 120),
    (8, "U1008", "周涛", "13800001008", "zhoutao@demo.com", "普通会员", "正常", 260),
    (9, "U1009", "吴敏", "13800001009", "wumin@demo.com", "钻石会员", "正常", 600),
    (10, "U1010", "郑凯", "13800001010", "zhengkai@demo.com", "普通会员", "正常", 220),
    (11, "U1011", "冯静", "13800001011", "fengjing@demo.com", "白银会员", "正常", 200),
    (12, "U1012", "蒋涛", "13800001012", "jiangtao@demo.com", "普通会员", "正常", 180),
]

# 共享地址/手机号常量：A12 / A13 / A14 共用，用于触发「地址多人共用 / 手机号多人共用」
SHARED_DETAIL = "W市X区团结路12号12栋1212"
SHARED_PHONE = "13800001212"

# (id, user_id, 收件人, 手机, 省, 市, 详细地址, 默认, 创建距今天数)
ADDRESSES = [
    (1, 1, "张伟", "13800001001", "A省", "A市", "A市B区幸福路1号1栋101", 1, 380),
    (2, 2, "李娜", "13800001002", "C省", "C市", "C市D区朝阳路2号2栋202", 1, 3),
    (3, 3, "王强", "13800001003", "E省", "E市", "E市F区人民路3号3栋303", 1, 480),
    (4, 4, "刘洋", "13800001004", "G省", "G市", "G市H区解放路4号4栋404", 1, 2),
    (5, 5, "陈静", "13800001005", "I省", "I市", "I市J区建设路5号5栋505", 1, 340),
    (6, 6, "赵磊", "13800001006", "K省", "K市", "K市L区中山路6号6栋606", 1, 290),
    (7, 7, "孙丽", "13800001007", "M省", "M市", "M市N区文化路7号7栋707", 1, 115),
    (8, 8, "周涛", "13800001008", "O省", "O市", "O市P区长江路8号8栋808", 1, 250),
    (9, 9, "吴敏", "13800001009", "Q省", "Q市", "Q市R区黄河路9号9栋909", 1, 580),
    (10, 10, "郑凯", "13800001010", "S省", "S市", "S市T区和平路10号10栋1010", 1, 210),
    (11, 11, "冯静", "13800001011", "U省", "U市", "U市V区光明路11号11栋1111", 1, 195),
    (12, 12, "蒋涛", SHARED_PHONE, "W省", "W市", SHARED_DETAIL, 1, 175),
    (13, 5, "陈静", SHARED_PHONE, "W省", "W市", SHARED_DETAIL, 0, 170),
    (14, 7, "孙丽", SHARED_PHONE, "W省", "W市", SHARED_DETAIL, 0, 168),
    (15, 10, "郑凯", "13800001010", "S省", "S市", "S市T区和平路10号11栋1011", 0, 8),
    (16, 10, "郑凯", "13800001010", "S省", "S市", "S市T区和平路10号12栋1012", 0, 6),
]

# 订单：(订单号, 用户id, 地址id, 类目, 金额, 件数, 设备IP, 状态, 创建距今天数,
#        pay_hour, pay_gap_seconds, 是否已支付)
# pay_hour=None 表示沿用默认（白天），pay_gap_seconds=None 表示默认 900 秒
ORDERS = [
    # --- U1001 黑名单用户：3 单/30天，老地址，命中黑名单 IP ---
    ("SO202400101", 1, 1, "服装", 2000, 2, "58.22.1.99", "已支付", 0, 15, 1500, True),
    ("SO202400102", 1, 1, "服装", 1200, 1, "58.22.1.99", "已支付", 10, 11, 800, True),
    ("SO202400103", 1, 1, "鞋靴", 800, 1, "113.10.1.5", "已支付", 20, 16, 600, True),

    # --- U1002 新注册（3天）首单 6000 元，新地址，未支付 ---
    ("SO202400201", 2, 2, "家用电器", 6000, 2, "220.1.1.1", "待支付", 0, None, None, False),

    # --- U1003 深夜 23:40 支付 25000 元 ---
    ("SO202400301", 3, 3, "家用电器", 25000, 1, "221.2.2.2", "已支付", 0, 23, 3600, True),
    ("SO202400302", 3, 3, "家用电器", 5500, 1, "221.2.2.2", "已支付", 3, 14, 900, True),
    ("SO202400303", 3, 3, "家用电器", 5500, 2, "221.2.2.2", "已支付", 6, 10, 1200, True),
    ("SO202400304", 3, 3, "家用电器", 5500, 1, "221.2.2.2", "已支付", 9, 20, 700, True),
    ("SO202400305", 3, 3, "家用电器", 5500, 1, "221.2.2.2", "已支付", 12, 13, 1500, True),
    ("SO202400306", 3, 3, "家用电器", 5500, 3, "221.2.2.2", "已支付", 15, 9, 400, True),

    # --- U1004 新注册（2天）首单 5000 元虚拟卡券，8 秒支付 ---
    ("SO202400401", 4, 4, "虚拟卡券", 5000, 3, "222.3.3.3", "已支付", 0, 14, 8, True),

    # --- U1005 退款狂魔：30 天 10 单、7 次退款 ---
    ("SO202400501", 5, 5, "美妆", 2600, 2, "223.4.4.4", "已支付", 0, 10, 7200, True),
    ("SO202400502", 5, 5, "美妆", 1800, 1, "223.4.4.4", "已退款", 2, 11, 900, True),
    ("SO202400503", 5, 5, "美妆", 2200, 2, "223.4.4.4", "已退款", 4, 15, 1100, True),
    ("SO202400504", 5, 5, "美妆", 1600, 1, "223.4.4.4", "已退款", 5, 9, 600, True),
    ("SO202400505", 5, 5, "个护", 2400, 3, "223.4.4.4", "已退款", 8, 16, 1300, True),
    ("SO202400506", 5, 5, "个护", 1900, 1, "223.4.4.4", "已退款", 11, 12, 900, True),
    ("SO202400507", 5, 5, "美妆", 2100, 2, "223.4.4.4", "已退款", 14, 18, 750, True),
    ("SO202400508", 5, 5, "美妆", 1700, 1, "223.4.4.4", "已退款", 17, 10, 1000, True),
    ("SO202400509", 5, 5, "个护", 2000, 2, "223.4.4.4", "已支付", 21, 14, 800, True),
    ("SO202400510", 5, 5, "美妆", 1500, 1, "223.4.4.4", "已支付", 25, 11, 950, True),

    # --- U1006 顽固退款 + 历史被拒：8 单 / 30 天内 6 单 / 6 次退款 ---
    ("SO202400601", 6, 6, "数码配件", 2600, 2, "224.5.5.5", "已退款", 0, 16, 60, True),
    ("SO202400602", 6, 6, "数码配件", 1500, 1, "224.5.5.5", "已退款", 2, 13, 500, True),
    ("SO202400603", 6, 6, "数码配件", 1700, 1, "224.5.5.5", "已退款", 4, 15, 800, True),
    ("SO202400604", 6, 6, "数码配件", 1400, 2, "224.5.5.5", "已退款", 7, 11, 900, True),
    ("SO202400605", 6, 6, "数码配件", 1600, 1, "224.5.5.5", "已退款", 10, 20, 700, True),
    ("SO202400606", 6, 6, "数码配件", 1300, 1, "224.5.5.5", "已退款", 13, 10, 1200, True),
    ("SO202400607", 6, 6, "数码配件", 1200, 1, "224.5.5.5", "已支付", 40, 14, 800, True),
    ("SO202400608", 6, 6, "数码配件", 1100, 1, "224.5.5.5", "已支付", 50, 15, 900, True),

    # --- U1007 投诉惯犯、低活跃：30 天 2 单 ---
    ("SO202400701", 7, 7, "食品", 800, 1, "225.6.6.6", "已支付", 0, 12, 600, True),
    ("SO202400702", 7, 7, "食品", 500, 1, "225.6.6.6", "已支付", 12, 11, 700, True),

    # --- U1008 投诉 4 次 + 收货地址命中黑名单 ---
    ("SO202400801", 8, 8, "家居", 1500, 2, "226.7.7.7", "已支付", 0, 13, 900, True),
    ("SO202400802", 8, 8, "家居", 900, 1, "226.7.7.7", "已支付", 15, 10, 800, True),

    # --- U1009 正常用户：30 天 5 单，小额日用品 ---
    ("SO202400901", 9, 9, "日用品", 300, 1, "227.8.8.8", "已支付", 0, 14, 500, True),
    ("SO202400902", 9, 9, "日用品", 260, 1, "227.8.8.8", "已支付", 5, 11, 600, True),
    ("SO202400903", 9, 9, "日用品", 420, 2, "227.8.8.8", "已支付", 12, 16, 700, True),
    ("SO202400904", 9, 9, "日用品", 180, 1, "227.8.8.8", "已支付", 18, 15, 550, True),
    ("SO202400905", 9, 9, "日用品", 350, 1, "227.8.8.8", "已支付", 26, 10, 650, True),

    # --- U1010 近 7 天 3 个不同收货地址 + 新地址 6000 元 ---
    ("SO202401001", 10, 10, "服饰", 6000, 3, "228.9.9.9", "已支付", 0, 11, 900, True),
    ("SO202401002", 10, 15, "服饰", 2000, 1, "228.9.9.9", "已支付", 3, 14, 800, True),
    ("SO202401003", 10, 16, "服饰", 2100, 2, "228.9.9.9", "已支付", 5, 10, 700, True),
    ("SO202401004", 10, 15, "服饰", 1900, 1, "228.9.9.9", "已支付", 6, 15, 600, True),

    # --- U1011 24 小时内 4 个 IP 登录 + 低活跃老用户大额下单 ---
    ("SO202401101", 11, 11, "图书", 4000, 5, "229.10.10.10", "已支付", 0, 13, 800, True),

    # --- U1012 地址/手机号 3 人共用 + 金额突增（历史均价 500 → 本单 3200） ---
    ("SO202401201", 12, 12, "鞋靴", 3200, 2, "230.11.11.11", "已支付", 0, 14, 900, True),
    ("SO202401202", 12, 12, "鞋靴", 500, 1, "230.11.11.11", "已支付", 3, 11, 600, True),
    ("SO202401203", 12, 12, "鞋靴", 480, 1, "230.11.11.11", "已支付", 5, 16, 700, True),
    ("SO202401204", 12, 12, "鞋靴", 520, 1, "230.11.11.11", "已支付", 20, 10, 800, True),
]

# 退款记录：(订单号, 用户id, 金额, 原因, 状态, 申请距今天数)
REFUNDS = [
    ("SO202400501", 5, 2600, "商品与描述不符", "已退款", 0),
    ("SO202400502", 5, 1800, "七天无理由退货", "已退款", 2),
    ("SO202400503", 5, 2200, "质量问题", "已退款", 4),
    ("SO202400504", 5, 1600, "七天无理由退货", "已退款", 5),
    ("SO202400505", 5, 2400, "质量问题", "已退款", 8),
    ("SO202400506", 5, 1900, "拍错/多拍", "已退款", 11),
    ("SO202400507", 5, 2100, "七天无理由退货", "已退款", 14),
    ("SO202400601", 6, 2600, "商品与描述不符", "已退款", 0),
    ("SO202400602", 6, 1500, "质量问题", "已退款", 3),
    ("SO202400603", 6, 1700, "七天无理由退货", "已退款", 5),
    ("SO202400604", 6, 1400, "质量问题", "已退款", 8),
    ("SO202400605", 6, 1600, "拍错/多拍", "已退款", 11),
    ("SO202400606", 6, 1300, "七天无理由退货", "已退款", 14),
    ("SO202400303", 3, 5500, "七天无理由退货", "已退款", 5),
    ("SO202400903", 9, 420, "拍错/多拍", "已完成", 11),
]

# 投诉：(订单号, 用户id, 类型, 描述, 距今天数)
COMPLAINTS = [
    ("SO202400701", 7, "物流延迟", "包裹超过 7 天未更新物流", 5),
    ("SO202400701", 7, "包裹破损", "收到商品外包装严重破损", 20),
    ("SO202400702", 7, "配送态度", "配送员未按约定时间上门", 45),
    ("SO202400801", 8, "物流延迟", "同一订单三次延迟配送", 6),
    ("SO202400801", 8, "虚假签收", "未收到货但显示已签收", 15),
    ("SO202400802", 8, "包裹破损", "商品破损且缺少配件", 30),
    ("SO202400802", 8, "退款纠纷", "退款迟迟未到账", 60),
    ("SO202400502", 5, "物流延迟", "物流信息长时间未更新", 10),
    ("SO202400602", 6, "退款纠纷", "退款金额与实付不一致", 8),
]

# 登录记录：(用户id, IP, 距今天数, 距今小时)
LOGINS = [
    # U1011：24 小时内 4 个不同 IP
    (11, "229.10.10.10", 0, 2), (11, "229.10.10.11", 0, 8),
    (11, "229.10.10.12", 0, 15), (11, "229.10.10.13", 0, 22),
    (11, "229.10.10.10", 3, 5),
    # 其它用户：24 小时内最多 2 个 IP
    (1, "58.22.1.99", 0, 3), (1, "113.10.1.5", 0, 20),
    (2, "220.1.1.1", 0, 5),
    (3, "221.2.2.2", 0, 4), (3, "221.2.2.9", 0, 18),
    (4, "222.3.3.3", 0, 6),
    (5, "223.4.4.4", 0, 7), (5, "223.4.4.9", 0, 19),
    (6, "224.5.5.5", 0, 8),
    (7, "225.6.6.6", 0, 9),
    (8, "226.7.7.7", 0, 10),
    (9, "227.8.8.8", 0, 11), (9, "227.8.8.9", 0, 21),
    (10, "228.9.9.9", 0, 12),
    (12, "230.11.11.11", 0, 13),
]

# 黑名单：(类型, 值, 备注, 状态, 创建距今天数)
BLACKLISTS = [
    ("user", "U1001", "历史欺诈行为，确认为恶意账号，永久拉黑", "active", 120),
    ("ip", "58.22.1.99", "高风险设备 IP，关联多起团伙欺诈", "active", 90),
    ("address", "O市P区长江路8号8栋808", "虚假收货地址，批量刷单专用", "active", 60),
    ("user", "U1099", "已申诉成功解除拉黑（演示停用状态）", "disabled", 30),
]

# 历史风险检查记录：让看板在演示开始前就有数据
# (用户id, 订单号, 事件类型, 分值, 等级, 决策, 距今天数, 命中规则code列表)
HISTORY = [
    (6, "SO202400606", "after_sale_apply", 80, "high", "reject", 6,
     ["R_REFUND_ABUSER", "R_HIGH_RISK_AFTER_SALE", "R_PRIOR_REJECTED"]),
    (6, "SO202400605", "after_sale_apply", 75, "high", "reject", 4,
     ["R_REFUND_ABUSER", "R_HIGH_RISK_AFTER_SALE"]),
    (1, "SO202400102", "order_create", 30, "medium", "manual_review", 6, ["R_BLACKLIST_IP"]),
    (3, "SO202400302", "order_pay", 45, "medium", "manual_review", 5, ["R_LATE_NIGHT_PAY", "R_AMOUNT_SPIKE"]),
    (5, "SO202400503", "after_sale_apply", 45, "medium", "manual_review", 5,
     ["R_REFUND_ABUSER", "R_HIGH_RISK_AFTER_SALE"]),
    (5, "SO202400505", "after_sale_apply", 45, "medium", "manual_review", 3,
     ["R_REFUND_ABUSER", "R_HIGH_RISK_AFTER_SALE"]),
    (7, "SO202400702", "logistics_complaint", 35, "medium", "manual_review", 3,
     ["R_COMPLAINT_ABUSER", "R_COMPLAINT_NEW_USER"]),
    (8, "SO202400802", "logistics_complaint", 35, "medium", "manual_review", 2,
     ["R_COMPLAINT_ABUSER", "R_COMPLAINT_NEW_USER"]),
    (12, "SO202401202", "order_create", 55, "medium", "manual_review", 2, ["R_ADDRESS_SHARED", "R_PHONE_SHARED"]),
    (9, "SO202400903", "order_create", 0, "low", "pass", 1, []),
    (9, "SO202400904", "order_pay", 0, "low", "pass", 1, []),
]

# 历史案件：(订单号, 用户id, 案件状态, 审核人, 审核结论, 距今创建天数, 处理备注)
HISTORY_CASES = [
    ("SO202400606", 6, "resolved", "风控审核员-李芳", "reject", 6, "确认为恶意退款，驳回并加入观察名单"),
    ("SO202400605", 6, "rejected", "风控审核员-李芳", "reject", 4, "同上，维持拒绝处置"),
    ("SO202400102", 1, "approved", "风控审核员-王明", "approve", 6, "核实为正常老用户调换设备，予以放行"),
    ("SO202400302", 3, "resolved", "风控审核员-王明", "resolve", 5, "联系用户确认为本人操作，予以结案"),
    ("SO202400503", 5, "resolved", "风控审核员-李芳", "resolve", 5, "售后正常，已引导走平台退货流程"),
    ("SO202400505", 5, "pending", None, None, 3, None),
    ("SO202400702", 7, "reviewing", None, None, 3, None),
    ("SO202400802", 8, "resolved", "风控审核员-张涛", "reject", 2, "地址确认为刷单窝点，拒绝并拉黑"),
    ("SO202401202", 12, "approved", "风控审核员-王明", "approve", 2, "家庭共享账号，核实后放行"),
]


# ============================================================================
# 四、写入逻辑
# ============================================================================
def init_database(force: bool = False):
    if DB_PATH.exists():
        if not force:
            print(f"[跳过] 数据库已存在：{DB_PATH}")
            print("       如需重建请执行：python scripts/init_db.py --force")
            return
        DB_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            extra = DB_PATH.with_name(DB_PATH.name + suffix)
            if extra.exists():
                extra.unlink()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    # ---- 业务数据 ----
    conn.executemany(
        "INSERT INTO users (id, user_no, username, phone, email, level, status, registered_at) VALUES (?,?,?,?,?,?,?,?)",
        [(uid, uno, name, phone, mail, lvl, st, ts(days_ago=d)) for uid, uno, name, phone, mail, lvl, st, d in USERS],
    )
    conn.executemany(
        "INSERT INTO addresses (id, user_id, receiver_name, phone, province, city, detail, is_default, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        [(aid, uid, rn, ph, prov, city, detail, dflt, ts(days_ago=d))
         for aid, uid, rn, ph, prov, city, detail, dflt, d in ADDRESSES],
    )
    # 订单创建时间由「支付时间 - 支付间隔」反推，保证 order_pay_gap_seconds 与 pay_hour 精确可控
    order_rows, payments = [], []
    for i, (ono, uid, aid, cat, amt, items, ip, st, d, hour, gap, paid) in enumerate(ORDERS, start=1):
        if not paid:
            created_dt = NOW - timedelta(days=d)
        else:
            gap = 900 if gap is None else gap
            if hour is not None:
                paid_dt = (NOW - timedelta(days=d)).replace(
                    hour=hour, minute=40 if hour == 23 else 15, second=0, microsecond=0)
                if paid_dt > NOW:  # 目标时刻晚于当前时间则回退一天，避免出现未来时间
                    paid_dt -= timedelta(days=1)
                created_dt = paid_dt - timedelta(seconds=gap)
            else:
                created_dt = (NOW - timedelta(days=d)).replace(microsecond=0)
                paid_dt = created_dt + timedelta(seconds=gap)
            payments.append((i, uid, amt, "在线支付", paid_dt.strftime("%Y-%m-%d %H:%M:%S")))
        order_rows.append((i, ono, uid, aid, cat, amt, items, ip, st, created_dt.strftime("%Y-%m-%d %H:%M:%S")))

    conn.executemany(
        "INSERT INTO orders (id, order_no, user_id, address_id, category, amount, items_count, device_ip, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)", order_rows,
    )
    order_id_by_no = {row["order_no"]: row["id"] for row in conn.execute("SELECT id, order_no FROM orders")}
    conn.executemany(
        "INSERT INTO payments (order_id, user_id, amount, channel, paid_at) VALUES (?,?,?,?,?)", payments
    )

    conn.executemany(
        "INSERT INTO refunds (order_id, user_id, amount, reason, status, applied_at) VALUES (?,?,?,?,?,?)",
        [(order_id_by_no[o], uid, amt, reason, st, ts(days_ago=d)) for o, uid, amt, reason, st, d in REFUNDS],
    )
    conn.executemany(
        "INSERT INTO complaints (order_id, user_id, complaint_type, description, created_at) VALUES (?,?,?,?,?)",
        [(order_id_by_no[o], uid, ctype, desc, ts(days_ago=d)) for o, uid, ctype, desc, d in COMPLAINTS],
    )
    conn.executemany(
        "INSERT INTO user_logins (user_id, ip, login_time) VALUES (?,?,?)",
        [(uid, ip, ts(days_ago=d, hours_ago=h)) for uid, ip, d, h in LOGINS],
    )

    # 物流记录：为每条订单生成一条轨迹
    logistics = []
    for ono, uid, _aid, _cat, _amt, _items, _ip, st, d, *_rest in ORDERS:
        if st == "待支付":
            continue
        status = "已签收" if st == "已退款" else ("运输中" if d <= 1 else "已签收")
        logistics.append((order_id_by_no[ono], status, f"订单 {ono} 物流状态：{status}", ts(days_ago=max(d - 1, 0))))
    conn.executemany(
        "INSERT INTO logistics (order_id, status, description, updated_at) VALUES (?,?,?,?)", logistics
    )

    conn.executemany(
        "INSERT INTO blacklists (blacklist_type, blacklist_value, remark, status, created_at) VALUES (?,?,?,?,?)",
        [(t, v, r, s, ts(days_ago=d)) for t, v, r, s, d in BLACKLISTS],
    )

    # ---- 24 条规则 ----
    conn.executemany(
        "INSERT INTO risk_rules (rule_code, rule_name, rule_status, priority, score, condition_json, description, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [(r["rule_code"], r["rule_name"], "enabled", r["priority"], r["score"],
          json.dumps(r["condition_json"], ensure_ascii=False), r["description"], ts()) for r in RULES],
    )
    rule_id_by_code = {row["rule_code"]: row["id"] for row in conn.execute("SELECT id, rule_code FROM risk_rules")}
    user_id_by_no = {row["user_no"]: row["id"] for row in conn.execute("SELECT id, user_no FROM users")}

    # ---- 历史风险检查记录 + 案件 + 审核日志 ----
    case_id_by_order = {}
    for uid, ono, etype, score, level, decision, days, hit_codes in HISTORY:
        user_no = f"U{1000 + uid}"
        payload = {"user_id": user_no, "order_id": ono, "event_type": etype, "source_type": "离线批量回溯"}
        cur = conn.execute(
            "INSERT INTO risk_events (event_type, source_id, user_id, order_id, event_payload_json, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (etype, f"backfill_{ono}", user_no, ono, json.dumps(payload, ensure_ascii=False), ts(days_ago=days, hours_ago=2)),
        )
        event_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO risk_assessments (event_id, risk_score, risk_level, decision, assessment_status, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (event_id, score, level, decision, "completed", ts(days_ago=days, hours_ago=2)),
        )
        assessment_id = cur.lastrowid
        # 历史记录同样保存完整的 25 项特征快照（按当前业务数据口径回溯计算），
        # 保证案件详情页可正常回看特征，而不是一片空值。
        snapshot = features_module.compute_features(conn, etype, user_no, ono)
        conn.execute(
            "INSERT INTO feature_snapshots (assessment_id, feature_json, created_at) VALUES (?,?,?)",
            (assessment_id, json.dumps(snapshot, ensure_ascii=False, default=str), ts(days_ago=days, hours_ago=2)),
        )
        for code in hit_codes:
            rid = rule_id_by_code.get(code)
            rule = next((r for r in RULES if r["rule_code"] == code), None)
            if rid is None or rule is None:
                continue
            conn.execute(
                "INSERT INTO rule_hits (assessment_id, rule_id, hit_score, hit_message, created_at) VALUES (?,?,?,?,?)",
                (assessment_id, rid, rule["score"], f"命中规则【{rule['rule_name']}】", ts(days_ago=days, hours_ago=2)),
            )
        # 中高风险自动建案
        if level == "high" or decision in ("manual_review", "reject"):
            cur = conn.execute(
                "INSERT INTO risk_cases (assessment_id, user_id, order_id, case_status, reviewer_id, review_result, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (assessment_id, user_no, ono, "pending", None, None, ts(days_ago=days, hours_ago=2), ts(days_ago=days, hours_ago=2)),
            )
            case_id_by_order[ono] = cur.lastrowid
            conn.execute(
                "INSERT INTO review_logs (case_id, operator_id, action_type, action_remark, created_at) VALUES (?,?,?,?,?)",
                (cur.lastrowid, "系统", "create", f"风险等级 {level}，自动创建案件", ts(days_ago=days, hours_ago=2)),
            )

    # 历史案件状态回填
    for ono, _uid, cstatus, reviewer, rresult, days, remark in HISTORY_CASES:
        case_id = case_id_by_order.get(ono)
        if case_id is None:
            continue
        updated = ts(days_ago=max(days - 1, 0), hours_ago=1)
        conn.execute(
            "UPDATE risk_cases SET case_status=?, reviewer_id=?, review_result=?, updated_at=? WHERE id=?",
            (cstatus, reviewer, rresult, updated, case_id),
        )
        if reviewer and rresult:
            action = "resolve" if rresult == "resolve" else "review"
            conn.execute(
                "INSERT INTO review_logs (case_id, operator_id, action_type, action_remark, created_at) VALUES (?,?,?,?,?)",
                (case_id, reviewer, action, remark, updated),
            )
            if cstatus == "resolved" and action != "resolve":
                conn.execute(
                    "INSERT INTO review_logs (case_id, operator_id, action_type, action_remark, created_at) VALUES (?,?,?,?,?)",
                    (case_id, reviewer, "resolve", "处置结论已执行，案件结案", ts(days_ago=max(days - 1, 0))),
                )

    conn.commit()

    # ---- 汇总输出 ----
    tables = ["users", "addresses", "orders", "payments", "refunds", "complaints", "logistics",
              "user_logins", "blacklists", "risk_rules", "risk_events", "risk_assessments",
              "feature_snapshots", "rule_hits", "risk_cases", "review_logs"]
    print(f"[完成] 数据库已初始化：{DB_PATH}")
    for t in tables:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"       {t:<20} {cnt:>4} 行")
    enabled = conn.execute("SELECT COUNT(*) FROM risk_rules WHERE rule_status='enabled'").fetchone()[0]
    print(f"       其中启用状态规则 {enabled} 条 / 共 {len(RULES)} 条")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="初始化电商风控系统数据库")
    parser.add_argument("--force", action="store_true", help="删除已有数据库并重建")
    args = parser.parse_args()
    init_database(force=args.force)
