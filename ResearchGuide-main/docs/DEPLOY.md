# 启研部署

控制台若问「Dockerfile 文件名」，填 `Dockerfile`。构建上下文是 `ResearchGuide-main`。

## 三套环境

| 环境 | 给谁 | 怎么起 |
| --- | --- | --- |
| 开发 | 写代码的人 | `docker compose up qiyan` → http://127.0.0.1:8100 |
| 测试 | 组内联调 | `docker compose up qiyan-test` → http://127.0.0.1:8101 ；云上是函数 `qiyan-test` |
| 生产 | 真实用户 | 页面 https://chengcanwu.github.io/AutoResearch/ ；接口函数 `qiyan`（杭州） |

没有备案域名，生产首页不用 `fcapp.run`（会下载 htm）。没有开 ECS：帐号按量付费额度不够，不充值。

## 本机容器

```
cd ResearchGuide-main
docker compose build
docker compose up qiyan
```

复制 `.env.example` 为 `.env` 并填 `LLM_API_KEY` 才会走模型。库文件在卷 `/data/qiyan.db`。

回滚：`docker compose down`，换回上一版镜像或 git 标签再 `build`。

## 云上函数

```
cd ResearchGuide-main/tools/deploy
python download_wheels.py
python deploy_fc.py
python deploy_fc.py qiyan-test
```

生产函数名 `qiyan`，测试函数名 `qiyan-test`。密钥只在本机 `.env` 和函数环境变量，不入库。

## 账号与数据

- 登录：学校邮箱验证码（默认只收 `edu.cn` 结尾），或访客昵称。会话令牌放请求头 `Authorization: Bearer`；所有接口默认要登录，公开的列在 `server/auth.py` 的 `PUBLIC`，请求里带的 `uid` 必须是登录的这个人。
- 发信：设 `SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD`（QQ / 163 邮箱开 SMTP 用授权码）。不设时页面只给访客入口。`AUTH_DEV_CODES=1` 只在本机用，线上不要设。
- 库文件：`QIYAN_DB` 指到会保留的盘。云函数的 `/tmp` 实例回收就清空，账号、记录一起丢；多实例时每个实例各有一份。要么函数挂 NAS 并把实例数限成 1，要么换一台常驻的机器（香港轻量服务器不用备案）。
- 备份：每天跑一次 `python tools/backup_db.py --out <备份目录> --keep 7`。隐私说明承诺删号后备份最多留 7 天，`--keep` 改大要同步改 `web/js/app.js` 的 `PRIVACY_HTML` 和 `server/auth.py` 的 `PRIVACY_VERSION`。
- 上线顺序：前端和接口一起发。旧前端不带令牌，新接口会一律回 401；老用户浏览器里只有 uid 的，新前端会自动认领一次（`/api/auth/legacy`）。
