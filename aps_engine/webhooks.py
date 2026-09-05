# -*- coding: utf-8 -*-
"""E1 真实推送通道（机器人 webhook）：钉钉 / 企业微信 / 飞书 / 微信（dsh-im 桥）。

- 纯 stdlib（urllib + hmac），无第三方依赖。
- webhook URL / 加签密钥是敏感信息：放本地 `data/channels.json`（已 gitignore），
  仓库只提交 `data/channels.example.json` 模板（无真实密钥）。
- 测试 mock 网络（不真发请求、不提交密钥）；真实推送需部署方配置 webhook。
- 契约见 docs/design-phase5-contract.md §2。
"""
import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from aps_engine.channels import Channels


def _post(url, payload, timeout=5):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def _dingtalk_sign(secret, timestamp_ms):
    string_to_sign = f"{timestamp_ms}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"),
                      digestmod=hashlib.sha256).digest()
    return urllib.parse.quote_plus(base64.b64encode(digest))


class _WebhookChannel:
    """机器人 webhook 通道基类：push 返回是否送达（不抛异常）。"""
    type = "webhook"

    def __init__(self, webhook, secret=None):
        self.webhook = webhook or ""
        self.secret = secret

    def health(self):
        return bool(self.webhook)

    def _send(self, url, payload):
        try:
            _post(url, payload)
            return True
        except (urllib.error.URLError, OSError, ValueError):
            return False


class DingTalkChannel(_WebhookChannel):
    """钉钉自定义机器人（加签可选）。"""

    def push(self, actor_id, text):
        url = self.webhook
        if self.secret:
            ts = str(int(time.time() * 1000))
            url = f"{self.webhook}&timestamp={ts}&sign={_dingtalk_sign(self.secret, ts)}"
        payload = {"msgtype": "text", "text": {"content": text}}
        return self._send(url, payload)


class WeComChannel(_WebhookChannel):
    """企业微信群机器人。"""

    def push(self, actor_id, text):
        payload = {"msgtype": "text", "text": {"content": text}}
        return self._send(self.webhook, payload)


class FeishuChannel(_WebhookChannel):
    """飞书自定义机器人。"""

    def push(self, actor_id, text):
        payload = {"msg_type": "text", "content": {"text": text}}
        return self._send(self.webhook, payload)


class WechatDshimChannel(_WebhookChannel):
    """微信（个人）——经 dsh-im 桥（DSH 技能层）转发。

    本通道是【客户端契约位】：POST `{to, text}` 到 dsh-im 的 HTTP 端点；
    dsh-im 桥本身（接收并转发到个人微信）属 DSH 技能层，不在本仓库实现。
    """

    def push(self, actor_id, text):
        payload = {"to": actor_id, "text": text}
        return self._send(self.webhook, payload)


_ADAPTERS = {
    "dingtalk": DingTalkChannel,
    "wecom": WeComChannel,
    "feishu": FeishuChannel,
    "wechat": WechatDshimChannel,   # 微信=dsh-im 桥
}


def register_from_config(path):
    """读 data/channels.json，把各通道适配器注册进 Channels。返回已注册通道 id 列表。

    config 形如 {"channels": {"dingtalk": {"type": "dingtalk", "webhook": "...", "secret": "..."}, ...}}
    """
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    channels = cfg.get("channels", {})
    registered = []
    for cid, c in channels.items():
        typ = c.get("type", cid)
        cls = _ADAPTERS.get(typ)
        if cls is None:
            continue
        Channels.register(cid, cls(c.get("webhook", ""), c.get("secret")))
        registered.append(cid)
    return registered
