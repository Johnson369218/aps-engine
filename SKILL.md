---
name: aps-engine
description: 通用 APS 智能排产引擎：订单/产线/产品 JSON → 校验 → CP-SAT 两阶段排产（无 ortools 自动回退启发式）→ 6 项一致性审计 → 公式联动 Excel（21 列排产表 + 甘特图 + 汇总）；可选 AHP 优先级 / 多模型预测 / 蒙特卡洛概率。行业规则经 config/industry_example.json 适配，引擎核心不绑定企业。适用：车间排产、交期承诺、产能预演、T+N 滚动计划。
read_when:
  - 排产（"帮我排一下本周生产""这批订单怎么排""排产表""车间安排"）
  - 交期承诺 / 产能预演 / 瓶颈分析 / T+N 滚动计划
  - 需要运行排产引擎并输出排产表（orders.json → aps_engine.api.solve → 排产表.xlsx）
---

# APS Engine · 通用智能排产引擎

## 定位
**通用 APS 引擎**：输入为标准 JSON 契约（orders/lines/products），输出排产计划 + 审计 + 指标。
行业/企业特定规则（单位换算、红线、排除清单、品类敏感度）全部外置到 `config/industry_example.json`，
引擎核心不绑定任何企业。参考试点为当前参考验证场景（`adapters/` 参考集成、`tests/` 公开数据集评测）。

## 输入契约（通用）
- orders：id/product/qty/due（YYYY-MM-DD [HH:MM]）/priority(1-3)/allowed_lines(可选)/release(可选)
- lines：id/name/work_minutes_per_day/shift_start/first_date/weekends_off/capacity(并行工位)
- products：id/name/speed_per_hour 或 capacity_8h/overhead_min/setup_min(换型矩阵)

## 使用（本机）
```bash
cd aps-engine  # 仓库根目录
python tools/schedule_cli.py \
    --orders <orders.json> --lines <lines.json> --products <products.json> \
    --out output/schedule.json --xlsx "output/排产表.xlsx" [--engine auto|cp|heuristic] \
    [--priority-mode default|ahp] [--convert-units]
```

## 核心能力
1. 排产：CP-SAT（排序指派 + 换型 2-opt 精确化）；无 ortools 回退启发式
2. 审计：6 项一致性（prod_date=后工序完成日、early_days、tardy、前工序≤后工序、end≥start）
3. 优先级：AHP 六因素（交期/质量/需求/齐套/瓶颈/换型，几何均值 + CR 一致性）
4. 预测：多模型择优（星期因子/wma4/naive7/GBDT/TimesFM/集成，walk-forward 回测）
5. 概率：Bootstrap 蒙特卡洛（P10/P50/P90 + 超载概率 + 覆盖率回测）
6. 输出：**公式联动 Excel（可核查）**——明细计算列用公式（延期=MAX(0,(结束-交期)*1440)、负荷=VLOOKUP 产能联动），汇总 KPI 用 COUNTIF/SUMIF 勾稽明细，fullCalcOnLoad 打开即重算；改数量 → 负荷/延期/汇总联动
7. 服务：FastAPI（tools/serve.sh start → /api/health /api/schedule）

## 行业适配（config/industry_example.json）
单位换算、排除关键词/类别、计划系数、提前天数、食品红线——按行业/企业替换，不改引擎。

## 可靠性
- 参考试点参考回归：aps-engine/tests/test_solve.py
- 公开数据集评测：tests/eval_suite.py --quick（BPI2019/JSSP/OEE/Kaggle 等 12 场景，全绿）
- APS 标准数据集验证：aps_docs/APS数据集可靠性验证报告.md

## 研发资产
- 排产方法论：aps_docs/排产技巧学习笔记-调研报告消化.md（参考试点参考）
- 创新方法设计：aps_docs/APS插件创新方法设计.md（Pinedo 理论 × 实践）
- 可靠性/科学性：aps_docs/APS数据集可靠性验证报告.md、T+3排产的合理性与科学性说明.md
