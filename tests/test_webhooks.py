# -*- coding: utf-8 -*-
"""E1 真实推送：钉钉/企微/飞书/微信(dsh-im) webhook 适配器——mock 网络，验证载荷与加签。"""
import json, os, sys, tempfile
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine.webhooks import (DingTalkChannel, WeComChannel, FeishuChannel,
                                 WechatDshimChannel, register_from_config)  # noqa: E402
from aps_engine.channels import Channels  # noqa: E402


def _capture():
    calls = []
    m = mock.patch("aps_engine.webhooks._post",
                   side_effect=lambda url, payload: calls.append((url, payload)) or (200, '{"errcode":0}'))
    return m, calls


def test_dingtalk_sign_and_payload():
    m, calls = _capture()
    with m:
        ok = DingTalkChannel("https://oapi.dingtalk.com/robot/send?access_token=TOKEN",
                             secret="SEC001").push("boss", "今日排产293单")
    assert ok is True
    url, payload = calls[0]
    assert "timestamp=" in url and "sign=" in url, "钉钉加签应带 timestamp+sign"
    assert payload["msgtype"] == "text" and "293" in payload["text"]["content"]
    print("PASS test_dingtalk_sign_and_payload")


def test_wecom_payload():
    m, calls = _capture()
    with m:
        ok = WeComChannel("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=K").push("workshop", "班前单")
    assert ok is True
    url, payload = calls[0]
    assert payload["msgtype"] == "text" and "班前单" in payload["text"]["content"]
    print("PASS test_wecom_payload")


def test_feishu_and_dshim_payload():
    m, calls = _capture()
    with m:
        FeishuChannel("https://open.feishu.cn/open-apis/bot/v2/hook/H").push("owner", "日报")
        WechatDshimChannel("http://127.0.0.1:9000/dsh-im/send").push("a_zhang", "简报")
    f_url, f_payload = calls[0]
    d_url, d_payload = calls[1]
    assert f_payload["msg_type"] == "text" and "日报" in f_payload["content"]["text"]
    assert d_payload == {"to": "a_zhang", "text": "简报"}, d_payload
    print("PASS test_feishu_and_dshim_payload")


def test_register_from_config():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "channels.json")
        json.dump({"channels": {
            "dingtalk": {"type": "dingtalk", "webhook": "https://x", "secret": ""},
            "wecom": {"type": "wecom", "webhook": "https://y"},
        }}, open(p, "w", encoding="utf-8"))
        reg = register_from_config(p)
        assert set(reg) == {"dingtalk", "wecom"}, reg
        h = Channels.health()
        assert h.get("dingtalk") is True and h.get("wecom") is True
    print("PASS test_register_from_config")


if __name__ == "__main__":
    test_dingtalk_sign_and_payload()
    test_wecom_payload()
    test_feishu_and_dshim_payload()
    test_register_from_config()
    print("ALL PASS")
