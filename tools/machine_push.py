# -*- coding: utf-8 -*-
"""设备直连 CLI：把排产结果下发到设备（红线：默认 dry-run，--confirm 才真写）。

用法:
  .venv/bin/python aps-engine/tools/machine_push.py \
      --schedule output/schedule.json --machines data/machines.json --machine flexo1 \
      [--products data/products.json] [--confirm]

机器地址/寄存器放本地 data/machines.json（已 gitignore，模板 data/machines.example.json）。
"""
import argparse, json, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine import machine  # noqa: E402

DEFAULT_MACHINES = os.path.join(_PLUGIN_DIR, "data", "machines.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description="设备直连：排产 → 设备指令（先确认再下发）")
    ap.add_argument("--schedule", required=True, help="排产结果 schedule.json")
    ap.add_argument("--machines", default=DEFAULT_MACHINES, help="data/machines.json 路径")
    ap.add_argument("--machine", required=True, help="目标机台 id（machines.json 的 key）")
    ap.add_argument("--products", default=None, help="products.json（可选，取工艺参数 process_params）")
    ap.add_argument("--confirm", action="store_true", help="⚠ 真写设备（默认 dry-run 只预览）")
    args = ap.parse_args(argv)

    if not os.path.exists(args.machines):
        print(f"未找到 {args.machines}（先复制 data/machines.example.json 并填 IP/寄存器）")
        return 1
    machines = machine.load_machines(args.machines)["machines"]
    if args.machine not in machines:
        print(f"机台 {args.machine} 不在配置中，可用: {', '.join(machines)}")
        return 1
    cfg = machines[args.machine]

    result = json.load(open(args.schedule, encoding="utf-8"))
    products = json.load(open(args.products, encoding="utf-8")) if args.products else None
    jobs = machine.build_jobs(result, cfg.get("line"), products=products)

    if not jobs:
        print(f"{cfg.get('name', args.machine)}（产线 {cfg.get('line')}）无排产任务")
        return 0

    r = machine.dispatch(cfg, jobs, confirm=args.confirm)
    mode = "⚠ 已真写设备" if not r["dry_run"] else "dry-run 预览（未下发，加 --confirm 真写）"
    print(f"机台: {r['machine']} | 类型: {r['type']} | {mode} | 指令 {len(r['commands'])} 条 / 成功 {r.get('sent', '-')}")
    for c in r["commands"]:
        print(f"  {c['order']}  参数[{c['param']}] = {c['value']}  → 寄存器 {c['addr']}" + (f"（{c['count']}寄存器）" if c['count'] > 1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
