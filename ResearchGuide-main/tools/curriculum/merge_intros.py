# -*- coding: utf-8 -*-
"""合并蒸馏结果（out_*.json）→ intros.json，并对着 batch_*.json 查有没有漏。

用法:
  python merge_intros.py --out knowledge/curriculum/intros.json \
      --base knowledge/curriculum/intros.json --dir .work/distill_sci
  python merge_intros.py --out knowledge/minor/intros.json --dir .work/minor_distill

--base 是原有的定位句（不在 --dir 里的专业沿用旧值），没有就传空。
"""
from __future__ import annotations

import argparse
import glob
import json
import os


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", default="")
    ap.add_argument("--dir", action="append", default=[], help="装着 out_*.json / batch_*.json 的目录，可多次给")
    ap.add_argument("--drop", default="", help="要删掉的旧 key（逗号分隔）：改名/拆重名后清理残留")
    a = ap.parse_args()

    merged: dict[str, str] = {}
    if a.base and os.path.exists(a.base):
        merged.update(json.load(open(a.base, encoding="utf-8")))
    before = len(merged)

    conflict: list[str] = []
    for d in a.dir:
        for fn in sorted(glob.glob(os.path.join(d, "out_*.json"))):
            part = json.load(open(fn, encoding="utf-8"))
            for k, v in part.items():
                if k in merged and merged[k] != v:
                    conflict.append(k)
                merged[k] = v
            print("  + %-28s %d 条" % (os.path.basename(fn), len(part)))

    want: set[str] = set()
    for d in a.dir:
        for fn in sorted(glob.glob(os.path.join(d, "batch_*.json"))):
            want |= set(json.load(open(fn, encoding="utf-8")))
    dropped = [k for k in (x.strip() for x in a.drop.split(",")) if k and k in merged]
    for k in dropped:
        merged.pop(k)
    if dropped:
        print(f"  删掉改名/失效的旧 key {len(dropped)} 个：{dropped}")
    want -= set(dropped)
    miss = sorted(want - set(merged))
    empty = sorted(k for k in want if not merged.get(k))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(merged, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"合并 {before} + 新蒸馏 → {len(merged)} 条 → {a.out}")
    if conflict:
        print(f"[警告] {len(conflict)} 条同名覆盖（旧值被新值替换）：{conflict[:8]}")
    if miss:
        print(f"[警告] {len(miss)} 条没蒸馏到：{miss[:12]}")
    if empty:
        print(f"[提示] {len(empty)} 条定位句为空（原文太稀薄）：{empty[:12]}")
    if not miss and not conflict:
        print("[通过] 蒸馏结果完整、无冲突")


if __name__ == "__main__":
    main()
