# -*- coding: utf-8 -*-
"""闭环端到端（合成语料）：排产 → 报工 → 台账 → 急单事件 → 触发 → 重排 → 校准。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import ledger, calibration, trigger  # noqa: E402
from aps_engine.scheduler import run  # noqa: E402
from aps_engine.replan import replan  # noqa: E402
from tools.report_back import record as report_record  # noqa: E402

LINES = [
    {"id": "L1", "name": "一线", "capacity": 1, "work_minutes_per_day": 480,
     "shift_start": "08:00", "first_date": "2026-09-01", "weekends_off": False},
]
PRODUCTS = [
    {"id": "P_A", "name": "A 产品", "capacity_8h": 480, "default_setup_min": 30},
]
ORDERS = [
    {"id": "O1", "product": "P_A", "qty": 10, "due": "2026-09-01 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
    {"id": "O2", "product": "P_A", "qty": 10, "due": "2026-09-02 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
]
RUSH = {"id": "O-R1", "product": "P_A", "qty": 10, "due": "2026-09-01 15:00",
        "priority": 1, "allowed_lines": ["L1"]}


def test_closed_loop():
    plan = run(ORDERS, LINES, PRODUCTS, engine="heuristic")
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        ledger.init_db(db)

        # 1) 报工 → 台账（execution + completion 事件）
        ledger.record_order(db, {"order_code": "O1", "product": "P_A", "qty": 10})
        report_record(db, {"order_code": "O1", "qty_done_units": 10,
                           "actual_end": "2026-09-01 10:00"})
        assert ledger.count_events(db, "completion") == 1

        # 2) 急单事件 → 台账
        ledger.record_order(db, {"order_code": "O-R1", "product": "P_A", "qty": 10,
                                 "due": "2026-09-01 15:00", "priority": 1})
        ledger.emit_event(db, "rush_order", {"order_code": "O-R1", "qty": 10,
                                             "due": "2026-09-01 15:00"})

        # 3) 触发评估
        tasks = [{"order_code": t["order"], "line": blk["line"],
                  "start_min": t["start"], "end_min": t["end"], "frozen": False}
                 for blk in plan["schedule"] for t in blk["tasks"]]
        rep = trigger.evaluate_triggers({"tasks": tasks},
                                        [{"type": "rush_order", "order_code": "O-R1"}], {}, {})
        assert rep["triggered"] and rep["scope"] == "local"

        # 4) 真实重排（冻结区 0 变动 + 急单入列 + 变更清单）
        res = replan(plan, [RUSH], LINES, PRODUCTS, freeze_before="2026-09-01 09:00")
        assert res["frozen_touched"] == 0
        assert any(c["kind"] == "added" and c["order"] == "O-R1" for c in res["change_list"])
        rush_in = [t for blk in res["schedule"] for t in blk["tasks"] if t["order"] == "O-R1"]
        assert len(rush_in) == 1

        # 5) 校准（执行回填：台账 actuals vs 计划）
        executions = ledger.recent_executions(db)
        assert len(executions) == 1
        records, summary = calibration.backfill_execution(plan, executions)
        assert records[0]["action"] == "keep" and records[0]["status"] == "达成", records
    print("PASS test_closed_loop")


if __name__ == "__main__":
    test_closed_loop()
    print("ALL PASS")
