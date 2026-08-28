# -*- coding: utf-8 -*-
"""T+3 滚动预测：按 SKU × 星期因子（历史均值）预测未来 N 天需求。

口径（来自调研报告 2026年车间8月份生产计划-规范版 §01 需求预测）：
  需求预测 = 历史日均 × 星期因子；此处用 8 月历史（orders_aug_strict 293 单，已单位换算）
  按 (SKU, 星期几) 取均值；该星期几无历史 → 用 SKU 日均；再无 → 不预测（诚实）
  精度：单位 kg 保留 1 位，其余取整（复盘：kg保留1位，其余按整数）
  订单：id=<SKU>-<yyyymmdd>F，due=当日 17:00，duration=max(10, round(qty/capacity_8h*480))
"""
from collections import defaultdict

DOW = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]


def _dow_of(date_str):
    from datetime import datetime
    return DOW[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def _round_qty(qty, unit):
    if unit == "kg":
        return round(qty, 1)
    return int(round(qty))


def forecast_orders(history_orders, products, lines, dates, min_appear_days=1):
    """返回 (预测订单列表, stats)。"""
    prod_by_id = {p["id"]: p for p in products}
    line_of = {p["id"]: p.get("line") for p in products}
    cap8 = {p["id"]: p.get("capacity_8h") for p in products}
    unit_of = {p["id"]: p.get("unit", "") for p in products}

    by_sku_dow = defaultdict(lambda: defaultdict(lambda: {"sum": 0.0, "n": 0}))
    by_sku = defaultdict(lambda: {"sum": 0.0, "n": 0})
    for o in history_orders:
        sku = o["product"]
        q = float(o["qty"])
        d = o["due"][:10]
        by_sku_dow[sku][_dow_of(d)]["sum"] += q
        by_sku_dow[sku][_dow_of(d)]["n"] += 1
        by_sku[sku]["sum"] += q
        by_sku[sku]["n"] += 1

    orders, stats = [], {"skus": 0, "per_day": {}}
    for d in dates:
        dow = _dow_of(d)
        day_orders = 0
        for sku in prod_by_id:
            hist = by_sku_dow.get(sku, {}).get(dow)
            avg = None
            if hist and hist["n"] >= min_appear_days:
                avg = hist["sum"] / hist["n"]
            else:
                g = by_sku.get(sku)
                if g and g["n"] >= min_appear_days:
                    avg = g["sum"] / g["n"]
            if not avg or avg <= 0:
                continue
            qty = _round_qty(avg, unit_of.get(sku, ""))
            if qty <= 0:
                continue
            c8 = cap8.get(sku)
            dur = max(10, round(qty / c8 * 480)) if c8 else 10
            orders.append({
                "id": f"{sku}-{d.replace(chr(45), chr(45))}F",
                "product": sku,
                "qty": qty,
                "due": f"{d} 17:00",
                "priority": 2,
                "allowed_lines": [line_of[sku]] if line_of.get(sku) else None,
                "duration_min": dur,
                "order_type": "forecast",
                "forecast_basis": f"历史{dow}均值(8月)",
            })
            day_orders += 1
        stats["per_day"][d] = day_orders
    stats["skus"] = len({o["product"] for o in orders})
    stats["orders"] = len(orders)
    return orders, stats


if __name__ == "__main__":
    import json, sys
    hist = json.load(open(sys.argv[1], encoding="utf-8"))
    products = json.load(open(sys.argv[2], encoding="utf-8"))
    lines = json.load(open(sys.argv[3], encoding="utf-8"))
    dates = sys.argv[4].split(",")
    orders, stats = forecast_orders(hist, products, lines, dates)
    print(json.dumps(stats, ensure_ascii=False))
    json.dump(orders, open(sys.argv[5], "w", encoding="utf-8"), ensure_ascii=False, indent=2)