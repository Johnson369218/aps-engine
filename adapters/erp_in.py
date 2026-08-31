# -*- coding: utf-8 -*-
"""示例ERP ERP 销售明细快照 → 标准订单（aps_engine 输入契约）。

管道（口径来自 aps_docs/2026年8月订单复盘与排产报告.md，已用 aug_orders_raw.json 全量复现验证）：
  1. 合并去重（billNo+goodsName+executionDate+qty）
  2. 排除退货（numberType=2）
  3. SKU 映射（sku_map.json：商品名 → SKU id）；非产成品排除 + 未映射商品列入待确认清单（不静默）
  4. 单位换算（袋→个，复盘实证：老面馒头400g/刀切馒头400g/西葫芦粉条包400g ×4，孜然牛肉包200g ×2，玉米粑粑240g ×4）
  5. 按 (SKU × 执行日) 聚合 → 订单
  6. duration_min = max(10, round(qty / capacity_8h * 480))（293/293 验证命中）
     due = 示例ERP executionDate 当天 17:00；order_time = 最早 createdTime

用法：
  .venv/bin/python aps-engine/adapters/erp_in.py \
      --raw real_aug_sep/aug_orders_raw.json --products real/products.json \
      --lines real_aug_sep/lines.json --out output/orders_from_erp.json
"""
import argparse
import json
import os
import sys
from collections import defaultdict

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(_PLUGIN_DIR)
for _p in (_PLUGIN_DIR, _WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 单位换算（袋→个）：复盘实证，防馒头按袋当个的历史错误（L3 负荷曾虚低 27%）
UNIT_CONV = {
    '老面馒头400g': 4, '刀切馒头400g': 4, '西葫芦粉条包400g': 4,
    '孜然牛肉包200g': 2, '玉米粑粑240g': 4,
}

# 非产成品排除关键词/类别（复盘：样品/原料/包装物等 17 类不排产）
EXCLUDE_NAME_KEYWORDS = ('样品', '提货卡', '盒子')  # 名称级硬排除：即使有 SKU 映射也剔除（复盘实证：酸汤汁/臊子肉/馒头样品均不排产）
EXCLUDE_CATEGORY_KEYWORDS = ('原物辅料', '工器具', '低值易耗', '外包材', '粮食加工品')


def _load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _conv_factor(name):
    for k, v in UNIT_CONV.items():
        if k in name:
            return v
    return 1


def _is_excluded(row):
    name = (row.get('goodsName') or '').strip()
    cat = (row.get('categoryName') or '').strip()
    if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
        return True
    if any(k in cat for k in EXCLUDE_CATEGORY_KEYWORDS):
        return True
    return False


def erp_to_orders(raw, products, lines, sku_map, engine_meta=None):
    """返回 (orders, stats)。stats 含漏斗与待确认清单。"""
    prod_by_id = {p['id']: p for p in products}
    line_ids = {l['id'] for l in lines}
    stats = {'raw_rows': len(raw), 'return_rows': 0, 'sales_rows': 0,
             'excluded_non_product': 0, 'unmapped': [], 'orders': 0}

    # 1) 去重
    seen = set()
    rows = []
    for r in raw:
        key = (r.get('billNo'), r.get('goodsName'), r.get('executionDate'), r.get('qty'))
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
    stats['dedup_rows'] = len(rows)

    # 2) 排除退货
    sales = [r for r in rows if r.get('numberType') != 2]
    stats['return_rows'] = len(rows) - len(sales)
    stats['sales_rows'] = len(sales)

    # 3) SKU 映射 + 排除非产成品
    acc = defaultdict(lambda: {'qty': 0.0, 'order_times': []})
    for r in sales:
        name = (r.get('goodsName') or '').strip()
        # 名称级硬排除（样品/提货卡/盒子）：即使有映射也剔除
        if any(k in name for k in EXCLUDE_NAME_KEYWORDS):
            stats['excluded_non_product'] += 1
            continue
        sku = sku_map.get(name)
        if not sku:
            # 未映射：类别级排除（原物辅料/工器具/外包材…）兜底，其余列入待确认
            if _is_excluded(r):
                stats['excluded_non_product'] += 1
                continue
            stats['unmapped'].append({
                'name': name, 'rows': 1,
                'category': r.get('categoryName', ''),
                'unit': r.get('salesUnitName', ''),
            })
            continue
        factor = _conv_factor(name)
        date = str(r.get('executionDate') or '')[:10]
        k = (sku, date)
        acc[k]['qty'] += float(r.get('qty') or 0) * factor
        ct = r.get('createdTime') or ''
        if ct:
            acc[k]['order_times'].append(ct)

    # 4) 聚合 → 订单
    orders = []
    for (sku, date), v in sorted(acc.items()):
        prod = prod_by_id.get(sku)
        if not prod:
            continue
        cap8 = prod.get('capacity_8h')
        qty = round(v['qty'], 2)
        dur = max(10, round(qty / cap8 * 480)) if cap8 else 10
        orders.append({
            'id': f"{sku}-{date.replace('-', '')}",
            'product': sku,
            'qty': qty,
            'due': f'{date} 17:00',
            'priority': 2,
            'allowed_lines': [prod['line']] if prod.get('line') in line_ids else None,
            'duration_min': dur,
            'order_time': (min(v['order_times'])[:16]) if v['order_times'] else f'{date} 08:00',
        })
    stats['orders'] = len(orders)
    stats['mapped_names'] = len(set(sku_map))
    stats['involved_skus'] = len(set(o['product'] for o in orders))
    return orders, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description='示例ERP快照 → 标准订单')
    ap.add_argument('--raw', required=True)
    ap.add_argument('--products', required=True)
    ap.add_argument('--lines', required=True)
    ap.add_argument('--sku-map', default=None, help='缺省用 aps-engine/adapters/sku_map.json')
    ap.add_argument('--out', default=None)
    args = ap.parse_args(argv)

    sku_map_path = args.sku_map or os.path.join(_PLUGIN_DIR, 'adapters/sku_map.json')
    sku_map = _load(sku_map_path)['map']
    orders, stats = erp_to_orders(_load(args.raw), _load(args.products),
                                  _load(args.lines), sku_map)

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

    print('管道漏斗: ' + ' → '.join([
        str(stats['raw_rows']),
        f"去重{stats.get('dedup_rows', stats['raw_rows'])}",
        f"销售{stats['sales_rows']}",
        f"排除非产成品{stats['excluded_non_product']}",
        f"订单{stats['orders']}",
    ]))
    if stats['unmapped']:
        print('⚠ 未映射商品（已排除，请确认是否新增 SKU）:')
        for u in stats['unmapped']:
            print(f"  - {u['name']}（{u['category']}/{u['unit']}）")
    if args.out:
        print('已写入: ' + args.out)


if __name__ == '__main__':
    main()