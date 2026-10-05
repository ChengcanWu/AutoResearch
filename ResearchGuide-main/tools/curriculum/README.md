# tools/curriculum · 培养方案 → 院系-专业知识库

把《北京大学本科培养方案》PDF（文科卷 + 理科卷）与《北京大学本科辅修双专业培养方案》PDF
抽成 AI 能直接查的结构化知识包：**院系 → 专业 → 专业卡 → 学分结构 → 课程表 → 课程结构指纹**，
外加一层**辅修 / 双专业**（`minor_extract.py`）。
不抽简介、培养目标、培养要求这类描述性文字（见 `docs/DEPARTMENT_KNOWLEDGE.md` 的「挤水分」口径）；
唯一的例外是蒸馏后的一句 ≤40 字定位（`distill.py`）。

## 跑法

```powershell
# 1) 每卷各自全量抽取（约 10–15 分钟/卷）
python tools/curriculum/extract_curriculum.py `
  --pdf "C:\Users\<你的用户名>\Desktop\北京大学本科培养方案（2026）文科卷.pdf" --out .work\kb_lib
python tools/curriculum/extract_curriculum.py `
  --pdf "C:\Users\<你的用户名>\Desktop\北京大学本科培养方案（2026）理科卷.pdf" --out .work\kb_sci
# 2) 合并成一个知识包（专业目录 / 公共课 / 章节 / 计划都合并）
python tools/curriculum/merge_kb.py --into .work\kb_lib --add .work\kb_sci `
  --into-volume 文科卷 --volume 理科卷

# 3) 只抽几个专业（调试用）
python tools/curriculum/extract_curriculum.py --pdf <pdf> --out .tmp\kb --only 经济学专业,社会学专业

# 4) 定位句：抽原文 → 分批次给 LLM 压成 ≤40 字 → 合并（--dir 可给多个卷的目录）
python tools/curriculum/distill.py --kb .work\kb_sci --pdf "<理科卷.pdf>" --out .work\distill_sci --batches 5
python tools/curriculum/merge_intros.py --out knowledge\curriculum\intros.json `
  --base knowledge\curriculum\intros.json --dir .work\distill --dir .work\distill_sci

# 5) 生成专业卡（cards.json + CARDS.md，这一层才是给 AI 读的）
python tools/curriculum/compact.py --kb knowledge/curriculum --out knowledge/curriculum

# 5b) 按「用户会怎么说」查（四层检索：主键 → 别名 → 包含 → 最像的 3 个名字）
python tools/curriculum/lookup.py --kb knowledge/curriculum --ask 软件工程专业
python tools/curriculum/lookup.py --kb knowledge/curriculum --ask 经济学      # 一个名字对上多个 → 专业簇
python tools/curriculum/lookup.py --kb knowledge/curriculum --minor --ask 法学辅修
python tools/curriculum/lookup.py --kb knowledge/curriculum --ask 统计学 --json   # 给接口/Agent 用

# 6) 辅修 / 双专业层
python tools/curriculum/minor_extract.py --pdf "<辅修双专业.pdf>" --out knowledge/minor
python tools/curriculum/minor_extract.py --out knowledge/minor --batches 4 --batch-dir .work\minor_distill
python tools/curriculum/merge_intros.py --out knowledge\minor\intros.json --dir .work\minor_distill
python tools/curriculum/minor_extract.py --out knowledge/minor --cards --intros knowledge\minor\intros.json

# 7) 抽检表 + 留一验证 + 摘公共课的回归
python tools/curriculum/review.py --kb knowledge/curriculum --raw .work\distill\prose_raw.json `
  --raw .work\distill_sci\prose_raw.json --out docs\curriculum_intros_review.md
python tools/curriculum/review.py --kb knowledge/minor --minor --out docs\curriculum_minor_review.md
python tools/curriculum/validate.py knowledge/curriculum docs/curriculum_validation.md
python tools/curriculum/check_split.py --orig .work\plans_orig --kb knowledge/curriculum

# 8) 改了指纹/标签规则、不想重解析 PDF：
python tools/curriculum/extract_curriculum.py --out knowledge/curriculum --refingerprint
```

依赖：`pdfplumber`（只要这一个；`pdfplumber` 能正确解析这份 PDF 的嵌入字体，PyMuPDF/fitz 会抽出乱码）。

## 产出

| 文件 | 内容 | 用途 |
| --- | --- | --- |
| `cards.json` | **专业卡**：门类/专业类/学位/学制 + 一句定位 + 代表性必修课 + 数学计算底子 + `检索别名` / `目录条目` | 给 AI 读的那一层 |
| `lookup.py` | 查表入口：主键 → 别名 → 包含 → 最像的 3 个名字；一个名字对上多个就返回「专业簇」 | AI/接口按用户说法查专业 |
| `catalog.json` | 院系 × 专业骨架：专业代码 / 门类 / 专业类 / 学位 / 修业年限（本部全院系） | 「细分到院系-专业」的主键表 |
| `sections.json` | 章节表：学部 → 院系 → 专业/项目，书内页码 + PDF 页码区间 + `卷` | 溯源、增量重跑 |
| `plans/<专业>.json` | 单个专业：学分结构、按模块归类的课程表（公共课已摘出） | 回答「这个专业要修什么」 |
| `public_courses.json` | 公共基础课程（思政/体育/英语/信息科学/通识）两卷一致，只存一份 | 拼回完整毕业要求 |
| `fingerprints.json` | 每专业紧凑指纹：必修学分、数学/计算/语言/实践学分、课号前缀分布、学期分布 | 匹配、比较、排序（毫秒级） |
| `intros.json` | 蒸馏定位句（人工抽检表见 `docs/curriculum_intros_review.md`） | 卡片里的「这个专业是干什么的」 |
| `course_index.json` | 课号 → 哪些专业把它列为必修 | 拿成绩单反查院系 |
| `prefix_ownership.json` | 课号前 4 位 → 谁在必修它 + 课程名样例 | 用课号认开课院系 |
| `knowledge/minor/*` | 辅修 / 双专业：学分量、核心课程、**替代课程** | 回答「主修修过了还算不算」 |

## 抽取契约（改代码时别破坏）

1. **只抽原文**：抽不到就留空，不补不猜。每条记录带来源页，能指回 PDF。
2. **必修优先**：指纹只统计「必修」课程。选修课是菜单（一个专业可以列 58 门选修供挑 22 学分），
   把菜单当要求会得出错误的结论。
3. **模块标题按页内纵向顺序推进**：表归到它上面最近的模块标题；跨页续表沿用上一页的模块。
   模块状态（`mod` / `alt`）必须跨页保留——续表的页面上没有标题，按页重置会把课程全丢进「课程」。
4. **学分结构是两列排版**，一行里可能出现两个模块（`2．专业必修课程：51 学分  2-2 专业核心课：10 学分`），
   所以用 `finditer` 而不是行首 `match`。
5. **页码**：书内页码从页眉/页脚的 `·N·` 取；`pdf页码 = 书内页码 + 偏移`，偏移取众数（各卷不同）。
6. **公共基础课程不进专业**：`1.x / 公共必修 / 体育 / 大学英语 / 通识` 之类的模块在 `write_derived`
   里被摘到 `public_courses.json`（每个专业都一样的 43～49 学分，存 100 遍没有信息增益）。
   判定要看两件事，不能只看标题：标题说公共课 **而且** 课号确实不是本系开的
   （`module_is_public`）。实跑踩过三个坑——项目类章节把自己的核心课也从 1 开始编号
   （古典语文学项目的「1-1 古希腊语拉丁语课程」）、`2-4 实习/实践/劳动教育课` 因「劳动教育」
   三个字被误判、历史学专业古典语文学项目把本系基础课表排在「1.2 通识教育课」标题下面。
   改完用 `check_split.py` 对账：摘走的每一门课都必须能在 `public_courses.json` 里按「出现于」找回。
7. **跨院系菜单用课号前缀自证归属**：培养方案里常有「需选修下表中人文学部与其他院系的专业必修课
   至少 4 学分」，排版上会插在本系课表前面（世界史专业就是），`own_prefixes()` 取覆盖 ≥60%
   课程的前缀作为「本系课」，卡上的代表性必修课只从本系课里出，不够 4 门才让跨院系课补位。
8. **院系归属按页码区间判**：专业挂在「书内页码在它之前、且最靠后的那个院系」下。
   目录的排版顺序不等于章节顺序（理科卷就不是），按顺序挂会把工学院的专业挂到信息科学技术学院。
9. **学部名和院系名可能连在一行印**（`工学部北京大学工学院`），必须剥掉，否则会当成一个「专业」。
10. **同一页可以有两个专业**：理科卷把「地质学 / 地球化学」「地球物理学 / 物理学（地球物理方向）」
    印在同一章里，目录给同一个页码。取「下一页」时必须找页码**严格更大**的条目，
    否则会算出 `start>end` 的空区间把整章丢掉；两份计划内容相同，靠 `合章` 字段说明。
11. **合并单元格表格：表头行和数据行的「空法」不一样**。数据行里被合并的格子是 `None`，
    表头行里是一串 `''`，表头还常常多一个行首空格子——只有把 `None` 和 `''` 都丢掉，
    表头与数据行才落到同一个列序上；否则课程名会取到学分那一列（辅修卷尤其明显）。
    行比表头短时按「实践总学时 / 选课学期」补占位。
12. **别拿「替代」两个字当替代表开关**：正文里写「主修修过同名课，须从选修里挑别的替代」，
    紧随其后的必修表会被整张搬进 `替代课程`（信科的双专业就这么丢过必修表）。
    只有 `说明 / 附：/ 注：/ 可替代课程列表` 开头的行才引出替代表。
13. **模块标题可能没有编号**：辅修卷写成「专业必修课：31学分」，`MODULE_RE` 抓不到，
    得用 `PLAIN_CREDIT_HEAD_RE` 兜住（名字里含「课/组」才算，避免把「要求的总学分：31学分」吃掉）。
14. **卡片的名字必须用章节名，不能只用专业目录名**。目录写「汉语言文学」、章节写「汉语言文学专业」，
    照目录出卡会让 150 张卡片的名字和 `plans/`、`intros.json` 的键全部对不上，查表只能靠模糊匹配。
    现在卡里 `专业` = 章节名，目录写法放 `目录专业名`，两种写法 + 去方向括号 + 去「专业」二字
    一起进 `检索别名`（199 张卡 499 个检索键）。
15. **一份培养方案覆盖多个专业目录条目时只出一张卡**（物理学院 p112 的物理学/大气物理/天体物理，
    化学与分子工程学院 p168 的化学（材料化学方向）070301 与材料化学 080403）。
    按目录条目各出一张就是把同一份内容存 N 遍，AI 还会重复读到；被覆盖的条目收进 `目录条目`。
16. **检索要保留歧义**：`lookup.py` 查到一个名字对上多个专业时返回**全部候选**（专业簇），
    不要随便挑一个——「信息与计算科学」对 8 个方向、「理论与应用力学」对 9 个。全库 66 个这种入口。
