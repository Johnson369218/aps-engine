# -*- coding: utf-8 -*-
"""aps_engine 主入口：solve() 包装 scheduler.run()，内置调研报告口径。

口径（来自 aps_docs/排产技巧学习笔记-调研报告消化.md）：
- 8h 计划产能 = 工程产能 × 0.88（计划系数）；products 缺 capacity_8h 时用 speed_per_hour×8 兜底
- 单位换算：老面馒头400g/刀切馒头400g/西葫芦粉条包400g ×4、孜然牛肉包200g ×2、玉米粑粑240g ×4（袋→个）
- 入库日期 = 后工序完成日（引擎 prod_date 已固化）；audit 6 项一致性必跑
- T-1 生产：交期 D 的订单按 D-1 生成班前执行单（lead_days=1，业务口径，不强行改排程）
"""
import json
import os
import sys
from datetime import datetime

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # aps-engine/
_WORKSPACE = os.path.dirname(_PLUGIN_DIR)                                    # 生产调度/
for _p in (_PLUGIN_DIR, _WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import aps_engine.scheduler as scheduler  # noqa: E402
from aps_engine.audit import audit_result  # noqa: E402
from aps_engine.export import export_schedule_xlsx  # noqa: E402
from aps_engine.schema import validate_inputs, ValidationError  # noqa: E402
from aps_engine.summarize import a_report_inbox, b_kanban_block  # noqa: E402

# ── 行业适配配置（引擎核心不内置行业假设）──
# 优先级：本地客户配置 industry_food.json > 仓库示例 industry_example.json > 内置默认
CONFIG = {}
for _cfg_name in ("industry_food.json", "industry_example.json"):
    _cfg_path = os.path.join(_PLUGIN_DIR, "config", _cfg_name)
    if os.path.exists(_cfg_path):
        with open(_cfg_path, encoding="utf-8") as _f:
            CONFIG = json.load(_f)
        break
UNIT_CONVERSIONS = CONFIG.get("unit_conversions") or {}   # 行业配置驱动，不内嵌客户品名
PLAN_COEFFICIENT = CONFIG.get("plan_coefficient", 0.88)
LEAD_DAYS = CONFIG.get("lead_days", 1)


def normalize_orders(orders, products, convert_units=False):
    """订单归一化：
    - convert_units=True 时按产品名做袋→个换算（返回换算说明）
    - 补齐 allowed_lines 缺省、priority 缺省
    """
    notes = []
    prod_by_name = {}
    if isinstance(products, list):
        prod_by_name = {p.get("name", ""): p for p in products}
    out = []
    for o in orders:
        oo = dict(o)
        name = oo.get("product_name") or ""
        prod = None
        for key, fac in UNIT_CONVERSIONS.items():
            if key in name or any(key in str(p.get("name", "")) for p in products
                                  if p.get("id") == oo.get("product")):
                if convert_units:
                    oo["qty"] = round(float(oo.get("qty", 0)) * fac, 2)
                    notes.append(f"{oo.get('id')}: {key} 袋→个 ×{fac}")
                break
        oo.setdefault("priority", 2)
        out.append(oo)
    return out, notes


def solve(orders, lines, products, engine="auto", time_limit=20,
          convert_units=False, out_path=None, xlsx_path=None,
          products_raw=None, run_audit=True, priority_mode="default", seed=42):
    """一键排产：校验 → 归一化 → 引擎 → 审计 → 落盘。返回 result dict。

    out_path/xlsx_path 为 None 时不写盘；products_raw 用于 21 列导出（品类/单价/产能）。
    """
    errors = validate_inputs(orders, lines, products)
    if errors:
        raise ValidationError("输入校验未通过：\n" + "\n".join(errors[:20]))

    orders_n, notes = normalize_orders(orders, products, convert_units=convert_units)
    ahp_stats = None
    if priority_mode == "ahp":
        from aps_engine.ahp import apply_ahp_priorities
        # 线负荷用上一次排产结果太绕：先用默认排产一次拿 utilization，再 AHP 打分重排
        pre = scheduler.run(orders_n, lines, products, engine=engine,
                            time_limit=min(time_limit, 15), seed=seed)
        orders_n, ahp_stats = apply_ahp_priorities(orders_n, products,
                                                   line_util=pre["summary"]["utilization"])
    result = scheduler.run(orders_n, lines, products, engine=engine,
                           time_limit=time_limit, seed=seed)

    if run_audit:
        n, issues = audit_result(result)
        if issues:
            result["audit"] = {"ok": False, "tasks": n, "issues": issues[:20]}
            raise AssertionError(
                f"排产审计未通过（{len(issues)} 项）：\n" + "\n".join(issues[:10]))
        result["audit"] = {"ok": True, "tasks": n, "issues": 0}

    result["notes"] = notes
    if ahp_stats:
        result["ahp"] = ahp_stats
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    if xlsx_path:
        os.makedirs(os.path.dirname(os.path.abspath(xlsx_path)), exist_ok=True)
        export_schedule_xlsx(result, xlsx_path, products_raw or products)
    return result
