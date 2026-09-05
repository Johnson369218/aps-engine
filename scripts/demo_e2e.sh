#!/bin/bash
# ============================================================================
# APS Engine 端到端演示脚本（可录屏，X/Twitter 与 YouTube 通用）
#
# 运行：  bash scripts/demo_e2e.sh
# 录屏用法：
#   X / Twitter（~90 秒）→ 只录「场景1 识别 + 场景2 排产」两个片段，加一句旁白
#   YouTube（~6 分钟）    → 录全部 4 个场景 + 全程配音讲解
#
# 4 个场景 = 一条完整闭环：
#   1 一句话识别（药瓶 vs 手机壳 自动区分）→ 2 排产(CP-SAT) → 3 设备直连(Modbus) → 4 急单重排
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."                      # 回到 aps-engine 根目录
mkdir -p /tmp/aps_demo

# 优先用工作区 .venv 的 python（../.venv = 生产调度/.venv）
PY="python3"
[ -x "../.venv/bin/python" ] && PY="../.venv/bin/python"

scene() {
  echo ""
  echo "══════════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "══════════════════════════════════════════════════════════════════"
  sleep "${2:-2}"
}

scene "场景1 · AI 识别：一句话自动区分「药瓶 vs 手机壳」" 2
$PY tools/industry_wizard.py --text "生产手机保护壳和药剂瓶，注塑加吹瓶" 2>&1 | head -16

scene "场景2 · 排产：CP-SAT + 换型优化，100% 准时 + 审计通过" 2
$PY tools/schedule_cli.py \
  --orders examples/plastic_injection/orders.json \
  --lines examples/plastic_injection/lines.json \
  --products examples/plastic_injection/products.json \
  --out /tmp/aps_demo/schedule.json --engine auto --seed 42 2>&1 | head -10

scene "场景3 · 设备直连：Modbus 写寄存器（dry-run 预览，未真写）" 2
cat > /tmp/aps_demo/machines.json <<'EOF'
{"machines":{"inj1":{"name":"注塑机1#(120T)","type":"modbus_tcp","host":"192.168.1.10","port":502,"unit":1,"line":"L1","registers":{"qty":{"addr":0,"count":2},"pressure":{"addr":10},"temperature":{"addr":20},"cycle":{"addr":30}}}}}
EOF
$PY tools/machine_push.py --schedule /tmp/aps_demo/schedule.json \
  --machines /tmp/aps_demo/machines.json --machine inj1 \
  --products examples/plastic_injection/products.json 2>&1 | head -8

scene "场景4 · 闭环：急单 → 触发 → 真实重排 → 变更清单" 2
$PY tools/replan_cli.py \
  --plan /tmp/aps_demo/schedule.json \
  --lines examples/plastic_injection/lines.json \
  --products examples/plastic_injection/products.json \
  --rush '{"id":"RUSH-001","product":"P_CASE","qty":5000,"due":"2026-09-01 15:00","priority":1,"allowed_lines":["L1"]}' \
  --freeze-before "2026-09-01 09:00" --out /tmp/aps_demo/replan.json 2>&1 | head -8

echo ""
echo "演示结束。X 用场景 1+2（~90 秒）；YouTube 用全部 4 场景（~6 分钟）+ 配音。"
