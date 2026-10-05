# -*- coding: utf-8 -*-
"""对话能不能真的用上院系-专业知识库（离线，不联网、不调模型）。

起因是一次真实对话：用户问「信管有哪些专业分流」，回复是「我手上没有能检索北大培养方案
的工具」——工具其实已经做出来了（server/curriculum.py + MCP），只是没挂进对话的 registry。
这批用例就是钉住这件事：**问院系要能回专业名单，问不出来的要如实说不知道**。
运行：pytest server/tests
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import curriculum  # noqa: E402
import llm  # noqa: E402
import mcp_curriculum  # noqa: E402

llm.enabled = lambda: False

import dialogue  # noqa: E402
import store  # noqa: E402
import tools  # noqa: E402

KB_TOOLS = ("major_lookup", "major_detail", "match_transcript", "minor_programs", "course_lookup")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()


def make_user() -> str:
    return store.create_user("t")["uid"]


def fill_transcript(uid: str, major: str = "经济学专业", n: int = 18) -> list[str]:
    """把某个专业的必修课名当成绩单写进去（北大成绩单打印件只有课名，没有课号）。"""
    import json
    plan = json.loads((Path(curriculum.__file__).resolve().parent.parent
                       / "knowledge" / "curriculum" / "plans" / f"{major}.json"
                       ).read_text(encoding="utf-8"))
    names = [c["课程名称"] for m in plan["课程表"] for c in m["课程"] if c.get("课程名称")][:n]
    store.add_enrollments(uid, [{"course": nm, "grade": "85", "credits": 3,
                                 "term": "25-26学年度1学期", "kind": "专业必修",
                                 "status": "completed"} for nm in names])
    return names


# ---------- registry ----------


def test_curriculum_tools_are_registered_and_described():
    text = tools.describe()
    for name in KB_TOOLS:
        assert name in tools.TOOL_SPECS, f"{name} 没挂进对话的工具表"
        assert name in text, f"{name} 没出现在给模型看的工具清单里"


def test_dialogue_tools_match_the_mcp_tool_table():
    """对话和 MCP 共用一套定义：MCP 里有的，对话里也得有（kb_stats 除外，模型用不上）。"""
    mcp_names = {t["name"] for t in mcp_curriculum.list_tools()}
    for name in KB_TOOLS:
        assert name in mcp_names, f"{name} 在 MCP 工具表里不见了"
        assert tools.TOOL_SPECS[name]["desc"] == next(
            t["description"] for t in mcp_curriculum.list_tools() if t["name"] == name)


def test_prompt_forbids_claiming_there_is_no_tool():
    """那次翻车的原话必须被系统提示词明确否掉，否则模型还会这么说。"""
    sys_prompt = dialogue._proposal_system()
    assert "没有能检索培养方案的工具" in sys_prompt
    for name in KB_TOOLS:
        assert name in sys_prompt


def test_dept_alias_targets_really_exist():
    """简称只能指到库里真实存在的院系：写错了就会给出一个「像是查到了」的答案。"""
    depts = {c.get("院系", "") for c in curriculum.cards()}
    for short, full in curriculum.DEPT_ALIAS.items():
        assert full in depts, f"简称「{short}」指向的「{full}」在知识库里不存在"


# ---------- 按院系问专业（用户原话那种问法） ----------


@pytest.mark.parametrize("q", ["信管", "信息管理系"])
def test_dept_query_lists_all_majors(q):
    uid = make_user()
    r = tools.run(uid, {"tool": "major_lookup", "args": {"query": q}})
    majors = [c["专业"] for c in r["命中"]]
    assert r["ok"] is True and "院系" in r["kind"] and r["院系"] == "信息管理系"
    assert majors == ["信息管理与信息系统专业（文理科生）", "图书馆学专业", "大数据管理与应用专业"]
    assert "以院系教务" in r["说明"], "分流的名额/口径要说清以教务为准"


def test_full_sentence_query_still_finds_the_department():
    """模型常把整句当 query 传（「信管有哪些专业分流」）——代码从原话里抠名字再查一次。"""
    uid = make_user()
    r = tools.run(uid, {"tool": "major_lookup", "args": {}},
                  context={"query_hint": "信管有哪些专业分流"})
    assert r["ok"] is True and r["query"] == "信管", r
    assert r["query_from"] == "user_message"
    assert len(r["命中"]) == 3


def test_unknown_major_says_so_and_states_coverage():
    uid = make_user()
    r = tools.run(uid, {"tool": "major_lookup", "args": {"query": "量子玄学专业"}})
    assert r["ok"] is True and r["kind"] == "未命中" and r["命中"] == []
    assert "医学部" in r["说明"], "没查到必须同时交代覆盖边界，别让用户以为北大没有这个专业"


def test_missing_query_fails_cleanly():
    uid = make_user()
    r = tools.run(uid, {"tool": "major_lookup", "args": {}})
    assert r["ok"] is False and "query" in r["error"]


# ---------- 专业详情 ----------


def test_major_detail_gives_credits_and_required_courses():
    uid = make_user()
    r = tools.run(uid, {"tool": "major_detail", "args": {"name": "大数据管理与应用专业"}})
    assert r["ok"] is True and r["卡片"]["院系"] == "信息管理系"
    assert r["学分结构"]["毕业总学分"] == "131～137学分"
    assert len(r["必修课"]) >= 10 and all(c["课程名"] for c in r["必修课"])
    assert "检索别名" not in r["卡片"], "检索用的同义词表不该占模型上下文"


def test_major_detail_miss_keeps_the_boundary_note():
    uid = make_user()
    r = tools.run(uid, {"tool": "major_detail", "args": {"name": "量子玄学专业"}})
    assert r["ok"] is False and "医学部" in r["说明"]


# ---------- 成绩单认院系：课名 → 课号 ----------


def test_match_transcript_uses_the_stored_transcript():
    """画像里录过成绩单就不用模型抄课号：代码拿课名反查课号（成绩单里本来就没有课号）。"""
    uid = make_user()
    names = fill_transcript(uid)
    r = tools.run(uid, {"tool": "match_transcript", "args": {}})
    assert r["ok"] is True and r["source"] == "transcript"
    assert r["院系排名"][0]["院系"] == "经济学院"
    assert r["识别到课号"] >= len(names) // 2
    assert "课名" in r["note"]


def test_match_transcript_without_anything_is_honest():
    uid = make_user()
    r = tools.run(uid, {"tool": "match_transcript", "args": {}})
    assert r["ok"] is True and r["has_transcript"] is False and r["院系排名"] == []


def test_match_transcript_accepts_model_supplied_codes():
    uid = make_user()
    codes = [c["课号"] for m in curriculum.plans()["经济学专业"]["课程表"]
             for c in m["课程"] if c.get("课号")][:16]
    r = tools.run(uid, {"tool": "match_transcript", "args": {"codes": codes}})
    assert r["ok"] is True and r["source"] == "model"
    assert r["院系排名"][0]["院系"] == "经济学院"


def test_match_transcript_accepts_course_names_from_the_user():
    """用户说的是课名（「我学过这些课」），模型多半原样传进 codes：代码自己查索引换成课号。"""
    uid = make_user()
    names = [c["课程名称"] for m in curriculum.plans()["经济学专业"]["课程表"]
             for c in m["课程"] if c.get("课程名称")][:16]
    r = tools.run(uid, {"tool": "match_transcript", "args": {"codes": names}})
    assert r["ok"] is True and r["source"] == "model_names"
    assert r["院系排名"][0]["院系"] == "经济学院"
    assert "课名" in r["note"]


def test_match_transcript_says_so_when_names_are_unknown():
    uid = make_user()
    r = tools.run(uid, {"tool": "match_transcript", "args": {"codes": ["量子玄学导论"]}})
    assert r["ok"] is True and r["院系排名"] == [] and "认不出" in r["note"]


def test_codes_for_names_does_not_guess():
    """反查只认「归一后完全相同」，认不出来就如实列出来。

    括号和空格要归一（成绩单印「线性代数(B)」、方案原文写「线性代数（B）」）；
    但**不做模糊匹配**：库里只有「高等数学（B）（一）/（二）」这种分学期的名字，
    写「高等数学B」就该认不出来，而不是随手挑一个学期的课号。
    """
    half = curriculum.codes_for_names(["线性代数（B）"])
    full = curriculum.codes_for_names(["线性代数(B)"])
    assert half["codes"] and half["codes"] == full["codes"]
    looked = curriculum.codes_for_names(["高等数学B", "这门课不存在xyz"])
    assert looked["codes"] == []
    assert looked["missed"] == ["高等数学B", "这门课不存在xyz"]
    assert all(c.isdigit() and len(c) == 8 for c in half["codes"])


# ---------- 降级路径 ----------


def test_fallback_reply_understands_curriculum_results():
    text = dialogue._tool_fallback_reply({"tool": "major_lookup", "ok": True, "命中": [
        {"专业": "图书馆学专业"}, {"专业": "大数据管理与应用专业"}]})
    assert "图书馆学专业" in text and "候选" in text


def test_fallback_reply_for_unknown_shape_does_not_dump_a_dict():
    text = dialogue._tool_fallback_reply({"tool": "major_lookup", "ok": True, "kind": "未命中",
                                          "命中": [], "近名": ["哲学专业"]})
    assert "没有合适的结果" in text


# ---------- 整轮对话：模型决定调工具，代码执行 ----------


def test_turn_executes_the_curriculum_tool_and_reply_sees_it(monkeypatch):
    uid = make_user()
    seen: dict[str, str] = {}

    def fake_chat_json(system, user, **kw):
        if kw.get("tag") == "dialogue.reply":
            seen["reply_prompt"] = user
            return {"reply": "信管这三个专业是…", "next_action": None}
        return {
            "understanding": {"gist": "用户问信管的分流", "signals": [], "corrections": []},
            "memory_ops": [],
            "tool_intent": {"tool": "major_lookup", "args": {"query": "信管"}},
            "dialogue": {"move": "answer", "reason": "要先查知识库", "reply": None,
                         "offered_actions": []},
            "next_action": None,
        }

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_json", fake_chat_json)

    r = dialogue.turn(uid, "信管有哪些专业分流")
    assert r["tool_results"] and r["tool_results"][0]["tool"] == "major_lookup"
    assert r["tool_results"][0]["ok"] is True
    # 工具结果必须真的进到调用②里，否则模型只能靠印象编
    assert "图书馆学专业" in seen["reply_prompt"] and "大数据管理与应用专业" in seen["reply_prompt"]
    assert r["reply"] == "信管这三个专业是…"
    assert r["trace"]["tool"] == "major_lookup" and r["trace"]["tool_ok"] is True
