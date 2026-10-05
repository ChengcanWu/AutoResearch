# -*- coding: utf-8 -*-
"""院系-专业知识库接口的离线测试：不联网、不调模型，只查表。

运行：uv run --no-project --with pytest --with fastapi --with pydantic --with httpx pytest server/tests
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import curriculum  # noqa: E402


def test_stats_nonempty():
    s = curriculum.stats()
    assert s["ok"] and s["专业卡"] > 150 and s["培养方案"] > 150
    assert s["辅修双专业卡"] == 98
    assert s["辅修方案"] == 98          # 别按 `专业` 字段取键，会把双专业/辅修并成 56 条


@pytest.mark.parametrize("q,expect", [
    ("经济学专业", "唯一"),               # 章节名
    ("经济学", "专业簇"),                 # 口语 → 兄弟专业并列
    ("软件工程专业", "唯一"),              # 章节名是「软件工程专业培养方案」，靠别名兜住
    ("信息与计算科学", "专业簇"),
    ("印地语专业", "唯一"),               # 只有专业目录骨架、没有培养方案
])
def test_find_major_kinds(q, expect):
    r = curriculum.find_major(q)
    assert r["ok"] and expect in r["kind"], r
    assert r["命中"]


def test_find_major_unknown_suggests():
    r = curriculum.find_major("量子玄学专业")
    assert r["ok"] and r["kind"] == "未命中" and r["近名"]


def test_find_major_empty_query():
    assert curriculum.find_major("")["ok"] is False


def test_major_detail_has_courses_and_siblings():
    d = curriculum.major_detail("经济学专业")
    assert d["ok"]
    assert d["卡片"]["院系"] == "经济学院" and d["卡片"]["卷"] == "文科卷"
    assert d["学分结构"]["毕业总学分"]
    codes = [c["课号"] for c in d["必修课"]]
    assert "00130201" in codes and all(c["课程名"] for c in d["必修课"])
    assert d["必修课"][0]["模块"] == "2.1.1 数学组"
    assert "金融学专业" in d["兄弟专业"]


def test_major_detail_skips_public_modules():
    """信科的 `1.1 公共必修课` 里放着本专业必修课（计算概论A），不能一刀切按模块号剔除；
    而思政/体育/英语那类模块必须剔除。"""
    d = curriculum.major_detail("软件工程专业")
    mods = {c["模块"] for c in d["必修课"]}
    assert not any("思想政治" in m or "体育" in m or "大学英语" in m for m in mods), mods


def test_parse_codes_from_text_and_list():
    assert curriculum.parse_codes("00130201 高等数学B 5学分") == ["00130201"]
    assert curriculum.parse_codes(["02530001 微观经济学", "02530001"]) == ["02530001"]
    assert curriculum.parse_codes([]) == []


def test_match_recognises_own_major():
    plan = curriculum.plans()["经济学专业"]
    codes = [c["课号"] for m in plan["课程表"] for c in m["课程"] if c.get("课号")][:20]
    m = curriculum.match(codes)
    assert m["ok"] and m["院系排名"][0]["院系"] == "经济学院"
    assert m["专业排名"][0]["专业"] == "经济学专业"
    assert m["专业排名"][0]["分"] == 1.0
    assert m["专业排名"][0]["还缺"] == []


def test_match_low_grades_keeps_department():
    plan = curriculum.plans()["经济学专业"]
    codes = [c["课号"] for m in plan["课程表"] for c in m["课程"] if c.get("课号")][:20]
    m = curriculum.match(codes, low_only=True)
    assert m["院系排名"][0]["院系"] == "经济学院"


def test_match_rejects_noise():
    m = curriculum.match([])
    assert m["ok"] is False and m["专业排名"] == []


def test_match_department_rows_have_hits():
    plan = curriculum.plans()["地球化学专业"]
    codes = [c["课号"] for m in plan["课程表"] for c in m["课程"] if c.get("课号")][:12]
    m = curriculum.match(codes)
    assert all(d["命中数"] > 0 for d in m["院系排名"])


def test_minor_lookup_and_by_dept():
    r = curriculum.find_minor("法学辅修")
    assert r["命中"][0]["类型"] == "辅修" and r["命中"][0]["总学分"] == "30学分"
    by_dept = curriculum.find_minor(dept="工学院")
    assert by_dept["总数"] > 10
    assert curriculum.minor_plans()


def test_minor_replacement_courses_present():
    """替代课程是辅修层独有的：主修修过同名必修课时改修这些。"""
    with_repl = [c for c in curriculum.cards(True) if c.get("替代课程")]
    assert with_repl, "辅修层应当有带替代课程的条目"


def test_course_detail():
    d = curriculum.course_detail("02530060")
    assert d["ok"] and d["课程名"] == "微观经济学"
    assert "经济学专业" in d["必修它的专业"]
    assert d["同前缀有多少专业在必修"] is not None
    assert curriculum.course_detail("abc")["ok"] is False
