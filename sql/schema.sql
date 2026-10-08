-- =============================================================================
-- 电商风险控制系统 star-tradeGuard —— 数据库建表脚本（MySQL 8.0 方言）
--
-- 说明：
--   演示运行默认使用 SQLite（scripts/init_db.py 自动建库，零依赖）。
--   本脚本用于交付/生产环境 MySQL 部署，表结构与 SQLite 版本完全一致。
--
-- 执行方式：
--   mysql -u root -p < sql/schema.sql
--   mysql -u root -p tradeguard < sql/sample_data.sql
-- =============================================================================

CREATE DATABASE IF NOT EXISTS tradeguard
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_general_ci;

USE tradeguard;

-- 按依赖倒序清理（便于重复执行本脚本）
DROP TABLE IF EXISTS review_logs;
DROP TABLE IF EXISTS blacklists;
DROP TABLE IF EXISTS risk_cases;
DROP TABLE IF EXISTS rule_hits;
DROP TABLE IF EXISTS risk_rules;
DROP TABLE IF EXISTS feature_snapshots;
DROP TABLE IF EXISTS risk_assessments;
DROP TABLE IF EXISTS risk_events;
DROP TABLE IF EXISTS logistics;
DROP TABLE IF EXISTS complaints;
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS addresses;
DROP TABLE IF EXISTS user_logins;
DROP TABLE IF EXISTS users;

-- =============================================================================
-- 一、业务数据表（风险特征计算的数据来源）
-- =============================================================================

CREATE TABLE users (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户主键',
  user_no       VARCHAR(32)  NOT NULL COMMENT '用户编号（业务主键，风控按此匹配）',
  username      VARCHAR(64)  NOT NULL COMMENT '用户名称',
  phone         VARCHAR(32)           COMMENT '手机号',
  email         VARCHAR(128)          COMMENT '邮箱',
  level         VARCHAR(32)           COMMENT '会员等级',
  status        VARCHAR(32)           COMMENT '账号状态',
  registered_at DATETIME     NOT NULL COMMENT '注册时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_user_no (user_no)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户表';

CREATE TABLE user_logins (
  id         BIGINT      NOT NULL AUTO_INCREMENT,
  user_id    BIGINT      NOT NULL COMMENT '用户主键',
  ip         VARCHAR(64)          COMMENT '登录IP',
  login_time DATETIME    NOT NULL COMMENT '登录时间',
  PRIMARY KEY (id),
  KEY idx_logins_user (user_id),
  CONSTRAINT fk_logins_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户登录记录（用于短时多IP登录特征）';

CREATE TABLE addresses (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  user_id       BIGINT       NOT NULL COMMENT '所属用户',
  receiver_name VARCHAR(64)           COMMENT '收件人',
  phone         VARCHAR(32)           COMMENT '收件手机号',
  province      VARCHAR(64)           COMMENT '省',
  city          VARCHAR(64)           COMMENT '市',
  detail        VARCHAR(255) NOT NULL COMMENT '详细地址（地址黑名单按此匹配）',
  is_default    TINYINT      DEFAULT 0 COMMENT '是否默认地址',
  created_at    DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_addresses_user (user_id),
  KEY idx_addresses_detail (detail(64)),
  KEY idx_addresses_phone (phone),
  CONSTRAINT fk_addresses_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '收货地址表';

CREATE TABLE orders (
  id          BIGINT        NOT NULL AUTO_INCREMENT,
  order_no    VARCHAR(64)   NOT NULL COMMENT '订单编号（业务主键）',
  user_id     BIGINT        NOT NULL COMMENT '下单用户',
  address_id  BIGINT                 COMMENT '收货地址',
  category    VARCHAR(64)            COMMENT '商品类目',
  amount      DECIMAL(12, 2) NOT NULL COMMENT '订单金额',
  items_count INT           DEFAULT 1 COMMENT '商品件数',
  device_ip   VARCHAR(64)            COMMENT '下单设备IP（IP黑名单按此匹配）',
  status      VARCHAR(32)            COMMENT '订单状态',
  created_at  DATETIME      NOT NULL COMMENT '下单时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_orders_order_no (order_no),
  KEY idx_orders_user (user_id),
  KEY idx_orders_device_ip (device_ip),
  KEY idx_orders_created (created_at),
  CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_orders_address FOREIGN KEY (address_id) REFERENCES addresses (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '订单表';

CREATE TABLE payments (
  id       BIGINT        NOT NULL AUTO_INCREMENT,
  order_id BIGINT        NOT NULL COMMENT '订单主键',
  user_id  BIGINT        NOT NULL COMMENT '支付用户',
  amount   DECIMAL(12, 2) NOT NULL COMMENT '实付金额',
  channel  VARCHAR(32)            COMMENT '支付渠道',
  paid_at  DATETIME      NOT NULL COMMENT '支付时间（用于深夜支付/秒级支付特征）',
  PRIMARY KEY (id),
  KEY idx_payments_order (order_id),
  KEY idx_payments_user (user_id),
  KEY idx_payments_paid_at (paid_at),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_payments_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '支付记录表';

CREATE TABLE refunds (
  id         BIGINT        NOT NULL AUTO_INCREMENT,
  order_id   BIGINT        NOT NULL COMMENT '订单主键',
  user_id    BIGINT        NOT NULL COMMENT '退款用户',
  amount     DECIMAL(12, 2) NOT NULL COMMENT '退款金额',
  reason     VARCHAR(255)           COMMENT '退款原因',
  status     VARCHAR(32)            COMMENT '退款状态',
  applied_at DATETIME      NOT NULL COMMENT '申请时间',
  PRIMARY KEY (id),
  KEY idx_refunds_order (order_id),
  KEY idx_refunds_user (user_id),
  CONSTRAINT fk_refunds_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_refunds_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '退款/售后表（用于退款占比、售后次数特征）';

CREATE TABLE complaints (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  order_id       BIGINT                COMMENT '关联订单',
  user_id        BIGINT       NOT NULL COMMENT '投诉用户',
  complaint_type VARCHAR(64)           COMMENT '投诉类型',
  description    VARCHAR(255)          COMMENT '投诉描述',
  created_at     DATETIME     NOT NULL COMMENT '投诉时间',
  PRIMARY KEY (id),
  KEY idx_complaints_user (user_id),
  KEY idx_complaints_created (created_at),
  CONSTRAINT fk_complaints_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_complaints_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '投诉表（用于近90天投诉次数特征）';

CREATE TABLE logistics (
  id          BIGINT       NOT NULL AUTO_INCREMENT,
  order_id    BIGINT       NOT NULL COMMENT '订单主键',
  status      VARCHAR(32)           COMMENT '物流状态',
  description VARCHAR(255)          COMMENT '物流描述',
  updated_at  DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_logistics_order (order_id),
  CONSTRAINT fk_logistics_order FOREIGN KEY (order_id) REFERENCES orders (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '物流轨迹表';

-- =============================================================================
-- 二、风控规范表（需求 1.2.8 指定的 8 张表）
-- =============================================================================

CREATE TABLE risk_events (
  id                 BIGINT       NOT NULL AUTO_INCREMENT,
  event_type         VARCHAR(64)  NOT NULL COMMENT '业务事件类型：order_create/order_pay/after_sale_apply/logistics_complaint',
  source_id          VARCHAR(128)          COMMENT '来源标识',
  user_id            VARCHAR(64)           COMMENT '用户编号',
  order_id           VARCHAR(64)           COMMENT '订单编号',
  event_payload_json JSON                  COMMENT '原始入参快照',
  created_at         DATETIME     NOT NULL COMMENT '事件接入时间',
  PRIMARY KEY (id),
  KEY idx_events_user (user_id),
  KEY idx_events_type (event_type),
  KEY idx_events_created (created_at)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险事件表（每次检查保存原始入参）';

CREATE TABLE risk_assessments (
  id                BIGINT      NOT NULL AUTO_INCREMENT,
  event_id          BIGINT      NOT NULL COMMENT '关联风险事件',
  risk_score        INT         NOT NULL DEFAULT 0 COMMENT '风险评分 0-100',
  risk_level        VARCHAR(16) NOT NULL COMMENT '风险等级：low/medium/high',
  decision          VARCHAR(32) NOT NULL COMMENT '处理建议：pass/manual_review/reject',
  assessment_status VARCHAR(32) NOT NULL DEFAULT 'completed' COMMENT '评估状态',
  created_at        DATETIME    NOT NULL,
  PRIMARY KEY (id),
  KEY idx_assess_event (event_id),
  KEY idx_assess_level (risk_level),
  KEY idx_assess_created (created_at),
  CONSTRAINT fk_assess_event FOREIGN KEY (event_id) REFERENCES risk_events (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险评估结果表';

CREATE TABLE feature_snapshots (
  id            BIGINT   NOT NULL AUTO_INCREMENT,
  assessment_id BIGINT   NOT NULL COMMENT '关联评估结果',
  feature_json  JSON     NOT NULL COMMENT '特征快照（25 个键值对）',
  created_at    DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY idx_snapshot_assess (assessment_id),
  CONSTRAINT fk_snapshot_assess FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '特征快照表（便于回看与问题排查）';

CREATE TABLE risk_rules (
  id             BIGINT       NOT NULL AUTO_INCREMENT,
  rule_code      VARCHAR(64)  NOT NULL COMMENT '规则编码',
  rule_name      VARCHAR(128) NOT NULL COMMENT '规则名称',
  rule_status    VARCHAR(16)  NOT NULL DEFAULT 'enabled' COMMENT '规则状态：enabled/disabled',
  priority       INT          NOT NULL DEFAULT 100 COMMENT '优先级，数字越小越先匹配',
  score          INT          NOT NULL DEFAULT 10 COMMENT '命中分值',
  condition_json JSON         NOT NULL COMMENT '触发条件（all/any + gt/gte/lt/lte/eq/neq/contains）',
  description    VARCHAR(255)          COMMENT '规则描述',
  updated_at     DATETIME     NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_rules_code (rule_code),
  KEY idx_rules_status_priority (rule_status, priority)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险规则表';

CREATE TABLE rule_hits (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  assessment_id BIGINT       NOT NULL COMMENT '关联评估结果',
  rule_id       BIGINT                COMMENT '命中规则（规则删除后置空，命中记录保留留痕）',
  hit_score     INT          NOT NULL DEFAULT 0 COMMENT '命中分值',
  hit_message   VARCHAR(512)          COMMENT '命中原因描述',
  created_at    DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_hits_assess (assessment_id),
  KEY idx_hits_rule (rule_id),
  CONSTRAINT fk_hits_assess FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '规则命中记录表';

CREATE TABLE risk_cases (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  assessment_id BIGINT       NOT NULL COMMENT '关联评估结果',
  user_id       VARCHAR(64)           COMMENT '关联用户',
  order_id      VARCHAR(64)           COMMENT '关联订单',
  case_status   VARCHAR(32)  NOT NULL DEFAULT 'pending'
                COMMENT '案件状态：pending/reviewing/approved/rejected/resolved',
  reviewer_id   VARCHAR(64)           COMMENT '审核人',
  review_result VARCHAR(32)           COMMENT '审核结论：approve/reject/resolve',
  created_at    DATETIME     NOT NULL,
  updated_at    DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_cases_assess (assessment_id),
  KEY idx_cases_user (user_id),
  KEY idx_cases_status (case_status),
  CONSTRAINT fk_cases_assess FOREIGN KEY (assessment_id) REFERENCES risk_assessments (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险案件表';

CREATE TABLE blacklists (
  id              BIGINT       NOT NULL AUTO_INCREMENT,
  blacklist_type  VARCHAR(32)  NOT NULL COMMENT '黑名单类型：user/order/address/ip/phone',
  blacklist_value VARCHAR(255) NOT NULL COMMENT '命中值',
  remark          VARCHAR(255)          COMMENT '备注',
  status          VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT '状态：active/disabled',
  created_at      DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_blacklist_type_value (blacklist_type, blacklist_value),
  KEY idx_blacklist_status (status)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '黑名单表';

CREATE TABLE review_logs (
  id            BIGINT       NOT NULL AUTO_INCREMENT,
  case_id       BIGINT       NOT NULL COMMENT '关联案件',
  operator_id   VARCHAR(64)           COMMENT '操作人',
  action_type   VARCHAR(32)           COMMENT '动作类型：create/review/resolve',
  action_remark VARCHAR(512)          COMMENT '动作备注（处理结论留痕）',
  created_at    DATETIME     NOT NULL,
  PRIMARY KEY (id),
  KEY idx_logs_case (case_id),
  CONSTRAINT fk_logs_case FOREIGN KEY (case_id) REFERENCES risk_cases (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '审核日志表（处置留痕）';
