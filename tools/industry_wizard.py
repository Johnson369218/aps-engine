# -*- coding: utf-8 -*-
"""行业适配向导：描述你的工厂（设备/产品/工艺）→ 识别大类 → 标准功能推荐。

用法:
  .venv/bin/python aps-engine/tools/industry_wizard.py --text "我们做注塑，生产手机壳和药瓶，几台海天注塑机"
  .venv/bin/python aps-engine/tools/industry_wizard.py --list     # 列出 31 大类适配度汇总
"""
import argparse, os, sys
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_PLUGIN_DIR, os.path.dirname(_PLUGIN_DIR)):
    if _p not in sys.path: sys.path.insert(0, _p)
from aps_engine.industry import INDUSTRIES, GUIDE_PROMPT, recognize, fit_summary  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="行业适配向导（APS 适合我的需求吗？）")
    ap.add_argument("--text", default=None, help="用一段话描述你的工厂")
    ap.add_argument("--list", action="store_true", help="列出 31 大类适配度汇总")
    ap.add_argument("--guide", action="store_true", help="显示客户提示词（怎么描述才准确）")
    args = ap.parse_args(argv)

    if args.guide:
        print(GUIDE_PROMPT)
        return 0

    if args.list:
        s = fit_summary()
        print(f"制造业 {s['total']} 大类：强适配 {s['high']} / 中适配 {s['mid']} / 弱适配 {s['low']}\n")
        for i in INDUSTRIES:
            print(f"  {i['code']} {i['name']:<14} {i['type']:<8} {'✅强' if i['fit']=='high' else '🟡中' if i['fit']=='mid' else '⚪弱'}  {i['engine']}")
        return 0

    if not args.text:
        ap.print_help()
        return 1

    matches = recognize(args.text)
    if not matches:
        print("描述太笼统，没对上号。照着下面这样说，我就能准确归类：\n")
        print(GUIDE_PROMPT)
        return 1
    print(f"你的描述：{args.text}\n")
    for i, r in enumerate(matches, 1):
        print(f"── 匹配 {i} ──")
        for k, v in r.items():
            if isinstance(v, list):
                print(f"  {k}: {', '.join(v)}")
            else:
                print(f"  {k}: {v}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
