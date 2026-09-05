# -*- coding: utf-8 -*-
"""多工序 Job-Shop（ft06 基准）：前序约束 + 机器无重叠 + makespan 达公开最优 55。"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine.jssp import group_corpus_orders, solve_jssp  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FT06 = os.path.join(HERE, "corpus", "jssp_ft06")


def _load():
    orders = json.load(open(os.path.join(FT06, "orders.json"), encoding="utf-8"))
    lines = json.load(open(os.path.join(FT06, "lines.json"), encoding="utf-8"))
    return orders, lines


def test_ft06_optimal_makespan():
    corpus, lines = _load()
    jobs = group_corpus_orders(corpus)
    assert len(jobs) == 6, f"6 作业, got {len(jobs)}"
    assert all(len(j["operations"]) == 6 for j in jobs), "每作业 6 道工序"
    res = solve_jssp(jobs, lines, time_limit=30)
    assert res["precedence_violations"] == 0, res["precedence_violations"]
    assert res["makespan"] == 55, f"makespan {res['makespan']} != 公开最优 55"
    # 每台机器无重叠
    for blk in res["schedule"]:
        ts = sorted(blk["tasks"], key=lambda x: x["start"])
        for a, b in zip(ts, ts[1:]):
            assert a["end"] <= b["start"], (blk["machine"], a["op_id"], b["op_id"])
    print(f"PASS test_ft06_optimal_makespan (makespan={res['makespan']}, 前序违规 0, 无重叠)")


def test_heuristic_feasible():
    corpus, lines = _load()
    jobs = group_corpus_orders(corpus)
    import aps_engine.jssp as J
    # 强制走启发式（模拟无 ortools 环境）
    saved = J.HAVE_ORTools
    J.HAVE_ORTools = False
    try:
        res = solve_jssp(jobs, lines, time_limit=5)
    finally:
        J.HAVE_ORTools = saved
    assert res["precedence_violations"] == 0
    assert res["makespan"] >= 55, "启发式 makespan 应 ≥ 最优 55"
    print(f"PASS test_heuristic_feasible (启发式 makespan={res['makespan']} ≥ 55, 前序违规 0)")


if __name__ == "__main__":
    test_ft06_optimal_makespan()
    test_heuristic_feasible()
    print("ALL PASS")
