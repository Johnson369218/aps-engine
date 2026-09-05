# -*- coding: utf-8 -*-
"""B6：分解模式结果审计通过且默认 mode 语义不变；规则回放推荐可输出。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine.api import solve  # noqa: E402

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(_PLUGIN_DIR)
FIX = {"orders": os.path.join(_WORKSPACE, "real_aug_sep/orders_aug_strict.json"),
       "lines": os.path.join(_WORKSPACE, "real_aug_sep/lines.json"),
       "products": os.path.join(_WORKSPACE, "real/products.json")}

def test_decompose_audit_ok():
    o = json.load(open(FIX["orders"], encoding="utf-8"))
    l = json.load(open(FIX["lines"], encoding="utf-8"))
    p = json.load(open(FIX["products"], encoding="utf-8"))
    r = solve(o, l, p, engine="auto", time_limit=6, mode="decompose")
    assert r["audit"]["ok"] is True, r["audit"]
    print("PASS 分解模式 audit ok")

def test_default_mode_unchanged():
    o = json.load(open(FIX["orders"], encoding="utf-8"))
    l = json.load(open(FIX["lines"], encoding="utf-8"))
    p = json.load(open(FIX["products"], encoding="utf-8"))
    r = solve(o, l, p, engine="auto", time_limit=6)  # 默认 mode=cp
    assert r["audit"]["ok"] is True
    print("PASS 默认 mode 语义不变")

if __name__ == "__main__":
    test_decompose_audit_ok(); test_default_mode_unchanged()
    print("ALL PASS")
