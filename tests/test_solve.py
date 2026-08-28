# -*- coding: utf-8 -*-
"""回归测试：real_aug_sep 严格版(293单) 对齐 output/schedule_aug_strict.json。

运行: .venv/bin/python aps-engine/tests/test_solve.py
"""
import json
import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(_PLUGIN_DIR)
for _p in (_PLUGIN_DIR, _WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from aps_engine.api import solve  # noqa: E402
from aps_engine.audit import audit_result  # noqa: E402
from aps_engine.schema import validate_inputs  # noqa: E402

FIX = {
    "orders": os.path.join(_WORKSPACE, "real_aug_sep/orders_aug_strict.json"),
    "lines": os.path.join(_WORKSPACE, "real_aug_sep/lines.json"),
    "products": os.path.join(_WORKSPACE, "real/products.json"),
    "baseline": os.path.join(_WORKSPACE, "output/schedule_aug_strict_v2.json"),
}


def main():
    orders = json.load(open(FIX["orders"], encoding="utf-8"))
    lines = json.load(open(FIX["lines"], encoding="utf-8"))
    products = json.load(open(FIX["products"], encoding="utf-8"))
    base = json.load(open(FIX["baseline"], encoding="utf-8"))

    errs = validate_inputs(orders, lines, products)
    assert not errs, "输入校验失败: " + "\n".join(errs[:10])

    result = solve(orders, lines, products, engine="cp", time_limit=30)
    s, bs = result["summary"], base["summary"]

    # ── 硬不变量（必须严格成立）──────────────────────────────
    assert s["orders"] == bs["orders"] == 293, f"订单数 {s['orders']} != 293"
    assert s["on_time"] == bs["on_time"] == 293, "应 100% 准时"
    assert s["tardy"] == 0, f"延期 {s['tardy']}"
    # 每线任务数必须与基线一致（覆盖不变）
    base_cnt = {blk["line"]: len(blk["tasks"]) for blk in base["schedule"]}
    mine_cnt = {blk["line"]: len(blk["tasks"]) for blk in result["schedule"]}
    assert base_cnt == mine_cnt, f"每线任务数不一致: 基线 {base_cnt} vs 新 {mine_cnt}"

    # ── 容忍区间（CP-SAT 在等价最优解间不确定：准时率/覆盖不变，
    #    序列与换型分配会漂移；仅校验量级）──────────────────────
    for ln in bs["utilization"]:
        diff = abs(s["utilization"][ln] - bs["utilization"][ln])
        assert diff < 0.02, f"利用率 {ln} 偏差 {diff:.3f}（新 {s['utilization'][ln]:.3f} vs 基线 {bs['utilization'][ln]:.3f}）"
    assert abs(s["total_setup_min"] - bs["total_setup_min"]) <= 120, \
        f"换型总耗时偏差过大: {s['total_setup_min']} vs {bs['total_setup_min']}（CP-SAT 多解漂移容忍 120 分）"

    n, issues = audit_result(result)
    assert not issues, f"audit {len(issues)} 项问题: " + "\n".join(issues[:5])

    # 21 列口径字段存在性
    for line in result["schedule"]:
        for t in line["tasks"]:
            for k in ("prod_date", "early_days", "tardy_min", "front_start",
                      "front_end", "start", "end", "due", "product_name"):
                assert k in t, f"任务缺少字段 {k}: {t.get('order')}"

    print("✅ 回归通过（硬不变量 + 容忍区间）")
    print(f"   订单 {s['orders']} | 准时率 {s['on_time_rate']:.1%} | 换型 {s['total_setup_min']} 分")
    print(f"   每线任务数: " + " ".join(f"{k}={mine_cnt[k]}" for k in sorted(mine_cnt)))
    print(f"   利用率: " + " ".join(f"{k}={s['utilization'][k]*100:.1f}%" for k in sorted(s['utilization'])))
    print(f"   audit: {n} 任务 0 问题")


if __name__ == "__main__":
    main()
