# Changelog

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
