# -*- coding: utf-8 -*-
"""C3 基线回放：AI schedule.json vs 规则基线，产出对比报告。

用法: .venv/bin/python aps-engine/tools/replay_baseline.py \
        --orders real_aug_sep/orders_aug_strict.json --lines real_aug_sep/lines.json \
        --products real/products.json --ai-output output/schedule.json \
        --baseline priority_edd --out "output/baseline_<日期>.md"
"""
import argparse, json, os, sys, datetime
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine.api import solve  # noqa: E402

RULES = {"priority_edd", "edd", "spt", "wspt", "cr"}

def _kpi(result):
    s = result["summary"]
    return {"准时率": s["on_time_rate"], "总延期分": s["total_tardiness_min"],
            "换型分": s["total_setup_min"],
            "瓶颈": "、".join(s["bottlenecks"]) or "无"}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", required=True); ap.add_argument("--lines", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--ai-output", required=True, help="AI 排产 schedule.json")
    ap.add_argument("--baseline", default="priority_edd", choices=sorted(RULES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--time-limit", type=int, default=10)
    args = ap.parse_args(argv)
    o = json.load(open(args.orders, encoding="utf-8"))
    l = json.load(open(args.lines, encoding="utf-8"))
    p = json.load(open(args.products, encoding="utf-8"))
    ai = json.load(open(args.ai_output, encoding="utf-8"))
    base = solve(o, l, p, engine="heuristic", time_limit=args.time_limit)
    rows = [("AI 引擎", _kpi(ai)), (f"基线 {args.baseline}", _kpi(base))]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(f"# 排产基线回放报告（{datetime.date.today()}）\n\n")
        f.write("| 方案 | 准时率 | 总延期分 | 换型分 | 瓶颈 |\n|---|---|---|---|---|\n")
        for name, k in rows:
            f.write(f"| {name} | {k['准时率']:.1%} | {k['总延期分']} | {k['换型分']} | {k['瓶颈']} |\n")
        f.write("\n> 基线为规则回放参考，不改变正式排产；采纳需计划员判断（拍板在人）。\n")
    print(f"基线回放: {args.out}")
    for name, k in rows:
        print(f"  {name}: 准时率 {k['准时率']:.1%} 延期 {k['总延期分']} 换型 {k['换型分']}")

if __name__ == "__main__":
    main()
