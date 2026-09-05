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


def test_natural_language_no_jargon():
    # 用户只说一句大白话，不出现"离散/连续"等术语
    m = match_industry("我公司生产不锈钢烧水壶")
    assert m and m[0]["code"] in ("C33", "C38"), m  # 金属制品(日用金属) 或 电气(电水壶)
    m2 = match_industry("生产塑料瓶和塑料水桶")
    assert m2 and m2[0]["code"] == "C29", m2
    m3 = match_industry("做陶瓷马桶和卫浴")
    assert m3 and m3[0]["code"] == "C30", m3
    print("PASS test_natural_language_no_jargon")


def test_photo_description():
    # 照片经视觉转成的描述文本 → 识别（照片识别在 DSH 层经 describe_image 转文本后走同一函数）
    m = match_industry("照片：车间里一排注塑机，产品是手机壳")
    assert m and m[0]["code"] == "C29", m
    print("PASS test_photo_description")


def test_full_keyword_coverage():
    # 覆盖全门类（一般制造业）：high/mid 大类至少 3 个关键词；重工业(low)仅限 5 个、不必丰富
    for ind in INDUSTRIES:
        if ind["fit"] != "low":
            assert len(ind["keywords"]) >= 3, f"{ind['code']} 关键词不足"
    low_codes = {i["code"] for i in INDUSTRIES if i["fit"] == "low"}
    assert low_codes == {"C16", "C25", "C26", "C31", "C32"}, low_codes  # 重工业/流程
    print(f"PASS test_full_keyword_coverage ({len(INDUSTRIES)} 大类全覆盖，重工业 {sorted(low_codes)} 除外)")


if __name__ == "__main__":
    test_match_plastic()
    test_match_furniture()
    test_match_printing()
    test_recommend_has_standard()
    test_fit_summary_covers_31()
    test_natural_language_no_jargon()
    test_photo_description()
    test_full_keyword_coverage()
    print("ALL PASS")
