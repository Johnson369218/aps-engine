# 训练语料（12 个场景，随仓库打包）

每个场景目录含 orders.json / lines.json / products.json / expected.json（+原始数据文件）。
expected.json 为权威期望值（评测基准），synthetic=true 表示合成代表语料（下载真实数据后由
normalize.py 覆盖）。

| 场景 | 来源数据集 | 能力 scope | 期望值来源 |
|---|---|---|---|
| bottling_line_ts | 灌装线时间序列（Zenodo） | forecast, oee | 星期因子均值复算；OEE=0.86 |
| bpi2019_purchase_orders | BPI Challenge 2019（4TU） | schedule | 按日负荷≤480 构造，准时率 1.0 |
| vynfi_ocel_mfg | VynFi OCEL Manufacturing（HF） | schedule | 瓶颈 M03；前后工序 30/30 |
| mfg005_line_performance | MFG-005（HF） | schedule, oee | OEE 分解表；计划系数 0.88 |
| open_mes_korea_erp | open-mes-korea（GitHub） | mapping, schedule | erp_in 漏斗复算（101→36 订单） |
| jssp_ft06 | ScheduleOpt/SchedulingLab 基准 | jssp | 公开最优 55（LB=44） |
| jssp_gen33 | JSSP 基准（生成） | jssp | 暴力枚举最优 22（216 组合） |
| jssp_gen44 | JSSP 基准（生成） | jssp | 暴力枚举最优 23（331,776 组合） |
| oee_blogpost_shifts | kurtholst/blogpost-oee（GitHub） | oee, schedule | OEE=A×P×Q 复算≈0.80 |
| kaggle_manufacturing_production | Kaggle Manufacturing Production | forecast | 星期因子留出 MAE（7 天） |
| kaggle_smart_mfg_params | Kaggle Smart Manufacturing | schedule, risk | 质量风险分桶/漂移计数 |
| kaggle_oee_downtime | Kaggle Factory OEE & Downtime | oee, schedule | 可用率/停机归因复算 |

> 注：ft06 实例与最优值 55 来自公开基准（SchedulingLab jsp-instances）；gen33/gen44
> 的最优值由暴力枚举独立验证。JSSP 场景评估会暴露引擎"无工序前序约束"的能力缺口（预期
> precedence_violations>0），这是训练结论的一部分，而非语料错误。
