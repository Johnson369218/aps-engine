# -*- coding: utf-8 -*-
"""闭环重排 CLI：急单/事件 → 台账+事件 → 触发评估 → 真实重排 → 变更清单（what-if 建议）。

用法:
  .venv/bin/python aps-engine/tools/replan_cli.py \
      --plan output/schedule.json --lines real_aug_sep/lines.json --products real/products.json \
      --rush '{"id":"RUSH-001","product":"SKU001","qty":200,"due":"2026-08-02 12:00",\
"priority":1,"allowed_lines":["L1"]}' \
      --freeze-before "2026-08-01 18:00" [--db data/ledger/aps_ledger.db] \
      --out output/_phase3/replan_result.json

红线：输出为建议（拍板在人），不自动覆盖正式排产文件；--db 仅落台账事实，不改排产参数。
"""
import argparse, json, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)

from aps_engine import ledger, trigger, replan  # noqa: E402
from aps_engine.scheduler import parse_dt  # noqa: E402


def _to_tasks(plan, freeze_before=None):
    freeze_dt = parse_dt(freeze_before) if freeze_before else None
    tasks = []
    for blk in plan.get("schedule", []):
        for t in blk.get("tasks", []):
            tasks.append({"order_code": t.get("order"), "line": blk.get("line"),
                          "start_min": t.get("start"), "end_min": t.get("end"),
                          "frozen": bool(freeze_dt and parse_dt(t.get("start")) < freeze_dt)})
    return tasks


def main(argv=None):
    ap = argparse.ArgumentParser(description="闭环重排（急单 what-if）：触发评估 + 真实重排 + 变更清单")
    ap.add_argument("--plan", required=True, help="现有排产 schedule.json")
    ap.add_argument("--lines", required=True)
    ap.add_argument("--products", required=True)
    ap.add_argument("--rush", action="append", default=[], help="急单 JSON（可多次）")
    ap.add_argument("--freeze-before", default=None, help="冻结边界（早于此的任务不变）")
    ap.add_argument("--db", default=None, help="台账库（可选，落订单+事件）")
    ap.add_argument("--out", default=None, help="重排结果 JSON 输出路径")
    args = ap.parse_args(argv)

    plan = json.load(open(args.plan, encoding="utf-8"))
    lines = json.load(open(args.lines, encoding="utf-8"))
    products = json.load(open(args.products, encoding="utf-8"))
    rush_orders = []
    for r in args.rush:
        obj = json.loads(r)
        rush_orders.extend(obj if isinstance(obj, list) else [obj])

    if args.db:
        ledger.init_db(args.db)
        for o in rush_orders:
            ledger.record_order(args.db, {"order_code": o["id"], "product": o["product"],
                                          "qty": int(o.get("qty", 0)), "due": o.get("due"),
                                          "priority": o.get("priority", 2),
                                          "source_system": "rush"})
            ledger.emit_event(args.db, "rush_order",
                              {"order_code": o["id"], "qty": o.get("qty"),
                               "due": o.get("due"), "line": (o.get("allowed_lines") or [None])[0],
                               "ts": args.freeze_before or ""})

    events = [{"type": "rush_order", "order_code": o["id"],
               "line": (o.get("allowed_lines") or [None])[0]} for o in rush_orders]
    rep = trigger.evaluate_triggers({"tasks": _to_tasks(plan, args.freeze_before)}, events, {}, {})

    res = replan.replan(plan, rush_orders, lines, products, freeze_before=args.freeze_before)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(res, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    s = res["summary"]
    added = sum(1 for c in res["change_list"] if c["kind"] == "added")
    moved = sum(1 for c in res["change_list"] if c["kind"] == "moved")
    print("=== 闭环重排（建议，待审批）===")
    print(f"触发: triggered={rep['triggered']} scope={rep['scope']} 原因={[r['type'] for r in rep['reasons']]}")
    print(f"冻结边界: {res['freeze_before']} | 受影响线: {'、'.join(res['affected_lines']) or '无'} | frozen_touched={res['frozen_touched']}")
    print(f"订单 {s['orders']} | 准时 {s['on_time']} | 延期 {s['tardy']}（准时率 {s['on_time_rate']:.1%}）")
    print(f"变更清单: {len(res['change_list'])} 条（新增 {added} / 移动 {moved}）")
    for c in res["change_list"][:8]:
        b = c.get("before") or {}
        a = c.get("after") or {}
        print(f"  {c['kind']:<6} {c['order']}  {b.get('start','')} → {a.get('start','')}")
    if len(res["change_list"]) > 8:
        print(f"  … 其余 {len(res['change_list']) - 8} 条")
    if args.out:
        print(f"已写入: {args.out}")


if __name__ == "__main__":
    main()
