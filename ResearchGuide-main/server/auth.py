# -*- coding: utf-8 -*-
"""账号：学校邮箱验证码登录 + 会话；访客可以先用，之后绑邮箱把数据带走。

- 为什么是学校邮箱：短信签名要企业资质，微信网站登录要企业认证和备案域名，团队都没有；
  学校邮箱还顺带证明「是学生」，一人一号，送的模型额度才有意义（昵称账号随手能开一百个）。
- 令牌放在请求头 Authorization: Bearer，不用 cookie：页面在 github.io、接口在 fcapp.run，跨站 cookie 会被浏览器拦。
- 所有接口默认要登录，PUBLIC 里的才放行；请求里带的 uid（查询串、路径、JSON 体）必须就是登录的这个人。
  原来 uid 就是唯一凭证：知道别人的 uid 就能读他的成绩单和对话。
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import mailer
import store

SESSION_TTL = 30 * 86400   # 三十天不用才过期；用着的一天续一次
CODE_TTL = 600             # 验证码十分钟有效
CODE_TRIES = 5             # 一个验证码最多试五次
RESEND_GAP = 60            # 同一邮箱一分钟发一次
PER_EMAIL_HOUR = 5         # 同一邮箱一小时最多五封
PER_IP_HOUR = 30           # 同一来源一小时最多发三十封、开三十个访客号
MAIL_DAILY = int(os.environ.get("AUTH_MAIL_DAILY") or 300)  # 全站每天最多发这么多封（QQ / 163 邮箱的发信上限在这个量级）

# 隐私说明改了就改这个日期：老用户下次打开会再看到一次说明并重新同意。说明正文在 web/js/app.js 的 PRIVACY_HTML。
PRIVACY_VERSION = "2026-10-09"

# 不登录也能用的接口（按路由模板写）。新加的接口默认要登录：要么带 uid，要么加到这里并说明为什么可以公开。
PUBLIC = frozenset({
    "/", "/api/health",
    "/api/auth/login", "/api/auth/code", "/api/auth/verify", "/api/auth/legacy",
    # 公开知识：课程、老师、专业、培养方案、方向路径、阅读工具包、论文原文、给学生自己 agent 的简报
    "/api/explore/courses", "/api/explore/teachers", "/api/explore/majors", "/api/explore/major",
    "/api/explore/minor", "/api/explore/course", "/api/curriculum/match", "/api/curriculum/stats",
    "/mcp", "/api/projects/sources", "/api/paths", "/api/kits", "/api/kits/{kit_id}",
    "/api/papers/{arxiv_id}", "/api/brief",
    "/api/llm/connect",  # 自己核对管理员口令
})

router = APIRouter()


# ---------- 每个请求：认人 ----------

def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


# 续期要写库、要拿写锁；放到这个线程里做，事件循环上的 guard 只读
_TOUCH = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-touch")


def _session_uid(request: Request) -> str | None:
    token = _bearer(request)
    if not token:
        return None
    uid, stale = store.session_lookup(token)
    if stale:
        _TOUCH.submit(store.touch_session, token, SESSION_TTL)
    return uid


async def guard(request: Request) -> None:
    """挂在整个 app 上的依赖。公开接口直接放行；其余的先认会话，再核对请求里自称的 uid。"""
    route = request.scope.get("route")
    if getattr(route, "path", None) in PUBLIC:
        return
    uid = _session_uid(request)
    if not uid:
        raise HTTPException(401, "请先登录", headers={"WWW-Authenticate": "Bearer"})
    request.state.uid = uid
    claimed = [request.query_params.get("uid"), request.path_params.get("uid")]
    # 只看有 JSON 体的接口：FastAPI 在跑依赖之前已经把它读进内存，这里再取是缓存，不会把上传流读一遍
    if getattr(route, "body_field", None) is not None and "json" in request.headers.get("content-type", ""):
        try:
            body = await request.json()
        except ValueError:
            body = None  # 坏 JSON 交给接口自己报 422
        if isinstance(body, dict):
            claimed.append(body.get("uid"))
    if any(c not in (None, "") and c != uid for c in claimed):
        raise HTTPException(403, "这不是你的账号")


def me(request: Request) -> str | None:
    """登录的这个人。只在不带 uid、按对象 id 取东西的接口里用来核对归属。"""
    return getattr(request.state, "uid", None)


# ---------- 频率与邮箱 ----------

_EMAIL = re.compile(r"^[a-z0-9._%+-]{1,64}@(?:[a-z0-9-]+\.)+[a-z]{2,}$")
_IP_HITS: dict[str, list[float]] = {}
_IP_LOCK = threading.Lock()


def email_domains() -> list[str]:
    """允许的邮箱后缀，默认 edu.cn（北大的 pku.edu.cn、stu.pku.edu.cn 都在内）。填 * 就不限。"""
    raw = os.environ.get("AUTH_EMAIL_DOMAINS") or "edu.cn"
    return [d.strip().lower().lstrip(".@") for d in raw.split(",") if d.strip()]


def _check_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if len(email) > 254 or not _EMAIL.match(email):
        raise HTTPException(400, "邮箱格式不对")
    domain = email.rsplit("@", 1)[1]
    allowed = email_domains()
    if not any(d == "*" or domain == d or domain.endswith("." + d) for d in allowed):
        raise HTTPException(400, f"请用学校邮箱（{'、'.join(allowed)} 结尾）")
    return email


def _client_ip(request: Request) -> str | None:
    """限频用的来源地址。在代理后面（TRUST_PROXY=1）取 X-Forwarded-For 第一个；
    否则只认公网地址——代理的内网地址是所有人共用的，按它限频会把所有人一起拦住。"""
    if os.environ.get("TRUST_PROXY") == "1":
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if first:
            return first
    host = request.client.host if request.client else ""
    try:
        return host if ipaddress.ip_address(host).is_global else None
    except ValueError:
        return None


def _ip_allows(request: Request, kind: str) -> bool:
    ip = _client_ip(request)
    if ip is None:
        return True
    now, key = time.time(), f"{kind}:{ip}"
    with _IP_LOCK:
        if len(_IP_HITS) > 10000:  # 有界：一小时内的才有用，旧的整体清掉
            for k in [k for k, v in _IP_HITS.items() if not v or now - v[-1] > 3600]:
                del _IP_HITS[k]
        hits = [t for t in _IP_HITS.get(key, []) if now - t < 3600]
        if len(hits) >= PER_IP_HOUR:
            _IP_HITS[key] = hits
            return False
        hits.append(now)
        _IP_HITS[key] = hits
    return True


def _code_hash(salt: str, code: str) -> str:
    return hmac.new(salt.encode(), code.encode(), hashlib.sha256).hexdigest()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def account(uid: str) -> dict[str, Any]:
    u = store.get_user(uid) or {}
    return {
        "uid": uid,
        "nickname": u.get("nickname", ""),
        "email": u.get("email"),
        "guest": not u.get("email"),
        "consent_ok": u.get("consent_version") == PRIVACY_VERSION,
        "privacy_version": PRIVACY_VERSION,
    }


def status() -> dict[str, Any]:
    """给 /api/health：页面据此决定显示「邮箱登录」还是只给访客入口。"""
    dev = os.environ.get("AUTH_DEV_CODES") == "1"
    return {"email_login": mailer.configured() or dev, "dev_codes": dev and not mailer.configured(),
            "email_domains": email_domains(), "privacy_version": PRIVACY_VERSION}


# ---------- 接口 ----------

class GuestReq(BaseModel):
    nickname: str
    consent: bool = False


class CodeReq(BaseModel):
    email: str


class VerifyReq(BaseModel):
    email: str
    code: str
    nickname: str = ""
    consent: bool = False


class LegacyReq(BaseModel):
    uid: str


class ConsentReq(BaseModel):
    version: str


@router.post("/api/auth/login")
def guest_login(req: GuestReq, request: Request):
    """访客：只要昵称。数据只能凭这台浏览器里的令牌找回，之后绑学校邮箱就能换设备。"""
    nickname = req.nickname.strip()[:24]
    if not nickname:
        raise HTTPException(400, "nickname is required")
    if not _ip_allows(request, "guest"):
        raise HTTPException(429, "开的访客号太多了，过一会儿再试")
    uid = store.create_user(nickname)["uid"]
    if req.consent:
        store.record_consent(uid, PRIVACY_VERSION)
    return {**account(uid), "token": store.create_session(uid, SESSION_TTL)}


@router.post("/api/auth/code")
def send_code(req: CodeReq, request: Request):
    email = _check_email(req.email)
    now = time.time()
    row = store.code_row(email)
    if row and now - row["sent_at"] < RESEND_GAP:
        raise HTTPException(429, f"{int(RESEND_GAP - (now - row['sent_at'])) + 1} 秒后可以再发")
    hour_start, hour_count = (row["hour_start"], row["hour_count"]) if row and now - row["hour_start"] < 3600 else (now, 0)
    if hour_count >= PER_EMAIL_HOUR:
        raise HTTPException(429, "这个邮箱一小时内收了太多验证码，过一会儿再试")
    if not _ip_allows(request, "code"):
        raise HTTPException(429, "发得太频繁了，过一会儿再试")
    if store.mail_count(_today()) >= MAIL_DAILY:
        raise HTTPException(503, "今天的验证码发完了，明天再来，或先用访客进入")
    code = f"{secrets.randbelow(10 ** 6):06d}"
    if mailer.configured():
        try:
            mailer.send_code(email, code, CODE_TTL // 60)
        except Exception as exc:  # noqa: BLE001 — SMTP 的错误种类很多，对用户都是「没发出去」
            print(json.dumps({"auth": "mail_failed", "error": type(exc).__name__}, ensure_ascii=False))
            raise HTTPException(502, "验证码没发出去，请稍后再试") from exc
    elif os.environ.get("AUTH_DEV_CODES") == "1":
        # 本机开发没配发信邮箱：验证码只打印在服务器日志里，绝不放进响应
        print(json.dumps({"auth": "dev_code", "email": email, "code": code}, ensure_ascii=False))
    else:
        raise HTTPException(503, "服务器还没配发信邮箱，暂时只能用访客进入")
    salt = secrets.token_hex(8)
    store.put_code(email, salt, _code_hash(salt, code), now + CODE_TTL, now, hour_start, hour_count + 1)
    store.count_mail(_today())
    return {"ok": True, "email": email, "resend_after": RESEND_GAP}


@router.post("/api/auth/verify")
def verify_code(req: VerifyReq, request: Request):
    """验证码对了：这个邮箱有账号就登进去；没有的话，带着访客会话来的就把邮箱绑到访客号上（数据跟着走），
    否则新开一个。"""
    email = _check_email(req.email)
    row = store.code_row(email)
    if not row or not row["code_hash"] or row["expires_at"] <= time.time():
        raise HTTPException(400, "验证码过期了，请重新发送")
    if row["tries"] >= CODE_TRIES:
        raise HTTPException(400, "错的次数太多，请重新发送")
    if not hmac.compare_digest(row["code_hash"], _code_hash(row["salt"], req.code.strip())):
        store.bump_code_tries(email)
        left = CODE_TRIES - row["tries"] - 1
        raise HTTPException(400, f"验证码不对，还能再试 {left} 次" if left else "错的次数太多，请重新发送")
    store.spend_code(email)

    guest_token = _bearer(request)
    guest_uid = store.session_user(guest_token, SESSION_TTL) if guest_token else None
    user = store.user_by_email(email)
    created = bound = False
    if user:
        uid = user["id"]
    else:
        try:
            if guest_uid and store.bind_email(guest_uid, email):
                uid, bound = guest_uid, True
            else:
                uid, created = store.create_user((req.nickname or "").strip()[:24] or "同学", email=email)["uid"], True
        except sqlite3.IntegrityError:  # 两个请求同时用同一邮箱开号：后到的登进先开的那个
            uid = store.user_by_email(email)["id"]
    if req.consent:
        store.record_consent(uid, PRIVACY_VERSION)
    if guest_token and guest_uid:
        store.drop_session(guest_token)
    return {**account(uid), "token": store.create_session(uid, SESSION_TTL),
            "created": created, "bound": bound, "left_guest": bool(guest_uid and guest_uid != uid)}


@router.post("/api/auth/legacy")
def claim_legacy(req: LegacyReq):
    """有账号之前，浏览器里只存了 uid。这样的老用户凭 uid 认领一次，之后就要凭会话。"""
    if not store.claim_legacy(req.uid):
        raise HTTPException(401, "这个旧账号已经认领过或不存在，请重新登录")
    return {**account(req.uid), "token": store.create_session(req.uid, SESSION_TTL)}


@router.get("/api/auth/me")
def whoami(request: Request):
    return account(me(request))


@router.post("/api/auth/consent")
def consent(req: ConsentReq, request: Request):
    if req.version != PRIVACY_VERSION:
        raise HTTPException(409, "隐私说明更新了，请刷新页面再看一遍")
    store.record_consent(me(request), PRIVACY_VERSION)
    return account(me(request))


@router.post("/api/auth/logout")
def logout(request: Request):
    store.drop_session(_bearer(request))
    return {"ok": True}


@router.get("/api/me/export")
def export_mine(request: Request):
    data = store.export_user(me(request))
    return JSONResponse(data, headers={"Content-Disposition": "attachment; filename=qiyan-my-data.json"})


@router.delete("/api/me")
def delete_mine(request: Request):
    """真删：每张表里这个人的行、所有会话、账号本身。备份按 tools/backup_db.py 的保留期自然过期。"""
    return {"ok": True, "deleted": store.delete_user(me(request))}
