# APS Engine 输出契约 v1.0

## 交付三件套（每次排产必出）
1. **排产表.xlsx**：5-Sheet 公式联动（可核查）——缺任一 Sheet 不算交付
2. **schedule.json**：引擎完整结果（engine/generated_at/summary/tardy_orders/schedule）
3. **assumptions.json**：假设快照（H 清单 + 来源 + 校准状态 + 敏感度）

## Excel 5-Sheet 模板
| Sheet | 内容 | 可核查公式 |
|---|---|---|
| 排产明细 | 产线/订单/产品/数量/交期/开始/结束/生产日期 | 延期=MAX(0,(结束-交期)*1440)、负荷=ROUND(数量/VLOOKUP(产能)*8,2)、准时=IF(延期=0,1,0) |
| 主数据 | 产品 ID/名称/单位/8h 产能 | VLOOKUP 源 |
| 汇总 | 准时数/准时率/总延期/每线汇总 | COUNTIF/SUMIF 勾稽明细 |
| 甘特图 | 产线×日期 负荷矩阵 | SUMIFS + 条件格式 |
| 假设与口径 | H1-Hn 清单+来源+校准状态+敏感度 | 结论绑定假设 |

## schedule.json 结构
{"engine": "cp|heuristic", "generated_at": "...", "seed": 42,
 "summary": {orders,on_time,tardy,on_time_rate,total_tardiness_min,max_tardiness_min,total_setup_min,utilization,bottlenecks},
 "tardy_orders": [...], "schedule": [{line,line_name,tasks:[{order,product,product_name,qty,start,end,prod_date,due,tardy_min,early_days}]}],
 "audit": {ok,tasks,issues}}

## 勾稽规则（生成器自动断言）
- 汇总.准时数 == COUNTIF(明细.准时,1)
- 汇总.总延期 == SUM(明细.延期)
- 汇总.准时率 == 准时数/总订单数
- 每线任务数 == COUNTIF(明细.产线)
