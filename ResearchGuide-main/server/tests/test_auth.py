# -*- coding: utf-8 -*-
"""账号：默认要登录、uid 必须是本人、手机号短信验证码、访客绑手机号、老用户认领、删号与导出。

这里用真的 auth.guard（其余测试把它换成「信请求里的 uid」）。不联网、不发短信：
阿里云那一侧用 texts 夹具假装（它出码、它核验），签名和报文另用本机假服务器测。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import main  # noqa: E402
import sms  # noqa: E402
import store  # noqa: E402

pytestmark = pytest.mark.real_auth
SERVER = Path(__file__).resolve().parent.parent
PRIVACY_DIGEST = "b431f26a5d20"  # web/js/app.js 里 PRIVACY_HTML 的指纹，见最后一个测试
PHONE = "13800138000"


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "auth.db")
    store.init_db()
    auth._IP_HITS.clear()
    for k in ("AUTH_DEV_CODES", "TRUST_PROXY", "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
              "ALIBABA_CLOUD_SECURITY_TOKEN", "SMS_SIGN_NAME", "SMS_TEMPLATE_CODE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def client():
    return TestClient(main.app)


class FakeAliyun:
    """假装阿里云短信认证：发的时候出一个码记下，核验时比对。"""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}
        self.sent: list[str] = []
        self.checks = 0

    def send(self, phone: str, minutes: int) -> None:
        self.codes[phone] = f"{secrets.randbelow(10 ** 6):06d}"
        self.sent.append(phone)

    def check(self, phone: str, code: str) -> bool:
        self.checks += 1
        return self.codes.get(phone) == code


@pytest.fixture
def texts(monkeypatch):
    fake = FakeAliyun()
    monkeypatch.setattr(sms, "configured", lambda: True)
    monkeypatch.setattr(sms, "send", fake.send)
    monkeypatch.setattr(sms, "check", fake.check)
    monkeypatch.setattr(auth, "RESEND_GAP", 0)
    return fake


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _guest(client, nick="小北") -> tuple[str, str]:
    r = client.post("/api/auth/login", json={"nickname": nick, "consent": True}).json()
    return r["uid"], r["token"]


def _phone_login(client, texts, phone=PHONE, headers=None, **extra):
    r = client.post("/api/auth/sms/send", json={"phone": phone})
    assert r.status_code == 200, r.text
    num = auth._check_phone(phone)
    r = client.post("/api/auth/sms/verify", json={"phone": phone, "code": texts.codes[num], "consent": True, **extra},
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


# ---------- 手机号验证码 ----------

def test_phone_code_logs_in_and_a_second_device_gets_the_same_account(client, texts):
    first = _phone_login(client, texts, " 138 0013-8000 ", nickname="小北")
    assert first["created"] and first["phone"] == "138****8000" and first["nickname"] == "小北"
    assert texts.sent == [PHONE]
    again = _phone_login(client, texts, "+86 13800138000")
    assert again["uid"] == first["uid"] and not again["created"] and again["token"] != first["token"]
    me = client.get("/api/auth/me", headers=_h(again["token"])).json()
    assert me["phone"] == "138****8000" and not me["guest"]


def test_only_mainland_mobile_numbers(client, texts):
    for bad in ("12345", "23800138000", "+1 650 253 0000", "1380013800a", ""):
        r = client.post("/api/auth/sms/send", json={"phone": bad})
        assert r.status_code == 400 and "手机号" in r.json()["detail"], bad
    assert not texts.sent


def test_wrong_codes_run_out_and_codes_are_single_use(client, texts):
    client.post("/api/auth/sms/send", json={"phone": PHONE})
    code = texts.codes[PHONE]
    wrong = "000000" if code != "000000" else "111111"
    r = client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": wrong})
    assert r.status_code == 400 and "4" in r.json()["detail"]
    for _ in range(4):
        client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": wrong})
    r = client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": code})
    assert r.status_code == 400 and "过期" in r.json()["detail"]  # 试满五次就作废，对的也不认了

    client.post("/api/auth/sms/send", json={"phone": PHONE})
    code = texts.codes[PHONE]
    assert client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": code}).status_code == 200
    # 阿里云那边同一个码在有效期内可能还会 PASS；我们这边用过就作废，不再去问
    checks = texts.checks
    assert client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": code}).status_code == 400
    assert texts.checks == checks


def test_code_expires(client, texts):
    client.post("/api/auth/sms/send", json={"phone": PHONE})
    with sqlite3.connect(store.DB_PATH) as c:
        c.execute("UPDATE sms_codes SET expires_at=?", (time.time() - 1,))
    r = client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": texts.codes[PHONE]})
    assert r.status_code == 400 and "过期" in r.json()["detail"]


def test_sending_is_rate_limited_per_phone_and_per_day(client, texts, monkeypatch):
    monkeypatch.setattr(auth, "RESEND_GAP", 60)
    assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 200
    assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 429
    monkeypatch.setattr(auth, "RESEND_GAP", 0)
    for _ in range(auth.PER_PHONE_HOUR - 1):
        assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 200
    assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 429
    monkeypatch.setattr(auth, "SMS_DAILY", len(texts.sent))
    r = client.post("/api/auth/sms/send", json={"phone": "13900139000"})
    assert r.status_code == 503 and len(texts.sent) == auth.SMS_DAILY


def test_per_phone_daily_cap_counts_across_hours(client, texts, monkeypatch):
    monkeypatch.setattr(auth, "PER_PHONE_HOUR", 100)
    for _ in range(auth.PER_PHONE_DAY):
        assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 200
    assert client.post("/api/auth/sms/send", json={"phone": PHONE}).status_code == 429


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


def test_aliyun_errors_become_plain_messages(client, texts, monkeypatch):
    def refuse(code):
        def send(phone, minutes):
            raise sms.SmsError(code, "原文")
        return send

    monkeypatch.setattr(sms, "send", refuse("BUSINESS_LIMIT_CONTROL"))
    r = client.post("/api/auth/sms/send", json={"phone": PHONE})
    assert r.status_code == 429 and "太多" in r.json()["detail"]
    monkeypatch.setattr(sms, "send", refuse("SignatureDoesNotMatch"))
    r = client.post("/api/auth/sms/send", json={"phone": PHONE})
    assert r.status_code == 502 and "原文" not in r.text
    assert store.sms_day_count(auth._today()) == 0  # 没发出去的不计数

    monkeypatch.setattr(sms, "send", texts.send)
    client.post("/api/auth/sms/send", json={"phone": PHONE})

    def broken(phone, code):
        raise OSError("网络断了")

    monkeypatch.setattr(sms, "check", broken)
    r = client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": "123456"})
    assert r.status_code == 502
    assert store.sms_row(PHONE)["tries"] == 0  # 核验接口自己出错，不算用户试错


def test_without_sms_config_codes_are_refused_or_only_logged(client, capsys, monkeypatch):
    r = client.post("/api/auth/sms/send", json={"phone": PHONE})
    assert r.status_code == 503
    assert client.get("/api/health").json()["auth"]["sms_login"] is False

    monkeypatch.setenv("AUTH_DEV_CODES", "1")
    assert client.get("/api/health").json()["auth"]["sms_login"] is True
    r = client.post("/api/auth/sms/send", json={"phone": PHONE})
    assert r.status_code == 200
    logged = [ln for ln in capsys.readouterr().out.splitlines() if "dev_code" in ln]
    code = json.loads(logged[-1])["code"]
    assert code not in r.text  # 验证码只在服务器日志里，不在响应里
    assert client.post("/api/auth/sms/verify", json={"phone": PHONE, "code": code}).status_code == 200


def test_dev_codes_are_ignored_once_aliyun_is_configured(monkeypatch):
    monkeypatch.setenv("AUTH_DEV_CODES", "1")
    for k, v in {"ALIBABA_CLOUD_ACCESS_KEY_ID": "id", "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "s",
                 "SMS_SIGN_NAME": "签名", "SMS_TEMPLATE_CODE": "100001"}.items():
        monkeypatch.setenv(k, v)
    assert sms.configured() and not auth._dev_codes()


# ---------- 阿里云接口：签名与报文 ----------

def test_signature_matches_aliyun_documented_example():
    params = {"AccessKeyId": "testid", "Action": "DescribeRegions", "Format": "XML", "SignatureMethod": "HMAC-SHA1",
              "SignatureNonce": "3ee8c1b8-83d3-44af-a94f-4e0ad82fd6cf", "SignatureVersion": "1.0",
              "Timestamp": "2016-02-23T12:46:24Z", "Version": "2014-05-26"}
    assert sms.sign(params, "testsecret") == "OLeaidS1JvxuMvnyHOwuJ+uX5qY="


@pytest.fixture
def aliyun_stub(monkeypatch):
    """本机假的 dypnsapi：记下收到的查询参数，按 replies 回话。"""
    seen: list[dict] = []
    replies: list[tuple[int, dict]] = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query)))
            status, body = replies.pop(0)
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(sms, "ENDPOINT", f"http://127.0.0.1:{srv.server_address[1]}/")
    for k, v in {"ALIBABA_CLOUD_ACCESS_KEY_ID": "kid", "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "ksecret",
                 "SMS_SIGN_NAME": "速通互联验证码", "SMS_TEMPLATE_CODE": "100001"}.items():
        monkeypatch.setenv(k, v)
    yield seen, replies
    srv.shutdown()


def test_send_and_check_are_signed_requests_with_the_right_fields(aliyun_stub):
    seen, replies = aliyun_stub
    replies += [(200, {"Code": "OK", "Success": True, "Model": {"BizId": "b"}}),
                (200, {"Code": "OK", "Success": True, "Model": {"VerifyResult": "PASS"}}),
                (200, {"Code": "OK", "Success": True, "Model": {"VerifyResult": "UNKNOWN"}})]
    sms.send(PHONE, 5)
    assert sms.check(PHONE, "123456") is True
    assert sms.check(PHONE, "654321") is False
    sent = seen[0]
    assert sent["Action"] == "SendSmsVerifyCode" and sent["Version"] == "2017-05-25"
    assert sent["PhoneNumber"] == PHONE and sent["SignName"] == "速通互联验证码" and sent["TemplateCode"] == "100001"
    assert json.loads(sent["TemplateParam"]) == {"code": "##code##", "min": "5"}  # 阿里云出码，我们不碰验证码
    assert sent["CodeLength"] == "6" and sent["ValidTime"] == "300" and sent["ReturnVerifyCode"] == "false"
    assert seen[1]["Action"] == "CheckSmsVerifyCode" and seen[1]["VerifyCode"] == "123456"
    for q in seen:
        sig = q.pop("Signature")
        assert sig == sms.sign(q, "ksecret") and q["AccessKeyId"] == "kid"
        assert "SecurityToken" not in q


def test_error_replies_and_sts_tokens(aliyun_stub, monkeypatch):
    seen, replies = aliyun_stub
    monkeypatch.setenv("ALIBABA_CLOUD_SECURITY_TOKEN", "sts-token")
    replies.append((400, {"Code": "isv.BUSINESS_LIMIT_CONTROL", "Message": "触发天级流控"}))
    with pytest.raises(sms.SmsError) as err:
        sms.send(PHONE, 5)
    assert err.value.code == "BUSINESS_LIMIT_CONTROL"
    assert seen[0]["SecurityToken"] == "sts-token"  # 函数计算挂角色时用临时密钥


# ---------- 访客、老用户、会话 ----------

def test_guest_binding_a_phone_keeps_the_guest_data(client, texts):
    uid, token = _guest(client)
    client.post("/api/edges", json={"uid": uid, "kind": "language", "text": "粤语母语", "evidence_url": ""},
                headers=_h(token))
    r = _phone_login(client, texts, headers=_h(token))
    assert r["bound"] and r["uid"] == uid and not r["left_guest"]
    assert client.get("/api/auth/me", headers=_h(token)).status_code == 401  # 访客会话换成了新会话
    edges = client.get(f"/api/edges?uid={uid}", headers=_h(r["token"])).json()
    assert "粤语母语" in str(edges)


def test_guest_logging_into_an_existing_phone_switches_account_and_says_so(client, texts):
    owner = _phone_login(client, texts)
    _, guest_token = _guest(client)
    r = _phone_login(client, texts, headers=_h(guest_token))
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

def test_delete_account_removes_every_row_and_the_session(client, texts):
    r = _phone_login(client, texts)
    uid, h = r["uid"], _h(r["token"])
    client.post("/api/edges", json={"uid": uid, "kind": "language", "text": "粤语母语", "evidence_url": ""}, headers=h)
    client.post("/api/tasks/generate", json={"uid": uid, "direction": "ai", "level": 1}, headers=h)
    client.post("/api/onboard/start", json={"uid": uid}, headers=h)
    other, _ = _guest(client, "别人")

    exported = client.get("/api/me/export", headers=h)
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    data = exported.json()
    assert data["user"]["phone"] == PHONE and data["edges"] and data["tasks"]
    assert "sessions" not in data and "token" not in data["user"]

    out = client.delete("/api/me", headers=h).json()
    assert out["ok"] and out["deleted"]["users"] == 1
    with sqlite3.connect(store.DB_PATH) as c:
        c.row_factory = sqlite3.Row
        for t in store._user_tables(c):
            assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id=?", (uid,)).fetchone()[0] == 0, t
        assert c.execute("SELECT COUNT(*) FROM sms_codes WHERE phone=?", (PHONE,)).fetchone()[0] == 0
    assert store.get_user(other)  # 别人不受影响
    assert client.get("/api/auth/me", headers=h).status_code == 401
    again = _phone_login(client, texts)  # 同一号码可以重新注册，是个新号
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
