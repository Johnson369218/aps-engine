# -*- coding: utf-8 -*-
"""D2 事件与台账 CLI。

用法:
  .venv/bin/python aps-engine/tools/ledger_cli.py init [--db data/ledger/aps_ledger.db]
  ... event --type rush_order --payload '{"order_code":"O-R1","qty":500,"due":"2026-09-06 18:00"}'
  ... orders --file orders.json        # 批量落库（orders 数组或 {"data":[...]})
  ... events [--type shortage]
"""
import argparse, json, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine import ledger  # noqa: E402

DEFAULT_DB = os.path.join(os.path.dirname(_PLUGIN_DIR), "data", "ledger", "aps_ledger.db")


def main(argv=None):
    # --db 在主解析器与各子命令均可（plan 用法「init [--db ...]」与「--db ... event」并存）；
    # 子命令用 SUPPRESS 默认，避免覆盖主解析器已解析的 --db。
    _parent = argparse.ArgumentParser(add_help=False)
    _parent.add_argument("--db", default=argparse.SUPPRESS)

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", parents=[_parent])
    p_ev = sub.add_parser("event", parents=[_parent]); p_ev.add_argument("--type", required=True)
    p_ev.add_argument("--payload", required=True)
    p_ord = sub.add_parser("orders", parents=[_parent]); p_ord.add_argument("--file", required=True)
    p_ls = sub.add_parser("events", parents=[_parent]); p_ls.add_argument("--type", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "init":
        ledger.init_db(args.db); print(f"台账初始化: {args.db}")
    elif args.cmd == "event":
        ledger.emit_event(args.db, args.type, json.loads(args.payload))
        print(f"事件入库: {args.type}")
    elif args.cmd == "orders":
        data = json.load(open(args.file, encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("data", [])
        for r in rows:
            r.setdefault("order_code", r.get("id"))
            ledger.record_order(args.db, r)
        print(f"订单落库: {len(rows)} 条")
    elif args.cmd == "events":
        for e in ledger.recent_events(args.db):
            print(e["id"], e["event_type"], e["payload_json"])


if __name__ == "__main__":
    main()
