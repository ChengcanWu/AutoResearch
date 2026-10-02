# TASK3 · 边学边练：项目从哪来、怎么派、交上来怎么评

> 任务表「任务 3」的交付说明。代码：`server/projects.py`、`server/project_adapters.py`、`server/submission.py`；给模型的说明：`skills/project-scout/`、`skills/project-review/`；来源清单：`knowledge/project_sources.json`；界面：侧栏「项目」。

## 1. 来源清单

共 24 个来源、72 条样例，全部在 2026-09-29/30 实际访问核对；每条样例的「原文」逐字出自当时抓到的页面或接口返回。完整字段（接口地址、参数、字段映射、注意事项）见 [`knowledge/project_sources.json`](../knowledge/project_sources.json)。

> ⚠️ 核对时的出口 IP 在台北（台大），不是大陆。所有「能不能连上」的结论需要在大陆网络下复测；北大开放数据的网页在境外 IP 下返回 403，接口正常。

| 来源 | 类型 | 方向 | 阶段 | 取数方式 | 样例 |
| --- | --- | --- | --- | --- | --- |
| [开源之夏 OSPP（点亮计划）](https://summer.ospp.ac.cn/) | 开源 | 系统、AI | 学完一块、做过项目 | 快照 + 路线 | 4 |
| [GLCC 开源编程夏令营（GitLink）](https://www.gitlink.org.cn/glcc) | 开源 | 系统、AI | 学完一块、做过项目 | 快照 + 路线 | 4 |
| [Gitee Issues（API v5）](https://gitee.com/) | 开源 | 系统、AI | 学完一块、做过项目 | 快照 + 路线 | 2 |
| [GitCode / AtomGit Issues（API v5）](https://gitcode.com/) | 开源 | 系统、AI | 做过项目 | 快照 + 路线 | 1 |
| [飞桨 AI Studio 学习赛/比赛](https://aistudio.baidu.com/competition) | 竞赛 | AI、经济、数学 | 小任务、学完一块 | 实时接口 | 6 |
| [阿里云天池 新人赛/教学赛](https://tianchi.aliyun.com/competition/gameList/activeList) | 竞赛 | 经济、统计、AI | 概念、小任务、学完一块 | 实时接口 | 5 |
| [和鲸社区 Heywhale 训练营/Workshop](https://www.heywhale.com/home/competition) | 课程作业 | 认知、经济、统计、AI | 概念、小任务、学完一块 | 实时接口 | 5 |
| [DataFountain 往届经典赛](https://www.datafountain.cn/competitions) | 竞赛 | AI、认知 | 小任务、学完一块 | 快照 + 路线 | 2 |
| [魔搭 ModelScope 赛事/活动](https://www.modelscope.cn/) | 竞赛 | AI | 小任务、学完一块、做过项目 | 快照 + 路线 | 2 |
| [全国大学生数学建模竞赛 CUMCM 历年赛题](https://www.mcm.edu.cn/html_cn/block/8579f5fce999cdc896f78bca5d4f8237.html) | 竞赛 | 数学、统计 | 学完一块、做过项目 | 快照 + 路线 | 2 |
| [Project Euler 欧拉计划中文站（pe-cn.github.io）](https://pe-cn.github.io/) | 公开题 | 数学、AI | 概念、小任务、学完一块 | 实时接口 | 4 |
| [北京大学开放研究数据平台（Dataverse）](https://opendata.pku.edu.cn/) | 公开数据 | 认知、经济、统计、AI | 小任务、学完一块、做过项目 | 实时接口 | 5 |
| [科学数据银行 Science Data Bank（scidb.cn）](https://www.scidb.cn/) | 公开数据 | 认知、经济、统计 | 小任务、学完一块、做过项目 | 实时接口 | 4 |
| [国家统计局 国家数据（data.stats.gov.cn）](https://data.stats.gov.cn/) | 公开数据 | 经济、统计 | 概念、小任务、学完一块 | 不可达 | 0 |
| [国家级大学生创新创业训练计划平台](http://gjcxcy.bjtu.edu.cn/) | 创新项目 | 认知、经济、数学、AI、统计、系统 | 学完一块、做过项目 | 只给路线 | 0 |
| [“挑战杯”竞赛（含揭榜挂帅、人工智能+ 专项）](https://www.tiaozhanbei.net/) | 竞赛 | AI、经济、系统、认知 | 小任务、学完一块、做过项目 | 快照 + 路线 | 4 |
| [中国国际大学生创新大赛（原“互联网+”）产业赛道企业命题](https://cy.ncss.cn/mtcontest/list) | 公开题 | 认知、经济、统计、AI、系统、数学 | 学完一块、做过项目 | 实时接口 | 4 |
| [全国大学生统计建模大赛](http://tjjmds.ai-learning.net/) | 竞赛 | 统计、经济 | 小任务、学完一块、做过项目 | 快照 + 路线 | 3 |
| [全国大学生市场调查与分析大赛（中国商业统计学会）](http://www.china-cssc.org/list-60-1.html) | 竞赛 | 经济、统计、认知 | 概念、小任务、学完一块 | 快照 + 路线 | 4 |
| [头歌 EduCoder 实践课程](https://www.educoder.net/) | 课程作业 | AI、数学、统计、系统 | 概念、小任务、学完一块 | 快照 + 路线 | 3 |
| [蓝桥云课](https://www.lanqiao.cn/) | 课程作业 | AI、系统 | 概念、小任务 | 快照 + 路线 | 1 |
| [北大课程公开作业仓库（GitHub）](https://github.com/search?q=pku+course&type=repositories) | 课程作业 | 系统、AI | 概念、小任务、学完一块、做过项目 | 快照 + 路线 | 3 |
| [R4Psy：R语言在心理学研究中的应用（南京师范大学，GitHub）](https://github.com/hcp4715/R4Psy) | 课程作业 | 认知、统计 | 概念、小任务、学完一块、做过项目 | 快照 + 路线 | 2 |
| [OSF 心理学重复研究（Many Labs 等）](https://osf.io/) | 公开题 | 认知 | 学完一块、做过项目 | 快照 + 路线 | 2 |

**每个来源的样例**（标题 · 在练什么 · 原文 · 检索时间）

- **开源之夏 OSPP（点亮计划）**
  - [基于Agent实现自然语言驱动的数据看板生成与发布（DB-GPT）](https://summer.ospp.ac.cn/org/prodetail/26f420021) · 自然语言→SQL→图表的 BI 看板生成；Dashboard schema 设计、组件查询绑定 · 原文「完成看板编辑发布及两个演示案例」 · 2026-09-29
  - [为 AReno 增加 OPD 算法支持：接入 On-Policy Distillation 训练流程](https://summer.ospp.ac.cn/org/prodetail/267bf0003) · 大模型后训练算法（On-Policy Distillation）、PyTorch、在已有算法注册机制上扩展 · 原文「在AReno仓库实现完整的OPD算法」 · 2026-09-29
  - [基于Agent实现财报采集分析与可追溯研究分析（DB-GPT）](https://summer.ospp.ac.cn/org/prodetail/26f420016) · 公开财报抓取与结构化抽取（营收、毛利、现金流等）、同比/环比与公司对比分析、数据来源追踪 · 原文「提供单公司财报分析和多公司财务对比分析两个可演示案例」 · 2026-09-29
  - [基于Kaiwu-PyTorch-Plugin实现均衡传播算法](https://summer.ospp.ac.cn/org/prodetail/26b1f0072) · 能量模型与均衡传播（Equilibrium Propagation）、与反向传播对比实验、单元测试 · 原文「一个可直接运行的分类训练示例」 · 2026-09-29
- **GLCC 开源编程夏令营（GitLink）**
  - [OpenCT-AI文本数据挖掘项目](https://www.gitlink.org.cn/Open-CT/AI) · 用大语言模型做大规模文本分析与挖掘、撰写分析报告 · 原文「对文本类大规模教育资料进行分析和挖掘」 · 2026-09-29
  - [基于AI的大数据挖掘（OpenCT）](https://www.gitlink.org.cn/Open-CT/OpenCT-AI) · 爬虫开发、用大模型对爬取数据做编码分析 · 原文「开发相应的爬虫流程」 · 2026-09-29
  - [成为开源社区的「种子运营官」（OpenGrow）](https://www.gitlink.org.cn/metax-maca/opengrow/issues/1) · 开源社区调研、轻量贡献、运营方案设计 · 原文「绘制技术图谱，分析社区现状」 · 2026-09-29
  - [具身智能训练工具链开发（x-humanoid）](https://www.gitlink.org.cn/X-Humanoid/x-humanoid-training-toolchain/issues/1) · 具身操作模型训练工具链 · 原文「实现使用者可以低门槛的高效训练端到端主流模型」 · 2026-09-29
- **Gitee Issues（API v5）**
  - [LeakyReLU 算子 Kernel 未注册（MindSpore, intern）](https://gitee.com/mindspore/mindspore/issues/IBRPVP) · 深度学习框架算子注册与测试 · 原文「The kernel LeakyReLUExt unregistered」 · 2026-09-29
  - [基于diffuser的虚拟试衣项目pytorch转换mindspore框架推理实现](https://gitee.com/mindspore/mindspore/issues/IB2OYP) · 模型迁移（PyTorch→MindSpore）、权重迁移与推理部署 · 原文「将pytorch2.1替换成mindspore来进行推理」 · 2026-09-29
- **GitCode / AtomGit Issues（API v5）**
  - [【TASK】aclnnLeScalar 接入（MindSpore）](https://gitcode.com/mindspore/mindspore/issues/29685) · 深度学习框架算子接入 · 原文「补充专用的 `LeScalar` 执行路径」 · 2026-09-29
- **飞桨 AI Studio 学习赛/比赛**
  - [飞桨学习赛：中文新闻文本标题分类](https://aistudio.baidu.com/competition/detail/809/0/introduction) · 文本分类（THUCNews 14 类）、PaddleNLP 基线 · 原文「要求参赛者基于原始新闻标题文本数据训练模型」 · 2026-09-29
  - [飞桨学习赛：个贷违约预测](https://aistudio.baidu.com/competition/detail/803/0/introduction) · 信贷风险二分类、表格特征工程（利率、债务收入比等） · 原文「train_public.csv 个人贷款违约记录数据」 · 2026-09-29
  - [飞桨学习赛：MarTech Challenge 用户购买预测](https://aistudio.baidu.com/competition/detail/819/0/introduction) · 用户购买行为预测、订单数据特征构造 · 原文「预测下个月用户是否购买」 · 2026-09-29
  - [飞桨学习赛：英雄联盟大师预测](https://aistudio.baidu.com/competition/detail/797/0/introduction) · 表格二分类、数据挖掘入门 · 原文「预测玩家在本局游戏中的输赢情况」 · 2026-09-29
  - [飞桨学习赛：图神经网络入门节点分类](https://aistudio.baidu.com/competition/detail/817/0/introduction) · 图神经网络节点分类（论文引用网络） · 原文「图上的每个节点代表一篇论文」 · 2026-09-29
  - [飞桨学习赛：量子电路合成](https://aistudio.baidu.com/competition/detail/815/0/introduction) · 量子门近似合成（线性代数/优化） · 原文「量子电路合成是量子计算中十分重要的问题」 · 2026-09-29
- **阿里云天池 新人赛/教学赛**
  - [【教学赛】金融数据分析赛题1：银行客户认购产品预测](https://tianchi.aliyun.com/competition/entrance/531993/introduction) · 分类预测、客户特征与宏观指标（就业、银行同业拆借率） · 原文「预测用户是否进行购买产品」 · 2026-09-29
  - [【教学赛】金融数据分析赛题3：证券数据可视化分析](https://tianchi.aliyun.com/competition/entrance/531992/introduction) · 股票/指数日线月线、融资融券、MACD 等指标可视化 · 原文「你感兴趣的某一支股票，和大盘之间的相关性」 · 2026-09-29
  - [资金流入流出预测-挑战Baseline](https://tianchi.aliyun.com/competition/entrance/231573/introduction) · 时间序列预测、申购赎回与利率数据 · 原文「用户申购赎回数据、收益率表和银行间拆借利率表」 · 2026-09-29
  - [【教学赛】数据分析达人赛1:用户情感可视化分析](https://tianchi.aliyun.com/competition/entrance/531890/introduction) · 评论文本情感/议题的探索性分析与可视化 · 原文「为10000+条行业用户关于耳机的评论」 · 2026-09-29
  - [【天池经典打榜赛】赛道六-评论观点挖掘赛](https://tianchi.aliyun.com/competition/entrance/532421/introduction) · 属性级情感分析/信息抽取 · 原文「在商品评论中抽取商品属性特征和消费者观点」 · 2026-09-29
- **和鲸社区 Heywhale 训练营/Workshop**
  - [R 语言心理学数据分析训练营 PSY1.0：数据读取和预处理](https://www.heywhale.com/home/competition/652df88ecf318d693e2b20de) · R/tidyverse 清洗心理学实验与问卷数据、反向计分、贝叶斯概率分布 · 原文「对问卷数据实现反向计分与加和等操作」 · 2026-09-29
  - [R 语言量化社会科学训练营（上）：从统计分析到因果推断 QSS1](https://www.heywhale.com/home/competition/66f7bd325ff342a282a967ea) · 用 CGSS 数据做描述统计、假设检验、线性回归、双重差分 · 原文「关卡 4：因果推断：运用双重差分法评估政策效应」 · 2026-09-29
  - [超丝滑！经管Python统计分析](https://www.heywhale.com/home/competition/65dd5b8227f874132ff7cabc) · 描述统计、假设检验、方差分析、相关与回归（GDP、房价数据） · 原文「对北京和上海GDP情况进行假设检验和方差分析」 · 2026-09-29
  - [R 语言量化社会科学训练营（下）QSS2](https://www.heywhale.com/home/competition/6757b8ca2b6570ddb795f9c5) · 蒙特卡洛模拟、文本数据探索、因果推断与政策评估 · 原文「蒙特卡洛实验、文本数据探索、因果推断与政策评估实战操作」 · 2026-09-29
  - [我在和鲸狂刷统计知识100题](https://www.heywhale.com/home/competition/655aedfcedce41c896f92393) · 统计学基础知识题库 · 原文「一边做题查漏，一边看解析补缺」 · 2026-09-29
- **DataFountain 往届经典赛**
  - [剧本角色情感识别（经典赛）](https://www.datafountain.cn/competitions/518) · 多维度情感识别、上下文依赖的对白理解 · 原文「对剧本场景中每句对白和动作描述中涉及到的每个角色的情感」 · 2026-09-29
  - [疫情期间网民情绪识别（经典赛）](https://www.datafountain.cn/competitions/423) · 微博情绪三分类（积极/消极/中性） · 原文「判断微博内容是积极的、消极的还是中性的」 · 2026-09-29
- **魔搭 ModelScope 赛事/活动**
  - [昇腾CANN社区任务【7月】](https://www.modelscope.cn/competition/250) · 昇腾 CANN 算子/开发实操任务 · 原文「任务每月更新，月底截止」 · 2026-09-29
  - [知乎黑客松 2026 校园新锐季](https://www.modelscope.cn/competition/346) · AI 应用创意与原型 · 原文「用 AI 解锁知识社区的「新玩法」」 · 2026-09-29
- **全国大学生数学建模竞赛 CUMCM 历年赛题**
  - [2026年高教社杯全国大学生数学建模竞赛赛题](https://www.mcm.edu.cn/html_cn/node/27b6e148f8113f09b0269f64a02629fb.html) · 数学建模（题面在 zip 附件，本次未下载） · 原文「点击链接下载赛题」 · 2026-09-29
  - [2025年高教社杯全国大学生数学建模竞赛赛题](https://www.mcm.edu.cn/html_cn/node/03c91a444e62eee81a3740fa97a461a6.html) · 数学建模（题面在 zip 附件，本次未下载） · 原文「赛题见附件！」 · 2026-09-29
- **Project Euler 欧拉计划中文站（pe-cn.github.io）**
  - [Problem 1：3或5的倍数](https://pe-cn.github.io/1/) · 整除、容斥 · 原文「求小于$1000$的自然数中所有$3$或$5$的倍数之和」 · 2026-09-29
  - [Problem 12：有很多约数的三角形数](https://pe-cn.github.io/12/) · 三角形数、约数个数函数 · 原文「第一个约数数量超过五百的三角形数是多少？」 · 2026-09-29
  - [Problem 31：硬币求和](https://pe-cn.github.io/31/) · 计数/动态规划（整数分拆） · 原文「不限制硬币数量，凑出£2有多少种不同的做法？」 · 2026-09-29
  - [Problem 100：Arranged Probability](https://pe-cn.github.io/100/) · 概率 + 二次丢番图方程（Pell 型） · 原文「chance of taking two blue discs」 · 2026-09-29
- **北京大学开放研究数据平台（Dataverse）**
  - [Replication Data for: Analysis of Chinese Society's Emotional Perception in the Background of China-US Trade War Based on Weibo Public Opinion](https://doi.org/10.18170/DVN/6HHMGY) · 社交媒体情绪感知、爬虫数据清洗、情感分析 · 原文「Sina Weibo official website」 · 2026-09-29
  - [The Influencing Factors of Online Fundraising Trust](https://doi.org/10.18170/DVN/HLWSOX) · 问卷数据分析、信任影响因素（社会心理） · 原文「Training Program of Nankai University」 · 2026-09-29
  - [Analysis of Factors Influencing Public Behavior Decision-making Under Mass Incidents](https://doi.org/10.18170/DVN/NLK783) · 结构方程模型（AMOS）、公众行为决策 · 原文「using the structural equation method」 · 2026-09-29
  - [Replication Data for: Housing Price and Talent Allocation](https://doi.org/10.18170/DVN/KW1AMR) · Stata 面板数据清洗、房价与公私部门职业选择 · 原文「China Labor Dynamics Survey (CLDS)」 · 2026-09-29
  - [CPI Weibo text data for Real-time Prediction of CPI](https://doi.org/10.18170/DVN/TXXO4M) · 文本聚类+情感得分构造 CPI 实时预测指标 · 原文「CPI series from 2016 to 2018」 · 2026-09-29
- **科学数据银行 Science Data Bank（scidb.cn）**
  - [中国大学生“躺平”心理的内涵及问卷编制](https://doi.org/10.57760/sciencedb.27362) · 量表编制、问卷数据清洗（按作答时长剔除）、信效度分析 · 原文「《大学生躺平心态量表》预测试」 · 2026-09-29
  - [《心理学与脑科学研究中的样本代表性》补充材料](https://doi.org/10.57760/sciencedb.17369) · 系统综述、被试人口学信息编码 · 原文「女性被试多于男性」 · 2026-09-29
  - [基于线性混合效应模型的心理实验数据建模stan代码](https://doi.org/10.57760/sciencedb.j00052.00299) · 线性混合效应模型、Stan 贝叶斯建模 · 原文「基于线性混合效应模型的心理实验数据建模」 · 2026-09-29
  - [中国货币政策、股票价格与非对称性——基于计量经济学与人工智能方法的比较研究](https://doi.org/10.57760/sciencedb.j00214.00170) · VAR/MS-VAR 与 LSTM 对比、货币政策非对称效应 · 原文「熊市下扩张性货币政策效果大于牛市下紧缩性货币政策效果」 · 2026-09-29
- **国家统计局 国家数据（data.stats.gov.cn）**：没有可直接取的样例。data.stats.gov.cn → 年度/季度/月度数据 → 选指标 → 下载表格（新版为 SPA）。
- **国家级大学生创新创业训练计划平台**：没有可直接取的样例。gjcxcy.bjtu.edu.cn → 历年项目 → 选年份 → “学校查询”选项卡填项目名称关键词（如“心理”）→ 查询。
- **“挑战杯”竞赛（含揭榜挂帅、人工智能+ 专项）**
  - [第十九届“挑战杯”竞赛“人工智能+”专项赛（创意赛道）](https://www.tiaozhanbei.net/article/15775/) · 借助大模型零/低代码做 AI 原生应用 · 原文「通过零代码或低代码完成人工智能原生应用的设计」 · 2026-09-29
  - [2026年度中国青年科技创新“揭榜挂帅”擂台赛第二批榜题](https://www.tiaozhanbei.net/article/15841/) · 企业真实技术难题攻关（信息技术、AI、机器人等） · 原文「揭榜报名时间为2026年5月30日至2026年6月30日」 · 2026-09-29
  - [2026年度“揭榜挂帅”擂台赛第一批（103 个榜题）](https://www.tiaozhanbei.net/article/15836/) · 8 大前沿领域企业榜题 · 原文「严选 103 个榜题」 · 2026-09-29
  - [第十五届“挑战杯”中国大学生创业计划竞赛通知](https://www.tiaozhanbei.net/article/15842/) · 商业模式创新、创业计划（8 个赛道含新消费与文化创意） · 原文「围绕价值创造逻辑重构、交易结构优化、盈利模式突破」 · 2026-09-29
- **中国国际大学生创新大赛（原“互联网+”）产业赛道企业命题**
  - [基于多维度数据挖掘的博彩行为经济与心理危害量化分析及风险防控研究](https://cy.ncss.cn/mtcontest/detail?id=2c93f4c6a00f063201a03d78660e1bf6) · 脱敏行为数据清洗与统计、非理性消费与成瘾风险量化 · 原文「验证长期博彩无正收益、投注越多亏损越显著的核心规律」 · 2026-09-29
  - [基于AI技术的心理健康风险智能筛查体系构建与应用研究的项目征集](https://cy.ncss.cn/mtcontest/detail?id=2c93f4c6a00f063201a03d780884128d) · 心理健康筛查、量表与多模态数据融合 · 原文「从“单一量表”到“多模态数据融合”的转变」 · 2026-09-29
  - [基于统计检测与机器学习研究客户对保险兴趣因素分析](https://cy.ncss.cn/mtcontest/detail?id=2c93f4c6a00f063201a03d7866311bfe) · 客户数据预测建模、统计检验 · 原文「帮助公司识别哪些现有客户可能对新的车辆保险产品感兴趣」 · 2026-09-29
  - [数字经济、智慧赋能——商业智能BI在零售业的预测与优化](https://cy.ncss.cn/mtcontest/detail?id=2c93f4c6a00f063201a03d7865cc1be8) · 销售预测（时间序列、回归）、库存与供应链优化、BI 可视化 · 原文「如时间序列分析、回归分析等」 · 2026-09-29
- **全国大学生统计建模大赛**
  - [2026年(第十二届)全国大学生统计建模大赛（主题：服务国家战略 创新统计赋能）](http://tjjmds.ai-learning.net/dstz/37119.jhtml) · 统计建模论文写作、自拟选题 · 原文「参赛队围绕主题自拟题目撰写论文」 · 2026-09-29
  - [2026年统计建模大赛培训课程（主题讲解与研究方向建议）](http://tjjmds.ai-learning.net/pxzy/37123.jhtml) · 选题方法、统计建模流程、AI 工具规范 · 原文「统计建模大赛主题讲解与研究方向建议」 · 2026-09-29
  - [2022年（第八届）统计建模大赛主题解读（文字版）](http://tjjmds.ai-learning.net/dsdt/36782.jhtml) · 统计测度、因果推断、政策干预效果评估 · 原文「政策干预效果评估的统计测度」 · 2026-09-29
- **全国大学生市场调查与分析大赛（中国商业统计学会）**
  - [第十七届全国大学生市场调查与分析大赛（通知）](http://www.china-cssc.org/show-304-2179-1.html) · 市场调查理论（知识赛）、团队调研项目 · 原文「实践赛发文及企业命题公布」 · 2026-09-29
  - [优秀论文：智能手环使用现状及产品发展分析报告](http://www.china-cssc.org/show-22-315-1.html) · 电商评论文本挖掘 + 抽样调查 · 原文「基于电商平台消费者购买评价的文本挖掘与武汉市的抽样调查」 · 2026-09-29
  - [优秀论文：大学生烘焙类食品消费习惯调查及产品定制](http://www.china-cssc.org/show-22-313-1.html) · 消费习惯问卷调查 · 原文「大学生烘焙类食品消费习惯调查及产品定制」 · 2026-09-29
  - [优秀论文：“读研热”的冷思考调查报告](http://www.china-cssc.org/show-22-314-1.html) · 大学生升学意向调查 · 原文「”读研热“的冷思考调查报告」 · 2026-09-29
- **头歌 EduCoder 实践课程**
  - [机器学习实践（复旦大学）](https://www.educoder.net/paths/ygpm7bqe) · 分类、文本分析、CNN/RNN、注意力、GAN、推荐系统 · 原文「实现了近20个典型的实战案例」 · 2026-09-29
  - [数学建模实验——MATLAB版（集美大学）](https://www.educoder.net/paths/ijq7wl3s) · 数学规划、图论、微分方程、插值拟合、数理统计 · 原文「数学规划模型、图论算法、微分方程、插值拟合、数理统计」 · 2026-09-29
  - [数理统计（头歌教研中心）](https://www.educoder.net/paths/nepso6it) · 统计推断与预测 · 原文「研究怎样用有效的方法去收集和使用受随机性影响的数据」 · 2026-09-29
- **蓝桥云课**
  - [机器学习开放基础课程](https://www.lanqiao.cn/courses/1283) · 常用分类/回归算法与数据预处理 · 原文「机器学习免费基础实战课」 · 2026-09-29
- **北大课程公开作业仓库（GitHub）**
  - [北大编译实践在线文档（SysY → RISC-V 编译器）](https://github.com/pku-minic/online-doc) · 词法/语法分析、IR、RISC-V 代码生成 · 原文「实现一个可将 SysY 语言编译到 RISC-V」 · 2026-09-29
  - [《开源软件开发》课程项目：为真正的开源项目做贡献](https://github.com/osslab-pku/OSSDevelopment/blob/main/Assignments/Project.md) · 开源协作、PR、社区沟通 · 原文「对一个或多个具有一定质量水准的开源项目，做出自己的贡献」 · 2026-09-29
  - [《开源软件开发》Lab 1：熟悉git和GitHub](https://github.com/osslab-pku/OSSDevelopment/blob/main/Assignments/Lab1.md) · git/GitHub 基本流程 · 原文「熟悉开源软件开发中常用的工具、平台、和开发流程」 · 2026-09-29
- **R4Psy：R语言在心理学研究中的应用（南京师范大学，GitHub）**
  - [R4Psy 第二次作业：penguin 数据读取与清洗](https://github.com/hcp4715/R4Psy/blob/main/practice/The_2nd_homework.Rmd) · R 读数、dplyr 筛选变量、类型转换 · 原文「读取 penguin_rawdata.csv」 · 2026-09-29
  - [心理学量化研究的计算可复现性检验指南](https://github.com/hcp4715/R4Psy/tree/main/reproducibility_check_guide) · 计算可复现性检验流程、报告模板与评分表 · 原文「完成一篇心理学量化研究的计算可复现性检验」 · 2026-09-29
- **OSF 心理学重复研究（Many Labs 等）**
  - [Reproduction of Many Labs' Replication of the Van Lange et al. study on SVO and Family Size](https://osf.io/p4evh/) · 社会价值取向与兄弟姐妹数的相关、重复研究方法 · 原文「was not able to reproduce this effect」 · 2026-09-29
  - [Many Labs 3: Participant Pool Edition](https://osf.io/swiz8/) · 学期时间对效应可检测性的影响、多实验室协议 · 原文「10 known effects within 30 minutes」 · 2026-09-29

## 2. 检索：输入与输出

**输入**（`POST /api/projects/search`）

```json
{"uid": "…", "direction": "ai", "stage": 1, "keywords": "情感分类", "node": "评价"}
```

- `direction`：方向树的领域代码（ai / math / stat / psy / econ / se）。
- `stage`：走到哪。0 只学了概念 · 1 做过小任务 · 2 学完一块（走完一个分支或学过一门课）· 3 做过项目。默认由 `GET /api/projects/context` 按服务端记录推出（交过几次小任务、有没有评过的项目），界面上用户可以改。
- `keywords`、`node`：可选；关键词优先参与检索和排序。

**处理**

1. 取出方向对得上、阶段相差不超过一档的来源。
2. 有公开接口的来源实时检索（并发、单个 12 秒超时、结果缓存 6 小时）；失败或没有接口的，用该来源里已核对过的样例（界面标「快照」，保留原检索时间）。
3. 规则打分：方向对得上 +3，方向词命中每个 +0.6，关键词命中每个 +4，阶段对得上 +2、相差两档以上 −1.5，快照 −0.3；取前 24 条。
4. 连了模型：按 `skills/project-scout/SKILL.md` 从候选里最多挑 6 个，只依据原文写「在练什么 / 大概要做什么 / 为什么是现在」；返回的 id 不在候选里就丢掉。没连模型：取规则前 5 条，「大概要做什么」用来源原文。
5. 其余来源整理成「去哪找」路线（点哪里、搜什么），学生自己去看。

**输出**

```json
{
  "query": {"direction": "ai", "direction_name": "人工智能与机器学习", "stage": 1, "stage_label": "做过小任务", "keywords": "情感分类"},
  "items": [{
    "id": "…", "name": "项目名（来源原标题）", "url": "项目页链接",
    "source_name": "来源", "retrieved_at": "2026-09-30T…",
    "practices": "它在练什么", "todo": "大概要做什么", "why_fit": "为什么是现在",
    "difficulty": "来源标的难度", "deadline": "来源标的截止", "snapshot": false, "voice": "llm"
  }],
  "sources": [{"name": "…", "ok": true, "count": 8, "live": true}, {"name": "…", "ok": false, "error": "实时检索失败（连不上）"}],
  "routes": [{"name": "…", "url": "…", "manual_route": "点哪里、搜什么", "search_terms": ["…"]}],
  "empty_reason": "", "voice": "llm", "retrieved_at": "…"
}
```

查不到时 `items` 为空，`empty_reason` 如实说明，界面不补任何项目。`POST /api/projects/pick` 只接受最近一次检索结果里的 id。

## 3. 压缩包要求

只收一个 `.zip`（≤ 20 MB，解压后 ≤ 100 MB，≤ 300 个文件）。压缩包里至少要有：

| 必须 | 内容 |
| --- | --- |
| `README.md`（最外层） | `## 题目`（项目名 + 来源链接 + 用自己的话写要回答的问题）· `## 我做了什么` · `## 结果在哪`（每个结果文件一行：路径 + 说明了什么）· `## 怎么复现` · `## 还没做完的` |
| `results/` | 自己做出来的图、表、输出或报告，至少一个，且在 README 里被提到 |
| 代码类项目 | `src/` 或 `.ipynb`，README 写清运行命令 |
| 调查 / 写作类项目 | 数据来源链接、问卷或访谈提纲、方法步骤 |

界面上可以下载按项目生成的 README 模板和一份「示例成果.zip」。收取时只在内存里读，不解压到磁盘、不执行任何代码；Windows 压缩出来的中文文件名按 GBK 还原；`.docx` 和 `.ipynb` 读正文，PDF 和图片只记文件名并如实说明没读。

## 4. 评分标准

评的是「这份成果像不像这个项目要的东西」，不是评人。每条判「做到 / 部分做到 / 还没做到」，给出处（文件 + 原文）和「改哪里」。

| 标准 | 规则先查（上限） | 模型再判 |
| --- | --- | --- |
| 说清了要解决什么问题 | 有 README，有「题目 / 问题」段，长度 ≥ 80 字 | 是否写了项目名或来源、问题是不是自己的话 |
| 有自己做出来的结果 | 有非空的图 / 表 / 结果文件，且 README 提到了它们；提到了但不存在的文件会列出来 | 结果有没有说明各自说明了什么 |
| 和项目要求对得上 | 有 README 才可能判做到 | 逐条对照「大概要做什么」，写对上了哪几点、缺哪一点 |
| 别人能照着核对或复现 | 代码类：有代码且有「复现 / 运行」段；非代码类：有「方法」段和结果 | 说明是否真的够别人照做（例如代码是不是只有占位） |
| 说清了没做完的和下一步 | 有「局限 / 没做完 / 下一步」段 | 是否具体，不是一句「还有很多不足」 |

- 规则判定是上限：模型只能判得更低，不能更高；模型给的原文必须在文件里逐字找得到，否则丢掉。
- 评语最后只给一处「下一步」：第一条没做到的标准该改哪个文件、补什么。
- 每次提交写回一条行为事实：「交了项目《…》的成果：k/5 条做到」。

## 5. 跑通样例

2026-09-30 在本机实际跑过一遍（DeepSeek `deepseek-chat`）。复现：启动服务后在「项目」里选 经济 · 做过小任务 · 关键词「银行」。

**① 检索**：`{"direction": "econ", "stage": 1, "keywords": "银行"}` → 6 个项目，第一条：

```json
{
 "name": "【教学赛】金融数据分析赛题1：银行客户认购产品预测",
 "url": "https://tianchi.aliyun.com/competition/entrance/531993/introduction",
 "source_name": "阿里云天池 新人赛/教学赛",
 "practices": "清洗客户表格数据、做分类预测、看评价指标",
 "todo": "用赛题给的客户信息、联系记录和市场情况数据，预测客户是否认购银行产品，交一份预测结果和简单分析。已截止，当练习做。",
 "why_fit": "关键词银行对得上，学习赛难度适合做过小任务的学生",
 "deadline": "2026-03-31",
 "closed": true,
 "retrieved_at": "2026-09-29T20:19:45+00:00"
}
```

**② 交成果**：一份按第 3 节要求打包的示例压缩包（为演示而写，不是真实学生作业）：

```text
bank-subscribe/
  README.md            题目 / 我做了什么 / 结果在哪 / 怎么复现 / 还没做完的
  results/metrics.csv  两个模型的准确率、认购类精确率与召回率、AUC
  results/feature_top10.csv
  results/notes.md     三条观察
  src/baseline.py      逻辑回归基线
```

**③ 评阅**：4 / 5 条做到。一份结构完整的练习成果：README 说清问题、结果和复现方式，指标表与特征表齐全，还主动指出 duration 的信息泄漏问题。主要缺口是训练数据未随成果提交。

| 标准 | 判定 | 评语 | 出处 | 改哪里 |
| --- | --- | --- | --- | --- |
| 说清了要解决什么问题 | 做到 | 用自己的话写出了要回答的问题，还点出正例稀少不能只看准确率。 | `README.md`「我想回答：只用客户的基本信息和上一次联系记录，能不能比「全猜不认购」更好地找出会认购的客户？」 | — |
| 有自己做出来的结果 | 做到 | 有指标表和特征系数表，README 逐项说明各自说明了什么。 | `README.md`「results/metrics.csv：两个模型在验证集上的准确率、认购类精确率 / 召回率、AUC」 | — |
| 和项目要求对得上 | 做到 | 清洗、分类预测、评价指标三点都覆盖，还做了阈值规则对照。 | `README.md`「把 job、marital 等类别变量做 one-hot」 | — |
| 别人能照着核对或复现 | 部分做到 | 代码和运行命令都有，但 data/train.csv 未随成果提交，别人无法直接跑。 | `README.md`「数据从上面的天池页面下载（需登录），放到 data/train.csv」 | 在 README.md 的「怎么复现」里补上数据获取的具体步骤，或把 data/train.csv 一并提交。 |
| 说清了没做完的和下一步 | 做到 | 写清了泄漏嫌疑、未调参、未交平台，下一步也具体。 | `README.md`「「上一次联系时长」是打完电话才知道的，用它预测有信息泄漏的嫌疑」 | — |

**下一步**：先改「别人能照着核对或复现」：在 README.md 的「怎么复现」里补上数据获取的具体步骤，或把 data/train.csv 一并提交。

**写回画像**：「交了项目《【教学赛】金融数据分析赛题1：银行客户认购产品预测》的成果：4/5 条做到」（行为事实，置信度 0.8）。

同一项目下载的「示例成果.zip」（格式演示、内容是占位）评下来是 1 / 5：评阅指出它做的是 A/B 描述对比、和「预测是否认购」对不上。说明评分看的是成果和题目是否对得上，不是看格式齐不齐。

## 6. 代码和 skill 怎么分

见 [`skills/README.md`](../skills/README.md)：能确定的（检索、出处、时间、安全、文件是否存在）写成代码；要读懂和取舍的（挑哪个、对不对得上、评语）写进 `SKILL.md` 交给模型，代码校验它的输出。改 `SKILL.md` 不用重启服务。

## 7. 和任务 4 的方向路径怎么接

任务 4 把每个方向收成 6 步路径（`docs/paths/`）。「项目」页对有路径的方向改成「你在路径的哪一步」：六张卡片写着每一步的名称和「做完怎样算过了」，选中后按这一步找项目。

- 机读版：`knowledge/paths.json`，由 `knowledge/build_paths.py` 从 `docs/paths/*.md` 生成（只抄步骤名、先弄懂什么、做完怎样算过了），不要手改。甲补上 `认知.md` / `经济.md` 后跑一次 `uv run --no-project python knowledge/build_paths.py` 就接上；`server/tests` 里有一条测试会在文档和 json 不一致时失败。
- 检索：`POST /api/projects/search` 多一个可选字段 `path_step`（1–6）。有路径时以它为准换算项目阶段，步骤名当作「正在学的节点」，这一步的过关标准和 `改树建议.md` §5 的项目形态一起交给模型，优先挑「做完能直接交出这一步过关材料」的项目。没有路径的方向忽略它，仍按四个阶段。
- `GET /api/projects/context` 多返回 `paths` 和默认的 `path_step`（按记录推：只学了概念→第 1 步，做过小任务→第 2 步，学完一块→第 3 步，做过项目→第 5 步）。

| 路径 | 步骤 | 换算成项目阶段 |
| --- | --- | --- |
| 数学 | 第 1 步 · 把「显然」拆成步骤 | 只学了概念 |
| 数学 | 第 2 步 · 把极限说严格 | 做过小任务 |
| 数学 | 第 3 步 · 线性代数：矩阵是映射，不是表格 | 学完一块 |
| 数学 | 第 4 步 · 概率与统计：学会带着不确定性说话 | 学完一块 |
| 数学 | 第 5 步 · 读论文：把定义依赖画出来 | 做过项目 |
| 数学 | 第 6 步 · 做一个小问题：从「读懂」到「做出」 | 做过项目 |
| 人工智能与机器学习 | 第 1 步 · 先修：线代、概率、Python | 只学了概念 |
| 人工智能与机器学习 | 第 2 步 · 经典机器学习：先把「怎样算做对」学明白 | 做过小任务 |
| 人工智能与机器学习 | 第 3 步 · 深度学习：把训练变成可复现的实验 | 学完一块 |
| 人工智能与机器学习 | 第 4 步 · 读论文：从综述到经典 | 学完一块 |
| 人工智能与机器学习 | 第 5 步 · 复现实验：把别人的结果跑出来 | 做过项目 |
| 人工智能与机器学习 | 第 6 步 · 卡住的地方就是题目：做一次小研究 | 做过项目 |

实测（2026-10-01，DeepSeek）：人工智能第 2 步找到飞桨学习赛里的分类题，理由写「能交出基线加混淆矩阵」；第 5 步找到开源之夏、Gitee 上的复现和排查任务；数学第 1 步是欧拉计划前几题，第 6 步是数学建模往年赛题。
