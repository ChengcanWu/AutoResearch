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

- 登录：访客起个称呼即可。若开了公众号，网页给一个 6 位数字，学生关注后把数字发过去就能认回同一个号；也可以先访客、之后在「记录」页绑定微信。会话令牌放请求头 `Authorization: Bearer`；所有接口默认要登录，公开的列在 `server/auth.py` 的 `PUBLIC`，请求里带的 `uid` 必须是登录的这个人。
- 函数计算必须尽量只跑一个实例，且库在会保留的盘上。现在线上 SQLite 仍写 `/tmp`，实例回收会丢掉账号和记录。`/api/health` 的 `db.ephemeral` 为 true 就是这种情况。前端遇到 `user not found` / 401 会清掉过期会话，请重新进入，不再把研读工具包显示成加载失败。
- 上线顺序：前端和接口一起发。旧前端不带令牌，新接口会一律回 401；老用户浏览器里只有 uid 的，新前端会自动认领一次（`/api/auth/legacy`）。
- 工作线程数默认 128（`QIYAN_THREADS`）。流式对话有总时限和字数封顶，并对 DeepSeek 关掉思考。
