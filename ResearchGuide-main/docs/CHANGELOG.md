# CHANGELOG · 需求与文档变更日志

> **这是所有变更的唯一事实源。** 规则见 DOC_SYNC §1–2：改文档必须在这里追加条目；
> 每个 AI 开发会话开始时 agent 必读本文件并提醒用户新变更。
> 条目格式：`## [日期] [类型] 标题` + 变更内容 / 影响文档 / 影响模块 / 决策来源 / 登记人。

---

## [2026-10-03] [DOC] 产品设计提案 v2（HCI）
- 变更内容：新增 `docs/DESIGN_PROPOSAL.md`。判断：学东西越来越便宜，技能和知识不再是瓶颈，学生要赢靠的是用自己的边去差异化。所以主价值是定位与博弈层（§1D：边清单 → 竞争地图（需求 / 供给 / 势头，k≥5、按档、滞后）→ 生态位与定位陈述「我是能做 X 的人，因为 Y」→ 信号表 → 时机 → 冲 / 稳 / 保下注组合，并防羊群）；研究思维层（阅读卡 → 综合矩阵 → 问题阶梯 → 提案画布 → 最小测试）是降成本的引擎、也是边的原材料。节奏分层：每日 ≤10 分钟（arXiv 新论文分拣、雷达变化、一次定位微调），重活按周。双窗口：学生自己的 Agent 是手，启研是地图、标准和账本。IA 五标签：今日 / 定位 / 研读 / 机会 / 作品。按天排期，含验证计划（「Agent 单独 vs Agent + 启研」对照）。是提案，不改代码与契约；采纳哪些在群里定。
- 影响文档：docs/DESIGN_PROPOSAL.md（新增）、docs/README.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-10-03] [BUILD] 当前学期公开课快照：每个节点本地检索，老师可点
- 变更内容：把 2026-2027-1 全院系公开课翻进 `knowledge/catalog/`（`courses.json` / `teachers.json` / `meta.json`）。检索先读这份快照，不再每次打教务。方向树上每个节点都用节点名做关键词查课，对不上就空着。老师名可点，看到本学期教了哪些课；简介只在 OpenAlex 对上北京大学任职时才写。生成脚本：`server/catalog_build.py`。
- 影响模块：server/catalog.py、server/catalog_build.py、server/pku_adapter.py、server/main.py、web/js/app.js、web/css/styles.css、knowledge/catalog/、docs/ARCHITECTURE.md
- 决策来源：邬程灿
- 登记人：助手

## [2026-10-02] [BUILD] 方向树画成「6 步主干 + 原有节点」（任务 4 路径进树）
- 变更内容：新增 `GET /api/paths`；前端启动时读路径，把数学、人工智能、认知、经济四棵树组成「6 步主干 + 原有节点」：主干竖排成一条粗线、带序号，原有概念节点按 `docs/paths/改树建议.md` §3/§4/§7/§8 的改动清单挂到对应步骤右侧（`web/js/app.js` 的 `CHAIN_ATTACH`），`FIELD_TREES` 原文不动；统计、系统不变。点主干看「先弄懂什么 / 做完怎样算过了」，并能直接「找能交出这一步的项目」；任务页标出当前节点属于第几步、这一步要交什么；「项目」页按树上的位置预选步骤。修复：第一次在方向区接过服务端已选方向时没有按已交任务对齐进度。
- 影响模块：server/main.py、web/js/app.js、web/css/styles.css、server/tests/、docs/DESIGN_SPEC.md、docs/TASK3_PROJECTS.md、docs/paths/README.md（一行）
- 决策来源：陈浩文（依据任务 4 改树建议）
- 登记人：助手

## [2026-10-02] [BUILD] 做完之后怎么接：今日、任务完成、项目评阅都落到下一件事
- 变更内容：今日的建议按「有项目没改完 → 选了项目没交 → 交过 3 次小任务该找项目 → 继续当前节点」排，每条一个主动作加一个备选；改项目时直接引用上次评阅的「下一步」。任务完成页在交够 3 次（或走完方向）后多一个「学完一块了，找个项目练手」。项目页每次评阅和上一版比多了几条；五条全做到标为「做完了」，给「找下一个项目（难一档）」。规则表见 TASK3_PROJECTS §8。
- 影响模块：web/js/app.js、web/css/styles.css、server/projects.py（五条全做到时状态记为 done）、server/tests/、docs/TASK3_PROJECTS.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-10-02] [BUILD] 整条链路的接口测试 + GitHub Actions
- 变更内容：新增 `server/tests/test_api_flow.py`：用真实 FastAPI 应用走一遍 登录 → 五问 → 核对（改一条、划一条）→ 选方向 → 节点任务 → 提交反馈 → 找项目（实时来源全部「连不上」，走快照）→ 交压缩包 → 记录 → 软删，外加未知用户 / 方向的拒绝。数据库放临时目录、不联网、不调模型。仓库根目录新增 `.github/workflows/tests.yml`：每个 PR 和 main 上的提交跑后端测试、`node --check` 前端、并检查 `knowledge/paths.json` 和 `docs/paths/` 是否一致。
- 影响模块：server/tests/、.github/workflows/、README.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-10-02] [FIX] paths.json 接上认知、经济路径；清掉 CHANGELOG 里残留的合并冲突标记
- 变更内容：#5 加了 `docs/paths/认知.md`、`经济.md`，但没有重新生成 `knowledge/paths.json`，main 上 `server/tests` 有一条测试失败。现在跑过 `knowledge/build_paths.py`，四个方向都有 6 步路径，「项目」页的认知、经济也按路径步骤选。`改树建议.md` §5 的项目形态是为数学、人工智能写的，生成时只给这两个方向带上。另外删掉本文件里 #3 合并时留下的一行 `=======`。检索加 12 秒总时限：慢来源（今天产业命题要 20–35 秒）先用快照、后台跑完写缓存，冷启动从 40 多秒降到约 17 秒，缓存热了约 5 秒。
- 影响模块：knowledge/paths.json、knowledge/build_paths.py、server/projects.py、server/project_adapters.py、server/tests/test_projects.py、docs/TASK3_PROJECTS.md、docs/CHANGELOG.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-10-01] [BUILD] 「项目」接上任务 4 的方向路径
- 变更内容：新增 `knowledge/paths.json`（由 `knowledge/build_paths.py` 从 `docs/paths/*.md` 生成，目前有数学、人工智能）。「项目」页对有路径的方向改为「你在路径的哪一步」，按这一步的过关标准找项目；检索接口多一个可选字段 `path_step`，`context` 多返回 `paths` 和默认步骤。没有路径的方向不变。甲补上认知、经济后跑一次生成脚本即可接上。登录页「五个工作区」改为六个。
- 影响模块：server/projects.py、server/main.py、skills/project-scout/SKILL.md、web/js/app.js、web/css/styles.css、knowledge/、docs/TASK3_PROJECTS.md、docs/ARCHITECTURE.md、docs/paths/README.md（一行）
- 决策来源：陈浩文
- 登记人：助手

## [2026-09-30] [DOC] 新增方向路径交付目录（任务 4 · 数学 / 人工智能）
- 变更内容：新增 `docs/paths/`：`README.md`（每步的固定字段 + 主链标注约定）、`数学.md`、`人工智能.md`、`改树建议.md`。两条路径各 6 步，每步含「为什么是这一步 / 先弄懂什么 / 做完怎样算过了 / 依据 / 对应现有树节点」；文中共 41 条外部链接于 2026-09-30 逐条请求核对，核不到的四条（AMS Notices、Papers with Code、Hugging Face、Tao 某篇旧文）在文末如实记录，未用替代链接补位。
- 影响文档：`docs/paths/`（新增）；甲的两个方向（认知、经济）待补
- 影响模块：暂无代码改动；`web/js/app.js` 的 `FIELD_TREES` 改不改、怎么改，等两人路径合并后再定（建议见 `docs/paths/改树建议.md`）
- 决策来源：陈旭 依据任务表（任务 4乙）

## [2026-09-30] [BUILD] 任务 3 边学边练：公开来源检索项目、交压缩包、五条标准评阅
- 变更内容：新增侧栏「项目」。来源清单 `knowledge/project_sources.json`（24 个来源、72 条逐字核对过原文的样例）；7 个来源实时检索（和鲸、飞桨学习赛、天池学习赛、北大开放数据、科学数据银行、创新大赛产业命题、欧拉计划中文站），其余给快照和「去哪找」路线；查不到就空着。成果以 `.zip` 提交，只在内存里读、不执行，按五条标准评阅，规则判定是上限，模型引文必须在文件里逐字找得到；每次提交写回一条行为事实。模型的工作说明写在 `skills/project-scout/`、`skills/project-review/`，代码与 skill 分工见 `skills/README.md`。新增接口只加不改，见 ARCHITECTURE §5。
- 影响模块：server/projects.py、server/project_adapters.py、server/submission.py、server/skills.py、server/store.py（新增 projects 表）、server/main.py、web/、knowledge/、skills/、docs/TASK3_PROJECTS.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-09-30] [BUILD] 首页点线图重画 + 工作区统一样式 + 后端几处修复
- 变更内容：首页去掉 Three.js 点云（`web/vendor/three.module.js` 5.4 万行删除），改为 Canvas 2D 点线图：六张图各一种一眼能认的线稿（台阶与门、问答气泡、罗盘、秒表、打勾的提交、生长的树），点距一致、每图一个主色；每屏前 40% 停住读字，之后像一支笔按笔画顺序改画成下一张。工作区重写 `styles.css`（1739 行叠加覆盖 → 一套 token），品牌移入侧栏，页面统一左对齐；方向树改为整齐树布局，连线不再交叉；任务与反馈去掉卡片套卡片；今日按「没聊 → 没核对 → 没方向 → 当前节点」给唯一建议。修复：视图快速切换时两个页面叠在一起、中文输入法回车误发送、今日页不认服务端已选方向、SQLite 连接不关闭、课程检索每次都起子进程（加 10 分钟缓存）、学期缓存永不过期（改为 3 天）、规则反馈对任何 60 字以上提交都给满分、LLM 无重试无 JSON 模式。
- 影响模块：web/、server/store.py、server/pku_adapter.py、server/llm.py、server/workbench.py、.env.example、docs/DESIGN_SPEC.md
- 决策来源：陈浩文
- 登记人：助手

## [2026-09-28] [FIX] 方向建议按当前画像分开
- 变更内容：方向区的建议改由当前画像的兴趣事实计算，不再因为已经选过方向就消失。不同画像命中的方向不同，芯片上标「建议」，并写一句为什么贴近。每份画像各自记住当前方向和进度。
- 影响模块：server/planner.py、server/main.py、web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-28] [FIX] 刷新后保住节点进度，切换方向要确认
- 变更内容：方向和任务上的进度按已经生成过的节点任务恢复，刷新不再退回树根。点另一个领域只是预览，要点「确认切换方向」才会改当前方向，并从新树的起点重新开始。
- 影响模块：web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-28] [FIX] 切换方向不再跳进任务，提交后留下反馈
- 变更内容：在方向区点另一个领域时留在树上，并记下这棵树为当前方向。任务区只显示这棵树上当前节点的题目，不再沿用那道固定的对比实验。提交后在当前页写出 AI 反馈，不再整页重画。
- 影响模块：web/js/app.js、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-28] [BUILD] 今日和方向先画出来，任务跟当前节点走
- 变更内容：进入今日和方向时不再等模型写完才显示。今日的内容按顺序浮出，方向树从起点一层层出现。任务对应当前方向树上的节点，完成后才提示进入下一节点并安排下一阶段任务。
- 影响模块：web/js/app.js、web/css/styles.css、web/index.html、server/workbench.py、server/main.py
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-28] [BUILD] 接上 DeepSeek，方向树加深
- 变更内容：本地 `.env` 写入 DeepSeek 密钥后，对话、方向文案和任务反馈会走真实模型。方向区改为六个领域各自一棵四层左右的树，点节点弹出介绍，可沿分支继续点。工作区侧栏和面板收得更紧。
- 影响模块：server/llm.py、web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 粒子左暗改成渐变，鼠标只碰身边
- 变更内容：从屏幕右侧到左侧亮度慢慢降一点，左边的粒子还在，不会突然灭掉。鼠标恢复成只拨开身边一小圈，划一下不再把整张图扭开。
- 影响模块：web/js/app.js、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页粒子让开文字，鼠标改成慢回的波纹
- 变更内容：散开时粒子主要往右走，左边文字区域的粒子压暗、缩小，避免挡住字。鼠标划过时粒子立刻分开，再像水波一样往外荡，大约三秒才慢慢合上。
- 影响模块：web/js/app.js、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 多画像、黑底粒子，方向改成生长的树
- 变更内容：画像可以新建、切换、删除，只有一份时显示为画像一。应用页去掉说明性文案。首页改为黑底，粒子用白、蓝、绿发光；图形聚好后先停一截再散开，散开时粒子朝眼前冲过来再聚合成下一张。方向区用一条会分叉的树标出已经过的节点、当前节点和还可以去的节点。
- 影响模块：server/store.py、server/main.py、web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 进入后改为工作区，不再按 1 到 9 往下点
- 变更内容：登录和首页体验按钮之后进入「今日」。左侧是今日、画像、方向、任务、记录五个工作区，主区域只显示当前这一个。画像里的对话和核对、任务里的提交和反馈，都留在各自工作区内部。保存、切换、返回不再被一条全局步骤条串起来。
- 影响模块：web/index.html、web/js/app.js、web/css/styles.css
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页补上每步说明，图案更快散开
- 变更内容：六屏各补一段重点说明，小任务页写清二十分钟、留下结果、按提交说话。图案聚好后，大约滑两下就开始散开，不再在页首停很长一段。
- 影响模块：web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页加长，体验按钮移到末尾
- 变更内容：「立即开始体验」只出现在最后一屏底部。每一屏加高，并用序号、刻度、清单这类版式把高度撑开。粒子在后半段滚动里慢慢散开，范围铺到整屏，再聚成下一张图。
- 影响模块：web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页图案改回粒子勾线
- 变更内容：去掉实线轮廓和填色。六张图都由更密的粒子自己画出来，分别是人与门、侧脸对话、罗盘分岔、二十分钟的钟和清单、批改标记、树与上升节点。滚动时先散开再聚拢；粒子可增减并淡入淡出，颜色随图渐变。
- 影响模块：web/js/app.js、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页改为连续滚动，轮廓实线、粒子填色
- 变更内容：去掉整屏吸附。滚动时当前形状先散成带噪声的曲线云，再聚成下一步。每个图案用实线勾边，粒子填在轮廓里面。
- 影响模块：web/js/app.js、web/css/styles.css、web/index.html
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-27] [BUILD] 首页粒子改为 Three.js 点云
- 变更内容：首页六屏粒子从 2D 方点改为 WebGL `Points`（约 2 万颗）。轮廓仍对应六页主题；滚动时在预计算点云之间形变。运动带小幅噪声漂移，鼠标附近有斥力与涟漪。点是软边圆点，墨色里夹少量橙色。未加全屏泛光，避免纸色底上字发雾。Three.js 放在 `web/vendor/three.module.js`。
- 影响模块：web/js/app.js、web/index.html、web/vendor
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-24] [DOC] 项目基线 v1.0 建立
- 变更内容：完成旧 Demo 审计、产品重构方案、全套 docs（PRD/架构/路线/分工等 21 份）
- 当前状态：**产品功能描述为草案**，D1–D10 决策（见 PRODUCT_EXPLAINED §五）待 2026-09-25 脑暴会逐条拍板
- 影响模块：全部
- 决策来源：项目组
- 登记人：A

## [待脑暴] 以下条目 9/25 会后补录
- D1 产品名
- D2 Onboarding 形态
- D3 首批重点学科名单
- D4 微任务素材来源
- D5 账号形态
- D6 部署位置
- D7 反馈通知频率
- D8 LLM 选型
- D9 论文陪读版权边界
- D10 种子用户计划

## [2026-09-27] [BUILD] 页面连接模型 + 视觉提一档
- 变更内容：首页与右上角可填写 OpenAI 兼容接口，连通后写入本机 `.env`。开场白、方向卡「为什么是你」、下一步文案、任务反馈在连通后走模型，失败仍回退规则。首页增加点云、序号橙色游标、分页底色和胶囊导航。
- 影响模块：server/llm.py、main.py、onboarding.py、planner.py、web
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-26] [BUILD] 接入 OpenAI 兼容模型 + 首页视觉升级
- 变更内容：新增 `server/llm.py`，对话回应、自由文本事实归纳、NBA 文案、任务反馈在配置 `LLM_API_KEY` 后走真实模型，失败回退规则。首页增加加载页、顶部引导细线和序号色块。密钥放 `.env`，示例见 `.env.example`。
- 影响模块：server/llm.py、onboarding、planner、workbench、web
- 决策来源：邬程灿
- 登记人：助手

## [2026-09-25] [BUILD] W0 核心 Demo 交付 + 文档体系精简
- 变更内容：
  1. **W0 Thin Slice 全链路实装并验证**：昵称登录 → 5 轮 onboarding（选项卡+不知道）→ UM 确认页（可改可删）→ 3 张方向推荐卡（rationale 引用用户原话 + 北大真实课程 live 检索 + 入门读物）→ 20 分钟微任务 → 提交 → rubric 逐条反馈 → behavior 事实真实写回 UM → 进阶 NBA。技术：FastAPI（server/）+ 无构建静态前端（web/），课程检索经 uv 子进程调 skills/pku-course（原 pku-course-skill-main 原样迁入），LLM 三处按 NEXT_PRE §3 白名单 mock（数据结构真实）。
  2. **文档精简 25→5**：新增 DESIGN_SPEC（旧 Demo 视觉提炼为规范）、ARCHITECTURE（四份长文档浓缩合并）、TASK_ASSIGNMENTS（6 人 vibecoding+PR 分工）；删除 PRD/VISION/GAP/AUDIT/DOC_SYNC/SESSION_PROMPT/RISK/ROADMAP 等 20 份长文档与 ideas/想法类文件。
  3. **旧 Demo 处置**：discipline-map 网页删除（设计已提炼进 DESIGN_SPEC，搜课适配逻辑迁入 server/pku_adapter.py）；可复用资产迁入 skills/pku-course 与 knowledge/。
- 影响模块：全部
- 决策来源：别克扎提（产品 Owner）
- 登记人：别克扎提·拜别提
