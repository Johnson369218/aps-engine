# -*- coding: utf-8 -*-
"""闭环重排（replan）：急单/事件 → 冻结区锁定 + 受影响线真实重排 → 变更清单。

设计（最小扰动 / local 语义）：
- 冻结区任务（start < freeze_before 或显式 frozen_set）逐分钟不变，frozen_touched 恒为 0；
- 未受影响线（新订单 allowed_lines 之外的线）滚动任务保持原位，0 扰动；
- 仅受影响线的滚动任务 + 新订单在真实区间（工作分钟域，日历感知）重排：
  交期优先、换型增量最小，优先「最早能赶上交期的槽位」，赶不上才落到最早可放槽；
- 产出可稽核 change_list（moved / added，含 before→after 与 frozen 标志）。

红线：仅作 what-if 建议（拍板在人），不自动改写排产参数、不改 solve() 语义。
"""
from datetime import datetime

from aps_engine.scheduler import Calendar, build_durations, get_setup, parse_dt


def _extract_tasks(plan_before):
    tasks = []
    for blk in plan_before.get("schedule", []):
        for t in blk.get("tasks", []):
            tasks.append({
                "order": t.get("order"),
                "line": blk.get("line"),
                "product": t.get("product"),
                "product_name": t.get("product_name", t.get("product")),
                "qty": t.get("qty"),
                "due": t.get("due"),
                "priority": t.get("priority", 2),
                "proc_min": t.get("proc_min"),
                "setup_min": t.get("setup_min", 0),
                "start": t.get("start"),
                "end": t.get("end"),
                "prod_date": t.get("prod_date"),
                "tardy_min": t.get("tardy_min", 0),
                "early_days": t.get("early_days", 0),
                "order_time": t.get("order_time"),
                "order_lead_h": t.get("order_lead_h"),
                "front_start": t.get("front_start"),
                "front_end": t.get("front_end"),
            })
    return tasks


def _find_slot(busy_l, start_min, dur, prod, products, due_min=None):
    """在已排序 busy_l[(s,e,p)] 的空隙里找槽位。

    返回 (place_s, place_e, setup)：优先「最早且 end≤due_min」；无满足交期槽时返回最早可放。
    """
    first_feasible = None
    cur = start_min
    prev_prod = None
    for s, e, p in busy_l:
        if e <= cur:
            prev_prod = p
            continue
        setup = 0 if prev_prod is None or prev_prod == prod else get_setup(products, prev_prod, prod)
        ps, pe = cur + setup, cur + setup + dur
        if pe <= s:  # 该空隙放得下
            if due_min is None or pe <= due_min:
                return ps, pe, setup
            if first_feasible is None:
                first_feasible = (ps, pe, setup)
        cur = e
        prev_prod = p
    setup = 0 if prev_prod is None or prev_prod == prod else get_setup(products, prev_prod, prod)
    ps, pe = cur + setup, cur + setup + dur
    if due_min is None or pe <= due_min:
        return ps, pe, setup
    return first_feasible if first_feasible is not None else (ps, pe, setup)


def replan(plan_before, new_orders, lines, products,
           freeze_before=None, frozen_set=None, seed=42):
    """重排：返回 {engine, generated_at, freeze_before, affected_lines, summary,
    schedule, change_list, frozen_touched}。new_orders 为引擎订单（id/product/qty/due/...）。"""
    products = {p["id"]: p for p in products} if isinstance(products, list) else dict(products)
    line_ids = [l["id"] for l in lines]
    line_names = {l["id"]: l["name"] for l in lines}
    cals = {l["id"]: Calendar(l.get("first_date", "2026-08-01"),
                              l.get("shift_start", "08:00"),
                              l.get("work_minutes_per_day", 480),
                              l.get("weekends_off", True)) for l in lines}
    freeze_dt = parse_dt(freeze_before) if isinstance(freeze_before, str) else freeze_before
    frozen_set = set(frozen_set or [])
    new_orders = list(new_orders or [])
    affected = {l for o in new_orders for l in (o.get("allowed_lines") or line_ids)}

    tasks = _extract_tasks(plan_before)
    frozen, reserved, movable = [], [], []
    for t in tasks:
        is_frozen = t["order"] in frozen_set or (freeze_dt is not None and parse_dt(t["start"]) < freeze_dt)
        if is_frozen:
            frozen.append(t)
        elif t["line"] not in affected:
            reserved.append(t)      # 未受影响线：原位保持，0 扰动
        else:
            movable.append(t)       # 受影响线：参与重排

    # 冻结 + 未受影响线 = 占位区间
    busy = {l: [] for l in line_ids}
    for t in frozen + reserved:
        cal = cals[t["line"]]
        busy[t["line"]].append([cal.dt_to_min(parse_dt(t["start"])),
                                cal.dt_to_min(parse_dt(t["end"])), t["product"]])
    for l in line_ids:
        busy[l].sort(key=lambda x: x[0])

    # 待放：受影响线滚动任务（固定线）+ 新订单（可选线）
    to_place = []
    for t in movable:
        to_place.append({"order": t["order"], "product": t["product"],
                         "product_name": t["product_name"], "qty": t["qty"],
                         "due": t["due"], "priority": t["priority"],
                         "proc_min": t["proc_min"], "line": t["line"], "is_new": False,
                         "order_time": t["order_time"]})
    allowed = {o["id"]: o.get("allowed_lines") or line_ids for o in new_orders}
    new_dur = build_durations(list(new_orders), products, allowed)
    for o in new_orders:
        to_place.append({"order": o["id"], "product": o["product"],
                         "product_name": products.get(o["product"], {}).get("name", o["product"]),
                         "qty": o["qty"], "due": o["due"], "priority": o.get("priority", 2),
                         "proc_min": None, "allowed": allowed[o["id"]],
                         "durs": new_dur.get(o["id"], {}), "is_new": True,
                         "order_time": o.get("order_time")})

    to_place.sort(key=lambda x: (x["due"], x["priority"], -(x["qty"] or 0)))

    placed = []
    for item in to_place:
        due_dt = parse_dt(item["due"])
        if item["is_new"]:
            best = None
            for l in item["allowed"]:
                cal = cals[l]
                dur = item["durs"].get(l)
                if not dur:
                    continue
                start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
                slot = _find_slot(busy[l], start_min, dur, item["product"], products, cal.dt_to_min(due_dt))
                if best is None or slot[1] < best["pe"]:
                    best = {"line": l, "ps": slot[0], "pe": slot[1], "setup": slot[2], "dur": dur}
            if best is None:
                l = item["allowed"][0]; cal = cals[l]
                dur = item["durs"].get(l) or max(10, int((item["qty"] or 1) * 480 / 480))
                start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
                s, e, su = _find_slot(busy[l], start_min, dur, item["product"], products, None)
                best = {"line": l, "ps": s, "pe": e, "setup": su, "dur": dur}
            l = best["line"]; cal = cals[l]
            busy[l].append([best["ps"], best["pe"], item["product"]]); busy[l].sort(key=lambda x: x[0])
            placed.append({"order": item["order"], "line": l, "product": item["product"],
                           "product_name": item["product_name"], "qty": item["qty"],
                           "proc_min": best["dur"], "setup_min": best["setup"],
                           "start_min": best["ps"], "end_min": best["pe"],
                           "due": item["due"], "priority": item["priority"],
                           "order_time": item["order_time"], "is_new": True})
        else:
            l = item["line"]; cal = cals[l]
            start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
            ps, pe, su = _find_slot(busy[l], start_min, item["proc_min"], item["product"],
                                    products, cal.dt_to_min(due_dt))
            busy[l].append([ps, pe, item["product"]]); busy[l].sort(key=lambda x: x[0])
            placed.append({"order": item["order"], "line": l, "product": item["product"],
                           "product_name": item["product_name"], "qty": item["qty"],
                           "proc_min": item["proc_min"], "setup_min": su,
                           "start_min": ps, "end_min": pe,
                           "due": item["due"], "priority": item["priority"],
                           "order_time": item["order_time"], "is_new": False})

    def _task_out(t, cal):
        start_dt = cal.min_to_dt(t["start_min"]); end_dt = cal.min_to_dt(t["end_min"])
        due_dt = parse_dt(t["due"])
        tardy = max(0, int((end_dt - due_dt).total_seconds() / 60))
        early = max(0, (due_dt.date() - end_dt.date()).days)
        return {"order": t["order"], "product": t["product"],
                "product_name": t["product_name"], "qty": t["qty"],
                "proc_min": int(t["proc_min"]), "setup_min": t["setup_min"],
                "setup_from": "-", "start": start_dt.strftime("%Y-%m-%d %H:%M"),
                "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                "prod_date": end_dt.strftime("%Y-%m-%d"),
                "due": t["due"], "tardy_min": tardy, "early_days": early,
                "order_time": t.get("order_time"),
                "order_lead_h": None, "front_start": None, "front_end": None,
                "priority": t["priority"], "frozen": False, "is_new": t["is_new"]}

    placed_by_line = {l: [] for l in line_ids}
    for p in placed:
        placed_by_line[p["line"]].append(_task_out(p, cals[p["line"]]))

    schedule = []
    for l in line_ids:
        line_tasks = []
        for t in frozen + reserved:
            if t["line"] == l:
                d = dict(t); d["frozen"] = t in frozen; d["is_new"] = False
                d.pop("line", None)
                line_tasks.append(d)
        line_tasks.extend(placed_by_line[l])
        line_tasks.sort(key=lambda x: x["start"])
        schedule.append({"line": l, "line_name": line_names.get(l, l), "tasks": line_tasks})

    # 变更清单：受影响线滚动任务 moved / 新订单 added
    change_list = []
    old_movable = {t["order"]: t for t in movable}
    for p in placed:
        cal = cals[p["line"]]
        if p["is_new"]:
            change_list.append({"order": p["order"], "line": p["line"], "kind": "added",
                                "frozen": False,
                                "after": {"start": cal.min_to_dt(p["start_min"]).strftime("%Y-%m-%d %H:%M"),
                                          "end": cal.min_to_dt(p["end_min"]).strftime("%Y-%m-%d %H:%M")}})
        else:
            old = old_movable[p["order"]]
            new_s = cal.min_to_dt(p["start_min"]).strftime("%Y-%m-%d %H:%M")
            new_e = cal.min_to_dt(p["end_min"]).strftime("%Y-%m-%d %H:%M")
            if new_s != old["start"] or new_e != old["end"]:
                change_list.append({"order": p["order"], "line": p["line"], "kind": "moved",
                                    "frozen": False,
                                    "before": {"start": old["start"], "end": old["end"]},
                                    "after": {"start": new_s, "end": new_e}})

    all_tasks = [t for blk in schedule for t in blk["tasks"]]
    n = len(all_tasks)
    tardy = [t for t in all_tasks if t["tardy_min"] > 0]
    total_tard = sum(t["tardy_min"] for t in tardy)
    total_setup = sum(t.get("setup_min", 0) for t in all_tasks)
    util = {}
    for l in line_ids:
        ts = [t for blk in schedule if blk["line"] == l for t in blk["tasks"]]
        if not ts:
            util[l] = 0.0
            continue
        cal = cals[l]
        s0 = min(cal.dt_to_min(parse_dt(t["start"])) for t in ts)
        e1 = max(cal.dt_to_min(parse_dt(t["end"])) for t in ts)
        span = max(e1 - s0, cal.wmpd)
        proc = sum(int(t["proc_min"]) for t in ts)
        util[l] = round(proc / span, 3)
    summary = {
        "orders": n, "on_time": n - len(tardy), "tardy": len(tardy),
        "on_time_rate": round((n - len(tardy)) / n, 3) if n else 1.0,
        "total_tardiness_min": total_tard,
        "max_tardiness_min": max((t["tardy_min"] for t in tardy), default=0),
        "total_setup_min": total_setup,
        "utilization": util,
        "bottlenecks": sorted([l for l, u in util.items() if u >= 0.8], key=lambda l: -util[l]),
    }

    return {"engine": "replan-heuristic",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "freeze_before": freeze_dt.strftime("%Y-%m-%d %H:%M") if freeze_dt else None,
            "affected_lines": sorted(affected),
            "summary": summary, "schedule": schedule,
            "change_list": change_list, "frozen_touched": 0}
