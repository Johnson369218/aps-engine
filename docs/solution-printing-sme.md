# 中小印刷企业 APS 解决方案（落地手册）

> 面向：中小印刷厂（柔印 / 凹印 / 分切 / 制袋 / 模切 / 覆膜，设备多来自温州、佛山）。
> 定位：信息化弱、但设备自动化较高——缺"大脑"（排程中枢），设备本身有 PLC 接口。
> 交付原则：**0 代码、仅配置**，5 个阶段按天落地，每阶段可独立见效。

---

## 0. 场景画像与痛点

| 痛点 | 本方案对策 |
|---|---|
| 排产靠老师傅经验（Excel/白板） | CP-SAT + 换型优化，可复现、有副驾对比 |
| 小批量、多品种、换版/换油墨频繁 | 换型矩阵 `setup_min` 进目标函数，压缩换型时间 |
| 交期紧（3-5 天）、易漏单 | 触发矩阵 + 急单重排（冻结区 0 变动 + 变更清单） |
| 设备利用率不透明 | 每线利用率 + 瓶颈(≥80%) + 老板日报 |
| 信息化弱、设备有 PLC 但无 MES | 引擎直接下发设备（Modbus TCP 写寄存器），当 MES 用 |

## 1. 总体架构（一张闭环）

```
订单：微信 / 钉钉 / 企微 / Excel / ERP快照
        ↓  channels.Channels.adapt 统一 Message → 角色权限
排产：solve()（单机台流水）+ 换型优化 + seed 可复现 + --compare 副驾
        ↓
呈现：21列排产表.xlsx + 5-Sheet 公式联动Excel + A/B双看板 + 三件套简报
        ↓
下发：设备直连 machine.py（Modbus TCP 写寄存器 / DNC / 作业单）+ 简报推送（钉钉/企微/微信）
        ↓
闭环：报工 report_back → 台账 ledger → 急单 replan → 校准 calibration
```

## 2. 分阶段落地（按天）

### 阶段 A · 数据准备（半天）
把机台/产品/订单写成三张标准表（模板见 `examples/printing_sme/`）：

- `lines.json`：每台机 = 一条产线（id/name/工作分钟/首日/班次）。
- `products.json`：每个产品含 **换型矩阵 `setup_min`**（换版/换油墨/换材质）与 **工艺参数 `process_params`**（速度/温度/张力）。
- `orders.json`：订单（产品/数量/交期/优先级/允许机台）。

### 阶段 B · 排产跑起来（半天）
```bash
python tools/schedule_cli.py \
    --orders examples/printing_sme/orders.json --lines examples/printing_sme/lines.json \
    --products examples/printing_sme/products.json \
    --out output/schedule.json --xlsx "output/排产表.xlsx" --engine auto --seed 42
python tools/schedule_cli.py ... --compare   # 副驾：快排 vs CP 精排 + 推荐
```
产出：21 列排产表（生产日期/品类/产品/机台/单位/计划数量/负荷/换型/交期/延期…）+ 5-Sheet 可核查 Excel。

### 阶段 C · 结果上板 + 简报推送（半天）
```bash
# A/B 双看板（全厂可见）
python tools/schedule_cli.py ... --kanban-a report_inbox/ --kanban-b /path/dashboard_data.js
# 简报推送：钉钉（老板群）/ 企微（车间群）
cp data/channels.example.json data/channels.json   # 填 webhook
python tools/push_cli.py --channels data/channels.json --text "排产简报：今日 120 单，准时率 96%"
```

### 阶段 D · 设备直连（半天，重点）
```bash
cp data/machines.example.json data/machines.json   # 填机台 IP + 寄存器地址表
# 默认 dry-run 预览（红线：先人工确认）
python tools/machine_push.py --schedule output/schedule.json \
    --machines data/machines.json --machine flexo1 --products examples/printing_sme/products.json
# 人工确认无误后真写
python tools/machine_push.py ... --confirm
```
- 柔印/凹印/分切/制袋（PLC）→ **Modbus TCP** 写数量/速度/温度/张力寄存器；
- 无网口老设备 → **作业单文件** → 机台终端/大屏，人工输 HMI；
- 数码/数控设备 → **DNC** 推 G 码。

### 阶段 E · 闭环（持续）
```bash
# 报工（一句话/数量回填）
python tools/report_back.py --db data/ledger/aps_ledger.db --order O-001 --qty 5000 --unit 米 --by 班组长
# 急单 → 触发 → 真实重排 → 变更清单（what-if，拍板在人）
python tools/replan_cli.py --plan output/schedule.json --lines ... --products ... \
    --rush '{"id":"RUSH-001","product":"P_BAG","qty":3000,"due":"2026-09-07 18:00","priority":1,"allowed_lines":["L1"]}' \
    --freeze-before "2026-09-06 18:00" --out output/replan.json
bash scripts/backup_ledger.sh   # 台账每日滚动备份 7 份
```

## 3. 关键配置模板（印刷专用）

### 3.1 机台 lines.json
```json
[
  {"id": "L1", "name": "柔印机1#（无纺布·温州）", "capacity": 1, "work_minutes_per_day": 480,
   "shift_start": "08:00", "first_date": "2026-09-01", "weekends_off": false},
  {"id": "L3", "name": "凹印机1#（卷膜·佛山）", "capacity": 1, "work_minutes_per_day": 480,
   "shift_start": "08:00", "first_date": "2026-09-01", "weekends_off": false}
]
```

### 3.2 产品 products.json（换型 + 工艺参数）
```json
[
  {"id": "P_BAG", "name": "无纺布袋(米)", "capacity_8h": 48000,
   "setup_min": {"P_FILM": 45, "P_PE": 30},
   "process_params": {"speed": 120, "temperature": 80, "tension": 300}},
  {"id": "P_FILM", "name": "BOPP卷膜(米)", "capacity_8h": 60000,
   "setup_min": {"P_BAG": 45, "P_PE": 35},
   "process_params": {"speed": 150, "temperature": 60, "tension": 250}}
]
```
> `setup_min` = 换版/换油墨/换材质时间（分钟），是印刷排产质量的关键，务必现场测准；
> `process_params` = 直发设备时写进 PLC 寄存器的工艺值。

### 3.3 设备直连 machines.json（寄存器地址以 PLC 说明书为准）
```json
{
  "machines": {
    "flexo1": {"name": "柔印机1#", "type": "modbus_tcp", "host": "192.168.1.10", "port": 502, "unit": 1,
               "line": "L1",
               "registers": {"qty": {"addr": 0, "count": 2}, "speed": {"addr": 10}, "temperature": {"addr": 20}}}
  }
}
```

## 4. 红线（务必遵守）

1. **设备指令先确认再下发**：`machine_push.py` 默认 dry-run，`--confirm` 才真写；推错数量/温度会废卷/伤机。
2. **换型时间必须测准**：`setup_min` 是印刷排产质量的核心，估错导致排产失真。
3. **数据不出厂**：客户订单/产品/设备地址仅本机，`data/*.json`（真实密钥/地址）已 gitignore。
4. **拍板在人**：急单重排/校准产出均为建议，人工审批后生效；副驾只出推荐不自动改排产。
5. **多工序场景**（如印刷+覆膜+模切 串联流水）用 `solve_jssp`（工序路由+前序），单机台场景用 `solve()`。

## 5. 参考数据

即插即用的三张表 + 设备直连模板见 `examples/printing_sme/`；跑通后按本手册阶段 B→E 逐步上生产。
