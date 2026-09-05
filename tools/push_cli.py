# -*- coding: utf-8 -*-
"""E1 真实推送 CLI：把文本简报推送到已配置的机器人 webhook（钉钉/企微/飞书/微信 dsh-im）。

用法:
  .venv/bin/python aps-engine/tools/push_cli.py --channels data/channels.json \
      --text "排产简报：293 单，准时率 100%" [--channel dingtalk] [--to boss]

通道密钥放本地 data/channels.json（已 gitignore，模板见 data/channels.example.json）。
"""
import argparse, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine import channels, webhooks  # noqa: E402

DEFAULT_CHANNELS = os.path.join(_PLUGIN_DIR, "data", "channels.json")


def main(argv=None):
    ap = argparse.ArgumentParser(description="真实推送：简报文本 → 机器人 webhook")
    ap.add_argument("--channels", default=DEFAULT_CHANNELS, help="data/channels.json 路径")
    ap.add_argument("--text", required=True, help="推送内容")
    ap.add_argument("--channel", default=None, help="指定通道 id（省略则广播全部已配置通道）")
    ap.add_argument("--to", default="boss", help="actor_id（微信 dsh-im 等按人路由用）")
    args = ap.parse_args(argv)

    if not os.path.exists(args.channels):
        print(f"未找到 {args.channels}（先复制 data/channels.example.json 并填 webhook）")
        return 1
    reg = webhooks.register_from_config(args.channels)
    if not reg:
        print("无可用通道（channels.json 未配置 webhook）")
        return 1
    sent = channels.Channels.push(args.to, args.text, channel=args.channel)
    for cid, ok in sent:
        print(("✅ 已推送 " if ok else "⛔ 推送失败 ") + cid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
