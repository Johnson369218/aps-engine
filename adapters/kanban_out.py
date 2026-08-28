# -*- coding: utf-8 -*-
"""看板上板适配器。

A 看板（管道/契约）：report_inbox/schedule_daily_<日期>.json
  → 需先在 看板字段口径.json 注册 schedule_daily 模块（本文件 --register-caliber 一次性完成，幂等）
  → 再由参考试点管理看板 pipeline/merge_reports.py 合并入看板
B 看板（快照）：dashboard_data.js 注入 production_schedule 块（与 sync_schedule_to_dashboard.py 同构）
"""
import argparse
import json
import os
import re
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from aps_engine.summarize import a_report_inbox, b_kanban_block  # noqa: E402

# A 看板模块定义（对齐 看板字段口径.json 的 module 对象结构）
SCHEDULE_DAILY_MODULE = {
    "module": "schedule_daily",
    "title": "排产日计划（APS 插件产出）",
    "freq": "日",
    "tip": "每日排产结果摘要：计划产量/订单数/准时率/瓶颈/班前执行单。由 aps-engine adapters/kanban_out.py 写入 report_inbox。",
    "fields": [
        {"key": "plan_date", "label": "计划日期", "unit": "文本", "tip": "入库日期（后工序完成日，真实生产日期，YYYY-MM-DD）"},
        {"key": "plan_qty", "label": "当日计划产量", "unit": "数量", "tip": "当日全部产线计划数量合计（按各自单位）"},
        {"key": "plan_orders", "label": "当日排产订单数", "unit": "单", "tip": "当日计划排产订单条数"},
        {"key": "on_time_rate", "label": "排产准时率", "unit": "%", "tip": "计划内准时完成占比，目标≥95%"},
        {"key": "bottleneck", "label": "瓶颈产线", "unit": "文本", "tip": "负荷≥80% 的产线及负荷率"},
        {"key": "handover", "label": "班前执行单摘要", "unit": "文本", "tip": "每行：产线|产品×数量|开始→结束|风险状态"},
    ],
}


def register_schedule_daily(caliber_path):
    """把 schedule_daily 模块写入 看板字段口径.json（幂等）。"""
    with open(caliber_path, encoding="utf-8") as f:
        cal = json.load(f)
    if any(m.get("module") == "schedule_daily" for m in cal):
        return False, "schedule_daily 已注册，跳过"
    cal.append(SCHEDULE_DAILY_MODULE)
    with open(caliber_path, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)
    return True, f"已注册 schedule_daily（{caliber_path}）"


def write_a_inbox(result, inbox_dir, by="生产计划", when=None):
    """写 A 看板 report_inbox/schedule_daily_<日期>.json（每个入库日一条）。"""
    os.makedirs(inbox_dir, exist_ok=True)
    reports = a_report_inbox(result, by=by, when=when)
    paths = []
    for r in reports:
        date = r["data"]["plan_date"]
        p = os.path.join(inbox_dir, f"schedule_daily_{date}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        paths.append(p)
    return paths


def write_b_dashboard(result, dashboard_js, source=None):
    """B 看板：dashboard_data.js 注入 production_schedule 块（幂等，覆盖语义）。"""
    block = b_kanban_block(result, source=source)
    with open(dashboard_js, encoding="utf-8") as f:
        src = f.read()
    if '"production_schedule":' in src:
        src = re.sub(r'"production_schedule": {.*?},\n(?="weekly_tasks")',
                     '"production_schedule": ' + json.dumps(block, ensure_ascii=False) + ',\n',
                     src, count=1, flags=re.S)
        changed = "已更新 production_schedule 块"
    else:
        anchor = '"weekly_tasks":'
        if anchor not in src:
            return False, "dashboard_data.js 缺少 weekly_tasks 锚点，无法注入"
        src = src.replace(anchor,
                          '"production_schedule": ' + json.dumps(block, ensure_ascii=False)
                          + ',\n' + anchor, 1)
        changed = "已注入 production_schedule 块"
    with open(dashboard_js, "w", encoding="utf-8") as f:
        f.write(src)
    return True, changed


def main(argv=None):
    ap = argparse.ArgumentParser(description="看板上板适配器")
    ap.add_argument("--register-caliber", metavar="PATH",
                    help="把 schedule_daily 模块注册进 看板字段口径.json（一次性）")
    ap.add_argument("--result", metavar="PATH", help="排产结果 schedule.json")
    ap.add_argument("--inbox-dir", metavar="DIR", help="A 看板 report_inbox 目录")
    ap.add_argument("--dashboard-js", metavar="PATH", help="B 看板 dashboard_data.js")
    ap.add_argument("--by", default="生产计划")
    args = ap.parse_args(argv)

    if args.register_caliber:
        ok, msg = register_schedule_daily(args.register_caliber)
        print(("✅ " if ok else "⏭ ") + msg)
    if args.result:
        result = json.load(open(args.result, encoding="utf-8"))
        if args.inbox_dir:
            ps = write_a_inbox(result, args.inbox_dir, by=args.by)
            print(f"A 看板：写入 {len(ps)} 条 schedule_daily 日报 → report_inbox/")
        if args.dashboard_js:
            ok, msg = write_b_dashboard(result, args.dashboard_js)
            print(("✅ " if ok else "⛔ ") + msg)


if __name__ == "__main__":
    main()
