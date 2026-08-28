# -*- coding: utf-8 -*-
"""订单/负荷多模型预测 + 择优（用户要求：哪个预测结论准确，就用哪个）。

预测对象：6 条产线日负荷序列（Σ 数量÷8h产能×8，与排产负荷同口径）。
模型集合：
  dow_factor  星期因子均值（基线）
  wma4_dow    近4周加权移动平均 × 星期因子（规范版 §01 方法）
  naive7      上周同日
  gbdt        TL-XGBoost 式特征工程（lag1/2/3/7 + 滚动3/7均值 + 星期 + 趋势 → GBDT）
  timesfm     Google TimesFM 2.5 零样本（子进程 _ml_forecast venv，P50 点预测）
  ensemble    按回测 MAE 加权集成

择优：walk-forward 回测（训练→逐日预测→对比实际），按线选 MAE 最小模型。
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta

DOW = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
MODELS = ["dow_factor", "wma4_dow", "naive7", "gbdt", "timesfm", "ensemble"]

ML_VENV = "/Users/johnsonbai/Desktop/参考试点/调研报告/终稿/推演资料/_ml_forecast/venv/bin/python"
SERVICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timesfm_service.py")


def _dow_of(date_str):
    return DOW[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def line_load_series(history, products):
    """返回 {line: [(date, load_hour), ...]} 按日期排序。"""
    line_of = {p["id"]: p.get("line") for p in products}
    cap8 = {p["id"]: p.get("capacity_8h") or 0 for p in products}
    by = defaultdict(lambda: defaultdict(float))
    for o in history:
        ln = line_of.get(o["product"])
        c8 = cap8.get(o["product"])
        if ln and c8:
            by[ln][o["due"][:10]] += float(o["qty"]) / c8 * 8
    return {ln: sorted(d.items()) for ln, d in by.items()}


def predict_dow_factor(train, date):
    dow = _dow_of(date)
    vals = [v for d, v in train if _dow_of(d) == dow]
    return _mean(vals) if vals else _mean([v for _, v in train])


def predict_wma4(train, date):
    dow = _dow_of(date)
    same = [(d, v) for d, v in train if _dow_of(d) == dow]
    recent = same[-4:]
    if not recent:
        return predict_dow_factor(train, date)
    wsum = sum(v * w for w, (_, v) in zip([4, 3, 2, 1][-len(recent):], recent))
    wden = sum([4, 3, 2, 1][-len(recent):])
    return wsum / wden


def predict_naive7(train, date):
    target = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    for d, v in reversed(train):
        if d == target:
            return v
    return predict_dow_factor(train, date)


def _gbdt_feat(vals, i, date):
    def g(k):
        return vals[i - k] if i - k >= 0 else 0.0
    return [
        g(1), g(2), g(3), g(7),
        _mean(vals[max(0, i - 3):i]), _mean(vals[max(0, i - 7):i]),
        datetime.strptime(date, "%Y-%m-%d").weekday(), i,
    ]


def predict_gbdt(train_vals, date):
    from sklearn.ensemble import GradientBoostingRegressor
    if len(train_vals) < 10:
        return None
    X, y = [], []
    for i in range(7, len(train_vals)):
        X.append(_gbdt_feat(train_vals, i, date))
        y.append(train_vals[i])
    if len(X) < 5:
        return None
    model = GradientBoostingRegressor(n_estimators=60, max_depth=2,
                                      learning_rate=0.1, random_state=42)
    model.fit(X, y)
    feat = [
        train_vals[-1], train_vals[-2] if len(train_vals) > 1 else 0,
        train_vals[-3] if len(train_vals) > 2 else 0,
        train_vals[-7] if len(train_vals) > 6 else 0,
        _mean(train_vals[-3:]), _mean(train_vals[-7:]),
        datetime.strptime(date, "%Y-%m-%d").weekday(), len(train_vals),
    ]
    return max(0.0, float(model.predict([feat])[0]))


def call_timesfm(seqs, horizon=1):
    """子进程批量调 TimesFM。seqs: {key: [v,...]} → {key: {p50:[...],p10:[...],p90:[...]}}。"""
    if not os.path.exists(ML_VENV):
        return {}
    payload = json.dumps({"seqs": seqs, "horizon": horizon})
    try:
        r = subprocess.run([ML_VENV, SERVICE], input=payload, capture_output=True,
                           text=True, timeout=600, cwd=os.path.dirname(SERVICE))
        if r.returncode != 0:
            return {}
        return json.loads(r.stdout)
    except Exception:
        return {}


def _mae(preds, actuals):
    n = len(preds)
    return sum(abs(p - a) for p, a in zip(preds, actuals)) / n if n else float("inf")


def run_backtest(history, products, train_days=20):
    """walk-forward 回测。返回 {model: {line: mae}}, best_per_line, series。"""
    series = line_load_series(history, products)
    lines = sorted(series)
    all_days = sorted({d for ln in lines for d, _ in series[ln]})
    train_days_list = all_days[:train_days]
    val_days = all_days[train_days:]
    if not val_days:
        return None, None, series
    # 收集 timesfm 批量请求
    tf_reqs = {}
    for ln in lines:
        base = dict(series[ln])
        for step, date in enumerate(val_days):
            hist_vals = [v for d, v in series[ln] if d < date]
            tf_reqs[f"{ln}__{step}"] = hist_vals
    tf_out = call_timesfm(tf_reqs, horizon=1)
    # 逐模型逐线逐日
    err = {m: {ln: [] for ln in lines} for m in MODELS}
    for ln in lines:
        train = [(d, v) for d, v in series[ln] if d in train_days_list]
        base_vals = [v for _, v in train]
        for step, date in enumerate(val_days):
            actual = dict(series[ln]).get(date, 0.0)
            tf_key = f"{ln}__{step}"
            preds = {
                "dow_factor": predict_dow_factor(train, date),
                "wma4_dow": predict_wma4(train, date),
                "naive7": predict_naive7(train, date),
                "gbdt": predict_gbdt([v for _, v in train], date) or predict_dow_factor(train, date),
                "timesfm": tf_out.get(tf_key, {}).get("p50", [predict_dow_factor(train, date)])[0],
            }
            for m in ("dow_factor", "wma4_dow", "naive7", "gbdt", "timesfm"):
                err[m][ln].append(abs(preds[m] - actual))
            train.append((date, actual))
    # MAE + ensemble 权重 + 择优
    mae = {}
    for m in ("dow_factor", "wma4_dow", "naive7", "gbdt", "timesfm"):
        mae[m] = {ln: _mae(err[m][ln], [0] * len(err[m][ln])) for ln in lines}
    best = {}
    for ln in lines:
        best[ln] = min(("dow_factor", "wma4_dow", "naive7", "gbdt", "timesfm"),
                       key=lambda m: mae[m][ln])
    return mae, best, series


def forecast_future(series, products, dates, best, mae):
    """用每线最优模型预测未来 dates（3 天）。返回 {line: {date: load}} + 各模型对比。"""
    lines = sorted(series)
    tf_reqs = {ln: [v for _, v in series[ln]] for ln in lines}
    tf_out = call_timesfm(tf_reqs, horizon=len(dates))
    out = {},
    future = {}
    compare = {}
    for ln in lines:
        train = series[ln]
        vals = [v for _, v in train]
        by_model = {m: [] for m in MODELS}
        for i, date in enumerate(dates):
            by_model["dow_factor"].append(predict_dow_factor(train, date))
            by_model["wma4_dow"].append(predict_wma4(train, date))
            by_model["naive7"].append(predict_naive7(train, date))
            by_model["gbdt"].append(predict_gbdt(vals, date) or predict_dow_factor(train, date))
            by_model["timesfm"].append(tf_out.get(ln, {}).get("p50", [0] * len(dates))[i])
        # ensemble：按回测 MAE 加权（权重 ∝ 1/mae）
        ws = {m: 1.0 / max(mae[m][ln], 1e-6) for m in ("dow_factor", "wma4_dow", "naive7", "gbdt", "timesfm")}
        wsum = sum(ws.values())
        by_model["ensemble"] = [sum(ws[m] * by_model[m][i] for m in ws) / wsum for i in range(len(dates))]
        compare[ln] = {m: [round(x, 2) for x in by_model[m]] for m in MODELS}
        chosen = by_model[best[ln]]
        future[ln] = {d: round(chosen[i], 2) for i, d in enumerate(dates)}
    return future, compare


if __name__ == "__main__":
    pass