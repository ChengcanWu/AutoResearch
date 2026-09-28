# product · 学科瞭望（发给同学可直接跑）

面向本科 **1–2 年级** 的学科分类与科研入门网页。

- 依据：GB/T 13745-2009《学科分类与代码》
- 功能：按门类 / 一、二级学科浏览介绍；可搜索北大教务**公开**开课信息
- 代码位置：`discipline-map/`（网页）+ `pku-course-skill-main/`（搜课，需与前者同级）

打包发给同学时，请保证解压后大致是这样：

```text
product/
  README.md                 ← 本文件（先看这里）
  discipline-map/           ← 网页与启动脚本
  pku-course-skill-main/    ← 北大公开课检索（不要删）
```

---

## 一、运行前需要安装什么

| 依赖 | 是否必须 | 说明 |
| --- | --- | --- |
| **Python 3.11 或更高** | 必须 | 用来跑 `server.py`。在终端执行 `python --version` 检查。 |
| **uv**（0.10 或更高） | 必须（要搜课） | 自动管理搜课工具的依赖，**不用**自己 `pip install`。 |
| 浏览器 | 必须 | Chrome / Edge / Firefox 均可。 |
| 网络 | 搜课时必须 | 首次启动会拉依赖；搜课会访问北大教务公开接口。 |

### 1. 安装 Python

- Windows：从 [python.org](https://www.python.org/downloads/) 下载安装包  
  - 安装时勾选 **Add python.exe to PATH**
- 安装后新开一个终端，确认：

```powershell
python --version
```

应显示类似 `Python 3.11.x` 或 `3.12.x` / `3.13.x`。若提示找不到命令，把 Python 重新装一遍并勾选 PATH，或使用「开始菜单」里的 Python 终端。

### 2. 安装 uv

任选一种方式（Windows PowerShell 推荐第一种）：

```powershell
# 官方安装脚本
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

或用 pip（若已有 Python）：

```powershell
pip install uv
```

装好后**新开终端**，确认：

```powershell
uv --version
```

应显示 `uv 0.10.x` 或更高（例如 `0.12.x`）。

> 说明：`beautifulsoup4` 等搜课依赖由 `uv` 根据 `pku-course-skill-main/uv.lock` **自动安装**，同学一般不必手动 pip。第一次运行 `server.py` 并点「搜索课程」时，可能会多等几十秒下载环境。

---

## 二、如何运行网页

### 步骤

1. 解压项目，进入目录 `product/discipline-map`  
   （路径以你本机解压位置为准，下面换成你的实际路径。）

```powershell
cd 你的路径\product\discipline-map
```

2. 启动服务：

```powershell
python server.py
```

终端出现类似提示即成功：

```text
学科瞭望: http://127.0.0.1:8765/
API:      http://127.0.0.1:8765/api/health
```

3. 用浏览器打开：**http://127.0.0.1:8765/**

4. 使用方式简要：
   - 左侧选**一级学科** → 右侧看介绍，并可点**二级学科**卡片
   - 标题下方绿色区域 **「搜北大相关课程」** → 改关键词 → 点 **「搜索课程」**
   - 结束时在终端按 `Ctrl + C` 关闭服务

### 端口被占用时

```powershell
$env:DISCIPLINE_MAP_PORT=8766
python server.py
```

然后打开：http://127.0.0.1:8766/

### 不要用的方式

- **不要**只双击打开 `index.html`（浏览器常会拦本地 JSON，页面也不完整）。
- **不要**只用 `python -m http.server`（能看页面，但**不能搜课**）。
- 必须保留旁边的 `pku-course-skill-main` 文件夹，且与 `discipline-map` **同级**。

---

## 三、常见问题

| 现象 | 处理 |
| --- | --- |
| `python` 不是内部或外部命令 | 重装 Python 并勾选 PATH，或换用「Python」安装器自带的终端。 |
| `uv` 不是内部或外部命令 | 重新安装 uv 后**新开**终端再试。 |
| 搜课区提示连不上 API | 确认是用 `python server.py` 启动的，并已打开上面的 `127.0.0.1` 地址。 |
| 课程名乱码 | 请使用仓库里最新的 `server.py` 后，先 `Ctrl+C` 再重新 `python server.py`，浏览器 `Ctrl+F5`。 |
| 搜课失败 / 超时 | 检查网络；教务公开站可能限流或维护，稍后再试。 |
| 缺少 `pku-course-skill-main` | 向发压缩包的人确认是否打包完整。 |

---

## 四、更多说明

- 更细的目录与数据更新：见 [`discipline-map/README.md`](discipline-map/README.md)
- 开课结果**不等于**培养方案，也**不能**代替学校正式选课系统
- 本工具只读公开数据，不会登录选课系统，也不会绕过验证码
