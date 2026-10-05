# -*- coding: utf-8 -*-
"""证明新加的那几条守卫**真的能失败**。

不能失败的测试等于没有测试，还会让人以为有保护。这里把每个修复
当场回滚一次，断言对应的守卫确实变红，然后还原。

（这个脚本本身不改仓库状态：改完一定还原，异常路径也走 finally。）
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]   # tools/verify -> 仓库根
WEB = ROOT / "web"
TESTS = ROOT / "server" / "tests"
APPJS = WEB / "js" / "app.js"
CSS = WEB / "css" / "styles.css"

fails = 0


def check(ok, label, extra=""):
    global fails
    print(f"  [{'OK ' if ok else '!! '}] {label} {extra}")
    if not ok:
        fails += 1


def run_test(name: str) -> int:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        f"server/tests/test_web_assets.py::{name}"],
                       cwd=str(TESTS.parent.parent), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode


def with_edit(path: pathlib.Path, old: str, new: str, label: str, test: str):
    """在原文件上做一次替换，跑测试，然后还原。"""
    orig = path.read_text(encoding="utf-8")
    if old not in orig:
        check(False, f"{label}：找不到要替换的原文，守卫可能已经失效")
        return
    path.write_text(orig.replace(old, new, 1), encoding="utf-8", newline="")
    try:
        rc = run_test(test)
    finally:
        path.write_text(orig, encoding="utf-8", newline="")
    check(rc != 0, f"{label} → 守卫变红", f"(returncode={rc})")


print("=== 0) 先确认当前是全绿的 ===")
check(run_test("test_completed_task_does_not_render_two_headers") == 0,
      "当前 done 分支的守卫通过")

print("\n=== 1) 回滚「done 分支先清空面板」 ===")
with_edit(APPJS,
          '    p.innerHTML = "";\n    taskPanelDone(p, task, opts);',
          '    taskPanelDone(p, task, opts);',
          "去掉 p.innerHTML = ''", "test_completed_task_does_not_render_two_headers")

print("\n=== 2) 回滚「--wash 改成 --sunken」 ===")
with_edit(CSS, "background: var(--sunken); border-radius: 6px;",
          "background: var(--wash); border-radius: 6px;",
          "写回未定义的 --wash", "test_css_variables_are_all_defined")

print("\n=== 3) 回滚「删掉重复的 .finished-note」 ===")
with_edit(CSS, "/* `.finished-note` 的样式统一写在文件末尾那一处。",
          ".finished-note { margin-top: var(--gap-4); }\n/* `.finished-note` 的样式统一写在文件末尾那一处。",
          "加回第二条 .finished-note", "test_no_class_has_two_disagreeing_rule_blocks")

print("\n=== 4) 回滚「删掉死钩子 .typing」 ===")
with_edit(CSS, "@keyframes blink { 50% { opacity: 0.2; } }",
          "@keyframes blink { 50% { opacity: 0.2; } }\n.typing { align-self: flex-start; }",
          "加回 .typing", "test_dead_css_hooks_stay_deleted")

print("\n=== 5) 回滚版本戳（把 css 的 ?v= 改成往后错一位） ===")
HTML = WEB / "index.html"
_html = HTML.read_text(encoding="utf-8")
_m = re.search(r'\?v=(w\d+)', _html)
if not _m:
    check(False, "找不到缓存参数")
else:
    # 不写死版本号：下次升版时这个脚本不该跟着烂掉
    cur = _m.group(1)
    wrong = "w0" if cur != "w0" else "w99"
    with_edit(HTML, f"?v={cur}", f"?v={wrong}",
              f"{cur} → {wrong}", "test_build_stamp_matches_every_cache_buster")

print("\n=== 6) 回滚「三个区的顺序」 ===")
CHATJS = WEB / "js" / "chat.js"
with_edit(CHATJS, "chat.append(scroll, actions, inputZone);",
          "chat.append(scroll, inputZone, actions);",
          "把输入区换到行动区前面", "test_chat_page_has_three_named_zones_in_order")

print("\n=== 7) 回滚「两列高度一致」 ===")
with_edit(CSS, "  max-height: clamp(520px, calc(100vh - 250px), 880px);\n  overflow-y: auto;",
          "  max-height: 400px;\n  overflow-y: auto;",
          "侧栏改用别的高度算法", "test_chat_panel_height_matches_side_panel_height")

print("\n=== 8) 回滚「新类名都有规则」（把一个类名的规则改名） ===")
# 要挑**只出现一次**的类名。第一版挑的是 .chat-next，但它在样式表里
# 还有两条规则（> :last-child 和窄屏那条），改名一条还剩两条，
# 守卫当然不会红——那是回滚不彻底，不是守卫失效。
with_edit(CSS, ".ws-bar-main {",
          ".ws-bar-main-renamed {",
          "把 .ws-bar-main 的规则改名", "test_new_class_names_all_have_rules")

print("\n" + ("全部通过：每条守卫都确实能失败" if not fails else f"失败 {fails} 项"))
raise SystemExit(1 if fails else 0)
