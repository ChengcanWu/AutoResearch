# -*- coding: utf-8 -*-
"""验证：只靠「课程结构」能不能认出这是哪个院系-专业。

两种口径：
  全量   该专业全部必修课号当成绩单（乐观上限）
  低年级 只留选课学期在大一/大二的必修课号（贴近「大二来问」的真实场景）

排序用 F1（既看命中多少，也看这个专业的必修结构有多小），避免「必修课少的专业」白捡分。
用法: python validate.py <kb目录> <报告.md>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_curriculum import professional_courses  # noqa: E402


def core_must(plan: dict, term_filter=None) -> set:
    out = set()
    for c in professional_courses(plan):
        if "必修" not in c.get("课程性质", ""):
            continue
        if term_filter and not term_filter(c.get("选课学期", "")):
            continue
        out.add(c["课号"])
    return out


def f1_rank(transcript: set, profiles: dict, common: set) -> list[tuple[str, float, int]]:
    rows = []
    for key, must in profiles.items():
        core = must - common
        if not core:
            continue
        hit = core & transcript
        if not hit:
            continue
        rec = len(hit) / len(core)
        pre = len(hit) / max(1, len(transcript & (must | common)))
        f1 = 0.0 if rec + pre == 0 else 2 * rec * pre / (rec + pre)
        rows.append((key, round(f1, 3), len(hit)))
    return sorted(rows, key=lambda x: (-x[1], -x[2]))


def main() -> None:
    kb, out = sys.argv[1], sys.argv[2]
    pdir = os.path.join(kb, "plans")
    plans = {}
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".json"):
            continue
        plan = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
        name = plan.get("专业") or fn[:-5]
        if plan.get("类别", "专业") not in ("专业", "项目"):
            continue                                # 附录 / 说明 不参评
        plans[name] = plan

    profiles_all = {k: core_must(p) for k, p in plans.items()}
    profiles_low = {k: core_must(p, lambda t: any(x in t for x in ("一", "二")))
                    for k, p in plans.items()}
    counts = {}
    for k, v in profiles_all.items():
        for code in v:
            counts[code] = counts.get(code, 0) + 1
    n = len(plans)
    common = {c for c, cnt in counts.items() if cnt / n >= 0.3}

    lines = ["# 课程结构认专业 · 留一验证", "",
             f"样本：{len(plans)} 个专业；公共必修课（出现在 ≥30% 专业的必修结构里）"
             f"共 {len(common)} 门，比对时先剔除。", ""]

    # 噪声口径：本专业低年级必修 + 从别的专业菜单里随机抓的 6 门课（模拟通识/选修/转过专业）
    import random
    rng = random.Random(20261005)
    pool = sorted({c["课号"] for p in plans.values() for c in p.get("课程_去重", [])
                   if "必修" not in c.get("课程性质", "")})
    noised = {}
    for key, must in profiles_low.items():
        if len(must) < 3:
            continue
        noised[key] = set(must) | set(rng.sample(pool, min(6, len(pool))))

    detail = []
    variants = (("全量", profiles_all, lambda k: profiles_all[k]),
                ("低年级", profiles_low, lambda k: profiles_low[k]),
                ("低年级+噪声", profiles_low, lambda k: noised.get(k, set())))
    for tag, profiles, pick in variants:
        t1 = t3 = ok = d1 = 0
        rows = []
        for key in sorted(profiles):
            tr = pick(key)
            if len(tr) < 3:
                continue
            ranked = f1_rank(tr, profiles, common)
            names = [r[0] for r in ranked]
            rank = names.index(key) + 1 if key in names else -1
            ok += 1
            t1 += rank == 1
            t3 += 0 < rank <= 3
            # 院系级：第一名只要和真身同一个院系就算对（经济学院几个专业前两年本来就同构）
            same_dept = bool(names) and (plans[names[0]].get("院系") == plans[key].get("院系"))
            d1 += same_dept
            rows.append((key, len(tr), rank, names[:3], same_dept))
        if ok:
            lines.append(f"## {tag}口径（{ok} 个专业参评）")
            lines.append(f"- 专业级 Top-1：{t1}/{ok} = {t1 / ok:.0%}")
            lines.append(f"- 专业级 Top-3：{t3}/{ok} = {t3 / ok:.0%}")
            lines.append(f"- 院系级 Top-1：{d1}/{ok} = {d1 / ok:.0%}")
            lines.append("")
            detail.append((tag, rows))

    for tag, rows in detail:
        lines.append(f"## 逐专业结果（{tag}）")
        lines.append("| 专业 | 成绩单课数 | 专业排名 | 院系对否 | 系统给的前三名 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for key, cnt, rank, top, same in rows:
            lines.append(f"| {key} | {cnt} | {rank} | {'✓' if same else '✗'} | {' / '.join(top)} |")
        lines.append("")

    pm = json.load(open(os.path.join(kb, "prefix_ownership.json"), encoding="utf-8"))
    lines.append("## 课号前 4 位 → 谁在必修它")
    lines.append("")
    lines.append("| 课号前缀 | 必修该前缀课程的专业数 | 课程名样例 |")
    lines.append("| --- | --- | --- |")
    for p, v in pm.items():
        lines.append(f"| {p} | {v['必修该前缀课程的专业数']} | {'、'.join(v['课程名样例'][:4])} |")

    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print("->", out)


if __name__ == "__main__":
    main()
