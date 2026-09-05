# Changelog

## [0.3.0] - 2026-09-06（信任协同 + 闭环数据 + 入口规模化）

### 阶段 2 · 信任与协同（人敢拍板）
- B1 求解可复现：`seed=42` 默认固定（`solve/schedule_cli --seed`），同输入同 seed 任务序列逐字节一致
- C3 基线回放：`tools/replay_baseline.py`（AI vs 规则基线对照报告）
- C1 副驾 v1：`schedule_cli --compare`（heuristic 快排 vs CP 精排 + 推荐理由）

### 阶段 3 · 闭环与数据底座（闭环转起来）
- D1 SQLite 台账 `aps_engine/ledger.py`（orders/execution/events/adjust_log，migrate 幂等）
- D2 事件入口 `tools/ledger_cli.py`；D3 报工 `tools/report_back.py`（单位换算防呆）
- B3 执行校准 `aps_engine/calibration.py`（±5%/≥10% 状态机 + 执行回填，建议需审批）
- B4 触发矩阵 `aps_engine/trigger.py`（6 类触发 + 冻结区 0 变动）
- 真实重排 `aps_engine/replan.py`（冻结锁定 + 受影响线最小扰动 + 变更清单）+ `tools/replan_cli.py` 闭环

### 阶段 5 · 入口与规模化（可复制、可交付）
- E1 多通道消息网关 `aps_engine/channels.py`（Message 协议 + 角色权限）+ 真实推送 `aps_engine/webhooks.py`（钉钉加签/企微/飞书/微信 dsh-im）+ `tools/push_cli.py`
- E2 输出三件套 `aps_engine/briefing.py`（员工/车间/老板 + 降级标注）
- E4 韧性 `scripts/backup_ledger.sh`（台账滚动备份 7 份）
- B6 瓶颈分解 `solve(mode="decompose")`（瓶颈线 CP、其余启发式）+ `tools/replay_rules.py`（规则回放推荐走审批）

### 红线守约
- `solve()` 默认语义、5-Sheet 契约、audit 6 项不变；新功能均新参数/新模块、默认关闭
- 通道 webhook 密钥 `data/channels.json` 已 gitignore（模板 `data/channels.example.json`）
- 验证只用公开语料与合成语料（12 场景全绿 + 全量测试 ALL PASS）

## [0.2.1] - 2026-08-28（架构 V2 修复）
### 上架准备（发布前）
- 零客户数据红线：客户文件 gitignore 修复（行尾注释曾致忽略失效）、全仓库客户名匿名化、docs/validation.md 验证声明
- 兼容性修复：8 处 Python 3.12 PEP701 f-string 改 3.11 兼容（CI 双版本可跑）
- 配置兜底：industry_food.json（客户本地）缺失时自动回退 config/industry_example.json（仓库示例）
- 失效引用修正：aps_training/ → tests/、本机绝对路径 → 仓库相对、版本号统一 0.2.1（plugin.yaml/pyproject/__init__/server）
- CI：tests/test_public_data.py 冒烟 + eval_suite 12 场景 + tag v* 自动 GitHub Release
### 修复（复盘缺陷）
- 输出契约升级为 5-Sheet 公式联动（排产明细/主数据/汇总/甘特图/假设与口径），缺任一 Sheet 不算交付
- 新增假设管理：assumptions.json + 敏感度 + "假设与口径"Sheet（结论绑定假设）
- 新增契约冻结：schema/input.schema.json、output.contract.md、assumptions.schema.json
- 客户试点排产（本地验证，数据不出厂）：全量窗口/拆批/19 线/热启动/公式可核查（准时率 39.3%→79.8%）

## [0.2.0] - 2026-08-27
- 通用化命名：aps-engine / aps_engine；配置外置 config/industry_food.json
- 引擎修复：启发式重复任务、前工序产能兜底、多工位字段/延期口径、util 双 bug
- 能力：AHP、多模型预测（TimesFM/GBDT）、蒙特卡洛、热启动、公开数据集 12/12

## [0.1.0] - 2026-08-26
- 初版：CP-SAT 两阶段排产 + 审计 6 项 + 21 列排产表 + 双看板上板
