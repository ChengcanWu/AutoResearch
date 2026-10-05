# -*- coding: utf-8 -*-
"""工具 registry 的离线测试：不联网。

工具是模型唯一的「看世界」通道，全部只读；失败必须结构化返回，不能抛异常中断对话。
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
import tools  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()


def make_user() -> str:
    return store.create_user("t")["uid"]


def test_unknown_tool_is_rejected_not_raised():
    uid = make_user()
    r = tools.run(uid, {"tool": "db.delete_everything", "args": {}})
    assert r["ok"] is False and r["error"] == "unknown tool"


def test_bad_args_shape_does_not_crash():
    uid = make_user()
    r = tools.run(uid, {"tool": "project.search", "args": "not a dict"})
    assert r["ok"] is False  # 没方向 → 结构化失败


def test_only_registered_tools_are_described():
    text = tools.describe()
    for name in tools.TOOL_SPECS:
        assert name in text


def test_course_search_falls_back_to_the_user_message(monkeypatch):
    """模型漏传 query 时不浪费一整轮：用用户这句话当检索词，并标明来源。"""
    uid = make_user()
    called = {}

    def fake_search(query, **kw):
        called["query"] = query
        return {"ok": True, "items": [{"name": "机器学习导论"}], "term": "2026秋"}

    monkeypatch.setattr(tools, "search_courses", fake_search)
    r = tools.run(uid, {"tool": "course.search", "args": {}},
                  context={"query_hint": "北大有哪些机器学习的课"})

    assert called["query"] == "北大有哪些机器学习的课"
    assert r["ok"] is True
    assert r["query_from"] == "user_message"
    assert r["items"][0]["name"] == "机器学习导论"


def test_course_search_marks_model_supplied_query(monkeypatch):
    uid = make_user()
    monkeypatch.setattr(tools, "search_courses", lambda q, **kw: {"ok": True, "items": []})
    r = tools.run(uid, {"tool": "course.search", "args": {"query": "线性代数"}})
    assert r["query_from"] == "model"


def test_course_search_without_query_or_context_still_fails_cleanly():
    uid = make_user()
    r = tools.run(uid, {"tool": "course.search", "args": {}})
    assert r["ok"] is False and "query" in r["error"]


def test_course_search_reports_failure_without_inventing(monkeypatch):
    uid = make_user()
    monkeypatch.setattr(tools, "search_courses",
                        lambda q, **kw: {"ok": False, "error": "network URLError"})
    r = tools.run(uid, {"tool": "course.search", "args": {"query": "机器学习"}})
    assert r["ok"] is False
    assert "items" not in r  # 失败时不带任何结果，避免下游误用
    assert "network" in r["error"]


def test_tool_exception_becomes_structured_failure(monkeypatch):
    uid = make_user()

    def boom(*a, **k):
        raise RuntimeError("pku subprocess died")

    monkeypatch.setattr(tools, "search_courses", boom)
    r = tools.run(uid, {"tool": "course.search", "args": {"query": "x"}})
    assert r["ok"] is False and "RuntimeError" in r["error"]


def test_project_review_cannot_reach_another_profile(monkeypatch):
    uid = make_user()
    store.save_project(uid, "p1", {"name": "项目"}, "reviewed")
    assert tools.run(uid, {"tool": "project.review", "args": {"project_id": "p1"}})["ok"] is True

    store.open_new_portrait(uid)
    r = tools.run(uid, {"tool": "project.review", "args": {"project_id": "p1"}})
    assert r["ok"] is False and "不属于当前画像" in r["error"]


def test_project_search_needs_a_direction_first():
    uid = make_user()
    r = tools.run(uid, {"tool": "project.search", "args": {}})
    assert r["ok"] is False and "方向" in r["error"]
