# -*- coding: utf-8 -*-
"""输入校验：orders/lines/products（口径来自 data/ 与 real/ 真实数据结构）。"""
import re
from datetime import datetime


class ValidationError(Exception):
    pass


_DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")


def _parse_dt(s):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def validate_inputs(orders, lines, products):
    """返回错误列表；空列表=通过。"""
    errors = []

    if not isinstance(lines, list) or not lines:
        errors.append("lines 必须是非空列表")
    else:
        ids = [l.get("id") for l in lines]
        if len(ids) != len(set(ids)):
            errors.append("lines.id 存在重复")
        for l in lines:
            if not l.get("id") or not l.get("name"):
                errors.append(f"产线缺少 id/name: {l}")
            if int(l.get("work_minutes_per_day", 480)) <= 0:
                errors.append(f"产线 {l.get('id')} work_minutes_per_day 必须>0")
            if not re.match(r"^\d{2}:\d{2}$", str(l.get("shift_start", "08:00"))):
                errors.append(f"产线 {l.get('id')} shift_start 格式应为 HH:MM")
            if not _parse_dt(str(l.get("first_date", ""))):
                errors.append(f"产线 {l.get('id')} first_date 格式应为 YYYY-MM-DD")
            if int(l.get("capacity", 1)) < 1:
                errors.append(f"产线 {l.get('id')} capacity 必须>=1")

    if not isinstance(products, list) or not products:
        errors.append("products 必须是非空列表")
    else:
        pids = [p.get("id") for p in products]
        if len(pids) != len(set(pids)):
            errors.append("products.id 存在重复")
        for p in products:
            if not p.get("id"):
                errors.append("产品缺少 id")
                continue
            cap = p.get("capacity_8h")
            spd = p.get("speed_per_hour")
            if (cap is None or float(cap) <= 0) and (spd is None or float(spd) <= 0):
                errors.append(f"产品 {p.get('id')} 必须提供 capacity_8h 或 speed_per_hour>0")
            sm = p.get("setup_min")
            if sm is not None:
                if not isinstance(sm, dict):
                    errors.append(f"产品 {p.get('id')} setup_min 应为 dict")
                else:
                    for k, v in sm.items():
                        if not isinstance(v, (int, float)) or v < 0:
                            errors.append(f"产品 {p.get('id')} setup_min[{k}] 应为非负数")

    if not isinstance(orders, list) or not orders:
        errors.append("orders 必须是非空列表")
    else:
        oids = [o.get("id") for o in orders]
        if len(oids) != len(set(oids)):
            errors.append("orders.id 存在重复")
        prod_ids = {p["id"] for p in products} if isinstance(products, list) else set()
        line_ids = {l["id"] for l in lines} if isinstance(lines, list) else set()
        for o in orders:
            if not o.get("id"):
                errors.append("订单缺少 id")
            if o.get("product") not in prod_ids:
                errors.append(f"订单 {o.get('id')} product 不在 products 中: {o.get('product')}")
            try:
                if float(o.get("qty", 0)) <= 0:
                    errors.append(f"订单 {o.get('id')} qty 必须>0")
            except (TypeError, ValueError):
                errors.append(f"订单 {o.get('id')} qty 非数值: {o.get('qty')}")
            if not _parse_dt(str(o.get("due", ""))):
                errors.append(f"订单 {o.get('id')} due 格式应为 YYYY-MM-DD [HH:MM]")
            if int(o.get("priority", 2)) not in (1, 2, 3):
                errors.append(f"订单 {o.get('id')} priority 应在 1/2/3")
            al = o.get("allowed_lines")
            if al is not None and not set(al) <= line_ids:
                errors.append(f"订单 {o.get('id')} allowed_lines 含未知产线: {al}")
            if o.get("duration_min") is not None:
                try:
                    if float(o["duration_min"]) <= 0:
                        errors.append(f"订单 {o.get('id')} duration_min 必须>0")
                except (TypeError, ValueError):
                    errors.append(f"订单 {o.get('id')} duration_min 非数值")
    return errors
