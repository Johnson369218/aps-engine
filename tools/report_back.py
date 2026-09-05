# -*- coding: utf-8 -*-
"""D3 报工最懒化入口：一句话/JSON → execution 落库 + 完成事件。

用法: .venv/bin/python aps-engine/tools/report_back.py --db data/ledger/aps_ledger.db \
        --order O-001 --qty 1000 --unit 袋 --factor 4 --by 班组长
       （unit/factor 换算规则来自 config/industry_food.json unit_conversions）
"""
import argparse, json, os, re, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine import ledger  # noqa: E402


def parse_report(text, conversions):
    """极简解析：提取订单号/数量/单位；单位→个 换算。"""
    m = re.search(r"([A-Za-z0-9_-]{3,})", text)
    order_code = m.group(1) if m else None
    qty = None
    qm = re.search(r"(\d+)\s*([袋盒箱件包])", text)
    if qm:
        qty = int(qm.group(1))
        unit = qm.group(2)
        factor = conversions.get(unit, 1)
        qty_units = qty * factor
    else:
        qty_units = None
    return {"order_code": order_code, "qty_done_units": qty_units}


def record(db, r, by="班组长"):
    ledger.record_execution(db, {"order_code": r["order_code"], "plan_date": None,
                                 "actual_end": r.get("actual_end"),
                                 "qty_done": r.get("qty_done_units"),
                                 "reported_by": by})
    ledger.emit_event(db, "completion",
                      {"order_code": r["order_code"], "qty_done": r.get("qty_done_units")})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--order", required=True)
    ap.add_argument("--qty", type=int, required=True)
    ap.add_argument("--unit", default="个")
    ap.add_argument("--factor", type=int, default=1, help="袋→个换算系数（如馒头 4）")
    ap.add_argument("--by", default="班组长")
    args = ap.parse_args(argv)
    record(args.db, {"order_code": args.order, "qty_done_units": args.qty * args.factor,
                     "actual_end": None}, by=args.by)
    print(f"报工回填: {args.order} {args.qty}{args.unit}（×{args.factor} = {args.qty * args.factor} 个）")


if __name__ == "__main__":
    main()
