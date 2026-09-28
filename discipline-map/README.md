# 学科瞭望（产品）

面向**本科一、二年级**学生的学科分类与科研入门网站。

分类依据：GB/T 13745-2009《学科分类与代码》（门类 A–E；一、二级学科）。

> **发给同学部署时，请先看上一级的 [`../README.md`](../README.md)**（安装依赖 + 启动步骤写在那里）。

可对接同目录旁的 [`pku-course-skill-main`](../pku-course-skill-main)：在一级 / 二级学科页搜索北大公开开课。

## 目录

```
product/discipline-map/
  index.html
  server.py              ← 启动入口（静态页 + /api/courses）
  build_data.py          ← 从国标文本生成 disciplines.json
  css/styles.css
  js/app.js
  data/
    disciplines.json
    gbt13745_source.txt
```

## 快速启动（摘要）

**运行前准备：** Python ≥ 3.11、uv ≥ 0.10、浏览器；搜课需要网络。安装细节见 [`../README.md`](../README.md)。

```powershell
cd product\discipline-map
python server.py
```

浏览器打开：http://127.0.0.1:8765/

- 浏览一级学科 → 点二级学科卡片看介绍  
- 在详情页绿色「搜北大相关课程」里搜索公开开课  

端口占用时：

```powershell
$env:DISCIPLINE_MAP_PORT=8766
python server.py
```

## 更新学科数据（维护者）

```powershell
python build_data.py
```

一级学科导读在 `build_data.py` 的 `LEVEL1_GUIDE`；二级名称与说明来自 `data/gbt13745_source.txt`。

## 产品目标（当前版本）

1. 按国标浏览 **5 个门类、62 个一级、约 700 个二级学科**。  
2. 每个一级 / 二级提供入门介绍；一级下列出全部二级并可点入。  
3. 对接北大教务公开查询，按学科关键词搜相关课程。  
4. 支持门类筛选与关键词搜索（含二级学科名 / 代码）。

## 说明

- 开课结果 **不等于** 专业培养方案，也 **不能** 代替正式选课系统。  
- 遇教务验证码 / 限流时，课程 API 会报错并停止，不会绕过限制。
