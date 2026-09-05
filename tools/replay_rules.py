# -*- coding: utf-8 -*-
"""B6 规则回放择优：同输入下多规则对比，输出推荐规则候选（pending_replay，须 skill_gate 审批）。

用法: .venv/bin/python aps-engine/tools/replay_rules.py --orders orders.json \
        --lines L.json --products P.json --out "output/rules_<日期>.json"

说明（诚实标注）：v1 各规则共用同一启发式（EDD 优先 + 负载均衡 + 换型 2-opt），
规则差异（EDD/SPT/WSPT/CR 作为独立排序键）属「扩展位」——需改调度器排序入口（白名单外），
本阶段仅落地「对比结构 + 推荐 + pending_replay 审批门」流程，不自动生效。
"""
import argparse, json, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine.api import solve  # noqa: E402

RULES = ["edd", "spt", "wspt", "cr"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--orders", required=True); ap.add_argument("--lines", required=True)
    ap.add_argument("--products", required=True); ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    o = json.load(open(args.orders, encoding="utf-8"))
    l = json.load(open(args.lines, encoding="utf-8"))
    p = json.load(open(args.products, encoding="utf-8"))
    rows = []
    for rule in RULES:
        r = solve(o, l, p, engine="heuristic", time_limit=3)  # heuristic 内按 rule 排序（扩展位）
        s = r["summary"]
        rows.append({"rule": rule, "on_time_rate": s["on_time_rate"],
                     "total_tardiness_min": s["total_tardiness_min"],
                     "total_setup_min": s["total_setup_min"]})
    best = max(rows, key=lambda x: (x["on_time_rate"], -x["total_tardiness_min"]))
    doc = {"kind": "rule_replay", "rows": rows, "recommend": best["rule"],
           "activation": "pending_replay",
           "note": "推荐规则须回放+审批后启用（红线），不自动生效"}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("规则回放完成，推荐:", best["rule"], "→", args.out)
    for r in rows:
        print(f"  {r['rule']}: 准时率 {r['on_time_rate']:.1%} 延期 {r['total_tardiness_min']}")


if __name__ == "__main__":
    main()
