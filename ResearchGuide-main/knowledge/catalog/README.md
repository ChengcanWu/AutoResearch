# 北大公开课快照

当前学期、全院系一份。来源是教务公开检索，不登录。

| 文件 | 内容 |
| --- | --- |
| `meta.json` | 学期、爬取时间、条数 |
| `courses.json` | 开课记录（课名、老师、院系、学分、时间） |
| `teachers.json` | 老师：本学期教了哪些课；能对上公开学者档案时才有简介 |

生成：

```text
uv run --locked --project skills/pku-course python server/catalog_build.py
```

中断后重跑会接着上次的页往下翻。简介来自 OpenAlex，且只要最后任职含北京大学的记录；对不上就空着，不编。
