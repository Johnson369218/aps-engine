# -*- coding: utf-8 -*-
"""排产结果 6 项一致性审计（固化自 audit_schedule.py，改为对 dict 操作）。"""
from datetime import datetime


def audit_result(result):
    """返回 (任务数, 问题列表)。问题列表为空=通过。"""
    issues, n = [], 0
    for line in result.get("schedule", []):
        for t in line.get("tasks", []):
            n += 1
            end, start = t["end"], t["start"]
            if t.get("prod_date") != end[:10]:
                issues.append(f"{t['order']} prod_date={t.get('prod_date')} != end日期={end[:10]}")
            due = t["due"][:10]
            exp_early = max(0, (datetime.strptime(due, "%Y-%m-%d")
                                - datetime.strptime(t["prod_date"], "%Y-%m-%d")).days)
            if t.get("early_days") != exp_early:
                issues.append(f"{t['order']} early_days={t.get('early_days')} != {exp_early}")
            ot = t.get("order_time")
            if ot and str(ot).strip() and t.get("order_lead_h") is not None:
                exp_h = round((datetime.strptime(end, "%Y-%m-%d %H:%M")
                               - datetime.strptime(str(ot)[:16], "%Y-%m-%d %H:%M")).total_seconds() / 3600, 1)
                if abs(t["order_lead_h"] - exp_h) > 0.2:
                    issues.append(f"{t['order']} order_lead_h={t['order_lead_h']} != {exp_h}")
            exp_tardy = max(0, int((datetime.strptime(end, "%Y-%m-%d %H:%M")
                                    - datetime.strptime(t["due"], "%Y-%m-%d %H:%M")).total_seconds() / 60))
            if t.get("tardy_min") != exp_tardy:
                issues.append(f"{t['order']} tardy_min={t.get('tardy_min')} != {exp_tardy}")
            if t.get("front_end") and t.get("front_start") and t["front_end"] > t["start"]:
                issues.append(f"{t['order']} 前工序{t['front_end']} > 后工序{t['start']}")
            if end < start:
                issues.append(f"{t['order']} end<start")
    return n, issues
