# -*- coding: utf-8 -*-
"""E2：员工简报/车间班前摘要/老板日报——全部 ≤N 行的人话。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import briefing  # noqa: E402

def _sample():
    return {"summary": {"orders": 293, "on_time": 293, "tardy": 0, "on_time_rate": 1.0,
                        "total_tardiness_min": 0, "total_setup_min": 5130,
                        "utilization": {"L3": 0.658, "L1": 0.35}, "bottlenecks": []},
            "engine": "cp"}

def test_brief_worker_short():
    b = briefing.brief_worker(_sample())
    assert len(b.splitlines()) <= 5, b
    assert "准时" in b
    print("PASS test_brief_worker_short")

def test_brief_owner_has_suggestion():
    b = briefing.brief_owner(_sample())
    assert "建议" in b or "风险" in b, b
    print("PASS test_brief_owner_has_suggestion")

def test_degraded_marks_heuristic():
    s = _sample(); s["engine"] = "heuristic"
    b = briefing.brief_worker(s)
    assert "兜底" in b or "heuristic" in b, b
    print("PASS test_degraded_marks_heuristic")

if __name__ == "__main__":
    test_brief_worker_short(); test_brief_owner_has_suggestion(); test_degraded_marks_heuristic()
    print("ALL PASS")
