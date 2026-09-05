# -*- coding: utf-8 -*-
"""E1 多通道消息网关：通道无关业务层。
- 入口：任何通道消息 → adapt() 规范化 → 业务层（收单/事件/查询）
- 出口：push(actor_id, text) 按角色偏好路由（通道注册表驱动）
- 身份：actors.json（channel_user_id → actor_id/role）；未知用户默认 operator（最低权限）
- 契约见 docs/design-phase5-contract.md §1-2
"""
import json
import os
import uuid

_ROLES = ("owner", "planner", "sales", "warehouse", "operator")
# 动作→最低角色（owner 万能）
_PERMISSIONS = {
    "report_order": "operator",    # 报单人人可
    "report_back": "operator",     # 报工人人可
    "reschedule": "planner",       # 重排须计划员+
    "publish_plan": "planner",
    "adjust_rule": "owner",        # 规则/口径只有 owner
    "view_owner_brief": "owner",
}


class Channels:
    """通道注册表 + 规范化（本阶段内置 cli；wechat 桥接 dsh-im 的契约位）。"""

    _registry = {}

    @classmethod
    def register(cls, channel_id, adapter):
        cls._registry[channel_id] = adapter

    @classmethod
    def adapt(cls, raw):
        """把任意通道消息规范化为统一 Message（不可信输入，只取白名单字段）。"""
        sender = raw.get("sender", {})
        return {
            "message_id": raw.get("message_id") or uuid.uuid4().hex,
            "source_channel": raw.get("source_channel", "cli"),
            "sender": {"channel_user_id": sender.get("channel_user_id", "unknown"),
                       "display_name": sender.get("display_name", "未知")},
            "content_type": raw.get("content_type", "text"),
            "content": str(raw.get("content", "")),
            "attachments": raw.get("attachments") or [],
            "ts": raw.get("ts"),
        }

    @classmethod
    def push(cls, actor_id, text, channel=None):
        if not cls._registry:
            return [("cli", text)]
        sent = []
        for cid, ad in cls._registry.items():
            if channel and cid != channel:
                continue
            ok = ad.push(actor_id, text)
            sent.append((cid, ok))
        return sent

    @classmethod
    def health(cls):
        return {cid: bool(ad.health()) for cid, ad in cls._registry.items()}


class CliChannel:
    def __init__(self, out=None):
        self._out = out

    def push(self, actor_id, text):
        if self._out is None:
            print(f"[cli->{actor_id}] {text}")
        else:
            with open(self._out, "a", encoding="utf-8") as f:
                f.write(f"[{actor_id}] {text}\n")
        return True

    def health(self):
        return True


def load_actors(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def role_of(actors_path, channel_user_id, default="operator"):
    actors = load_actors(actors_path)
    rec = actors.get(channel_user_id, {})
    return rec.get("role", default)


def can(role, action):
    need = _PERMISSIONS.get(action, "owner")
    return _ROLES.index(role) <= _ROLES.index(need)
