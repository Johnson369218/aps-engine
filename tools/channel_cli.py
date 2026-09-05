# -*- coding: utf-8 -*-
"""E1 通道 CLI 演示：终端模拟通道（测试与演示用）。

用法:
  .venv/bin/python aps-engine/tools/channel_cli.py --user li --content "3号线完成 O-001 500袋" --action report_back
  .venv/bin/python aps-engine/tools/channel_cli.py --user zhang --content "急单5000明天交" --action report_order
  .venv/bin/python aps-engine/tools/channel_cli.py --user li --content "重排" --action reschedule   # 应被权限拦截
"""
import argparse, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine import channels  # noqa: E402

DEFAULT_ACTORS = os.path.join(_PLUGIN_DIR, "data", "actors.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description="通道 CLI 演示（终端模拟通道）")
    ap.add_argument("--user", default="li")
    ap.add_argument("--content", required=True)
    ap.add_argument("--action", default="report_back",
                    help="report_order/report_back/reschedule/publish_plan/adjust_rule")
    ap.add_argument("--actors", default=DEFAULT_ACTORS)
    args = ap.parse_args(argv)

    msg = channels.Channels.adapt({"source_channel": "cli",
                                   "sender": {"channel_user_id": args.user, "display_name": args.user},
                                   "content_type": "text", "content": args.content})
    role = channels.role_of(args.actors, args.user)
    ok = channels.can(role, args.action)
    print(f"通道: {msg['source_channel']} | 用户: {args.user} | 角色: {role}")
    print(f"动作: {args.action} | 允许: {'✅' if ok else '⛔ 权限不足'}")
    print(f"消息: {msg['content']}")
    if ok:
        channels.Channels.register("cli", channels.CliChannel())
        channels.Channels.push(args.user, f"已受理（{args.action}）: {args.content}", channel="cli")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
