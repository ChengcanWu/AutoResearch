# 子 Agent 任务（tutorial-tree-v2）

工作目录：本仓库 `ResearchGuide-main/`（即本文件上两级）。

## 必读

1. `skills/tutorial-distill/SKILL.md`（全文照做）
2. 样例：`knowledge/tutorials/520.20.json`、`knowledge/tutorials/520.40.json`
3. 若已有 `knowledge/tutorials/{id}.json`（旧 6 步），可复用你核得开的来源，但必须整份重写成 `format: tutorial-tree-v2`，并再检索补强。不要只改字段名。

## 只准改

- 只写 `knowledge/tutorials/{你的 id}.json`
- 不要改 `web/js/directions.js`、`SKILL.md`、`validate.py`、别人的 JSON、README（父代理会登记）

## 硬规则

- 至少 4 次检索，中英都要；只采用你真正打开过正文的页。
- 至少 2 个互相独立的来源（不同学校或出版社）。不够就 `status: insufficient`，不要编满一棵树。
- 主干 ≥ 2 节点。分叉仅当来源把后面写成并行课/选修轨；顺序打架写 `conflicts`，取更靠前的。同一关两种交卷方式用 `task.alternatives`。
- 每个节点必须有 `learn`、`task`（kind + prompt + from）、`resources`（url + title + use）。url 必须已在 `sources`。
- `task.kind` 只能是 reading / exercise / problem_set / lab / project / writeup。禁止「理解了/掌握了/熟悉」。
- 不编论文篇名、DOI、没打开过的课号。
- 医学只做基础科学：解剖/生理/生化/免疫/病理/药理/微生物/遗传。不写诊断、处方、操作规程、临床指南。
- 临床与咨询心理：停在本科评估概念与可观察行为，不写治疗手册或处方。
- 终点：能读、能复现、能交卷。不承诺新结果。

## 写完自检

在仓库根执行：

```text
python skills/tutorial-distill/validate.py
python skills/tutorial-distill/preview.py knowledge/tutorials/{id}.json
```

`validate.py` 应对你的文件报 OK。`preview.py` 能画出 mermaid。

## 回复父代理

- 打开过的 URL 列表
- `status`、节点 id 列表、有无分叉
- `validate.py` 该文件是否 OK
- 一句话说明分叉依据或为什么是一条主干
