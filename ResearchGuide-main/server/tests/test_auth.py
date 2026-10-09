# -*- coding: utf-8 -*-
"""账号：默认要登录、uid 必须是本人、学校邮箱验证码、访客绑邮箱、老用户认领、删号与导出。

这里用真的 auth.guard（其余测试把它换成「信请求里的 uid」）。不联网、不发邮件。
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import mailer  # noqa: E402
import main  # noqa: E402
import store  # noqa: E402

pytestmark = pytest.mark.real_auth
SERVER = Path(__file__).resolve().parent.parent
PRIVACY_DIGEST = "dd379f9b13eb"  # web/js/app.js 里 PRIVACY_HTML 的指纹，见最后一个测试


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "auth.db")
    store.init_db()
    auth._IP_HITS.clear()
    for k in ("AUTH_EMAIL_DOMAINS", "AUTH_DEV_CODES", "TRUST_PROXY"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def outbox(monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send_code", lambda to, code, minutes: sent.append((to, code)))
    monkeypatch.setattr(auth, "RESEND_GAP", 0)
    return sent


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _guest(client, nick="小北") -> tuple[str, str]:
    r = client.post("/api/auth/login", json={"nickname": nick, "consent": True}).json()
    return r["uid"], r["token"]


def _email_login(client, outbox, email, headers=None, **extra):
    assert client.post("/api/auth/code", json={"email": email}).status_code == 200
    code = outbox[-1][1]
    r = client.post("/api/auth/verify", json={"email": email, "code": code, "consent": True, **extra},
                    headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 默认要登录 ----------

def _routes() -> dict[str, set[str]]:
    """所有接口：路由模板 → 方法。用 OpenAPI 列表而不是 app.routes——新版 FastAPI 把 include_router 的路由包了一层。"""
    return {path: {m.upper() for m in ops} for path, ops in main.app.openapi()["paths"].items()}


def test_every_private_route_refuses_requests_without_a_session(client):
    checked = 0
    for path, methods in _routes().items():
        if path in auth.PUBLIC:
            continue
        url = path.replace("{", "").replace("}", "")  # 路径参数随便填
        for method in methods:
            r = client.request(method, url)
            assert r.status_code == 401, f"{method} {path} 没登录也进去了：{r.status_code}"
            checked += 1
    assert checked > 50


def test_public_list_only_names_routes_that_exist():
    assert auth.PUBLIC <= set(_routes()), sorted(auth.PUBLIC - set(_routes()))


def test_uid_in_query_body_or_path_must_be_the_session_owner(client):
    a, ta = _guest(client, "甲")
    b, _ = _guest(client, "乙")
    assert client.get(f"/api/me/facts?uid={a}", headers=_h(ta)).status_code == 200
    assert client.get(f"/api/me/facts?uid={b}", headers=_h(ta)).status_code == 403
    assert client.get(f"/api/me/facts?uid={a}").status_code == 401
    assert client.get(f"/api/me/facts?uid={a}", headers=_h("qy_not-a-session")).status_code == 401
    edge = {"uid": b, "kind": "language", "text": "粤语母语", "evidence_url": ""}
    assert client.post("/api/edges", json=edge, headers=_h(ta)).status_code == 403
    assert client.post("/api/edges", json={**edge, "uid": a}, headers=_h(ta)).status_code == 200


def test_task_detail_is_only_visible_to_its_owner(client):
    a, ta = _guest(client, "甲")
    _, tb = _guest(client, "乙")
    t = client.post("/api/tasks/generate", json={"uid": a, "direction": "ai", "level": 1}, headers=_h(ta)).json()
    assert client.get(f"/api/tasks/{t['id']}", headers=_h(ta)).status_code == 200
    assert client.get(f"/api/tasks/{t['id']}", headers=_h(tb)).status_code == 404


def test_upload_route_is_not_read_by_the_guard(client):
    a, ta = _guest(client)
    r = client.post(f"/api/projects/nope/submit?uid={a}", content=b"PK\x03\x04" + b"x" * 1000,
                    headers={**_h(ta), "Content-Type": "application/zip"})
    assert r.status_code == 404  # 过了登录，接口自己说项目不存在


# ---------- 邮箱验证码 ----------

def test_school_email_code_logs_in_and_a_second_device_gets_the_same_account(client, outbox):
    first = _email_login(client, outbox, " Xiao@Stu.PKU.edu.cn ", nickname="小北")
    assert first["created"] and first["email"] == "xiao@stu.pku.edu.cn" and first["nickname"] == "小北"
    assert outbox[-1][0] == "xiao@stu.pku.edu.cn"
    again = _email_login(client, outbox, "xiao@stu.pku.edu.cn")
    assert again["uid"] == first["uid"] and not again["created"] and again["token"] != first["token"]
    me = client.get("/api/auth/me", headers=_h(again["token"])).json()
    assert me["email"] == "xiao@stu.pku.edu.cn" and not me["guest"]


def test_only_school_domains_by_default(client, outbox, monkeypatch):
    r = client.post("/api/auth/code", json={"email": "someone@gmail.com"})
    assert r.status_code == 400 and "edu.cn" in r.json()["detail"]
    assert client.post("/api/auth/code", json={"email": "not-an-email"}).status_code == 400
    assert not outbox
    monkeypatch.setenv("AUTH_EMAIL_DOMAINS", "*")
    assert client.post("/api/auth/code", json={"email": "someone@gmail.com"}).status_code == 200


def test_wrong_codes_run_out_and_codes_are_single_use(client, outbox):
    email = "a@pku.edu.cn"
    client.post("/api/auth/code", json={"email": email})
    code = outbox[-1][1]
    wrong = "000000" if code != "000000" else "111111"
    r = client.post("/api/auth/verify", json={"email": email, "code": wrong})
    assert r.status_code == 400 and "4" in r.json()["detail"]
    for _ in range(4):
        client.post("/api/auth/verify", json={"email": email, "code": wrong})
    r = client.post("/api/auth/verify", json={"email": email, "code": code})
    assert r.status_code == 400 and "太多" in r.json()["detail"]  # 试满五次，对的也不认了

    client.post("/api/auth/code", json={"email": email})
    code = outbox[-1][1]
    assert client.post("/api/auth/verify", json={"email": email, "code": code}).status_code == 200
    assert client.post("/api/auth/verify", json={"email": email, "code": code}).status_code == 400


def test_code_expires(client, outbox):
    email = "a@pku.edu.cn"
    client.post("/api/auth/code", json={"email": email})
    with sqlite3.connect(store.DB_PATH) as c:
        c.execute("UPDATE login_codes SET expires_at=?", (time.time() - 1,))
    r = client.post("/api/auth/verify", json={"email": email, "code": outbox[-1][1]})
    assert r.status_code == 400 and "过期" in r.json()["detail"]


def test_sending_is_rate_limited_per_email_and_per_day(client, outbox, monkeypatch):
    monkeypatch.setattr(auth, "RESEND_GAP", 60)
    assert client.post("/api/auth/code", json={"email": "a@pku.edu.cn"}).status_code == 200
    assert client.post("/api/auth/code", json={"email": "a@pku.edu.cn"}).status_code == 429
    monkeypatch.setattr(auth, "RESEND_GAP", 0)
    for _ in range(auth.PER_EMAIL_HOUR - 1):
        assert client.post("/api/auth/code", json={"email": "a@pku.edu.cn"}).status_code == 200
    assert client.post("/api/auth/code", json={"email": "a@pku.edu.cn"}).status_code == 429
    monkeypatch.setattr(auth, "MAIL_DAILY", len(outbox))
    r = client.post("/api/auth/code", json={"email": "b@pku.edu.cn"})
    assert r.status_code == 503 and len(outbox) == auth.MAIL_DAILY


def test_per_source_limit_uses_forwarded_address_only_behind_a_proxy(client, monkeypatch):
    monkeypatch.setattr(auth, "PER_IP_HOUR", 2)
    fwd = {"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    for _ in range(3):  # 没开 TRUST_PROXY：不认转发头，测试客户端不是公网地址，不限
        assert client.post("/api/auth/login", json={"nickname": "x"}, headers=fwd).status_code == 200
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert client.post("/api/auth/login", json={"nickname": "x"}, headers=fwd).status_code == 200
    assert client.post("/api/auth/login", json={"nickname": "x"}, headers=fwd).status_code == 200
    assert client.post("/api/auth/login", json={"nickname": "x"}, headers=fwd).status_code == 429
    other = {"X-Forwarded-For": "198.51.100.9"}
    assert client.post("/api/auth/login", json={"nickname": "x"}, headers=other).status_code == 200


def test_without_mail_config_codes_are_refused_or_only_logged(client, monkeypatch, capsys):
    monkeypatch.setattr(mailer, "configured", lambda: False)
    r = client.post("/api/auth/code", json={"email": "a@pku.edu.cn"})
    assert r.status_code == 503
    assert client.get("/api/health").json()["auth"]["email_login"] is False

    monkeypatch.setenv("AUTH_DEV_CODES", "1")
    r = client.post("/api/auth/code", json={"email": "a@pku.edu.cn"})
    assert r.status_code == 200
    logged = [ln for ln in capsys.readouterr().out.splitlines() if "dev_code" in ln]
    code = __import__("json").loads(logged[-1])["code"]
    assert code not in r.text  # 验证码只在服务器日志里，不在响应里
    assert client.post("/api/auth/verify", json={"email": "a@pku.edu.cn", "code": code}).status_code == 200


# ---------- 访客、老用户、会话 ----------

def test_guest_binding_a_school_email_keeps_the_guest_data(client, outbox):
    uid, token = _guest(client)
    client.post("/api/edges", json={"uid": uid, "kind": "language", "text": "粤语母语", "evidence_url": ""},
                headers=_h(token))
    r = _email_login(client, outbox, "b@stu.pku.edu.cn", headers=_h(token))
    assert r["bound"] and r["uid"] == uid and not r["left_guest"]
    assert client.get(f"/api/auth/me", headers=_h(token)).status_code == 401  # 访客会话换成了新会话
    edges = client.get(f"/api/edges?uid={uid}", headers=_h(r["token"])).json()
    assert "粤语母语" in str(edges)


def test_guest_logging_into_an_existing_email_switches_account_and_says_so(client, outbox):
    owner = _email_login(client, outbox, "c@pku.edu.cn")
    _, guest_token = _guest(client)
    r = _email_login(client, outbox, "c@pku.edu.cn", headers=_h(guest_token))
    assert r["uid"] == owner["uid"] and r["left_guest"] and not r["bound"]


def test_pre_account_users_can_claim_their_uid_exactly_once(client):
    old = store.create_user("老用户")["uid"]
    with sqlite3.connect(store.DB_PATH) as c:  # 加账号之前建的号没有 claimed_at
        c.execute("UPDATE users SET claimed_at=NULL WHERE id=?", (old,))
    r = client.post("/api/auth/legacy", json={"uid": old})
    assert r.status_code == 200 and r.json()["uid"] == old
    assert client.get(f"/api/me/facts?uid={old}", headers=_h(r.json()["token"])).status_code == 200
    assert client.post("/api/auth/legacy", json={"uid": old}).status_code == 401
    fresh, _ = _guest(client)  # 新号一出生就算认领过，知道 uid 也认领不了
    assert client.post("/api/auth/legacy", json={"uid": fresh}).status_code == 401


def test_logout_and_expiry_end_the_session(client):
    uid, token = _guest(client)
    assert client.get("/api/auth/me", headers=_h(token)).status_code == 200
    client.post("/api/auth/logout", headers=_h(token))
    assert client.get("/api/auth/me", headers=_h(token)).status_code == 401
    _, token = _guest(client)
    with sqlite3.connect(store.DB_PATH) as c:
        c.execute("UPDATE sessions SET expires_at=?", (time.time() - 1,))
    assert client.get("/api/auth/me", headers=_h(token)).status_code == 401


def test_sessions_store_only_a_hash_of_the_token(client):
    _, token = _guest(client)
    with sqlite3.connect(store.DB_PATH) as c:
        dump = "\n".join(c.iterdump())
    assert token not in dump


def test_consent_is_recorded_against_the_current_privacy_version(client):
    r = client.post("/api/auth/login", json={"nickname": "x"}).json()
    assert r["consent_ok"] is False
    assert client.post("/api/auth/consent", json={"version": "2000-01-01"}, headers=_h(r["token"])).status_code == 409
    ok = client.post("/api/auth/consent", json={"version": auth.PRIVACY_VERSION}, headers=_h(r["token"])).json()
    assert ok["consent_ok"] is True


# ---------- 删号与导出 ----------

def test_delete_account_removes_every_row_and_the_session(client, outbox):
    r = _email_login(client, outbox, "d@pku.edu.cn")
    uid, h = r["uid"], _h(r["token"])
    client.post("/api/edges", json={"uid": uid, "kind": "language", "text": "粤语母语", "evidence_url": ""}, headers=h)
    client.post("/api/tasks/generate", json={"uid": uid, "direction": "ai", "level": 1}, headers=h)
    client.post("/api/onboard/start", json={"uid": uid}, headers=h)
    other, _ = _guest(client, "别人")

    exported = client.get("/api/me/export", headers=h)
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    data = exported.json()
    assert data["user"]["email"] == "d@pku.edu.cn" and data["edges"] and data["tasks"]
    assert "sessions" not in data and "token" not in data["user"]

    out = client.delete("/api/me", headers=h).json()
    assert out["ok"] and out["deleted"]["users"] == 1
    with sqlite3.connect(store.DB_PATH) as c:
        c.row_factory = sqlite3.Row
        for t in store._user_tables(c):
            assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id=?", (uid,)).fetchone()[0] == 0, t
        assert c.execute("SELECT COUNT(*) FROM login_codes WHERE email='d@pku.edu.cn'").fetchone()[0] == 0
    assert store.get_user(other)  # 别人不受影响
    assert client.get("/api/auth/me", headers=h).status_code == 401
    again = _email_login(client, outbox, "d@pku.edu.cn")  # 同一邮箱可以重新注册，是个新号
    assert again["created"] and again["uid"] != uid


# ---------- 库文件的位置 ----------

def test_db_path_follows_qiyan_db(tmp_path):
    target = tmp_path / "vol" / "qiyan.db"
    out = subprocess.run([sys.executable, "-c", "import store; print(store.DB_PATH)"], cwd=SERVER,
                         env={**os.environ, "QIYAN_DB": str(target)}, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == str(target)


# ---------- 备份 ----------

def test_backup_copies_a_consistent_snapshot_and_prunes_old_ones(tmp_path):
    uid = store.create_user("备份")["uid"]
    out = tmp_path / "bk"
    out.mkdir()
    old = out / "qiyan-20000101-000000.db"
    old.write_bytes(b"x")
    os.utime(old, (0, 0))
    sys.path.insert(0, str(SERVER.parent / "tools"))
    import backup_db
    dest = backup_db.backup(store.DB_PATH, out, 7)
    assert not old.exists() and dest.exists() and not list(out.glob("*.part"))
    with sqlite3.connect(dest) as c:
        assert c.execute("SELECT nickname FROM users WHERE id=?", (uid,)).fetchone()[0] == "备份"


# ---------- 前端 ----------

WEB = SERVER.parent / "web"


def test_every_frontend_request_goes_through_the_authenticated_helper():
    for name in ("app.js", "chat.js", "directions.js"):
        js = (WEB / "js" / name).read_text(encoding="utf-8")
        raw = re.findall(r"(?<![\w.])fetch\(", js)
        # 只有 apiFetch 自己里面那一处直接 fetch；别处直接 fetch 会漏掉会话令牌和接口地址
        assert len(raw) == (1 if name == "app.js" else 0), f"{name} 里有绕过 apiFetch 的请求"
        assert "/api/" not in "".join(re.findall(r"(?:href|src)=[\"'`][^\"'`]*", js)), f"{name} 用链接直接打接口，带不上令牌"


def test_new_account_classes_have_rules():
    css = (WEB / "css" / "styles.css").read_text(encoding="utf-8")
    for cls in ("login-step", "login-nick", "login-note", "consent-row", "privacy-box", "privacy-body",
                "account-panel", "account-actions"):
        assert re.search(rf"\.{re.escape(cls)}(?![\w-])", css), cls


def test_privacy_text_and_version_change_together():
    js = (WEB / "js" / "app.js").read_text(encoding="utf-8")
    text = re.search(r"const PRIVACY_HTML = `(.*?)`;", js, re.S).group(1)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    # 改了隐私说明：把 auth.PRIVACY_VERSION 换成当天日期（老用户会再同意一次），再把这里的指纹和日期一起更新
    assert (auth.PRIVACY_VERSION, digest) == ("2026-10-09", PRIVACY_DIGEST), digest


def test_sessions_slide_forward_when_used_after_a_day(client):
    _, token = _guest(client)
    with sqlite3.connect(store.DB_PATH) as c:
        c.execute("UPDATE sessions SET last_seen=?, expires_at=?", (time.time() - 2 * 86400, time.time() + 3600))
    assert client.get("/api/auth/me", headers=_h(token)).status_code == 200
    auth._TOUCH.submit(lambda: None).result()  # 等续期那个线程做完
    with sqlite3.connect(store.DB_PATH) as c:
        expires = c.execute("SELECT expires_at FROM sessions").fetchone()[0]
    assert expires > time.time() + auth.SESSION_TTL - 60
