# -*- coding: utf-8 -*-
"""B3 校准状态机：|delta|<5% → 已校准；≥10% → 已修正+建议值；5-10% 保持待实测。"""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import calibration  # noqa: E402

ASSUM = {"assumptions": {
    "H2": {"item": "SKU 产能", "value": 10000, "source": "products", "status": "待实测"}}}

def test_calibrated_under_5pct():
    records, _ = calibration.backfill({}, {"H2": 10200}, ASSUM)
    r = records[0]
    assert r["status"] == "已校准" or r["action"] == "keep", r
    print("PASS test_calibrated_under_5pct")

def test_corrected_over_10pct():
    records, _ = calibration.backfill({}, {"H2": 8200}, ASSUM)
    r = records[0]
    assert r["action"] == "correct", r
    assert r["suggestion"] == 8200, r
    print("PASS test_corrected_over_10pct")

def test_report_requires_approval():
    # 校准报告为建议，不自动改写参数（红线：审批生效）
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "校准报告.md")
        calibration.write_report({"H2": 8200}, ASSUM, p)
        assert os.path.exists(p)
        txt = open(p, encoding="utf-8").read()
        assert "建议" in txt and "审批" in txt, txt
    print("PASS test_report_requires_approval")

if __name__ == "__main__":
    test_calibrated_under_5pct(); test_corrected_over_10pct(); test_report_requires_approval()
    print("ALL PASS")
