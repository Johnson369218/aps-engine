# 阶段 2 · 信任与协同 输出扩展契约（冻结）

> 依据《APS 插件技术改进路线》阶段 2（B1 可复现 / C3 基线回放 / C1 副驾 v1）。
> 红线：不改 `solve()` 的 5-Sheet 输出契约与 audit 6 项语义；新行为全部走**新参数，默认关闭**；
> 不引入客户数据进仓库；拍板权在人（副驾只出建议）。

---

## 1. 可复现契约（B1）

- `aps_engine/api.py::solve(...)` 新增参数 `seed: int = 42`（默认固定），透传至引擎。
- `aps_engine/scheduler.py::run(...)` / `solve_cp(...)` / `solve_heuristic(...)` 新增 `seed: int = 42`。
  - `solve_cp`：`solver.parameters.random_seed = seed`，且为保证「同 seed → 结果逐字节一致」，
    固定 `num_search_workers = 1`（多 worker 并行即使固定 seed 也不确定）。
  - `solve_heuristic`：接受 `seed`，排序/并列打破逻辑用 `random.Random(seed)`（当前启发式为确定性排序，seed 为兼容占位）。
- CLI：`tools/schedule_cli.py` 新增 `--seed`（`type=int, default=42`），并传入 `solve(seed=args.seed)`。

**契约定义**：同输入（orders/lines/products 文件内容一致）、同 `engine`、同 `seed`、同 `time_limit` →
两次运行产出的 `schedule` 任务序列（按 `line` + `order` + `start` + `end` 元组）**完全一致**。

---

## 2. 基线回放契约（C3）

`tools/replay_baseline.py`：

- **输入**：AI 结果 `schedule.json`（引擎任意，含 `summary`/`schedule` 顶层键）
  + 基线规则名（`priority_edd | edd | spt | wspt | cr`，`--baseline`，默认 `priority_edd`）。
- **输出**：`output/baseline_<日期>.md` 对比表：

  | 方案 | 准时率 | 总延期分 | 换型分 | 瓶颈 |
  |---|---|---|---|---|
  | AI 引擎 | ... | ... | ... | ... |
  | 基线 <规则> | ... | ... | ... | ... |

- **口径**：KPI 取自 `result["summary"]` 的 `on_time_rate` / `total_tardiness_min` /
  `total_setup_min` / `bottlenecks`。v1 基线 = 内置启发式（EDD 优先 + 负载均衡 + 换型 2-opt）；
  `--baseline` 仅作规则标签记录，多规则独立回放择优属 ROADMAP v0.5「规则回放」扩展。
- **性质**：基线报告只作参照，不改变正式排产；采纳需计划员判断（拍板在人）。

---

## 3. 副驾 v1 契约（C1）

`tools/schedule_cli.py` 新增 `--compare`（`action="store_true"`，**默认关闭**）：

- 跑两版：heuristic 快排（`time_limit=3`）与 cp 精排（`time_limit=--time-limit`），
  均透传 `convert_units` 与 `seed`。
- 输出对比块：

  ```
  === 副驾对比 ===
    CP 精排   : 准时率 ..% 延期 .. 换型 ..
    快排(基线): 准时率 ..% 延期 .. 换型 ..
    推荐: <CP 精排 | 快排基线>（<一行理由，引用差异字段>）
  ```

- **推荐次序**：准时率 → 换型。规则：
  1. `CP 准时率 ≥ 快排准时率` 且 `CP 换型 ≤ 快排换型` → 推荐 CP 精排（准时率不低且换型不增）；
  2. 否则 `CP 准时率 > 快排准时率` → 推荐 CP 精排（准时率更高，换型代价 +N 分）；
  3. 否则 → 推荐快排基线（换型/负荷更优，建议人工确认瓶颈线）。

---

## 4. 验收清单

| 项 | 命令 | 期望 |
|---|---|---|
| B1 单元 | `.venv/bin/python aps-engine/tests/test_reproducible.py` | `PASS 同 seed 可复现` + `PASS 不同 seed 可运行` + `ALL PASS` |
| B1 端到端 | CLI 两次 `--seed 42` 输出 s1.json/s2.json 后 diff 任务序列 | `CLI 可复现 OK: <N> 任务` |
| C3 | `.venv/bin/python aps-engine/tools/replay_baseline.py ... --baseline priority_edd --out ...` | `head -6` 表头含 `AI 引擎` 与 `基线 priority_edd` 两行 |
| C1 | CLI `--engine cp --time-limit 8 --compare` | 输出含 `=== 副驾对比 ===`、两方案行、`推荐:` 行 |
| 回归 | `.venv/bin/python aps-engine/tests/test_solve.py` | `✅ 回归通过`（硬不变量 + 容忍区间） |

阶段 2 退出标准：同输入同 seed 两次运行任务序列一致（B1）+ 基线回放报告可产出（C3）+
副驾对比含推荐理由（C1）+ 契约文档提交、回归全绿、分支可合并（Task 0/4）。
