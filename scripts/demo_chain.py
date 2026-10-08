"""完整演示链路 + 验收断言脚本（零第三方依赖，仅用标准库 urllib）。

前置条件：后端服务已启动（start.bat 或 uvicorn）。
用法：
    python scripts/demo_chain.py
    python scripts/demo_chain.py --base-url http://127.0.0.1:8005

脚本会按顺序验证：
    A. 12 个用户的风险场景矩阵（评分 / 风险等级 / 命中规则）
    B. 「黑名单用户大额下单」8 步完整闭环（检查 → 建案 → 审核 → 留痕 → 复检）
    C. 黑名单增删与规则启停对评分的影响
    D. 运营看板统计指标
所有断言均可在重复执行下保持稳定（特征计算不依赖历史评估结果累积）。
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

BASE_URL = "http://127.0.0.1:8005"
PASSED, FAILED = [], []


# ---------------------------------------------------------------- HTTP 工具
def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}
    except urllib.error.URLError as exc:
        print(f"[致命] 无法连接后端服务 {BASE_URL}：{exc}")
        print("       请先启动服务（根目录执行 start.bat）后重试。")
        sys.exit(2)


def check(name: str, actual, expected) -> bool:
    ok = actual == expected
    (PASSED if ok else FAILED).append(name)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        print(f"         期望：{expected!r}")
        print(f"         实际：{actual!r}")
    return ok


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def risk_check(user_id: str, order_id: str, event_type: str, source_id: str = "demo_chain") -> dict:
    status, data = request("POST", "/api/risk/check",
                           {"event_type": event_type, "source_id": source_id,
                            "user_id": user_id, "order_id": order_id})
    if status != 200:
        raise SystemExit(f"风险检查失败 {user_id}/{order_id}: HTTP {status} {data}")
    return data


# ------------------------------------------------- A. 场景矩阵
SCENARIOS = [
    # (用户, 订单, 事件类型, 期望评分, 期望等级, 期望建议, 期望命中规则)
    ("U1001", "SO202400101", "order_create", 70, "high", "reject",
     ["R_BLACKLIST_USER", "R_BLACKLIST_IP"]),
    ("U1002", "SO202400201", "order_create", 55, "medium", "manual_review",
     ["R_NEW_USER_BIG_ORDER", "R_NEW_ADDRESS_HIGH_AMOUNT"]),
    ("U1003", "SO202400301", "order_pay", 70, "high", "reject",
     ["R_LATE_NIGHT_PAY", "R_LATE_NIGHT_HIGH_AMOUNT", "R_AMOUNT_ABNORMAL_HIGH"]),
    ("U1004", "SO202400401", "order_pay", 60, "medium", "manual_review",
     ["R_NEW_USER_BIG_ORDER", "R_FLASH_PAY", "R_VIRTUAL_CATEGORY_BIG"]),
    ("U1005", "SO202400501", "after_sale_apply", 45, "medium", "manual_review",
     ["R_REFUND_ABUSER", "R_HIGH_RISK_AFTER_SALE"]),
    ("U1006", "SO202400601", "after_sale_apply", 80, "high", "reject",
     ["R_REFUND_ABUSER", "R_ORDER_STATUS_REFUNDED", "R_HIGH_RISK_AFTER_SALE",
      "R_PRIOR_REJECTED", "R_AFTER_SALE_QUICK_REFUND"]),
    ("U1007", "SO202400701", "logistics_complaint", 35, "medium", "manual_review",
     ["R_COMPLAINT_ABUSER", "R_COMPLAINT_NEW_USER"]),
    ("U1008", "SO202400801", "logistics_complaint", 70, "high", "reject",
     ["R_BLACKLIST_ADDRESS", "R_COMPLAINT_ABUSER", "R_COMPLAINT_NEW_USER"]),
    ("U1009", "SO202400901", "order_create", 0, "low", "pass", []),
    ("U1010", "SO202401001", "order_create", 50, "medium", "manual_review",
     ["R_MULTI_ADDRESS_7D", "R_NEW_ADDRESS_HIGH_AMOUNT"]),
    ("U1011", "SO202401101", "order_create", 45, "medium", "manual_review",
     ["R_MULTI_IP_LOGIN", "R_LOW_ACTIVITY_HIGH_AMOUNT"]),
    ("U1012", "SO202401201", "order_create", 60, "medium", "manual_review",
     ["R_AMOUNT_SPIKE", "R_ADDRESS_SHARED", "R_PHONE_SHARED"]),
]


def run_scenarios():
    section("A. 风险场景矩阵（4 类业务事件 × 12 个用户画像）")
    for user_id, order_id, event_type, score, level, decision, rules in SCENARIOS:
        result = risk_check(user_id, order_id, event_type)
        hit_codes = sorted(h["rule_code"] for h in result["rule_hits"])
        print(f"\n[{user_id}] {event_type} / {order_id}")
        check(f"{user_id} 风险评分 = {score}", result["risk_score"], score)
        check(f"{user_id} 风险等级 = {level}", result["risk_level"], level)
        check(f"{user_id} 处理建议 = {decision}", result["decision"], decision)
        check(f"{user_id} 命中规则", hit_codes, sorted(rules))
        check(f"{user_id} 特征快照包含 25 项", len(result["feature_snapshot"]), 25)
        # 高风险或需人工审核时自动建案；低风险放行不应建案
        expect_case = level == "high" or decision in ("manual_review", "reject")
        check(f"{user_id} 自动建案 = {expect_case}", result["case_id"] is not None, expect_case)


# ------------------------------------------------- B. 完整闭环链路
def run_demo_chain():
    section("B. 命名演示链路：黑名单用户大额下单全流程")

    print("\n[步骤 1] 发起风险检查（order_create / U1001 / SO202400101）")
    result = risk_check("U1001", "SO202400101", "order_create")
    check("评分 70", result["risk_score"], 70)
    check("风险等级 high", result["risk_level"], "high")
    check("处理建议 reject", result["decision"], "reject")
    check("命中用户黑名单规则", [h["rule_code"] for h in result["rule_hits"]],
          ["R_BLACKLIST_USER", "R_BLACKLIST_IP"])
    check("命中原因可读", "命中规则【用户黑名单命中】" in result["rule_hits"][0]["hit_message"], True)
    assessment_id, case_id = result["assessment_id"], result["case_id"]
    check("高风险自动创建案件", case_id is not None, True)
    check("案件初始状态为审核中", result["case_status"], "reviewing")

    print("\n[步骤 2] 回查风险检查结果（特征快照 + 命中规则）")
    status, detail = request("GET", f"/api/risk/assessments/{assessment_id}")
    check("接口返回 200", status, 200)
    check("特征快照 25 项", len(detail["feature_snapshot"]), 25)
    check("快照含订单金额", detail["feature_snapshot"]["order_amount"], 2000.0)
    check("快照含命中用户黑名单标记", detail["feature_snapshot"]["user_blacklisted"], 1)
    check("命中规则 2 条", len(detail["rule_hits"]), 2)

    print("\n[步骤 3] 案件列表可查到该案件")
    status, cases = request("GET", "/api/risk/cases?order_id=SO202400101&page_size=50")
    check("案件列表包含新案件", any(c["id"] == case_id for c in cases["list"]), True)

    print("\n[步骤 4] 案件详情（风险结果 + 审核记录）")
    status, case_detail = request("GET", f"/api/risk/cases/{case_id}")
    check("接口返回 200", status, 200)
    check("案件详情含风险评分", case_detail["assessment"]["risk_score"], 70)
    check("案件详情含特征快照", len(case_detail["assessment"]["feature_snapshot"]), 25)
    check("审核日志含系统建案记录", case_detail["review_logs"][0]["action_type"], "create")

    print("\n[步骤 5] 人工审核：拒绝")
    status, reviewed = request("POST", "/api/risk/cases/review",
                               {"case_id": case_id, "review_result": "reject",
                                "review_remark": "确认为黑名单用户，拒绝交易", "reviewer_id": "风控审核员-李芳"})
    check("接口返回 200", status, 200)
    check("案件状态变为已拒绝", reviewed["case_status"], "rejected")

    print("\n[步骤 6] 结案归档")
    status, resolved = request("POST", "/api/risk/cases/review",
                               {"case_id": case_id, "review_result": "resolve",
                                "review_remark": "处置完成，案件结案", "reviewer_id": "风控审核员-李芳"})
    check("案件状态变为已结案", resolved["case_status"], "resolved")

    status, case_detail = request("GET", f"/api/risk/cases/{case_id}")
    check("审核日志累计 3 条（建案/审核/结案）", len(case_detail["review_logs"]), 3)
    check("审核结论已留痕", case_detail["review_result"], "resolve")
    check("审核人已留痕", case_detail["reviewer_id"], "风控审核员-李芳")

    print("\n[步骤 7] 移除黑名单后复检，风险应下降")
    status, blacklists = request("GET", "/api/risk/blacklists?page_size=50")
    target = next(b for b in blacklists["list"]
                  if b["blacklist_type"] == "user" and b["blacklist_value"] == "U1001")
    status, deleted = request("POST", "/api/risk/blacklists/delete", {"id": target["id"]})
    check("黑名单删除成功", status, 200)
    after = risk_check("U1001", "SO202400101", "order_create")
    check("复检评分降为 30", after["risk_score"], 30)
    check("复检等级降为 medium", after["risk_level"], "medium")
    check("复检建议变为 manual_review", after["decision"], "manual_review")
    check("仅剩 IP 黑名单命中", [h["rule_code"] for h in after["rule_hits"]], ["R_BLACKLIST_IP"])

    print("\n[步骤 8] 重新拉黑，风险回到高位")
    status, added = request("POST", "/api/risk/blacklists",
                            {"blacklist_type": "user", "blacklist_value": "U1001",
                             "remark": "演示重新拉黑", "status": "active"})
    check("黑名单新增成功", status, 200)
    restored = risk_check("U1001", "SO202400101", "order_create")
    check("复检评分恢复 70", restored["risk_score"], 70)
    check("复检等级恢复 high", restored["risk_level"], "high")

    print("\n[步骤 9] 停用规则后复检，规则立即失效")
    status, rules = request("GET", "/api/risk/rules")
    rule = next(r for r in rules["list"] if r["rule_code"] == "R_BLACKLIST_USER")
    status, toggled = request("POST", "/api/risk/rules/status",
                              {"id": rule["id"], "rule_status": "disabled"})
    check("规则停用成功", status, 200)
    disabled = risk_check("U1001", "SO202400101", "order_create")
    check("停用后评分降为 30", disabled["risk_score"], 30)

    print("\n[步骤 10] 重新启用规则，风险恢复")
    status, toggled = request("POST", "/api/risk/rules/status",
                              {"id": rule["id"], "rule_status": "enabled"})
    check("规则启用成功", status, 200)
    enabled = risk_check("U1001", "SO202400101", "order_create")
    check("启用后评分恢复 70", enabled["risk_score"], 70)


# ------------------------------------------------- C. 规则与黑名单管理
def run_management():
    section("C. 规则管理 / 黑名单管理 / 批量导入")

    print("\n[规则] 新增 → 更新 → 启停用 → 删除")
    new_rule = {
        "rule_code": "R_DEMO_TEMP", "rule_name": "演示临时规则", "rule_status": "enabled",
        "priority": 99, "score": 20,
        "condition_json": {"all": [{"op": "gte", "feature": "order_amount", "value": 100}]},
        "description": "演示脚本创建的临时规则",
    }
    status, created = request("POST", "/api/risk/rules", new_rule)
    check("新增规则返回 200", status, 200)
    rule_id = created.get("id")

    status, rules = request("GET", "/api/risk/rules")
    check("规则总数变为 25 条", rules["total"], 25)
    check("新增规则默认启用", next(r for r in rules["list"] if r["id"] == rule_id)["rule_status"], "enabled")

    # 新规则生效：任何金额 >= 100 的订单都会命中
    hit = risk_check("U1009", "SO202400901", "order_create")
    check("新规则参与匹配（评分 0→20）", hit["risk_score"], 20)
    check("新规则出现在命中列表", "R_DEMO_TEMP" in [h["rule_code"] for h in hit["rule_hits"]], True)

    status, updated = request("POST", "/api/risk/rules/update",
                              {**new_rule, "id": rule_id, "rule_name": "演示临时规则(已改)", "score": 25})
    check("更新规则返回 200", status, 200)
    after_update = risk_check("U1009", "SO202400901", "order_create")
    check("更新后分值生效（20→25）", after_update["risk_score"], 25)

    status, _ = request("POST", "/api/risk/rules/status", {"id": rule_id, "rule_status": "disabled"})
    after_disable = risk_check("U1009", "SO202400901", "order_create")
    check("停用后新规则不再命中（回到 0）", after_disable["risk_score"], 0)

    status, deleted = request("POST", "/api/risk/rules/delete", {"id": rule_id})
    check("删除规则返回 200", status, 200)
    status, rules = request("GET", "/api/risk/rules")
    check("规则总数恢复 24 条", rules["total"], 24)

    print("\n[黑名单] 新增 → 生效 → 批量导入 → 删除")
    status, added = request("POST", "/api/risk/blacklists",
                            {"blacklist_type": "user", "blacklist_value": "U1009",
                             "remark": "演示：临时拉黑正常用户", "status": "active"})
    check("新增黑名单返回 200", status, 200)
    bl_id = added.get("id")
    blacklisted = risk_check("U1009", "SO202400901", "order_create")
    check("黑名单生效，正常用户变高风险(0→40)", blacklisted["risk_score"], 40)

    status, batch = request("POST", "/api/risk/blacklists/batch",
                            {"text": "ip,10.99.99.99,演示批量导入IP\nuser,U8888,演示批量导入用户"})
    check("批量导入返回 200", status, 200)
    check("批量导入成功 2 条", batch["success_count"], 2)

    status, _ = request("POST", "/api/risk/blacklists/delete", {"id": bl_id})
    restored = risk_check("U1009", "SO202400901", "order_create")
    check("移除黑名单后恢复正常(→0)", restored["risk_score"], 0)

    # 清理批量导入的演示数据
    status, blacklists = request("GET", "/api/risk/blacklists?page_size=50")
    for item in blacklists["list"]:
        if item["blacklist_value"] in ("10.99.99.99", "U8888"):
            request("POST", "/api/risk/blacklists/delete", {"id": item["id"]})


# ------------------------------------------------- D. 用户画像与看板
def run_profile_and_dashboard():
    section("D. 用户画像 / 运营看板")

    print("\n[画像] 查询用户画像")
    status, profile = request("GET", "/api/risk/users/U1006/profile")
    check("画像接口返回 200", status, 200)
    check("画像含历史订单数", profile["summary"]["total_orders"], 8)
    check("画像含退款次数", profile["summary"]["refund_count"], 6)
    check("画像含投诉次数", profile["summary"]["complaint_count"], 1)
    check("画像含地址数量", profile["summary"]["address_count"], 1)
    check("画像含最近风险事件", len(profile["recent_risk_events"]) > 0, True)
    check("画像含关联案件", len(profile["related_cases"]) > 0, True)
    check("画像雷达指标 6 项", len(profile["profile_metrics"]), 6)

    print("\n[看板] 查询统计指标")
    status, dash = request("GET", "/api/risk/dashboard")
    check("看板接口返回 200", status, 200)
    overview = dash["overview"]
    print(f"       风险事件总数={overview['total_events']} 高风险占比={overview['high_risk_ratio']}% "
          f"案件总数={overview['total_cases']} 处理率={overview['handled_ratio']}% "
          f"平均处理时长={overview['avg_handle_hours']}h")
    check("风险事件总数大于 0", overview["total_events"] > 0, True)
    check("高风险占比在合理区间", 0 < overview["high_risk_ratio"] <= 100, True)
    check("案件总数大于 0", overview["total_cases"] > 0, True)
    check("事件类型统计 4 类", len(dash["event_type_stat"]), 4)
    check("风险等级统计 3 档", len(dash["risk_level_stat"]), 3)
    check("案件状态统计 5 种", len(dash["case_status_stat"]), 5)
    check("规则命中排行非空", len(dash["rule_rank"]) > 0, True)
    check("黑名单命中次数被统计", dash["blacklist_stat"]["total_hit"] > 0, True)
    check("趋势数据 7 天", len(dash["trend"]), 7)
    top = dash["rule_rank"][0]
    print(f"       命中排行第一：{top['rule_name']}（{top['hit_count']} 次）")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="star-tradeGuard 完整演示链路验收脚本")
    parser.add_argument("--base-url", default=BASE_URL, help="后端服务地址")
    parser.add_argument("--skip-scenarios", action="store_true", help="跳过 12 个场景矩阵")
    args = parser.parse_args()
    BASE_URL = args.base_url.rstrip("/")

    print("=" * 78)
    print("  电商风险控制系统 star-tradeGuard —— 完整演示链路验收")
    print(f"  服务地址：{BASE_URL}")
    print("=" * 78)

    status, health = request("GET", "/api/health")
    if status != 200:
        print("[致命] 后端健康检查失败，请确认服务已启动。")
        sys.exit(2)

    if not args.skip_scenarios:
        run_scenarios()
    run_demo_chain()
    run_management()
    run_profile_and_dashboard()

    section("验收结果汇总")
    total = len(PASSED) + len(FAILED)
    print(f"  断言总数：{total}    通过：{len(PASSED)}    失败：{len(FAILED)}")
    if FAILED:
        print("\n  失败项：")
        for name in FAILED:
            print(f"    - {name}")
        print("\n  ✗ 验收未通过")
        sys.exit(1)
    print("\n  ✓ 全部断言通过，完整演示链路运行正常")


if __name__ == "__main__":
    main()
