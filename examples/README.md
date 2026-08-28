# 示例（开箱即核查）

## APS数据集-排产示例-5Sheet公式联动.xlsx
- 数据：APS 标准数据集（14 单 / 3 线 / 7 产品），非任何企业数据
- 输出：5-Sheet 公式联动（排产明细/主数据/汇总/甘特图/假设与口径）
- 核查方式：打开 → Cmd+Option+F9（重算）→ 改任意"数量"→ 负荷/延期/准时率/汇总联动
- 汇总准时率 = COUNTIF(准时,1)/COUNTA(订单)，从明细公式算出，可独立复核

## 复现
```bash
.venv/bin/python aps-engine/tools/schedule_cli.py \
    --orders data/orders.json --lines data/lines.json --products data/products.json \
    --out output/schedule.json --xlsx output/排产表.xlsx
```
