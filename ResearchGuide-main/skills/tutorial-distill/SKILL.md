---
name: tutorial-distill
description: 输入一个策展学科方向，检索多份可公开核对的权威教程/大纲/公开教材，蒸馏成流程树：先共用主干，仅当来源把后面写成并行课或选修轨时才分叉。每个节点必须带来源里的「学什么 / 做什么 / 打开哪一页」。来源不够就标 insufficient，不编步骤、不编链接、不编论文篇名。
---

你在为本科一、二年级做「点开这一步该学什么、对照哪一页去做什么」。输入是一个方向。输出是一棵流程树，不是口味测试，也不是再画一棵学科分类树。

## 输入

```text
id          方向节点 id（如 520.30）
name        树上的显示名
gb_name     国标或完整学科名
query       课程检索词
blurb       一句对象/方法（只作消歧，不作证据）
level       1 | 2 | 3
parent      父节点名（三级时用来避免写成二级的教程）
```

## 1. 检索（至少 4 次，中英都要）

每次换一种问法，不要只搜「X 教程」：

1. `{gb_name} undergraduate syllabus` 或 `{name} MIT OCW` / `Stanford` / `Berkeley`
2. `{name} open textbook table of contents` 或 `{name} OpenStax` / `Open Textbook Library`
3. `{gb_name} 本科 教学大纲` 或 `{name} 公开课 大纲`
4. 该方向的学会课程建议（如 `ACM CS2023`、`ASA curriculum`、`APA undergraduate`），没有就改搜 `{name} lecture notes site:.edu`

医学只搜基础医学（解剖、生理、生化、免疫、病理、药理、微生物、遗传）。不搜临床诊疗、处方、操作规程。

## 2. 哪些来源能用

打开前先看域名和页面类型。**至少采用 2 个互相独立的来源**（不同学校或不同出版社）。只采用你真正 fetch 到正文的页。

能用：

- 大学公开课 / 教学大纲（MIT OCW、Stanford、Berkeley、Open Yale、国内高校公开的培养方案或大纲 PDF）
- 公开教材目录与章节（OpenStax、Open Textbook Library、作者官网免费全书如 MML）
- 学会或专业组织的本科课程建议（ACM、ASA 等）
- NCBI Bookshelf、大学实验室公开讲义（基础医学）

不能单独当权威（可作补充，不能当某一步的唯一依据）：

- 知乎、CSDN、个人博客、培训机构落地页、没有作者单位的「roadmap」图

直接丢掉：

- 打不开、只有标题没有章节顺序的页面
- 付费墙后你没读到的内容
- 临床指南当基础医学教程

打开的每一页都写进 `sources`：原标题、URL、`kind`、`used_for`（哪几个节点、哪一段顺序）。后面节点只能引用这里出现过的 URL。

## 3. 蒸馏成树（不要先画树再找材料）

对每一份采用的来源，抽出**有顺序的主题列表**（目录、week 1–N、syllabus schedule），以及每段对应的**作业形态**（Reading / Exercise / Lab / Problem Set / Project / 复习题 / 标本指认）。

然后：

1. **主干 `trunk`**：至少两份来源都出现、或一份写成先修/核心、另一份不反对的主题，按来源里的先后排成一条线。通常 2–5 个节点。
2. **分叉 `forks`（可空）**：只有来源自己把后面写成并行课、并行知识单元、或明确的选修轨时才许分叉。必须在 `why` 里引用课表/学会原文，并给出 `source_urls`。学生选 `pick` 条（通常 1）做完即可。
3. **汇合 `join`（可空）**：两条轨之后来源又回到同一类收束（同一门课的 lab 记录、同一份短评）时才写。没有共同收束就不要硬汇。
4. **不要分叉的情况**（写进 `conflicts`，取更靠前、更保守的一条）：
   - 来源顺序打架（先贝叶斯还是先频率派）
   - 同一关的两种交卷方式（MIT 短评 或 教材习题）——写在该节点 `task.alternatives`，不要长成树枝
   - 「你对理论还是应用更感兴趣」这种口味题
5. 一个节点只解决一个卡点。卡点必须能在来源里找到对应。
6. 终点停在本科生进得去：能读、能复现、能交卷。不承诺新结果、不承诺临床能力。

禁止：

- 编造没打开过的论文篇名、DOI、课号
- 把来源没有的学校、教材、数字写进去
- 用 blurb 或自己的常识补一个节点或一条分叉
- 过关标准写成「理解了」「掌握了」「熟悉」

打开后仍然凑不够 2 个独立来源：`status` 设为 `insufficient`，`nodes` / `trunk` 可空，`missing` 写还缺什么检索。不要用自己的话把树凑满。

样例（有分叉）：`knowledge/tutorials/520.20.json`（人工智能）、`520.40.json`（计算机软件）。多数方向没有分叉，树退化成一条主干即可。

## 4. 每个节点必须能直接写到产品页

用户点开一个节点，要能立刻看到三件事。这三件事都必须来自你打开过的页，不能只留一句口号。

| 字段 | 产品上干什么 | 必须写清 |
| --- | --- | --- |
| `name` | 节点标题 | 短，能画在流程图上 |
| `why` | 为什么现在做这一步 | 指回来源把这一块放在这里的理由 |
| `learn` | 「该学啥」 | 来源里的术语/主题，2–6 条，不发明 |
| `task` | 「该做什么」 | 对照哪一讲/哪一章、交什么；`kind` 只能用下面枚举 |
| `resources` | 点开就能读/做的页 | 每条有 `url`（必须已在 `sources`）、`title`、`use`（读这一讲 / 做这个 lab / 看这章习题） |

`task.kind` 只能是：

- `reading`：读指定讲义/章节并留下可核对的笔记或标注
- `exercise`：教材或课内习题
- `problem_set`：课程 Problem Set / 作业
- `lab`：实验、Studio、上机、标本/模型指认
- `project`：课程 Project（扫描器、SQL project 等）
- `writeup`：短评、实验记录、设计草案

同一关有两种来源认可的交卷方式时，用 `task.alternatives`（每项也是 `kind` + `prompt` + `from`），不要为此加分叉。

`resources` 尽量落到具体讲次、章节、作业页，不要只挂课程首页。首页可以留在 `sources` 里说明顺序。

## 5. 输出

只写一个 JSON 文件：`knowledge/tutorials/{id}.json`  
三级 id：`520.20.nlp` → `520.20.nlp.json`。

```json
{
  "id": "520.40",
  "name": "计算机软件",
  "format": "tutorial-tree-v2",
  "status": "ok",
  "goal": "一句话终点，必须能从来源的课程目标改写，不能夸大",
  "sources": [
    {
      "title": "页面上的原标题",
      "url": "https://...",
      "kind": "ocw|syllabus|open_textbook|society|lecture_notes|other",
      "used_for": "主干前两步的顺序；或某条分叉的课历"
    }
  ],
  "trunk": ["tools", "adt"],
  "forks": [
    {
      "id": "after-adt",
      "after": "adt",
      "pick": 1,
      "why": "必须引用来源：谁把后面写成并行课",
      "source_urls": ["https://..."],
      "branches": [
        { "id": "os", "name": "操作系统", "nodes": ["os-process", "os-sync"] },
        { "id": "compiler", "name": "编译前端", "nodes": ["parser"] },
        { "id": "db", "name": "数据库", "nodes": ["sql"] }
      ]
    }
  ],
  "join": null,
  "nodes": {
    "tools": {
      "name": "工具、静态检查与测试",
      "why": "来源为什么把这一块放最前",
      "learn": ["静态检查", "test-first", "Git clone/commit/push"],
      "task": {
        "kind": "lab",
        "prompt": "能交出来的东西，写清对照哪一页",
        "from": "6.031 Getting Started + Reading 1 + Reading 3"
      },
      "resources": [
        {
          "url": "https://...",
          "title": "页面原标题",
          "use": "先照这页搭环境"
        }
      ]
    }
  },
  "conflicts": [],
  "missing": "",
  "checked_at": "YYYY-MM-DD"
}
```

`status=ok` 时：`format` 必须是 `tutorial-tree-v2`；`trunk` 至少 2 个节点；每个被引用的 id 都在 `nodes` 里；`nodes` 里不能有没被 trunk/fork/join 引用的孤儿；每个节点的 `resources.url` 都必须出现在 `sources`。  
没有分叉时 `forks` 为 `[]`，`join` 为 `null`，树就是一条主干。  
`checked_at` 用你检索当天的日期。

写完后在仓库根对这一份跑：

```text
python skills/tutorial-distill/validate.py
python skills/tutorial-distill/preview.py knowledge/tutorials/{id}.json
```

`preview.py` 会画出 mermaid 流程图，并列出每个节点的学什么 / 做什么 / 链接。你自己先看一遍：分叉理由是否写在来源里，链接是否都是你打开过的。

不要改 `web/js/directions.js`。蒸馏结果只进 `knowledge/tutorials/`。前端接入是另一步。
