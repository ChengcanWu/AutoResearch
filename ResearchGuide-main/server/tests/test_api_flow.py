# -*- coding: utf-8 -*-
"""整条链路的接口测试：登录 → 五问 → 核对 → 选方向 → 节点任务 → 提交反馈 → 找项目 → 交压缩包 → 记录。

不联网、不调模型：数据库放临时目录，模型关掉，所有实时来源一律「连不上」（检索走快照）。
运行：uv run --no-project --with pytest --with fastapi --with pydantic --with httpx pytest server/tests
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import llm  # noqa: E402
import store  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "flow.db")
    monkeypatch.setattr(llm, "config", lambda: {"enabled": False, "base_url": "", "model": "", "has_key": False})
    monkeypatch.setattr(llm, "enabled", lambda: False)
    monkeypatch.setattr(llm, "chat", lambda *a, **k: None)
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: None)
    import project_adapters

    def offline(*_a, **_k):
        raise project_adapters.AdapterError("测试里不联网")

    monkeypatch.setattr(project_adapters, "ADAPTERS", {k: offline for k in project_adapters.ADAPTERS})
    from fastapi.testclient import TestClient
    import main
    store.init_db()
    return TestClient(main.app)


def test_whole_flow(client):
    c = client
    assert c.get("/api/health").json()["llm"]["enabled"] is False
    assert c.get("/").status_code == 200 and "启研" in c.get("/").text
    assert c.get("/static/js/app.js").status_code == 200
    paths = c.get("/api/paths").json()["paths"]
    assert {"math", "ai", "psy", "econ"} <= set(paths) and all(len(p["steps"]) == 6 for p in paths.values())

    uid = c.post("/api/auth/login", json={"nickname": "小北"}).json()["uid"]
    first = c.post("/api/onboard/start", json={"uid": uid}).json()
    assert first["options"]

    answers = ["大一 · 理科 / 工科", "两者都接触过", "看它的数据和运行行为", "为什么机器能从数据里学会东西", "先动手跑起来，再回头补理论"]
    for i, a in enumerate(answers):
        turn = c.post("/api/onboard/message", json={"uid": uid, "msg": a}).json()
        assert turn["facts"], a
        assert turn["done"] is (i == len(answers) - 1)
    drafts = [f for f in c.get(f"/api/onboard/result?uid={uid}").json()["facts"] if f["status"] == "draft"]
    assert len(drafts) == 5

    # 核对：改一条、划掉一条
    edits = [{"id": drafts[0]["id"], "value": "本科一年级，物理系"}, {"id": drafts[4]["id"], "dismissed": True}]
    confirmed = c.post("/api/onboard/confirm", json={"uid": uid, "edits": edits}).json()["facts"]
    assert len(confirmed) == 4 and confirmed[0]["value"] == "本科一年级，物理系"

    cards = c.get(f"/api/directions/recommend?uid={uid}").json()["cards"]
    assert cards and cards[0]["direction"]["code"] == "ai"
    assert c.post("/api/directions/choose", json={"uid": uid, "code": "ai"}).json()["fact"]["key"] == "direction:ai"

    task = c.post("/api/tasks/generate", json={"uid": uid, "direction": "ai", "level": 1, "title": "看懂机器学习",
                                               "brief": "机器学习是让程序从例子里找出规律"}).json()
    assert c.post(f"/api/tasks/{task['id']}/submit", json={"uid": uid, "payload": "太短"}).status_code == 400
    fb = c.post(f"/api/tasks/{task['id']}/submit", json={"uid": uid, "payload": (
        "我理解「看懂机器学习」在问：程序怎么从例子里找规律。例如 20 条外卖评论里，规则判错了 4 条。"
        "我现在还卡在：不知道模型是学会了还是记住了。")}).json()
    assert [r["pass"] for r in fb["rubric"]] == [True, True, True]
    assert fb["learned_facts"][0]["source"] == "behavior"

    # 找项目：实时来源都连不上，检索仍然返回快照里的真实项目，并如实标出
    ctx = c.get(f"/api/projects/context?uid={uid}").json()
    assert ctx["direction"] == "ai" and ctx["stage"] == 1 and ctx["path_step"] == 2
    res = c.post("/api/projects/search", json={"uid": uid, "direction": "ai", "stage": 1, "path_step": 2}).json()
    assert res["query"]["path_step"] == 2 and res["voice"] == "rules"
    assert res["items"] and all(i["snapshot"] and i["url"].startswith("http") for i in res["items"])
    assert any(s.get("snapshot") and "实时检索失败" in (s.get("error") or "") for s in res["sources"])
    assert c.post("/api/projects/pick", json={"uid": uid, "id": "0" * 16}).status_code == 409
    proj = c.post("/api/projects/pick", json={"uid": uid, "id": res["items"][0]["id"]}).json()

    readme = c.get(f"/api/projects/{proj['id']}/readme?uid={uid}")
    assert readme.status_code == 200 and proj["name"] in readme.text
    sample = c.get(f"/api/projects/{proj['id']}/sample.zip?uid={uid}").content
    assert "示例成果/README.md" in zipfile.ZipFile(io.BytesIO(sample)).namelist()

    bad = c.post(f"/api/projects/{proj['id']}/submit?uid={uid}", content=b"not a zip", headers={"Content-Type": "application/zip"})
    assert bad.status_code == 400
    review = c.post(f"/api/projects/{proj['id']}/submit?uid={uid}", content=sample, headers={"Content-Type": "application/zip"}).json()
    assert review["total"] == 5 and review["voice"] == "rules" and review["next_step"]
    assert review["fact"]["key"] == f"project:{proj['id']}"

    mine = c.get(f"/api/projects/mine?uid={uid}").json()["projects"]
    assert mine[0]["status"] == "reviewed" and mine[0]["reviews"][0]["total"] == 5

    facts = c.get(f"/api/me/facts?uid={uid}").json()["facts"]
    keys = {f["key"] for f in facts}
    assert {"direction:ai", f"project:{proj['id']}"} <= keys
    assert any(k.startswith("task_done:") for k in keys)

    # 软删一条，记录里就看不到。
    # 「软删」在合并后的代码里是 status=retracted（memory.user_retract，留 revision 可追溯）；
    # 研读层作废结论用的是 deleted。两个都算「不再算数」——按状态筛选用白名单。
    fid = next(f["id"] for f in facts if f["key"] == "direction:ai")
    assert c.delete(f"/api/me/facts/{fid}?uid={uid}").json()["ok"] is True
    assert fid not in {f["id"] for f in c.get(f"/api/me/facts?uid={uid}").json()["facts"]
                       if f["status"] not in ("deleted", "retracted")}


def test_unknown_user_and_direction_are_rejected(client):
    assert client.get("/api/me/facts?uid=nobody").status_code == 404
    uid = client.post("/api/auth/login", json={"nickname": "t"}).json()["uid"]
    assert client.post("/api/projects/search", json={"uid": uid, "direction": "astrology"}).status_code == 400
    assert client.post("/api/directions/choose", json={"uid": uid, "code": "astrology"}).status_code == 400
