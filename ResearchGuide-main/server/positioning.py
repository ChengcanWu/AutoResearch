# -*- coding: utf-8 -*-
"""定位层：边清单、竞争地图、定位陈述、下注组合（docs/DESIGN_PROPOSAL.md §1D）。

学东西越来越便宜，「会不会」不再是瓶颈；这一层帮学生看清自己能赢在哪，并写出一句有证据的「为什么是我」。

规矩：
- 一切数值和检查由规则算；模型不推荐生态位、不替学生写陈述。
- 需求只数有投入的人（在该工具包有过线阅读卡、陈述指向这里），滞后一周；人数 < K_MIN 不报数，
  池子 < POOL_MIN 写「数据不足」而不写「冷」，免得把「平台人少」读成「没人做」。
- 供给不知道就写「未知」并给去哪问；势头来自离线核对的 arXiv 计数（kit_momentum.py），只作修正。
- 不给「最冷门」排行：地图按工具包顺序或学生自选的键排，每行都和学生自己的边并排。
"""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from itertools import combinations
from typing import Any

import reading
import store
from schemas import now_iso

EDGE_KINDS = {"skill": "技能", "course": "课程组合", "language": "语言", "background": "背景与经历",
              "source": "信息源（你常看、同学少看的）", "access": "数据或社群接入", "time": "时间", "tool": "工具与算力"}
FACT_TO_KIND = {"background": "background", "experience": "background", "capability": "skill"}
# 在哪个申请池里都常见、造假成本为零的理由（信号表最后一行）；只提示，不拦
GENERIC = ["热爱科研", "热爱", "学习能力", "自学能力", "认真", "负责", "吃苦", "执行力", "沟通", "团队合作", "好奇心",
           "逻辑思维", "会python", "python基础", "编程基础", "数学基础", "英语好", "绩点", "gpa", "成绩好"]
CONCRETE = ["中文", "英文", "多语", "方言", "数学", "代码", "医学", "法律", "金融", "安全", "裁判", "污染", "基准", "数据集",
            "检验", "校正", "打乱", "排行", "人工", "众包", "偏见", "鲁棒", "多模态", "图像", "语音", "小模型", "开源", "功效", "显著"]
K_MIN = 5          # 少于 5 人不报数
POOL_MIN = 20      # 同一工具包有过线卡的人少于这个数，地图写「数据不足」
LAG_DAYS = 7
MAX_BETS = 3
TIERS = {"reach": "冲", "match": "稳", "safety": "保"}
BET_KINDS = {"group": "进组", "program": "本研 / 科研计划", "contest": "竞赛", "project": "练手项目"}
OUTCOMES = {"got": "拿到了", "missed": "没拿到", "dropped": "主动放弃"}
X_MIN, X_MAX = 8, 60


CHANNELS = reading.ROOT / "knowledge" / "channels.json"
CIRCLES = ["中文圈", "英文圈"]


class PositionError(Exception):
    pass


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def is_generic(text: str) -> bool:
    t = _norm(text)
    return any(g in t for g in GENERIC)


# ---------- 边清单 ----------

def edges(uid: str) -> dict[str, Any]:
    """已证明的边从账本自动导入（不可手改）；自述的边由学生自己加。画像里记着的背景、经历给出一键导入。"""
    facts = store.list_facts(uid, ["active"])
    out = []
    for f in facts:
        if f.source != "behavior":
            continue
        ev = (f.evidence or [{}])[0]
        # 阅读卡的账本条目很长，边里用短名；其他作品照原文
        text = f"过线阅读卡《{ev['task_title']}》" if ev.get("type") == "reading_card" else f.value.removeprefix("已证明：")
        out.append({"id": f"fact:{f.id}", "kind": "skill", "text": text, "status": "proven", "source": "ledger",
                    "key": f.key or f.id, "arxiv_id": ev.get("arxiv_id", ""), "created_at": f.created_at})
    mine = store.list_edges(uid)
    for e in mine:
        out.append({"id": e["id"], "kind": e["kind"], "text": e["text"], "status": "declared", "source": "self",
                    "key": _self_key(e), "ref": e.get("ref", ""),
                    "evidence_url": e["evidence_url"], "created_at": e["created_at"]})
    for e in out:
        e["generic"] = is_generic(e["text"])
    have = {_norm(e["text"]) for e in mine}
    suggest = [{"kind": FACT_TO_KIND[f.category], "text": f.value, "from": "画像"} for f in facts
               if f.source != "behavior" and f.category in FACT_TO_KIND and _norm(f.value) not in have]
    return {"kinds": EDGE_KINDS, "edges": out, "suggest": suggest[:8],
            "proven": sum(e["status"] == "proven" for e in out), "declared": len(mine)}


def add_edge(uid: str, kind: str, text: str, evidence_url: str = "") -> dict[str, Any]:
    if kind not in EDGE_KINDS:
        raise PositionError("边的类别不对")
    text = (text or "").strip()
    if not 2 <= len(text) <= 60:
        raise PositionError("一条边写 2–60 字：具体到别人能核对，比如「粤语母语」「修过《数理统计》」")
    url = (evidence_url or "").strip()
    if url and not re.match(r"^https?://", url):
        raise PositionError("凭据链接要以 http:// 或 https:// 开头")
    if any(_norm(e["text"]) == _norm(text) for e in store.list_edges(uid)):
        raise PositionError("这条已经在清单里了")
    store.add_edge(uid, kind, text, url)
    return edges(uid)


def delete_edge(uid: str, edge_id: str) -> dict[str, Any]:
    if edge_id.startswith("fact:"):
        raise PositionError("已证明的边来自账本，不能在这里删")
    if not store.delete_edge(uid, edge_id):
        raise PositionError("没有这条边")
    return edges(uid)


def _self_key(row: dict[str, Any]) -> str:
    """自述边的比较键：信息源用 id（跨用户可比），其余用规范化文字。账本条目用它的 fact key。"""
    return f"channel:{row['ref']}" if row.get("ref") else _norm(row["text"])


def _peer_keys(uids: list[str]) -> list[set[str]]:
    """池子里每个人的边键，两条批量查询拿全（原来每人 edges() 一次、两个连接，一千人两千次）。"""
    proofs, rows = store.proof_keys_for(uids), store.edges_for(uids)
    return [proofs[u] | {_self_key(r) for r in rows[u]} for u in uids]


def combo_rarity(uid: str, kit_id: str) -> dict[str, Any]:
    """两两组合在同一工具包的池子里有多少人也有；k ≥ K_MIN 才计数，按档显示。"""
    pool = [u for u in store.kit_pool(kit_id) if u != uid]
    mine = edges(uid)["edges"]
    if len(pool) + 1 < POOL_MIN:
        return {"status": "数据不足", "why": f"这个工具包里有过线阅读卡的同学还不到 {POOL_MIN} 人，组合稀有度先不算"}
    others = _peer_keys(pool)
    pairs = []
    for a, b in combinations(mine, 2):
        n = sum(1 for keys in others if a["key"] in keys and b["key"] in keys)
        band = "罕见" if n < K_MIN else "少见" if n < 0.15 * len(pool) else "常见"
        pairs.append({"a": a["text"], "b": b["text"], "band": band})
    return {"status": "ok", "pairs": pairs}


# ---------- 信息源地图：这个方向的人在哪说话 ----------

def _channels() -> dict[str, Any]:
    if not CHANNELS.exists():
        return {"channels": [], "blind_spots": {}, "signal_kinds": {}, "checked_at": ""}
    return json.loads(CHANNELS.read_text(encoding="utf-8"))


def channel_map(uid: str, direction: str) -> dict[str, Any]:
    """按方向列信息源，标出学生常看的、没看的；常看的人多不多按 k 与池子规则给档位。"""
    data = _channels()
    mine = {e["ref"]: e["id"] for e in store.list_edges(uid) if e["kind"] == "source" and e.get("ref")}
    readers = store.channel_readers()
    pool = set().union(*readers.values()) if readers else set()
    enough = len(pool) >= POOL_MIN
    rows = []
    for c in data["channels"]:
        if direction not in c["directions"] and "career" not in c["directions"]:
            continue
        n = len(readers.get(c["id"], set()) - {uid})
        if not enough:
            band = "数据不足"
        else:
            band = "少有人看" if n < K_MIN else "常见" if n >= 0.3 * len(pool) else "有人看"
        rows.append({**c, "read": c["id"] in mine, "edge_id": mine.get(c["id"], ""), "band": band,
                     "group": "career" if direction not in c["directions"] else direction})
    summary = {circle: {"read": sum(1 for r in rows if r["circle"] == circle and r["read"] and r["group"] == direction),
                        "total": sum(1 for r in rows if r["circle"] == circle and r["group"] == direction)} for circle in CIRCLES}
    blind = [r["name"] for r in rows if not r["read"] and r["group"] == direction and r["circle"] != _main_circle(rows, direction)]
    return {"direction": direction, "channels": rows, "summary": summary, "signal_kinds": data.get("signal_kinds", {}),
            "blind_spot": data.get("blind_spots", {}).get(direction, ""), "career_blind_spot": data.get("blind_spots", {}).get("career", ""),
            "other_circle_unread": blind[:6], "checked_at": data.get("checked_at", ""), "access_note": data.get("access_note", ""),
            "pool_enough": enough}


def _main_circle(rows: list[dict[str, Any]], direction: str) -> str:
    """学生读得多的那一圈；一个都没标时当作中文圈，盲区先指英文圈。"""
    counts = {c: sum(1 for r in rows if r["circle"] == c and r["read"] and r["group"] == direction) for c in CIRCLES}
    return max(CIRCLES, key=lambda c: (counts[c], c == "中文圈"))


def toggle_channel(uid: str, channel_id: str, on: bool, direction: str) -> dict[str, Any]:
    c = next((x for x in _channels()["channels"] if x["id"] == channel_id), None)
    if not c:
        raise PositionError("没有这个信息源")
    mine = [e for e in store.list_edges(uid) if e["kind"] == "source" and e.get("ref") == channel_id]
    if on and not mine:
        store.add_edge(uid, "source", f"常看{c['name']}"[:60], "", channel_id)
    if not on:
        for e in mine:
            store.delete_edge(uid, e["id"])
    return channel_map(uid, direction)


# ---------- 竞争地图 ----------

def _matches(edge: dict[str, Any], o: dict[str, Any]) -> bool:
    if edge.get("arxiv_id") and edge["arxiv_id"] == o["arxiv_id"]:
        return True
    t = edge["text"].lower()
    return any(k.lower() in t for k in o.get("edge_keywords", []))


def _cutoff() -> str:
    return (dt.datetime.fromisoformat(now_iso().replace("Z", "+00:00")) - dt.timedelta(days=LAG_DAYS)).isoformat()


def competition_map(uid: str, kit_id: str) -> dict[str, Any]:
    k = reading.kit(kit_id)
    my = edges(uid)["edges"]
    pool = store.kit_pool(kit_id)
    enough = len(pool) >= POOL_MIN
    refs = store.statement_refs(kit_id, _cutoff()) if enough else {}
    members = set(pool)  # 原来在列表里逐个找，一万人时每行都要扫一遍
    demand_by_ref = Counter(ref for u, ref in refs.items() if u in members)
    passed = {c["arxiv_id"] for c in store.latest_cards(uid, kit_id) if c["status"] == "pass"}
    rows = []
    for i, o in enumerate(k["open_problems"]):
        if enough:
            n = demand_by_ref[o["id"]]
            demand = {"band": "冷" if n < K_MIN else "温" if n < 0.2 * len(pool) else "热", "why": "滞后一周；只数有过线卡、陈述指向这里的人"}
        else:
            demand = {"band": "数据不足", "why": f"这个工具包里有过线阅读卡的同学还不到 {POOL_MIN} 人，不能把「人少」读成「冷门」"}
        m = o.get("momentum") or {}
        mine = [e for e in my if _matches(e, o)]
        rows.append({
            "order": i, "id": o["id"], "niche": o["niche"], "note": o["note"], "quote": o["quote"],
            "paper": o["paper"], "arxiv_id": o["arxiv_id"], "section": o["section"],
            "demand": demand,
            "supply": {"status": "未知", "how": "问做这个方向的学长学姐：哪些组在做、这学期收不收本科生；或查本研公开题目"},
            "momentum": {"trend": m.get("trend", ""), "last12": m.get("last12"), "prev12": m.get("prev12"),
                         "relative": m.get("relative"), "checked_at": m.get("checked_at", "")},
            "crowding": "数据不足" if demand["band"] == "数据不足" else "供给未知",
            "my_edges": [{"text": e["text"], "status": e["status"]} for e in mine],
            "read": o["arxiv_id"] in passed,
        })
    return {"kit": {"id": k["id"], "name": k["name"], "direction": k.get("direction", "")}, "rows": rows, "pool_enough": enough,
            "base": k.get("momentum_base", {}), "lag_days": LAG_DAYS, "k_min": K_MIN,
            "formula": "拥挤度 = 需求档位 ÷ 已知供给；势头（近 12 个月 arXiv 论文数的增长 ÷ 所在分类整体的增长）只作修正",
            "rarity": combo_rarity(uid, kit_id)}


# ---------- 定位陈述 ----------

def _concrete(text: str, k: dict[str, Any]) -> bool:
    t = text.lower()
    names = [d["name"].split("/")[-1].lower() for d in k.get("datasets", [])]
    return bool(re.search(r"[a-z]{2,}|\d", t)) or any(w in text for w in CONCRETE) or any(n and n in t for n in names)


def review_statement(uid: str, kit_id: str, x_ref: str, x_text: str, y_ids: list[str]) -> dict[str, Any]:
    k = reading.kit(kit_id)
    o = next((p for p in k["open_problems"] if p["id"] == x_ref), None)
    mine = {e["id"]: e for e in edges(uid)["edges"]}
    y = [mine[i] for i in y_ids if i in mine]
    x_text = (x_text or "").strip()
    passed = {c["arxiv_id"] for c in store.latest_cards(uid, kit_id) if c["status"] == "pass"}
    checks: list[dict[str, Any]] = []

    def add(key: str, label: str, ok: bool, note: str, level: str) -> None:
        checks.append({"key": key, "label": label, "pass": ok, "note": note, "level": level})

    add("x_ref", "X 指向一个开放问题", bool(o), "已指向「" + o["niche"] + "」" if o else "先在竞争地图里选一个开放问题", "must")
    ok_len = X_MIN <= len(x_text) <= X_MAX
    ok_conc = ok_len and _concrete(x_text, k)
    add("x_text", "X 具体：点名对象、方法或数据", ok_conc,
        "够具体" if ok_conc else (f"X 写 {X_MIN}–{X_MAX} 字" if not ok_len else "没看到具体的对象、方法或数据：比如「中文数学题基准上的单次污染检测」"),
        "must" if not ok_len else "portfolio")
    add("y_any", "Y 至少引一条你的边", bool(y), "引了 %d 条" % len(y) if y else "从边清单里选至少一条", "must")
    proven = [e for e in y if e["status"] == "proven"]
    have_proof = any(e["status"] == "proven" for e in mine.values())
    add("y_proven", "Y 有已证明的条目", bool(proven),
        "有已证明条目" if proven else "待证明：Y 只有自述，可以保存，进不了作品集。"
        + ("你的边清单里有已证明的，选上它" if have_proof else "交一张过线的阅读卡就有了"), "portfolio")
    generic = [e["text"] for e in y if e["generic"]]
    add("y_generic", "Y 不是谁都有的理由", not generic,
        "没有空泛理由" if not generic else f"「{'」「'.join(generic)}」在哪个池子里都常见——什么是别人没有的？", "portfolio")
    if o:
        related = [e for e in y if _matches(e, o)]
        add("y_related", "Y 和 X 有关", bool(related),
            "有直接相关的边" if related else "选的边和这个问题的联系没写出来：换一条直接相关的，或先读懂出处论文", "hint")
        add("x_read", "读过 X 的出处", o["arxiv_id"] in passed,
            "出处论文有过线阅读卡" if o["arxiv_id"] in passed else f"这个问题出自《{o['paper']}》，你还没给它交过过线的阅读卡", "hint")
    must_ok = all(c["pass"] for c in checks if c["level"] == "must")
    portfolio_ok = must_ok and all(c["pass"] for c in checks if c["level"] == "portfolio")
    sentence = f"我是能做「{x_text}」的人，因为" + "、".join(f"{e['text']}" + ("" if e["status"] == "proven" else "（自述）") for e in y) + "。" if must_ok else ""
    return {"checks": checks, "can_save": must_ok, "portfolio_ready": portfolio_ok, "sentence": sentence,
            "niche": o and {"id": o["id"], "niche": o["niche"], "quote": o["quote"], "paper": o["paper"], "section": o["section"]},
            "y": [{"id": e["id"], "text": e["text"], "status": e["status"]} for e in y]}


def save_statement(uid: str, kit_id: str, x_ref: str, x_text: str, y_ids: list[str]) -> dict[str, Any]:
    r = review_statement(uid, kit_id, x_ref, x_text, y_ids)
    if not r["can_save"]:
        first = next(c for c in r["checks"] if c["level"] == "must" and not c["pass"])
        raise PositionError(f"先改「{first['label']}」：{first['note']}")
    prev = store.latest_statement(uid, kit_id)
    return store.save_statement(uid, kit_id, x_ref, {**r, "x_text": x_text.strip(), "y_ids": y_ids,
                                                       "prev_version": prev and prev["version"]})


def statement(uid: str, kit_id: str) -> dict[str, Any]:
    s = store.latest_statement(uid, kit_id)
    if not s:
        return {"statement": None}
    fresh = review_statement(uid, kit_id, s["x_ref"], s["x_text"], s["y_ids"])  # 账本变了，检查跟着变
    return {"statement": {**s, "checks": fresh["checks"], "portfolio_ready": fresh["portfolio_ready"], "y": fresh["y"]}}


# ---------- 下注组合 ----------

def _bet_checks(uid: str, active: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    tiers = [b["tier"] for b in active]
    if len(active) >= 2 and set(tiers) == {"reach"}:
        out.append({"level": "warn", "note": "全是「冲」：风险压在一处。至少放一个「稳」或「保」"})
    same: dict[tuple[str, str], list[str]] = {}
    for b in active:
        if b.get("niche"):
            same.setdefault((b.get("kit", ""), b["niche"]), []).append(b["name"])
    for names in same.values():
        if len(names) >= 2:
            out.append({"level": "warn", "note": f"「{'」「'.join(names)}」押在同一个子方向：它一热起来，这几个目标一起变难"})
    has_work = any(f.source == "behavior" for f in store.list_facts(uid, ["active"]))
    if active and "safety" not in tiers and not has_work:
        out.append({"level": "hint", "note": "你还没有过线的作品：先用一个「保」拿到第一件过线作品和第一位能为你说话的人，再冲"})
    if not out and active:
        out.append({"level": "ok", "note": "组合没有明显的集中风险"})
    return out


def bets(uid: str) -> dict[str, Any]:
    allb = store.list_bets(uid)
    active = [b for b in allb if b["status"] == "active"]
    return {"active": active, "closed": [b for b in allb if b["status"] == "closed"], "max": MAX_BETS,
            "tiers": TIERS, "kinds": BET_KINDS, "outcomes": OUTCOMES, "checks": _bet_checks(uid, active)}


def add_bet(uid: str, name: str, kind: str, tier: str, kit_id: str = "", niche: str = "") -> dict[str, Any]:
    name = (name or "").strip()
    if not 2 <= len(name) <= 40:
        raise PositionError("目标写 2–40 字：哪个组、哪个计划、哪个竞赛")
    if kind not in BET_KINDS or tier not in TIERS:
        raise PositionError("选目标类型和冲 / 稳 / 保")
    if sum(b["status"] == "active" for b in store.list_bets(uid)) >= MAX_BETS:
        raise PositionError(f"同时最多 {MAX_BETS} 个目标：先结束一个。有限才可信——「这是我这学期联系的三个组之一」本身就是信号")
    store.save_bet(uid, {"name": name, "kind": kind, "tier": tier, "kit": kit_id, "niche": niche, "status": "active"})
    return bets(uid)


def close_bet(uid: str, bet_id: str, outcome: str, reason: str) -> dict[str, Any]:
    b = next((x for x in store.list_bets(uid) if x["id"] == bet_id and x["status"] == "active"), None)
    if not b:
        raise PositionError("没有这个进行中的目标")
    if outcome not in OUTCOMES:
        raise PositionError("选结果：拿到了 / 没拿到 / 主动放弃")
    reason = (reason or "").strip()
    if len(reason) < 4:
        raise PositionError("写一句原因（至少 4 字）：以后的你和后来的同学都用得上")
    store.save_bet(uid, {**b, "status": "closed", "outcome": outcome, "reason": reason, "closed_at": now_iso()})
    return bets(uid)


# ---------- 今日的一次定位微调 ----------

def daily_tweak(uid: str, kit_id: str, kept_today: list[dict[str, Any]]) -> dict[str, Any] | None:
    """每天至多一句，指向一个能马上做的小动作；没有就不说。"""
    k = reading.kit(kit_id)
    s = store.latest_statement(uid, kit_id)
    passed = [c for c in store.latest_cards(uid, kit_id) if c["status"] == "pass"]
    if not s:
        if not passed:
            return None
        return {"text": "你已经有过线的阅读卡了。花两分钟写第一版定位：我是能做 X 的人，因为 Y。", "action": "写定位", "view": "position"}
    new_proof = [f for f in store.list_facts(uid, ["active"]) if f.source == "behavior" and f.created_at > s["created_at"]]
    if new_proof:
        return {"text": f"你新证明了「{new_proof[-1].value[:40]}」——这条能不能强化你的 Y？", "action": "改定位", "view": "position"}
    o = next((p for p in k["open_problems"] if p["id"] == s["x_ref"]), None)
    if o:
        for t in kept_today:
            text = (t.get("title") or "") + " " + (t.get("why") or "")
            if any(w.lower() in text.lower() for w in o["keywords"]):
                return {"text": f"今天留下的《{t.get('title', '')[:50]}》碰到了你的 X「{o['niche']}」：读成一张卡，Y 就多一条已证明。",
                        "action": "去读", "view": "read"}
    return None
