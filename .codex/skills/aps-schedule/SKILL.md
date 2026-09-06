---
name: aps-schedule
description: 通用 APS 排产与优化引擎（APS Engine）。当用户要「排产 / 生产计划 / 车间排程 / 急单重排 / 报工 / 设备下发 / 识别我是什么行业」时使用本技能——一句话或照片识别行业（制造业 31 大类 + 细分工艺），然后 CP-SAT / Job-Shop 排产，结果经 Modbus TCP / DNC / REST 直发设备或输出 Excel/简报，并支持报工→台账→重排→校准闭环。
---

# APS Engine · 车间排产（Codex 版）

## 红线（违反即事故，务必遵守）

1. **设备指令先 dry-run，人工确认后才 `--confirm`**：推错寄存器/数量/温度会废料甚至伤机。
2. **拍板在人**：副驾推荐、急单重排、规则回放、校准修正都是「建议」，绝不自动改正式排产参数。
3. **细分工艺别混淆**：同一大类不同产品工艺/合规不同——`药剂瓶`=药包材（带 GMP/洁净/批号/溶出物），`手机壳`=普通注塑（GB/T）。识别按产品词命中细分模板，绝不大类一锅烩。
4. **数据不出厂、不瞎编**：客户数据/设备地址/密钥仅本机（`data/*.json` 已 gitignore）；排不出就直说无解/建议放宽，模糊就追问，不编数据。

## 工作流（四步）

### 1 收单 + 识别（一句话/照片，不问术语）
```bash
python tools/industry_wizard.py --text "我们做注塑，生产药剂瓶和手机壳"
# 用户描述太笼统（如「做瓶子」）→ 出示提示词引导补全，不猜：
python tools/industry_wizard.py --guide
```

### 2 排产（CP-SAT 单工序；多工序用 solve_jssp）
```bash
python tools/schedule_cli.py \
    --orders <orders.json> --lines <lines.json> --products <products.json> \
    --out output/schedule.json --xlsx "output/排产表.xlsx" --engine auto --seed 42
# 副驾对比（快排 vs CP 精排 + 推荐理由）：
python tools/schedule_cli.py ... --compare
# 多工序（车/铣/钻/磨 等有前序）：aps_engine/jssp.py::solve_jssp
```

### 3 设备直连（先 dry-run，人工确认后再 confirm）
```bash
cp data/machines.example.json data/machines.json   # 填机台 IP + 寄存器地址表（以 PLC 说明书为准）
python tools/machine_push.py --schedule output/schedule.json \
    --machines data/machines.json --machine <机台id> --products <products.json>
# 确认无误后： python tools/machine_push.py ... --confirm
```

### 4 闭环（报工 → 台账 → 急单重排 → 校准）
```bash
python tools/report_back.py --db data/ledger/aps_ledger.db --order O-001 --qty 5000 --unit 米 --by 班组长
python tools/replan_cli.py --plan output/schedule.json --lines <l> --products <p> \
    --rush '{"id":"RUSH-001","product":"P_CASE","qty":5000,"due":"…","priority":1,"allowed_lines":["L1"]}' \
    --freeze-before "…" --out output/replan.json
bash scripts/backup_ledger.sh
```

## 即插即用模板

- `examples/printing_sme/` —— 印刷（柔印/凹印/分切/制袋，含换型 + 速度温度张力）
- `examples/plastic_injection/` —— 注塑/塑料（含换模具 + 压力温度模次）

## 验证（证据先于断言）

- 单元测试（assert+`__main__`，无 pytest）：`python tests/test_<x>.py`
- 公开数据集评测：`python tests/eval_suite.py --quick`（12 场景，JSSP ft06=55 最优）
- 结论可靠性：契约先行 / 公开语料 / seed 可复现 / audit 6 项 / 基线回放 / 校准闭环 / 蒙特卡洛 P10-P50-P90 / 拍板在人
