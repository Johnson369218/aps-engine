# 阶段 5 · 入口与规模化 契约（冻结）

> 依据《APS 插件技术改进路线》阶段 5（E1 多通道网关 + E4 韧性 + E2 输出三件套 + B6 规模化）。
> 退出标准：第二家试点企业接入（0 代码，仅配置）。
> 红线：业务层与通道解耦（换通道 0 业务改动）；消息按不可信输入处理；台账/排产数据不出厂；
> 概率/回放结果只做建议（推荐规则须 skill_gate 审批生效）；版本联动五处。

---

## 1. Message 协议（E1）

```json
{
  "message_id": "uuid",
  "source_channel": "cli|wechat|dingtalk|feishu|sms",
  "sender": {"channel_user_id": "…", "display_name": "…"},
  "content_type": "text|voice|image|file",
  "content": "…",
  "attachments": [],
  "ts": "…"
}
```

- **身份映射**：`data/actors.json`：`channel_user_id → {actor_id, role, display_name}`；
  `role ∈ {owner, planner, sales, warehouse, operator}`。
- **角色=权限**：`operator` 仅报单/报工，不可重排/发布计划；`planner` 可重排/发布；`owner` 万能（改规则/口径）。

## 2. 通道适配器接口（E1）

- `Channels.register(channel_id, adapter)` / `Channels.adapt(raw) -> Message`（只取白名单字段，不可信输入）
  / `Channels.push(actor_id, text, channel=None)` / `Channels.health()`。
- v1 内置 `cli` 通道（终端模拟）；`wechat` 对接 `dsh-im`（桥接契约位，本阶段不实现桥本身）；
  `dingtalk/feishu/sms` 为协议预留。

## 3. 输出三件套（E2）

- `brief_worker(result)`：员工一句话（≤5 行：排产/准时/延期/最忙线/瓶颈）。
- `brief_shopfloor(result)`：车间班前单摘要（每线 单数×数量 起止，打印/大屏用）。
- `brief_owner(result, extra)`：老板日报（准时率/总延期/换型/瓶颈/建议 + 待办）。
- **E4 降级标注**：`result.engine != 'cp'` 时标注「规则兜底，非 AI 优化」。

## 4. 韧性（E4）

- `scripts/backup_ledger.sh`：每日备份 `data/ledger/*.db → data/backup/`（滚动保留 7 份，幂等）。

## 5. 规模化（B6）

- **瓶颈分解**：`solve(..., mode="decompose")`（新参数，默认 `"cp"` 不变）——
  heuristic 快解得各线负荷 → 负荷 > 85% 的线用 CP 精排、其余保持 heuristic → 合并 → 跑 audit。
- **概率缓冲**：`config/industry_example.json` 增 `prob_buffer: {}` 段（算法接入后续）。
- **规则回放择优**：`tools/replay_rules.py` 六规则对比 → 输出「推荐规则」候选
  （`activation: "pending_replay"`），须 `skill_gate` 审批后生效，**不自动生效**。

## 6. 接入即适配清单（阶段 5 退出标准）

新试点 = ① `config/industry_<x>.json` ② `data/actors.json` ③ `data/experience/`（可选）→ **0 代码**。

---

## 验收清单

| 项 | 命令 | 期望 |
|---|---|---|
| E1 | `.venv/bin/python aps-engine/tests/test_channels.py` | 3 PASS + `ALL PASS` |
| E2 | `.venv/bin/python aps-engine/tests/test_briefing.py` | 3 PASS + `ALL PASS` |
| E4 | `bash scripts/backup_ledger.sh`（两次） | 两次 `备份完成`，`data/backup/` 有带时间戳副本 |
| B6 | `.venv/bin/python aps-engine/tests/test_scaling.py` | `PASS 分解模式 audit ok` + `PASS 默认 mode 语义不变` |
| 接入演示 | 配置 + 消息 → `Channels.adapt` + `role_of` + `can` | `配置就绪，0 代码；角色 operator 可报工` |
