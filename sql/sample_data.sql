-- =============================================================================
-- 电商风险控制系统 star-tradeGuard —— 示例数据脚本（MySQL 8.0 方言）
--
-- 前置：先执行 sql/schema.sql 建库建表
-- 执行：mysql -u root -p tradeguard < sql/sample_data.sql
--
-- 时间说明：所有时间均以 NOW() 为基准按天数回推，保证 30 天 / 7 天 / 24 小时等
--           特征统计窗口在任何时间执行本脚本都有效。
--           订单 created_at 由「支付时间 - 支付间隔」反推，
--           以确保 order_pay_gap_seconds 与 order_pay_hour 特征精确可控。
-- =============================================================================

USE tradeguard;
SET NAMES utf8mb4;

-- 清空既有数据（保留表结构）
DELETE FROM review_logs;
DELETE FROM blacklists;
DELETE FROM risk_cases;
DELETE FROM rule_hits;
DELETE FROM risk_rules;
DELETE FROM feature_snapshots;
DELETE FROM risk_assessments;
DELETE FROM risk_events;
DELETE FROM logistics;
DELETE FROM complaints;
DELETE FROM refunds;
DELETE FROM payments;
DELETE FROM orders;
DELETE FROM addresses;
DELETE FROM user_logins;
DELETE FROM users;

-- ---------- 用户（12 个，覆盖正常用户与各类风险画像） ----------
INSERT INTO users (id, user_no, username, phone, email, level, status, registered_at) VALUES
(1, 'U1001', '张伟', '13800001001', 'zhangwei@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 400 DAY)),
(2, 'U1002', '李娜', '13800001002', 'lina@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(3, 'U1003', '王强', '13800001003', 'wangqiang@demo.com', '黄金会员', '正常', DATE_SUB(NOW(), INTERVAL 500 DAY)),
(4, 'U1004', '刘洋', '13800001004', 'liuyang@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(5, 'U1005', '陈静', '13800001005', 'chenjing@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 350 DAY)),
(6, 'U1006', '赵磊', '13800001006', 'zhaolei@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 300 DAY)),
(7, 'U1007', '孙丽', '13800001007', 'sunli@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 120 DAY)),
(8, 'U1008', '周涛', '13800001008', 'zhoutao@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 260 DAY)),
(9, 'U1009', '吴敏', '13800001009', 'wumin@demo.com', '钻石会员', '正常', DATE_SUB(NOW(), INTERVAL 600 DAY)),
(10, 'U1010', '郑凯', '13800001010', 'zhengkai@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 220 DAY)),
(11, 'U1011', '冯静', '13800001011', 'fengjing@demo.com', '白银会员', '正常', DATE_SUB(NOW(), INTERVAL 200 DAY)),
(12, 'U1012', '蒋涛', '13800001012', 'jiangtao@demo.com', '普通会员', '正常', DATE_SUB(NOW(), INTERVAL 180 DAY));

-- ---------- 收货地址（含 3 人共用的地址/手机号，用于「地址多人共用」特征） ----------
INSERT INTO addresses (id, user_id, receiver_name, phone, province, city, detail, is_default, created_at) VALUES
(1, 1, '张伟', '13800001001', 'A省', 'A市', 'A市B区幸福路1号1栋101', 1, DATE_SUB(NOW(), INTERVAL 380 DAY)),
(2, 2, '李娜', '13800001002', 'C省', 'C市', 'C市D区朝阳路2号2栋202', 1, DATE_SUB(NOW(), INTERVAL 3 DAY)),
(3, 3, '王强', '13800001003', 'E省', 'E市', 'E市F区人民路3号3栋303', 1, DATE_SUB(NOW(), INTERVAL 480 DAY)),
(4, 4, '刘洋', '13800001004', 'G省', 'G市', 'G市H区解放路4号4栋404', 1, DATE_SUB(NOW(), INTERVAL 2 DAY)),
(5, 5, '陈静', '13800001005', 'I省', 'I市', 'I市J区建设路5号5栋505', 1, DATE_SUB(NOW(), INTERVAL 340 DAY)),
(6, 6, '赵磊', '13800001006', 'K省', 'K市', 'K市L区中山路6号6栋606', 1, DATE_SUB(NOW(), INTERVAL 290 DAY)),
(7, 7, '孙丽', '13800001007', 'M省', 'M市', 'M市N区文化路7号7栋707', 1, DATE_SUB(NOW(), INTERVAL 115 DAY)),
(8, 8, '周涛', '13800001008', 'O省', 'O市', 'O市P区长江路8号8栋808', 1, DATE_SUB(NOW(), INTERVAL 250 DAY)),
(9, 9, '吴敏', '13800001009', 'Q省', 'Q市', 'Q市R区黄河路9号9栋909', 1, DATE_SUB(NOW(), INTERVAL 580 DAY)),
(10, 10, '郑凯', '13800001010', 'S省', 'S市', 'S市T区和平路10号10栋1010', 1, DATE_SUB(NOW(), INTERVAL 210 DAY)),
(11, 11, '冯静', '13800001011', 'U省', 'U市', 'U市V区光明路11号11栋1111', 1, DATE_SUB(NOW(), INTERVAL 195 DAY)),
(12, 12, '蒋涛', '13800001212', 'W省', 'W市', 'W市X区团结路12号12栋1212', 1, DATE_SUB(NOW(), INTERVAL 175 DAY)),
(13, 5, '陈静', '13800001212', 'W省', 'W市', 'W市X区团结路12号12栋1212', 0, DATE_SUB(NOW(), INTERVAL 170 DAY)),
(14, 7, '孙丽', '13800001212', 'W省', 'W市', 'W市X区团结路12号12栋1212', 0, DATE_SUB(NOW(), INTERVAL 168 DAY)),
(15, 10, '郑凯', '13800001010', 'S省', 'S市', 'S市T区和平路10号11栋1011', 0, DATE_SUB(NOW(), INTERVAL 8 DAY)),
(16, 10, '郑凯', '13800001010', 'S省', 'S市', 'S市T区和平路10号12栋1012', 0, DATE_SUB(NOW(), INTERVAL 6 DAY));

-- ---------- 订单（47 笔，含 12 个风险场景展示订单） ----------
INSERT INTO orders (id, order_no, user_id, address_id, category, amount, items_count, device_ip, status, created_at) VALUES
(1, 'SO202400101', 1, 1, '服装', 2000.00, 2, '58.22.1.99', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 1500 SECOND)),
(2, 'SO202400102', 1, 1, '服装', 1200.00, 1, '58.22.1.99', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 10 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(3, 'SO202400103', 1, 1, '鞋靴', 800.00, 1, '113.10.1.5', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 20 DAY)), INTERVAL (16 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(4, 'SO202400201', 2, 2, '家用电器', 6000.00, 2, '220.1.1.1', '待支付', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(5, 'SO202400301', 3, 3, '家用电器', 25000.00, 1, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (23 * 3600 + 40 * 60) SECOND), INTERVAL 3600 SECOND)),
(6, 'SO202400302', 3, 3, '家用电器', 5500.00, 1, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 3 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(7, 'SO202400303', 3, 3, '家用电器', 5500.00, 2, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 6 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 1200 SECOND)),
(8, 'SO202400304', 3, 3, '家用电器', 5500.00, 1, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 9 DAY)), INTERVAL (20 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(9, 'SO202400305', 3, 3, '家用电器', 5500.00, 1, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 12 DAY)), INTERVAL (13 * 3600 + 15 * 60) SECOND), INTERVAL 1500 SECOND)),
(10, 'SO202400306', 3, 3, '家用电器', 5500.00, 3, '221.2.2.2', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 15 DAY)), INTERVAL (9 * 3600 + 15 * 60) SECOND), INTERVAL 400 SECOND)),
(11, 'SO202400401', 4, 4, '虚拟卡券', 5000.00, 3, '222.3.3.3', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 8 SECOND)),
(12, 'SO202400501', 5, 5, '美妆', 2600.00, 2, '223.4.4.4', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 7200 SECOND)),
(13, 'SO202400502', 5, 5, '美妆', 1800.00, 1, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 2 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(14, 'SO202400503', 5, 5, '美妆', 2200.00, 2, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 4 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 1100 SECOND)),
(15, 'SO202400504', 5, 5, '美妆', 1600.00, 1, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 5 DAY)), INTERVAL (9 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(16, 'SO202400505', 5, 5, '个护', 2400.00, 3, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 8 DAY)), INTERVAL (16 * 3600 + 15 * 60) SECOND), INTERVAL 1300 SECOND)),
(17, 'SO202400506', 5, 5, '个护', 1900.00, 1, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 11 DAY)), INTERVAL (12 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(18, 'SO202400507', 5, 5, '美妆', 2100.00, 2, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 14 DAY)), INTERVAL (18 * 3600 + 15 * 60) SECOND), INTERVAL 750 SECOND)),
(19, 'SO202400508', 5, 5, '美妆', 1700.00, 1, '223.4.4.4', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 17 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 1000 SECOND)),
(20, 'SO202400509', 5, 5, '个护', 2000.00, 2, '223.4.4.4', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 21 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(21, 'SO202400510', 5, 5, '美妆', 1500.00, 1, '223.4.4.4', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 25 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 950 SECOND)),
(22, 'SO202400601', 6, 6, '数码配件', 2600.00, 2, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (16 * 3600 + 15 * 60) SECOND), INTERVAL 60 SECOND)),
(23, 'SO202400602', 6, 6, '数码配件', 1500.00, 1, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 2 DAY)), INTERVAL (13 * 3600 + 15 * 60) SECOND), INTERVAL 500 SECOND)),
(24, 'SO202400603', 6, 6, '数码配件', 1700.00, 1, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 4 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(25, 'SO202400604', 6, 6, '数码配件', 1400.00, 2, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 7 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(26, 'SO202400605', 6, 6, '数码配件', 1600.00, 1, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 10 DAY)), INTERVAL (20 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(27, 'SO202400606', 6, 6, '数码配件', 1300.00, 1, '224.5.5.5', '已退款', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 13 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 1200 SECOND)),
(28, 'SO202400607', 6, 6, '数码配件', 1200.00, 1, '224.5.5.5', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 40 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(29, 'SO202400608', 6, 6, '数码配件', 1100.00, 1, '224.5.5.5', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 50 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(30, 'SO202400701', 7, 7, '食品', 800.00, 1, '225.6.6.6', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (12 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(31, 'SO202400702', 7, 7, '食品', 500.00, 1, '225.6.6.6', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 12 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(32, 'SO202400801', 8, 8, '家居', 1500.00, 2, '226.7.7.7', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (13 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(33, 'SO202400802', 8, 8, '家居', 900.00, 1, '226.7.7.7', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 15 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(34, 'SO202400901', 9, 9, '日用品', 300.00, 1, '227.8.8.8', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 500 SECOND)),
(35, 'SO202400902', 9, 9, '日用品', 260.00, 1, '227.8.8.8', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 5 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(36, 'SO202400903', 9, 9, '日用品', 420.00, 2, '227.8.8.8', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 12 DAY)), INTERVAL (16 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(37, 'SO202400904', 9, 9, '日用品', 180.00, 1, '227.8.8.8', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 18 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 550 SECOND)),
(38, 'SO202400905', 9, 9, '日用品', 350.00, 1, '227.8.8.8', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 26 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 650 SECOND)),
(39, 'SO202401001', 10, 10, '服饰', 6000.00, 3, '228.9.9.9', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(40, 'SO202401002', 10, 15, '服饰', 2000.00, 1, '228.9.9.9', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 3 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(41, 'SO202401003', 10, 16, '服饰', 2100.00, 2, '228.9.9.9', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 5 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(42, 'SO202401004', 10, 15, '服饰', 1900.00, 1, '228.9.9.9', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 6 DAY)), INTERVAL (15 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(43, 'SO202401101', 11, 11, '图书', 4000.00, 5, '229.10.10.10', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (13 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND)),
(44, 'SO202401201', 12, 12, '鞋靴', 3200.00, 2, '230.11.11.11', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 0 DAY)), INTERVAL (14 * 3600 + 15 * 60) SECOND), INTERVAL 900 SECOND)),
(45, 'SO202401202', 12, 12, '鞋靴', 500.00, 1, '230.11.11.11', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 3 DAY)), INTERVAL (11 * 3600 + 15 * 60) SECOND), INTERVAL 600 SECOND)),
(46, 'SO202401203', 12, 12, '鞋靴', 480.00, 1, '230.11.11.11', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 5 DAY)), INTERVAL (16 * 3600 + 15 * 60) SECOND), INTERVAL 700 SECOND)),
(47, 'SO202401204', 12, 12, '鞋靴', 520.00, 1, '230.11.11.11', '已支付', DATE_SUB(DATE_ADD(DATE(DATE_SUB(NOW(), INTERVAL 20 DAY)), INTERVAL (10 * 3600 + 15 * 60) SECOND), INTERVAL 800 SECOND));

-- ---------- 支付记录（支付时间 = 下单时间 + 支付间隔，秒数精确可控） ----------
INSERT INTO payments (order_id, user_id, amount, channel, paid_at)
SELECT o.id, o.user_id, o.amount, '在线支付', DATE_ADD(o.created_at, INTERVAL (CASE o.id WHEN 1 THEN 1500 WHEN 2 THEN 800 WHEN 3 THEN 600 WHEN 5 THEN 3600 WHEN 6 THEN 900 WHEN 7 THEN 1200 WHEN 8 THEN 700 WHEN 9 THEN 1500 WHEN 10 THEN 400 WHEN 11 THEN 8 WHEN 12 THEN 7200 WHEN 13 THEN 900 WHEN 14 THEN 1100 WHEN 15 THEN 600 WHEN 16 THEN 1300 WHEN 17 THEN 900 WHEN 18 THEN 750 WHEN 19 THEN 1000 WHEN 20 THEN 800 WHEN 21 THEN 950 WHEN 22 THEN 60 WHEN 23 THEN 500 WHEN 24 THEN 800 WHEN 25 THEN 900 WHEN 26 THEN 700 WHEN 27 THEN 1200 WHEN 28 THEN 800 WHEN 29 THEN 900 WHEN 30 THEN 600 WHEN 31 THEN 700 WHEN 32 THEN 900 WHEN 33 THEN 800 WHEN 34 THEN 500 WHEN 35 THEN 600 WHEN 36 THEN 700 WHEN 37 THEN 550 WHEN 38 THEN 650 WHEN 39 THEN 900 WHEN 40 THEN 800 WHEN 41 THEN 700 WHEN 42 THEN 600 WHEN 43 THEN 800 WHEN 44 THEN 900 WHEN 45 THEN 600 WHEN 46 THEN 700 WHEN 47 THEN 800 END) SECOND)
FROM orders o WHERE o.id IN (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47);

-- ---------- 退款记录（U1005 退款狂魔 / U1006 顽固退款） ----------
INSERT INTO refunds (order_id, user_id, amount, reason, status, applied_at) VALUES
(1, 5, 2600.00, '商品与描述不符', '已退款', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(2, 5, 1800.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(3, 5, 2200.00, '质量问题', '已退款', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(4, 5, 1600.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(5, 5, 2400.00, '质量问题', '已退款', DATE_SUB(NOW(), INTERVAL 8 DAY)),
(6, 5, 1900.00, '拍错/多拍', '已退款', DATE_SUB(NOW(), INTERVAL 11 DAY)),
(7, 5, 2100.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 14 DAY)),
(8, 6, 2600.00, '商品与描述不符', '已退款', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(9, 6, 1500.00, '质量问题', '已退款', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(10, 6, 1700.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(11, 6, 1400.00, '质量问题', '已退款', DATE_SUB(NOW(), INTERVAL 8 DAY)),
(12, 6, 1600.00, '拍错/多拍', '已退款', DATE_SUB(NOW(), INTERVAL 11 DAY)),
(13, 6, 1300.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 14 DAY)),
(14, 3, 5500.00, '七天无理由退货', '已退款', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(15, 9, 420.00, '拍错/多拍', '已完成', DATE_SUB(NOW(), INTERVAL 11 DAY));

-- ---------- 投诉记录（U1007 投诉 3 次 / U1008 投诉 4 次） ----------
INSERT INTO complaints (order_id, user_id, complaint_type, description, created_at) VALUES
(1, 30, 7, '物流延迟', '包裹超过 7 天未更新物流', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(2, 30, 7, '包裹破损', '收到商品外包装严重破损', DATE_SUB(NOW(), INTERVAL 20 DAY)),
(3, 31, 7, '配送态度', '配送员未按约定时间上门', DATE_SUB(NOW(), INTERVAL 45 DAY)),
(4, 32, 8, '物流延迟', '同一订单三次延迟配送', DATE_SUB(NOW(), INTERVAL 6 DAY)),
(5, 32, 8, '虚假签收', '未收到货但显示已签收', DATE_SUB(NOW(), INTERVAL 15 DAY)),
(6, 33, 8, '包裹破损', '商品破损且缺少配件', DATE_SUB(NOW(), INTERVAL 30 DAY)),
(7, 33, 8, '退款纠纷', '退款迟迟未到账', DATE_SUB(NOW(), INTERVAL 60 DAY)),
(8, 13, 5, '物流延迟', '物流信息长时间未更新', DATE_SUB(NOW(), INTERVAL 10 DAY)),
(9, 23, 6, '退款纠纷', '退款金额与实付不一致', DATE_SUB(NOW(), INTERVAL 8 DAY));

-- ---------- 登录记录（U1011 24 小时内 4 个不同 IP） ----------
INSERT INTO user_logins (id, user_id, ip, login_time) VALUES
(1, 11, '229.10.10.10', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 2 HOUR)),
(2, 11, '229.10.10.11', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 8 HOUR)),
(3, 11, '229.10.10.12', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 15 HOUR)),
(4, 11, '229.10.10.13', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 22 HOUR)),
(5, 11, '229.10.10.10', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 5 HOUR)),
(6, 1, '58.22.1.99', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 3 HOUR)),
(7, 1, '113.10.1.5', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 20 HOUR)),
(8, 2, '220.1.1.1', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 5 HOUR)),
(9, 3, '221.2.2.2', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 4 HOUR)),
(10, 3, '221.2.2.9', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 18 HOUR)),
(11, 4, '222.3.3.3', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 6 HOUR)),
(12, 5, '223.4.4.4', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 7 HOUR)),
(13, 5, '223.4.4.9', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 19 HOUR)),
(14, 6, '224.5.5.5', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 8 HOUR)),
(15, 7, '225.6.6.6', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 9 HOUR)),
(16, 8, '226.7.7.7', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 10 HOUR)),
(17, 9, '227.8.8.8', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 11 HOUR)),
(18, 9, '227.8.8.9', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 21 HOUR)),
(19, 10, '228.9.9.9', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 12 HOUR)),
(20, 12, '230.11.11.11', DATE_SUB(DATE_SUB(NOW(), INTERVAL 0 DAY), INTERVAL 13 HOUR));

-- ---------- 物流轨迹 ----------
INSERT INTO logistics (id, order_id, status, description, updated_at) VALUES
(1, 1, '运输中', '订单 SO202400101 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(2, 2, '已签收', '订单 SO202400102 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 9 DAY)),
(3, 3, '已签收', '订单 SO202400103 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 19 DAY)),
(4, 5, '运输中', '订单 SO202400301 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(5, 6, '已签收', '订单 SO202400302 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(6, 7, '已签收', '订单 SO202400303 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(7, 8, '已签收', '订单 SO202400304 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 8 DAY)),
(8, 9, '已签收', '订单 SO202400305 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 11 DAY)),
(9, 10, '已签收', '订单 SO202400306 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 14 DAY)),
(10, 11, '运输中', '订单 SO202400401 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(11, 12, '运输中', '订单 SO202400501 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(12, 13, '已签收', '订单 SO202400502 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(13, 14, '已签收', '订单 SO202400503 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(14, 15, '已签收', '订单 SO202400504 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(15, 16, '已签收', '订单 SO202400505 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 7 DAY)),
(16, 17, '已签收', '订单 SO202400506 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 10 DAY)),
(17, 18, '已签收', '订单 SO202400507 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 13 DAY)),
(18, 19, '已签收', '订单 SO202400508 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 16 DAY)),
(19, 20, '已签收', '订单 SO202400509 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 20 DAY)),
(20, 21, '已签收', '订单 SO202400510 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 24 DAY)),
(21, 22, '已签收', '订单 SO202400601 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(22, 23, '已签收', '订单 SO202400602 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(23, 24, '已签收', '订单 SO202400603 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(24, 25, '已签收', '订单 SO202400604 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 6 DAY)),
(25, 26, '已签收', '订单 SO202400605 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 9 DAY)),
(26, 27, '已签收', '订单 SO202400606 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 12 DAY)),
(27, 28, '已签收', '订单 SO202400607 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 39 DAY)),
(28, 29, '已签收', '订单 SO202400608 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 49 DAY)),
(29, 30, '运输中', '订单 SO202400701 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(30, 31, '已签收', '订单 SO202400702 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 11 DAY)),
(31, 32, '运输中', '订单 SO202400801 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(32, 33, '已签收', '订单 SO202400802 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 14 DAY)),
(33, 34, '运输中', '订单 SO202400901 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(34, 35, '已签收', '订单 SO202400902 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(35, 36, '已签收', '订单 SO202400903 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 11 DAY)),
(36, 37, '已签收', '订单 SO202400904 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 17 DAY)),
(37, 38, '已签收', '订单 SO202400905 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 25 DAY)),
(38, 39, '运输中', '订单 SO202401001 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(39, 40, '已签收', '订单 SO202401002 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(40, 41, '已签收', '订单 SO202401003 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(41, 42, '已签收', '订单 SO202401004 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(42, 43, '运输中', '订单 SO202401101 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(43, 44, '运输中', '订单 SO202401201 物流状态：运输中', DATE_SUB(NOW(), INTERVAL 0 DAY)),
(44, 45, '已签收', '订单 SO202401202 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(45, 46, '已签收', '订单 SO202401203 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 4 DAY)),
(46, 47, '已签收', '订单 SO202401204 物流状态：已签收', DATE_SUB(NOW(), INTERVAL 19 DAY));

-- ---------- 黑名单（3 条生效 + 1 条停用演示） ----------
INSERT INTO blacklists (id, blacklist_type, blacklist_value, remark, status, created_at) VALUES
(1, 'user', 'U1001', '历史欺诈行为，确认为恶意账号，永久拉黑', 'active', DATE_SUB(NOW(), INTERVAL 120 DAY)),
(2, 'ip', '58.22.1.99', '高风险设备 IP，关联多起团伙欺诈', 'active', DATE_SUB(NOW(), INTERVAL 90 DAY)),
(3, 'address', 'O市P区长江路8号8栋808', '虚假收货地址，批量刷单专用', 'active', DATE_SUB(NOW(), INTERVAL 60 DAY)),
(4, 'user', 'U1099', '已申诉成功解除拉黑（演示停用状态）', 'disabled', DATE_SUB(NOW(), INTERVAL 30 DAY));

-- ---------- 24 条风险规则（覆盖用户/订单/地址三类维度） ----------
INSERT INTO risk_rules (id, rule_code, rule_name, rule_status, priority, score, condition_json, description, updated_at) VALUES
(1, 'R_BLACKLIST_USER', '用户黑名单命中', 'enabled', 1, 40, '{"all": [{"op": "eq", "feature": "user_blacklisted", "value": 1}]}', '用户编号命中黑名单且状态为生效，直接高风险', NOW()),
(2, 'R_BLACKLIST_ADDRESS', '收货地址黑名单', 'enabled', 2, 35, '{"all": [{"op": "eq", "feature": "address_blacklisted", "value": 1}]}', '收货地址命中黑名单，常见于虚假地址刷单', NOW()),
(3, 'R_BLACKLIST_IP', '设备IP黑名单', 'enabled', 3, 30, '{"all": [{"op": "eq", "feature": "address_ip_blacklisted", "value": 1}]}', '下单设备IP命中黑名单，疑似团伙作案设备', NOW()),
(4, 'R_NEW_USER_BIG_ORDER', '新注册大额下单', 'enabled', 4, 30, '{"all": [{"op": "eq", "feature": "user_first_order_flag", "value": 1}, {"op": "lte", "feature": "user_age_days", "value": 7}, {"op": "gte", "feature": "order_amount", "value": 5000}]}', '注册 7 天内首单金额超过 5000 元', NOW()),
(5, 'R_AMOUNT_SPIKE', '订单金额突增', 'enabled', 5, 25, '{"all": [{"op": "gte", "feature": "order_amount_ratio", "value": 5}, {"op": "gte", "feature": "order_amount", "value": 3000}]}', '本单金额超过该用户历史已支付订单均价的 5 倍', NOW()),
(6, 'R_REFUND_ABUSER', '退款狂魔', 'enabled', 6, 25, '{"all": [{"op": "gte", "feature": "user_refund_ratio", "value": 0.5}, {"op": "gte", "feature": "user_orders_30d", "value": 5}, {"op": "gte", "feature": "user_paid_amount_30d", "value": 5000}]}', '近 30 天下单 5 笔以上且退款占比超过 50%', NOW()),
(7, 'R_COMPLAINT_ABUSER', '投诉惯犯', 'enabled', 7, 20, '{"all": [{"op": "gte", "feature": "user_complaints_90d", "value": 3}]}', '近 90 天投诉次数达到 3 次以上', NOW()),
(8, 'R_LATE_NIGHT_PAY', '深夜支付', 'enabled', 8, 10, '{"any": [{"op": "gte", "feature": "order_pay_hour", "value": 23}, {"op": "lte", "feature": "order_pay_hour", "value": 4}]}', '支付时间落在 23 点至次日 4 点之间', NOW()),
(9, 'R_LATE_NIGHT_HIGH_AMOUNT', '深夜大额支付', 'enabled', 9, 30, '{"all": [{"op": "gte", "feature": "order_pay_hour", "value": 22}, {"op": "gte", "feature": "order_amount", "value": 8000}]}', '22 点后支付且订单金额超过 8000 元', NOW()),
(10, 'R_MULTI_ADDRESS_7D', '短时多收货地址', 'enabled', 10, 25, '{"all": [{"op": "gte", "feature": "address_change_count_7d", "value": 3}]}', '近 7 天使用 3 个以上不同收货地址', NOW()),
(11, 'R_ADDRESS_SHARED', '收货地址多人共用', 'enabled', 11, 20, '{"all": [{"op": "gte", "feature": "address_shared_user_count", "value": 3}]}', '同一收货地址被 3 个以上用户使用，疑似刷单窝点', NOW()),
(12, 'R_PHONE_SHARED', '收货手机号多人共用', 'enabled', 12, 15, '{"all": [{"op": "gte", "feature": "address_phone_shared_count", "value": 3}]}', '同一收货手机号被 3 个以上用户使用', NOW()),
(13, 'R_IP_MULTI_USER', '单IP多用户下单', 'enabled', 13, 20, '{"all": [{"op": "gte", "feature": "address_ip_user_count", "value": 3}]}', '同一个设备 IP 关联 3 个以上用户', NOW()),
(14, 'R_MULTI_IP_LOGIN', '短时多IP登录', 'enabled', 14, 25, '{"all": [{"op": "gte", "feature": "user_login_ip_count_24h", "value": 3}]}', '24 小时内使用 3 个以上 IP 登录，疑似账号被盗', NOW()),
(15, 'R_FLASH_PAY', '秒级支付', 'enabled', 15, 10, '{"all": [{"op": "lte", "feature": "order_pay_gap_seconds", "value": 10}]}', '下单后 10 秒内完成支付，疑似脚本批量操作', NOW()),
(16, 'R_VIRTUAL_CATEGORY_BIG', '高敏类目大额下单', 'enabled', 16, 20, '{"all": [{"op": "contains", "feature": "order_category", "value": ["虚拟卡券", "数码3C"]}, {"op": "gte", "feature": "order_amount", "value": 3000}, {"op": "gte", "feature": "order_items_count", "value": 3}]}', '虚拟卡券/数码3C 等易变现类目大额多件下单', NOW()),
(17, 'R_ORDER_STATUS_REFUNDED', '已退款订单再次申请售后', 'enabled', 17, 5, '{"all": [{"op": "eq", "feature": "order_status", "value": "已退款"}]}', '订单已退款仍发起售后申请', NOW()),
(18, 'R_HIGH_RISK_AFTER_SALE', '高频售后退款用户', 'enabled', 18, 20, '{"all": [{"op": "eq", "feature": "event_type", "value": "after_sale_apply"}, {"op": "gte", "feature": "order_amount", "value": 1000}, {"op": "gte", "feature": "user_refund_ratio", "value": 0.3}, {"op": "gte", "feature": "order_after_sale_count", "value": 1}]}', '售后申请 + 订单金额较高 + 历史退款占比超过 30%', NOW()),
(19, 'R_COMPLAINT_NEW_USER', '低活跃用户投诉', 'enabled', 19, 15, '{"all": [{"op": "eq", "feature": "event_type", "value": "logistics_complaint"}, {"op": "lte", "feature": "user_orders_30d", "value": 2}]}', '下单量很少却频繁发起物流投诉', NOW()),
(20, 'R_PRIOR_REJECTED', '历史被拒用户', 'enabled', 20, 15, '{"all": [{"op": "neq", "feature": "user_rejected_count", "value": 0}]}', '该用户历史风险检查存在拒绝处置记录', NOW()),
(21, 'R_NEW_ADDRESS_HIGH_AMOUNT', '新收货地址大额下单', 'enabled', 21, 25, '{"all": [{"op": "eq", "feature": "address_is_new_for_user", "value": 1}, {"op": "gte", "feature": "order_amount", "value": 6000}]}', '首次使用的收货地址且订单金额超过 6000 元', NOW()),
(22, 'R_LOW_ACTIVITY_HIGH_AMOUNT', '低活跃老用户大额下单', 'enabled', 22, 20, '{"all": [{"op": "lte", "feature": "user_orders_30d", "value": 1}, {"op": "gte", "feature": "order_amount", "value": 4000}, {"op": "gt", "feature": "user_age_days", "value": 7}]}', '注册超过 7 天但近 30 天几乎无下单，突然大额下单', NOW()),
(23, 'R_AMOUNT_ABNORMAL_HIGH', '订单金额异常超大', 'enabled', 23, 30, '{"all": [{"op": "gt", "feature": "order_amount", "value": 20000}]}', '单笔订单金额超过 20000 元', NOW()),
(24, 'R_AFTER_SALE_QUICK_REFUND', '秒付秒退', 'enabled', 24, 15, '{"all": [{"op": "eq", "feature": "event_type", "value": "after_sale_apply"}, {"op": "lt", "feature": "order_pay_gap_seconds", "value": 300}]}', '支付后 5 分钟内即发起售后申请', NOW());

-- ---------- 历史风险检查记录（让看板在演示开始前即有数据） ----------
INSERT INTO risk_events (id, event_type, source_id, user_id, order_id, event_payload_json, created_at) VALUES
(1, 'after_sale_apply', 'backfill_SO202400606', 'U1006', 'SO202400606', '{"user_id": "U1006", "order_id": "SO202400606", "event_type": "after_sale_apply", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 'after_sale_apply', 'backfill_SO202400605', 'U1006', 'SO202400605', '{"user_id": "U1006", "order_id": "SO202400605", "event_type": "after_sale_apply", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(3, 'order_create', 'backfill_SO202400102', 'U1001', 'SO202400102', '{"user_id": "U1001", "order_id": "SO202400102", "event_type": "order_create", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 'order_pay', 'backfill_SO202400302', 'U1003', 'SO202400302', '{"user_id": "U1003", "order_id": "SO202400302", "event_type": "order_pay", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(5, 'after_sale_apply', 'backfill_SO202400503', 'U1005', 'SO202400503', '{"user_id": "U1005", "order_id": "SO202400503", "event_type": "after_sale_apply", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(6, 'after_sale_apply', 'backfill_SO202400505', 'U1005', 'SO202400505', '{"user_id": "U1005", "order_id": "SO202400505", "event_type": "after_sale_apply", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(7, 'logistics_complaint', 'backfill_SO202400702', 'U1007', 'SO202400702', '{"user_id": "U1007", "order_id": "SO202400702", "event_type": "logistics_complaint", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(8, 'logistics_complaint', 'backfill_SO202400802', 'U1008', 'SO202400802', '{"user_id": "U1008", "order_id": "SO202400802", "event_type": "logistics_complaint", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(9, 'order_create', 'backfill_SO202401202', 'U1012', 'SO202401202', '{"user_id": "U1012", "order_id": "SO202401202", "event_type": "order_create", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(10, 'order_create', 'backfill_SO202400903', 'U1009', 'SO202400903', '{"user_id": "U1009", "order_id": "SO202400903", "event_type": "order_create", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR)),
(11, 'order_pay', 'backfill_SO202400904', 'U1009', 'SO202400904', '{"user_id": "U1009", "order_id": "SO202400904", "event_type": "order_pay", "source_type": "离线批量回溯"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR));

INSERT INTO risk_assessments (id, event_id, risk_score, risk_level, decision, assessment_status, created_at) VALUES
(1, 1, 80, 'high', 'reject', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 2, 75, 'high', 'reject', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(3, 3, 30, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 4, 45, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(5, 5, 45, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(6, 6, 45, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(7, 7, 35, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(8, 8, 35, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(9, 9, 55, 'medium', 'manual_review', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(10, 10, 0, 'low', 'pass', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR)),
(11, 11, 0, 'low', 'pass', 'completed', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR));

INSERT INTO feature_snapshots (id, assessment_id, feature_json, created_at) VALUES
(1, 1, '{"user_age_days": 300, "user_orders_30d": 6, "user_paid_amount_30d": 10100.0, "user_refund_ratio": 0.75, "user_complaints_90d": 1, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 1, "order_amount": 1300.0, "order_items_count": 1, "order_pay_hour": 10, "order_pay_gap_seconds": 1200, "order_amount_ratio": 0.82, "order_after_sale_count": 1, "order_category": "数码配件", "order_status": "已退款", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "after_sale_apply"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 2, '{"user_age_days": 300, "user_orders_30d": 6, "user_paid_amount_30d": 10100.0, "user_refund_ratio": 0.75, "user_complaints_90d": 1, "user_rejected_count": 1, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 1, "order_amount": 1600.0, "order_items_count": 1, "order_pay_hour": 20, "order_pay_gap_seconds": 700, "order_amount_ratio": 1.04, "order_after_sale_count": 1, "order_category": "数码配件", "order_status": "已退款", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "after_sale_apply"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(3, 3, '{"user_age_days": 400, "user_orders_30d": 3, "user_paid_amount_30d": 4000.0, "user_refund_ratio": 0.0, "user_complaints_90d": 0, "user_rejected_count": 0, "user_blacklisted": 1, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 1200.0, "order_items_count": 1, "order_pay_hour": 11, "order_pay_gap_seconds": 800, "order_amount_ratio": 0.86, "order_after_sale_count": 0, "order_category": "服装", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 1, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "order_create"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 4, '{"user_age_days": 500, "user_orders_30d": 6, "user_paid_amount_30d": 52500.0, "user_refund_ratio": 0.1667, "user_complaints_90d": 0, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 5500.0, "order_items_count": 1, "order_pay_hour": 14, "order_pay_gap_seconds": 900, "order_amount_ratio": 0.59, "order_after_sale_count": 0, "order_category": "家用电器", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "order_pay"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(5, 5, '{"user_age_days": 350, "user_orders_30d": 10, "user_paid_amount_30d": 19800.0, "user_refund_ratio": 0.7, "user_complaints_90d": 1, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 2200.0, "order_items_count": 2, "order_pay_hour": 15, "order_pay_gap_seconds": 1100, "order_amount_ratio": 1.12, "order_after_sale_count": 1, "order_category": "美妆", "order_status": "已退款", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "after_sale_apply"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(6, 6, '{"user_age_days": 350, "user_orders_30d": 10, "user_paid_amount_30d": 19800.0, "user_refund_ratio": 0.7, "user_complaints_90d": 1, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 2400.0, "order_items_count": 3, "order_pay_hour": 16, "order_pay_gap_seconds": 1300, "order_amount_ratio": 1.24, "order_after_sale_count": 1, "order_category": "个护", "order_status": "已退款", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "after_sale_apply"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(7, 7, '{"user_age_days": 120, "user_orders_30d": 2, "user_paid_amount_30d": 1300.0, "user_refund_ratio": 0.0, "user_complaints_90d": 3, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 1, "user_login_ip_count_24h": 1, "order_amount": 500.0, "order_items_count": 1, "order_pay_hour": 11, "order_pay_gap_seconds": 700, "order_amount_ratio": 0.62, "order_after_sale_count": 0, "order_category": "食品", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "logistics_complaint"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(8, 8, '{"user_age_days": 260, "user_orders_30d": 2, "user_paid_amount_30d": 2400.0, "user_refund_ratio": 0.0, "user_complaints_90d": 4, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 1, "user_login_ip_count_24h": 1, "order_amount": 900.0, "order_items_count": 1, "order_pay_hour": 10, "order_pay_gap_seconds": 800, "order_amount_ratio": 0.6, "order_after_sale_count": 0, "order_category": "家居", "order_status": "已支付", "address_blacklisted": 1, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "logistics_complaint"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(9, 9, '{"user_age_days": 180, "user_orders_30d": 4, "user_paid_amount_30d": 4700.0, "user_refund_ratio": 0.0, "user_complaints_90d": 0, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 1, "order_amount": 500.0, "order_items_count": 1, "order_pay_hour": 11, "order_pay_gap_seconds": 600, "order_amount_ratio": 0.36, "order_after_sale_count": 0, "order_category": "鞋靴", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 3, "address_phone_shared_count": 3, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "order_create"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(10, 10, '{"user_age_days": 600, "user_orders_30d": 5, "user_paid_amount_30d": 1510.0, "user_refund_ratio": 0.2, "user_complaints_90d": 0, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 420.0, "order_items_count": 2, "order_pay_hour": 16, "order_pay_gap_seconds": 700, "order_amount_ratio": 1.54, "order_after_sale_count": 1, "order_category": "日用品", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "order_create"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR)),
(11, 11, '{"user_age_days": 600, "user_orders_30d": 5, "user_paid_amount_30d": 1510.0, "user_refund_ratio": 0.2, "user_complaints_90d": 0, "user_rejected_count": 0, "user_blacklisted": 0, "user_first_order_flag": 0, "user_login_ip_count_24h": 2, "order_amount": 180.0, "order_items_count": 1, "order_pay_hour": 15, "order_pay_gap_seconds": 550, "order_amount_ratio": 0.54, "order_after_sale_count": 0, "order_category": "日用品", "order_status": "已支付", "address_blacklisted": 0, "address_ip_blacklisted": 0, "address_change_count_7d": 1, "address_shared_user_count": 1, "address_phone_shared_count": 1, "address_is_new_for_user": 0, "address_ip_user_count": 1, "event_type": "order_pay"}', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 2 HOUR));

INSERT INTO rule_hits (id, assessment_id, rule_id, hit_score, hit_message, created_at) VALUES
(1, 1, 6, 25, '命中规则【退款狂魔】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 1, 18, 20, '命中规则【高频售后退款用户】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(3, 1, 20, 15, '命中规则【历史被拒用户】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 2, 6, 25, '命中规则【退款狂魔】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(5, 2, 18, 20, '命中规则【高频售后退款用户】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(6, 3, 3, 30, '命中规则【设备IP黑名单】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(7, 4, 8, 10, '命中规则【深夜支付】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(8, 4, 5, 25, '命中规则【订单金额突增】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(9, 5, 6, 25, '命中规则【退款狂魔】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(10, 5, 18, 20, '命中规则【高频售后退款用户】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(11, 6, 6, 25, '命中规则【退款狂魔】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(12, 6, 18, 20, '命中规则【高频售后退款用户】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(13, 7, 7, 20, '命中规则【投诉惯犯】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(14, 7, 19, 15, '命中规则【低活跃用户投诉】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(15, 8, 7, 20, '命中规则【投诉惯犯】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(16, 8, 19, 15, '命中规则【低活跃用户投诉】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(17, 9, 11, 20, '命中规则【收货地址多人共用】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(18, 9, 12, 15, '命中规则【收货手机号多人共用】', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR));

INSERT INTO risk_cases (id, assessment_id, user_id, order_id, case_status, reviewer_id, review_result, created_at, updated_at) VALUES
(1, 1, 'U1006', 'SO202400606', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 2, 'U1006', 'SO202400605', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(3, 3, 'U1001', 'SO202400102', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 4, 'U1003', 'SO202400302', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(5, 5, 'U1005', 'SO202400503', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(6, 6, 'U1005', 'SO202400505', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(7, 7, 'U1007', 'SO202400702', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(8, 8, 'U1008', 'SO202400802', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(9, 9, 'U1012', 'SO202401202', 'pending', NULL, NULL, DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR), DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR));

UPDATE risk_cases SET case_status = 'resolved', reviewer_id = '风控审核员-李芳', review_result = 'reject', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 1 HOUR) WHERE id = 1;
UPDATE risk_cases SET case_status = 'rejected', reviewer_id = '风控审核员-李芳', review_result = 'reject', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 1 HOUR) WHERE id = 2;
UPDATE risk_cases SET case_status = 'approved', reviewer_id = '风控审核员-王明', review_result = 'approve', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 1 HOUR) WHERE id = 3;
UPDATE risk_cases SET case_status = 'resolved', reviewer_id = '风控审核员-王明', review_result = 'resolve', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 1 HOUR) WHERE id = 4;
UPDATE risk_cases SET case_status = 'resolved', reviewer_id = '风控审核员-李芳', review_result = 'resolve', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 1 HOUR) WHERE id = 5;
UPDATE risk_cases SET case_status = 'pending', reviewer_id = NULL, review_result = NULL, updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 1 HOUR) WHERE id = 6;
UPDATE risk_cases SET case_status = 'reviewing', reviewer_id = NULL, review_result = NULL, updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 1 HOUR) WHERE id = 7;
UPDATE risk_cases SET case_status = 'resolved', reviewer_id = '风控审核员-张涛', review_result = 'reject', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 1 HOUR) WHERE id = 8;
UPDATE risk_cases SET case_status = 'approved', reviewer_id = '风控审核员-王明', review_result = 'approve', updated_at = DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 1 HOUR) WHERE id = 9;

-- ---------- 历史审核日志（处置留痕） ----------
INSERT INTO review_logs (id, case_id, operator_id, action_type, action_remark, created_at) VALUES
(1, 1, '系统', 'create', '风险等级 high，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(2, 2, '系统', 'create', '风险等级 high，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 2 HOUR)),
(3, 3, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 6 DAY), INTERVAL 2 HOUR)),
(4, 4, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(5, 5, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 2 HOUR)),
(6, 6, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(7, 7, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 2 HOUR)),
(8, 8, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(9, 9, '系统', 'create', '风险等级 medium，自动创建案件', DATE_SUB(DATE_SUB(NOW(), INTERVAL 2 DAY), INTERVAL 2 HOUR)),
(10, 1, '风控审核员-李芳', 'review', '确认为恶意退款，驳回并加入观察名单', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 1 HOUR)),
(11, 1, '风控审核员-李芳', 'resolve', '处置结论已执行，案件结案', DATE_SUB(NOW(), INTERVAL 5 DAY)),
(12, 2, '风控审核员-李芳', 'review', '同上，维持拒绝处置', DATE_SUB(DATE_SUB(NOW(), INTERVAL 3 DAY), INTERVAL 1 HOUR)),
(13, 3, '风控审核员-王明', 'review', '核实为正常老用户调换设备，予以放行', DATE_SUB(DATE_SUB(NOW(), INTERVAL 5 DAY), INTERVAL 1 HOUR)),
(14, 4, '风控审核员-王明', 'resolve', '联系用户确认为本人操作，予以结案', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 1 HOUR)),
(15, 5, '风控审核员-李芳', 'resolve', '售后正常，已引导走平台退货流程', DATE_SUB(DATE_SUB(NOW(), INTERVAL 4 DAY), INTERVAL 1 HOUR)),
(16, 8, '风控审核员-张涛', 'review', '地址确认为刷单窝点，拒绝并拉黑', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 1 HOUR)),
(17, 8, '风控审核员-张涛', 'resolve', '处置结论已执行，案件结案', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(18, 9, '风控审核员-王明', 'review', '家庭共享账号，核实后放行', DATE_SUB(DATE_SUB(NOW(), INTERVAL 1 DAY), INTERVAL 1 HOUR));

-- 统计：12 用户 / 16 地址 / 47 订单 / 24 规则 / 4 黑名单
SELECT (SELECT COUNT(*) FROM users) AS users,
       (SELECT COUNT(*) FROM orders) AS orders,
       (SELECT COUNT(*) FROM risk_rules) AS rules,
       (SELECT COUNT(*) FROM blacklists) AS blacklists;