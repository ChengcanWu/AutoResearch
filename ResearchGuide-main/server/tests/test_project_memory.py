# -*- coding: utf-8 -*-
"""项目记忆：一个项目 = 一个文件夹。

用户的原话：「这里的存储感觉不是很智能，既然这些都归 Kotoba·AI 的大项目，
为什么要这么零碎的存储呢？不能搞大项目记忆吗？同时也支持对原来的记忆进行
增删改，不然后面记忆越来越多了」

所以这里要同时钉住两件看起来矛盾的事：
  1. 一个项目在界面上是**一张卡**（不零碎）
  2. 每条属性在存储上**仍然是独立事实**（可单独改删、各有证据、各有有效期）

做法是「实体 + 属性」，不是二选一。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

SERVER = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))

import memory  # noqa: E402
import store  # noqa: E402
from schemas import UserFact  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.init_db()


@pytest.fixture()
def uid():
    return store.create_user("项目")["uid"]


def put(uid, key, value, source="declared", affects="task_difficulty", ttl=None):
    f = UserFact(user_id=uid, category="practice", key=key, value=value,
                 confidence=0.6, source=source, affects=affects,
                 evidence=[{"type": "dialogue_turn", "quote": value}],
                 status="active", valid_until=ttl)
    store.add_fact(f)
    return f


def seed_kotoba(uid):
    """用户真实那几条，改写成项目形态。"""
    return {
        "entity": put(uid, "project:kotoba", "KotobaAI，一个 Agent 日语学习项目"),
        "traction": put(uid, "project:kotoba.traction", "有官网 kotoba.com.cn，全平台累计下载 400+"),
        "stack": put(uid, "project:kotoba.stack", "VibeCoding 开发：自己明确业务逻辑，代码由 AI 实现"),
        "blocker": put(uid, "project:kotoba.blocker", "代码是 AI 写的，复杂逻辑自己读不顺"),
    }


def test_project_keys_are_writable_by_the_model(uid):
    """project: 必须是模型写得进去的 key，否则它又会拆回 capability:。"""
    spec = memory.spec_for("project:kotoba.blocker")
    assert spec is not None, "project: 得在 registry 里"
    assert "declared" in spec.sources and "inferred" in spec.sources
    assert memory.layer_of("project:kotoba") == "practice", \
        "项目属于「当前实践」——它是此刻手头在做的事"


def test_a_project_is_one_card(uid):
    """界面上：一个项目一张卡，属性是子行（用户要的「大文件夹」）。"""
    seed_kotoba(uid)
    cards = memory.project_cards(uid)
    assert len(cards) == 1, f"Kotoba 的 4 条应该聚成 1 张卡，而不是 {len(cards)} 张"
    card = cards[0]
    assert card["slug"] == "kotoba"
    assert len(card["facts"]) == 4
    labels = [card["attr_label"][f.id] for f in card["facts"]]
    assert "卡点" in labels and "成果" in labels
    # 属性按固定顺序排，读起来像一张介绍，而不是随机的几行
    assert labels.index("成果") < labels.index("卡点")


def test_但存储上每条仍然是独立事实(uid):
    """可单独改删——这正是「不能做成一块 blob」的原因。"""
    ids = seed_kotoba(uid)
    facts = store.list_facts(uid, statuses=["active"])
    assert len(facts) == 4, "4 条属性 = 4 行事实，而不是 1 行 JSON"
    # 每条都能单独改（走真实写入路径：先过闸门，再落库）。
    # replace 是按 target_fact_id 定位到**具体那一行**的——这正是
    # 「属性是独立事实、可以只改其中一条」的意思。
    op = {"op": "replace", "key": "project:kotoba.blocker",
          "target_fact_id": ids["blocker"].id,
          "value": "接口对接总是失败", "affects": "task_difficulty",
          "evidence_quote": "接口对接总是失败"}
    accepted, rejected = memory.validate_ops(
        uid, [op], ["接口对接总是失败"] + [f.value for f in facts])
    assert not rejected, f"这条应该写得进去，被拒了：{rejected}"
    memory.apply_ops(uid, accepted, "")
    cards = memory.project_cards(uid)
    blocker = next(f for f in cards[0]["facts"] if f.key.endswith(".blocker"))
    assert "接口对接" in blocker.value
    assert len(cards[0]["facts"]) == 4, "改一条不该影响同项目其它属性"
    # 每条都能单独删（删一条不影响同项目其它属性）
    store.update_fact(ids["traction"].id, status="deleted")
    assert len(memory.project_cards(uid)[0]["facts"]) == 3


def test_two_projects_are_two_cards(uid):
    """再做一个项目就是第二个文件夹，不会混进第一个。"""
    seed_kotoba(uid)
    put(uid, "project:campusmap", "校园地图小程序")
    put(uid, "project:campusmap.stage", "只做到能看教室空闲")
    cards = memory.project_cards(uid)
    assert {c["slug"] for c in cards} == {"kotoba", "campusmap"}
    assert all(c["name"] for c in cards), "每张卡都要有名字"


def test_a_project_is_injected_whole_never_half(uid):
    """整卡进出：不能只把「成果」给它、却不给「卡点」。

    只知道项目有 400+ 下载而不知道代码读不顺，会给出错得离谱的下一步。
    """
    seed_kotoba(uid)
    grouped, _ = memory.recall_grouped(uid, "KotobaAI")
    keys = {f.key for f in grouped.get("practice", [])}
    assert "project:kotoba" in keys
    assert "project:kotoba.blocker" in keys, "卡点必须一起进来"
    assert "project:kotoba.traction" in keys
    assert "project:kotoba.stack" in keys


def test_a_project_never_appears_half_even_when_the_budget_is_tight(uid):
    """预算再紧也不许把项目切成一半——这里故意把 practice 预算压到 1。"""
    seed_kotoba(uid)
    grouped, _ = memory.recall_grouped(uid, "KotobaAI", budgets={"practice": 1})
    got = {f.key for f in grouped.get("practice", [])}
    assert len(got) == 4, f"预算 1 也必须整组进来，实际只有 {got}"


def test_an_unrelated_project_is_not_dragged_in(uid):
    """整卡进出只对**被召回的那个项目**生效，不能把所有项目都拖进来。

    注意要用紧预算才有意义：practice 预算宽裕时，另一个项目本来就能靠自己的
    相关度进来，那不算「被拖进来」。预算压到 1 之后，只有 kotoba 有相关性，
    这时再检查 campusmap 有没有被顺带拽进来。
    """
    seed_kotoba(uid)
    put(uid, "project:campusmap", "校园地图小程序")
    put(uid, "project:campusmap.stage", "只做到能看教室空闲")
    grouped, _ = memory.recall_grouped(uid, "KotobaAI", budgets={"practice": 1})
    keys = {f.key for f in grouped.get("practice", [])}
    assert "project:kotoba" in keys
    assert "project:campusmap" not in keys, "没被问到的项目不该被带进来"
    assert "project:campusmap.stage" not in keys


def test_projects_count_as_current_practice_in_the_ladder(uid):
    """一个在做的项目就算「当前实践有数了」，阶梯不该还在这儿问。"""
    put(uid, "grade", "大二")
    before = memory.ladder_state(uid)
    practice_before = next(L for L in before["layers"] if L["layer"] == "practice")
    assert not practice_before["known"], "没有项目时这层是空的"

    put(uid, "project:kotoba", "KotobaAI，一个 Agent 日语学习项目")
    after = memory.ladder_state(uid)
    practice_after = next(L for L in after["layers"] if L["layer"] == "practice")
    assert practice_after["known"], "有了项目就算这层有数了"


def test_project_shows_up_in_the_coverage_board(uid):
    """「核对」页要有「在做的项目」这一格，否则用户不知道这里能填。"""
    groups = {g[0]: g for g in memory.COVERAGE_GROUPS}
    practice = groups["practice"]
    slots = [s.key for s in practice[3]]
    assert "project:" in slots, f"当前实践这组里要有项目，实际是 {slots}"

    put(uid, "project:kotoba", "KotobaAI")
    cov = memory.coverage(uid)
    grp = next(g for g in cov["groups"] if g["group"] == "practice")
    slot = next(s for s in grp["slots"] if s["key"] == "project:")
    assert slot["filled"], "填了就要显示为已填"
    assert slot["value"] == "KotobaAI", "要显示真实值，不能显示 key"


def test_an_empty_attribute_is_not_invented(uid):
    """没提到的属性不要建空条目——空属性会显得我们知道得比实际多。"""
    put(uid, "project:kotoba", "KotobaAI")
    put(uid, "project:kotoba.blocker", "读不顺 AI 写的复杂逻辑")
    card = memory.project_cards(uid)[0]
    assert len(card["facts"]) == 2
    assert not any("next" in f.key for f in card["facts"])


def test_project_ttl_is_longer_than_this_week_practice(uid):
    """项目比「这周在做什么」活得久，但也不该永久有效。"""
    proj = memory.spec_for("project:kotoba")
    cur = memory.spec_for("current:kotobaai")
    assert proj.default_ttl_days and cur.default_ttl_days
    assert proj.default_ttl_days > cur.default_ttl_days, \
        "项目的有效期应该比当前的课/事更长"


def test_project_slug_parser_handles_both_forms(uid):
    assert memory._project_slug("project:kotoba") == "kotoba"
    assert memory._project_slug("project:kotoba.blocker") == "kotoba"
    assert memory._project_slug("capability:vibecoding") == ""
    assert memory._project_slug("project:") == ""


# ---------- 名字里带点的项目 ----------
#
# key 里**允许出现点**（_SLUG_RE 放行 `.` 和 `-`），所以
#     project:my.app.blocker
# 按第一个点切会得到实体 "my"、属性 "app.blocker"，
# 于是 project:my.app 和 project:my.other 塌成同一个项目、属性互相串。
# 按最后一个点切又会在 project:kotoba.next 上把实体切成 "kotoba.next"。
# 正确做法是用属性表消歧：**只在最后一段是已知属性时才切**。


@pytest.mark.parametrize("key,slug,attr", [
    ("project:kotoba", "kotoba", ""),
    ("project:kotoba.blocker", "kotoba", "blocker"),
    ("project:my.app", "my.app", ""),
    ("project:my.app.blocker", "my.app", "blocker"),
    # 未知属性：整段当实体。宁可多建一张卡，也不要把两条无关的东西并到一起
    ("project:my.app.why", "my.app.why", ""),
    ("project:", "", ""),
    ("capability:vibecoding", "", ""),
])
def test_project_parts_disambiguates_dots(key, slug, attr):
    assert memory._project_parts(key) == (slug, attr), f"{key} 切错了"


def test_two_dotted_projects_do_not_merge_into_one_card(uid):
    """这是「名字里带点」真正会造成的坏事：两张卡合成一张。"""
    put(uid, "project:my.app", "我的 App")
    put(uid, "project:my.app.blocker", "登录一直做不通")
    put(uid, "project:my.other", "另一个项目")
    put(uid, "project:my.other.blocker", "数据源找不到")

    cards = memory.project_cards(uid)
    slugs = [c["slug"] for c in cards]
    assert slugs == ["my.app", "my.other"], f"两个项目被合掉了：{slugs}"

    by = {c["slug"]: c for c in cards}
    assert by["my.app"]["name"] == "我的 App"
    assert by["my.other"]["name"] == "另一个项目"
    # 属性不能串：my.app 的卡里不该出现 my.other 的卡点
    app_vals = " ".join(f.value for f in by["my.app"]["facts"])
    assert "登录一直做不通" in app_vals
    assert "数据源找不到" not in app_vals, "两个项目的属性串了"


def test_dotted_project_attribute_labels_match_its_own_card(uid):
    """卡片名和属性名必须来自同一个切分函数，否则显示会对不上。"""
    put(uid, "project:my.app", "我的 App")
    put(uid, "project:my.app.blocker", "登录一直做不通")
    card = next(c for c in memory.project_cards(uid) if c["slug"] == "my.app")
    labels = {f.value: card["attr_label"][f.id] for f in card["facts"]}
    assert labels["我的 App"] == "是什么"
    assert labels["登录一直做不通"] == "卡点", labels


def test_dotted_project_whole_card_still_injected_together(uid):
    """整卡进出的规则对带点的项目同样成立。"""
    put(uid, "project:my.app", "我的 App")
    put(uid, "project:my.app.blocker", "登录一直做不通")
    selected = [f for f in memory.active_facts(uid) if f.key == "project:my.app"]
    out = memory._complete_project_groups(selected, memory.active_facts(uid))
    keys = {f.key for f in out}
    assert "project:my.app.blocker" in keys, "整卡进出对带点的项目失效了"
