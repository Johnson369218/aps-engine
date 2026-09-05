# -*- coding: utf-8 -*-
"""B4 触发矩阵：周期/缺料/停机/急单/连续偏差/目标变动 6 类；冻结区 0 变动；变更清单。"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import trigger  # noqa: E402

PLAN = {"tasks": [
    {"order_code": "A", "line": "L1", "start_min": 0, "end_min": 480, "frozen": True},
    {"order_code": "B", "line": "L1", "start_min": 480, "end_min": 960, "frozen": False}]}


def test_rush_order_triggers_local():
    rep = trigger.evaluate_triggers(PLAN, [{"type": "rush_order"}], {}, {})
    assert rep["triggered"] is True and rep["scope"] == "local", rep
    print("PASS test_rush_order_triggers_local")


def test_frozen_untouched():
    rep = trigger.evaluate_triggers(PLAN, [{"type": "rush_order"}], {}, {})
    # 变更清单仅含非冻结任务
    assert all(not c["frozen"] for c in rep["change_list"]), rep
    assert rep["frozen_touched"] == 0, rep
    print("PASS test_frozen_untouched")


def test_six_trigger_types():
    for t in ["period", "shortage", "breakdown", "rush_order", "deviation", "target_change"]:
        rep = trigger.evaluate_triggers(PLAN, [{"type": t}], {}, {})
        assert rep["reasons"], (t, rep)
    print("PASS test_six_trigger_types")


if __name__ == "__main__":
    test_rush_order_triggers_local(); test_frozen_untouched(); test_six_trigger_types()
    print("ALL PASS")
