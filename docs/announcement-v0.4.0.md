# APS Engine v0.4.0 发布公告（中文 + English）

> 用于发布到 V2EX / 知乎 / 掘金 / CSDN（中文），以及 Hacker News / Reddit r/manufacturing（英文）。
> 直接复制对应版本发布即可，`<repo>` 替换为 `https://github.com/Johnson369218/aps-engine`。

---

## 中文版（知乎 / V2EX / 掘金）

**标题：开源了一个通用制造业 APS 排产引擎——一句话描述工厂，自动识别、排产、直发设备（Modbus/CNC）**

做中小制造业的都知道排产有多痛：订单靠老师傅 Excel 排，换模换线频繁，交期总漏，设备利用率不透明。商业 APS 动辄几十万还要养实施团队，frePPLe 又是英文、只覆盖通用场景。

所以我开源了 **APS Engine**（MIT），一个面向国内中小制造企业的通用排产引擎：

- **一句话识别行业**：说「我公司生产不锈钢烧水壶」或发张车间照片，自动匹配 31 个制造业大类 + 细分工艺（药包材药瓶 vs 普通注塑件会分开，带上 GMP/批号/溶出物约束），**不问"离散还是连续"这种术语**；
- **排产**：CP-SAT + 换型压缩 + 多工序 Job-Shop（ft06 达公开最优 55，前序违规 0）+ seed 可复现；
- **设备直连**：排产结果直接写进设备——Modbus TCP（信捷/汇川/台达 PLC，柔印机/注塑机/窑炉）、网络 DNC（CNC 推 G 码）、作业单（无网口老设备），**默认 dry-run、人工确认后才真写**；
- **多通道**：订单微信/钉钉/企微/ERP 进来，结果以 Excel/看板/一句话简报出去，钉钉加签/企微/飞书真实推送；
- **闭环**：报工→台账→急单重排（冻结区 0 变动+变更清单）→执行校准（±5%/≥10% 状态机，审批才生效）。

**验证**：12 个公开数据集全绿、JSSP 三例达最优、零客户数据入库、14 个测试全 PASS。

**上手**：三张表（机台/产品/订单）+ 一个 machines.json，小时级出第一版排产。即插即用模板已备好印刷、注塑两个行业。

仓库：<repo>　README 里有一份完整落地手册和 31 大类适配矩阵。

---

## English (Hacker News / Reddit r/manufacturing)

**Title: Show HN: APS Engine — open-source production scheduling for manufacturing SMEs (CP-SAT, JSSP-optimal, Modbus/DNC machine integration)**

Small and mid-size manufacturers still schedule with spreadsheets and the old hand's gut feel. Commercial APS costs six figures and needs consultants; existing open-source schedulers are English-only and ignore shop-floor reality (changeovers, machine protocols, WeChat/DingTalk intake).

I open-sourced **APS Engine** (MIT) — a generic APS engine for manufacturing SMEs:

- **Describe your factory, not your data model** — "we make stainless steel kettles" (or a photo) → it matches one of 31 manufacturing categories + segment-level process (e.g. *medicine bottle* → pharmaceutical packaging with GMP/cleanroom/batch constraints, vs *phone case* → consumer injection molding). No "discrete vs continuous" questions.
- **Scheduling** — CP-SAT + setup-time reduction + multi-operation Job-Shop (ft06 = 55, optimal, 0 precedence violations) + reproducible (seed=42).
- **Machine-direct output** — push to PLCs over Modbus TCP, G-code to CNCs over network DNC, JSON to IoT gateways, or a job ticket for legacy machines. `dry-run` before any write (human-in-the-loop on purpose).
- **Closed loop** — report-back → ledger → rush-order replan (frozen-zone safe) → execution calibration (±5%/≥10%, approval-gated).

**Evidence**: 12 public datasets green, JSSP optimal, 14 tests passing, zero customer data in the repo.

**Try it**: three JSON tables + one machines.json → first schedule in hours. Ready-made templates for printing and injection molding.

Repo: <repo> — English README included.
