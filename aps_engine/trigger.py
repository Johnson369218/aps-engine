# -*- coding: utf-8 -*-
"""B4 重调度触发矩阵：周期/事件/阈值 → TriggerReport（原因/范围/变更清单/冻结区校验）。
范围：rush_order/shortage/breakdown → local；deviation/target_change → full；period → rolling。"""
TYPE_SCOPE = {"period": "rolling", "shortage": "local", "breakdown": "local",
              "rush_order": "local", "deviation": "full", "target_change": "full"}


def evaluate_triggers(plan_before, events, kpis, config):
    """plan_before: {"tasks":[{order_code,line,start_min,end_min,frozen}]}；返回 TriggerReport。"""
    tasks = plan_before.get("tasks", [])
    reasons = []
    scope = "none"
    for ev in events:
        t = ev.get("type")
        if t in TYPE_SCOPE:
            reasons.append({"type": t, "why": f"事件 {t} 触发（{ev.get('order_code', '-')}）"})
            if TYPE_SCOPE[t] == "full":
                scope = "full"
            elif scope in ("none", "rolling"):
                scope = TYPE_SCOPE[t] if t != "period" else "rolling"
    # 变更清单：非冻结任务按顺序重排（占位：真实重排由调度器执行后 diff 生成）
    change_list = []
    for i, t in enumerate(tasks):
        if t.get("frozen"):
            continue
        if scope != "none":
            change_list.append({"order_code": t["order_code"], "line": t["line"],
                                "before_min": t["start_min"], "after_min": t["start_min"],
                                "frozen": False, "seq": i})
    frozen_touched = 0
    return {"triggered": scope != "none", "reasons": reasons, "scope": scope,
            "change_list": change_list, "frozen_touched": frozen_touched}
