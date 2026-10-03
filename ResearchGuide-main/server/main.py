# -*- coding: utf-8 -*-
"""启研 · AI Research Mentor —— W0 Demo 后端（FastAPI 单体）。

运行：python server/main.py  （或 uvicorn server.main:app --port 8100）
默认地址 http://127.0.0.1:8100/
"""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import llm
import onboarding
import planner
import positioning
import projects
import quotes
import reading
import store
import submission
import workbench
from pku_adapter import search_courses
from limits import TTLCache
from singleflight import AsyncFlight

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


class ProjectSearchReq(BaseModel):
    uid: str
    direction: str
    stage: int = 0
    keywords: str = ""
    node: str = ""
    path_step: int = 0


class ProjectPickReq(BaseModel):
    uid: str
    id: str


class TriageReq(BaseModel):
    uid: str
    kit: str
    arxiv_id: str
    verdict: str
    why: str
    title: str = ""


class CardReq(BaseModel):
    uid: str
    kit: str
    arxiv_id: str
    fields: dict[str, str] = {}
    dims: dict[str, str] = {}
    decision_log: list[dict[str, str]] = []


class EdgeReq(BaseModel):
    uid: str
    kind: str
    text: str
    evidence_url: str = ""


class StatementReq(BaseModel):
    uid: str
    kit: str
    x_ref: str = ""
    x_text: str = ""
    y: list[str] = []
    dry_run: bool = False


class ChannelReq(BaseModel):
    uid: str
    id: str
    on: bool
    direction: str


class BetReq(BaseModel):
    uid: str
    name: str
    kind: str
    tier: str
    kit: str = ""
    niche: str = ""


class BetCloseReq(BaseModel):
    uid: str
    outcome: str
    reason: str


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
async def explore_courses(query: str, limit: int = 5, term: str = ""):
    """相同的课程检索在事件循环里共等一个结果；原来跟随者各占一个工作线程干等。"""
    if not query.strip():
        raise HTTPException(400, "query is required")
    key = ("courses", query.strip(), min(10, max(1, limit)), term.strip())
    return await _shared(key, search_courses, query, limit, term)


# ---------- 边学边练：项目检索 / 选定 / 交成果（任务 3） ----------

@app.get("/api/projects/sources")
def project_sources():
    reg = projects.registry()
    return {"generated_at": reg.get("generated_at"), "sources": [
        {k: s.get(k) for k in ("id", "name", "home_url", "kind", "directions", "stage_fit", "access", "cadence", "manual_route", "search_terms")}
        for s in reg["sources"]]}


@app.get("/api/paths")
def direction_paths():
    """任务 4 的方向路径（knowledge/paths.json），前端用它把方向树画成「6 步主干 + 原有节点」。"""
    return {"paths": projects.paths()}


@app.get("/api/projects/context")
def project_context(uid: str):
    _user_or_404(uid)
    return projects.context(uid)


@app.post("/api/projects/search")
def project_search(req: ProjectSearchReq):
    _user_or_404(req.uid)
    if req.direction not in planner.DIRECTIONS:
        raise HTTPException(400, f"unknown direction: {req.direction}")
    return projects.search(req.uid, req.direction, req.stage, req.keywords, req.node, req.path_step)


@app.post("/api/projects/pick")
def project_pick(req: ProjectPickReq):
    _user_or_404(req.uid)
    try:
        return projects.pick(req.uid, req.id)
    except KeyError as exc:
        raise HTTPException(409, str(exc.args[0])) from exc


@app.get("/api/projects/mine")
def project_mine(uid: str):
    _user_or_404(uid)
    return {"projects": [{k: v for k, v in p.items() if k != "reviews"} | {"reviews": [
        {"passed": r.get("passed"), "total": r.get("total"), "reviewed_at": r.get("reviewed_at")} for r in (p.get("reviews") or [])[:1]]}
        for p in store.list_projects(uid)]}


def _project_or_404(uid: str, pid: str) -> dict:
    _user_or_404(uid)
    p = store.get_project(uid, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@app.get("/api/projects/{pid}")
def project_get(pid: str, uid: str):
    return _project_or_404(uid, pid)


@app.get("/api/projects/{pid}/readme")
def project_readme(pid: str, uid: str):
    p = _project_or_404(uid, pid)
    return Response(projects.readme_template(p), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=README.md"})


@app.get("/api/projects/{pid}/sample.zip")
def project_sample(pid: str, uid: str):
    p = _project_or_404(uid, pid)
    return Response(projects.sample_zip(p), media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=sample.zip"})


# 评阅（解压、规则检查、模型调用、写库）都是阻塞的：放进有上限的线程池，不占事件循环。
# 上传和评阅分开计数：传到一半卡住的连接只占上传名额，而且有总时限，不会把评阅名额占光。
REVIEW_WORKERS = 2
REVIEW_PENDING_MAX = 6      # 已收完、在排队或在评阅的；每个握着最多 20 MB
UPLOADS_MAX = 8             # 同时在上传的
UPLOAD_IDLE_SECONDS = 20    # 这么久一个字节都没收到，就当连接卡住了
UPLOAD_TOTAL_SECONDS = 300  # 总时限：20 MB 在 70 KB/s 的慢网上也传得完；只防一直吊着不传完的连接
_REVIEW_POOL = ThreadPoolExecutor(max_workers=REVIEW_WORKERS, thread_name_prefix="review")
_review_pending = 0  # 这两个计数只在事件循环线程里改，不用锁
_uploads = 0


async def _read_capped(request: Request, limit: int) -> bytes:
    """边收边数，超过上限立刻停（原来先把整个请求体读进内存再判断大小）。
    慢网照样能传完：只在「很久没收到数据」或「总时间太长」时断开，不按固定的几十秒一刀切。"""
    too_big = f"压缩包超过 {limit // 1024 // 1024} MB。大数据集请只放样例，并在 README 里写下载链接。"
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, too_big)
    buf = bytearray()
    chunks = request.stream().__aiter__()
    deadline = asyncio.get_running_loop().time() + UPLOAD_TOTAL_SECONDS
    while True:
        left = deadline - asyncio.get_running_loop().time()
        if left <= 0:
            raise HTTPException(408, f"上传超过 {UPLOAD_TOTAL_SECONDS // 60} 分钟还没传完，已断开。请换个网络再交，或把压缩包弄小一点。")
        try:
            chunk = await asyncio.wait_for(chunks.__anext__(), min(UPLOAD_IDLE_SECONDS, left))
        except StopAsyncIteration:
            return bytes(buf)
        except asyncio.TimeoutError as exc:
            raise HTTPException(408, f"上传中断：{UPLOAD_IDLE_SECONDS} 秒没有收到数据。请检查网络后再交。") from exc
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(413, too_big)


def _review_and_record(uid: str, p: dict, data: bytes) -> dict:
    try:
        result = submission.review(data, p)
    except submission.SubmissionError as exc:
        raise HTTPException(400, str(exc)) from exc
    result["fact"] = projects.record_review(uid, p, result)
    return result


@app.post("/api/projects/{pid}/submit")
async def project_submit(pid: str, uid: str, request: Request):
    """请求体就是 .zip 本身（Content-Type: application/zip），不需要 multipart 依赖。"""
    global _review_pending, _uploads
    p = await run_in_threadpool(_project_or_404, uid, pid)
    if _uploads >= UPLOADS_MAX or _review_pending >= REVIEW_PENDING_MAX:
        raise HTTPException(503, "现在交的人太多，评阅在排队。请过一两分钟再交。")
    _uploads += 1
    try:
        data = await _read_capped(request, submission.MAX_ZIP_BYTES)
    finally:
        _uploads -= 1
    if not data:
        raise HTTPException(400, "没有收到文件")
    if _review_pending >= REVIEW_PENDING_MAX:
        raise HTTPException(503, "现在交的人太多，评阅在排队。请过一两分钟再交。")
    _review_pending += 1
    try:
        return await asyncio.get_running_loop().run_in_executor(_REVIEW_POOL, _review_and_record, uid, p, data)
    finally:
        _review_pending -= 1


# ---------- 研读：领域工具包 / 每日情报 / 阅读卡 / 矩阵 ----------

def _reading(fn, *args):
    try:
        return fn(*args)
    except (reading.ReadingError, positioning.PositionError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except reading.arxiv.ArxivError as exc:
        raise HTTPException(502, str(exc)) from exc


# 共享的活按种类分开线程池：arXiv 要排限速锁（每次至少隔 3 秒），几篇不同的论文就能把线程全占在等锁上；
# 分开以后，等 arXiv 的不会拖住课程检索和建引文索引
_FLIGHTS = {
    "arxiv": AsyncFlight(ThreadPoolExecutor(max_workers=4, thread_name_prefix="arxiv")),
    "index": AsyncFlight(ThreadPoolExecutor(max_workers=2, thread_name_prefix="index")),
    "courses": AsyncFlight(ThreadPoolExecutor(max_workers=4, thread_name_prefix="courses")),
}
_FLIGHT_OF = {"paper": "arxiv", "daily": "arxiv", "index": "index", "courses": "courses"}


async def _shared(key: tuple, fn, *args):
    """多人同时要同一份数据：只有一个线程去做，其余在事件循环里等结果，不各占一个工作线程。"""
    return await _FLIGHTS[_FLIGHT_OF[key[0]]].do(key, _reading, fn, *args)


def _paper_payload(aid: str) -> dict:
    p = reading.arxiv.fulltext(aid)
    return {**p, "sections": [{"name": n, "label": reading.arxiv.section_cn(n), "at": at} for n, at in reading.arxiv.sections(p["text"])]}


def _paper_index(aid: str) -> None:
    """交卡之前先把这篇论文的引文索引和分节建好：并发交同一篇时，跟随者在事件循环里等，不在评阅线程里干等。"""
    text = reading.arxiv.fulltext(aid)["text"]
    quotes.prepare(text)
    reading.arxiv.sections(text)


_DAILY_MISS = TTLCache(30, 64)  # arXiv 取不到时，三十秒内的请求直接用这个失败结果，不再去打


def _daily_source(kit_id: str) -> tuple[list, str]:
    """共享的那一步：候选或失败原因，作为参数交给 daily，不让每个请求在自己的线程里再取一次。"""
    hit, miss = _DAILY_MISS.lookup(kit_id)
    if hit:
        return miss
    got = reading.daily_source(kit_id)
    if got[1]:
        _DAILY_MISS.set(kit_id, got)
    return got


@app.get("/api/kits")
def kits_list():
    return {"kits": [{k: v for k, v in kit.items() if k in ("id", "name", "version", "direction", "goal", "status")}
                     for kit in reading.kits().values()]}


@app.get("/api/kits/{kit_id}")
def kit_get(kit_id: str):
    return _reading(reading.kit, kit_id)


def _daily_payload(uid: str, kit: str, source: tuple[list, str]) -> dict:
    d = _reading(reading.daily, uid, kit, source)
    today = [r for r in d["recent_keeps"] if r["created_at"][:10] == reading.now_iso()[:10]]
    return {**d, "tweak": _reading(positioning.daily_tweak, uid, kit, today)}


@app.get("/api/daily")
async def daily_feed(uid: str, kit: str):
    await run_in_threadpool(_user_or_404, uid)
    source = await _shared(("daily", kit), _daily_source, kit)
    return await run_in_threadpool(_daily_payload, uid, kit, source)


@app.post("/api/daily/triage")
async def daily_triage(req: TriageReq):
    await run_in_threadpool(_user_or_404, req.uid)
    source = await _shared(("daily", req.kit), _daily_source, req.kit)
    return await run_in_threadpool(_reading, reading.triage, req.uid, req.kit, req.arxiv_id, req.verdict, req.why, req.title, source)


@app.get("/api/papers/{arxiv_id}")
async def paper_text(arxiv_id: str):
    """论文正文（arXiv HTML 版，取不到则只有摘要）。只读、缓存。"""
    aid = _reading(reading.arxiv.clean_id, arxiv_id)
    return await _shared(("paper", aid), _paper_payload, aid)


@app.get("/api/cards")
def cards_list(uid: str, kit: str):
    _user_or_404(uid)
    return {"cards": store.latest_cards(uid, kit), "fields": reading.CARD_FIELDS}


@app.get("/api/cards/{arxiv_id}/history")
def card_history(arxiv_id: str, uid: str, kit: str):
    _user_or_404(uid)
    return {"versions": store.card_history(uid, kit, arxiv_id)}


def _card_submit(req: CardReq) -> dict:
    _user_or_404(req.uid)
    return _reading(reading.submit_card, req.uid, req.kit, req.arxiv_id, req.fields, req.dims, req.decision_log)


@app.post("/api/cards")
async def card_submit(req: CardReq):
    aid = _reading(reading.arxiv.clean_id, req.arxiv_id)
    await run_in_threadpool(_user_or_404, req.uid)
    await _shared(("paper", aid), _paper_payload, aid)  # 先把原文取进缓存，并发提交同一篇只取一次
    await _shared(("index", aid), _paper_index, aid)    # 再把引文索引建好；之后每张卡的核对都直接命中
    return await run_in_threadpool(_card_submit, req)


@app.get("/api/matrix")
def matrix_get(uid: str, kit: str):
    _user_or_404(uid)
    return _reading(reading.matrix, uid, kit)


@app.get("/api/brief")
def agent_brief(kit: str, arxiv_id: str):
    text = _reading(reading.brief, kit, arxiv_id)
    return Response(text, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=AGENTS.md"})


# ---------- 定位：边清单、竞争地图、定位陈述、下注组合 ----------

@app.get("/api/edges")
def edges_list(uid: str):
    _user_or_404(uid)
    return positioning.edges(uid)


@app.post("/api/edges")
def edges_add(req: EdgeReq):
    _user_or_404(req.uid)
    return _reading(positioning.add_edge, req.uid, req.kind, req.text, req.evidence_url)


@app.delete("/api/edges/{edge_id}")
def edges_delete(edge_id: str, uid: str):
    _user_or_404(uid)
    return _reading(positioning.delete_edge, uid, edge_id)


@app.get("/api/channels")
def channels_map(uid: str, direction: str):
    """这个方向的人在哪说话：信息源地图（knowledge/channels.json），标出学生常看的和盲区。"""
    _user_or_404(uid)
    return positioning.channel_map(uid, direction)


@app.post("/api/channels/toggle")
def channels_toggle(req: ChannelReq):
    _user_or_404(req.uid)
    return _reading(positioning.toggle_channel, req.uid, req.id, req.on, req.direction)


@app.get("/api/map")
def competition_map(uid: str, kit: str):
    _user_or_404(uid)
    return _reading(positioning.competition_map, uid, kit)


@app.get("/api/statement")
def statement_get(uid: str, kit: str):
    _user_or_404(uid)
    return _reading(positioning.statement, uid, kit)


@app.post("/api/statement")
def statement_save(req: StatementReq):
    """dry_run=true 只跑检查不保存，给编辑时实时提示用。"""
    _user_or_404(req.uid)
    if req.dry_run:
        return _reading(positioning.review_statement, req.uid, req.kit, req.x_ref, req.x_text, req.y)
    return _reading(positioning.save_statement, req.uid, req.kit, req.x_ref, req.x_text, req.y)


@app.get("/api/bets")
def bets_list(uid: str):
    _user_or_404(uid)
    return positioning.bets(uid)


@app.post("/api/bets")
def bets_add(req: BetReq):
    _user_or_404(req.uid)
    return _reading(positioning.add_bet, req.uid, req.name, req.kind, req.tier, req.kit, req.niche)


@app.post("/api/bets/{bet_id}/close")
def bets_close(bet_id: str, req: BetCloseReq):
    _user_or_404(req.uid)
    return _reading(positioning.close_bet, req.uid, bet_id, req.outcome, req.reason)


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
