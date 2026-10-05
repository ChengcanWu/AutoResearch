# knowledge/curriculum · 院系-专业培养方案知识包（文科卷 + 理科卷）

从《北京大学本科培养方案（2026）》**文科卷 + 理科卷**抽出来的结构化知识：
**院系 → 专业 → 学分结构 → 课程表（含选修菜单）→ 课程结构指纹**，本部 26 个院系、150 条专业记录全覆盖。
给 AI 回答「我要修什么 / 这门课哪个院开的 / 我上的课像哪个专业 / 这个学期该出现哪些课 / 我是哪个院系哪个专业的」。

- 辅修与双专业单独一层：`knowledge/minor/`（《北京大学本科辅修双专业培养方案（2025）》）
- 方案与验证结论：`docs/DEPARTMENT_KNOWLEDGE.md`
- 抽取工具与口径：`tools/curriculum/`（`extract_curriculum.py` / `merge_kb.py` / `compact.py` /
  `distill.py` / `merge_intros.py` / `validate.py` / `review.py` / `card.py` / `check_split.py`）
- 数据来源：
  - 《北京大学本科培养方案（2026）文科卷》，756 页（`卷 = 文科卷`）
  - 《北京大学本科培养方案（2026）理科卷》，752 页（`卷 = 理科卷`）
  - 两卷共用同一份《北京大学在用本科专业目录（本部）》（150 条），所以 `catalog.json` 只有一份，
    哪条专业在哪一卷有培养方案由 `plans/*.json` 的 `卷` 字段说明

## 生成命令（按顺序）

```powershell
# 1) 每卷各自抽全量章节（约 10–15 分钟/卷）
python tools/curriculum/extract_curriculum.py --pdf "<文科卷.pdf>" --out .work/kb_lib
python tools/curriculum/extract_curriculum.py --pdf "<理科卷.pdf>" --out .work/kb_sci
# 2) 合并成一个知识包（专业目录、公共课、指纹都会合并）
python tools/curriculum/merge_kb.py --into .work/kb_lib --add .work/kb_sci --into-volume 文科卷 --volume 理科卷
# 3) 定位句：抽原文 → 分批交给 LLM 压成 ≤40 字 → 合并
python tools/curriculum/distill.py --kb .work/kb_sci --pdf "<理科卷.pdf>" --out .work/distill_sci --batches 5
python tools/curriculum/merge_intros.py --out knowledge/curriculum/intros.json `
    --base knowledge/curriculum/intros.json --dir .work/distill --dir .work/distill_sci
# 4) 生成专业卡（cards.json / CARDS.md）
python tools/curriculum/compact.py --kb knowledge/curriculum --out knowledge/curriculum
# 5) 抽检表 + 留一验证
python tools/curriculum/review.py --kb knowledge/curriculum --raw .work/distill/prose_raw.json `
    --raw .work/distill_sci/prose_raw.json --out docs/curriculum_intros_review.md
python tools/curriculum/validate.py knowledge/curriculum docs/curriculum_validation.md
# 改了指纹规则、不想重解析 PDF 时（几秒钟）：
python tools/curriculum/extract_curriculum.py --out knowledge/curriculum --refingerprint
# 摘公共课的回归检查（要先有一份没摘过的 plans，见 tools/curriculum/check_split.py 注释）
python tools/curriculum/check_split.py --orig .work/plans_orig --kb knowledge/curriculum
```

| 文件 | 内容 |
| --- | --- |
| `catalog.json` | 院系 × 专业骨架（专业代码 / 门类 / 专业类 / 学位 / 修业年限），覆盖本部全院系 |
| `cards.json` | **专业卡**：这条是给 AI 直接读的——门类/专业类/学位/学制 + 一句定位 + 代表性必修课 + 数学计算底子 + `检索别名` / `目录条目` |
| `sections.json` | 章节表：学部 → 院系 → 专业/项目，书内页码 + PDF 页码区间 + `卷` |
| `plans/<名>.json` | 单章节：学分结构、按模块归类的课程表（含选修菜单）、文字统计、来源页、`卷` |
| `fingerprints.json` | 各章节紧凑指纹（必修学分、数学/计算/语言/实践学分、课号前缀、学期分布） |
| `intros.json` | 定位句成品（≤40 字，LLM 蒸馏 + 人工抽检，见 `docs/curriculum_intros_review.md`） |
| `public_courses.json` | 公共基础课程（思政/体育/英语/信息科学/通识…）**两卷一致，只存一份** |
| `course_index.json` | 课号 → 哪些专业把它列为必修 |
| `prefix_ownership.json` | 课号前 4 位 → 谁在必修它 + 课程名样例 |

## 读数据前先知道的六条

1. **`类别` 字段要筛**：`专业 / 项目 / 公共课 / 说明 / 附录 / 院系`，只有 `专业`、`项目` 会进 `cards.json`；
   `院系` 是院系章节（一整院的方案），`说明` 是评定细则、学分要求这类文件。
2. **`卷` 字段要带上**：`文科卷 / 理科卷 / 文科卷/理科卷`。公共课章节两卷完全一样，标成后者。
3. **选修课是菜单**：一个专业可以列 48 门专业选修供挑 26 学分。指纹只统计必修课，
   选修菜单只能回答「能选什么」，不能回答「必须修什么」。
4. **公共基础课程不在专业里**：各专业的 `plans/*.json` 已经把 1.x 公共课模块摘掉，
   统一放在 `public_courses.json`（每个专业都写一遍同样的思政/体育/英语，没有信息增益）。
   要「某专业毕业要修的全部课」时，把 `plans/<名>.json` 和 `public_courses.json` 拼起来。
5. **学分有区间**：`43～49`、`2～8` 是原文写法，别取中点当事实。
6. **查的时候用 `tools/curriculum/lookup.py`，别自己 `==` 比名字**：同一个专业有章节名（`汉语言文学专业`）、
   专业目录名（`汉语言文学`）、口语（`汉语言文学`、`软件工程专业`）三种写法，卡片里都收在 `检索别名`（全库 499 个键）。
   一个名字对上多个专业时它会返回全部候选（`经济学` → 3 个、`信息与计算科学` → 8 个），
   这是设计好的「专业簇」，不要随便挑一个。`目录条目` 字段说明这一份培养方案覆盖了哪几个专业目录条目。

## 纪律

- 只抽原文；原文没写就留空（例：法学专业原文「授予学位类型：」后面就是空的）。
- 不抽描述性文字：专业简介、培养目标、培养要求、师资荣誉、联系方式、政策附注一律不进库；
  只有蒸馏成 ≤40 字的一句话（`intros.json`）才进，原文另存 `.work/distill*/prose_raw.json` 供抽检。
- 每条记录都能指回 PDF 页码（`页码.pdf` 与 `页码.书内`），回答时应当带上来源。
- 覆盖范围：本部 26 个院系（文理两卷）。**医学部、深圳研究生院、软件与微电子学院不在其中**——
  基础医学、临床医学、药学（本部药学院另有辅修）等要等医学卷/其他卷补进来后重跑合并。
