# APS Engine · 通用智能排产引擎

> **定位**：通用 APS（高级计划排产）引擎，不绑定任何企业。参考试点为当前**参考验证场景**，
> 仅用于可靠性检验与参考集成（见 adapters/ 与 aps_training/）。

## 能力
- **排产**：CP-SAT 两阶段（排序指派 + 换型 2-opt 精确化）；无 ortools 自动回退启发式
- **审计**：6 项一致性（入库=后工序完成日、提前天数、延期、前后工序衔接）
- **优先级**：AHP 六因素（几何均值 + CR 一致性）
- **预测**：多模型择优（星期因子/wma4/naive7/GBDT/TimesFM/集成，walk-forward 回测）
- **概率**：Bootstrap 蒙特卡洛（P10/P50/P90 + 超载概率 + 覆盖率回测）
- **输出**：**5-Sheet 公式联动 Excel**（排产明细/主数据/汇总/甘特图/假设与口径，可核查，打开即重算）
- **服务**：FastAPI（tools/serve.sh start）

## 目录
```
aps-engine/
├── plugin.yaml          # 插件清单（上架元数据）
├── SKILL.md             # 通用技能文档
├── pyproject.toml       # 可安装包（name=aps-engine）
├── aps_engine/          # 引擎核心包（通用，无企业假设）
│   ├── api.py           # solve() 主入口
│   ├── audit.py schema.py summarize.py export.py export_t3_xlsx.py
│   ├── ahp.py           # AHP 优先级
│   ├── forecast.py prediction.py monte_carlo.py timesfm_service.py
│   └── server/          # FastAPI
├── config/
│   └── industry_food.json   # 行业适配（食品参考配置；换企业/行业替换此文件）
├── adapters/            # 集成适配器（erp_in 通用快照；kanban_out 参考试点看板参考）
├── tools/               # schedule_cli.py / serve.sh
├── tests/               # 回归（参考试点参考场景 + APS 标准数据集）
└── docs/                # 设计/方法论文档（见 aps_docs/）
```

## 仓库
GitHub: https://github.com/Johnson369218/aps-engine

## 快速使用
```bash
cd ~/Desktop/生产调度
.venv/bin/python aps-engine/tools/schedule_cli.py \
    --orders data/orders.json --lines data/lines.json --products data/products.json \
    --out output/schedule.json --xlsx "output/排产表.xlsx" [--engine auto|cp|heuristic]
```

## 命名规范（上架准备）
| 项 | 值 | 说明 |
|---|---|---|
| skill/插件名 | `aps-engine` | kebab-case，可上架 |
| Python 包 | `aps_engine` | PEP 8 包名 |
| 展示名 | APS Engine · 智能排产引擎 | 中文展示名可调 |
| 版本 | 0.2.0 | semver |
| 许可证 | MIT | 可调 |
| 作者 | Johnson369218（kwoko_china@126.com） | 已定 |
| 入口 | aps_engine.api.solve | 稳定 API |

## 验证声明（结论可靠性依据）

**本插件未使用、未上传任何客户数据**。验证基于公开数据集与合成语料（BPI2019/JSSP/Kaggle/灌装线等 12 场景全绿 + APS 标准数据集），详见 [docs/validation.md](docs/validation.md)。客户场景仅在本地运行，数据不出厂。

## 可靠性（三层背书）
1. APS 标准数据集（data/）：aps_docs/APS数据集可靠性验证报告.md（发现并修复 2 个引擎 bug）
2. 公开数据集评测（10 数据集）：aps_training/eval_suite.py
3. 参考试点参考回归：aps-engine/tests/test_solve.py

## 方法论资产（aps_docs/）
- 排产技巧学习笔记-调研报告消化.md（参考试点参考方法论）
- APS插件创新方法设计.md（Pinedo 理论 × 实践，7 个创新点）
- T+3排产的合理性与科学性说明.md（蒙特卡洛 + 覆盖率回测）
- 订单预测多模型对比与择优报告.md（TimesFM/GBDT 择优）
