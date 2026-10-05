# -*- coding: utf-8 -*-
"""对话 → 任务区 → 回对话，这条链路是不是真的通了。

用户问过两次：「我在对话里出现的任务是要我怎么完成」「任务区的任务和这个任务
是一个东西吗」。之前答案是「没法完成，而且不是一个东西」——对话的行动卡
从来没建过 tasks 行，任务区读 tasks 表，所以永远是空的。

这个文件就测那条链路，不碰模型（用规则回退路径拿一张行动卡）。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

SERVER = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import dialogue  # noqa: E402
import llm  # noqa: E402
import store  # noqa: E402
import workbench  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()
    # 这条链路不该依赖模型：固定走规则/骨架路径，测试才可重复
    monkeypatch.setattr(llm, "enabled", lambda: False)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: None)


@pytest.fixture()
def uid():
    return store.create_user("任务链路")["uid"]


def _open_action(uid):
    """造一张开着的行动卡（等价于对话给了你一个下一步）。"""
    return store.save_action(uid, conversation_id="c1", action="micro_task",
                             title="拿 Kotoba 的 20 条真实输入跑一遍", status="offered",
                             direction="ai")


def test_accept_creates_a_real_task(uid):
    """这条链路的唯一接点：accept 必须建任务。"""
    a = _open_action(uid)
    assert store.list_tasks(uid) == [], "一开始任务区应该是空的"

    out = dialogue.action_event(uid, a["id"], "accept")

    tasks = store.list_tasks(uid)
    assert len(tasks) == 1, "accept 之后任务区必须有东西"
    t = tasks[0]
    assert t.action_id == a["id"], "任务要知道自己来自哪张行动卡"
    assert t.origin == "dialogue"
    assert t.title == a["title"]
    assert out["task_id"] == t.id, "返回值要带上 task_id，前端才能跳过去"


def test_a_task_answers_all_three_questions(uid):
    """『我在对话里出现的任务是要我怎么完成』——任务必须回答三个问题。"""
    a = _open_action(uid)
    dialogue.action_event(uid, a["id"], "accept")
    t = store.list_tasks(uid)[0]
    assert len(t.steps) >= 2, "做什么：要有具体步骤"
    assert t.deliverable.strip(), "交什么：要说清交上来的东西长什么样"
    assert len(t.rubric) >= 2, "怎样算过：要有可逐条判定的标准"
    assert all(r.get("criterion") for r in t.rubric), "评分标准不能是空条目"


def test_accept_is_idempotent(uid):
    """重复 accept 不该造出第二个任务——否则任务区会越点越多。"""
    a = _open_action(uid)
    first = dialogue.action_event(uid, a["id"], "accept")
    second = dialogue.action_event(uid, a["id"], "accept")
    assert first["task_id"] == second["task_id"]
    assert len(store.list_tasks(uid)) == 1


def test_the_same_task_is_visible_from_both_sides(uid):
    """『任务区的任务和这个任务是一个东西吗』——现在必须是同一个。"""
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    # 任务区看到的
    from_task_area = store.get_task(out["task_id"])
    # 对话看到的
    public = dialogue._public_action(store.get_action(uid, a["id"]))
    assert public["task_id"] == from_task_area.id
    assert from_task_area.action_id == public["action_id"]
    # 同一个 id 两边都能取到同一行
    assert store.get_task(public["task_id"]).title == from_task_area.title


def test_submitting_closes_the_dialogue_action(uid):
    """在任务区做完 → 回到对话，对话必须知道这一步走完了。"""
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    t = store.get_task(out["task_id"])

    fb = workbench.submit(uid, t, "我跑了 20 条输入，其中 3 条判断反了。"
                                  "因为片假名夹杂时关键词规则失效，所以结论是……")

    assert store.get_action(uid, a["id"])["status"] == "completed", \
        "任务提交后，对话里那张卡要是已完成"
    assert fb["learned_facts"], "提交要写回一条经验事实"
    kinds = [e["kind"] for e in store.list_events(uid)]
    assert "action_completed" in kinds and "task_submitted" in kinds


def test_submitting_writes_an_experience_fact(uid):
    """真实写回：做完这是「经历积累」的证据，不是一句「已完成」。"""
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    workbench.submit(uid, store.get_task(out["task_id"]), "做完了，结果是这样……")
    facts = [f for f in store.list_facts(uid, statuses=("active",)) if f.category == "experience"]
    assert len(facts) == 1
    assert facts[0].source == "behavior", "来自真实行为，不是自述"
    assert "20 条" in facts[0].value or "微任务" in facts[0].value


def test_task_id_survives_a_refresh(uid):
    """刷新后还要能点「去完成」——所以 _public_action 要能重新查出 task_id。"""
    a = _open_action(uid)
    dialogue.action_event(uid, a["id"], "accept")
    # 模拟刷新：不带任何前端状态，只按 uid + action_id 重建
    again = dialogue._public_action(store.get_action(uid, a["id"]))
    assert again["task_id"], "刷新后拿不到 task_id 的话，用户就找不到那个任务了"


def test_declining_does_not_create_a_task(uid):
    """「先不做」不该往任务区塞东西。"""
    a = _open_action(uid)
    dialogue.action_event(uid, a["id"], "decline")
    assert store.list_tasks(uid) == []


def test_the_card_does_not_vanish_after_submitting(uid):
    """回到对话时那张卡不能凭空消失。

    pending_action 只含未终结的行动；任务一交，那一步就 completed 了，
    于是 pending_action 变成 None。如果 history 只给 pending_action，
    用户从任务区回到对话会发现「我刚做的那件事不见了」。
    """
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    workbench.submit(uid, store.get_task(out["task_id"]), "做完了，因为……所以……")

    h = dialogue.history(uid)
    assert h["pending_action"] is None, "这一步确实已经终结了"
    assert h["last_action"], "但必须还能拿到最近那张卡"
    assert h["last_action"]["action_id"] == a["id"]
    assert h["last_action"]["status"] == "completed"
    assert h["last_action"]["task_id"] == out["task_id"], "刷新后还要能点回任务"


def test_just_finished_carries_what_was_submitted(uid):
    """回到对话要能说一句「你刚交了 X」——所以得带上提交内容。"""
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    workbench.submit(uid, store.get_task(out["task_id"]),
                     "我跑了 20 条真实输入，其中 3 条判断反了。因为片假名被截断，所以……")
    jf = dialogue.history(uid)["just_finished"]
    assert jf, "刚完成的事要能被说出来"
    assert jf["action_id"] == a["id"]
    assert jf["title"] == a["title"]
    assert jf["payload"].get("chars"), "带上写了多少字"
    assert "score" in jf["payload"], "带上评分"


def test_just_finished_clears_once_a_new_action_is_offered(uid):
    """已经给出新的一步之后，就不该再念叨「你刚交了上一个」了。"""
    a = _open_action(uid)
    out = dialogue.action_event(uid, a["id"], "accept")
    workbench.submit(uid, store.get_task(out["task_id"]), "做完了，因为……")
    assert dialogue.history(uid)["just_finished"]

    new = store.save_action(uid, conversation_id="c1", action="micro_task",
                            title="下一步：把预处理加到线上", status="offered")
    h = dialogue.history(uid)
    assert h["pending_action"]["action_id"] == new["id"]
    assert h["just_finished"] is None, "有新任务了就不该再提旧的"


def test_tree_tasks_and_dialogue_tasks_are_distinguishable(uid):
    """两边的任务要能分开显示，但都在同一张表里（所以不会各查各的）。"""
    a = _open_action(uid)
    dialogue.action_event(uid, a["id"], "accept")
    tree = workbench.generate_task(uid, "ai", 1, title="特征")
    all_tasks = store.list_tasks(uid)
    assert len(all_tasks) == 2
    by_origin = {t.origin for t in all_tasks}
    assert by_origin == {"dialogue", "tree"}
    assert store.get_task(tree.id).origin == "tree"
    assert store.get_task(tree.id).deliverable, "树上出的任务也要说清交什么"


def test_old_tasks_without_deliverable_still_load(uid):
    """老数据没有 deliverable 字段，不能因此读不出来（本地库里有旧任务）。"""
    from schemas import MicroTask
    legacy = MicroTask(user_id=uid, direction="ai", title="旧任务")
    d = legacy.to_dict()
    d.pop("deliverable", None)
    d.pop("origin", None)
    d.pop("action_id", None)
    t = MicroTask.from_dict(d)
    assert t.deliverable == ""
    assert t.origin == "tree"
    assert t.action_id == ""
