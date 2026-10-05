# -*- coding: utf-8 -*-
"""画像完全隔离的回归测试（archive 中的 M5）。

每份画像必须像独立账号：对话、事实、任务、提交、项目、会话、行动、事件、修订、决策
全部互不可见。切换画像后再切回来要完整恢复。

运行：pytest server/tests
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm  # noqa: E402

llm.enabled = lambda: False

import store  # noqa: E402
from schemas import MicroTask, UserFact  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()


def fill(uid: str, tag: str) -> None:
    """往当前画像里塞满各类数据。"""
    store.add_fact(UserFact(user_id=uid, category="interest", key=f"interest:{tag}",
                            value=f"{tag} 的兴趣", status="confirmed"))
    store.add_message(uid, "user", f"我是 {tag}", conversation_id="c1")
    store.save_task(MicroTask(user_id=uid, direction="ai", title=f"任务 {tag}"))
    store.add_event(uid, "turn", source_id=tag)
    store.open_conversation(uid, topic_hint=tag)
    store.save_action(uid, conversation_id="c1", action="micro_task", title=f"行动 {tag}")
    store.save_project(uid, f"p-{tag}", {"name": f"项目 {tag}"}, "reviewed")
    store.bump_memory_version(uid)


def snapshot(uid: str) -> dict:
    return {
        "facts": sorted(f.key for f in store.list_facts(uid)),
        "messages": sorted(m["text"] for m in store.list_messages(uid)),
        "tasks": sorted(t.title for t in store.list_tasks(uid)),
        "events": len(store.list_events(uid)),
        "conversations": len(store.list_conversations(uid)),
        "actions": len(store.list_actions(uid)),
        "projects": sorted(p["name"] for p in store.list_projects(uid)),
        "memory_version": store.get_memory_version(uid),
    }


def test_new_portrait_sees_none_of_the_previous_data():
    uid = store.create_user("t")["uid"]
    fill(uid, "A")

    store.open_new_portrait(uid)

    assert snapshot(uid) == {
        "facts": [], "messages": [], "tasks": [], "events": 0,
        "conversations": 0, "actions": 0, "projects": [], "memory_version": 0,
    }


def test_switching_back_restores_the_original_portrait():
    uid = store.create_user("t")["uid"]
    fill(uid, "A")
    before = snapshot(uid)
    first = [p for p in store.list_portraits(uid) if p["active"]][0]["id"]

    store.open_new_portrait(uid)
    fill(uid, "B")
    after_b = snapshot(uid)
    assert after_b["facts"] == ["interest:B"]

    store.activate_portrait(uid, first)

    assert snapshot(uid) == before


def test_deleting_the_last_portrait_clears_everything():
    uid = store.create_user("t")["uid"]
    fill(uid, "A")
    pid = [p for p in store.list_portraits(uid) if p["active"]][0]["id"]

    needs_restart = store.delete_portrait(uid, pid)

    assert needs_restart is True
    assert snapshot(uid)["facts"] == []
    assert snapshot(uid)["tasks"] == []
    assert snapshot(uid)["projects"] == []


def test_two_users_never_share_data():
    a = store.create_user("a")["uid"]
    b = store.create_user("b")["uid"]
    fill(a, "A")
    fill(b, "B")

    assert store.list_tasks(a)[0].title == "任务 A"
    assert store.list_tasks(b)[0].title == "任务 B"
    assert [f.key for f in store.list_facts(a)] == ["interest:A"]
    assert [f.key for f in store.list_facts(b)] == ["interest:B"]
