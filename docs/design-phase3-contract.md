# 阶段 3 · 闭环与数据底座 契约（冻结）

> 依据《APS 插件技术改进路线》阶段 3（D1 台账 / D2 事件入口 / D3 报工 / B3 校准 / B4 触发）。
> 红线：schema 只 ADD COLUMN/新增表；台账文件放 DSH 本机工作区 `data/ledger/`（数据不出厂）；
> 校准/触发产出均为「建议/报告」，不自动改排产参数（拍板在人 + pending_replay 纪律）；
> 验证用公开语料与合成事件；不动 v0.2.1 `solve()` 语义与 5-Sheet 契约。

---

## 1. 台账表（D1，`data/ledger/aps_ledger.db`，sqlite3 stdlib）

- `orders(id, order_code UNIQUE, product, qty, due, priority, source_system DEFAULT 'chat', source_ref, status DEFAULT 'open', frozen INTEGER DEFAULT 0, created_at)`
- `execution(id, order_code, plan_date, actual_start, actual_end, qty_done, wait_reason, exception_reason, reported_by, created_at)`
- `events(id, event_type, payload_json, created_at)` —— `event_type ∈ {shortage, breakdown, rush_order, deviation}`（另含生命周期 `completion`，由报工产生）
- `adjust_log(id, order_code, field, old_value, new_value, reason, decided_by, created_at)`（阶段 4 复用）

**迁移规则**：`ledger.py::init_db(path)` 幂等（CREATE IF NOT EXISTS）；`ledger.py::migrate(path)` 幂等，
新增列走 `_MIGRATIONS` 里的 `ALTER TABLE ... ADD COLUMN`，**禁止 DROP**。

---

## 2. 事件协议（D2）

- 入口 `ledger.emit_event(db, event_type, payload)`（即 `emit(type, payload)` 协议：事件流落地到 `events` 表）。
- `payload` 必含 `ts`，可选 `{order_code?, line?, qty?, due?}`；以 JSON 存 `payload_json`。
- 事件 CLI：`tools/ledger_cli.py`（`init` / `event` / `orders` / `events` 子命令）。

**触发矩阵 6 类 → 事件类型 → 范围**：

| 触发类 | 事件类型 | 范围 |
|---|---|---|
| 周期 | `period` | rolling（滚动区重排，冻结区不动）|
| 缺料 | `shortage` | local |
| 停机 | `breakdown` | local |
| 急单 | `rush_order` | local |
| 连续偏差 | `deviation` | full |
| 目标变动 | `target_change` | full |

---

## 3. 校准契约（B3）

`calibration.backfill(result, actuals, assumptions, thresholds=(0.05, 0.10)) -> (records, summary)`

- `actuals: {H_key: actual_value}`；`assumptions` 形如 `{"assumptions": {H_key: {"value": ..., "status": ...}}}`。
- 每条 `records` 记录：`{key, predicted, actual, delta_pct, status, action: keep|calibrate|correct, suggestion?, note?}`。
- **状态机**：`|delta| < 5%` → `已校准`（action=keep）；`≥ 10%` → `已修正`（action=correct，`suggestion=actual`）；
  `5%–10%` → `待实测`（action=keep，继续积累样本）。
- 输出 `assumptions.calibrated.json` + `校准报告-<期间>.md`（`calibration.write_report`）。
- **审批红线**：修正建议须人工审批后写入配置（`apply_corrections` 仅由审批流程调用），报告不改任何排产参数。

---

## 4. 触发契约（B4）

`trigger.evaluate_triggers(plan_before, events, kpis, config) -> TriggerReport`

- `plan_before: {"tasks": [{order_code, line, start_min, end_min, frozen}]}`；`events: [{type, ...}]`。
- `TriggerReport = {triggered, reasons[], scope: none|local|full|rolling, change_list[{order_code, line, before_min, after_min, frozen}], frozen_touched}`。
- 范围合并：任一类触发 `full` → `full`；否则 `rush_order/shortage/breakdown` → `local`；`period` → `rolling`。
- **冻结区 0 变动**：`change_list` 仅含非冻结任务；`frozen_touched` 恒为 0。
- 真实重排由 `replan` 执行后 `diff` 生成变更清单（见 §4.1）。

### 4.1 真实重排契约（replan，闭环落地）

`replan.replan(plan_before, new_orders, lines, products, freeze_before=None, frozen_set=None)`

- `plan_before`：现有排产 result（schedule.json）；`new_orders`：急单等引擎订单（id/product/qty/due/priority/allowed_lines）。
- 返回 `{engine, generated_at, freeze_before, affected_lines, summary, schedule, change_list, frozen_touched}`。
- **两阶段最小扰动**：
  1. 阶段一「插入即得」：新订单塞进现有空隙（不搬动任何滚动任务），全部赶上交期 → `change_list` 只含 `added`；
  2. 阶段二「真实重排」：塞不下才重排受影响线（新订单 `allowed_lines` 交集）的滚动任务 + 新订单，
     交期优先、换型增量最小、latest-fit（贴交期当天生产，避免虚假提前）。
- 未受影响线的滚动任务保持原位（0 扰动）；冻结区任务逐分钟不变（`frozen_touched=0`）。
- 闭环 CLI：`tools/replan_cli.py`（`--plan/--rush/--freeze-before/--db/--out`），
  落台账事实（订单 + `rush_order` 事件）→ `trigger.evaluate_triggers` → `replan.replan` → 变更清单；
  输出为建议，待审批（拍板在人）。

---

## 5. 验收清单

| 项 | 命令 | 期望 |
|---|---|---|
| D1 | `.venv/bin/python aps-engine/tests/test_ledger.py` | 3 PASS + `ALL PASS` |
| D2 | `ledger_cli.py init/event/events` | 事件入库可查（含 `rush_order` 一行）|
| D3 | `.venv/bin/python aps-engine/tests/test_report_back.py` | 2 PASS + `ALL PASS`（单位换算防呆）|
| B3 | `.venv/bin/python aps-engine/tests/test_calibration.py` | 3 PASS + `ALL PASS`（±5%/≥10% + 审批提示）|
| B4 | `.venv/bin/python aps-engine/tests/test_trigger.py` | 3 PASS + `ALL PASS`（6 类触发 + 冻结区 0 变动）|
| 重排 | `.venv/bin/python aps-engine/tests/test_replan.py` | 2 PASS + `ALL PASS`（冻结锁定 + 急单插入 + 真实变更清单）|
| 闭环 | `.venv/bin/python aps-engine/tests/test_closed_loop.py` | 报工→台账→触发→重排→校准 全绿 |

阶段 3 退出标准：台账 init/迁移幂等、订单/执行/事件落库（D1）+ 事件 CLI 入库可查（D2）+
报工一句话回填 + 单位换算防呆（D3）+ 校准状态机 ±5%/≥10% 正确迁移且报告含审批提示（B3）+
一次急单事件端到端产出 TriggerReport + 变更清单、冻结区 0 变动（B4/端到端）。
