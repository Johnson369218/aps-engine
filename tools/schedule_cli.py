# -*- coding: utf-8 -*-
"""一键排产 CLI（DSH 本机）。

用法:
  .venv/bin/python aps-engine/tools/schedule_cli.py \
      --orders real_aug_sep/orders_aug_strict.json --lines real_aug_sep/lines.json \
      --products real/products.json --out output/schedule.json \
      --xlsx "output/排产表.xlsx" [--engine auto|cp|heuristic] [--convert-units] \
      [--kanban-a report_inbox/] [--kanban-b /path/dashboard_data.js] [--by 计划员]
"""
import argparse
import json
import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from aps_engine.api import solve  # noqa: E402
from aps_engine.audit import audit_result  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="参考试点 APS 一键排产（DSH 本机）")
    ap.add_argument("--orders", required=True)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--xlsx", default=None)
    ap.add_argument("--engine", default="auto", choices=["auto", "cp", "heuristic"])
    ap.add_argument("--time-limit", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42, help="求解随机种子（默认 42，保证可复现）")
    ap.add_argument("--convert-units", action="store_true",
                    help="对原始订单做袋→个单位换算（老面馒头400g×4 等）")
    ap.add_argument("--kanban-a", metavar="DIR", default=None,
                    help="A 看板 report_inbox 目录（写 schedule_daily 日报）")
    ap.add_argument("--kanban-b", metavar="PATH", default=None,
                    help="B 看板 dashboard_data.js（注入 production_schedule 块）")
    ap.add_argument("--by", default="生产计划", help="report_inbox 的 by 字段")
    args = ap.parse_args(argv)

    orders = json.load(open(args.orders, encoding="utf-8"))
    lines = json.load(open(args.lines, encoding="utf-8"))
    products = json.load(open(args.products, encoding="utf-8"))

    result = solve(orders, lines, products, engine=args.engine,
                   time_limit=args.time_limit, convert_units=args.convert_units,
                   out_path=args.out, products_raw=products, seed=args.seed)
    if args.xlsx:
        # 标准输出：公式联动排产表（可核查：改数联动/汇总勾稽/fullCalcOnLoad）
        from aps_engine.export_formula import export_formula_xlsx
        export_formula_xlsx(result, products, args.xlsx, title="APS Engine 排产（公式联动·可核查）")
        print(f"排产表(公式联动): {args.xlsx}")

    s = result["summary"]
    print(f"引擎: {result['engine']} | 订单 {s['orders']} | 准时 {s['on_time']} | "
          f"延期 {s['tardy']}（准时率 {s['on_time_rate']:.1%}）")
    print(f"总延期 {s['total_tardiness_min']} 分 | 换型 {s['total_setup_min']} 分 | "
          f"审计 {'✅ 通过' if result.get('audit', {}).get('ok') else '⛔ 未跑'}")
    print("瓶颈(≥80%):", "、".join(s["bottlenecks"]) or "无")
    for blk in result["schedule"]:
        print(f"  {blk['line_name']} 利用率 {s['utilization'].get(blk['line'], 0):.0%} "
              f"({len(blk['tasks'])} 任务)")
    if result.get("notes"):
        print("换算:", "; ".join(result["notes"][:10]))
    if args.out:
        print(f"已写入: {args.out}")
    if args.xlsx:
        print(f"排产表: {args.xlsx}")

    if args.kanban_a:
        from adapters.kanban_out import write_a_inbox
        ps = write_a_inbox(result, args.kanban_a, by=args.by)
        print(f"A 看板: report_inbox 写入 {len(ps)} 条 schedule_daily 日报")
    if args.kanban_b:
        from adapters.kanban_out import write_b_dashboard
        ok, msg = write_b_dashboard(result, args.kanban_b)
        print(("✅ " if ok else "⛔ ") + msg)


if __name__ == "__main__":
    main()
