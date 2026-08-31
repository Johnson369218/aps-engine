# Phase 4 设计 · 执行达成率回填 → 假设校准闭环

> 2026-08-28 | 状态：契约设计（实现归 v0.3.0） | 关联：schema/assumptions.schema.json、export_formula.py（假设与口径 Sheet）
> 目标：把"假设声明"升级为"声明 → 执行 → 回填 → 校准 → 再冻结"的可靠性闭环，
> 使 docs/validation.md 承诺的"假设可校准"可落地、可核查、可复现。

## 1. 为什么需要

当前假设管理止步于声明：
- `assumptions.json`（H1-Hn + source + status）→ 冻结 → 排产 → 输出"假设与口径"Sheet
- **缺最后一环**：执行期结束后，实际达成率没有回填，假设永远停在"待校准"。
- 结论可靠性因此只覆盖"排产时点"，不覆盖"执行后验证"。

## 2. 数据流

```
排产结果 result (schedule)         实际执行 actuals (订单→实际完成/实际产量)
        │                                  │
        └──────────────┬───────────────────┘
                       ▼
          aps_engine/calibration.py::backfill(result, actuals, assumptions)
                       │
          ┌────────────┼──────────────────────┐
          ▼            ▼                      ▼
  assumptions.calibrated.json    校准报告-<期间>.md     假设与口径Sheet（校准状态列）
  （状态机迁移）                （偏差/建议/证据）       （回填结果联动展示）
```

## 3. 契约

### 3.1 输入：actuals（实际执行数据，标准 JSON）

```json
{
  "period": "2026-09",
  "source": "erp|手工录入|看板",
  "actuals": [
    {
      "order": "O-101",
      "actual_end": "2026-09-02 16:30",
      "actual_qty": 9800,
      "actual_setup_min": 45
    }
  ]
}
```

字段说明：
- `order`：与排产 result.schedule[].tasks[].order 一一对应（主键）
- `actual_end`：实际完成时间；缺失则该单标记"未回填"
- `actual_qty`：实际产量（用于负荷/效率假设校准）
- `actual_setup_min`：实际换型时长（用于换型矩阵假设校准）

### 3.2 输出：校准记录（每假设一条）

```json
{
  "period": "2026-09",
  "generated_at": "2026-09-30 18:00",
  "engine_version": "0.3.0",
  "input_snapshot": "sha256:排产结果文件hash",
  "items": [
    {
      "hypothesis_id": "H1",
      "item": "产线建模（13线按产品族）",
      "predicted": {"value": "13线", "basis": "建模假设"},
      "actual": {"observed": "12线有效", "n_orders": 293},
      "deviation_pct": 7.7,
      "status_before": "待校准",
      "status_after": "已修正",
      "suggestion": "将 H1 取值改为 12 线并按瓶颈池合并建模",
      "evidence": ["O-101..O-105 在 L4 排队", "L6 全程空转（0.7% 利用率）"]
    }
  ]
}
```

### 3.3 假设状态机

```
待确认 ──用户冻结──▶ 待实测 ──执行回填──▶ 已校准（|偏差| < 阈值）
                        │                  │
                        │                  └──▶ 已修正（|偏差| ≥ 阈值，附建议值）
                        └──无实际数据──▶ 保持待实测（标注"缺数据"）
```

- 阈值（默认 `deviation_threshold_pct = 10`）由 config 驱动，可调
- **≥10% 偏差的假设禁止静默通过**：必须产出"已修正"+ 建议值，否则校准报告不通过校验

### 3.4 schema 扩展（向后兼容）

`schema/assumptions.schema.json` 的 `calibration` 对象扩展（新增字段，旧文件仍可读）：

```json
{
  "calibration": {
    "input_snapshot": "string",
    "engine_version": "string",
    "config_version": "string",
    "seed": 42,
    "history": [
      {"period": "2026-09", "deviation_pct": 7.7, "status_after": "已修正", "suggestion": "..."}
    ]
  }
}
```

## 4. 校准项映射（哪些假设可被实际数据校准）

| 假设类别 | 示例假设 | 回填字段 | 计算方式 |
|---|---|---|---|
| 产线产能 | 13 线按产品族建模 | actual_end / actual_qty | 实际节拍 vs 建模节拍 |
| 换型矩阵 | 换型 80min 均值 | actual_setup_min | 实际换型 vs 矩阵值 |
| 班次/工时 | 2 班 × 8h | actual_end 分布 | 实际完工时刻 vs 班次窗口 |
| 计划系数 | 0.88 达成率 | 准时单数/总单数 | 实际准时率 vs 0.88 |
| 提前期 | T+1 交期 | actual_end vs due | 实际提前/延后天数 |

## 5. 验收标准（v0.3.0 完成定义）

- [ ] `calibration.backfill` 对公开语料合成的假 actuals（±5%）正确迁移假设状态
- [ ] ≥10% 偏差假设必须产生"已修正"+ 建议值（负例测试：禁止静默通过）
- [ ] 校准记录可追溯：input_snapshot + engine_version + period 三者齐全
- [ ] 校准后 `export_formula_xlsx(assumptions=calibrated)` 输出的"假设与口径"Sheet 含校准状态列
- [ ] 扩展后 assumptions.schema.json 通过 json-schema 校验（旧快照向后兼容）
- [ ] 新增 2 个公开语料场景：`calibration_basic`（正常校准）、`calibration_overrun`（超限必须修正）

## 6. 非目标（v0.3.0 不做）

- 自动改写引擎参数（只给建议值，人确认后改）
- 实时在线校准（只做期间批次回填，如月/周）
- 预测模型重训（预测校准走 forecast 模块自己的回测）
