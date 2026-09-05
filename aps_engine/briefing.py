# -*- coding: utf-8 -*-
"""E2 输出三件套：brief_worker（员工，≤5 行）/ brief_shopfloor（车间班前摘要）/
brief_owner（老板日报：准时/延期/瓶颈/建议）。E4 降级标注：heuristic → '规则兜底'。"""
import datetime


def _util_top(result, n=2):
    u = result.get("summary", {}).get("utilization", {})
    return sorted(u.items(), key=lambda kv: kv[1], reverse=True)[:n]


def brief_worker(result):
    s = result["summary"]
    tag = "" if result.get("engine") == "cp" else "（规则兜底，非 AI 优化）"
    lines = [f"今日排产{tag}：{s['orders']} 单，准时 {s['on_time']}（{s['on_time_rate']:.0%}），"
             f"延期 {s['tardy']} 单"]
    tops = _util_top(result)
    if tops:
        busy = "、".join(f"{k} {v:.0%}" for k, v in tops if v >= 0.5)
        lines.append(f"最忙：{busy or '无超50%线'}")
    if s["bottlenecks"]:
        lines.append(f"⚠ 瓶颈：{'、'.join(s['bottlenecks'])}")
    else:
        lines.append("无 ≥80% 瓶颈线")
    return "\n".join(lines)


def brief_shopfloor(result):
    """班前单摘要：每线 单数×数量 起止一行；供打印/大屏。"""
    rows = []
    for blk in result.get("schedule", []):
        tasks = blk.get("tasks", [])
        if not tasks:
            continue
        first, last = tasks[0], tasks[-1]
        qty = sum(int(t.get("qty", 0) or 0) for t in tasks)
        rows.append(f"{blk['line']} | {len(tasks)} 单 × {qty} | "
                    f"{first.get('start', '')} → {last.get('end', '')}")
    return "\n".join(rows) or "（无排产任务）"


def brief_owner(result, extra=None):
    s = result["summary"]
    lines = [f"排产简报 {datetime.date.today()}：{s['orders']} 单，准时率 {s['on_time_rate']:.1%}，"
             f"总延期 {s['total_tardiness_min']} 分，换型 {s['total_setup_min']} 分"]
    if s["bottlenecks"]:
        lines.append(f"风险：瓶颈 {'、'.join(s['bottlenecks'])}，建议加班/外协/调优先级")
    else:
        lines.append("风险：无 ≥80% 瓶颈线")
    if extra:
        lines.append("待办：" + "；".join(extra[:3]))
    return "\n".join(lines)
