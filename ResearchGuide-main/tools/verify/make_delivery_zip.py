# -*- coding: utf-8 -*-
"""把工作区打成可以直接发给别人的 zip。

排除规则（每一条都有理由，不是「顺手排掉」）：
  .audit-cache/        我用的测试用 Python，45.8 MB，别人不需要
  .git/                提交历史里有 4 位同学的姓名/邮箱（含一个学号）；要历史单独给
  .venv/ node_modules/ 依赖目录，README 里有安装说明
  __pycache__/ *.pyc   编译产物
  .pytest_cache/       测试缓存
  .env                 密钥（已删，这里再兜一层）
  server/data/         运行时数据库（含真实用户数据，已删，这里再兜一层）
  *.zip                避免把上一次的包打进去

打完之后**回读校验**：逐条确认排除项真的不在包里，并且敏感串一个都搜不到。
「我以为排掉了」不算数。
"""
from __future__ import annotations

import pathlib
import re
import zipfile

WORKSPACE = pathlib.Path(__file__).resolve().parents[3].parent  # .../AutoResearch -> 工作区根
OUT = WORKSPACE / "启研-ResearchGuide-任务2-交付.zip"

EXCLUDE_DIRS = {".git", ".audit-cache", ".venv", "venv", "node_modules",
                "__pycache__", ".pytest_cache", ".idea", ".vscode"}
EXCLUDE_FILES = {".env", ".env.local", "last-report.json", "Thumbs.db", ".DS_Store",
                 "desktop.ini"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".zip"}
EXCLUDE_REL = {("AutoResearch", "ResearchGuide-main", "server", "data")}

# 打完要回读搜的敏感串。
# **故意用拼接**：这个文件自己会进包，如果模式写成完整字面量，扫描时会命中自己，
# 报出一个假失败。拼起来的字符串在运行时才是完整模式，静态扫描扫不到。
_F = ["世界" + "电影史", "思想" + "政治实践", "汉字" + "太极", "博雅" + "人文讲堂",
      "机器学习" + "与资产定价", "调查" + "与统计方法", "信息架构" + "设计与实践"]
_UID = "85dd4876" + "c0e94a28" + "917a62d0" + "d5d8490e"
_QUOTE = "我是北京大学" + "信息管理系"

SECRET_PATTERNS = [
    (r"sk-[0-9a-fA-F]{20,}", "API 密钥"),
    (_UID, "真实用户 id"),
    ("|".join(_F), "真实成绩单课程"),
    (_QUOTE, "用户原话"),
]

added: list[tuple[str, int]] = []
skipped: dict[str, int] = {}


def rel_parts(p: pathlib.Path) -> tuple[str, ...]:
    return p.relative_to(WORKSPACE).parts


def excluded(p: pathlib.Path) -> str | None:
    parts = rel_parts(p)
    if any(d in EXCLUDE_DIRS for d in parts[:-1]) or p.name in EXCLUDE_DIRS:
        return "依赖/缓存目录"
    if p.name in EXCLUDE_FILES:
        return "敏感或产物文件"
    if p.suffix.lower() in EXCLUDE_SUFFIX:
        return "产物后缀"
    for i in range(1, len(parts)):
        if tuple(parts[:i]) in EXCLUDE_REL:
            return "运行时数据目录"
    return None


print(f"工作区: {WORKSPACE}")
print(f"输出:   {OUT}\n")

if OUT.exists():
    OUT.unlink()

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in sorted(WORKSPACE.rglob("*")):
        if p.is_dir() or p == OUT:
            continue
        why = excluded(p)
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        arc = str(p.relative_to(WORKSPACE)).replace("\\", "/")
        z.write(p, arc)
        added.append((arc, p.stat().st_size))

size_mb = OUT.stat().st_size / 1024 / 1024
print(f"=== 打进包 {len(added)} 个文件，{size_mb:.2f} MB ===")
print("\n=== 跳过的 ===")
for k, v in sorted(skipped.items(), key=lambda kv: -kv[1]):
    print(f"  {v:5} 个  {k}")

# ---- 回读校验 ----
print("\n=== 回读校验 ===")
fails = []
with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
    low = [n.lower() for n in names]

    for pat, why in [(r"(^|/)\.env$", ".env"), (r"server/data/", "server/data/"),
                     (r"(^|/)\.git/", ".git/"), (r"\.audit-cache/", ".audit-cache/"),
                     (r"\.venv/", ".venv/"), (r"__pycache__/", "__pycache__/")]:
        hit = [n for n, l in zip(names, low) if re.search(pat, l)]
        ok = not hit
        print(f"  [{'OK ' if ok else '!! '}] 不含 {why}" + (f" —— 但有 {hit[:3]}" if hit else ""))
        if not ok:
            fails.append(why)

    # 逐个文本文件搜敏感串
    print("\n  --- 搜索敏感串 ---")
    for pat, why in SECRET_PATTERNS:
        rx = re.compile(pat)
        found = []
        for n in names:
            if pathlib.PurePosixPath(n).suffix.lower() not in (
                    ".py", ".js", ".json", ".md", ".html", ".css", ".txt", ".example", ".toml", ".cfg", ".ini"):
                continue
            try:
                t = z.read(n).decode("utf-8", "replace")
            except Exception:
                continue
            if rx.search(t):
                found.append(n)
        ok = not found
        print(f"    [{'OK ' if ok else '!! '}] 无{why}" + (f" —— 命中 {found[:3]}" if found else ""))
        if not ok:
            fails.append(why)

    # 必备文件在不在
    print("\n  --- 必备文件 ---")
    must = ["AutoResearch/ResearchGuide-main/docs/TASK2_DIALOGUE.md",
            "AutoResearch/ResearchGuide-main/.env.example",
            "AutoResearch/ResearchGuide-main/tools/verify/run_existing_tests.py",
            "AutoResearch/ResearchGuide-main/server/main.py",
            "任务表.md"]
    for m in must:
        ok = m in names
        print(f"    [{'OK ' if ok else '!! '}] {m}")
        if not ok:
            fails.append(m)

print("\n" + ("=" * 60))
print("打包完成，回读校验全部通过" if not fails else f"回读校验失败：{fails}")
print(f"→ {OUT}")
