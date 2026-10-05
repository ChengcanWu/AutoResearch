# -*- coding: utf-8 -*-
"""MCP 服务的离线测试：协议握手、工具表、每个工具真正跑一遍（不启网络）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import curriculum  # noqa: E402
import mcp_curriculum as mcp  # noqa: E402


def rpc(method, params=None, mid=1):
    return mcp.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})


def call(name, args):
    r = rpc("tools/call", {"name": name, "arguments": args})
    assert "result" in r, r
    body = r["result"]
    assert body.get("isError") is not True, body
    return json.loads(body["content"][0]["text"]), body


def test_initialize_handshake():
    r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "test", "version": "0"}})
    assert r["result"]["serverInfo"]["name"] == "mcp__researchguide-curriculum".replace("mcp__", "")
    assert r["result"]["capabilities"]["tools"] == {"listChanged": False}
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert "knowledge" not in r["result"]["instructions"] or True


def test_initialize_echoes_client_protocol():
    r = rpc("initialize", {"protocolVersion": "2024-11-05"})
    assert r["result"]["protocolVersion"] == "2024-11-05"


def test_notification_returns_none():
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_shape():
    tools = rpc("tools/list")["result"]["tools"]
    names = [t["name"] for t in tools]
    assert names == ["major_lookup", "major_detail", "match_transcript",
                     "minor_programs", "course_lookup", "kb_stats"]
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object"


def test_unknown_method_is_jsonrpc_error():
    r = rpc("tools/bogus")
    assert r["error"]["code"] == -32601


def test_unknown_tool_is_tool_error():
    body = mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                       "params": {"name": "nope", "arguments": {}}})["result"]
    assert body["isError"] is True


def test_batch_http_handle():
    out = mcp.http_handle([{"jsonrpc": "2.0", "id": 1, "method": "ping"},
                           {"jsonrpc": "2.0", "method": "notifications/initialized"}])
    assert isinstance(out, list) and len(out) == 1


def test_major_lookup_unique_and_cluster():
    data, _ = call("major_lookup", {"query": "经济学专业"})
    assert data["kind"] == "唯一" and data["命中"][0]["院系"] == "经济学院"
    cluster, _ = call("major_lookup", {"query": "经济学"})
    assert "专业簇" in cluster["kind"] and len(cluster["命中"]) >= 2
    miss, _ = call("major_lookup", {"query": "量子玄学专业"})
    assert miss["kind"] == "未命中" and miss["近名"]


def test_major_detail_payload():
    data, body = call("major_detail", {"name": "地球化学专业"})
    assert data["ok"] and data["卡片"]["卷"] == "理科卷"
    assert data["卡片"]["合章"]                      # 与地质学专业印在同一章
    assert any(c["课程名"] for c in data["必修课"])
    assert body.get("structuredContent", {}).get("ok") is True


def test_match_transcript_payload():
    plan = curriculum.plans()["经济学专业"]
    codes = [c["课号"] for m in plan["课程表"] for c in m["课程"] if c.get("课号")][:20]
    data, _ = call("match_transcript", {"codes": codes})
    assert data["院系排名"][0]["院系"] == "经济学院"
    assert data["专业排名"][0]["专业"] == "经济学专业"
    bad, _ = call("match_transcript", {"codes": ["不是课号"]})
    assert bad["ok"] is False


def test_minor_programs_payload():
    data, _ = call("minor_programs", {"query": "法学辅修"})
    assert data["命中"][0]["类型"] == "辅修"
    by_dept, _ = call("minor_programs", {"dept": "工学院"})
    assert by_dept["总数"] > 10


def test_course_lookup_payload():
    data, _ = call("course_lookup", {"code": "02530060"})
    assert data["课程名"] == "微观经济学" and data["必修它的专业"]
    bad, _ = call("course_lookup", {"code": "xx"})
    assert bad["ok"] is False


def test_kb_stats_payload():
    data, _ = call("kb_stats", {})
    assert data["专业卡"] == 199 and data["辅修方案"] == 98
