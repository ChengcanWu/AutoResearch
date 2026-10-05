# -*- coding: utf-8 -*-
"""把另一卷的抽取结果并进已有知识库（文科卷 + 理科卷 = 一个本部知识库）。

两卷共用同一份「北京大学在用本科专业目录（本部）」，公共基础课程章节也完全重复，
所以合并规则是：
  · catalog.json：两卷必须逐条一致（不一致就报冲突、以目标库为准并打印）；
  · sections.json / plans/：按名字取并集；公共课章节两卷都有，保留目标库那份；
  · 每个 plan 打上 `卷` 字段（文科卷 / 理科卷），互相重合的记 `卷 = 文科卷/理科卷`；
  · public_courses.json：课程与学分项取并集（同一门课只留一条）。
合并完再用 `extract_curriculum.py --refingerprint` 重建指纹/课程索引/前缀归属。

用法:
  python tools/curriculum/merge_kb.py --into knowledge/curriculum --add .work/kb_sci \
      --volume 理科卷 --into-volume 文科卷
"""
from __future__ import annotations

import argparse
import json
import os
import shutil


def load(kb: str) -> dict:
    out = {"kb": kb}
    for name in ("catalog.json", "sections.json", "public_courses.json"):
        p = os.path.join(kb, name)
        out[name] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
    plans = {}
    pdir = os.path.join(kb, "plans")
    for fn in sorted(os.listdir(pdir)):
        if fn.endswith(".json"):
            plans[fn] = json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
    out["plans"] = plans
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--into", required=True)
    ap.add_argument("--add", required=True)
    ap.add_argument("--volume", required=True, help="新增那卷的名字，如 理科卷")
    ap.add_argument("--into-volume", required=True, help="目标库那卷的名字，如 文科卷")
    a = ap.parse_args()

    dst, src = load(a.into), load(a.add)

    # ---- catalog ----
    def key(rec: dict) -> tuple:
        return (rec.get("院系"), rec.get("专业名称") or rec.get("专业"))
    def same(a: dict, b: dict) -> bool:
        """两卷的院系-专业目录表是同一张，唯一会变的是它落在哪一页。"""
        drop = {"来源页"}
        return ({k: v for k, v in a.items() if k not in drop}
                == {k: v for k, v in b.items() if k not in drop})

    dk = {key(r): r for r in dst["catalog.json"]}
    sk = {key(r): r for r in src["catalog.json"]}
    conflicts = [k for k in sk if k in dk and not same(sk[k], dk[k])]
    for k in sk:
        if k not in dk:
            dk[k] = sk[k]
        elif sk[k].get("来源页") != dk[k].get("来源页"):
            dk[k]["来源页_%s" % a.volume] = sk[k]["来源页"]
    merged_catalog = [dk[k] for k in sorted(dk, key=lambda x: (x[0] or "", x[1] or ""))]
    json.dump(merged_catalog, open(os.path.join(a.into, "catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ---- sections ----
    sec_dst = {(s["name"]): s for s in dst["sections.json"]}
    sec_src = {(s["name"]): s for s in src["sections.json"]}
    dropped = [n for n, s in sec_src.items() if s.get("pdf_start", 0) > s.get("pdf_end", 0)]
    sec_added = sec_both = 0
    for n, s in sec_src.items():
        if s.get("pdf_start", 0) > s.get("pdf_end", 0):
            continue                                  # 目录里重复出现的空条目
        if n in sec_dst:
            sec_dst[n]["卷"] = f"{a.into_volume}/{a.volume}"
            sec_both += 1
        else:
            s["卷"] = a.volume
            sec_dst[n] = s
            sec_added += 1
    for n, s in sec_dst.items():
        s.setdefault("卷", a.into_volume)
    merged_sections = sorted(sec_dst.values(), key=lambda s: s.get("pdf_start", 0))

    # ---- plans ----
    added, shared, dropped_plan = [], [], []
    for fn, plan in src["plans"].items():
        if plan.get("页码", {}).get("pdf", [0, 0])[0] > plan.get("页码", {}).get("pdf", [0, 1])[1]:
            dropped_plan.append(fn)
            continue                                  # 空壳（页范围倒挂）
        if fn in dst["plans"]:
            shared.append(fn)
            dst["plans"][fn]["卷"] = f"{a.into_volume}/{a.volume}"
        else:
            plan["卷"] = a.volume
            dst["plans"][fn] = plan
            added.append(fn)
    for fn, plan in dst["plans"].items():
        plan.setdefault("卷", a.into_volume)

    # ---- public_courses ----
    pub_dst = dict(dst["public_courses.json"] or {})
    pub_src = src["public_courses.json"] or {}
    new_courses = 0
    for code, node in pub_src.items():
        if code.startswith("_"):
            if code not in pub_dst:
                pub_dst[code] = node
            else:
                tgt = pub_dst[code]
                for k, v in node.items():
                    if k not in tgt:
                        tgt[k] = v
            continue
        if code in pub_dst:
            have = set(pub_dst[code].get("出现于", []))
            pub_dst[code]["出现于"] = sorted(have | set(node.get("出现于", [])))
            pub_dst[code]["出现于专业数"] = len(pub_dst[code]["出现于"])
        else:
            node["卷"] = a.volume
            pub_dst[code] = node
            new_courses += 1

    # ---- 落盘 ----
    vol_of_major: dict[str, set] = {}
    for plan in dst["plans"].values():
        vols = str(plan.get("卷", "")).split("/")
        vol_of_major.setdefault(plan.get("专业", ""), set()).update(vols)
    for r in merged_catalog:
        name = r.get("专业名称") or ""
        vols: set = set()
        for major, v in vol_of_major.items():
            if major == name or (name and major.startswith(name)):
                vols |= v
        r["卷"] = "/".join(sorted(vols - {""})) or ""
    json.dump(merged_catalog, open(os.path.join(a.into, "catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(merged_sections, open(os.path.join(a.into, "sections.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(pub_dst, open(os.path.join(a.into, "public_courses.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for fn, plan in dst["plans"].items():
        json.dump(plan, open(os.path.join(a.into, "plans", fn), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)

    print("catalog：%d 条（字段冲突 %d）" % (len(merged_catalog), len(conflicts)))
    if conflicts:
        print("  冲突：%s" % conflicts[:8])
    print("sections：%d 条（新增 %d，两卷共有 %d，丢弃空壳 %d）"
          % (len(merged_sections), sec_added, sec_both, len(dropped)))
    print("plans：%d 个（新增 %d，两卷共有 %d，丢弃空壳 %s）"
          % (len(dst["plans"]), len(added), len(shared), dropped_plan))
    print("public_courses：课程 %d 门、新增 %d 门"
          % (len([k for k in pub_dst if not k.startswith("_")]), new_courses))


if __name__ == "__main__":
    main()
