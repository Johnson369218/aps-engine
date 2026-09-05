# -*- coding: utf-8 -*-
"""闭环重排（replan）：急单/事件 → 冻结区锁定 + 受影响线最小扰动重排 → 变更清单。

设计（local / 最小扰动）：
- 冻结区任务（start < freeze_before 或显式 frozen_set）逐分钟不变，frozen_touched 恒为 0；
- 未受影响线（新订单 allowed_lines 之外的线）滚动任务保持原位，0 扰动；
- 阶段一（插入即得）：先尝试把新订单塞进现有空隙（不搬动任何滚动任务），全部赶上交期 → 变更清单只含 added；
- 阶段二（真实重排）：塞不下才重排受影响线的滚动任务 + 新订单，交期优先、换型增量最小、
  尽量「贴着交期当天生产」（latest-fit，避免虚假提前生产）；
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


def _setup_of(products, prev_prod, prod):
    return 0 if prev_prod is None or prev_prod == prod else get_setup(products, prev_prod, prod)


def _find_slot(busy_l, start_min, dur, prod, products, due_min=None):
    """在已排序 busy_l[(s,e,p)] 的空隙里找槽位。

    返回 (place_s, place_e, setup)：优先「贴着交期的最晚满足 end≤due_min 的槽」；
    无满足交期槽时返回最早可放（真实延期）。
    """
    first = None      # 最早可放（可能逾期）
    best = None       # 最晚满足交期
    cur = start_min
    prev_prod = None
    for s, e, p in busy_l:
        if e <= cur:
            prev_prod = p
            continue
        setup = _setup_of(products, prev_prod, prod)
        gap_start = cur + setup
        gap_end = s
        if gap_start + dur <= gap_end:
            if first is None:
                first = (gap_start, gap_start + dur, setup)
            if due_min is not None:
                le = min(gap_end, due_min)
                ls = le - dur
                if ls >= gap_start:
                    best = (ls, le, setup)
            else:
                best = (gap_start, gap_start + dur, setup)
        cur = e
        prev_prod = p
    # 尾空隙（无上界）
    setup = _setup_of(products, prev_prod, prod)
    gap_start = cur + setup
    if first is None:
        first = (gap_start, gap_start + dur, setup)
    if due_min is not None:
        le = due_min
        ls = le - dur
        if ls >= gap_start:
            best = (ls, le, setup)
    else:
        best = (gap_start, gap_start + dur, setup)
    return best if best is not None else first


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


def _summarize(schedule, cals, line_ids):
    all_tasks = [t for blk in schedule for t in blk["tasks"]]
    n = len(all_tasks)
    tardy = [t for t in all_tasks if t["tardy_min"] > 0]
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
        util[l] = round(sum(int(t["proc_min"]) for t in ts) / span, 3)
    return {
        "orders": n, "on_time": n - len(tardy), "tardy": len(tardy),
        "on_time_rate": round((n - len(tardy)) / n, 3) if n else 1.0,
        "total_tardiness_min": sum(t["tardy_min"] for t in tardy),
        "max_tardiness_min": max((t["tardy_min"] for t in tardy), default=0),
        "total_setup_min": sum(t.get("setup_min", 0) for t in all_tasks),
        "utilization": util,
        "bottlenecks": sorted([l for l, u in util.items() if u >= 0.8], key=lambda l: -util[l]),
    }


def _build_schedule(frozen, reserved, placed_by_line, line_ids, line_names):
    schedule = []
    for l in line_ids:
        line_tasks = []
        for t in frozen + reserved:
            if t["line"] == l:
                d = dict(t); d["frozen"] = t in frozen; d["is_new"] = False
                d.pop("line", None)
                line_tasks.append(d)
        line_tasks.extend(placed_by_line.get(l, []))
        line_tasks.sort(key=lambda x: x["start"])
        schedule.append({"line": l, "line_name": line_names.get(l, l), "tasks": line_tasks})
    return schedule


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
            reserved.append(t)
        else:
            movable.append(t)

    allowed = {o["id"]: o.get("allowed_lines") or line_ids for o in new_orders}
    new_dur = build_durations(list(new_orders), products, allowed)
    new_items = [{"order": o["id"], "product": o["product"],
                  "product_name": products.get(o["product"], {}).get("name", o["product"]),
                  "qty": o["qty"], "due": o["due"], "priority": o.get("priority", 2),
                  "durs": new_dur.get(o["id"], {}), "allowed": allowed[o["id"]],
                  "order_time": o.get("order_time")} for o in new_orders]
    new_items.sort(key=lambda x: (x["due"], x["priority"], -(x["qty"] or 0)))

    # 固定区间（冻结 + 未受影响线）
    def _fixed_busy():
        busy = {l: [] for l in line_ids}
        for t in frozen + reserved:
            cal = cals[t["line"]]
            busy[t["line"]].append([cal.dt_to_min(parse_dt(t["start"])),
                                    cal.dt_to_min(parse_dt(t["end"])), t["product"]])
        for l in line_ids:
            busy[l].sort(key=lambda x: x[0])
        return busy

    # ── 阶段一：插入即得（不搬动滚动任务）──
    busy1 = _fixed_busy()
    for t in movable:  # 滚动任务原位保留
        cal = cals[t["line"]]
        busy1[t["line"]].append([cal.dt_to_min(parse_dt(t["start"])),
                                 cal.dt_to_min(parse_dt(t["end"])), t["product"]])
    for l in line_ids:
        busy1[l].sort(key=lambda x: x[0])

    inserts = []
    ok = True
    for it in new_items:
        due_dt = parse_dt(it["due"])
        best = None
        for l in it["allowed"]:
            cal = cals[l]
            dur = it["durs"].get(l)
            if not dur:
                continue
            start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
            ps, pe, su = _find_slot(busy1[l], start_min, dur, it["product"], products, cal.dt_to_min(due_dt))
            if pe > cal.dt_to_min(due_dt):
                continue  # 该线塞不下且不逾期
            if best is None or pe < best["pe"]:
                best = {"line": l, "ps": ps, "pe": pe, "setup": su, "dur": dur}
        if best is None:
            ok = False
            break
        l = best["line"]
        busy1[l].append([best["ps"], best["pe"], it["product"]]); busy1[l].sort(key=lambda x: x[0])
        inserts.append({"order": it["order"], "line": l, "product": it["product"],
                        "product_name": it["product_name"], "qty": it["qty"],
                        "proc_min": best["dur"], "setup_min": best["setup"],
                        "start_min": best["ps"], "end_min": best["pe"],
                        "due": it["due"], "priority": it["priority"],
                        "order_time": it["order_time"], "is_new": True})

    if ok:
        placed_by_line = {l: [] for l in line_ids}
        for p in inserts:
            placed_by_line[p["line"]].append(_task_out(p, cals[p["line"]]))
        schedule = _build_schedule(frozen, reserved + movable, placed_by_line, line_ids, line_names)
        change_list = [{"order": p["order"], "line": p["line"], "kind": "added", "frozen": False,
                        "after": {"start": cals[p["line"]].min_to_dt(p["start_min"]).strftime("%Y-%m-%d %H:%M"),
                                  "end": cals[p["line"]].min_to_dt(p["end_min"]).strftime("%Y-%m-%d %H:%M")}}
                       for p in inserts]
        return {"engine": "replan-insert",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "freeze_before": freeze_dt.strftime("%Y-%m-%d %H:%M") if freeze_dt else None,
                "affected_lines": sorted(affected),
                "summary": _summarize(schedule, cals, line_ids),
                "schedule": schedule, "change_list": change_list, "frozen_touched": 0}

    # ── 阶段二：真实重排受影响线 ──
    busy2 = _fixed_busy()
    movable_items = [{"order": t["order"], "product": t["product"],
                      "product_name": t["product_name"], "qty": t["qty"],
                      "due": t["due"], "priority": t["priority"],
                      "proc_min": t["proc_min"], "line": t["line"],
                      "order_time": t["order_time"]} for t in movable]
    to_place = movable_items + [{"order": it["order"], "product": it["product"],
                                 "product_name": it["product_name"], "qty": it["qty"],
                                 "due": it["due"], "priority": it["priority"],
                                 "durs": it["durs"], "allowed": it["allowed"],
                                 "order_time": it["order_time"]} for it in new_items]
    to_place.sort(key=lambda x: (x["due"], x["priority"], -(x["qty"] or 0)))

    placed = []
    for item in to_place:
        due_dt = parse_dt(item["due"])
        if "allowed" in item:  # 新订单
            best = None
            for l in item["allowed"]:
                cal = cals[l]
                dur = item["durs"].get(l)
                if not dur:
                    continue
                start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
                ps, pe, su = _find_slot(busy2[l], start_min, dur, item["product"], products, cal.dt_to_min(due_dt))
                if best is None or pe < best["pe"]:
                    best = {"line": l, "ps": ps, "pe": pe, "setup": su, "dur": dur}
            l = best["line"]; cal = cals[l]
            busy2[l].append([best["ps"], best["pe"], item["product"]]); busy2[l].sort(key=lambda x: x[0])
            placed.append({"order": item["order"], "line": l, "product": item["product"],
                           "product_name": item["product_name"], "qty": item["qty"],
                           "proc_min": best["dur"], "setup_min": best["setup"],
                           "start_min": best["ps"], "end_min": best["pe"],
                           "due": item["due"], "priority": item["priority"],
                           "order_time": item["order_time"], "is_new": True})
        else:  # 滚动任务（固定线）
            l = item["line"]; cal = cals[l]
            start_min = cal.dt_to_min(freeze_dt) if freeze_dt is not None else 0
            ps, pe, su = _find_slot(busy2[l], start_min, item["proc_min"], item["product"],
                                    products, cal.dt_to_min(due_dt))
            busy2[l].append([ps, pe, item["product"]]); busy2[l].sort(key=lambda x: x[0])
            placed.append({"order": item["order"], "line": l, "product": item["product"],
                           "product_name": item["product_name"], "qty": item["qty"],
                           "proc_min": item["proc_min"], "setup_min": su,
                           "start_min": ps, "end_min": pe,
                           "due": item["due"], "priority": item["priority"],
                           "order_time": item["order_time"], "is_new": False})

    placed_by_line = {l: [] for l in line_ids}
    for p in placed:
        placed_by_line[p["line"]].append(_task_out(p, cals[p["line"]]))
    schedule = _build_schedule(frozen, reserved, placed_by_line, line_ids, line_names)

    old_movable = {t["order"]: t for t in movable}
    change_list = []
    for p in placed:
        cal = cals[p["line"]]
        if p["is_new"]:
            change_list.append({"order": p["order"], "line": p["line"], "kind": "added", "frozen": False,
                                "after": {"start": cal.min_to_dt(p["start_min"]).strftime("%Y-%m-%d %H:%M"),
                                          "end": cal.min_to_dt(p["end_min"]).strftime("%Y-%m-%d %H:%M")}})
        else:
            old = old_movable[p["order"]]
            new_s = cal.min_to_dt(p["start_min"]).strftime("%Y-%m-%d %H:%M")
            new_e = cal.min_to_dt(p["end_min"]).strftime("%Y-%m-%d %H:%M")
            if new_s != old["start"] or new_e != old["end"]:
                change_list.append({"order": p["order"], "line": p["line"], "kind": "moved", "frozen": False,
                                    "before": {"start": old["start"], "end": old["end"]},
                                    "after": {"start": new_s, "end": new_e}})

    return {"engine": "replan-heuristic",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "freeze_before": freeze_dt.strftime("%Y-%m-%d %H:%M") if freeze_dt else None,
            "affected_lines": sorted(affected),
            "summary": _summarize(schedule, cals, line_ids),
            "schedule": schedule, "change_list": change_list, "frozen_touched": 0}
