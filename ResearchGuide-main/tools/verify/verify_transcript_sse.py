# -*- coding: utf-8 -*-
"""走 SSE 那条路验成绩单识别。

前端用的是 `/api/dialogue/stream`（不是 `/api/dialogue/turn`），
所以光验 turn() 不够——用户点「发送」走的是 stream。
第一版就是在这个地方吃过亏：API 通了不等于用户那条路通了。
"""
from __future__ import annotations

import json
import random
import urllib.request

B = "http://127.0.0.1:8100"
fails = 0


def check(ok, label, extra=""):
    global fails
    print(f"  [{'OK ' if ok else '!! '}] {label} {extra}")
    if not ok:
        fails += 1


def post(path, body):
    r = urllib.request.Request(B + path, data=json.dumps(body, ensure_ascii=False).encode(),
                               method="POST", headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=180).read().decode()


def login(nick):
    return json.loads(post("/api/auth/login", {"nickname": nick}))["uid"]


TS = """25-26学年度1学期
3
学分
高等数学 (B) (二)
专业必修
86.5
3
学分
线性代数 (B)
专业必修
88
2
学分
计算概论（C）
专业必修
92
2
学分
中国美术简史
通选课
B+
2
学分
军事理论（上）
公共必修
IP
24-25学年度2学期
3
学分
概率统计 (B)
专业必修
96
1
学分
大学英语听说
全校必修
88.5
"""

uid = login(f"SSE成绩单{random.randint(1000, 9999)}")

print("=== 走 /api/dialogue/stream 粘成绩单 ===")
raw = post("/api/dialogue/stream", {"uid": uid, "message": TS})

# 解 SSE 帧：事件名在 event: 行上，不在 JSON 里
frames = []
for block in raw.split("\n\n"):
    name, data = None, None
    for line in block.split("\n"):
        if line.startswith("event: "):
            name = line[7:].strip()
        elif line.startswith("data: "):
            data = json.loads(line[6:])
    if name:
        frames.append((name, data))

kinds = [k for k, _ in frames]
print(f"        帧：{kinds}")
result = next((d for k, d in frames if k == "result"), None)
imp = (result or {}).get("transcript_import") or {}

check(result is not None, "SSE 里有 result 帧")
check(imp.get("written") == 7, "识别并落库 7 门", f"实际 {imp.get('written')}")
check(len(imp.get("derived") or []) >= 1, "推出了能力结论",
      f"{len(imp.get('derived') or [])} 条")
check(result and result["next_action"] is None, "没有顺手派任务")
# 成绩单是导入，不该有 delta 帧（没调模型、没流式）
check("delta" not in kinds, "没有 delta 帧（说明确实没调模型去流式生成）")

reply = (result or {}).get("reply", "")
check("7 门课" in reply, "回复说清了读了几门")
check("中国美术简史" in reply and "没有算进绩点" in reply, "说清了哪几门没算进绩点")
check("军事理论（上）" in reply, "说清了哪些还在修")

print("\n=== 对照：普通聊天仍然走模型那条路 ===")
uid2 = login(f"SSE聊天{random.randint(1000, 9999)}")
raw2 = post("/api/dialogue/stream", {"uid": uid2, "message": "你好，我想弄清楚我适合做什么方向"})
frames2 = []
for block in raw2.split("\n\n"):
    name = None
    for line in block.split("\n"):
        if line.startswith("event: "):
            name = line[7:].strip()
    if name:
        frames2.append(name)
print(f"        帧：{frames2}")
check("result" in frames2, "普通聊天也有 result 帧")
check("observe" in frames2 or "delta" in frames2, "普通聊天走了正常的观察/生成流程")

print("\n" + ("全部通过" if not fails else f"失败 {fails} 项"))
raise SystemExit(1 if fails else 0)
