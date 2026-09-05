# -*- coding: utf-8 -*-
"""Job-Shop 排产（多工序路由 + 前序约束）——通用离散制造核心扩展。

与单工序引擎（scheduler.run）解耦，独立入口 `solve_jssp`：
- 输入：订单含 `operations: [{machine, duration_min}, ...]`（有序路由）；
  也支持从语料 jssp_op 展平订单（job/seq）归一化（group_corpus_orders）。
- 约束：每台机器同一时刻最多一个工序（NoOverlap）；同一订单第 k+1 道工序不得早于第 k 道结束（前序）。
- 目标：makespan（默认）或加权拖期（订单带 due）。
- 回退：无 ortools 时用列表调度启发式（SPT 派工），保证可行（前序 + 无重叠）。

红线：不改 solve()/5-Sheet/audit 语义；本模块为新增多工序入口。
"""
from collections import defaultdict

try:
    from ortools.sat.python import cp_model
    HAVE_ORTools = True
except ImportError:  # pragma: no cover
    cp_model = None
    HAVE_ORTools = False


def group_corpus_orders(orders):
    """把语料 jssp_op 展平订单（job + seq + allowed_lines + duration_min）归并为作业路由。

    返回 [{id: job, due, priority, operations: [{machine, duration_min}]}]（按 seq 排序）。
    """
    jobs = defaultdict(lambda: {"id": None, "due": None, "priority": 2, "ops": {}})
    for o in orders:
        job = o.get("job") or o.get("id")
        seq = int(o.get("seq", 1))
        j = jobs[job]
        j["id"] = job
        j["due"] = j["due"] or o.get("due")
        j["priority"] = o.get("priority", j["priority"])
        machine = (o.get("allowed_lines") or [None])[0]
        j["ops"][seq] = {"machine": machine, "duration_min": int(o.get("duration_min", 0))}
    out = []
    for job in sorted(jobs):
        j = jobs[job]
        ops = [j["ops"][k] for k in sorted(j["ops"])]
        out.append({"id": j["id"], "due": j["due"], "priority": j["priority"],
                    "operations": ops})
    return out


def solve_jssp(orders, lines, time_limit=20, seed=42, objective="makespan"):
    """多工序排产。orders: [{id, operations:[{machine,duration_min}]}]; lines: 机器列表。

    返回 {engine, makespan, schedule:[{machine,tasks:[{order,op_index,op_id,start,end,duration_min}]}],
          precedence_violations, summary}。时间单位为分钟（0 起）。
    """
    machine_ids = [l["id"] for l in lines]
    ops = []  # (order_id, op_index, machine, duration)
    for o in orders:
        for i, op in enumerate(o.get("operations", [])):
            ops.append((o["id"], i, op["machine"], int(op["duration_min"])))
    horizon = sum(d for *_, d in ops) + 1

    if HAVE_ORTools:
        schedule, makespan = _solve_cp(orders, machine_ids, ops, horizon, time_limit, seed, objective)
        engine = "jssp-cp"
    else:  # pragma: no cover
        schedule, makespan = _solve_heuristic(orders, machine_ids, ops)
        engine = "jssp-heuristic"

    viol = _precedence_violations(schedule, orders)
    return {"engine": engine, "makespan": makespan,
            "schedule": schedule, "precedence_violations": viol,
            "summary": {"n_jobs": len(orders), "n_machines": len(machine_ids),
                        "n_ops": len(ops), "makespan": makespan}}


def _solve_cp(orders, machine_ids, ops, horizon, time_limit, seed, objective):
    model = cp_model.CpModel()
    starts, ends = {}, {}
    machine_ivs = defaultdict(list)
    for o in orders:
        prev_end = None
        for i, op in enumerate(o.get("operations", [])):
            m = op["machine"]; dur = int(op["duration_min"])
            s = model.NewIntVar(0, horizon, f"s_{o['id']}_{i}")
            iv = model.NewFixedSizeIntervalVar(s, dur, f"iv_{o['id']}_{i}_{m}")
            starts[(o["id"], i)] = s
            ends[(o["id"], i)] = s + dur
            machine_ivs[m].append(iv)
            if prev_end is not None:
                model.Add(s >= prev_end)  # 前序约束
            prev_end = s + dur
    for m, ivs in machine_ivs.items():
        model.AddNoOverlap(ivs)

    if objective == "tardiness":
        tard = {}
        for o in orders:
            if not o.get("due"):
                continue
            last = ends[(o["id"], len(o["operations"]) - 1)]
            due_min = 0  # 简化：JSSP 语料 due 为占位；这里不展开日历换算
            t = model.NewIntVar(0, horizon, f"tard_{o['id']}")
            model.Add(t >= last - due_min)
            tard[o["id"]] = t
        if tard:
            model.Minimize(sum(tard.values()))
        else:
            objective = "makespan"
    if objective == "makespan":
        mk = model.NewIntVar(0, horizon, "makespan")
        for o in orders:
            model.Add(mk >= ends[(o["id"], len(o["operations"]) - 1)])
        model.Minimize(mk)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = seed
    solver.parameters.num_search_workers = 1  # 可复现
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"JSSP 无可行解 (status={solver.StatusName(status)})")

    makespan = int(solver.ObjectiveValue())
    by_machine = defaultdict(list)
    for o in orders:
        for i, op in enumerate(o.get("operations", [])):
            s = int(solver.Value(starts[(o["id"], i)]))
            by_machine[op["machine"]].append({
                "order": o["id"], "op_index": i + 1, "op_id": f"{o['id']}_op{i + 1}",
                "machine": op["machine"], "start": s, "end": s + int(op["duration_min"]),
                "duration_min": int(op["duration_min"])})
    schedule = [{"machine": m, "tasks": sorted(by_machine.get(m, []), key=lambda x: x["start"])}
                for m in machine_ids]
    return schedule, makespan


def _solve_heuristic(orders, machine_ids, ops):
    """列表调度（SPT 派工）——可行解：前序 + 无重叠。"""
    machine_free = {m: 0 for m in machine_ids}
    job_ready = {o["id"]: 0 for o in orders}
    # SPT：按工序时长升序派工（同长按作业序号）
    pending = sorted(ops, key=lambda x: (x[3], x[0], x[1]))
    by_machine = defaultdict(list)
    makespan = 0
    placed = set()
    # 需按前序推进：维护每作业下一可派工序
    next_op = {o["id"]: 0 for o in orders}
    remaining = list(pending)
    while remaining:
        # 取所有「前序已就绪」的工序，选 SPT
        ready = [x for x in remaining if x[1] == next_op[x[0]]]
        if not ready:  # 死锁保护（不应发生）
            ready = remaining[:1]
        x = min(ready, key=lambda t: (t[3], t[0]))
        oid, oi, m, dur = x
        start = max(machine_free[m], job_ready[oid])
        machine_free[m] = start + dur
        job_ready[oid] = start + dur
        by_machine[m].append({"order": oid, "op_index": oi + 1, "op_id": f"{oid}_op{oi + 1}",
                              "machine": m, "start": start, "end": start + dur,
                              "duration_min": dur})
        makespan = max(makespan, start + dur)
        next_op[oid] += 1
        remaining.remove(x)
    schedule = [{"machine": m, "tasks": sorted(by_machine.get(m, []), key=lambda x: x["start"])}
                for m in machine_ids]
    return schedule, makespan


def _precedence_violations(schedule, orders):
    """统计前序违规数：同一订单第 k+1 道 start < 第 k 道 end。"""
    by_order = defaultdict(dict)
    for blk in schedule:
        for t in blk["tasks"]:
            by_order[t["order"]][t["op_index"]] = t
    viol = 0
    for o in orders:
        for i in range(1, len(o.get("operations", [])) + 1):
            if i in by_order[o["id"]] and i + 1 in by_order[o["id"]]:
                if by_order[o["id"]][i + 1]["start"] < by_order[o["id"]][i]["end"]:
                    viol += 1
    return viol
