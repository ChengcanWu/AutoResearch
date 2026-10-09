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

- 登录：微信。网页给一个 6 位数字，学生关注公众号、把数字发过去，网页自己登进去；没注册过的微信自动注册。也可以先以访客进入，之后在「记录」页绑定微信。会话令牌放请求头 `Authorization: Bearer`；所有接口默认要登录，公开的列在 `server/auth.py` 的 `PUBLIC`，请求里带的 `uid` 必须是登录的这个人。
- 为什么是公众号消息：网站扫码登录要微信开放平台企业认证 + 备案域名，公众号网页授权要认证服务号，个人都拿不到。个人订阅号能收用户消息，消息里带 openid（只对这个公众号有效），够认出是谁。不存手机号，不用密码。
- 开通（一次）：
  1. 用个人身份注册一个订阅号（mp.weixin.qq.com，免费）。
  2. 后台「设置与开发 → 基本配置 → 服务器配置」：URL 填 `<接口地址>/api/wechat`（现在是 `https://qiyan-caxplsowco.cn-hangzhou.fcapp.run/api/wechat`），Token 填一串长随机字符，消息加解密方式选「明文模式」，提交、启用。提交时微信会来验一次签名，所以要先把同一串 Token 设成函数的 `WECHAT_TOKEN` 并发布。
  3. 设 `WECHAT_ACCOUNT_ID`（公众号原始 ID，gh_ 开头，在「设置与开发 → 公众号设置」里）和 `WECHAT_ACCOUNT_NAME`，登录页就会显示关注二维码。二维码也可以下载下来放到页面里，用 `WECHAT_QR_URL` 指过去。
  没配时页面只给访客入口。`AUTH_DEV_CODES=1` 只在本机用（登录页多一个「模拟微信发送」），配了 `WECHAT_TOKEN` 就自动失效。
- **函数计算必须只跑一个实例，且库在会保留的盘上。** 微信的消息回调和网页的轮询是两个请求：落到两个实例上，各自的库里只有一半，登录就永远等不到。所以：函数实例数上限设 1（自定义运行时把单实例并发调高，比如 20），`QIYAN_DB` 指到挂载的 NAS。`/tmp` 实例回收就清空，账号、记录一起丢。或者换一台常驻的机器跑 Docker 镜像（香港轻量服务器不用备案）。
- 微信要求消息接口五秒内回复，超时会重发两次；处理是幂等的。冷启动太慢的话，学生会看到「该公众号暂时无法提供服务」，重发一次就行；在意的话给函数留一个预留实例。
- 备份：每天跑一次 `python tools/backup_db.py --out <备份目录> --keep 7`。隐私说明承诺删号后备份最多留 7 天，`--keep` 改大要同步改 `web/js/app.js` 的 `PRIVACY_HTML` 和 `server/auth.py` 的 `PRIVACY_VERSION`。
- 上线顺序：前端和接口一起发。旧前端不带令牌，新接口会一律回 401；老用户浏览器里只有 uid 的，新前端会自动认领一次（`/api/auth/legacy`）。
