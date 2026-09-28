import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import sharp from "sharp";
import PptxGenJS from "pptxgenjs";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  LuBan,
  LuBookOpen,
  LuCheck,
  LuClock,
  LuCompass,
  LuCpu,
  LuDatabase,
  LuGitBranch,
  LuLayers,
  LuLightbulb,
  LuMessageSquare,
  LuMonitor,
  LuPenLine,
  LuRefreshCw,
  LuSearch,
  LuServer,
  LuShieldCheck,
  LuSparkles,
  LuTriangleAlert,
  LuUserRound,
  LuUsers,
  LuWorkflow,
} from "react-icons/lu";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const iconDir = path.join(__dirname, "icons");
const outFile = path.join(__dirname, "..", "启研-阶段汇报.pptx");

const C = {
  ink: "14241F",
  teal: "0F6E64",
  tealDeep: "0C4F48",
  paper: "F6F3EC",
  card: "FFFCF8",
  line: "E4DCD0",
  muted: "5C6E67",
  coral: "C45C3E",
  gold: "8F6A24",
  white: "FFFFFF",
  deep: "10241F",
  deep2: "18332C",
  soft: "E7F3F0",
  coralSoft: "F8EBE6",
  goldSoft: "F8F1E4",
};

const FONT = "Microsoft YaHei";

const ICON_SET = {
  users: LuUsers,
  user: LuUserRound,
  search: LuSearch,
  pen: LuPenLine,
  bulb: LuLightbulb,
  monitor: LuMonitor,
  database: LuDatabase,
  cpu: LuCpu,
  shield: LuShieldCheck,
  workflow: LuWorkflow,
  server: LuServer,
  book: LuBookOpen,
  clock: LuClock,
  tree: LuGitBranch,
  refresh: LuRefreshCw,
  alert: LuTriangleAlert,
  spark: LuSparkles,
  check: LuCheck,
  layers: LuLayers,
  message: LuMessageSquare,
  compass: LuCompass,
  ban: LuBan,
};

async function raster(name, color) {
  const Icon = ICON_SET[name];
  let svg = renderToStaticMarkup(
    createElement(Icon, { size: 256, color, strokeWidth: 1.75 }),
  );
  svg = svg.replace(/currentColor/g, color);
  if (!svg.includes("xmlns=")) {
    svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ');
  }
  const file = path.join(iconDir, `${name}-${color.slice(1)}.png`);
  await sharp(Buffer.from(svg)).png().toFile(file);
  return file;
}

function icon(name, color) {
  return path.join(iconDir, `${name}-${color.slice(1)}.png`);
}

const pres = new PptxGenJS();
pres.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
pres.layout = "WIDE";
pres.author = "启研项目组";
pres.title = "启研 · 阶段汇报";
pres.subject = "2026-09-28 冲刺汇报";

function addPage(slide, n, total = 11) {
  slide.addText(`${String(n).padStart(2, "0")}  /  ${String(total).padStart(2, "0")}`, {
    x: 11.15,
    y: 7.12,
    w: 1.65,
    h: 0.24,
    fontFace: FONT,
    fontSize: 11,
    color: "8A948E",
    align: "right",
    margin: 0,
  });
}

function addKicker(slide, text) {
  slide.addText(text, {
    x: 0.55,
    y: 0.32,
    w: 10.2,
    h: 0.26,
    fontFace: FONT,
    fontSize: 12,
    color: C.teal,
    margin: 0,
  });
}

function addTitle(slide, text, y = 0.58) {
  slide.addText(text, {
    x: 0.55,
    y,
    w: 12.2,
    h: 0.48,
    fontFace: FONT,
    fontSize: 28,
    color: C.ink,
    bold: true,
    margin: 0,
  });
}

function card(slide, x, y, w, h, fill = C.card) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h,
    fill: { color: fill },
    line: { color: C.line, width: 1 },
    rectRadius: 0.08,
  });
}

async function main() {
  await mkdir(iconDir, { recursive: true });
  const colors = ["#0F6E64", "#F6F3EC", "#C45C3E", "#14241F", "#FFFFFF", "#8F6A24"];
  for (const name of Object.keys(ICON_SET)) {
    for (const color of colors) {
      await raster(name, color);
    }
  }

  cover();
  sprint();
  decisions();
  architecture();
  contract();
  localUi();
  truths();
  team();
  tracking();
  ai();
  close();

  await pres.writeFile({ fileName: outFile });
  console.log(outFile);
}

function cover() {
  const s = pres.addSlide();
  s.background = { color: C.deep };
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.85, y: 0, w: 4.483, h: 7.5,
    fill: { color: C.deep2 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 8.85, y: 0, w: 0.06, h: 7.5,
    fill: { color: C.teal },
  });

  s.addText("阶段汇报   ·   2026.09.28", {
    x: 0.62, y: 1.35, w: 7.6, h: 0.32,
    fontFace: FONT, fontSize: 14, color: "8FBFB6", margin: 0,
  });
  s.addText("启研", {
    x: 0.58, y: 1.78, w: 7.6, h: 1.05,
    fontFace: FONT, fontSize: 72, color: C.white, bold: true, margin: 0,
  });
  s.addText("面向大一大二。先认识这个人，再给他一件\n现在就做得完的事，做完还记得住。", {
    x: 0.62, y: 3.05, w: 7.4, h: 0.85,
    fontFace: FONT, fontSize: 18, color: "D5E4DE", margin: 0,
  });

  const metas = [
    ["06", "人"],
    ["01", "条闭环"],
    ["8100", "本机端口"],
  ];
  metas.forEach((m, i) => {
    const x = 0.62 + i * 2.35;
    s.addText(m[0], {
      x, y: 4.85, w: 2.1, h: 0.42,
      fontFace: FONT, fontSize: 22, color: C.white, bold: true, margin: 0,
    });
    s.addText(m[1], {
      x, y: 5.28, w: 2.1, h: 0.28,
      fontFace: FONT, fontSize: 13, color: "8FBFB6", margin: 0,
    });
  });

  s.addText("本机可演示。模型断了，规则还在。", {
    x: 0.62, y: 6.55, w: 7.4, h: 0.3,
    fontFace: FONT, fontSize: 13, color: "7E9A92", margin: 0,
  });

  const steps = [
    ["01", "认识你", "对话里抽出事实，人可以改"],
    ["02", "看方向", "六个领域，按当前画像建议"],
    ["03", "给下一步", "二十分钟能做完的一件事"],
    ["04", "陪做完", "提交后按条目说话"],
    ["05", "记住", "写回记录，再给下一次"],
  ];
  steps.forEach((st, i) => {
    const y = 0.72 + i * 1.22;
    s.addText(st[0], {
      x: 9.2, y, w: 0.7, h: 0.28,
      fontFace: FONT, fontSize: 12, color: "7DCFC3", margin: 0,
    });
    s.addText(st[1], {
      x: 9.95, y: y - 0.02, w: 2.9, h: 0.32,
      fontFace: FONT, fontSize: 18, color: C.white, bold: true, margin: 0,
    });
    s.addText(st[2], {
      x: 9.95, y: y + 0.34, w: 2.9, h: 0.4,
      fontFace: FONT, fontSize: 13, color: "B7C9C2", margin: 0,
    });
  });
}

function sprint() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "冲刺任务清单");
  addTitle(s, "这阶段只选一条走得完的链路");
  addPage(s, 2);

  const items = [
    ["01", "多画像进入", "昵称登录，画像可以有多份。\n每份各自记住方向和进度。"],
    ["02", "事实可核对", "几轮对话抽出背景和兴趣。\n确认之后能改，也能删。"],
    ["03", "方向按画像长", "六个领域，各长一棵树。\n建议按当前画像分开计算。"],
    ["04", "课程必须真实", "旁边检索北大公开课。\n没有结果就说明没有。"],
    ["05", "二十分钟任务", "只出当前节点上的题目。\n提交后按条目反馈，留在本页。"],
    ["06", "做完要记得住", "行为写进记录，刷新不回起点。\n换方向之前，要再确认一次。"],
  ];
  items.forEach((it, i) => {
    const col = i < 3 ? 0 : 1;
    const row = i % 3;
    const x = 0.55 + col * 4.55;
    const y = 1.35 + row * 1.82;
    card(s, x, y, 4.38, 1.68);
    s.addText(it[0], {
      x: x + 0.22, y: y + 0.2, w: 0.7, h: 0.28,
      fontFace: FONT, fontSize: 13, color: C.teal, bold: true, margin: 0,
    });
    s.addText("已接到本机", {
      x: x + 2.35, y: y + 0.2, w: 1.8, h: 0.28,
      fontFace: FONT, fontSize: 12, color: C.teal, align: "right", margin: 0,
    });
    s.addText(it[1], {
      x: x + 0.22, y: y + 0.56, w: 3.95, h: 0.34,
      fontFace: FONT, fontSize: 16, color: C.ink, bold: true, margin: 0,
    });
    s.addText(it[2], {
      x: x + 0.22, y: y + 0.96, w: 3.95, h: 0.58,
      fontFace: FONT, fontSize: 13, color: C.muted, margin: 0,
    });
  });

  card(s, 9.7, 1.35, 3.08, 5.46, C.deep);
  s.addImage({ path: icon("ban", "#F6F3EC"), x: 9.94, y: 1.58, w: 0.32, h: 0.32 });
  s.addText("这次不拿来冲", {
    x: 10.36, y: 1.58, w: 2.2, h: 0.32,
    fontFace: FONT, fontSize: 15, color: C.white, bold: true, margin: 0,
  });
  const skips = [
    "论文陪读",
    "课题组与竞赛",
    "注册和权限",
    "向量知识库",
    "拆成微服务",
    "离开开发机部署",
  ];
  skips.forEach((t, i) => {
    const y = 2.2 + i * 0.7;
    s.addText(t, {
      x: 9.98, y, w: 2.55, h: 0.5,
      fontFace: FONT, fontSize: 15, color: "E4EEEA", margin: 0,
    });
  });
}

function decisions() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "系统设计");
  addTitle(s, "先把边界定死，再让代码往里长");
  addPage(s, 3);

  const items = [
    ["server", "一个进程就够", "FastAPI 单体。校园演示的复杂度，不值得拆服务、上队列。"],
    ["database", "库先放在本机", "SQLite 存用户、事实、任务和提交。零运维，表按契约长。"],
    ["layers", "页面不经过构建", "静态页直接由服务托管。少一个会在现场坏掉的环节。"],
    ["cpu", "模型待在规则里面", "规则先圈定候选。模型只择优、改措辞。超时就退回规则。"],
    ["search", "搜课只读，失败可见", "独立技能查公开课。不登录教务。查不到就原样说查不到。"],
    ["workflow", "对话不自由发散", "显式状态机，轮数有限。能复现，也控得住调用成本。"],
  ];
  items.forEach((it, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = 0.55 + col * 4.2;
    const y = 1.4 + row * 2.7;
    card(s, x, y, 4.02, 2.5);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.22, y: y + 0.26, w: 0.52, h: 0.52,
      fill: { color: C.soft },
      rectRadius: 0.08,
    });
    s.addImage({ path: icon(it[0], "#0F6E64"), x: x + 0.32, y: y + 0.36, w: 0.32, h: 0.32 });
    s.addText(it[1], {
      x: x + 0.9, y: y + 0.32, w: 2.9, h: 0.42,
      fontFace: FONT, fontSize: 16, color: C.ink, bold: true, margin: 0,
    });
    s.addText(it[2], {
      x: x + 0.24, y: y + 1.08, w: 3.54, h: 1.1,
      fontFace: FONT, fontSize: 14, color: C.muted, margin: 0,
    });
  });
}

function architecture() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "软件体系结构");
  addTitle(s, "浏览器只展示，决定和记忆在一个进程里");
  addPage(s, 4);

  card(s, 0.55, 1.28, 12.23, 0.92, C.card);
  s.addImage({ path: icon("monitor", "#0F6E64"), x: 0.78, y: 1.56, w: 0.34, h: 0.34 });
  s.addText("浏览器", {
    x: 1.24, y: 1.42, w: 1.6, h: 0.32,
    fontFace: FONT, fontSize: 15, color: C.ink, bold: true, margin: 0,
  });
  s.addText("web/  ·  无构建", {
    x: 1.24, y: 1.74, w: 2.2, h: 0.26,
    fontFace: FONT, fontSize: 12, color: C.muted, margin: 0,
  });
  ["今日", "画像", "方向", "任务", "记录"].forEach((t, i) => {
    const x = 4.15 + i * 1.65;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 1.52, w: 1.48, h: 0.44,
      fill: { color: i === 0 ? C.teal : C.soft },
      rectRadius: 0.08,
    });
    s.addText(t, {
      x, y: 1.6, w: 1.48, h: 0.3,
      fontFace: FONT, fontSize: 13, color: i === 0 ? C.white : C.tealDeep,
      align: "center", bold: true, margin: 0,
    });
  });

  s.addShape(pres.shapes.DOWN_ARROW, {
    x: 6.48, y: 2.28, w: 0.28, h: 0.22,
    fill: { color: C.teal },
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.55, y: 2.58, w: 12.23, h: 2.15,
    fill: { color: C.deep },
    rectRadius: 0.08,
  });
  s.addImage({ path: icon("server", "#F6F3EC"), x: 0.78, y: 2.76, w: 0.28, h: 0.28 });
  s.addText("FastAPI   ·   server/", {
    x: 1.16, y: 2.74, w: 4, h: 0.32,
    fontFace: FONT, fontSize: 15, color: C.white, bold: true, margin: 0,
  });
  s.addText("REST 契约冻结。页面换了，端点签名不动。", {
    x: 5.3, y: 2.76, w: 7.1, h: 0.28,
    fontFace: FONT, fontSize: 13, color: "B7C9C2", align: "right", margin: 0,
  });

  const mods = [
    ["message", "对话状态机", "限轮抽取事实"],
    ["compass", "规划器", "先给出候选"],
    ["clock", "任务工作台", "出题、判、反馈"],
    ["user", "画像与事实", "可改、可删、可切换"],
  ];
  mods.forEach((m, i) => {
    const x = 0.78 + i * 3.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 3.28, w: 2.84, h: 1.2,
      fill: { color: "1C3832" },
      rectRadius: 0.08,
    });
    s.addImage({ path: icon(m[0], "#F6F3EC"), x: x + 0.16, y: 3.46, w: 0.28, h: 0.28 });
    s.addText(m[1], {
      x: x + 0.52, y: 3.44, w: 2.15, h: 0.32,
      fontFace: FONT, fontSize: 14, color: C.white, bold: true, margin: 0,
    });
    s.addText(m[2], {
      x: x + 0.16, y: 3.9, w: 2.52, h: 0.36,
      fontFace: FONT, fontSize: 13, color: "B7C9C2", margin: 0,
    });
  });

  s.addShape(pres.shapes.DOWN_ARROW, {
    x: 6.48, y: 4.82, w: 0.28, h: 0.2,
    fill: { color: C.teal },
  });

  const bottoms = [
    ["database", "SQLite", "事实、任务、提交\n同一张本机库"],
    ["cpu", "DeepSeek", "对话、理由、反馈\n失败则退回规则"],
    ["search", "pku-course", "子进程查公开课\n不登录、不改契约"],
  ];
  bottoms.forEach((b, i) => {
    const x = 0.55 + i * 4.15;
    card(s, x, 5.12, 3.98, 1.42);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.18, y: 5.36, w: 0.46, h: 0.46,
      fill: { color: C.soft },
      rectRadius: 0.08,
    });
    s.addImage({ path: icon(b[0], "#0F6E64"), x: x + 0.27, y: 5.45, w: 0.28, h: 0.28 });
    s.addText(b[1], {
      x: x + 0.78, y: 5.32, w: 2.95, h: 0.32,
      fontFace: FONT, fontSize: 15, color: C.ink, bold: true, margin: 0,
    });
    s.addText(b[2], {
      x: x + 0.78, y: 5.68, w: 2.95, h: 0.64,
      fontFace: FONT, fontSize: 13, color: C.muted, margin: 0,
    });
  });

  s.addText("学科名单在 knowledge/。这一阶段用关键词，不做向量库。", {
    x: 0.55, y: 6.68, w: 10.2, h: 0.28,
    fontFace: FONT, fontSize: 12, color: C.muted, margin: 0,
  });
}

function contract() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "系统设计");
  addTitle(s, "个性化必须能指回一句人话");
  addPage(s, 5);

  const cols = [
    ["user", "用户事实", "唯一的认知单元", [
      "背景、兴趣、能力、偏好、经历",
      "值是人可读的句子，不打分",
      "来源分声明、推断、行为",
      "没有证据，不允许写入",
    ]],
    ["compass", "下一步", "决策必须带理由", [
      "动作、标题、理由、备选",
      "理由至少引用一条事实",
      "规则先出候选，模型再措辞",
      "模型失败时，直接用规则第一名",
    ]],
    ["refresh", "写回", "做完的事要留下", [
      "提交生成一条行为事实",
      "旧事实可被取代，不悄悄改写",
      "人可以改、可以删",
      "刷新之后，记录还在",
    ]],
  ];
  cols.forEach((c, i) => {
    const x = 0.55 + i * 4.2;
    card(s, x, 1.35, 4.02, 4.55);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.22, y: 1.55, w: 0.5, h: 0.5,
      fill: { color: C.soft },
      rectRadius: 0.08,
    });
    s.addImage({ path: icon(c[0], "#0F6E64"), x: x + 0.33, y: 1.66, w: 0.28, h: 0.28 });
    s.addText(c[1], {
      x: x + 0.86, y: 1.52, w: 2.9, h: 0.32,
      fontFace: FONT, fontSize: 18, color: C.ink, bold: true, margin: 0,
    });
    s.addText(c[2], {
      x: x + 0.86, y: 1.86, w: 2.9, h: 0.26,
      fontFace: FONT, fontSize: 13, color: C.teal, margin: 0,
    });
    c[3].forEach((line, j) => {
      const y = 2.4 + j * 0.78;
      s.addText(String(j + 1).padStart(2, "0"), {
        x: x + 0.24, y, w: 0.46, h: 0.28,
        fontFace: FONT, fontSize: 12, color: C.teal, margin: 0,
      });
      s.addText(line, {
        x: x + 0.74, y: y - 0.02, w: 3.05, h: 0.55,
        fontFace: FONT, fontSize: 13, color: C.ink, margin: 0,
      });
    });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.55, y: 6.08, w: 12.23, h: 0.82,
    fill: { color: C.deep },
    rectRadius: 0.08,
  });
  const principles = ["行动大于信息", "个性化必须有依据", "不编造事实"];
  principles.forEach((p, i) => {
    s.addText(p, {
      x: 0.7 + i * 4.05, y: 6.3, w: 3.9, h: 0.4,
      fontFace: FONT, fontSize: 16, color: C.white, align: "center", bold: true, margin: 0,
    });
  });
}

function localUi() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "系统实现  ·  本机效果");
  addTitle(s, "打开 127.0.0.1:8100 之后");
  addPage(s, 6);

  card(s, 0.55, 1.32, 4.15, 5.45, C.deep);
  s.addText("进入之前", {
    x: 0.8, y: 1.52, w: 3.6, h: 0.3,
    fontFace: FONT, fontSize: 13, color: "7DCFC3", margin: 0,
  });
  s.addText("首页是黑底粒子", {
    x: 0.8, y: 1.88, w: 3.6, h: 0.7,
    fontFace: FONT, fontSize: 22, color: C.white, bold: true, margin: 0,
  });
  const home = [
    ["六屏顺着滚", "粒子勾出六步，从认识到记住。"],
    ["按钮在最后", "「立即开始体验」不放在第一屏。"],
    ["模型可现场接", "首页能填兼容接口。\n通了走 DeepSeek，不通仍能看。"],
  ];
  home.forEach((h, i) => {
    const y = 2.85 + i * 1.15;
    s.addText(h[0], {
      x: 0.8, y, w: 3.6, h: 0.32,
      fontFace: FONT, fontSize: 15, color: C.white, bold: true, margin: 0,
    });
    s.addText(h[1], {
      x: 0.8, y: y + 0.34, w: 3.55, h: 0.62,
      fontFace: FONT, fontSize: 13, color: "C5D5CE", margin: 0,
    });
  });

  const views = [
    ["今日", "进来就看到这一步，不等模型写完才显示。"],
    ["画像", "对话和核对都留在这里。可以新建、切换、删除。"],
    ["方向", "树从起点长出来。建议按当前画像分开，换方向要确认。"],
    ["任务", "只显示这棵树上的当前节点。提交后，反馈写在本页。"],
    ["记录", "它记住的事实在这里。刷新不会把进度退回树根。"],
  ];
  views.forEach((v, i) => {
    const y = 1.32 + i * 1.09;
    card(s, 4.9, y, 7.88, 1.0);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 5.08, y: y + 0.28, w: 1.15, h: 0.44,
      fill: { color: C.teal },
      rectRadius: 0.08,
    });
    s.addText(v[0], {
      x: 5.08, y: y + 0.35, w: 1.15, h: 0.3,
      fontFace: FONT, fontSize: 13, color: C.white, align: "center", bold: true, margin: 0,
    });
    s.addText(v[1], {
      x: 6.42, y: y + 0.28, w: 6.1, h: 0.48,
      fontFace: FONT, fontSize: 15, color: C.ink, margin: 0,
    });
  });
}

function truths() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "系统实现  ·  本机效果");
  addTitle(s, "三件事不能靠文案演出来");
  addPage(s, 7);

  const items = [
    ["search", "01", "课是查出来的", "方向旁的课来自北大教务公开接口。没查到就说明没有，不换成写死的课表。"],
    ["database", "02", "记得住是写进库的", "提交之后，记录里多一条行为事实，带着时间和这次提交。刷新页面还在。删掉也是软删，不是藏起来。"],
    ["cpu", "03", "模型断了，演示还在", "对话、方向理由和任务反馈走 DeepSeek。断了就退回规则，页面不白，链路还能走完。"],
  ];
  items.forEach((it, i) => {
    const y = 1.35 + i * 1.8;
    card(s, 0.55, y, 12.23, 1.66);
    s.addText(it[1], {
      x: 0.82, y: y + 0.28, w: 1.1, h: 0.46,
      fontFace: FONT, fontSize: 26, color: C.teal, bold: true, margin: 0,
    });
    s.addImage({ path: icon(it[0], "#0F6E64"), x: 2.05, y: y + 0.32, w: 0.34, h: 0.34 });
    s.addText(it[2], {
      x: 2.52, y: y + 0.28, w: 9.8, h: 0.42,
      fontFace: FONT, fontSize: 20, color: C.ink, bold: true, margin: 0,
    });
    s.addText(it[3], {
      x: 2.52, y: y + 0.82, w: 9.8, h: 0.6,
      fontFace: FONT, fontSize: 15, color: C.muted, margin: 0,
    });
  });
}

function team() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "团队");
  addTitle(s, "六个人，分成四件事");
  addPage(s, 8);

  s.addText("功能思考   ·   3 人", {
    x: 0.55, y: 1.22, w: 6, h: 0.28,
    fontFace: FONT, fontSize: 13, color: C.teal, margin: 0,
  });

  const thinkers = [
    ["邬程灿", "闭环怎么转", "画像怎么分，方向怎么建议。\n下一步只给一件现在能做的事。"],
    ["刘弘雅", "任务怎么闭环", "二十分钟里做什么、怎么判。\n做完的结果写回用户记录。"],
    ["张效端", "这阶段交什么", "演示停在本机。\n部署和持续集成划在界外。"],
  ];
  thinkers.forEach((t, i) => {
    const x = 0.55 + i * 4.2;
    card(s, x, 1.58, 4.02, 2.15);
    s.addImage({ path: icon("bulb", "#0F6E64"), x: x + 0.22, y: 1.78, w: 0.28, h: 0.28 });
    s.addText(t[0], {
      x: x + 0.58, y: 1.74, w: 3.2, h: 0.34,
      fontFace: FONT, fontSize: 16, color: C.ink, bold: true, margin: 0,
    });
    s.addText(t[1], {
      x: x + 0.22, y: 2.22, w: 3.58, h: 0.32,
      fontFace: FONT, fontSize: 14, color: C.teal, margin: 0,
    });
    s.addText(t[2], {
      x: x + 0.22, y: 2.62, w: 3.58, h: 0.8,
      fontFace: FONT, fontSize: 14, color: C.muted, margin: 0,
    });
  });

  const makers = [
    ["monitor", "搓 Demo", "别克扎提·拜别提", "登录、对话、方向、任务、写回，\n接成一条本机能跑的链路。"],
    ["search", "爬课程", "陈浩文", "公开课检索接进方向。\n查不到就明说，技能契约不改。"],
    ["pen", "优化前端", "陈旭", "五个工作区换掉原来的步骤条。\n首页和方向树收到能演示。"],
  ];
  makers.forEach((m, i) => {
    const x = 0.55 + i * 4.2;
    card(s, x, 3.95, 4.02, 2.55);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.22, y: 4.16, w: 0.48, h: 0.48,
      fill: { color: C.soft },
      rectRadius: 0.08,
    });
    s.addImage({ path: icon(m[0], "#0F6E64"), x: x + 0.32, y: 4.26, w: 0.28, h: 0.28 });
    s.addText(m[1], {
      x: x + 0.84, y: 4.16, w: 2.95, h: 0.26,
      fontFace: FONT, fontSize: 12, color: C.teal, margin: 0,
    });
    s.addText(m[2], {
      x: x + 0.84, y: 4.4, w: 2.95, h: 0.32,
      fontFace: FONT, fontSize: 16, color: C.ink, bold: true, margin: 0,
    });
    s.addText(m[3], {
      x: x + 0.22, y: 4.95, w: 3.58, h: 1.2,
      fontFace: FONT, fontSize: 14, color: C.muted, margin: 0,
    });
  });
}

function tracking() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "团队追踪");
  addTitle(s, "五天收到本机，部署留在下一步");
  addPage(s, 9);

  s.addShape(pres.shapes.RECTANGLE, {
    x: 1.54, y: 1.58, w: 9.8, h: 0.035,
    fill: { color: "C9D5CF" },
  });
  const days = [
    ["9/24", "契约"],
    ["9/25", "链路"],
    ["9/26", "模型"],
    ["9/27", "界面"],
    ["9/28", "收口"],
  ];
  days.forEach((d, i) => {
    const x = 0.85 + i * 2.45;
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.55, y: 1.46, w: 0.28, h: 0.28,
      fill: { color: i === 4 ? C.teal : C.deep },
    });
    s.addText(d[0], {
      x, y: 1.84, w: 1.4, h: 0.26,
      fontFace: FONT, fontSize: 13, color: C.ink, align: "center", bold: true, margin: 0,
    });
    s.addText(d[1], {
      x, y: 2.08, w: 1.4, h: 0.24,
      fontFace: FONT, fontSize: 12, color: C.muted, align: "center", margin: 0,
    });
  });

  const rows = [
    ["闭环、画像、下一步", "已接到本机", "邬程灿", true],
    ["微任务与反馈写回", "已接到本机", "刘弘雅", true],
    ["全链路 Demo", "8100 可打开", "别克扎提·拜别提", true],
    ["公开课检索", "已接，失败可见", "陈浩文", true],
    ["五个工作区", "已换掉步骤条", "陈旭", true],
    ["离开本机的部署", "这次没做", "张效端", false],
  ];
  rows.forEach((r, i) => {
    const y = 2.55 + i * 0.7;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.55, y, w: 12.23, h: 0.62,
      fill: { color: i % 2 === 0 ? C.card : "F3EFE6" },
      rectRadius: 0.06,
    });
    s.addText(r[0], {
      x: 0.78, y: y + 0.14, w: 4.3, h: 0.34,
      fontFace: FONT, fontSize: 15, color: C.ink, margin: 0,
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 5.3, y: y + 0.13, w: 2.55, h: 0.36,
      fill: { color: r[3] ? C.soft : C.coralSoft },
      rectRadius: 0.06,
    });
    s.addText(r[1], {
      x: 5.3, y: y + 0.17, w: 2.55, h: 0.28,
      fontFace: FONT, fontSize: 12, color: r[3] ? C.tealDeep : C.coral,
      align: "center", bold: true, margin: 0,
    });
    s.addText(r[2], {
      x: 8.15, y: y + 0.14, w: 4.3, h: 0.34,
      fontFace: FONT, fontSize: 15, color: C.ink, margin: 0,
    });
  });
}

function ai() {
  const s = pres.addSlide();
  s.background = { color: C.paper };
  addKicker(s, "AI 辅助开发");
  addTitle(s, "它加快了试错，也放大了没跑过的判断");
  addPage(s, 10);

  card(s, 0.55, 1.32, 6.0, 5.15);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.75, y: 1.52, w: 0.42, h: 0.42,
    fill: { color: C.soft },
    rectRadius: 0.08,
  });
  s.addImage({ path: icon("spark", "#0F6E64"), x: 0.82, y: 1.59, w: 0.28, h: 0.28 });
  s.addText("帮上的", {
    x: 1.3, y: 1.56, w: 4.8, h: 0.36,
    fontFace: FONT, fontSize: 18, color: C.ink, bold: true, margin: 0,
  });
  const pros = [
    ["契约没有被改散", "生成跟着已冻结的端点和字段走，没有各写一套接口。"],
    ["界面试得很快", "工作区、方向树、首页粒子，都是短周期改出来再留下的。"],
    ["下一次接得上", "改动写进变更日志。新会话先读日志，不靠聊天记录。"],
    ["退路被留住", "模型失败时规则路径还在，演示不会卡在白屏上。"],
  ];
  pros.forEach((p, i) => {
    const y = 2.18 + i * 1.02;
    s.addText(p[0], {
      x: 0.82, y, w: 5.45, h: 0.3,
      fontFace: FONT, fontSize: 15, color: C.ink, bold: true, margin: 0,
    });
    s.addText(p[1], {
      x: 0.82, y: y + 0.32, w: 5.45, h: 0.52,
      fontFace: FONT, fontSize: 13, color: C.muted, margin: 0,
    });
  });

  card(s, 6.75, 1.32, 6.02, 5.15);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 6.95, y: 1.52, w: 0.42, h: 0.42,
    fill: { color: C.coralSoft },
    rectRadius: 0.08,
  });
  s.addImage({ path: icon("alert", "#C45C3E"), x: 7.02, y: 1.59, w: 0.28, h: 0.28 });
  s.addText("帮倒的", {
    x: 7.5, y: 1.56, w: 4.9, h: 0.36,
    fontFace: FONT, fontSize: 18, color: C.ink, bold: true, margin: 0,
  });
  const cons = [
    ["多出来的说明", "会主动加文案、入口，和这次没人要的区块。"],
    ["视觉不自己收敛", "首页粒子改了很多轮，才停在黑底和慢回的波纹。"],
    ["不打开就说完成", "刷新丢进度、换方向跳进任务，都是点开页面才发现。"],
    ["一次动太多文件", "旧问题会在下一版回来，不能只看最新一句回复。"],
  ];
  cons.forEach((p, i) => {
    const y = 2.18 + i * 1.02;
    s.addText(p[0], {
      x: 7.02, y, w: 5.45, h: 0.3,
      fontFace: FONT, fontSize: 15, color: C.ink, bold: true, margin: 0,
    });
    s.addText(p[1], {
      x: 7.02, y: y + 0.32, w: 5.45, h: 0.52,
      fontFace: FONT, fontSize: 13, color: C.muted, margin: 0,
    });
  });
}

function close() {
  const s = pres.addSlide();
  s.background = { color: C.deep };
  s.addText("这一阶段交出去的", {
    x: 0.7, y: 1.35, w: 11, h: 0.36,
    fontFace: FONT, fontSize: 16, color: "8FBFB6", margin: 0,
  });
  s.addText("不是另一个问答框。", {
    x: 0.7, y: 1.9, w: 12, h: 0.7,
    fontFace: FONT, fontSize: 36, color: C.white, bold: true, margin: 0,
  });
  s.addText("是本机上走得完的一条闭环。", {
    x: 0.7, y: 2.65, w: 12, h: 0.7,
    fontFace: FONT, fontSize: 36, color: "E7F3F0", bold: true, margin: 0,
  });

  const next = [
    ["01", "任务再做厚", "每个方向的层级拉开，不停在第一道题。"],
    ["02", "演示离开开发机", "一条命令能在另一台机器上打开。"],
    ["03", "调用留下日志", "模型用了哪一版、花了多久，事后查得到。"],
  ];
  next.forEach((n, i) => {
    const x = 0.7 + i * 4.1;
    s.addText(n[0], {
      x, y: 4.15, w: 3.7, h: 0.28,
      fontFace: FONT, fontSize: 13, color: "7DCFC3", margin: 0,
    });
    s.addText(n[1], {
      x, y: 4.48, w: 3.7, h: 0.36,
      fontFace: FONT, fontSize: 18, color: C.white, bold: true, margin: 0,
    });
    s.addText(n[2], {
      x, y: 4.95, w: 3.7, h: 0.7,
      fontFace: FONT, fontSize: 14, color: "C5D5CE", margin: 0,
    });
  });

  s.addText("启研   ·   2026.09.28", {
    x: 0.7, y: 6.55, w: 8, h: 0.3,
    fontFace: FONT, fontSize: 14, color: "7E9A92", margin: 0,
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
