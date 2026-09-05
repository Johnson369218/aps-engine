# -*- coding: utf-8 -*-
"""行业适配矩阵：关键词识别 + 标准功能推荐 + 31 大类汇总。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine.industry import match_industry, recommend, fit_summary, INDUSTRIES  # noqa: E402


def test_match_plastic():
    m = match_industry("我们做注塑，生产手机壳和药瓶，几台海天注塑机")
    assert m and m[0]["code"] == "C29", m
    print("PASS test_match_plastic")


def test_match_furniture():
    m = match_industry("板式家具，做办公桌，开料封边打孔组装")
    assert m and m[0]["code"] == "C21", m
    assert m[0]["engine"] == "solve_jssp"
    print("PASS test_match_furniture")


def test_match_printing():
    m = match_industry("柔印无纺布袋，凹印卷膜，印刷厂")
    assert m and m[0]["code"] == "C23", m
    r = recommend(m[0])
    assert r["模板"] == "examples/printing_sme"
    print("PASS test_match_printing")


def test_recommend_has_standard():
    r = recommend(next(i for i in INDUSTRIES if i["code"] == "C29"))
    assert r["引擎"] and r["设备通道"] and r["换型/约束重点"] and r["标准工艺参数"]
    assert "pressure" in r["标准工艺参数"]  # 注塑标准工艺参数含注射压力
    print("PASS test_recommend_has_standard")


def test_fit_summary_covers_31():
    s = fit_summary()
    assert s["total"] == 31 and s["high"] + s["mid"] + s["low"] == 31
    assert s["high"] >= 20  # 强适配应占多数
    print(f"PASS test_fit_summary_covers_31 (强{s['high']}/中{s['mid']}/弱{s['low']})")


if __name__ == "__main__":
    test_match_plastic()
    test_match_furniture()
    test_match_printing()
    test_recommend_has_standard()
    test_fit_summary_covers_31()
    print("ALL PASS")
