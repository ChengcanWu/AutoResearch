# -*- coding: utf-8 -*-
"""启研 · AI Research Mentor —— W0 Demo 后端（FastAPI 单体）。

运行：python server/main.py  （或 uvicorn server.main:app --port 8100）
默认地址 http://127.0.0.1:8100/
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import llm
import onboarding
import planner
import store
import workbench
from pku_adapter import search_courses

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="启研 · AI Research Mentor (W0 Demo)", version="0.1.0")
store.init_db()


# ---------- 请求模型 ----------

class LoginReq(BaseModel):
    nickname: str


class OnboardMsgReq(BaseModel):
    uid: str
    msg: str


class OnboardConfirmReq(BaseModel):
    uid: str
    edits: list[dict] = []


class NBAReq(BaseModel):
    uid: str


class ChooseDirectionReq(BaseModel):
    uid: str
    code: str


class TaskGenerateReq(BaseModel):
    uid: str
    direction: str
    level: int = 1
    title: str = ""
    brief: str = ""


class SubmitReq(BaseModel):
    uid: str
    payload: str


class FactPatchReq(BaseModel):
    uid: str
    value: str | None = None
    status: str | None = None


class LlmConnectReq(BaseModel):
    base_url: str = "https://api.deepseek.com/v1"
    api_key: str
    model: str = "deepseek-chat"


class PortraitReq(BaseModel):
    uid: str
    id: str = ""


def _user_or_404(uid: str) -> dict:
    u = store.get_user(uid)
    if not u:
        raise HTTPException(404, "user not found")
    return u


# ---------- auth ----------

@app.post("/api/auth/login")
def login(req: LoginReq):
    nickname = req.nickname.strip()
    if not nickname:
        raise HTTPException(400, "nickname is required")
    return store.create_user(nickname)


# ---------- onboarding ----------

@app.post("/api/onboard/start")
def onboard_start(req: NBAReq):
    _user_or_404(req.uid)
    return onboarding.start(req.uid)


@app.post("/api/onboard/message")
def onboard_message(req: OnboardMsgReq):
    _user_or_404(req.uid)
    state = store.get_onboard_state(req.uid)
    if state.get("phase") == "done":
        raise HTTPException(400, "onboarding already done")
    if not state:
        return onboarding.start(req.uid)
    return onboarding.message(req.uid, req.msg)


@app.get("/api/onboard/result")
def onboard_result(uid: str):
    _user_or_404(uid)
    msgs = store.list_messages(uid)
    facts = [f.to_dict() for f in store.list_facts(uid)]
    return {"messages": msgs, "facts": facts,
            "state": store.get_onboard_state(uid)}


@app.post("/api/onboard/confirm")
def onboard_confirm(req: OnboardConfirmReq):
    _user_or_404(req.uid)
    confirmed = onboarding.confirm(req.uid, req.edits)
    return {"facts": [f.to_dict() for f in confirmed]}


@app.get("/api/portraits")
def portraits_list(uid: str):
    _user_or_404(uid)
    return {"portraits": store.list_portraits(uid)}


@app.post("/api/portraits")
def portraits_create(req: PortraitReq):
    _user_or_404(req.uid)
    store.open_new_portrait(req.uid)
    onboarding.start(req.uid)
    return {"portraits": store.list_portraits(req.uid)}


@app.post("/api/portraits/activate")
def portraits_activate(req: PortraitReq):
    _user_or_404(req.uid)
    if not req.id:
        raise HTTPException(400, "id is required")
    try:
        store.activate_portrait(req.uid, req.id)
    except KeyError:
        raise HTTPException(404, "portrait not found")
    return {"portraits": store.list_portraits(req.uid)}


@app.delete("/api/portraits/{pid}")
def portraits_delete(pid: str, uid: str):
    _user_or_404(uid)
    try:
        reset = store.delete_portrait(uid, pid)
    except KeyError:
        raise HTTPException(404, "portrait not found")
    if reset:
        onboarding.start(uid)
    return {"portraits": store.list_portraits(uid)}


# ---------- nba / directions ----------

@app.post("/api/nba")
def nba(req: NBAReq):
    _user_or_404(req.uid)
    return planner.next_best_action(req.uid)


@app.get("/api/directions/recommend")
def directions_recommend(uid: str):
    """按当前画像的兴趣给方向建议，不检索课程、不等模型改写。"""
    _user_or_404(uid)
    return {"cards": planner.direction_cards(uid, with_courses=False, voice=False)}


@app.post("/api/directions/cards")
def direction_cards(req: NBAReq):
    """带真实课程检索的推荐卡（课程 live，可能较慢，前端按卡懒加载时不用此聚合接口）。"""
    _user_or_404(req.uid)
    return {"cards": planner.direction_cards(req.uid, with_courses=True)}


@app.post("/api/directions/choose")
def choose_direction(req: ChooseDirectionReq):
    _user_or_404(req.uid)
    if req.code not in planner.DIRECTIONS:
        raise HTTPException(400, f"unknown direction: {req.code}")
    f = planner.choose_direction(req.uid, req.code)
    return {"fact": f.to_dict()}


# ---------- tasks / workbench ----------

@app.post("/api/tasks/generate")
def task_generate(req: TaskGenerateReq):
    _user_or_404(req.uid)
    if req.direction not in planner.DIRECTIONS:
        raise HTTPException(400, f"unknown direction: {req.direction}")
    t = workbench.generate_task(req.uid, req.direction, req.level, title=req.title, brief=req.brief)
    return t.to_dict()


@app.get("/api/tasks/{tid}")
def task_get(tid: str):
    t = store.get_task(tid)
    if not t:
        raise HTTPException(404, "task not found")
    return t.to_dict()


@app.get("/api/tasks")
def task_list(uid: str):
    _user_or_404(uid)
    return {"tasks": [t.to_dict() for t in store.list_tasks(uid)]}


@app.post("/api/tasks/{tid}/submit")
def task_submit(tid: str, req: SubmitReq):
    _user_or_404(req.uid)
    t = store.get_task(tid)
    if not t:
        raise HTTPException(404, "task not found")
    if len(req.payload.strip()) < 10:
        raise HTTPException(400, "提交内容太短，至少写一句话")
    fb = workbench.submit(req.uid, t, req.payload)
    return fb


# ---------- me（AI 认识的我） ----------

@app.get("/api/me/facts")
def me_facts(uid: str):
    _user_or_404(uid)
    return {"facts": [f.to_dict() for f in store.list_facts(uid)]}


@app.get("/api/me/facts/{fid}")
def me_fact(fid: str, uid: str):
    _user_or_404(uid)
    f = store.get_fact(fid)
    if not f or f.user_id != uid:
        raise HTTPException(404, "fact not found")
    return f.to_dict()


@app.patch("/api/me/facts/{fid}")
def me_fact_patch(fid: str, req: FactPatchReq):
    f = store.get_fact(fid)
    if not f or f.user_id != req.uid:
        raise HTTPException(404, "fact not found")
    if req.value is None and req.status is None:
        raise HTTPException(400, "nothing to update")
    f2 = store.update_fact(fid, value=req.value, status=req.status)
    return f2.to_dict() if f2 else {}


@app.delete("/api/me/facts/{fid}")
def me_fact_delete(fid: str, uid: str):
    f = store.get_fact(fid)
    if not f or f.user_id != uid:
        raise HTTPException(404, "fact not found")
    store.update_fact(fid, status="deleted")
    return {"ok": True}


# ---------- explore（真实课程检索透传） ----------

@app.get("/api/explore/courses")
def explore_courses(query: str, limit: int = 5, term: str = ""):
    if not query.strip():
        raise HTTPException(400, "query is required")
    res = search_courses(query, limit=limit, term=term)
    return res


@app.post("/api/llm/connect")
def llm_connect(req: LlmConnectReq):
    try:
        cfg = llm.apply_config(req.base_url, req.api_key, req.model, persist=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    probe = llm.probe()
    if not probe.get("ok"):
        raise HTTPException(502, probe.get("error") or "模型连通失败")
    return {"ok": True, "model": cfg["model"], "base_url": cfg["base_url"]}


@app.get("/api/health")
def health():
    cfg = llm.config()
    return {
        "ok": True,
        "service": "research-mentor",
        "version": "0.2.0",
        "llm": {
            "enabled": cfg["enabled"],
            "model": cfg["model"] if cfg["enabled"] else "",
            "base_url": cfg["base_url"] if cfg["enabled"] else "",
        },
    }


# ---------- 静态前端 ----------

app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEB_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    print("启研 W0 Demo: http://127.0.0.1:8100/")
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
