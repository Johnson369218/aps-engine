# -*- coding: utf-8 -*-
"""B1 可复现：同输入同 seed 两次运行，任务序列一致（解多解漂移）。"""
import json, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(_PLUGIN_DIR)
for _p in (_PLUGIN_DIR, _WORKSPACE):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine.api import solve  # noqa: E402

FIX = {
    "orders": os.path.join(_WORKSPACE, "real_aug_sep/orders_aug_strict.json"),
    "lines": os.path.join(_WORKSPACE, "real_aug_sep/lines.json"),
    "products": os.path.join(_WORKSPACE, "real/products.json"),
}

def _seq(paths):
    """任务序列：产线 + 订单 + 开始 + 结束（schedule 顶层块含 line，任务含 order/start/end）。"""
    return [(blk.get("line"), t.get("order"), t.get("start"), t.get("end"))
            for blk in paths for t in blk.get("tasks", [])]

def test_same_seed_reproducible():
    o = json.load(open(FIX["orders"], encoding="utf-8"))
    l = json.load(open(FIX["lines"], encoding="utf-8"))
    p = json.load(open(FIX["products"], encoding="utf-8"))
    r1 = solve(o, l, p, engine="cp", time_limit=8, seed=42)
    r2 = solve(o, l, p, engine="cp", time_limit=8, seed=42)
    s1, s2 = _seq(r1["schedule"]), _seq(r2["schedule"])
    assert s1 == s2, f"同 seed 两次结果不一致: {len(s1)} vs {len(s2)} 任务"
    print(f"PASS 同 seed 可复现: {len(s1)} 任务一致")

def test_diff_seed_allowed():
    o = json.load(open(FIX["orders"], encoding="utf-8"))
    l = json.load(open(FIX["lines"], encoding="utf-8"))
    p = json.load(open(FIX["products"], encoding="utf-8"))
    r1 = solve(o, l, p, engine="cp", time_limit=6, seed=1)
    r2 = solve(o, l, p, engine="cp", time_limit=6, seed=2)
    _ = r1; _ = r2  # 仅验证不同 seed 不抛异常
    print("PASS 不同 seed 可运行")

if __name__ == "__main__":
    test_same_seed_reproducible()
    test_diff_seed_allowed()
    print("ALL PASS")
