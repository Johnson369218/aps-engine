# APS Engine · 通用智能排产引擎

> **定位**：通用 APS（高级计划排产）引擎，不绑定任何企业。订单从「任意通道」进来（会话/微信/钉钉/企微/飞书/ERP），
> 排产后以「JSON + Excel + 简报 + 看板」按角色送达（老板看日报、车间看班前单、看板看全局）。
> 参考试点（岐品福）只是**一个**场景，仅用于可靠性检验与参考集成。

## 能力
- **排产**：CP-SAT 两阶段（排序指派 + 换型 2-opt 精确化）；无 ortools 自动回退启发式
- **可复现**：`seed=42` 默认固定，同输入同 seed 任务序列逐字节一致（B1）
- **基线回放**：AI 方案 vs 规则基线（EDD/SPT/…）对照报告（C3）
- **副驾**：`--compare` heuristic 快排 vs CP 精排，给出推荐 + 理由（C1）
- **闭环**：SQLite 台账 → 事件流 → 报工 → 执行校准 → 触发矩阵 → 真实重排（变更清单 + 冻结区 0 变动）
- **多通道网关**：Message 协议 + 角色权限（`owner/planner/operator/…`），入口通道无关
- **真实推送**：钉钉（加签）/ 企业微信 / 飞书 / 微信（dsh-im 桥）机器人 webhook
- **设备直连**：Modbus TCP（信捷/汇川/台达 PLC）/ REST / 作业单，排产结果直发设备（先确认再下发）
- **输出三件套**：员工一句话 / 车间班前单摘要 / 老板日报（≤N 行人话）
- **审计**：6 项一致性（入库=后工序完成日、提前天数、延期、前后工序衔接）
- **优先级**：AHP 六因素；**预测**：多模型择优；**概率**：蒙特卡洛 P10/P50/P90
- **输出**：**5-Sheet 公式联动 Excel**（排产明细/主数据/汇总/甘特图/假设与口径，可核查）
- **服务**：FastAPI（`POST /api/schedule`）

## 快速使用

### 1) 排产（一条命令）
```bash
cd aps-engine
python tools/schedule_cli.py \
    --orders data/orders.json --lines data/lines.json --products data/products.json \
    --out output/schedule.json --xlsx "output/排产表.xlsx" \
    --engine auto --seed 42            # 可复现
python tools/schedule_cli.py ... --compare   # 副驾：快排 vs CP 精排 + 推荐
```
或 pip 安装：`pip install .` 后 `import aps_engine.api; aps_engine.api.solve(...)`。

### 2) 闭环（报工 → 台账 → 急单 → 重排 → 变更清单）
```bash
# 报工（一句话回填，袋→个防呆）
python tools/report_back.py --db data/ledger/aps_ledger.db --order O-001 --qty 1000 --unit 袋 --factor 4 --by 班组长
# 急单事件 → 台账 → 触发 → 真实重排 → 变更清单（what-if 建议，拍板在人）
python tools/replan_cli.py \
    --plan output/schedule.json --lines data/lines.json --products data/products.json \
    --rush '{"id":"RUSH-001","product":"SKU001","qty":200,"due":"2026-08-02 12:00","priority":1,"allowed_lines":["L1"]}' \
    --freeze-before "2026-08-01 18:00" --db data/ledger/aps_ledger.db --out output/replan.json
```

### 3) 多通道推送（简报 → 钉钉/企微/飞书/微信）
```bash
# ① 复制模板并填真实 webhook（密钥不入库）
cp data/channels.example.json data/channels.json   # 编辑填 access_token/key
# ② 推送
python tools/push_cli.py --channels data/channels.json --text "排产简报：293 单，准时率 100%"
# ③ 角色权限（operator 不可重排，owner 万能）见 data/actors.json
```

### 4) 台账备份
```bash
bash scripts/backup_ledger.sh     # data/ledger/*.db → data/backup/（滚动保留 7 份）
```

### 5) 设备直连（印刷/卷材等自动化设备）
```bash
# ① 复制模板填设备 IP/寄存器（machines.json 已 gitignore）
cp data/machines.example.json data/machines.json
# ② 默认 dry-run 只预览指令（红线：先人工确认）
python tools/machine_push.py --schedule output/schedule.json \
    --machines data/machines.json --machine flexo1 --products data/products.json
# ③ 确认无误后再真写（--confirm）
python tools/machine_push.py ... --confirm
```
支持 Modbus TCP（信捷/汇川/台达/西门子 PLC）、REST（IoT 网关）、作业单（无网口老设备→机台终端/大屏）。

## 目录
```
aps-engine/
├── aps_engine/
│   ├── api.py            # solve() 主入口（seed/mode 新参数默认关）
│   ├── scheduler.py      # CP-SAT + 启发式 + 瓶颈分解 solve_decomposed
│   ├── ledger.py         # SQLite 台账（订单/执行/事件/调整日志）
│   ├── calibration.py    # 执行校准（±5%/≥10% 状态机）
│   ├── trigger.py        # 触发矩阵（6 类 + 冻结区校验）
│   ├── replan.py         # 真实重排（冻结锁定 + 最小扰动 + 变更清单）
│   ├── channels.py       # 多通道消息网关 + 角色权限
│   ├── webhooks.py       # 真实推送（钉钉加签/企微/飞书/微信 dsh-im）
│   ├── machine.py        # 设备直连（Modbus TCP/REST/作业单，先确认再下发）
│   ├── briefing.py       # 输出三件套（员工/车间/老板）
│   ├── audit.py schema.py summarize.py export.py export_t3_xlsx.py
│   ├── ahp.py forecast.py prediction.py monte_carlo.py timesfm_service.py
│   └── server/           # FastAPI
├── config/industry_example.json   # 行业适配示例（换行业复制替换）
├── data/
│   ├── actors.json       # 通道用户 → 角色映射（权限）
│   └── channels.example.json      # 通道 webhook 模板（真实密钥填 channels.json，已 gitignore）
├── adapters/             # erp_in（ERP 快照）、kanban_out（A/B 双看板上板）
├── tools/                # schedule_cli / replay_baseline / ledger_cli / report_back / replan_cli / push_cli / channel_cli / replay_rules / serve.sh
├── scripts/backup_ledger.sh
├── tests/                # 13 个测试（assert+__main__ 风格，无 pytest）
└── docs/                 # ROADMAP / design-phase2..5-contract / validation
```

## 仓库
GitHub: https://github.com/Johnson369218/aps-engine

## 增强路线图
v0.3.0 信任+闭环+入口 ✅（本版）→ v0.4.0 降本增强（批次合并 + LST 保质期约束）→ v0.5.0 规模化（瓶颈分解/概率约束/规则回放），详见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 命名规范
| 项 | 值 |
|---|---|
| skill/插件名 | `aps-engine` |
| Python 包 | `aps_engine` |
| 版本 | 0.3.0 |
| 许可证 | MIT |
| 入口 | `aps_engine.api.solve`（稳定 API） |

## 验证声明（结论可靠性依据）

**本插件未使用、未上传任何客户数据**。验证基于公开数据集与合成语料（BPI2019/JSSP/Kaggle/灌装线等 12 场景全绿 + APS 标准数据集），详见 [docs/validation.md](docs/validation.md)。客户场景仅在本地运行，数据不出厂；通道 webhook 密钥不入库。

## 可靠性（三层背书）
1. APS 标准数据集（data/）：aps_docs/APS数据集可靠性验证报告.md
2. 公开数据集评测（12 场景）：`tests/eval_suite.py --quick`
3. 参考试点回归（仅本地，需客户数据）：`tests/test_solve.py`

## 方法论资产
- [docs/validation.md](docs/validation.md)（验证声明：零客户数据 + 公开数据集证据链）
- T+3 排产：蒙特卡洛 + 覆盖率回测（见 docs/validation.md 四、边界声明）
- 多模型预测择优：TimesFM/GBDT/wma4/naive7（walk-forward 回测择优）
