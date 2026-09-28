# -*- coding: utf-8 -*-
"""演示版存储层：SQLite（标准库 sqlite3），单文件零运维。

表：users / facts / tasks / submissions / messages。
正式版将迁移到 SQLModel + Alembic（见 docs/ARCHITECTURE.md），
但表结构与本文件的字段一一对应，迁移成本可控。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from schemas import MicroTask, UserFact, new_id, now_iso

DB_PATH = Path(__file__).resolve().parent / "data" / "demo.db"
_LOCK = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  nickname TEXT NOT NULL,
  token TEXT NOT NULL,
  onboard_state TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  category TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  confidence REAL NOT NULL,
  source TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL,
  text TEXT NOT NULL,
  round TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portraits (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  snapshot TEXT NOT NULL DEFAULT '{}',
  active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_user ON facts(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_msgs_user ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_portraits_user ON portraits(user_id);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK, _conn() as c:
        c.executescript(_SCHEMA)


# ---------- users ----------

def create_user(nickname: str) -> dict[str, Any]:
    uid, token = new_id(), new_id()
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO users(id, nickname, token, onboard_state, created_at) VALUES(?,?,?,?,?)",
            (uid, nickname, token, "{}", now_iso()),
        )
    return {"uid": uid, "token": token, "nickname": nickname}


def get_user(uid: str) -> dict[str, Any] | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None


def set_onboard_state(uid: str, state: dict[str, Any]) -> None:
    with _LOCK, _conn() as c:
        c.execute("UPDATE users SET onboard_state=? WHERE id=?", (json.dumps(state, ensure_ascii=False), uid))


def get_onboard_state(uid: str) -> dict[str, Any]:
    u = get_user(uid)
    if not u:
        return {}
    try:
        return json.loads(u["onboard_state"] or "{}")
    except json.JSONDecodeError:
        return {}


# ---------- facts ----------

def _fact_row(r: sqlite3.Row) -> UserFact:
    return UserFact.from_dict({**dict(r), "evidence": json.loads(r["evidence"] or "[]")})


def add_fact(f: UserFact) -> UserFact:
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO facts(id,user_id,category,key,value,confidence,source,evidence,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (f.id, f.user_id, f.category, f.key, f.value, f.confidence, f.source,
             json.dumps(f.evidence, ensure_ascii=False), f.status, f.created_at, f.updated_at),
        )
    return f


def list_facts(uid: str, statuses: list[str] | None = None) -> list[UserFact]:
    q = "SELECT * FROM facts WHERE user_id=?"
    args: list[Any] = [uid]
    if statuses:
        q += f" AND status IN ({','.join('?' * len(statuses))})"
        args += statuses
    q += " ORDER BY created_at"
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    return [_fact_row(r) for r in rows]


def update_fact(fid: str, value: str | None = None, status: str | None = None) -> UserFact | None:
    f = get_fact(fid)
    if not f:
        return None
    if value is not None:
        f.value = value
    if status is not None:
        f.status = status
    f.updated_at = now_iso()
    with _LOCK, _conn() as c:
        c.execute(
            "UPDATE facts SET value=?, status=?, updated_at=? WHERE id=?",
            (f.value, f.status, f.updated_at, fid),
        )
    return f


def get_fact(fid: str) -> UserFact | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM facts WHERE id=?", (fid,)).fetchone()
    return _fact_row(row) if row else None


# ---------- tasks ----------

def save_task(t: MicroTask) -> MicroTask:
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO tasks(id, user_id, data) VALUES(?,?,?)",
            (t.id, t.user_id, json.dumps(t.to_dict(), ensure_ascii=False)),
        )
    return t


def get_task(tid: str) -> MicroTask | None:
    with _conn() as c:
        row = c.execute("SELECT data FROM tasks WHERE id=?", (tid,)).fetchone()
    return MicroTask.from_dict(json.loads(row["data"])) if row else None


def list_tasks(uid: str) -> list[MicroTask]:
    with _conn() as c:
        rows = c.execute("SELECT data FROM tasks WHERE user_id=? ORDER BY rowid", (uid,)).fetchall()
    return [MicroTask.from_dict(json.loads(r["data"])) for r in rows]


# ---------- submissions & messages ----------

def save_submission(task_id: str, uid: str, payload: str) -> str:
    sid = new_id()
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO submissions(id, task_id, user_id, payload, created_at) VALUES(?,?,?,?,?)",
            (sid, task_id, uid, payload, now_iso()),
        )
    return sid


def add_message(uid: str, role: str, text: str, round_id: str = "") -> None:
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO messages(id, user_id, role, text, round, created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), uid, role, text, round_id, now_iso()),
        )


def list_messages(uid: str) -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM messages WHERE user_id=? ORDER BY rowid", (uid,)).fetchall()
    return [dict(r) for r in rows]


# ---------- portraits（多份画像；当前份的对话和事实仍写在 live 表里） ----------

def _portrait_label(n: int) -> str:
    d = "零一二三四五六七八九"
    if n < 10:
        return "画像" + d[n]
    if n == 10:
        return "画像十"
    if n < 20:
        return "画像十" + d[n - 10]
    tens, ones = divmod(n, 10)
    return "画像" + d[tens] + "十" + (d[ones] if ones else "")


def _portrait_rows(c: sqlite3.Connection, uid: str) -> list[sqlite3.Row]:
    return c.execute(
        "SELECT * FROM portraits WHERE user_id=? ORDER BY created_at, rowid", (uid,)
    ).fetchall()


def _portrait_public(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [
        {"id": r["id"], "name": _portrait_label(i), "active": bool(r["active"]), "created_at": r["created_at"]}
        for i, r in enumerate(rows, 1)
    ]


def _dump_live(c: sqlite3.Connection, uid: str) -> dict[str, Any]:
    facts = []
    for r in c.execute("SELECT * FROM facts WHERE user_id=? ORDER BY created_at", (uid,)):
        item = dict(r)
        item["evidence"] = json.loads(item.get("evidence") or "[]")
        facts.append(item)
    msgs = [
        {"role": r["role"], "text": r["text"], "round": r["round"]}
        for r in c.execute("SELECT role, text, round FROM messages WHERE user_id=? ORDER BY rowid", (uid,))
    ]
    u = c.execute("SELECT onboard_state FROM users WHERE id=?", (uid,)).fetchone()
    state: dict[str, Any] = {}
    if u:
        try:
            state = json.loads(u["onboard_state"] or "{}")
        except json.JSONDecodeError:
            state = {}
    return {"facts": facts, "messages": msgs, "state": state}


def _clear_live(c: sqlite3.Connection, uid: str) -> None:
    c.execute("DELETE FROM facts WHERE user_id=?", (uid,))
    c.execute("DELETE FROM messages WHERE user_id=?", (uid,))
    c.execute("UPDATE users SET onboard_state=? WHERE id=?", ("{}", uid))


def _load_live(c: sqlite3.Connection, uid: str, snap: dict[str, Any]) -> None:
    _clear_live(c, uid)
    for f in snap.get("facts") or []:
        c.execute(
            "INSERT INTO facts(id,user_id,category,key,value,confidence,source,evidence,status,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (f.get("id") or new_id(), uid, f.get("category") or "interest", f.get("key") or "",
             f.get("value") or "", float(f.get("confidence") or 0.5), f.get("source") or "declared",
             json.dumps(f.get("evidence") or [], ensure_ascii=False), f.get("status") or "draft",
             f.get("created_at") or now_iso(), f.get("updated_at") or now_iso()),
        )
    for m in snap.get("messages") or []:
        c.execute(
            "INSERT INTO messages(id, user_id, role, text, round, created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), uid, m.get("role") or "assistant", m.get("text") or "", m.get("round") or "", now_iso()),
        )
    c.execute(
        "UPDATE users SET onboard_state=? WHERE id=?",
        (json.dumps(snap.get("state") or {}, ensure_ascii=False), uid),
    )


def _save_active(c: sqlite3.Connection, uid: str) -> None:
    row = c.execute("SELECT id FROM portraits WHERE user_id=? AND active=1", (uid,)).fetchone()
    if not row:
        return
    snap = json.dumps(_dump_live(c, uid), ensure_ascii=False)
    c.execute("UPDATE portraits SET snapshot=? WHERE id=?", (snap, row["id"]))


def list_portraits(uid: str) -> list[dict[str, Any]]:
    with _LOCK, _conn() as c:
        rows = _portrait_rows(c, uid)
        if not rows:
            c.execute(
                "INSERT INTO portraits(id, user_id, snapshot, active, created_at) VALUES(?,?,?,?,?)",
                (new_id(), uid, json.dumps(_dump_live(c, uid), ensure_ascii=False), 1, now_iso()),
            )
            rows = _portrait_rows(c, uid)
        return _portrait_public(rows)


def open_new_portrait(uid: str) -> None:
    """把当前这份收进快照，清空现场，留下一份空的新画像。"""
    with _LOCK, _conn() as c:
        if not _portrait_rows(c, uid):
            c.execute(
                "INSERT INTO portraits(id, user_id, snapshot, active, created_at) VALUES(?,?,?,?,?)",
                (new_id(), uid, json.dumps(_dump_live(c, uid), ensure_ascii=False), 1, now_iso()),
            )
        _save_active(c, uid)
        c.execute("UPDATE portraits SET active=0 WHERE user_id=?", (uid,))
        _clear_live(c, uid)
        c.execute(
            "INSERT INTO portraits(id, user_id, snapshot, active, created_at) VALUES(?,?,?,?,?)",
            (new_id(), uid, "{}", 1, now_iso()),
        )


def activate_portrait(uid: str, pid: str) -> None:
    with _LOCK, _conn() as c:
        target = c.execute("SELECT * FROM portraits WHERE id=? AND user_id=?", (pid, uid)).fetchone()
        if not target:
            raise KeyError(pid)
        if target["active"]:
            return
        _save_active(c, uid)
        try:
            snap = json.loads(target["snapshot"] or "{}")
        except json.JSONDecodeError:
            snap = {}
        _load_live(c, uid, snap)
        c.execute("UPDATE portraits SET active=0 WHERE user_id=?", (uid,))
        c.execute("UPDATE portraits SET active=1 WHERE id=?", (pid,))


def delete_portrait(uid: str, pid: str) -> bool:
    """删一份画像。若删的是最后一份，清空并返回 True，调用方需要重新开场。"""
    with _LOCK, _conn() as c:
        rows = _portrait_rows(c, uid)
        target = next((r for r in rows if r["id"] == pid), None)
        if not target:
            raise KeyError(pid)
        if len(rows) == 1:
            _clear_live(c, uid)
            c.execute("UPDATE portraits SET snapshot=? WHERE id=?", ("{}", pid))
            return True
        if target["active"]:
            other = next(r for r in rows if r["id"] != pid)
            _save_active(c, uid)
            try:
                snap = json.loads(other["snapshot"] or "{}")
            except json.JSONDecodeError:
                snap = {}
            _load_live(c, uid, snap)
            c.execute("UPDATE portraits SET active=0 WHERE user_id=?", (uid,))
            c.execute("UPDATE portraits SET active=1 WHERE id=?", (other["id"],))
        c.execute("DELETE FROM portraits WHERE id=? AND user_id=?", (pid, uid))
        return False
