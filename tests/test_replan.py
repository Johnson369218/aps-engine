# -*- coding: utf-8 -*-
"""闭环重排：冻结区锁定 + 急单插入 + 真实变更清单（合成语料，CI 可跑）。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine.scheduler import run, parse_dt  # noqa: E402
from aps_engine.replan import replan  # noqa: E402

LINES = [
    {"id": "L1", "name": "一线", "capacity": 1, "work_minutes_per_day": 480,
     "shift_start": "08:00", "first_date": "2026-09-01", "weekends_off": False},
    {"id": "L2", "name": "二线", "capacity": 1, "work_minutes_per_day": 480,
     "shift_start": "08:00", "first_date": "2026-09-01", "weekends_off": False},
]
PRODUCTS = [
    {"id": "P_A", "name": "A 产品", "capacity_8h": 480, "default_setup_min": 30},
    {"id": "P_B", "name": "B 产品", "capacity_8h": 480, "default_setup_min": 30},
]
# 原始排产：O1 08:00-10:00、O2 10:00-12:00（D1）、O3 D2、O4 D3（EDD 交期当天）
ORDERS = [
    {"id": "O1", "product": "P_A", "qty": 10, "due": "2026-09-01 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
    {"id": "O2", "product": "P_A", "qty": 10, "due": "2026-09-01 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
    {"id": "O3", "product": "P_B", "qty": 10, "due": "2026-09-02 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
    {"id": "O4", "product": "P_A", "qty": 10, "due": "2026-09-03 17:00", "priority": 2,
     "allowed_lines": ["L1"], "duration_min": 120},
]

# 急单：交期早于 O2，应挤进 10:00-12:00，把 O2 顶到 12:00-14:00
RUSH = {"id": "O-R1", "product": "P_A", "qty": 10, "due": "2026-09-01 12:00",
        "priority": 1, "allowed_lines": ["L1"]}

FREEZE = "2026-09-01 09:00"  # O1(08:00) 冻结，其余滚动


def _all(res):
    return [t for blk in res["schedule"] for t in blk["tasks"]]


def test_frozen_untouched_and_no_overlap():
    plan = run(ORDERS, LINES, PRODUCTS, engine="heuristic")
    res = replan(plan, [RUSH], LINES, PRODUCTS, freeze_before=FREEZE)

    # 1) 冻结区任务逐分钟不变
    frozen_orders = [t["order"] for t in _all(plan) if parse_dt(t["start"]) < parse_dt(FREEZE)]
    assert frozen_orders, "应存在冻结区任务"
    old_map = {(t["order"], parse_dt(t["start"]), parse_dt(t["end"])) for t in _all(plan)}
    for t in _all(res):
        if t["order"] in frozen_orders:
            assert (t["order"], parse_dt(t["start"]), parse_dt(t["end"])) in old_map, t
    assert res["frozen_touched"] == 0

    # 2) 急单已被排入且不延期
    rush_in = [t for t in _all(res) if t["order"] == "O-R1"]
    assert len(rush_in) == 1, "急单应被排入且仅一次"
    assert rush_in[0]["tardy_min"] == 0, "急单优先级1应赶得上交期"

    # 3) 每线无重叠
    for blk in res["schedule"]:
        ts = sorted(blk["tasks"], key=lambda x: x["start"])
        for a, b in zip(ts, ts[1:]):
            assert a["end"] <= b["start"], (blk["line"], a["order"], b["order"], a["end"], b["start"])
    print("PASS test_frozen_untouched_and_no_overlap")


def test_change_list_honest():
    plan = run(ORDERS, LINES, PRODUCTS, engine="heuristic")
    res = replan(plan, [RUSH], LINES, PRODUCTS, freeze_before=FREEZE)
    kinds = {c["kind"] for c in res["change_list"]}
    assert "added" in kinds, res["change_list"]
    assert all(not c["frozen"] for c in res["change_list"])
    added = [c for c in res["change_list"] if c["kind"] == "added"]
    assert any(c["order"] == "O-R1" for c in added), res["change_list"]
    # 急单挤占了 O2 的原槽位 → O2 必须出现在 moved 里（真实 diff，非占位）
    moved = [c for c in res["change_list"] if c["kind"] == "moved"]
    assert any(c["order"] == "O2" for c in moved), res["change_list"]
    print("PASS test_change_list_honest")


if __name__ == "__main__":
    test_frozen_untouched_and_no_overlap()
    test_change_list_honest()
    print("ALL PASS")
