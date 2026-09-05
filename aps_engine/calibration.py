# -*- coding: utf-8 -*-
"""B3 执行校准：predicted vs actual → 状态机（待实测→已校准/已修正）。
产出为建议与报告；参数改写必须人工审批后执行（红线：pending_replay→审批→生效）。"""
import datetime


def backfill(result, actuals, assumptions, thresholds=(0.05, 0.10)):
    """actuals: {H_key: actual_value}；返回 (records, summary)。"""
    low, high = thresholds
    hyps = assumptions.get("assumptions", assumptions)
    records = []
    for key, actual in actuals.items():
        hyp = hyps.get(key)
        if not hyp:
            continue
        try:
            predicted = float(hyp["value"])
        except (TypeError, ValueError):
            records.append({"key": key, "status": "无法比较", "action": "keep",
                            "predicted": hyp["value"], "actual": actual})
            continue
        delta = (actual - predicted) / predicted if predicted else 1.0
        pct = abs(delta)
        if pct < low:
            rec = {"key": key, "predicted": predicted, "actual": actual,
                   "delta_pct": round(delta, 4), "status": "已校准", "action": "keep"}
        elif pct >= high:
            rec = {"key": key, "predicted": predicted, "actual": actual,
                   "delta_pct": round(delta, 4), "status": "已修正", "action": "correct",
                   "suggestion": actual,
                   "note": "偏差≥10%，建议以实测为准；须审批后写入配置"}
        else:
            rec = {"key": key, "predicted": predicted, "actual": actual,
                   "delta_pct": round(delta, 4), "status": "待实测", "action": "keep",
                   "note": "偏差 5-10%，继续积累样本"}
        records.append(rec)
    summary = {"total": len(records),
               "corrected": sum(1 for r in records if r["action"] == "correct")}
    return records, summary


def write_report(actuals, assumptions, path):
    records, summary = backfill({}, actuals, assumptions)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 校准报告（{datetime.date.today()}）\n\n")
        f.write("| 假设 | 预测 | 实测 | 偏差% | 状态 | 建议 |\n|---|---|---|---|---|---|\n")
        for r in records:
            f.write(f"| {r['key']} | {r['predicted']} | {r['actual']} | {r['delta_pct']:.1%}"
                    f" | {r['status']} | {r.get('suggestion', r.get('note', '-'))} |\n")
        f.write("\n> 修正建议需人工审批后生效（拍板在人）；本报告不改动任何排产参数。\n")
    return records


def apply_corrections(records, config_path):
    """把 action=correct 的建议值写入 config（仅由审批流程调用）。返回写入条数。"""
    # 占位：审批通过后按 key 映射写入 industry 配置对应字段
    return sum(1 for r in records if r["action"] == "correct")


def backfill_execution(plan_before, executions, thresholds=(0.05, 0.10)):
    """执行回填：报工实际 vs 计划（数量达成率 + 是否准时）→ 状态机记录。

    executions: [{order_code, qty_done, actual_end}]（来自台账 execution 表）；
    plan_before: 排产 result。返回 (records, summary)。
    达成率偏差 |delta|<5% → 达成；5-10% → 关注；≥10% → 偏差（建议核实产能/报工数量）。
    """
    low, high = thresholds
    plan_by_order = {t["order"]: t for blk in plan_before.get("schedule", [])
                     for t in blk.get("tasks", [])}
    records = []
    for ex in executions:
        oid = ex.get("order_code")
        t = plan_by_order.get(oid)
        if not t:
            records.append({"key": oid, "status": "无计划", "action": "keep",
                            "predicted_qty": None, "actual_qty": ex.get("qty_done")})
            continue
        plan_qty = float(t.get("qty") or 0)
        done = ex.get("qty_done")
        rec = {"key": oid, "predicted_qty": plan_qty, "actual_qty": done,
               "plan_end": t.get("end"), "actual_end": ex.get("actual_end")}
        if done is None or plan_qty == 0:
            rec.update({"status": "缺报工", "action": "keep"})
            records.append(rec)
            continue
        delta = (float(done) - plan_qty) / plan_qty
        pct = abs(delta)
        rec["delta_pct"] = round(delta, 4)
        if pct < low:
            rec.update({"status": "达成", "action": "keep"})
        elif pct >= high:
            rec.update({"status": "偏差", "action": "correct",
                        "suggestion": "核实产能假设或报工数量",
                        "note": "达成率偏差≥10%，建议回填校验"})
        else:
            rec.update({"status": "关注", "action": "keep", "note": "偏差 5-10%，继续观察"})
        if ex.get("actual_end") and t.get("end"):
            rec["on_time"] = ex["actual_end"] <= t["end"]
        records.append(rec)
    summary = {"total": len(records),
               "corrected": sum(1 for r in records if r["action"] == "correct")}
    return records, summary
