# -*- coding: utf-8 -*-
"""E1：Message 规范化、身份→角色、通道解耦（cli 通道）、角色权限。"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aps_engine import channels  # noqa: E402

def test_adapt_cli_text():
    m = channels.Channels.adapt(
        {"source_channel": "cli", "sender": {"channel_user_id": "zhang", "display_name": "张三"},
         "content_type": "text", "content": "急单5000袋明天交"})
    assert m["source_channel"] == "cli" and m["content"] == "急单5000袋明天交"
    print("PASS test_adapt_cli_text")

def test_role_resolution():
    with tempfile.TemporaryDirectory() as td:
        actors = os.path.join(td, "actors.json")
        import json
        json.dump({"zhang": {"actor_id": "a1", "role": "planner"}}, open(actors, "w"))
        role = channels.role_of(actors, "zhang")
        assert role == "planner", role
        # 未知用户 → 默认 operator（最低权限）
        assert channels.role_of(actors, "nobody") == "operator"
    print("PASS test_role_resolution")

def test_permission_gate():
    # operator 不可提交重排指令
    assert channels.can("operator", "reschedule") is False
    assert channels.can("planner", "reschedule") is True
    assert channels.can("owner", "reschedule") is True
    print("PASS test_permission_gate")

if __name__ == "__main__":
    test_adapt_cli_text(); test_role_resolution(); test_permission_gate()
    print("ALL PASS")
