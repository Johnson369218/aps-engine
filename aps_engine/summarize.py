# -*- coding: utf-8 -*-
"""看板摘要生成：B 看板 production_schedule 块 + A 看板 schedule_daily report_inbox。"""
from collections import Counter, defaultdict
from datetime import datetime


def b_kanban_block(result, source=None):
    """与 sync_schedule_to_dashboard.build_block 同构（B 看板 dashboard_data.js）。"""
    s = result["summary"]
    line_top = {}
    for line in result["schedule"]:
        cnt = Counter(t["product_name"] for t in line["tasks"])
        line_top[line["line"]] = [{"product": n, "tasks": c}
                                  for n, c in cnt.most_common(4)]
    prod_qty = Counter()
    for line in result["schedule"]:
        for t in line["tasks"]:
            prod_qty[t["product_name"]] += t["qty"]
    return {
        "source": source or ("CP-SAT 排产引擎生成（" + result.get("engine", "auto") + "）"),
        "generated_at": result["generated_at"],
        "engine": result["engine"],
        "summary": {k: s[k] for k in
                    ("orders", "on_time", "tardy", "on_time_rate",
                     "total_tardiness_min", "total_setup_min")},
        "utilization": {k: round(v * 100, 1) for k, v in s["utilization"].items()},
        "bottlenecks": s["bottlenecks"],
        "by_line": {line["line"]: {"line_name": line["line_name"],
                                   "tasks": len(line["tasks"]),
                                   "top_products": line_top.get(line["line"], [])}
                    for line in result["schedule"]},
        "top_products": [{"product": n, "qty": round(q, 0)}
                         for n, q in prod_qty.most_common(12)],
    }


def _tasks_by_date(result):
    by = defaultdict(list)
    for line in result["schedule"]:
        for t in line["tasks"]:
            by.setdefault(t["prod_date"], []).append((line, t))
    return by


def a_report_inbox(result, by="生产计划", when=None, bottleneck_threshold=0.8):
    """A 看板 report_inbox：module=schedule_daily（freq=日），按入库日聚合。

    返回 [{module, data, by, when}, ...]，每个入库日一条。
    """
    when = when or datetime.now().strftime("%Y-%m-%d %H:%M")
    s = result["summary"]
    util = s["utilization"]
    bottlenecks = [f"{k}({util[k]*100:.0f}%)" for k, v in sorted(util.items(), key=lambda x: -x[1])
                   if v >= bottleneck_threshold]
    reports = []
    for date, items in sorted(_tasks_by_date(result).items()):
        plan_qty = round(sum(t["qty"] for _, t in items), 2)
        handover = "\n".join(
            f"{line['line_name']}|{t.get('product_name', t['product'])}×{t['qty']}"
            f"|{t['start']}→{t['end']}|{'产能冲突' if _load_h(t) > 8 else '正常'}"
            for line, t in items)
        reports.append({
            "module": "schedule_daily",
            "data": {
                "plan_date": date,
                "plan_qty": plan_qty,
                "plan_orders": len(items),
                "on_time_rate": round(s["on_time_rate"] * 100, 1),
                "bottleneck": ("、".join(bottlenecks)) or "无",
                "handover": handover,
            },
            "by": by,
            "when": when,
        })
    return reports


def _load_h(t):
    qty = t.get("qty") or 0
    cap = t.get("capacity_8h")
    if not cap:
        return 0
    return round(qty / cap * 8, 2)
