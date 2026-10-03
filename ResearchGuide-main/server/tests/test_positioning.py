# -*- coding: utf-8 -*-
"""定位层的离线测试：边清单、竞争地图（需求的 k 与滞后）、定位陈述检查、下注组合、每日微调。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import arxiv  # noqa: E402
import positioning  # noqa: E402
import reading  # noqa: E402
import store  # noqa: E402
from schemas import UserFact  # noqa: E402
from test_reading import DIMS, GOOD, PAPER  # noqa: E402

AID = "2310.17623"  # 开放问题 single-dup / multi-test / shuffle 出自这篇


@pytest.fixture(autouse=True)
def offline(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "p.db")
    store.init_db()
    monkeypatch.setattr(arxiv, "fulltext", lambda aid: {**PAPER, "id": arxiv.clean_id(aid)})


def user(with_card: bool = True) -> str:
    u = store.create_user("t")["uid"]
    if with_card:
        assert reading.submit_card(u, "llm-eval", AID, GOOD, DIMS)["status"] == "pass"
    return u


def test_edges_merge_ledger_and_self_reports():
    u = user()
    store.add_fact(UserFact(user_id=u, category="background", key="hometown", value="广东人，粤语母语", source="declared", status="active"))
    e = positioning.edges(u)
    assert e["proven"] == 1 and e["edges"][0]["status"] == "proven" and e["edges"][0]["arxiv_id"] == AID
    assert e["suggest"][0]["text"] == "广东人，粤语母语"
    e = positioning.add_edge(u, "course", "修过《数理统计》")
    e = positioning.add_edge(u, "skill", "学习能力强")
    assert [x["generic"] for x in e["edges"] if x["status"] == "declared"] == [False, True]
    with pytest.raises(positioning.PositionError):
        positioning.add_edge(u, "course", "修过《数理统计》")
    with pytest.raises(positioning.PositionError):
        positioning.delete_edge(u, e["edges"][0]["id"])  # 账本里的不能删
    assert positioning.delete_edge(u, e["edges"][-1]["id"])["declared"] == 1


def test_map_keeps_kit_order_and_says_data_insufficient_when_pool_small():
    u = user()
    positioning.add_edge(u, "course", "修过《数理统计》")
    m = positioning.competition_map(u, "llm-eval")
    assert [r["order"] for r in m["rows"]] == list(range(len(m["rows"])))  # 不按冷门排
    assert all(r["demand"]["band"] == "数据不足" and r["supply"]["status"] == "未知" for r in m["rows"])
    multi = next(r for r in m["rows"] if r["id"] == "multi-test")
    assert multi["read"] and {e["text"] for e in multi["my_edges"]} >= {"修过《数理统计》"}
    assert m["rarity"]["status"] == "数据不足"


def test_demand_counts_only_committed_lagged_statements(monkeypatch):
    monkeypatch.setattr(positioning, "POOL_MIN", 6)
    us = [user() for _ in range(6)]
    for u in us[:5]:
        positioning.save_statement(u, "llm-eval", "multi-test", "污染检验的多重比较校正", [positioning.edges(u)["edges"][0]["id"]])
    lagged = positioning.competition_map(us[5], "llm-eval")
    assert next(r for r in lagged["rows"] if r["id"] == "multi-test")["demand"]["band"] == "冷"  # 还在滞后期内，不计
    monkeypatch.setattr(positioning, "_cutoff", lambda: "9999")
    rows = positioning.competition_map(us[5], "llm-eval")["rows"]
    assert next(r for r in rows if r["id"] == "multi-test")["demand"]["band"] == "热"
    assert next(r for r in rows if r["id"] == "single-dup")["demand"]["band"] == "冷"


def test_statement_checks_point_out_without_scoring():
    u = user(with_card=False)
    with pytest.raises(positioning.PositionError):
        positioning.save_statement(u, "llm-eval", "multi-test", "多重比较校正问题", [])
    gen = positioning.add_edge(u, "skill", "学习能力强")["edges"][0]["id"]
    r = positioning.review_statement(u, "llm-eval", "multi-test", "做研究", [gen])
    by = {c["key"]: c for c in r["checks"]}
    assert not r["can_save"] and not by["x_text"]["pass"]
    r = positioning.review_statement(u, "llm-eval", "multi-test", "大模型污染检验的多重比较校正", [gen])
    by = {c["key"]: c for c in r["checks"]}
    assert r["can_save"] and not r["portfolio_ready"]
    assert not by["y_proven"]["pass"] and "常见" in by["y_generic"]["note"] and not by["x_read"]["pass"]
    reading.submit_card(u, "llm-eval", AID, GOOD, DIMS)
    proof = next(e["id"] for e in positioning.edges(u)["edges"] if e["status"] == "proven")
    s = positioning.save_statement(u, "llm-eval", "multi-test", "大模型污染检验的多重比较校正", [proof])
    assert s["portfolio_ready"] and s["version"] == 1 and s["sentence"].startswith("我是能做「")
    assert positioning.save_statement(u, "llm-eval", "multi-test", "大模型污染检验的多重比较校正（GPQA）", [proof])["version"] == 2


def test_bets_cap_and_concentration_warnings():
    u = user(with_card=False)
    for name in ("X 组", "Y 组"):
        b = positioning.add_bet(u, name, "group", "reach", "llm-eval", "judge-safety")
    notes = " ".join(c["note"] for c in b["checks"])
    assert "全是「冲」" in notes and "同一个子方向" in notes and "保" in notes
    positioning.add_bet(u, "本研公开题目", "program", "safety")
    with pytest.raises(positioning.PositionError):
        positioning.add_bet(u, "Z 组", "group", "match")
    bid = b["active"][0]["id"]
    with pytest.raises(positioning.PositionError):
        positioning.close_bet(u, bid, "missed", "")
    after = positioning.close_bet(u, bid, "missed", "组里这学期不收大一")
    assert len(after["active"]) == 2 and after["closed"][0]["reason"] == "组里这学期不收大一"


def test_daily_tweak_points_to_one_small_action():
    u = user(with_card=False)
    assert positioning.daily_tweak(u, "llm-eval", []) is None  # 没读过卡，不催写定位
    reading.submit_card(u, "llm-eval", AID, GOOD, DIMS)
    assert positioning.daily_tweak(u, "llm-eval", [])["view"] == "position"
    proof = positioning.edges(u)["edges"][0]["id"]
    positioning.save_statement(u, "llm-eval", "multi-test", "大模型污染检验的多重比较校正", [proof])
    assert positioning.daily_tweak(u, "llm-eval", []) is None
    kept = [{"title": "Controlling False Discoveries in Contamination Audits via Multiple Testing", "why": "和多重比较有关"}]
    assert positioning.daily_tweak(u, "llm-eval", kept)["view"] == "read"


CHANNELS = {
    "checked_at": "2026-10-03", "signal_kinds": {"review": "同行评审与争议", "experience": "经验帖"},
    "blind_spots": {"ai": "中文圈常漏评审讨论", "career": "英文圈常漏经验帖"},
    "channels": [
        {"id": "openreview", "name": "OpenReview", "url": "https://openreview.net/", "search_hint": "", "directions": ["ai"],
         "circle": "英文圈", "kind": "评审平台", "signals": ["review"], "good_for": "看审稿人怎么挑毛病", "caveat": "只覆盖部分会议",
         "cadence": "weekly", "access": "境内直连", "feed": "", "verified": True, "verified_how": "test"},
        {"id": "zhihu-ml", "name": "知乎 · 机器学习话题", "url": "https://www.zhihu.com/", "search_hint": "", "directions": ["ai"],
         "circle": "中文圈", "kind": "问答", "signals": ["review"], "good_for": "中文解读", "caveat": "二手转述",
         "cadence": "daily", "access": "境内直连", "feed": "", "verified": True, "verified_how": "test"},
        {"id": "xhs-camp", "name": "小红书 · 夏令营经验", "url": "", "search_hint": "北大 夏令营 经验", "directions": ["career"],
         "circle": "中文圈", "kind": "社交媒体", "signals": ["experience"], "good_for": "哪些组今年收人", "caveat": "幸存者偏差",
         "cadence": "weekly", "access": "境内直连", "feed": "", "verified": False, "verified_how": "test"},
        {"id": "nber", "name": "NBER", "url": "https://www.nber.org/", "search_hint": "", "directions": ["econ"],
         "circle": "英文圈", "kind": "预印本", "signals": ["review"], "good_for": "-", "caveat": "-",
         "cadence": "weekly", "access": "境内直连", "feed": "", "verified": True, "verified_how": "test"},
    ],
}


def test_channel_map_marks_reads_and_blind_spots(tmp_path, monkeypatch):
    path = tmp_path / "channels.json"
    path.write_text(__import__("json").dumps(CHANNELS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(positioning, "CHANNELS", path)
    u = user(with_card=False)
    m = positioning.channel_map(u, "ai")
    assert [c["id"] for c in m["channels"]] == ["openreview", "zhihu-ml", "xhs-camp"]  # 不混进别的方向
    assert m["other_circle_unread"] == ["OpenReview"] and m["channels"][0]["band"] == "数据不足"
    m = positioning.toggle_channel(u, "zhihu-ml", True, "ai")
    assert m["summary"]["中文圈"] == {"read": 1, "total": 1}
    edge = next(e for e in positioning.edges(u)["edges"] if e["kind"] == "source")
    assert edge["key"] == "channel:zhihu-ml"  # 跨用户可比，算稀有度用
    positioning.toggle_channel(u, "zhihu-ml", True, "ai")  # 重复点不重复加
    assert sum(e["kind"] == "source" for e in positioning.edges(u)["edges"]) == 1
    assert not positioning.toggle_channel(u, "zhihu-ml", False, "ai")["channels"][1]["read"]
    with pytest.raises(positioning.PositionError):
        positioning.toggle_channel(u, "nope", True, "ai")
