# -*- coding: utf-8 -*-
"""院系-专业知识库的 MCP 服务（Model Context Protocol）。

两种传输都支持，工具表只有一份：
  · stdio            `python server/mcp_curriculum.py`                    给 Claude Desktop / Cursor / DSH(stdio)
  · streamable-http  `POST http://127.0.0.1:8100/mcp`                     DSH 的 dsh-mcp-client 模板用的这种

工具（都只读本地 JSON，不联网、不调模型）：
  major_lookup / major_detail / match_transcript / minor_programs / course_lookup / kb_stats

设计纪律：
  · 一个名字对上多个专业时返回全部候选（专业簇），不替用户挑一个；
  · 未知专业返回最像的 3 个名字，而不是编一个；
  · 所有回答带来源页（书内页 + PDF 页），便于人工回查；
  · 数据口径与 tools/curriculum/validate.py 的留一验证一致（院系级 100%、专业级 89–91%）。
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import curriculum  # noqa: E402

PROTOCOL = "2025-06-18"
SERVER = {"name": "researchguide-curriculum", "version": "0.1.0"}

# ---------------- 工具表 ----------------

TOOLS: list[dict] = [
    {
        "name": "major_lookup",
        "description": "按用户说法查北大专业（院系-专业）。写法随意：『经济学』『经济学专业』"
                       "『信息与计算科学（图灵班）』都认。**也可以直接问院系**（『信管』『信息管理系』"
                       "『数学科学学院有哪些专业』），这时返回该院系的全部专业——这就是「有哪些分流」的答案。"
                       "一个名字可能对上多个专业——这时返回全部候选（专业簇），低年级成绩单本来就分不开"
                       "兄弟方向，不要替用户挑一个。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "专业名 / 用户的原话"},
                "minor": {"type": "boolean", "description": "查辅修、双专业层时为 true", "default": False},
                "limit": {"type": "integer", "description": "最多返回几个候选", "default": 8},
            },
            "required": ["query"],
        },
    },
    {
        "name": "major_detail",
        "description": "一个专业的完整画像：学分结构、专业必修课清单（含课号/学分/学期）、"
                       "学位与毕业总学分、数学/计算底子、**同院兄弟专业**（低年级认不出细分方向时要用）、来源页。",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "专业名，例如 经济学专业"}},
            "required": ["name"],
        },
    },
    {
        "name": "match_transcript",
        "description": "拿成绩单课号认院系/专业：返回院系排名、专业排名（F1 分、命中数、以及**还缺哪几门必修**）。"
                       "只知道大一/大二课时用 low_only=true。院系级可信度高（留一验证 100%），"
                       "专业级请当作专业簇看（同院兄弟专业必修结构高度重合）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "codes": {"type": "array", "items": {"type": "string"},
                          "description": "8 位课号数组，也可以直接贴整段成绩单文本"},
                "low_only": {"type": "boolean", "description": "只看大一/大二必修", "default": False},
                "top": {"type": "integer", "description": "返回前几名", "default": 5},
            },
            "required": ["codes"],
        },
    },
    {
        "name": "minor_programs",
        "description": "辅修 / 双专业：总学分、核心课程、**替代课程**（主修已修同名必修课时改修这些课才算完成）、"
                       "修读要求、来源页。可按名字查，也可按院系列出。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "例如『计算机科学与技术（双专业）』『法学辅修』"},
                "dept": {"type": "string", "description": "按院系列出，例如『工学院』"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "course_lookup",
        "description": "课号反查：这门课叫什么、哪些专业把它列为必修、课号前 4 位（开课院系）线索。",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "8 位课号，例如 02530060"}},
            "required": ["code"],
        },
    },
    {
        "name": "kb_stats",
        "description": "知识库规模与覆盖范围（专业卡 / 培养方案 / 辅修方案 / 课程索引），用来确认服务健康。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def list_tools() -> list[dict]:
    return TOOLS


def _dispatch(name: str, args: dict) -> dict:
    """真正的分派。未登记的工具抛 KeyError，执行出错抛原异常。"""
    if name == "major_lookup":
        return curriculum.find_major(str(args.get("query", "")),
                                     minor=bool(args.get("minor", False)),
                                     limit=int(args.get("limit", 8)))
    if name == "major_detail":
        return curriculum.major_detail(str(args.get("name", "")))
    if name == "match_transcript":
        return curriculum.match(args.get("codes", []), low_only=bool(args.get("low_only", False)),
                                top=int(args.get("top", 5)))
    if name == "minor_programs":
        return curriculum.find_minor(str(args.get("query", "")), str(args.get("dept", "")),
                                     top=int(args.get("limit", 20)))
    if name == "course_lookup":
        return curriculum.course_detail(str(args.get("code", "")))
    if name == "kb_stats":
        return curriculum.stats()
    raise KeyError(name)


def run_tool(name: str, args: dict | None) -> dict:
    """执行一个工具，返回**原始结果 dict**，且保证不抛异常。

    知识库工具的唯一入口：MCP 的 tools/call 和产品内对话的 tools.py 都走这里，
    于是在对话里问「信管有哪些专业分流」和外部 AI 客户端调 major_lookup
    拿到的是同一份数据、同一套口径。
    """
    try:
        return _dispatch(name, args or {})
    except KeyError:
        return {"ok": False, "error": f"未知工具：{name}"}
    except Exception as exc:                                            # noqa: BLE001
        return {"ok": False, "error": f"{name} 执行失败：{exc!r}"}


def call_tool(name: str, args: dict | None) -> dict:
    """执行一个工具，返回 MCP 的 content 结构。"""
    try:
        data = _dispatch(name, args or {})
    except KeyError:
        return {"content": [{"type": "text", "text": f"未知工具：{name}"}], "isError": True}
    except Exception as exc:                                            # noqa: BLE001
        return {"content": [{"type": "text", "text": f"{name} 执行失败：{exc!r}"}], "isError": True}

    out = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
    if isinstance(data, dict):
        out["structuredContent"] = data                                # 支持结构化输出的客户端可直接取字段
    return out


# ---------------- JSON-RPC / MCP ----------------

def handle(msg: dict) -> dict | None:
    """处理一条 JSON-RPC 消息；通知（没有 id）返回 None。"""
    if not isinstance(msg, dict):
        return _err(None, -32600, "invalid request")
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if mid is None:                                                   # 通知：不回
        return None
    if method == "initialize":
        want = params.get("protocolVersion") or PROTOCOL
        return _ok(mid, {"protocolVersion": want, "capabilities": {"tools": {"listChanged": False}},
                         "serverInfo": SERVER,
                         "instructions": "北大院系-专业培养方案知识库。先 major_lookup 找专业，"
                                         "再 major_detail 看要求；有成绩单课号时用 match_transcript 认院系。"})
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": list_tools()})
    if method == "tools/call":
        name = params.get("name", "")
        return _ok(mid, call_tool(name, params.get("arguments")))
    if method in ("resources/list", "resources/templates/list"):
        return _ok(mid, {"resources": [], "resourceTemplates": []})
    if method == "prompts/list":
        return _ok(mid, {"prompts": []})
    return _err(mid, -32601, f"method not found: {method}")


def http_handle(payload) -> dict | list | None:
    """给 streamable-http 用：支持单条消息和批量数组。"""
    if isinstance(payload, list):
        out = [r for r in (handle(m) for m in payload) if r is not None]
        return out or None
    return handle(payload)


def _ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def main() -> None:
    """stdio 传输：一行一条 JSON-RPC（UTF-8，不输出任何别的东西到 stdout）。"""
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", write_through=True)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            continue
        resp = http_handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
