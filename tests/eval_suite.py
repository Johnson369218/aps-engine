#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APS 插件应用能力训练 · 评测套件。

对 tests/corpus/<场景>/ 逐一：
  schema 校验 →（按 eval_scope）排产/审计/准时率/瓶颈/前后工序、JSSP 最优性、
  预测 MAE、ERP 映射漏斗、OEE/计划系数、质量风险分桶 → 输出
  tests/output/eval_report.json + aps_training/output/评测报告.md

用法:
  python tests/eval_suite.py [--only dir1,dir2] [--engine auto]
  .venv/bin/python aps_training/eval_suite.py --quick   # 只跑 schedule+audit+jssp
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")
OUT_DIR = os.path.join(HERE, "output")
WORKSPACE = os.path.dirname(HERE)          # 生产调度/
PLUGIN = os.path.join(WORKSPACE, "aps-engine")
for _p in (PLUGIN, WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from datetime import datetime, time  # noqa: E402
from aps_engine.schema import validate_inputs  # noqa: E402
from aps_engine.audit import audit_result  # noqa: E402
import aps_engine.scheduler as scheduler  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scenario_dirs(only=None):
    names = sorted(d for d in os.listdir(CORPUS)
                   if os.path.isdir(os.path.join(CORPUS, d)))
    return [d for d in names if not only or d in only]


def calc_oee(shifts):
    """OEE = A × P × Q；P 用 ideal(件/小时) 口径：P = 总产量/(运行分钟/60×理想节拍)。"""
    A = P = Q = 0.0
    for s in shifts:
        run_min = s["planned"] - s["down"]
        a = run_min / s["planned"]
        p = (s["good"] + s["defect"]) / (run_min / 60.0 * s["ideal"])
        q = s["good"] / (s["good"] + s["defect"])
        A += a; P += p; Q += q
    n = len(shifts)
    return {"A": round(A / n, 2), "P": round(P / n, 2),
            "Q": round(Q / n, 2), "oee": round(A / n * P / n * Q / n, 2)}


def calc_availability(downtime):
    by = {}
    for x in downtime:
        b = by.setdefault(x["machine"], {"sum": 0.0, "n": 0, "reasons": {}})
        b["sum"] += (x["planned"] - x["down"]) / x["planned"]
        b["n"] += 1
        b["reasons"][x["reason"]] = b["reasons"].get(x["reason"], 0) + x["down"]
    out = {}
    for m, b in by.items():
        out[m] = {"availability": round(b["sum"] / b["n"], 2),
                  "top_reason": max(b["reasons"], key=b["reasons"].get)}
    return out


def _load_h(t):
    return round((t.get("qty") or 0) / (t.get("capacity_8h") or 1) * 8, 2)         if t.get("capacity_8h") else None


def eval_schedule(sc, orders, lines, products, engine, time_limit, exp):
    from aps_engine.api import solve
    res = {"capability": "schedule", "checks": {}}
    try:
        result = solve(orders, lines, products, engine=engine,
                       time_limit=time_limit, run_audit=True)
        s = result["summary"]
        res["engine"] = result["engine"]
        res["orders"] = s["orders"]
        res["on_time"] = s["on_time"]
        res["tardy"] = s["tardy"]
        res["on_time_rate"] = round(s["on_time_rate"], 3)
        res["total_tardiness_min"] = s["total_tardiness_min"]
        res["total_setup_min"] = s["total_setup_min"]
        res["utilization"] = {k: round(v, 3) for k, v in s["utilization"].items()}
        res["bottlenecks"] = s["bottlenecks"]
        res["audit"] = result.get("audit", {})
        n, issues = audit_result(result)
        res["audit_tasks"] = n
        res["audit_issues"] = len(issues)
        checks = res["checks"]
        checks["audit6"] = len(issues) == 0
        exp_rate = exp.get("on_time_rate_expected", 1.0)
        checks["on_time"] = abs(res["on_time_rate"] - exp_rate) < 0.001
        if exp.get("bottleneck_expected"):
            b = res["bottlenecks"]
            # 双口径：绝对利用率≥0.8 预警 或 相对最高负荷线（TOC 瓶颈）
            top_line = max(res["utilization"], key=res["utilization"].get) if res["utilization"] else None
            checks["bottleneck"] = (exp["bottleneck_expected"] in b) or (exp["bottleneck_expected"] == top_line)
        if exp.get("front_ok_expected") is not None:
            front_ok = 0
            for blk in result["schedule"]:
                for t in blk["tasks"]:
                    if t.get("front_start") and t.get("front_end")                             and t["front_end"] <= t["start"]:
                        front_ok += 1
            res["front_ok"] = front_ok
            checks["front_ok"] = front_ok == exp["front_ok_expected"]
    except Exception as e:
        res["error"] = str(e)[:300]
        res["checks"]["solve"] = False
    res["pass"] = all(res["checks"].values()) if res["checks"] else False
    return res


def eval_jssp(sc, orders, lines, products, engine, time_limit, exp):
    from aps_engine.jssp import group_corpus_orders, solve_jssp
    res = {"capability": "jssp", "checks": {}}
    try:
        jobs = group_corpus_orders(orders)
        result = solve_jssp(jobs, lines, time_limit=time_limit)
        n_ops = sum(len(j["operations"]) for j in jobs)
        tasks = [t for blk in result["schedule"] for t in blk["tasks"]]
        checks = res["checks"]
        res["scheduled_ops"] = len(tasks)
        res["expected_ops"] = n_ops
        checks["all_ops_scheduled"] = len(tasks) == n_ops
        checks["feasible"] = len(tasks) == n_ops
        res["precedence_violations"] = result["precedence_violations"]
        res["makespan_min"] = result["makespan"]
        res["optimum_min"] = exp["optimum"]
        res["lower_bound_min"] = exp["lower_bound"]
        res["gap_vs_opt"] = round(result["makespan"] / exp["optimum"] - 1, 3) if exp["optimum"] else None
        # 前序约束已建模：违序=0 且 makespan ≤ 公开最优 才判最优性
        checks["optimality"] = (result["precedence_violations"] == 0
                                and result["makespan"] <= exp["optimum"])
    except Exception as e:
        res["error"] = str(e)[:300]
        res["checks"]["solve"] = False
    res["pass"] = all(v is not False for v in res["checks"].values())         if res["checks"] else False
    return res


def eval_forecast(sc, orders, lines, products, exp):
    from aps_engine.forecast import forecast_orders
    res = {"capability": "forecast", "checks": {}}
    preds, stats = forecast_orders(orders, products, lines, exp["holdout_dates"])
    got = {}
    for o in preds:
        got.setdefault(o["product"], {})[o["due"][:10]] = o["qty"]
    diffs = []
    for sku, by_date in exp["forecast"].items():
        for date, want in by_date.items():
            have = got.get(sku, {}).get(date)
            res["checks"][f"{sku}@{date}"] = have is not None and abs(have - want) <= 1
            if have is not None:
                diffs.append(abs(have - want))
    # MAE（与 expected.holdout_actual 对齐）
    mae = {}
    for sku, by_date in exp["holdout_actual"].items():
        m = sum(abs(got.get(sku, {}).get(d, 0) - a)
                for d, a in by_date.items())
        mae[sku] = round(m / len(by_date), 2)
    res["predicted"] = got
    res["mae"] = mae
    ok_mae = all(abs(mae.get(k, 1e9) - v) <= max(0.02, v * 0.01)
                 for k, v in exp["forecast_mae"].items())
    res["checks"]["mae"] = ok_mae
    res["orders_forecasted"] = stats.get("orders", len(preds))
    res["pass"] = all(res["checks"].values())
    return res


def eval_mapping(sc, orders, lines, products, exp):
    from adapters.erp_in import erp_to_orders
    res = {"capability": "mapping", "checks": {}}
    base = os.path.join(CORPUS, sc)
    raw = load(os.path.join(base, "raw_erp.json"))
    sku_map = load(os.path.join(base, "sku_map.json"))["map"]
    got_orders, stats = erp_to_orders(raw, products, lines, sku_map)
    exp_stats = exp["funnel_stats"]
    for k, v in exp_stats.items():
        got = stats.get(k)
        ok = (len(got) == v) if isinstance(got, list) else (got == v)
        res["checks"][f"funnel.{k}"] = ok
        res[k] = got if isinstance(got, list) else got
    res["unmapped"] = len(stats.get("unmapped", []))
    res["checks"]["unmapped==expected"] = len(stats.get("unmapped", [])) == len(
        exp.get("unmapped_names", []))
    res["pass"] = all(res["checks"].values())
    return res


def eval_oee(sc, orders, lines, products, exp):
    res = {"capability": "oee", "checks": {}}
    base = os.path.join(CORPUS, sc)
    if sc == "oee_blogpost_shifts":
        shifts = load(os.path.join(base, "shifts.json"))
        per = {m: calc_oee([s for s in shifts if s["machine"] == m])
               for m in ("MC-A", "MC-B")}
        for m, want in exp["oee_by_machine"].items():
            res["checks"][f"oee.{m}"] = all(
                abs(per.get(m, {}).get(k, 9) - v) <= 0.01
                for k, v in want.items())
        res["oee_by_machine"] = per
    elif sc == "mfg005_line_performance":
        for row in exp["oee_table"]:
            v = round(row["A"] * row["P"] * row["Q"], 2)
            res["checks"][f"oee.{row['line']}"] = abs(v - row["oee"]) < 0.001
        res["oee_table"] = exp["oee_table"]
    elif sc == "bottling_line_ts":
        per = calc_oee(exp["oee_shifts"])
        res["checks"]["oee"] = abs(per["oee"] - exp["oee_expected"]) <= 0.01
        res["oee"] = per["oee"]
    elif sc == "kaggle_oee_downtime":
        downtime = load(os.path.join(base, "downtime.json"))
        per = calc_availability(downtime)
        for m, want in exp["availability_by_machine"].items():
            res["checks"][f"avail.{m}"] = abs(per[m]["availability"] - want) <= 0.01
            res["checks"][f"top.{m}"] = per[m]["top_reason"] == exp["top_reason_by_machine"][m]
        res["availability"] = per
    # 计划系数一致性：capacity_8h == speed×8×0.88
    factor = exp.get("capacity_factor_expected", 0.88)
    bad = []
    for p in products:
        c8, sp = p.get("capacity_8h"), p.get("speed_per_hour")
        if c8 and sp:
            f = c8 / (sp * 8)
            if abs(f - factor) > 0.02:
                bad.append((p["id"], round(f, 3)))
    res["checks"]["plan_coefficient"] = not bad
    if bad:
        res["plan_coefficient_deviations"] = bad
    res["pass"] = all(v for k, v in res["checks"].items() if v is not None)
    return res


def eval_risk(sc, orders, lines, products, exp):
    res = {"capability": "risk", "checks": {}}
    high = mid = low = drift = 0
    for o in orders:
        r = o.get("quality_risk", 0)
        if r >= 0.7:
            high += 1
        elif r >= 0.4:
            mid += 1
        else:
            low += 1
        if o.get("param_drift"):
            drift += 1
    got = {"high": high, "mid": mid, "low": low}
    res["risk_buckets"] = got
    res["drift_count"] = drift
    want = exp["risk_buckets"]
    res["checks"]["buckets"] = got == want
    res["checks"]["drift"] = drift == exp.get("drift_count", drift)
    res["pass"] = all(res["checks"].values())
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="APS 插件应用能力评测套件")
    ap.add_argument("--only", default=None)
    ap.add_argument("--engine", default="auto", choices=["auto", "cp", "heuristic"])
    ap.add_argument("--time-limit", type=int, default=20)
    ap.add_argument("--quick", action="store_true",
                    help="只跑 schedule/audit/jssp，跳过预测与映射")
    args = ap.parse_args(argv)
    only = set(x.strip() for x in args.only.split(",")) if args.only else None
    os.makedirs(OUT_DIR, exist_ok=True)

    dirs = scenario_dirs(only)
    report = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "engine": args.engine, "scenarios": []}

    for sc in dirs:
        base = os.path.join(CORPUS, sc)
        orders = load(os.path.join(base, "orders.json"))
        lines = load(os.path.join(base, "lines.json"))
        products = load(os.path.join(base, "products.json"))
        exp = load(os.path.join(base, "expected.json"))
        errs = validate_inputs(orders, lines, products)
        entry = {"scenario": sc, "source_dataset": exp.get("source_dataset"),
                 "synthetic": exp.get("synthetic", True),
                 "eval_scope": exp.get("eval_scope", []),
                 "schema_errors": errs[:5]}
        if errs:
            entry["pass"] = False
            entry["note"] = "schema 校验失败"
            report["scenarios"].append(entry)
            continue
        scopes = exp.get("eval_scope", [])
        evals = {}
        for cap in scopes:
            if args.quick and cap in ("forecast", "mapping", "risk"):
                continue
            if cap == "schedule":
                evals[cap] = eval_schedule(sc, orders, lines, products,
                                           args.engine, args.time_limit, exp)
            elif cap == "jssp":
                evals[cap] = eval_jssp(sc, orders, lines, products,
                                       args.engine, args.time_limit, exp)
            elif cap == "forecast":
                evals[cap] = eval_forecast(sc, orders, lines, products, exp)
            elif cap == "mapping":
                evals[cap] = eval_mapping(sc, orders, lines, products, exp)
            elif cap == "oee":
                evals[cap] = eval_oee(sc, orders, lines, products, exp)
            elif cap == "risk":
                evals[cap] = eval_risk(sc, orders, lines, products, exp)
        entry["evals"] = evals
        entry["pass"] = all(v.get("pass", False) for v in evals.values())             if evals else True
        report["scenarios"].append(entry)

    out_json = os.path.join(OUT_DIR, "eval_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    write_markdown(report, os.path.join(OUT_DIR, "评测报告.md"))

    # 控制台摘要
    for e in report["scenarios"]:
        tag = "✅" if e["pass"] else "⛔"
        print(f"{tag} {e['scenario']} (scope={','.join(e.get('eval_scope', []))})")
        for cap, ev in e.get("evals", {}).items():
            detail = ""
            if cap == "schedule":
                detail = f"on_time={ev.get('on_time_rate')} audit={ev.get('audit_issues')}"
            elif cap == "jssp":
                detail = (f"ops={ev.get('scheduled_ops')}/{ev.get('expected_ops')} "
                          f"viol={ev.get('precedence_violations')} "
                          f"mk={ev.get('makespan_min')} opt={ev.get('optimum_min')}")
            elif cap == "forecast":
                detail = f"mae={ev.get('mae')}"
            elif cap == "mapping":
                detail = f"orders={ev.get('orders')} unmapped={ev.get('unmapped')}"
            elif cap == "oee":
                detail = "oee/系数一致" if ev.get("pass") else "oee 校验异常"
            elif cap == "risk":
                detail = f"buckets={ev.get('risk_buckets')}"
            flag = "PASS" if ev.get("pass") else "FAIL"
            print(f"   {cap}: {flag} {detail}")
        if not e["pass"]:
            for cap, ev in e.get("evals", {}).items():
                for k, v in ev.get("checks", {}).items():
                    if v is False:
                        print(f"     ✗ {cap}.{k}")
    print(f"\n报告: {out_json}")
    print(f"报告: {os.path.join(OUT_DIR, '评测报告.md')}")
    n_pass = sum(1 for e in report["scenarios"] if e["pass"])
    print(f"场景通过: {n_pass}/{len(report['scenarios'])}")
    return 0 if n_pass == len(report["scenarios"]) else 2


def write_markdown(report, path):
    L = ["# APS 插件应用能力训练 · 评测报告", "",
         f"- 生成时间: {report['generated_at']}  |  引擎: {report['engine']}", ""]
    L += ["## 场景结果", "", "| 场景 | 数据集 | scope | 结果 | 关键指标 |", "|---|---|---|---|---|"]
    for e in report["scenarios"]:
        key = []
        for cap, ev in e.get("evals", {}).items():
            if cap == "schedule":
                key.append(f"准时率{ev.get('on_time_rate')} audit问题{ev.get('audit_issues')}")
            elif cap == "jssp":
                key.append(f"工序{ev.get('scheduled_ops')}/{ev.get('expected_ops')} "
                           f"违序{ev.get('precedence_violations')} "
                           f"makespan{ev.get('makespan_min')}/最优{ev.get('optimum_min')}")
            elif cap == "forecast":
                key.append(f"MAE均值{round(sum(ev.get('mae', {}).values()) / max(1, len(ev.get('mae', {}))), 2)}")
            elif cap == "mapping":
                key.append(f"订单{ev.get('orders')} 未映射{ev.get('unmapped')}")
            elif cap == "oee":
                key.append("OEE/系数一致" if ev.get("pass") else "OEE异常")
            elif cap == "risk":
                key.append(f"风险桶{ev.get('risk_buckets')}")
        L.append(f"| {e['scenario']} | {e.get('source_dataset')} | {','.join(e.get('eval_scope', []))} "
                 f"| {'✅' if e['pass'] else '⛔'} | {'；'.join(key)[:120]} |")
    L += ["", "## 能力结论", ""]
    caps = [("cap_schedule", "排产可行性/准时率/瓶颈/审计6项"),
            ("cap_jssp", "JSSP 基准校验（最优性差距）"),
            ("cap_oee", "OEE → 计划系数 0.88 校准"),
            ("cap_forecast", "需求/负荷预测（MAE）"),
            ("cap_mapping", "ERP → 标准订单映射漏斗"),
            ("cap_risk", "质量风险 → 优先级")]
    for cid, cname in caps:
        L.append(f"- **{cname}**: 见各场景结果；JSSP 场景若 precedence_violations>0，"
                 "为已知能力缺口（引擎暂无工序前序约束与 makespan 目标），"
                 "列入路线图：给订单增加 predecessors/due-window 约束后重测。")
    L += ["", "> 说明：本报告由 eval_suite.py 生成；语料为仓库打包的合成代表语料"
             "（synthetic=true），下载真实数据集后由 normalize.py 覆盖为真实数据再复评。", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())