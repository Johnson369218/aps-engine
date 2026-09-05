# -*- coding: utf-8 -*-
"""D1 台账：init/migrate 幂等、订单落库、执行回填、事件落库。"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import ledger  # noqa: E402

def test_init_and_migrate_idempotent():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        ledger.init_db(db); ledger.init_db(db)  # 二次不报错
        ledger.migrate(db)
        assert os.path.exists(db)
    print("PASS test_init_and_migrate_idempotent")

def test_record_and_get_order():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        ledger.init_db(db)
        order = {"order_code": "O-T1", "product": "toast_plain", "qty": 1000,
                 "due": "2026-09-10 18:00", "priority": 2, "source_system": "chat"}
        ledger.record_order(db, order)
        row = ledger.get_order(db, "O-T1")
        assert row["order_code"] == "O-T1" and row["qty"] == 1000
    print("PASS test_record_and_get_order")

def test_execution_and_events():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        ledger.init_db(db)
        ledger.record_execution(db, {"order_code": "O-T1", "plan_date": "2026-09-05",
                                     "actual_start": "2026-09-05 08:00",
                                     "actual_end": "2026-09-05 10:30", "qty_done": 1000})
        ledger.emit_event(db, "rush_order", {"order_code": "O-R1", "qty": 500,
                                             "due": "2026-09-06 18:00"})
        n = ledger.count_events(db, "rush_order")
        assert n == 1, n
    print("PASS test_execution_and_events")

if __name__ == "__main__":
    test_init_and_migrate_idempotent()
    test_record_and_get_order()
    test_execution_and_events()
    print("ALL PASS")
