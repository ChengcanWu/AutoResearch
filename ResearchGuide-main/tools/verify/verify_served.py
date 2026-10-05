"""验证浏览器**实际收到**的东西 + 用真实成绩单走完整接口。

为什么单独验「收到的字节」：之前我用 PowerShell 改 index.html 的版本号，
把 4 个中文连后面的 ASCII 一起压成了 U+FFFD（`</small>` 少了 `<`、
两个属性少了收尾引号）。代码在 git 里看着没问题，**只有看真正发出去的字节才发现**。

前置：python server/main.py 已在 8100 起好。
"""
from __future__ import annotations

import json
import random
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # tools/verify -> 仓库根
BASE = "http://127.0.0.1:8100"

# 合成的成绩单。**不要**换成任何人的真实成绩单——这个文件会随仓库发给别人。
# 覆盖同样的分支：百分制（含小数）、字母等级、在修（IP）、五级制（合格）、W、0 学分。
# 末尾「总学分」必须等于各课学分之和，第 5 节那条断言才有意义。
SAMPLE_TRANSCRIPT = """25-26学年度2学期
4
学分
高等数学 (B) (二)
专业必修
89
3
学分
统计方法与数据分析
限选
92
0
学分
Python 程序设计上机
专业必修
合格
1
学分
军事理论（下）
全校必修
IP
25-26学年度1学期
2
学分
中国美术简史
通选课
B+
2
学分
学术写作与表达
任选
W
1
学分
大学英语听说
全校必修
87
1
学分
军事理论（上）
全校必修
IP
总学分
14
"""

fails: list[str] = []


def check(cond, label, extra=""):
    print(f"  [{'OK ' if cond else '!! '}] {label} {extra}")
    if not cond:
        fails.append(label)


def raw(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.read()


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                              headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read().decode() or "{}")


print("== 1) 发出去的 HTML 是合法 UTF-8、标签完整 ==")
html_bytes = raw("/")
html = html_bytes.decode("utf-8")          # 不合法会直接抛
check("\ufffd" not in html, "HTML 里没有 U+FFFD")
for tag in ("</small>", "</p>", "</title>", 'aria-label="工作区">'):
    check(tag in html, f"标签完整：{tag}")
check('<link rel="stylesheet"' in html, "样式表链接还在（没被坏属性吞掉）")
check(html.count("<script") >= 2, "脚本标签都在")

print("\n== 2) 发出去的 app.js 是新版 ==")
js = raw("/static/js/app.js").decode("utf-8")
check("\ufffd" not in js, "app.js 没有 U+FFFD")
# 「问卷」这两个字本身还会出现在：解释为什么删掉它的注释、以及课程搜索的
# 占位提示（「例如：数据可视化、问卷、证明」）。那些都是正当的。
# 真正要保证的是**它不再是一个标签页/视图**——所以按用法查，不按词查。
check('"问卷"' not in js, "没有把「问卷」当标签名")
check('case "onboarding"' not in js, "没有 onboarding 视图分支")
check("[问卷]" not in js and "问卷</" not in js, "没有渲染问卷标题的地方")
check("coverageBoard" in js, "有字段清单（核对页分类）")
check('["dialogue", "对话"], ["confirm", "核对"]' in js, "画像页只有对话/核对两个标签")
check("字段清单没加载出来" in js, "覆盖率接口失败时会说出来，而不是静默消失")
check("没有算进绩点" in js, "字母等级没算进绩点这件事会告诉用户")

print("\n== 3) 我加的 CSS 真的发出去了 ==")
css = raw("/static/css/styles.css").decode("utf-8")
check("\ufffd" not in css, "styles.css 没有 U+FFFD")
check(".cov-grid" in css and ".cov-col-identity" in css, "字段清单的样式在")
check(".mem-derived" in css, "推导记忆的样式在")

print("\n== 4) 接口：覆盖度九大类 ==")
uid = req("POST", "/api/auth/login",
          {"nickname": f"字节验证{random.randint(1000, 9999)}"})["uid"]
cov = req("GET", f"/api/me/coverage?uid={uid}")
check(len(cov["groups"]) == 9, f"九大类都在（{len(cov['groups'])}）",
      "/".join(g["label"] for g in cov["groups"]))
check(cov["total"] > 0 and cov["filled"] == 0, f"初始 {cov['filled']}/{cov['total']}")

print("\n== 5) 用合成成绩单走完整流程 ==")
text = SAMPLE_TRANSCRIPT
p = req("POST", "/api/me/transcript/parse", {"uid": uid, "text": text})
check(len(p["courses"]) == 8, f"识别 8 门（{len(p['courses'])}）")
check(p["warnings"] == [], "零警告", str(p["warnings"]))
s = p["summary"]
# 通过 = 4(高数) + 3(统计) + 0(上机·合格) + 2(美术史·B+) + 1(英语) = 10
check(s["passed_credits"] == 10.0, f"通过学分 10（{s['passed_credits']}）")
# 只有百分制进 GPA 分母：4 + 3 + 0 + 1 = 8
check(s["gpa_credits"] == 8.0, f"计入绩点的学分 8（{s['gpa_credits']}）")
check(len(s["ungraded"]) == 1 and s["ungraded"][0]["grade"] == "B+",
      "字母等级没进绩点，但被单独列出来", str(s["ungraded"]))
check(len(s["in_progress"]) == 2, "两门 IP 记成在修", str([u["course"] for u in s["in_progress"]]))
check(len(p["preview"]) >= 3, f"给得出会记下什么（{len(p['preview'])} 条）")

w = req("POST", "/api/me/transcript", {"uid": uid, "text": text, "mode": "replace"})
check(w["written"] == 8, f"落库 8 门（{w['written']}）")
check(len(w["derived"]) >= 2, f"推导出 {len(w['derived'])} 条能力结论")
for d in w["derived"]:
    print(f"        {d['value'][:66]}")

print("\n== 6) 在修课程落库时 status=current ==")
courses = req("GET", f"/api/me/transcript?uid={uid}")["courses"]
ip = [c for c in courses if c["grade"] == "IP"]
check(len(ip) == 2 and all(c["status"] == "current" for c in ip),
      "IP 的 status 是 current", str([(c["course"], c["status"]) for c in ip]))
check(all(c["status"] == "completed" for c in courses if c["grade"] != "IP"),
      "其余是 completed")

print("\n== 7) 覆盖度把成绩单算进「已修课程」 ==")
cov2 = req("GET", f"/api/me/coverage?uid={uid}")
done = next(g for g in cov2["groups"] if g["label"] == "已修课程")
check(done["slots"][0]["filled"] is True, "已修课程变成已填", done["slots"][0]["value"])
check(cov2["filled"] > cov["filled"], "覆盖度上升")

print("\n" + ("全部通过" if not fails else f"失败 {len(fails)} 项：{fails}"))
sys.exit(1 if fails else 0)
