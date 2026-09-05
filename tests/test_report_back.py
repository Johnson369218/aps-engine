# -*- coding: utf-8 -*-
"""D3 报工回填：懒化输入→execution 落库；qty 单位换算校验。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import ledger  # noqa: E402
from tools.report_back import parse_report  # noqa: E402

def test_parse_sentence():
    # "3号线完成了 O-001 1000袋" → 结构
    r = parse_report("O-001 完成 1000 袋", {"袋": 4})
    assert r["order_code"] == "O-001" and r["qty_done_units"] == 4000, r
    print("PASS test_parse_sentence")

def test_backfill_records_execution():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db"); ledger.init_db(db)
        ledger.record_order(db, {"order_code": "O-001", "product": "m", "qty": 4000})
        from tools.report_back import record
        record(db, {"order_code": "O-001", "qty_done_units": 4000,
                    "actual_end": "2026-09-05 10:30"})
        assert ledger.count_events(db) == 1  # 完成即事件（可触发校准）
    print("PASS test_backfill_records_execution")

if __name__ == "__main__":
    test_parse_sentence()
    test_backfill_records_execution()
    print("ALL PASS")
