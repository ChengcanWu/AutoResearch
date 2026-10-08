/* 启研 · W0 Demo 前端（无构建、经典脚本；设计规范 docs/DESIGN_SPEC.md）*/
"use strict";

/* ---------- 状态 ---------- */

const S = {
  uid: localStorage.getItem("rg_uid") || "",
  nickname: localStorage.getItem("rg_nick") || "",
  view: "home",
  resume: "login",
  onboard: { facts: [], messages: [] },
  lastTask: null,
  lastFeedback: null,
  newFactIds: [],
  portraitTab: "onboarding",
};

const $app = document.getElementById("app");
const $nav = document.getElementById("mainNav");
const $header = document.getElementById("headerRight");

/* ---------- API ---------- */

async function api(method, path, body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const res = await fetch(path, opt);
  let data = null;
  try { data = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) throw new Error((data && data.detail) || `请求失败 (${res.status})`);
  return data;
}

/* ---------- 工具 ---------- */

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(msg, ms = 2600) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const t = el("div", "toast", esc(msg));
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
/* 异步视图等待时的骨架占位：数据到了整块替换，避免白屏或旧页停流 */
function skeleton(rows = 2) {
  const box = el("div", "ws-skeleton");
  box.setAttribute("aria-hidden", "true");
  for (let i = 0; i < rows; i++) box.appendChild(el("div", "sk-block"));
  return box;
}
const CAT_CN = { background: "背景", interest: "兴趣", capability: "能力", preference: "偏好", experience: "经历" };
const SRC_CN = { declared: "自述", inferred: "推断", behavior: "行为" };

const WORKSPACE = {
  today: "today",
  onboarding: "portrait",
  confirm: "portrait",
  cards: "cards",
  workbench: "workbench",
  projects: "projects",
  project: "projects",
  me: "me",
};

/* ---------- 视图切换 ---------- */

function setView(name) {
  S.view = name;
  if (name === "onboarding" || name === "confirm") S.portraitTab = name;
  document.body.dataset.view = name;
  const home = name === "home";
  const inApp = !home && name !== "login" && !!S.uid;
  document.body.classList.toggle("is-home", home);
  document.body.classList.toggle("app-mode", inApp);
  if (!home && stopField) { stopField(); stopField = null; }
  if (name !== "cards") document.getElementById("nodeSheet")?.remove();
  document.querySelectorAll(".nav-btn").forEach((b) => {
    const on = b.dataset.workspace === WORKSPACE[name];
    b.classList.toggle("active", on);
    if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    b.disabled = !S.uid;
  });
  $nav.hidden = !inApp;
  $header.hidden = !inApp;
  render();
  window.scrollTo({ top: 0 });
}

/* 每次切换视图都有一个序号。异步渲染在每个 await 之后用 stale(seq) 检查：
   用户已经切走了，就不再往页面上写，避免两个视图叠在一起。 */
function stale(seq) {
  return seq !== S.renderSeq;
}

async function render() {
  S.renderSeq = (S.renderSeq || 0) + 1;
  if (S.view === "home") { renderHome(); return; }
  if (!S.uid && S.view !== "login") { renderLogin(); return; }
  switch (S.view) {
    case "login": renderLogin(); break;
    case "onboarding": renderOnboarding(); break;
    case "confirm": await renderConfirm(); break;
    case "cards": await renderCards(); break;
    case "workbench": await renderWorkbench(); break;
    case "projects": await renderProjects(); break;
    case "project": await renderProject(); break;
    case "me": await renderMe(); break;
    case "today":
    default: await renderToday(); break;
  }
}

/* ---------- 首页：六屏下滑，点线图随滚动重画 ---------- */

const HOME_PAGES = [
  {
    kicker: "启研 · AI RESEARCH MENTOR",
    title: "先认识你，<br>再走下一步。",
    lead: "面向本科一、二年级。它不是问答框，而是一条可以回头看的科研入门。",
  },
  {
    kicker: "01",
    title: "问答画像",
    lead: "几轮对话，勾出你现在的位置、基础和好奇。它只记你自己说的，不替你编一段人设。",
    points: [
      ["位置", "年级、专业，或者你现在停在哪一步。"],
      ["基础", "已经会的，和明确还没碰过的。"],
      ["好奇", "想试的问题。说不清也可以选「不知道」，它会如实记下。"],
    ],
  },
  {
    kicker: "02",
    title: "方向推荐",
    lead: "直接给出此刻值得试的方向。每条都要能对上你刚说过的话，不拿通用介绍来凑。",
    points: [
      ["为什么是你", "理由引用你的原话，至少对上位置、基础或好奇中的一件。"],
      ["真实课程", "从北大教务公开课里找。找不到就说找不到，不编课名和老师。"],
      ["入门读物", "先给读得动的那一篇，用来上手，不是一份书单。"],
    ],
  },
  {
    kicker: "03",
    title: "小任务",
    lead: "方向先不展开成阅读清单。它只给你一件二十分钟内能做完的事。",
    points: [
      ["做完", "读一小节、跑一个小例子，或回答一个具体问题。"],
      ["留下", "一段话、一张图或一个输出。结果要能被看见。"],
      ["记下", "实际做了什么，写回你的画像。"],
    ],
  },
  {
    kicker: "04",
    title: "获取反馈",
    lead: "按事先说好的标准逐条看你的提交。评价的是这件事做成了没有，不是你这个人。",
    points: [
      ["对事", "只看这一次交上来的内容，不推测你的潜力。"],
      ["标准", "做到哪条、缺哪条，分开写，并指出下一步改哪里。"],
      ["证据", "没有结果，就明确说缺证据。"],
    ],
  },
  {
    kicker: "05",
    title: "持续成长",
    lead: "记住这次证据，再决定下一件最值得做的事。下一步仍然只是一件事，不是一份新计划。",
    points: [
      ["认识", "你说过的位置、基础和好奇还在，不用每次从头介绍。"],
      ["记住", "反馈写回画像，下一次先看这些证据再开口。"],
      ["再下一步", "只给一件最值得做的事。做完，再进入下一轮。"],
    ],
    closing: "五步走完一圈，每一步它都记得。",
  },
];

let stopField = null;

function renderHome() {
  if (stopField) stopField();
  $app.innerHTML = "";
  const land = el("div", "land");
  const canvas = el("canvas", "land-field");
  canvas.setAttribute("aria-hidden", "true");
  const snap = el("div", "land-snap");
  HOME_PAGES.forEach((page, i) => {
    const sec = el("section", "snap");
    sec.dataset.index = String(i);
    const points = (page.points || [])
      .map(([k, v], j) => `<li style="--i:${j}"><b>${k}</b><span>${v}</span></li>`).join("");
    // snap-inner 钉在视口固定高度（sticky），不随滚动上下移动；显隐由 JS 按相位渐变
    sec.innerHTML = `<div class="snap-inner">`
      + (i === 0 ? `<p class="hero-kicker">${page.kicker}</p>` : `<p class="snap-no">${page.kicker}</p>`)
      + `<h2>${page.title}</h2>`
      + `<p class="land-lead">${page.lead}</p>`
      + (points ? `<ul class="land-points">${points}</ul>` : "")
      + (page.closing ? `<p class="land-closing">${page.closing}</p>` : "")
      + `</div>`;
    if (i === HOME_PAGES.length - 1) {
      const btn = el("button", "btn land-cta", "立即开始体验");
      btn.type = "button";
      btn.onclick = beginExperience;
      sec.querySelector(".snap-inner").appendChild(btn);
    }
    snap.appendChild(sec);
  });
  const hintEl = el("div", "land-hint");
  hintEl.setAttribute("aria-hidden", "true");
  hintEl.append(el("span", "", "滚动以继续"), el("i"));
  const skip = el("button", "land-skip", "跳过，直接开始");
  skip.type = "button";
  skip.onclick = beginExperience;
  land.append(canvas, buildSteps(), hintEl, skip, snap);
  $app.appendChild(land);
  stopField = mountSketch(canvas, snap);
}

/* 左缘纵向进度：当前步号随屏换（染主题色）、轨道随滚动生长、底部标总步数；序号从 00 计 */
function buildSteps() {
  const box = el("div", "land-steps");
  box.setAttribute("aria-hidden", "true");
  const cur = el("b", "", "00");
  const track = el("i", "land-steps-track");
  track.appendChild(el("i"));
  const total = el("span", "", `/ ${String(HOME_PAGES.length - 1).padStart(2, "0")}`);
  box.append(cur, track, total);
  return box;
}

function beginExperience() {
  if (stopField) stopField();
  if (S.uid) {
    document.getElementById("userNickname").textContent = S.nickname || "";
    setView("today");
    return;
  }
  setView("login");
}

/* 图形：[-1, 1] 坐标系，y 向下。每张图是若干笔画（折线），accent 笔画用主色。
   粒子按笔画顺序均匀排布，换图时第 i 颗粒子从旧图第 i 个位置走到新图第 i 个位置，
   看起来像一支笔把旧图擦掉、再把新图画出来。 */

function unitHash(i, salt) {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function arcPts(cx, cy, r, a0, a1, n = 48) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const a = a0 + (a1 - a0) * (i / n);
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  return pts;
}

function ring(cx, cy, r, n = 72) {
  return arcPts(cx, cy, r, 0, Math.PI * 2, n);
}

function curve(a, b, bend = 0.5) {
  const pts = [];
  const mx = a[0] + (b[0] - a[0]) * bend;
  for (let i = 0; i <= 24; i++) {
    const t = i / 24;
    const u = 1 - t;
    pts.push([
      u * u * u * a[0] + 3 * u * u * t * mx + 3 * u * t * t * mx + t * t * t * b[0],
      u * u * u * a[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t * t * t * b[1],
    ]);
  }
  return pts;
}

function rrect(x0, y0, x1, y1, r) {
  const pts = [];
  [[x1 - r, y0 + r, -Math.PI / 2, 0], [x1 - r, y1 - r, 0, Math.PI / 2],
    [x0 + r, y1 - r, Math.PI / 2, Math.PI], [x0 + r, y0 + r, Math.PI, Math.PI * 1.5]]
    .forEach(([cx, cy, a0, a1]) => arcPts(cx, cy, r, a0, a1, 8).forEach((p) => pts.push(p)));
  pts.push(pts[0]);
  return pts;
}

function bubble(x0, y0, x1, y1, r, tx, dir) {
  // 圆角气泡，尾巴开在底边 tx 处，dir = -1 朝左下，1 朝右下
  const pts = [];
  const corner = (cx, cy, a0, a1) => arcPts(cx, cy, r, a0, a1, 8).forEach((p) => pts.push(p));
  corner(x0 + r, y0 + r, Math.PI, Math.PI * 1.5);
  corner(x1 - r, y0 + r, -Math.PI / 2, 0);
  corner(x1 - r, y1 - r, 0, Math.PI / 2);
  pts.push([tx + 0.1, y1], [tx + dir * 0.12 + (dir > 0 ? 0.1 : 0), y1 + 0.16], [tx - 0.02, y1]);
  corner(x0 + r, y1 - r, Math.PI / 2, Math.PI);
  pts.push(pts[0]);
  return pts;
}

const SKETCHES = [
  // 00 台阶通向一扇门：先认识你，再走下一步（白门框不动，绿门板绕左铰链带透视向里推开；
  //     门内地板两条透视线收向消失点，门开了才渐显——走进去的路）
  () => {
    const door = [[0.22, 0.12], [0.22, -0.46], ...arcPts(0.5, -0.46, 0.28, Math.PI, Math.PI * 2, 32), [0.78, 0.12]];
    const inner = [[0.3, 0.12], [0.3, -0.44], ...arcPts(0.5, -0.44, 0.2, Math.PI, Math.PI * 2, 28), [0.7, 0.12]];
    const stairs = [[-0.95, 0.74], [-0.62, 0.74], [-0.62, 0.53], [-0.3, 0.53], [-0.3, 0.32], [0.02, 0.32], [0.02, 0.12], [0.95, 0.12]];
    const pathL = [[0.3, 0.12], [0.385, -0.05]];
    const pathR = [[0.7, 0.12], [0.615, -0.05]];
    return [
      { pts: stairs },
      { pts: door },
      { pts: inner, accent: true, part: "door" },
      { pts: ring(-0.46, 0.38, 0.05, 20), accent: true },
      { pts: pathL, accent: true, part: "path" },
      { pts: pathR, accent: true, part: "path" },
    ];
  },
  // 01 一问一答的两个气泡（问号绕自己的底部轻微摆动）
  () => {
    const q = [...arcPts(-0.36, -0.5, 0.1, Math.PI * 1.05, Math.PI * 2.25, 28), [-0.36, -0.33], [-0.36, -0.28]];
    return [
      { pts: bubble(-0.92, -0.78, 0.18, -0.12, 0.12, -0.62, -1) },
      { pts: q, accent: true, part: "q" },
      { pts: ring(-0.36, -0.2, 0.018, 8), accent: true, part: "q" },
      { pts: bubble(-0.18, 0.06, 0.92, 0.62, 0.12, 0.56, 1) },
      { pts: [[0.0, 0.22], [0.72, 0.22]] },
      { pts: [[0.0, 0.34], [0.6, 0.34]] },
      { pts: [[0.0, 0.46], [0.38, 0.46]] },
    ];
  },
  // 02 罗盘：指针指向一个方向（指针绕盘心来回摆动）
  () => {
    const out = [{ pts: ring(0, 0.04, 0.74, 96) }];
    for (let k = 0; k < 8; k++) {
      const a = (k / 8) * Math.PI * 2 - Math.PI / 2;
      const r0 = k % 2 === 0 ? 0.6 : 0.66;
      out.push({ pts: [[Math.cos(a) * r0, 0.04 + Math.sin(a) * r0], [Math.cos(a) * 0.74, 0.04 + Math.sin(a) * 0.74]] });
    }
    const a = -Math.PI / 4;
    const tip = (ang, r) => [Math.cos(ang) * r, 0.04 + Math.sin(ang) * r];
    const n = tip(a, 0.52);
    const s = tip(a + Math.PI, 0.52);
    const l = tip(a - Math.PI / 2, 0.1);
    const rr = tip(a + Math.PI / 2, 0.1);
    out.push({ pts: [l, n, rr], accent: true, part: "needle" });
    out.push({ pts: [l, s, rr], part: "needle" });
    out.push({ pts: ring(0, 0.04, 0.035, 12) });
    out.push({ pts: [[-0.05, -0.8], [-0.05, -0.96], [0.05, -0.8], [0.05, -0.96]] });
    return out;
  },
  // 03 秒表：二十分钟（指针转回 12 点方向）
  () => {
    const c = [0, 0.14];
    const out = [
      { pts: ring(c[0], c[1], 0.66, 96) },
      { pts: [[0, -0.52], [0, -0.62]] },
      { pts: rrect(-0.11, -0.76, 0.11, -0.62, 0.03) },
      { pts: [[0.47, -0.36], [0.55, -0.44]] },
    ];
    for (let k = 0; k < 12; k++) {
      const a = (k / 12) * Math.PI * 2 - Math.PI / 2;
      const r0 = k % 3 === 0 ? 0.5 : 0.56;
      out.push({ pts: [[c[0] + Math.cos(a) * r0, c[1] + Math.sin(a) * r0], [c[0] + Math.cos(a) * 0.62, c[1] + Math.sin(a) * 0.62]] });
    }
    out.push({ pts: arcPts(c[0], c[1], 0.4, -Math.PI / 2, Math.PI * 1.5 - 0.02, 120), accent: true, part: "arc" });
    out.push({ pts: [c, [c[0] + Math.cos(Math.PI / 6) * 0.44, c[1] + Math.sin(Math.PI / 6) * 0.44]], accent: true, part: "hand" });
    out.push({ pts: ring(c[0], c[1], 0.03, 12) });
    return out;
  },
  // 04 一页提交，逐条打勾（第三条的待办圈滚动时变成对勾、换成主题色）
  () => {
    const page = [[-0.58, -0.8], [0.2, -0.8], [0.44, -0.56], [0.44, 0.8], [-0.58, 0.8], [-0.58, -0.8]];
    const out = [{ pts: page }, { pts: [[0.2, -0.8], [0.2, -0.56], [0.44, -0.56]] }];
    [-0.3, 0.02, 0.34].forEach((y, i) => {
      if (i < 2) out.push({ pts: [[-0.42, y], [-0.35, y + 0.07], [-0.22, y - 0.08]], accent: true });
      else out.push({ pts: ring(-0.33, y, 0.06, 20), part: "todo" });
      out.push({ pts: [[-0.1, y], [0.28, y]] });
    });
    out.push({ pts: [[-0.42, 0.6], [0.1, 0.6]] });
    return out;
  },
  // 05 一棵往右长的树，走过的路用主色（R→A→A2→C2 四个节点依次点亮）
  () => {
    const R = [-0.82, 0.06];
    const A = [-0.3, -0.38];
    const B = [-0.3, 0.5];
    const A1 = [0.24, -0.64];
    const A2 = [0.24, -0.12];
    const B1 = [0.24, 0.34];
    const B2 = [0.24, 0.74];
    const C1 = [0.8, -0.34];
    const C2 = [0.8, 0.1];
    const node = (p, r, accent) => ({ pts: ring(p[0], p[1], r, 24), accent });
    const edge = (a, b, accent) => ({ pts: curve([a[0] + 0.06, a[1]], [b[0] - 0.06, b[1]]), accent });
    const arr = [
      node(R, 0.06, true), edge(R, A, true), node(A, 0.055, true), edge(A, A2, true), node(A2, 0.055, true),
      edge(A2, C2, true), node(C2, 0.05, true),
      edge(A, A1), node(A1, 0.05), edge(A2, C1), node(C1, 0.05),
      edge(R, B), node(B, 0.055), edge(B, B1), node(B1, 0.05), edge(B, B2), node(B2, 0.05),
    ];
    arr[0].part = "n0"; arr[2].part = "n1"; arr[4].part = "n2"; arr[6].part = "n3";
    return arr;
  },
];

/* 每屏主题色（参考彩色 WebGL 粒子站）：强调笔画、图形后柔光、背景微染、文字点缀共用，
   随滚动相位在相邻两色间连续过渡 */
const TONES = [
  [127, 209, 194], // 00 起点 · 青
  [143, 189, 246], // 01 画像 · 蓝
  [195, 174, 245], // 02 方向 · 紫
  [242, 205, 126], // 03 任务 · 金
  [242, 160, 138], // 04 反馈 · 珊瑚
  [164, 222, 138], // 05 成长 · 绿
];

/* 每图的聚形后动画：聚形完成、文字出完，随本屏向下滚动推进（act 0→1，scrub 可逆）。
   persp = 门板绕竖轴向里推的透视旋转；sweep = 弧线随指针扫过逐渐显出；fill = 点亮时填实心 */
const FIG_ANIMS = [
  // 00 绿门板绕自身左铰链向里推开 78°：远端向铰链收拢、向门高中线收缩（白门框不动）；
  //    门内地板两条透视线（收向消失点）随开门渐显——走进去的路
  { parts: {
    door: { persp: { hinge: [0.3, 0.12], w: 0.4, yc: -0.26, pf: 1.4, ang: (act) => 1.36 * (1 - Math.pow(1 - act, 3)) } },
    path: { reveal: (act) => 1 - Math.pow(1 - act, 2) },
  } },
  { parts: { q: { pivot: [-0.36, -0.28], ang: (act, tm) => Math.sin(tm * 2.2) * 0.14 * (0.15 + 0.85 * act) } } },
  // 02 指北针：以正北为中心，在相邻的两个刻度（东北—西北）之间来回摆
  { parts: { needle: { pivot: [0, 0.04], ang: (act, tm) => -Math.PI / 4 + (Math.PI / 4) * (0.15 + 0.85 * act) * Math.sin(tm * 1.6) } } },
  // 03 时针顺时针转 240° 回到 12 点；金色进度弧从 12 点起随时针扫过的位置延长
  { parts: {
    hand: { pivot: [0, 0.14], ang: (act) => 4.19 * (1 - Math.pow(1 - act, 3)) },
    arc: { pivot: [0, 0.14], sweep: { from: -Math.PI / 2, base: 2.09, span: 4.19 } },
  } },
  { parts: { todo: { morphTo: [[-0.42, 0.34], [-0.35, 0.41], [-0.22, 0.26]] } } },
  // 05 四个节点依次点亮：环内填成实心并发光
  { parts: {
    n0: { light: 0, fill: [-0.82, 0.06, 0.06] },
    n1: { light: 1, fill: [-0.3, -0.38, 0.055] },
    n2: { light: 2, fill: [0.24, -0.12, 0.055] },
    n3: { light: 3, fill: [0.8, 0.1, 0.05] },
  } },
];

function strokeLength(pts) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return L;
}

function sampleSketch(strokes, n) {
  // 沿全部笔画等距取 n 个点；返回 {xy, acc, sid}，顺序即笔画顺序；sid 记粒子属于哪一笔（供图形动画分组）
  const lens = strokes.map((s) => strokeLength(s.pts));
  const total = lens.reduce((a, b) => a + b, 0) || 1;
  const xy = new Float32Array(n * 2);
  const acc = new Uint8Array(n);
  const sid = new Uint16Array(n);
  let k = 0;
  strokes.forEach((s, si) => {
    const want = si === strokes.length - 1 ? n - k : Math.max(2, Math.round((lens[si] / total) * n));
    const count = Math.min(want, n - k);
    let seg = 1;
    let walked = 0;
    for (let j = 0; j < count; j++) {
      const d = count === 1 ? 0 : (j / (count - 1)) * lens[si];
      while (seg < s.pts.length - 1 && walked + Math.hypot(s.pts[seg][0] - s.pts[seg - 1][0], s.pts[seg][1] - s.pts[seg - 1][1]) < d) {
        walked += Math.hypot(s.pts[seg][0] - s.pts[seg - 1][0], s.pts[seg][1] - s.pts[seg - 1][1]);
        seg += 1;
      }
      const a = s.pts[seg - 1];
      const b = s.pts[seg];
      const sl = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const t = Math.min(1, Math.max(0, (d - walked) / sl));
      xy[k * 2] = a[0] + (b[0] - a[0]) * t;
      xy[k * 2 + 1] = a[1] + (b[1] - a[1]) * t;
      acc[k] = s.accent ? 1 : 0;
      sid[k] = si;
      k += 1;
    }
  });
  return { xy, acc, sid, length: total };
}

function mountSketch(canvas, scroller) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let W = 0; let H = 0; let size = 0; let dot = 1.15;
  let gy = 0;    // 图形锚点 y（恒为内容带中心）
  let gxA = [];  // 各屏图形锚点 x（与文字逐屏左右对调；转场时随相位插值横移）
  let figs = [];
  let N = 0;
  let scatter = []; // 换图途中粒子均匀散布的全屏目标位（也是开场出发点）
  let dust = [];    // 漂浮星尘：随主题色的氛围层，缓慢漂移明灭
  let plex = [];    // 星座网：漂移节点 + 近邻连线，背景的图案结构层
  let lastActive = -1; // 上次写进 CSS 的主题色屏号
  const stepsBox = canvas.parentElement ? canvas.parentElement.querySelector(".land-steps") : null;
  const stepCur = stepsBox ? stepsBox.querySelector("b") : null;
  const stepFill = stepsBox ? stepsBox.querySelector(".land-steps-track i") : null;

  /* 发光粒子 sprite：热芯型径向渐变（核心占 45%、外围快速衰减）画一次，逐点 drawImage；
     粒子层用加法混合，交叠处亮度叠加出「燃烧」感，而不是靠大光晕 */
  const glowSprite = (rgb) => {
    const c = document.createElement("canvas");
    c.width = 32; c.height = 32;
    const g = c.getContext("2d");
    const grad = g.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, `rgba(${rgb},1)`);
    grad.addColorStop(0.45, `rgba(${rgb},0.85)`);
    grad.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = grad;
    g.fillRect(0, 0, 32, 32);
    return c;
  };
  const SPR_INK = glowSprite("237,241,238");
  const SPRS = TONES.map((t) => glowSprite(t.join(","))); // 每屏一色的强调笔画 sprite
  /* 胶片颗粒：一张静态噪点瓦片（中灰上下抖动，overlay 才能双向），低透明度铺满全屏 */
  const grainTile = document.createElement("canvas");
  grainTile.width = grainTile.height = 160;
  {
    const g = grainTile.getContext("2d");
    const id = g.createImageData(160, 160);
    for (let i = 0; i < id.data.length; i += 4) {
      const v = 90 + Math.random() * 76;
      id.data[i] = id.data[i + 1] = id.data[i + 2] = v;
      id.data[i + 3] = 255;
    }
    g.putImageData(id, 0, 0);
  }
  const grainPat = ctx.createPattern(grainTile, "repeat");
  /* 相位 → 相邻两屏主题色的线性插值（背景微染/柔光/文字点缀共用） */
  const mixTone = (ph) => {
    const a = Math.min(TONES.length - 1, Math.floor(ph));
    const b = Math.min(TONES.length - 1, a + 1);
    const k = ph - a;
    return TONES[a].map((v, i) => v + (TONES[b][i] - v) * k);
  };
  /* 一团径向色斑（氛围光斑 / bokeh 共用画法） */
  const blob = (x, y, r, c, al) => {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${al})`);
    g.addColorStop(1, `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},0)`);
    ctx.fillStyle = g;
    ctx.fillRect(x - r, y - r, r * 2, r * 2);
  };
  let phase = 0;
  let target = 0;
  let intro = still ? 1 : 0;
  let raf = 0;
  let idleT = 0; // 静止期的星尘心跳定时器
  let introStart = 0;
  let step = 0;     // 已落定的屏号
  let actCur = 0;   // 当前屏聚形后动画的剧本进度 0→1
  let actStart = 0; // 动画起播时间戳（0 = 未起播）
  let busy = true;  // 剧本进行中（锁输入）；开场聚形后自动播 00 屏动画再亮提示
  let phaseFrom = 0; // 本段换屏的相位起点
  let transStart = 0; // 本段换屏起播时间
  const hintEl = canvas.parentElement ? canvas.parentElement.querySelector(".land-hint") : null;
  const skipEl = canvas.parentElement ? canvas.parentElement.querySelector(".land-skip") : null;
  const hint = (show) => {
    if (hintEl) hintEl.classList.toggle("show", show && !busy && step < figs.length - 1);
  };
  const syncSkip = () => {
    if (skipEl) skipEl.style.visibility = step >= figs.length - 1 ? "hidden" : "";
  };

  const build = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const narrow = W < 920;
    const mid = !narrow && W < 1280;
    /* 文字与图形逐屏左右对调（偶数屏文字左/图形右，奇数屏反之）；
       竖直位置由 JS 写 top、与图形中心对齐，整列放不下时向上收敛：
       顶部最少 72px、底部留 24px，保证不裁字（短屏配合 CSS max-height 收紧一档） */
    const inners = [...scroller.querySelectorAll(".snap-inner")];
    const hh = inners.reduce((m, el) => Math.max(m, el.offsetHeight), 0) || H * 0.5;
    let textTop;
    if (narrow) {
      const figSpace = Math.max(140, H - hh - 40);
      size = Math.min(W * 0.5, figSpace * 0.5);
      gy = 10 + figSpace / 2;
      gxA = inners.map(() => W * 0.5);
      textTop = Math.max(72, Math.min(H - 24 - hh, 10 + figSpace + 16));
    } else {
      const mL = Math.max(120, W * 0.13); // 左列文字边距（与 CSS --col-pad 一致，更靠中）
      const mR = Math.max(88, W * 0.09);  // 右列文字边距
      const colW = mid ? 360 : 440;
      const figM = Math.max(72, W * 0.05); // 图形区域的左右边距（宽图如「树」也不贴边）
      const rightRegion = [mL + colW + 48, W - figM]; // 文字在左时图形的区域
      const leftRegion = [figM, W - mR - colW - 48];  // 文字在右时图形的区域
      const availEven = rightRegion[1] - rightRegion[0];
      const availOdd = leftRegion[1] - leftRegion[0];
      size = Math.min(H * 0.42, availEven * 0.38, availOdd * 0.38);
      gy = H * 0.5;
      gxA = inners.map((_, i) => {
        const r = i % 2 === 0 ? rightRegion : leftRegion;
        return (r[0] + r[1]) / 2;
      });
      textTop = Math.max(72, (H - hh) / 2);
    }
    inners.forEach((el) => { el.style.top = `${textTop}px`; });
    dot = narrow ? 0.85 : 0.95;
    const spacing = narrow ? 1.8 : 1.6; // 更密：细粒子密排 + 横向散布铺成粗笔画
    const raws = SKETCHES.map((f) => f());
    const totalLen = (st) => st.reduce((s, x) => s + strokeLength(x.pts), 0);
    const need = raws.map((st) => Math.ceil((totalLen(st) * size) / spacing));
    N = Math.max(...need);
    // 每张图只点亮自己的 need 颗，保证各图点距一致；其余粒子跟着走但不可见
    const sample = (st, want) => {
      const f = sampleSketch(st, N);
      const vis = new Uint8Array(N);
      for (let j = 0; j < want; j++) vis[Math.floor((j * N) / want)] = 1;
      // 带 part 标记的笔画 → 粒子分组表（1 起，0 = 无分组），供聚形后动画用
      const names = [];
      const pid = new Uint8Array(N);
      st.forEach((s2, si) => {
        if (!s2.part) return;
        let id = names.indexOf(s2.part) + 1;
        if (!id) { names.push(s2.part); id = names.length; }
        for (let j = 0; j < N; j++) if (f.sid[j] === si) pid[j] = id;
      });
      f.pid = pid;
      f.pnames = names;
      f.vis = vis;
      return f;
    };
    figs = raws.map((st, k) => sample(st, need[k]));
    // 04「待办圈 → 对勾」的形变目标：沿对勾折线按弧长均匀取点，与圈上粒子一一对应
    const spec4 = FIG_ANIMS[4] && FIG_ANIMS[4].parts.todo;
    if (figs[4] && figs[4].pid && spec4) {
      const f4 = figs[4];
      const mid = f4.pnames.indexOf("todo") + 1;
      const idxs = [];
      for (let j = 0; j < N; j++) if (f4.pid[j] === mid) idxs.push(j);
      const [p0, p1, p2] = spec4.morphTo;
      const L1 = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
      const L2 = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
      const TT = L1 + L2;
      const tgt = new Float32Array(N * 2);
      idxs.forEach((j, q2) => {
        const d = idxs.length === 1 ? 0 : (q2 / (idxs.length - 1)) * TT;
        let k2;
        if (d <= L1) {
          k2 = L1 ? d / L1 : 0;
          tgt[j * 2] = p0[0] + (p1[0] - p0[0]) * k2;
          tgt[j * 2 + 1] = p0[1] + (p1[1] - p0[1]) * k2;
        } else {
          k2 = L2 ? (d - L1) / L2 : 0;
          tgt[j * 2] = p1[0] + (p2[0] - p1[0]) * k2;
          tgt[j * 2 + 1] = p1[1] + (p2[1] - p1[1]) * k2;
        }
      });
      f4.morph = tgt;
    }
    // 每个采样点的路径法线：细粒子沿法线横向散布，铺出有颗粒感的粗笔画
    figs.forEach((f) => {
      const nx = new Float32Array(N); const ny = new Float32Array(N);
      for (let i = 0; i < N; i++) {
        const i0 = Math.max(0, i - 2); const i1 = Math.min(N - 1, i + 2);
        const dx = f.xy[i1 * 2] - f.xy[i0 * 2];
        const dy = f.xy[i1 * 2 + 1] - f.xy[i0 * 2 + 1];
        const L = Math.hypot(dx, dy) || 1;
        nx[i] = -dy / L; ny[i] = dx / L;
      }
      f.nx = nx; f.ny = ny;
    });
    scatter = Array.from({ length: N }, (_, i) => [
      W * (0.06 + 0.88 * unitHash(i, 11)),
      H * (0.06 + 0.88 * unitHash(i, 13)),
    ]);
    // 星尘三层：远景细点（多而暗）→ 中景点 → 近景 bokeh 软斑（大而更淡、漂移更快），带出纵深
    dust = [];
    const addDust = (n, rr, ar, sp, soft) => {
      for (let k = 0; k < n; k++) {
        const s = dust.length;
        dust.push({
          x: unitHash(s, 19), y: unitHash(s, 23),
          r: rr[0] + unitHash(s, 29) * (rr[1] - rr[0]),
          p: unitHash(s, 31) * Math.PI * 2,
          w: 0.4 + unitHash(s, 37) * 0.9,
          a: ar[0] + unitHash(s, 41) * (ar[1] - ar[0]),
          sp, soft,
        });
      }
    };
    const nn = narrow ? 0.55 : 1;
    addDust(Math.round(74 * nn), [0.5, 1.3], [0.035, 0.09], 0.5, false);
    addDust(Math.round(34 * nn), [0.9, 1.9], [0.05, 0.12], 1, false);
    addDust(narrow ? 7 : 13, [6, 16], [0.028, 0.06], 1.7, true);
    // 星座网节点：向画面中央聚拢（左右两侧留给文字列），小幅漂移，连线随距离实时增减
    plex = Array.from({ length: narrow ? 12 : 24 }, (_, i) => ({
      x: 0.5 + (unitHash(i, 53) - 0.5) * 0.78,
      y: 0.08 + 0.84 * unitHash(i, 59),
      p: unitHash(i, 61) * Math.PI * 2,
      sp: 0.4 + unitHash(i, 67) * 0.7,
      r: 1.1 + unitHash(i, 71),
    }));
  };

  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  /* 聚形后动画进度：当前屏由剧本播放（actCur），已越过的屏视为播完，未到的屏为 0 */
  const actOf = (idx) => (idx === step ? actCur : idx < step ? 1 : 0);

  /* 聚形后动画的逐帧参数；ang 类预乘好 cos/sin，sweep/fill/flat 按各自类型展开 */
  const animsOf = (idx, tm2) => {
    const spec = FIG_ANIMS[idx];
    if (!spec) return null;
    const act = actOf(idx);
    const out = {};
    for (const name of Object.keys(spec.parts)) {
      const c = spec.parts[name];
      if (c.ang) {
        const ang = c.ang(act, tm2);
        out[name] = { ca: Math.cos(ang), sa: Math.sin(ang), px: c.pivot[0], py: c.pivot[1] };
      } else if (c.persp) {
        const ang = c.persp.ang(act);
        out[name] = {
          hx: c.persp.hinge[0], yc: c.persp.yc, w: c.persp.w, pf: c.persp.pf,
          co: Math.cos(ang), si: Math.sin(ang),
        };
      } else if (c.sweep) {
        out[name] = {
          sweep: c.sweep.base + c.sweep.span * (1 - Math.pow(1 - act, 3)),
          from: c.sweep.from, sx: c.pivot[0], sy: c.pivot[1],
        };
      } else if (c.reveal) {
        out[name] = { reveal: c.reveal(act) }; // 门内路面：随开门渐显
      } else if (c.morphTo) {
        out[name] = { morph: true, k: 1 - Math.pow(1 - act, 3) };
      } else if (c.light !== undefined) {
        out[name] = { light: Math.min(1, Math.max(0, act * 4 - c.light)), fill: c.fill || null };
      }
    }
    return out;
  };

  /* 每屏一色（参考彩色 WebGL 粒子站）：背景向主题色微染、图形后一团柔光、强调笔画换色，
  全部随相位在相邻两色间连续过渡；粒子换图途中先均匀散布全屏再聚回 */
  const draw = (now) => {
    if (!figs.length) return;
    const tone = mixTone(phase);
    const bg = mixTone(phase).map((v, i) => Math.round(v * 0.09 + [12, 15, 14][i] * 0.91));
    ctx.fillStyle = `rgb(${bg[0]},${bg[1]},${bg[2]})`;
    ctx.fillRect(0, 0, W, H);
    const a = Math.min(figs.length - 1, Math.floor(phase));
    const b = Math.min(figs.length - 1, a + 1);
    const t = phase - a;
    /* 图形锚点随相位在左右两个区域间插值横移（与文字对调），粒子散开途中完成换位 */
    const anchorT = still ? (t >= 0.5 ? 1 : 0) : ease(Math.min(1, Math.max(0, t / 0.8)));
    const gxCur = gxA.length ? gxA[a] + (gxA[b] - gxA[a]) * anchorT : W * 0.5;

    /* 氛围：四团大范围色斑几乎铺满画面（图形后主光斑 + 本屏色×2 + 下一屏色对角）缓慢漂移，
       背景有了色彩空间而不是单点光源（reduced-motion 时静止） */
    const tm = still ? 0 : (now || 0) / 1000;
    const next = mixTone(Math.min(phase + 1, TONES.length - 1));
    const dr = (p, amp) => (still ? 0 : Math.sin(tm * 0.05 + p) * amp);
    blob(gxCur + dr(0.3, 26), gy + dr(1.1, 20), Math.max(size * 2, H * 0.6), tone, 0.2);
    blob(gxCur - W * 0.22 + dr(2.2, 22), gy + H * 0.22 + dr(3.1, 18), H * 0.85, tone, 0.1);
    blob(W * 0.12 + dr(4.0, 20), H * 0.82 + dr(5.2, 16), H * 0.9, next, 0.09);
    blob(W - gxCur + dr(6.1, 18), H * 0.16 + dr(7.3, 14), H * 0.78, tone, 0.07);

    /* 星座网：节点缓慢漂移，近邻之间牵起随距离淡出的细线——背景有可辨的图案结构 */
    const linkR = Math.min(W, H) * 0.22;
    const pts = plex.map((n) => [
      n.x * W + Math.sin(tm * 0.05 * n.sp + n.p) * 16,
      n.y * H + Math.cos(tm * 0.04 * n.sp + n.p * 1.3) * 12,
    ]);
    const tcol = `rgba(${Math.round(tone[0])},${Math.round(tone[1])},${Math.round(tone[2])},1)`;
    /* 当前屏文字列所在的纵带：穿过去的连线淡化，别在字底下拉线 */
    const tx0 = (a % 2 === 0 ? 0.06 : 0.55) * W;
    const tx1 = tx0 + W * 0.39;
    const inTextBand = (p) => p[0] > tx0 && p[0] < tx1 && p[1] > H * 0.15 && p[1] < H * 0.88;
    ctx.lineWidth = 1;
    ctx.strokeStyle = tcol;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        const d = Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]);
        if (d >= linkR) continue;
        ctx.globalAlpha = (1 - d / linkR) * 0.14 * (inTextBand(pts[i]) || inTextBand(pts[j]) ? 0.3 : 1);
        ctx.beginPath();
        ctx.moveTo(pts[i][0], pts[i][1]);
        ctx.lineTo(pts[j][0], pts[j][1]);
        ctx.stroke();
      }
    }
    ctx.fillStyle = tcol;
    plex.forEach((n, i) => {
      ctx.globalAlpha = 0.12 + 0.08 * n.sp;
      ctx.beginPath();
      ctx.arc(pts[i][0], pts[i][1], n.r, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;

    /* 星尘三层：远景细点 / 中景点 / 近景 bokeh 软斑，漂移速度不同带出纵深 */
    for (const d of dust) {
      const x = d.x * W + Math.sin(tm * 0.12 + d.p) * 18 * d.sp;
      const y = d.y * H + Math.cos(tm * 0.09 + d.p * 1.7) * 14 * d.sp;
      const tw = still ? 0.8 : 0.55 + 0.45 * Math.sin(tm * d.w + d.p);
      ctx.globalAlpha = d.a * tw;
      if (d.soft) {
        blob(x, y, d.r, tone, 1);
        ctx.globalAlpha = 1;
        continue;
      }
      ctx.fillStyle = `rgb(${Math.round(tone[0])},${Math.round(tone[1])},${Math.round(tone[2])})`;
      ctx.beginPath();
      ctx.arc(x, y, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    /* 暗角：四周压暗，视线聚到画面中部（DOM 文字在 canvas 之上，不受影响） */
    const vg = ctx.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.36, W / 2, H / 2, Math.hypot(W, H) / 2);
    vg.addColorStop(0, "rgba(0,0,0,0)");
    vg.addColorStop(1, "rgba(0,0,0,0.18)");
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, W, H);

    const A = still && t >= 0.5 ? figs[b] : figs[a];
    const B = still ? A : figs[b];
    const fxA = still ? null : animsOf(a, tm);
    const fxB = still ? null : animsOf(b, tm);
    /* 05 点亮的节点：环内填成实心并发光（实心核 + 柔光晕，画在环粒子下面） */
    const drawFills = (fx) => {
      if (!fx) return;
      for (const nm2 of Object.keys(fx)) {
        const f2 = fx[nm2];
        if (f2.fill && f2.light > 0) {
          const fxp = gxCur + f2.fill[0] * size;
          const fyp = gy + f2.fill[1] * size;
          const fr = f2.fill[2] * size;
          blob(fxp, fyp, fr * 2.6, tone, 0.3 * f2.light);
          blob(fxp, fyp, fr * 0.95, tone, 0.85 * f2.light);
        }
      }
    };
    drawFills(fxA);
    drawFills(fxB);
    for (let i = 0; i < N; i++) {
      const f = i / N;
      const local = still ? (t >= 0.5 ? 1 : 0) : ease(Math.min(1, Math.max(0, (t - f * 0.35) / 0.65)));
      const ax = A.xy[i * 2]; const ay = A.xy[i * 2 + 1];
      const bx = B.xy[i * 2]; const by = B.xy[i * 2 + 1];
      const x = ax + (bx - ax) * local;
      const y = ay + (by - ay) * local;
      /* 聚形后动画：主导图形里带分组的粒子做 旋转（问号/罗盘/时针）/ 向里推（门）/
         弧线扫过显出（进度弧）/ 形变换色（待办圈→对勾）/ 依次点亮（树节点） */
      let xx = x; let yy = y; let lightK = 0; let recolor = false; let cut = false; let revealK = 1;
      const dom = local < 0.5 ? A : B;
      const domIdx = local < 0.5 ? a : b;
      const fx = domIdx === a ? fxA : fxB;
      if (fx && dom.pid && dom.pid[i]) {
        const f2 = fx[dom.pnames[dom.pid[i] - 1]];
        if (f2) {
          if (f2.ca !== undefined) {
            const dx0 = xx - f2.px; const dy0 = yy - f2.py;
            xx = f2.px + dx0 * f2.ca - dy0 * f2.sa;
            yy = f2.py + dx0 * f2.sa + dy0 * f2.ca;
          } else if (f2.hx !== undefined) {
            /* 绿门向里推：绕左铰链竖轴旋转 + 透视——远端向铰链收拢、向门高中线收缩 */
            const u0 = Math.min(1.2, Math.max(0, (xx - f2.hx) / f2.w));
            const p = 1 / (1 + u0 * f2.w * f2.si * f2.pf);
            xx = f2.hx + u0 * f2.w * f2.co * p;
            yy = f2.yc + (yy - f2.yc) * p;
          } else if (f2.sweep !== undefined) {
            const aP = Math.atan2(yy - f2.sy, xx - f2.sx);
            if ((aP - f2.from + Math.PI * 2.001) % (Math.PI * 2) > f2.sweep) cut = true;
          } else if (f2.morph && dom.morph) {
            xx += (dom.morph[i * 2] - xx) * f2.k;
            yy += (dom.morph[i * 2 + 1] - yy) * f2.k;
            if (f2.k > 0.5) recolor = true;
          } else if (f2.light > 0) {
            lightK = f2.light;
          } else if (f2.reveal !== undefined) {
            revealK = f2.reveal; // 门内路面随开门渐显
          }
        }
      }
      /* 横向散布：细粒子沿笔画法线铺开成粗带（±2.6×dot），转场时法线归零收成细线飞走 */
      const lat = (unitHash(i, 47) * 2 - 1) * 2.6 * dot;
      const nxv = A.nx[i] + (B.nx[i] - A.nx[i]) * local;
      const nyv = A.ny[i] + (B.ny[i] - A.ny[i]) * local;
      let px = gxCur + xx * size + nxv * lat;
      let py = gy + yy * size + nyv * lat;
      const lift = Math.sin(Math.PI * local); // 散开程度：0 聚成图形、1 均匀铺满全屏
      if (lift > 0.001) {
        px += (scatter[i][0] - px) * lift;
        py += (scatter[i][1] - py) * lift;
      }
      if (intro < 1) { // 开场：从全屏散布的暗点聚成首图
        const k2 = Math.min(1, Math.max(0, (intro - f * 0.3) / 0.7));
        px += (scatter[i][0] - px) * (1 - k2);
        py += (scatter[i][1] - py) * (1 - k2);
      }
      const vis = A.vis[i] + (B.vis[i] - A.vis[i]) * local;
      const focus = 1 - lift; // 聚形度：散开暗而细，聚形亮而粗，聚拢完成时最强
      let alpha = vis * (0.28 + 0.72 * Math.pow(focus, 1.4)) * Math.min(1, intro * 1.4) * revealK;
      if (cut || alpha < 0.03) continue; // 进度弧只显出指针扫过的部分；门内路面随开门渐显
      let spr = (local < 0.5 ? A.acc[i] : B.acc[i]) ? (local < 0.5 ? SPRS[a] : SPRS[b]) : SPR_INK;
      if (recolor) spr = SPRS[domIdx]; // 待办圈形变过半后换成本屏主题色
      /* 背景回声：同一图形放大 2.1 倍铺在画面中心后面，淡而可辨的大轮廓（每 3 颗画 1 颗） */
      if (i % 3 === 0) {
        const gpx = W / 2 + x * size * 2.1;
        const gpy = H / 2 + y * size * 2.1;
        const gs = dot * 3;
        ctx.globalAlpha = alpha * 0.15;
        ctx.drawImage(spr, gpx - gs, gpy - gs, gs * 2, gs * 2);
      }
      const jit = 0.75 + unitHash(i, 17) * 0.6; // 粒径抖动：大小参差，聚形后不是均匀的「灯管」
      let r = dot * (0.55 + 1.05 * focus) * jit;
      if (lightK) { // 树节点依次点亮：变亮变大，点亮的瞬间鼓一下再落定
        alpha = Math.min(1, alpha * (1 + 0.8 * lightK));
        r *= 1 + 0.35 * lightK + Math.sin(lightK * Math.PI) * 0.55;
      }
      const s = r * 2.2; // 光晕收小：亮在芯、不在晕
      ctx.globalAlpha = alpha;
      ctx.drawImage(spr, px - s, py - s, s * 2, s * 2);
    }
    ctx.globalAlpha = 1;

    /* 胶片颗粒：静态噪点以 overlay 叠全屏——亮部见纹理、暗部保持干净 */
    if (grainPat) {
      ctx.globalCompositeOperation = "overlay";
      ctx.globalAlpha = 0.08;
      ctx.fillStyle = grainPat;
      ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
    }
  };

  const sections = [...scroller.querySelectorAll(".snap")];

  const syncRail = () => {
    const active = Math.min(figs.length - 1, Math.round(phase));
    /* 文字点缀（kicker/大编号/滚动提示线/进度条）的 --tone 随屏换主题色、步号随屏跳；
       换屏发生在文字淡出的间隙，跳变不会被看见 */
    if (active !== lastActive) {
      lastActive = active;
      const tn = TONES[active];
      (canvas.parentElement || canvas).style.setProperty("--tone", `rgb(${tn[0]},${tn[1]},${tn[2]})`);
      if (stepCur) stepCur.textContent = String(active).padStart(2, "0");
    }
    /* 左缘纵向进度轨道随换屏相位连续生长 */
    if (stepFill) {
      stepFill.style.height = `${Math.min(1, phase / Math.max(1, figs.length - 1)) * 100}%`;
    }
    /* 文字钉在视口不动，只按相位渐显渐隐：行进后段（聚形近完成）渐入，
       开始滚向下一步就渐出；首屏等开场粒子聚完再出现 */
    sections.forEach((sec, i) => {
      const d = phase - i;
      let vis;
      if (still) vis = d > -0.5 && d < 0.5 ? 1 : 0;
      else if (d <= -0.36 || d >= 0.18) vis = 0;
      else if (d < -0.03) vis = (d + 0.36) / 0.33;
      else if (d <= 0.02) vis = 1;
      else vis = 1 - (d - 0.02) / 0.16;
      if (i === 0) vis *= Math.min(1, Math.max(0, (intro - 0.5) / 0.4));
      sec.style.opacity = String(Math.min(1, Math.max(0, vis)));
      sec.classList.toggle("lit", vis > 0.5);
    });
  };

  /* 一次滚轮/滑动/按键 = 走一整段剧本：粒子散开聚形换位 → 文字两段进场 →
     聚形后动画 → 亮「滚动以继续」提示；期间锁输入，不吃连续滚动 */
  const go = (n) => {
    const next = Math.min(figs.length - 1, Math.max(0, n));
    if (busy || next === step) return;
    busy = true;
    actCur = 0;
    actStart = 0;
    phaseFrom = phase;
    transStart = 0;
    target = next;
    hint(false);
    wake();
  };

  const tick = (now) => {
    raf = 0;
    if (!canvas.isConnected) return;
    let moving = false;
    if (intro < 1) {
      if (!introStart) introStart = now;
      intro = Math.min(1, (now - introStart) / 2200);
      moving = true;
    }
    if (busy && intro >= 1) { // 开场聚形先走完，剧本才开始——00 屏的过程要看得见
      if (!transStart) transStart = now;
      const kk = still ? 1 : Math.min(1, (now - transStart) / 4200); // 换屏整段 4.2s，帧率无关
      const ee = kk * kk * (3 - 2 * kk); // smoothstep：缓起缓收，全程可见的运动
      phase = phaseFrom + (target - phaseFrom) * ee;
      moving = true;
      /* 文字进场刚收尾（差 0.02 相位）就起播本屏动画——提示与动画同时亮、输入同时解锁 */
      if (target - phase <= 0.02) {
        phase = target;
        step = target;
        syncSkip();
        if (!actStart) {
          actStart = now;
          busy = false;
          hint(true);
        }
      }
    }
    if (!busy && actStart && actCur < 1) { // 动画与收尾并行，播完转入空闲心跳
      actCur = still ? 1 : Math.min(1, (now - actStart) / 1600);
      moving = true;
    }
    draw(now);
    syncRail();
    if (moving || busy) raf = requestAnimationFrame(tick);
    else if (!still && dust.length) {
      idleT = setTimeout(() => { idleT = 0; raf = requestAnimationFrame(tick); }, 80);
    }
  };
  const wake = () => {
    if (idleT) { clearTimeout(idleT); idleT = 0; }
    if (!raf) raf = requestAnimationFrame(tick);
  };
  const onResize = () => { build(); wake(); };

  /* 步进输入：滚轮（阈值 + busy 锁）、触摸滑动、方向键/翻页键/空格 */
  const onWheel = (e) => {
    if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    e.preventDefault();
    if (e.deltaY > 12) go(step + 1);
    else if (e.deltaY < -12) go(step - 1);
  };
  let touchY = null;
  const onTouchStart = (e) => { touchY = e.touches[0].clientY; };
  const onTouchMove = (e) => { e.preventDefault(); };
  const onTouchEnd = (e) => {
    if (touchY == null) return;
    const d = touchY - e.changedTouches[0].clientY;
    touchY = null;
    if (d > 46) go(step + 1);
    else if (d < -46) go(step - 1);
  };
  const onKey = (e) => {
    if (e.target && e.target.closest && e.target.closest("button, input, textarea")) return;
    if (e.key === "ArrowDown" || e.key === "PageDown" || e.key === " ") { e.preventDefault(); go(step + 1); }
    else if (e.key === "ArrowUp" || e.key === "PageUp") { e.preventDefault(); go(step - 1); }
    else if (e.key === "Home") { e.preventDefault(); go(0); }
    else if (e.key === "End") { e.preventDefault(); go(figs.length - 1); }
  };

  build();
  target = 0;
  phase = 0;
  step = 0;
  window.addEventListener("wheel", onWheel, { passive: false });
  window.addEventListener("touchstart", onTouchStart, { passive: true });
  window.addEventListener("touchmove", onTouchMove, { passive: false });
  window.addEventListener("touchend", onTouchEnd, { passive: true });
  window.addEventListener("keydown", onKey);
  window.addEventListener("resize", onResize);
  // 衬线字体到位后行高会变：重新量内容高度再收敛钉位（采样带 unitHash，是确定性的，重建无跳变）
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => { if (canvas.isConnected) { build(); wake(); } });
  }
  wake();

  return () => {
    cancelAnimationFrame(raf);
    raf = 0;
    if (idleT) clearTimeout(idleT);
    idleT = 0;
    window.removeEventListener("wheel", onWheel);
    window.removeEventListener("touchstart", onTouchStart);
    window.removeEventListener("touchmove", onTouchMove);
    window.removeEventListener("touchend", onTouchEnd);
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", onResize);
  };
}

function workspaceHead(title, lead) {
  const h = el("header", "ws-head");
  h.appendChild(el("h2", "", title));
  if (lead) h.appendChild(el("p", "", lead));
  return h;
}

function portraitTabs(active) {
  const nav = el("nav", "ws-tabs");
  [["onboarding", "对话"], ["confirm", "核对"]].forEach(([view, label]) => {
    const b = el("button", `ws-tab${view === active ? " on" : ""}`, label);
    b.type = "button";
    b.onclick = () => setView(view);
    nav.appendChild(b);
  });
  return nav;
}

function renderLogin() {
  $nav.hidden = true; $header.hidden = true;
  $app.innerHTML = "";
  const hero = el("section", "hero stagger");
  hero.appendChild(el("p", "hero-kicker", "启研 · AI RESEARCH MENTOR"));
  hero.appendChild(el("h2", "", "怎么称呼你？"));
  hero.appendChild(el("p", "hero-lead", "不用真实姓名。进去之后是五个工作区：今日、画像、方向、任务、记录，随时可以换。"));
  const row = el("div", "login-row");
  const input = el("input"); input.placeholder = "你的昵称，例如：小北"; input.maxLength = 24;
  input.setAttribute("aria-label", "昵称");
  const btn = el("button", "btn", "进入启研");
  btn.type = "button";
  btn.onclick = async () => {
    const nick = input.value.trim();
    if (!nick) { toast("先起个昵称吧"); input.focus(); return; }
    btn.disabled = true; btn.textContent = "进入中…";
    try {
      const r = await api("POST", "/api/auth/login", { nickname: nick });
      S.uid = r.uid; S.nickname = r.nickname;
      localStorage.setItem("rg_uid", r.uid);
      localStorage.setItem("rg_nick", r.nickname);
      await api("POST", "/api/onboard/start", { uid: S.uid });
      toast(`你好，${r.nickname}`);
      document.getElementById("userNickname").textContent = r.nickname;
      setView("onboarding");
    } catch (e) { toast(e.message); btn.disabled = false; btn.textContent = "进入启研"; }
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) btn.click(); });
  row.append(input, btn);
  const links = el("div", "hero-links");
  const link = el("button", "linkish", "连接模型 API");
  link.type = "button";
  link.onclick = () => openConnect();
  const back = el("button", "linkish", "返回首页");
  back.type = "button";
  back.onclick = () => setView("home");
  links.append(link, back);
  hero.append(row, links);
  $app.appendChild(hero);
  input.focus();
}

function openConnect() {
  document.querySelectorAll(".connect-mask").forEach((n) => n.remove());
  const mask = el("div", "connect-mask");
  const box = el("form", "connect-box");
  box.innerHTML = `
    <p class="hero-kicker">MODEL</p>
    <h3>连接模型</h3>
    <p class="panel-sub">OpenAI 兼容接口。密钥只写在本机 .env，不会出现在页面回显里。</p>
    <label>接口地址<input name="base" value="https://api.deepseek.com/v1" /></label>
    <label>API Key<input name="key" type="password" placeholder="sk-…" autocomplete="off" /></label>
    <label>模型名<input name="model" value="deepseek-chat" /></label>
    <div class="connect-actions">
      <button type="button" class="btn secondary" id="connectCancel">取消</button>
      <button type="submit" class="btn" id="connectGo">测试并保存</button>
    </div>`;
  mask.appendChild(box);
  document.body.appendChild(mask);
  box.querySelector("#connectCancel").onclick = () => mask.remove();
  mask.addEventListener("click", (e) => { if (e.target === mask) mask.remove(); });
  box.onsubmit = async (e) => {
    e.preventDefault();
    const go = box.querySelector("#connectGo");
    go.disabled = true; go.textContent = "正在连通…";
    try {
      const r = await api("POST", "/api/llm/connect", {
        base_url: box.base.value.trim(),
        api_key: box.key.value.trim(),
        model: box.model.value.trim(),
      });
      applyLlmPill({ enabled: true, model: r.model });
      toast(`已连接 ${r.model}`);
      mask.remove();
    } catch (err) {
      toast(err.message);
      go.disabled = false; go.textContent = "测试并保存";
    }
  };
}

function applyLlmPill(llm) {
  const pill = document.getElementById("llmPill");
  if (!pill || !llm) return;
  pill.textContent = llm.enabled ? `模型 · ${llm.model}` : "连接模型";
  pill.classList.toggle("on", !!llm.enabled);
  pill.onclick = () => openConnect();
}

/* ---------- 画像切换 ---------- */

async function portraitBar() {
  const r = await api("GET", `/api/portraits?uid=${S.uid}`);
  const bar = el("div", "portrait-bar");
  (r.portraits || []).forEach((p) => {
    const chip = el("div", "portrait-chip" + (p.active ? " on" : ""));
    const name = el("button", "portrait-name", p.name);
    name.type = "button";
    name.onclick = async () => {
      if (p.active) return;
      S.portraitId = p.id;
      await api("POST", "/api/portraits/activate", { uid: S.uid, id: p.id });
      setView(S.view === "confirm" ? "confirm" : "onboarding");
    };
    const del = el("button", "portrait-x", "删除");
    del.type = "button";
    del.onclick = async () => {
      if (!window.confirm(`删除「${p.name}」？这份画像的对话和记录都会清掉，不能恢复。`)) return;
      S.portraitId = "";
      await api("DELETE", `/api/portraits/${p.id}?uid=${S.uid}`);
      setView("onboarding");
    };
    chip.append(name, del);
    bar.appendChild(chip);
  });
  const add = el("button", "portrait-add", "新建");
  add.type = "button";
  add.onclick = async () => {
    const created = await api("POST", "/api/portraits", { uid: S.uid });
    const active = (created.portraits || []).find((item) => item.active);
    S.portraitId = active ? active.id : "";
    setView("onboarding");
  };
  bar.appendChild(add);
  return bar;
}

/* ---------- ② onboarding 对话 ---------- */

async function renderOnboarding() {
  const seq = S.renderSeq;
  const bar = await portraitBar();
  if (stale(seq)) return;
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("画像"));
  $app.appendChild(bar);
  $app.appendChild(portraitTabs("onboarding"));
  const wrap = el("div", "two-col");
  const chat = el("div", "panel chat-panel");

  const scroll = el("div", "chat-scroll");
  scroll.setAttribute("aria-live", "polite");
  const foot = el("div", "chat-foot");
  const hint = el("p", "chat-hint");
  const options = el("div", "chat-options");
  const inputRow = el("div", "chat-input-row");
  const input = el("input"); input.placeholder = "或者直接打字告诉我…"; input.maxLength = 200;
  input.setAttribute("aria-label", "回答");
  const sendBtn = el("button", "btn small", "发送");
  sendBtn.type = "button";
  inputRow.append(input, sendBtn);
  foot.append(hint, options, inputRow);
  chat.append(scroll, foot);

  const side = el("div", "panel side-panel");
  side.appendChild(el("p", "side-title", "它刚记下的"));
  const sideList = el("div", "fact-list");
  side.append(sideList, el("p", "side-empty", "每答一问，这里会多一条待你核对的记录。"));

  wrap.append(chat, side);
  $app.appendChild(wrap);

  const r = await api("GET", `/api/onboard/result?uid=${S.uid}`);
  if (stale(seq)) return;
  S.onboard = r;
  r.messages.forEach((m) => addBubble(m.role === "user" ? "user" : "ai", m.text));
  r.facts.filter((f) => f.status === "draft").forEach((f) => sideList.appendChild(factCard(f)));

  if (r.state.phase === "done") {
    finish();
    return;
  }

  const turn = await api("POST", "/api/onboard/message", { uid: S.uid, msg: "" });
  if (stale(seq)) return;
  // msg 为空时后端重发当前轮问题，这里只取 hint/options
  showTurn(turn);

  async function send(text) {
    if (!text.trim() || input.disabled) return;
    addBubble("user", text);
    input.value = "";
    input.disabled = true; sendBtn.disabled = true;
    options.innerHTML = "";
    hint.textContent = "";
    const typing = el("div", "typing", "正在整理");
    scroll.appendChild(typing);
    scroll.scrollTop = scroll.scrollHeight;
    let done = false;
    try {
      const t = await api("POST", "/api/onboard/message", { uid: S.uid, msg: text });
      typing.remove();
      addBubble("ai", t.reply);
      (t.facts || []).forEach((f) => { S.onboard.facts.push(f); sideList.appendChild(factCard(f, false, true)); });
      done = !!t.done;
      showTurn(t);
    } catch (e) {
      typing.remove();
      toast(e.message);
    }
    if (!done) { input.disabled = false; sendBtn.disabled = false; input.focus(); }
  }

  function finish() {
    hint.textContent = "五问已经聊完。右边每一条都可以改或删，核对之后才会用来推荐方向。";
    options.innerHTML = "";
    const go = el("button", "btn", "去核对");
    go.type = "button";
    go.onclick = () => setView("confirm");
    options.appendChild(go);
    inputRow.hidden = true;
  }

  function showTurn(t) {
    if (t.done) { finish(); return; }
    hint.textContent = t.hint || "";
    options.innerHTML = "";
    (t.options || []).forEach((label) => {
      const b = el("button", "chip", esc(label));
      b.type = "button";
      b.onclick = () => send(label);
      options.appendChild(b);
    });
  }

  function addBubble(kind, text) {
    scroll.appendChild(el("div", `bubble ${kind}`, esc(text)));
    scroll.scrollTop = scroll.scrollHeight;
  }

  sendBtn.onclick = () => send(input.value);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) send(input.value); });
}

/* ---------- ③ 确认页 ---------- */

async function renderConfirm() {
  const seq = S.renderSeq;
  const [r, bar] = await Promise.all([api("GET", `/api/onboard/result?uid=${S.uid}`), portraitBar()]);
  if (stale(seq)) return;
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("画像"));
  $app.appendChild(bar);
  $app.appendChild(portraitTabs("confirm"));
  const main = el("div", "panel");

  const list = el("div", "fact-list");
  const drafts = r.facts.filter((f) => f.status === "draft");
  const others = r.facts.filter((f) => f.status === "confirmed" || f.status === "active");
  const edits = {};
  const dismissed = new Set();

  if (drafts.length) {
    main.appendChild(el("p", "panel-sub", "这些是它从对话里记下的。说得不对就直接改，不属实就划掉。保存之后才会用来推荐方向。"));
  } else if (!others.length) {
    main.appendChild(el("div", "note-box", "还没有可核对的记录。先在「对话」里回答几问。"));
  }

  drafts.forEach((f) => {
    const card = factCard(f, true);
    const input = card.querySelector("input");
    input.value = f.value;
    input.setAttribute("aria-label", "修改这条记录");
    input.addEventListener("input", () => { edits[f.id] = input.value; });
    const del = el("button", "linkish danger", "不属实，划掉");
    del.type = "button";
    del.onclick = () => {
      if (dismissed.has(f.id)) dismissed.delete(f.id); else dismissed.add(f.id);
      const off = dismissed.has(f.id);
      card.classList.toggle("is-dismissed", off);
      input.disabled = off;
      del.textContent = off ? "恢复" : "不属实，划掉";
    };
    card.querySelector(".fact-actions").appendChild(del);
    list.appendChild(card);
  });
  if (others.length) {
    if (drafts.length) list.appendChild(el("p", "section-label", "已核对"));
    others.forEach((f) => list.appendChild(factCard(f, false)));
  }
  main.appendChild(list);

  const actions = el("div", "submit-actions");
  if (drafts.length) {
    const ok = el("button", "btn", "保存核对");
    ok.type = "button";
    ok.onclick = async () => {
      const payload = Object.entries(edits).map(([id, value]) => ({ id, value }))
        .concat([...dismissed].map((id) => ({ id, dismissed: true })));
      ok.disabled = true;
      try {
        await api("POST", "/api/onboard/confirm", { uid: S.uid, edits: payload });
        toast("已保存，接下来看方向");
        setView("cards");
      } catch (e) { toast(e.message); ok.disabled = false; }
    };
    actions.appendChild(ok);
  }
  const later = el("button", drafts.length ? "btn ghost" : "btn", "去方向区");
  later.type = "button";
  later.onclick = () => setView("cards");
  actions.appendChild(later);
  main.appendChild(actions);
  $app.appendChild(main);
}

/* ---------- ④ 方向：生长的边界 ---------- */

function twig(label, intro, children) {
  return { label, intro, children: children || [] };
}

function stampTree(node, id) {
  node.id = id;
  (node.children || []).forEach((child, i) => stampTree(child, `${id}.${i}`));
  return node;
}

const FIELD_TREES = {
  ai: {
    name: "人工智能",
    query: "人工智能",
    root: stampTree(twig("看懂机器学习", "机器学习是让程序从例子里找出规律，而不是把每条规则手写死。入门先分清：数据是什么、模型在学什么、你怎么知道它学对了。", [
      twig("数据", "没有数据就没有可检查的结果。先弄清例子从哪来、每个例子长什么样，再谈模型。", [
        twig("例子从哪来", "数据可以是你自己收集的，也可以是别人公开的。来源决定你能下什么结论。", [
          twig("自己标一份", "拿二三十条真实例子，自己写下标签。你会立刻碰到：标准含糊、两类例子长得很像。"),
          twig("公开数据集", "先读数据说明，而不是直接训练。看它收集了谁、缺了谁、标签是谁打的。"),
        ]),
        twig("特征", "特征是你决定让模型看见的那一部分。选错了，后面的模型再复杂也学不到你想问的事。", [
          twig("表格", "一行一个例子，一列一个属性。先画分布，再决定哪一列能用、哪一列不该用。"),
          twig("文本和图像", "文字和图片要先变成数字。这一步叫表示，入门时知道它存在即可，不必先写网络。"),
        ]),
      ]),
      twig("模型怎么学", "模型把「猜错了多少」变成一个数，再按这个数改自己。你要看的是它改完以后，对新例子还对不对。", [
        twig("损失", "损失是猜错的程度。训练就是想把这个数变小，但变小不等于真正学会了。", [
          twig("过拟合", "训练例子上很准、新例子上很差。通常是记得太死，而不是方法更高级。"),
          twig("训练曲线", "把损失随步数画出来。一直降、突然炸、或者很快不动，分别是三种不同的问题。"),
        ]),
        twig("评价", "先定「怎样算做对」，再跑模型。标准要在看结果之前写下来。", [
          twig("别只看准确率", "某一类特别多时，全猜那一类也会有很高的准确率。要看每一类分别怎样。"),
          twig("误差从哪来", "把判错的例子摊开。是标签有问题、特征没覆盖，还是这类例子根本太少。"),
        ]),
      ]),
      twig("用起来", "先做一个小而完整的预测，再碰生成。生成看起来聪明，但更难核对它有没有胡说。", [
        twig("预测一件事", "选一个能在二十分钟里核对的问题，比如一段话是积极还是消极。留下输入、输出和你不同意的例子。"),
        twig("生成", "生成是在续写，不是在检索事实。你要单独检查它说的每件可核对的事。", [
          twig("提示", "把任务、例子和限制写进提示。改一个词，输出就会变，所以提示本身也是实验条件。"),
          twig("幻觉", "说得流畅不等于有依据。对课程名、论文、数字，要回到原处核对，查不到就当没有。"),
        ]),
      ]),
    ]), "ai"),
  },
  math: {
    name: "数学",
    query: "数学",
    root: stampTree(twig("证明是什么", "数学入门不是多做题，而是把一句「显然」拆成别人能检查的步骤。先从定义出发，再谈证明和例子。", [
      twig("定义", "定义规定一个词在这里到底指什么。后面的证明只能用已经定义过的东西。", [
        twig("对象", "先说清你在谈论哪一类东西：数、集合、函数，还是一种关系。", [
          twig("集合", "集合是把对象放在一起的一种说法。属于、子集、空集，是后面所有话的地基。"),
          twig("函数", "函数是一条对应规则：每个输入对应唯一输出。先别急着算，先说清定义域。"),
        ]),
        twig("说法", "把日常句子改成「对所有」或「存在一个」。这句话的范围变了，真假也会变。", [
          twig("量词", "「所有人都会」和「有人会」不是同一句话。写证明前先把量词写对。"),
          twig("反例", "要否定「所有」，举一个不行的例子就够了。这个例子必须真的落在定义里。"),
        ]),
      ]),
      twig("证明", "证明是从定义和已知走到结论的一条路。每一步都要能指出它用了哪一条。", [
        twig("直接证", "假设条件成立，按定义推出结论。写的时候别跳步，跳步通常藏着还没定义的词。", [
          twig("一步一由", "每写一行，旁边注明用的是定义、上一步，还是一条已经证过的事实。"),
        ]),
        twig("反证", "先假设结论不成立，推出和已知矛盾。矛盾必须是明确的，不能只是「看起来怪」。", [
          twig("矛盾要落地", "写出互相否定的那两句话。说「这不可能」之前，先指出不可能的是哪一句。"),
        ]),
      ]),
      twig("结构", "很多新对象其实是旧对象加上一种运算或关系。看懂结构，就是看懂什么被保留了。", [
        twig("关系", "相等、大小、整除，都是关系。先问它是否自反、对称、传递。"),
        twig("不变量", "操作之后仍然不变的量，常常就是问题真正在问的东西。"),
      ]),
    ]), "math"),
  },
  stat: {
    name: "统计",
    query: "统计",
    root: stampTree(twig("数据在说什么", "统计是在不确定里做判断：这批数据支持哪一种说法，以及这个支持有多不稳。", [
      twig("描述", "先把数据本身看清楚，再谈推断。均值会掩盖少数极端值。", [
        twig("分布", "看数据堆在哪里、散得有多开、有没有孤零零的点。", [
          twig("中心", "均值、中位数回答「典型值在哪」。有极端值时，两者会分开。"),
          twig("散开", "同一均值可以很集中，也可以很散。散开程度决定你敢不敢用这个典型值。"),
        ]),
        twig("图", "直方图、散点图比一张表更容易看见形状。图的坐标和分组会改变你看见的故事。", [
          twig("分组", "直方图的箱子宽度变了，峰的个数可能也变。先试两种宽度再下结论。"),
        ]),
      ]),
      twig("推断", "你手里的是样本，想说的是更大的总体。样本不是总体的缩小复印件。", [
        twig("抽样", "谁有机会被抽到，决定你能把结论推到谁身上。", [
          twig("偏差", "方便抽到的人，往往不是你想代表的那群人。先写出没被抽到的是谁。"),
          twig("样本量", "样本越大，波动通常越小，但不能自动消除收集方式带来的偏差。"),
        ]),
        twig("不确定", "用区间或误差说明「还可能差多少」，而不是只给一个点。", [
          twig("区间", "区间越窄不一定越好。要看它是在什么假设下算出来的。"),
        ]),
      ]),
      twig("相关不是因果", "两件事一起变化，可能是第三件事在推动，也可能只是一起出现。", [
        twig("混杂", "找出一个同时影响两边的因素，再问：扣掉它之后，关系还在不在。"),
        twig("实验", "如果能主动分组而不是只观察，因果才比较站得住。分组方式本身要先写清。"),
      ]),
    ]), "stat"),
  },
  psy: {
    name: "认知",
    query: "心理",
    root: stampTree(twig("人如何做判断", "认知科学用可重复的任务，看人在知觉、记忆和决定上实际怎么做，而不是只问他觉得自己怎么做。", [
      twig("知觉", "你看见的不是原始刺激的复印件。大脑会补全、会忽略、会受上下文影响。", [
        twig("注意", "注意是选择。没被选中的信息，常常进不了后面的判断。", [
          twig("漏看", "专心找一件东西时，明显的另一件也可能看不见。这是任务设计，不是粗心的道德问题。"),
        ]),
        twig("错觉", "错觉说明知觉规则在什么时候会给出和物理事实不同的结果。", [
          twig("上下文", "同一个灰块，放在不同背景里明暗会变。判断依赖周围，不依赖孤立的一点。"),
        ]),
      ]),
      twig("记忆", "记忆是重建，不是回放。提问方式和间隔会改变你「记得」的内容。", [
        twig("编码", "当时怎么理解，决定后来能提取出什么。只反复读，不如试着回忆。", [
          twig("提取练习", "合上材料试着写出来，比再看一遍更能暴露你其实没记住的部分。"),
        ]),
        twig("扭曲", "事后信息会改写原先的记忆。问句里的一个词就可能改变回答。", [
          twig("误导提问", "「撞碎」和「碰到」问的不是同一件事。记录原始用词，再比较回答。"),
        ]),
      ]),
      twig("决策", "人常用快捷判断。快捷在熟悉情境里有用，在概率和罕见事件上容易偏。", [
        twig("直觉", "直觉是很快的模式匹配。它擅长你见过很多次的情况。"),
        twig("偏差", "容易想到的例子会被觉得更常见。先把基数写下来，再相信感觉。", [
          twig("基数", "一百个人里真正有多少，比你刚听到的一个生动故事更该先看。"),
        ]),
      ]),
    ]), "psy"),
  },
  econ: {
    name: "经济",
    query: "经济学",
    root: stampTree(twig("选择与激励", "经济学看人在约束下怎么选，以及规则一变，选择会怎么变。先别背模型名字，先写清谁在选、成本是什么。", [
      twig("约束", "任何选择都有放弃的另一项。没写出放弃了什么，就还没开始分析。", [
        twig("机会成本", "成本是你为此没做成的最好的那件事，不只是花出去的钱。", [
          twig("时间也算", "免费的活动如果占掉唯一的晚上，成本就是那个晚上能做的另一件事。"),
        ]),
        twig("预算", "预算是硬边界。边界内怎么分配，取决于每一元换来的增量，不是总价值。", [
          twig("边际", "再多一单位值不值得，和前面已经消费的不是同一个问题。"),
        ]),
      ]),
      twig("激励", "人会对规则做出反应，而且常常反应在你没写进规则的那一面。", [
        twig("奖励", "奖励什么，人们就多做什么。如果指标和你真正想要的不是一回事，行为会对着指标走。", [
          twig("指标被对付", "只奖数量时，质量可能下降。改规则之前，先猜人们会钻哪一个空。"),
        ]),
        twig("Tradeoff", "多得到一项，通常要少得到另一项。政策争论常常是在争这个交换值不值。"),
      ]),
      twig("市场", "价格把分散的信息收成一个信号：哪里缺、哪里多。价格也会漏掉没有被买卖的影响。", [
        twig("供需", "一边更想要、另一边更难提供，价格通常会动。先说清动的是需求还是供给。"),
        twig("外部性", "一笔交易影响到没参加的人时，价格里没有这部分。拥堵、噪音、污染是典型例子。", [
          twig("谁没被算进去", "列出没付钱也没收款、但被影响到的人。他们的损益不在价格里。"),
        ]),
      ]),
    ]), "econ"),
  },
  se: {
    name: "系统",
    query: "软件",
    root: stampTree(twig("程序到底在做什么", "系统入门是把「我写的东西」和「机器实际做的事」对上。先走通一条小路径，再谈结构和可靠性。", [
      twig("表示", "所有数据在机器里都是位。文字、数字、图片只是不同的解释方式。", [
        twig("位和字节", "八个位是一个字节。数字溢出、符号搞反，都发生在这个很底层的约定上。", [
          twig("整数范围", "固定位数能表示的整数有上限。再加一会绕回去，这不是数学里的整数。"),
        ]),
        twig("文本", "一个字对应哪个数字，由编码决定。编码不一致，看到的就是乱码，不是内容变了。", [
          twig("编码", "同一串字节，用 UTF-8 和用别的编码读，会得到不同的字。读写两边要说好。"),
        ]),
      ]),
      twig("执行", "程序是一条条指令。调用函数、读文件、发请求，都是在某个时刻真正发生的事。", [
        twig("调用", "函数调用会把参数和返回地址压进一条路径。你要能说出：谁调用了谁，结果回到哪。", [
          twig("调用栈", "出错时从上往下读栈，最上面是真正炸的地方，下面是谁把它叫起来的。"),
        ]),
        twig("状态", "程序记住的东西会变。同一个函数，状态不同，结果就不同。", [
          twig("可变数据", "改了一处共享的数据，另一处会跟着变。先找出这份数据被谁拿着。"),
        ]),
      ]),
      twig("可靠", "能跑一次不算完成。输入变一点、失败一次、两个人同时用，系统还是否说得通。", [
        twig("边界", "空的、特别长的、刚好差一的输入，最容易露出你没处理的假设。"),
        twig("失败", "网络、文件、用户输入都会失败。失败时留下能看懂的记录，比假装成功有用。", [
          twig("说清楚失败", "告诉使用者失败了什么、你已经知道什么、什么还不知道。不要编一个正常结果。"),
        ]),
      ]),
    ]), "se"),
  },
};

function flattenField(root) {
  const levels = [];
  const byId = {};
  const walk = (node, depth, parent) => {
    const item = { ...node, depth, parent, children: node.children || [] };
    byId[node.id] = item;
    (levels[depth] = levels[depth] || []).push(item);
    item.children.forEach((child) => walk(child, depth + 1, node.id));
  };
  walk(root, 0, null);
  return { levels, byId };
}

function trailStorageKey() {
  return "rg_trail_" + S.uid + (S.portraitId ? "_" + S.portraitId : "");
}

async function ensurePortrait() {
  if (S.portraitId) return S.portraitId;
  try {
    const r = await api("GET", `/api/portraits?uid=${S.uid}`);
    const active = (r.portraits || []).find((p) => p.active);
    S.portraitId = active ? active.id : "";
  } catch (_) {
    S.portraitId = "";
  }
  if (S.portraitId) adoptLegacyTrail(S.portraitId);
  return S.portraitId;
}

function adoptLegacyTrail(pid) {
  const ownerKey = "rg_trail_owner_" + S.uid;
  if (localStorage.getItem(ownerKey)) return;
  const legacy = localStorage.getItem("rg_trail_" + S.uid);
  if (legacy) localStorage.setItem("rg_trail_" + S.uid + "_" + pid, legacy);
  localStorage.setItem(ownerKey, pid);
}

function trail() {
  try {
    const t = JSON.parse(localStorage.getItem(trailStorageKey()) || "null");
    if (t && typeof t === "object") {
      return {
        code: t.code || "",
        done: Array.isArray(t.done) ? t.done : [],
        tasks: t.tasks && typeof t.tasks === "object" ? t.tasks : {},
      };
    }
  } catch (_) { /* 坏数据就当没有进度 */ }
  return { code: "", done: [], tasks: {} };
}

function saveTrail(t, force) {
  const prev = trail();
  const code = t.code || "";
  let done = t.done || [];
  const field = FIELD_TREES[code];
  if (!force && prev.code === code && field) {
    const path = pathNodes(field);
    const prevAt = currentOnPath(field, prev.done);
    const nextAt = currentOnPath(field, done);
    const prevI = prevAt ? path.findIndex((n) => n.id === prevAt.id) : path.length;
    const nextI = nextAt ? path.findIndex((n) => n.id === nextAt.id) : path.length;
    if (nextI < prevI) done = prev.done;
  }
  localStorage.setItem(trailStorageKey(), JSON.stringify({
    code,
    done,
    tasks: force ? (t.tasks || {}) : Object.assign({}, prev.code === code ? prev.tasks : {}, t.tasks || {}),
  }));
}

function inferredDone(code, tasks) {
  const field = FIELD_TREES[code];
  if (!field) return [];
  const path = pathNodes(field);
  let furthest = -1;
  path.forEach((node, i) => {
    const title = node.label.slice(0, 40);
    if ((tasks || []).some((tk) => tk.direction === code && tk.title === title)) furthest = i;
  });
  if (furthest <= 0) return [];
  return path.slice(0, furthest).map((n) => n.id);
}

function mergeTrail(code, tasks) {
  const local = trail();
  const field = FIELD_TREES[code];
  const inferred = inferredDone(code, tasks);
  if (!field) return local;
  if (local.code !== code) return { code, done: inferred, tasks: {} };
  const path = pathNodes(field);
  const localAt = currentOnPath(field, local.done);
  const inferredAt = currentOnPath(field, inferred);
  const localI = localAt ? path.findIndex((n) => n.id === localAt.id) : path.length;
  const inferredI = inferredAt ? path.findIndex((n) => n.id === inferredAt.id) : path.length;
  if (inferredI > localI) return { code, done: inferred, tasks: local.tasks || {} };
  return local;
}

function adoptDirection(facts) {
  // 方向写在事实里（服务端），进度写在本机；本机还没有进度时，从事实里接过方向
  const t = trail();
  if (t.code) return t;
  const dirs = (facts || []).filter((f) => (f.key || "").startsWith("direction:")
    && (f.status === "confirmed" || f.status === "active"));
  const chosen = dirs[dirs.length - 1];
  const code = chosen ? chosen.key.split(":")[1] : "";
  if (!code || !FIELD_TREES[code]) return t;
  const next = { code, done: [], tasks: {} };
  saveTrail(next);
  return next;
}

function pathNodes(field) {
  const out = [];
  const walk = (node) => {
    out.push(node);
    (node.children || []).forEach(walk);
  };
  walk(field.root);
  return out;
}

function currentOnPath(field, done) {
  const seen = new Set(done || []);
  return pathNodes(field).find((node) => !seen.has(node.id)) || null;
}

function drawFieldTree(field, picked, onPick, progress, animate) {
  // 整齐树布局：叶子各占一行，父节点落在子节点的中线上，连线不会交叉
  const { byId } = flattenField(field.root);
  const narrow = window.innerWidth < 920;
  const COL = narrow ? 128 : 168;
  const ROW = narrow ? 42 : 50;
  const NODE_W = narrow ? 104 : 128;
  const NODE_H = 34;
  const PAD = narrow ? 24 : 30;
  const pos = {};
  let row = 0;
  let depthMax = 0;
  const place = (node, depth) => {
    depthMax = Math.max(depthMax, depth);
    const kids = node.children || [];
    if (!kids.length) {
      pos[node.id] = { x: depth * COL, y: row * ROW };
      row += 1;
      return;
    }
    kids.forEach((k) => place(k, depth + 1));
    const first = pos[kids[0].id].y;
    const last = pos[kids[kids.length - 1].id].y;
    pos[node.id] = { x: depth * COL, y: (first + last) / 2 };
  };
  place(field.root, 0);
  const width = depthMax * COL + NODE_W + PAD * 2;
  const height = (row - 1) * ROW + NODE_H + PAD * 2;

  const box = el("div", "frontier");
  box.style.width = width + "px";
  box.style.height = height + "px";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "frontier-svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  const layer = el("div", "frontier-nodes");
  const done = new Set((progress && progress.done) || []);
  const here = progress && progress.here;
  const onPickPath = (id) => picked && (picked === id || picked.startsWith(id + "."));

  Object.values(byId).forEach((node) => {
    if (!node.parent) return;
    const a = pos[node.parent];
    const b = pos[node.id];
    const x1 = PAD + a.x + NODE_W;
    const y1 = PAD + a.y + NODE_H / 2;
    const x2 = PAD + b.x;
    const y2 = PAD + b.y + NODE_H / 2;
    const mid = x1 + (x2 - x1) * 0.5;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`);
    const cls = ["frontier-link"];
    if (onPickPath(node.id)) cls.push("is-hot");
    else if (done.has(node.id) || here === node.id) cls.push("is-past");
    if (animate) { cls.push("reveal"); path.style.setProperty("--d", String(node.depth)); }
    path.setAttribute("class", cls.join(" "));
    svg.appendChild(path);
  });

  Object.values(byId).forEach((node) => {
    const flags = [
      "frontier-node",
      node.id === picked ? "is-pick" : "",
      onPickPath(node.id) && node.id !== picked ? "is-path" : "",
      done.has(node.id) ? "is-past" : "",
      here === node.id ? "is-now" : "",
      animate ? "reveal" : "",
    ].filter(Boolean).join(" ");
    const btn = el("button", flags, esc(node.label));
    btn.type = "button";
    btn.title = node.label;
    btn.style.left = PAD + pos[node.id].x + "px";
    btn.style.top = PAD + pos[node.id].y + "px";
    btn.style.width = NODE_W + "px";
    if (animate) btn.style.setProperty("--d", String(node.depth));
    if (here === node.id) btn.setAttribute("aria-current", "step");
    btn.onclick = () => onPick(byId[node.id]);
    layer.appendChild(btn);
  });
  box.append(svg, layer);
  return box;
}

function openNodeSheet(field, node, ctx) {
  let sheet = document.getElementById("nodeSheet");
  if (!sheet) {
    sheet = el("aside", "node-sheet");
    sheet.id = "nodeSheet";
    document.body.appendChild(sheet);
  }
  sheet.className = "node-sheet open";
  sheet.innerHTML = "";
  const head = el("div", "sheet-head");
  const x = el("button", "sheet-x", "关闭");
  x.type = "button";
  x.onclick = () => sheet.remove();
  head.append(el("p", "sheet-kicker", esc(field.name)), x);
  sheet.appendChild(head);
  sheet.appendChild(el("h3", "", esc(node.label)));
  sheet.appendChild(el("p", "sheet-intro", esc(node.intro || "")));
  if (node.id === field.root.id && ctx.why) {
    sheet.appendChild(el("p", "sheet-why", esc(ctx.why)));
  }
  if (node.children && node.children.length) {
    sheet.appendChild(el("p", "sheet-label", "往下"));
    const row = el("div", "sheet-nexts");
    node.children.forEach((child) => {
      const b = el("button", "sheet-next", esc(child.label));
      b.type = "button";
      b.onclick = () => ctx.onPick(child.id);
      row.appendChild(b);
    });
    sheet.appendChild(row);
  }
  if (ctx.here === node.id && ctx.chosen) {
    const go = el("button", "btn", "去做这一步");
    go.type = "button";
    go.onclick = () => setView("workbench");
    sheet.appendChild(go);
  }
  if (node.id === field.root.id) {
    if (ctx.reading && ctx.reading.title) {
      const read = el("div", "sheet-reading");
      read.appendChild(el("h4", "", "入门读物"));
      read.appendChild(el("p", "reading-title", esc(ctx.reading.title)));
      if (ctx.reading.why) read.appendChild(el("p", "reading-why", esc(ctx.reading.why)));
      sheet.appendChild(read);
    }
    const courses = el("div", "course-block");
    courses.appendChild(el("h4", "", "课程"));
    courses.appendChild(el("div", "course-status", "检索中"));
    sheet.appendChild(courses);
    loadCourses(courses, field.query);
    if (!ctx.chosen) {
      const choose = el("button", "btn", ctx.hasCurrent ? "确认切换方向" : "确认这个方向");
      choose.type = "button";
      choose.onclick = () => ctx.onChoose();
      sheet.appendChild(choose);
    }
  }
  sheet.querySelector(".sheet-x").focus({ preventScroll: true });
}

async function renderCards() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  let saved = trail();
  try {
    const taskRes = await api("GET", `/api/tasks?uid=${S.uid}`);
    if (stale(seq)) return;
    if (saved.code) {
      const merged = mergeTrail(saved.code, taskRes.tasks || []);
      if (merged.done.join(",") !== saved.done.join(",")) saveTrail(merged);
    }
  } catch (_) { /* 树先按本地进度画 */ }
  if (stale(seq)) return;
  saved = trail();
  let chosenCode = saved.code && FIELD_TREES[saved.code] ? saved.code : "";
  let cards = [];
  let recommended = new Set();
  let current = chosenCode || "ai";
  let touched = !!chosenCode;
  let picked = null;
  let grew = true;

  $app.innerHTML = "";
  $app.appendChild(workspaceHead("方向"));
  const switcher = el("div", "field-switch");
  switcher.setAttribute("role", "tablist");
  const recLine = el("div", "rec-line");
  const confirmBar = el("div", "switch-bar");
  const stage = el("div", "forest-stage");
  const legend = el("div", "tree-legend",
    '<span class="now"><i></i>你在这里</span><span class="past"><i></i>已走过</span><span><i></i>还可以去</span><span>点任一节点看说明</span>');
  $app.append(switcher, recLine, confirmBar, stage, legend);

  const paint = () => {
    switcher.innerHTML = "";
    Object.entries(FIELD_TREES).forEach(([code, field]) => {
      const b = el("button", "field-chip" + (code === current ? " on" : ""));
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", code === current ? "true" : "false");
      b.appendChild(el("span", "", field.name));
      if (code === chosenCode) b.appendChild(el("i", "", "当前"));
      else if (recommended.has(code)) b.appendChild(el("i", "", "建议"));
      b.onclick = () => {
        current = code;
        touched = true;
        picked = null;
        grew = true;
        document.getElementById("nodeSheet")?.remove();
        paint();
      };
      switcher.appendChild(b);
    });
    const hereTrail = trail();
    const fieldNow = FIELD_TREES[current];
    const here = hereTrail.code === current ? currentOnPath(fieldNow, hereTrail.done) : null;
    confirmBar.innerHTML = "";
    if (!chosenCode || current !== chosenCode) {
      const note = el("p", "", chosenCode
        ? `正在预览「${fieldNow.name}」。当前方向仍是「${FIELD_TREES[chosenCode].name}」。`
        : `正在看「${fieldNow.name}」。确认之后，它才会成为当前方向。`);
      const ok = el("button", "btn small", chosenCode ? "确认切换方向" : "确认这个方向");
      ok.type = "button";
      ok.onclick = () => chooseField();
      confirmBar.append(note, ok);
    } else if (here) {
      const note = el("p", "", `当前方向「${fieldNow.name}」，你在「${here.label}」。`);
      const go = el("button", "btn small", "去做这一步");
      go.type = "button";
      go.onclick = () => setView("workbench");
      confirmBar.append(note, go);
    }
    stage.innerHTML = "";
    stage.appendChild(drawFieldTree(fieldNow, picked, (node) => show(node.id), {
      done: hereTrail.code === current ? hereTrail.done : [],
      here: here && here.id,
    }, grew));
    grew = false;
  };

  const chooseField = async () => {
    const field = FIELD_TREES[current];
    try {
      await api("POST", "/api/directions/choose", { uid: S.uid, code: current });
      const switching = !!(chosenCode && chosenCode !== current);
      saveTrail({ code: current, done: [], tasks: {} }, true);
      chosenCode = current;
      toast(switching
        ? `已切换到「${field.name}」，从「${field.root.label}」重新开始`
        : `已确认「${field.name}」，从「${field.root.label}」开始`);
      document.getElementById("nodeSheet")?.remove();
      picked = null;
      paint();
    } catch (e) { toast(e.message); }
  };

  const show = (id) => {
    const field = FIELD_TREES[current];
    const node = flattenField(field.root).byId[id];
    if (!node) return;
    picked = id;
    paint();
    const hereTrail = trail();
    const here = hereTrail.code === current ? currentOnPath(field, hereTrail.done) : null;
    const card = cards.find((c) => c.direction && c.direction.code === current);
    openNodeSheet(field, node, {
      why: card && card.why_you,
      reading: card && card.reading,
      chosen: current === chosenCode,
      hasCurrent: !!chosenCode,
      here: here && here.id,
      onPick: show,
      onChoose: chooseField,
    });
  };

  paint();
  api("GET", `/api/onboard/result?uid=${S.uid}`).then((onboard) => {
    if (stale(seq)) return;
    const facts = ((onboard && onboard.facts) || []).filter((f) => f.status !== "deleted" && f.status !== "dismissed");
    const dirs = facts.filter((f) => (f.key || "").startsWith("direction:") && (f.status === "confirmed" || f.status === "active"));
    const chosen = dirs[dirs.length - 1];
    const code = chosen ? chosen.key.split(":")[1] : "";
    if (code && FIELD_TREES[code] && !trail().code) {
      saveTrail({ code, done: [], tasks: {} });
      chosenCode = code;
      current = code;
      touched = true;
      grew = true;
      paint();
    } else if (trail().code && trail().code !== chosenCode) {
      chosenCode = trail().code;
      paint();
    }
  }).catch(() => {});
  api("GET", `/api/directions/recommend?uid=${S.uid}`).then((rec) => {
    if (stale(seq)) return;
    cards = rec.cards || [];
    recommended = new Set(cards.map((c) => c.direction && c.direction.code).filter(Boolean));
    recLine.innerHTML = "";
    if (!cards.length) {
      recLine.appendChild(el("p", "", "这份画像还没有可对照的兴趣。先在画像里把对话做完，建议才会按你分开。"));
    } else {
      const names = cards.map((c) => {
        const code = c.direction && c.direction.code;
        return (FIELD_TREES[code] && FIELD_TREES[code].name) || (c.direction && c.direction.name) || "";
      }).filter(Boolean);
      recLine.appendChild(el("p", "", `这份画像更贴近${names.join("、")}。${cards[0].why_you || ""}`));
      if (window.innerWidth < 920) {
        recLine.classList.add("clamp");
        recLine.onclick = () => recLine.classList.remove("clamp");
      }
      const top = cards[0].direction && cards[0].direction.code;
      if (!touched && top && FIELD_TREES[top]) { current = top; grew = true; }
    }
    paint();
  }).catch(() => {});
}

async function loadCourses(box, query) {
  const status = box.querySelector(".course-status");
  try {
    const r = await api("GET", `/api/explore/courses?query=${encodeURIComponent(query)}&limit=4`);
    if (!r.ok) { status.textContent = `检索失败（如实说明）：${r.error || "未知错误"}`; return; }
    status.remove();
    if (!r.items || !r.items.length) {
      box.appendChild(el("div", "course-status", `本轮「${query}」没有查到课程——真实检索，查不到就说查不到。`));
      return;
    }
    r.items.forEach((it) => {
      const name = it.name || it.courseName || "(未命名课程)";
      const teacher = it.teacher || it.teachers || "";
      const dept = it.department || it.dept || "";
      box.appendChild(el("div", "course-item",
        `${esc(name)}<br><span class="meta">${esc([teacher, dept, r.term].filter(Boolean).join(" · "))}</span>`));
    });
  } catch (e) {
    status.textContent = `检索失败（如实说明）：${e.message}`;
  }
}

/* ---------- ⑤⑥ 工作台 ---------- */

function readDraft(tid) {
  try { return localStorage.getItem("rg_draft_" + tid) || ""; } catch (_) { return ""; }
}
function writeDraft(tid, text) {
  try {
    if (text) localStorage.setItem("rg_draft_" + tid, text);
    else localStorage.removeItem("rg_draft_" + tid);
  } catch (_) { /* 存不了就算了，不影响提交 */ }
}

function emptyPanel(text, label, view) {
  const p = el("div", "panel");
  p.appendChild(el("p", "panel-sub", text));
  if (label) {
    const b = el("button", "btn", label);
    b.type = "button";
    b.style.marginTop = "16px";
    b.onclick = () => setView(view);
    p.appendChild(b);
  }
  return p;
}

async function renderWorkbench() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  $app.innerHTML = "";
  $app.appendChild(skeleton(2));
  const [taskRes, onboard] = await Promise.all([
    api("GET", `/api/tasks?uid=${S.uid}`).catch(() => ({ tasks: [] })),
    api("GET", `/api/onboard/result?uid=${S.uid}`).catch(() => null),
  ]);
  if (stale(seq)) return;
  $app.innerHTML = "";
  const wrap = el("div", "stagger");
  wrap.appendChild(workspaceHead("任务"));
  $app.appendChild(wrap);
  const facts = ((onboard && onboard.facts) || []).filter((f) => f.status !== "deleted" && f.status !== "dismissed");
  let t = adoptDirection(facts);
  const listed = taskRes.tasks || [];
  if (t.code) {
    const merged = mergeTrail(t.code, listed);
    if (merged.done.join(",") !== t.done.join(",")) {
      t = merged;
      saveTrail(t);
    }
  }
  const code = t.code;
  if (!code || !FIELD_TREES[code]) {
    wrap.appendChild(emptyPanel("还没有方向。先在方向区选定一棵树，任务会从它的起点开始。", "去方向区", "cards"));
    return;
  }
  const field = FIELD_TREES[code];
  const node = currentOnPath(field, t.done);
  if (!node) {
    wrap.appendChild(emptyPanel(`「${field.name}」这条路径上的节点都走完了。`, "回方向区换一棵树", "cards"));
    return;
  }
  const expect = node.label.slice(0, 40);
  const boundId = (t.tasks || {})[node.id];
  let task = boundId ? listed.find((tk) => tk.id === boundId) : null;
  if (task && task.title !== expect) task = null;
  if (!task) task = [...listed].reverse().find((tk) => tk.title === expect && tk.direction === code) || null;
  if (!task) {
    task = await api("POST", "/api/tasks/generate", {
      uid: S.uid, direction: code, level: 1, title: node.label, brief: node.intro,
    });
    if (stale(seq)) return;
  }
  if (!task || task.title !== expect) {
    wrap.appendChild(emptyPanel(`当前节点是「${node.label}」，但任务服务还在用旧题目。请重新启动本地服务后再打开任务区。`));
    return;
  }
  t.tasks = Object.assign({}, t.tasks, { [node.id]: task.id });
  saveTrail(t);
  S.lastTask = task;
  if (task.status === "done" && S.lastFeedbackTaskId !== task.id) {
    try {
      const saved = JSON.parse(sessionStorage.getItem("rg_fb_" + task.id) || "null");
      if (saved) {
        S.lastFeedback = saved;
        S.lastFeedbackTaskId = task.id;
      }
    } catch (_) { /* 没有存过这次反馈 */ }
  }
  const path = pathNodes(field);
  const stepNo = path.findIndex((n) => n.id === node.id) + 1;
  wrap.appendChild(el("div", "ws-status",
    `<span>${esc(field.name)}</span><span>第 ${stepNo} / ${path.length} 个节点</span>`));
  const p = el("div", "panel");
  wrap.appendChild(p);

  const paintHead = () => {
    const head = el("div", "task-head");
    const hl = el("div");
    hl.appendChild(el("h2", "task-title", esc(node.label)));
    hl.appendChild(el("p", "task-brief", esc(node.intro || task.brief)));
    head.appendChild(hl);
    head.appendChild(el("span", "task-meta", `约 ${task.time_budget_min} 分钟`));
    p.appendChild(head);
  };

  const showFinished = () => {
    p.innerHTML = "";
    paintHead();
    if (S.lastFeedback && S.lastFeedbackTaskId === task.id) renderFeedbackInto(p);
    const next = currentOnPath(field, t.done.concat(node.id));
    p.appendChild(el("div", "note-box finished-note", next
      ? `这一节点已完成。下一节点是「${esc(next.label)}」，进入之后才会安排那一步的任务。`
      : "这是这条方向上的最后一个节点。"));
    const acts = el("div", "submit-actions");
    if (next) {
      const go = el("button", "btn", `进入「${esc(next.label)}」`);
      go.type = "button";
      go.onclick = async () => {
        go.disabled = true;
        try {
          const created = await api("POST", "/api/tasks/generate", {
            uid: S.uid, direction: code, level: 1, title: next.label, brief: next.intro,
          });
          if (!created || created.title !== next.label.slice(0, 40)) {
            toast("下一节点的任务没有生成，请重启本地服务后再试");
            go.disabled = false;
            return;
          }
          const tasksMap = Object.assign({}, t.tasks, { [next.id]: created.id });
          saveTrail({ code, done: t.done.concat(node.id), tasks: tasksMap });
          S.lastTask = created;
          S.lastFeedback = null;
          S.lastFeedbackTaskId = "";
          setView("workbench");
        } catch (e) {
          toast(e.message);
          go.disabled = false;
        }
      };
      acts.appendChild(go);
    }
    const me = el("button", "btn ghost", "看它记下了什么");
    me.type = "button";
    me.onclick = () => setView("me");
    acts.appendChild(me);
    p.appendChild(acts);
  };

  if (task.status === "done") {
    showFinished();
    return;
  }

  paintHead();

  p.appendChild(el("h3", "section-label", "步骤"));
  const steps = el("div", "step-list");
  task.steps.forEach((st) => {
    const row = el("label", "step");
    const cb = el("input"); cb.type = "checkbox";
    row.append(cb, el("span", "", esc(st)));
    steps.appendChild(row);
  });
  p.appendChild(steps);

  p.appendChild(el("h3", "section-label", "怎样算做到"));
  const crit = el("ul", "criteria");
  task.rubric.forEach((r2) => crit.appendChild(el("li", "", esc(r2.criterion))));
  p.appendChild(crit);

  const box = el("div", "submit-box");
  const ta = el("textarea");
  ta.placeholder = "写下你的过程与发现：例子、原因、你现在的判断。没做完也可以交，它只看你写了什么。";
  ta.setAttribute("aria-label", "提交内容");
  ta.value = readDraft(task.id);
  const count = el("span", "hint");
  const recount = () => { count.textContent = ta.value.trim() ? `已写 ${ta.value.trim().length} 字 · 草稿自动保存在本机` : "提交后按上面的标准逐条反馈，并写回你的记录。"; };
  ta.addEventListener("input", () => { writeDraft(task.id, ta.value); recount(); });
  recount();
  const demo = el("button", "btn ghost small", "填入演示示例");
  demo.type = "button";
  demo.onclick = () => {
    ta.value =
      "10 条弹幕：「太好哭了」「就这？」「编剧封神」「注水严重」「封神」「看不下去了」「细节绝了」「一般」「泪目」「神剧」\n\n" +
      "不一致例子 1：「太好哭了」——规则判积极（含「哭」可能误判消极），模型判积极。原因：规则把「哭」当消极词，但语境是感动。\n" +
      "不一致例子 2：「就这？」——规则因为无情感词判中性，模型判消极。原因：反问语气规则抓不到，模型学了语料里的讽刺用法。\n" +
      "不一致例子 3：「封神」——规则词表里没有，判中性；模型判积极。原因：网络新词，词表更新慢，模型能从上下文推断。\n\n" +
      "总结：模型的错误多来自词表覆盖与语境缺失两类；因为规则的可解释性和模型的表达力正好互补，可以互为校验。所以每次重要判断最好两个方法都跑一遍，不一致的例子就是最有价值的学习样本。";
    writeDraft(task.id, ta.value);
    recount();
  };
  const actions = el("div", "submit-actions");
  const submit = el("button", "btn", "提交");
  submit.type = "button";
  submit.onclick = async (ev) => {
    ev.preventDefault();
    if (ta.value.trim().length < 10) { toast("至少写一句话再提交"); ta.focus(); return; }
    submit.disabled = true; submit.textContent = "正在逐条看…";
    try {
      const fb = await api("POST", `/api/tasks/${task.id}/submit`, { uid: S.uid, payload: ta.value });
      S.lastFeedback = fb;
      S.lastFeedbackTaskId = task.id;
      sessionStorage.setItem("rg_fb_" + task.id, JSON.stringify(fb));
      writeDraft(task.id, "");
      S.newFactIds = (fb.learned_facts || []).map((f) => f.id);
      task.status = "done";
      showFinished();
      setTimeout(() => document.getElementById("fbPanel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
    } catch (e) { toast(e.message); submit.disabled = false; submit.textContent = "提交"; }
  };
  actions.append(submit, demo, count);
  box.append(ta, actions);
  p.appendChild(box);
}

/* ---------- ⑦ 反馈 ---------- */

function renderFeedbackInto(p) {
  const fb = S.lastFeedback;
  if (!fb) return;
  const box = el("section", "feedback");
  box.id = "fbPanel";
  const head = el("div", "feedback-head");
  const hl = el("div");
  hl.appendChild(el("h3", "", "反馈"));
  if (fb.encouragement) hl.appendChild(el("p", "", esc(fb.encouragement)));
  head.appendChild(hl);
  const passed = (fb.rubric || []).filter((r) => r.pass).length;
  head.appendChild(el("div", "score-ring", `<span class="num">${passed}</span>/ ${(fb.rubric || []).length} 条做到`));
  box.appendChild(head);
  if ((fb.rubric || []).length) {
    const bar = el("div", "pass-bar");
    (fb.rubric || []).forEach((r) => bar.appendChild(el("i", r.pass ? "ok" : "bad")));
    box.appendChild(bar);
  }

  const rub = el("div", "rubric-list");
  (fb.rubric || []).forEach((r) => {
    rub.appendChild(el("div", `rubric-item ${r.pass ? "pass" : "fail"}`,
      `<span class="rubric-mark" aria-label="${r.pass ? "做到" : "还没做到"}">${r.pass ? "✓" : "!"}</span><div><p class="rubric-crit">${esc(r.criterion)}</p><p class="rubric-comment">${esc(r.comment)}</p></div>`));
  });
  box.appendChild(rub);
  if (fb.next_hint) box.appendChild(el("div", "why-box", `<b>下一步　</b>${esc(fb.next_hint)}`));

  if (fb.learned_facts && fb.learned_facts.length) {
    const fl = el("div", "fact-list");
    fb.learned_facts.forEach((f) => fl.appendChild(factCard(f, false, true)));
    box.appendChild(fl);
  }
  p.appendChild(box);
}

/* ---------- 今日 / ⑨ NBA ---------- */

/* 服务端 NBA 的 action → 按钮文案与目标视图（schemas.NBA 契约里的枚举） */
const NBA_ACTION_VIEW = {
  micro_task: ["去做这一步", "workbench"],
  explore_direction: ["去方向区", "cards"],
  course_action: ["去方向区", "cards"],
  read_paper: ["去方向区", "cards"],
  ask_clarifying: ["去画像", "onboarding"],
  review_progress: ["去记录", "me"],
};

/* 今日页顶部的闭环进度条：聊过 → 核对 → 方向 → 任务 → 项目 → 记录，点任一步直接跳 */
function loopStrip(steps, nowIdx) {
  const strip = el("nav", "loop-strip");
  strip.setAttribute("aria-label", "科研入门闭环");
  steps.forEach((s, i) => {
    const cls = "loop-step" + (s.done ? " done" : "") + (i === nowIdx ? " now" : "");
    const b = el("button", cls, `<i></i><span>${esc(s.label)}</span>`);
    b.type = "button";
    b.title = s.done ? `${s.label}：已走过` : i === nowIdx ? `${s.label}：当前这一步` : `${s.label}：还没到`;
    if (i === nowIdx) b.setAttribute("aria-current", "step");
    b.onclick = () => setView(s.view);
    strip.appendChild(b);
  });
  return strip;
}

async function renderToday() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  $app.innerHTML = "";
  $app.appendChild(skeleton(3));
  const [taskRes, onboard, mineRes] = await Promise.all([
    api("GET", `/api/tasks?uid=${S.uid}`).catch(() => null),
    api("GET", `/api/onboard/result?uid=${S.uid}`).catch(() => null),
    api("GET", `/api/projects/mine?uid=${S.uid}`).catch(() => ({ projects: [] })),
  ]);
  if (stale(seq)) return;
  adoptDirection((onboard && onboard.facts) || []);
  let saved = trail();
  if (taskRes && saved.code) {
    const merged = mergeTrail(saved.code, taskRes.tasks || []);
    if (merged.done.join(",") !== saved.done.join(",")) {
      saveTrail(merged);
      saved = trail();
    }
  }
  const field = FIELD_TREES[saved.code];
  const node = field ? currentOnPath(field, saved.done) : null;
  const facts = (onboard && onboard.facts) || [];
  const talked = onboard && onboard.state && onboard.state.phase === "done";
  const drafts = facts.filter((f) => f.status === "draft").length;
  const doneTasks = ((taskRes && taskRes.tasks) || []).filter((t) => t.status === "done");
  const behavior = facts.filter((f) => f.source === "behavior" && f.status !== "deleted").length;

  /* 客户端兜底建议：没聊 / 没核对这两种服务端 NBA 覆盖不到的状态，仍按本地判断 */
  let title; let why; let label; let view;
  if (!field && !talked) {
    title = "先聊五个问题";
    why = "它还不认识你。五个问题，大约五分钟：年级、基础、好奇什么、习惯怎么学。每一问都可以选「不知道」。";
    label = "去画像"; view = "onboarding";
  } else if (!field && drafts) {
    title = `核对它记下的 ${drafts} 条`;
    why = "对话里记下的内容还是草稿。改掉不对的、划掉不属实的，方向建议才会按你来。";
    label = "去核对"; view = "confirm";
  } else if (!field) {
    title = "选定一个方向";
    why = "方向区有六棵树，已经按你的画像标出建议。确认其中一棵，任务会从它的起点开始。";
    label = "去方向区"; view = "cards";
  } else if (node) {
    title = `继续「${node.label}」`;
    why = node.intro;
    label = "去做这一步"; view = "workbench";
  } else {
    title = `「${field.name}」这条路已经走到头`;
    why = "可以回方向区换一棵树，或者到记录里回看这一路留下的证据。";
    label = "去方向区"; view = "cards";
  }

  /* 服务端 NBA（POST /api/nba）不挡首屏：本地建议先画出来，模型措辞回来后原地升级卡片 */
  $app.innerHTML = "";
  const wrap = el("div", "stagger");
  wrap.appendChild(workspaceHead("今日"));

  const status = el("div", "status-chips");
  status.appendChild(el("span", "status-chip" + (field ? " on" : ""), field ? esc(field.name) : "还没有方向"));
  if (node) status.appendChild(el("span", "status-chip", `正在「${esc(node.label)}」`));
  if (behavior) status.appendChild(el("span", "status-chip", `已交 ${behavior} 次任务`));
  wrap.appendChild(status);

  /* 闭环进度：每步是否走过由真实数据判定，不猜 */
  const confirmed = facts.filter((f) => f.status === "confirmed" || f.status === "active").length;
  const steps = [
    { label: "聊过", done: !!talked, view: "onboarding" },
    { label: "核对", done: !!talked && drafts === 0 && confirmed > 0, view: "confirm" },
    { label: "方向", done: !!field, view: "cards" },
    { label: "任务", done: doneTasks.length > 0, view: "workbench" },
    { label: "项目", done: ((mineRes && mineRes.projects) || []).length > 0, view: "projects" },
    { label: "记录", done: confirmed > 0, view: "me" },
  ];
  const nowIdx = steps.findIndex((s) => !s.done);
  wrap.appendChild(loopStrip(steps, nowIdx));

  const card = el("div", "nba-card");
  card.appendChild(el("h3", "nba-title", esc(title)));
  card.appendChild(el("p", "nba-why", esc(why)));
  const act = el("div", "submit-actions");
  const go = el("button", "btn", label);
  go.type = "button";
  go.onclick = () => setView(view);
  act.appendChild(go);
  card.appendChild(act);
  wrap.appendChild(card);
  $app.appendChild(wrap);

  /* 核对完之后问服务端 NBA：规则决策 + 可选模型措辞，带依据引用与备选行动；慢或失败就保持本地建议 */
  if ((talked && drafts === 0) || field) {
    api("POST", "/api/nba", { uid: S.uid }).then((nba) => {
      if (stale(seq) || !nba || !nba.title || !nba.rationale) return;
      card.querySelector(".nba-title").textContent = nba.title;
      card.querySelector(".nba-why").textContent = nba.rationale;
      const hit = NBA_ACTION_VIEW[nba.action] || NBA_ACTION_VIEW.micro_task;
      go.textContent = hit[0];
      go.onclick = () => setView(hit[1]);
      (nba.rationale_facts || []).slice(0, 2).forEach((fid) => {
        const f = facts.find((x) => x.id === fid);
        if (f && f.value) card.insertBefore(el("p", "nba-evidence", `你说过的：「${esc(f.value)}」`), act);
      });
      const alts = (nba.alternatives || []).slice(0, 2);
      if (alts.length && !card.querySelector(".nba-alts")) {
        const altRow = el("div", "nba-alts");
        alts.forEach((a) => {
          const to = NBA_ACTION_VIEW[a.action];
          const b = el("button", "btn small ghost", esc(a.title || a.action));
          b.type = "button";
          if (to) b.onclick = () => setView(to[1]);
          altRow.appendChild(b);
        });
        card.appendChild(altRow);
      }
    }).catch(() => { /* 保持本地建议，不提示错误 */ });
  }
}

/* ---------- ⑧ me 页 ---------- */

async function renderMe() {
  const seq = S.renderSeq;
  $app.innerHTML = "";
  $app.appendChild(skeleton(3));
  let r;
  try {
    r = await api("GET", `/api/me/facts?uid=${S.uid}`);
  } catch (e) {
    if (stale(seq)) return;
    $app.innerHTML = "";
    $app.appendChild(workspaceHead("记录", "它记住的每一条都写着来源。说得不对可以改，不想让它记着可以删。"));
    $app.appendChild(el("div", "note-box", `记录读取失败（如实说明）：${esc(e.message)}`));
    return;
  }
  if (stale(seq)) return;
  const facts = r.facts.filter((f) => f.status !== "deleted" && f.status !== "dismissed");
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("记录", "它记住的每一条都写着来源。说得不对可以改，不想让它记着可以删。"));
  const main = el("div", "panel");

  const groups = {};
  facts.forEach((f) => { (groups[f.category] = groups[f.category] || []).push(f); });
  Object.keys(CAT_CN).forEach((cat) => {
    if (!groups[cat] || !groups[cat].length) return;
    const g = el("section", "fact-group");
    g.appendChild(el("h3", "section-label", `${CAT_CN[cat]} · ${groups[cat].length}`));
    const list = el("div", "fact-list");
    groups[cat].forEach((f) => list.appendChild(factCard(f, false, S.newFactIds.includes(f.id))));
    g.appendChild(list);
    main.appendChild(g);
  });
  if (!facts.length) {
    main.appendChild(el("p", "panel-sub", "还没有记录。先在画像里聊几句。"));
    const go = el("button", "btn", "去画像");
    go.type = "button";
    go.style.marginTop = "16px";
    go.onclick = () => setView("onboarding");
    main.appendChild(go);
  }
  $app.appendChild(main);
}

/* ---------- 边学边练：项目 ---------- */

const STAGES = [
  { value: 0, label: "只学了概念", hint: "刚看过定义和例子，还没动手" },
  { value: 1, label: "做过小任务", hint: "在树上交过一两次二十分钟任务" },
  { value: 2, label: "学完一块", hint: "走完一个分支，或学过一门相关课" },
  { value: 3, label: "做过项目", hint: "交过一个完整的练手项目" },
];

/* 来源 kind 的中文名，与 server/projects.py 的 KIND_LABELS 保持一致 */
const SRC_KIND_CN = {
  competition: "竞赛", open_source: "开源", open_problem: "公开题", dataset: "公开数据",
  course_project: "课程大作业", innovation_program: "创新项目",
};

const STATUS_CN = { pass: "做到", partial: "部分做到", fail: "还没做到" };
const STATUS_MARK = { pass: "✓", partial: "~", fail: "!" };

function fmtTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function downloadBlob(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

function projectTabs(active, mineCount) {
  const nav = el("nav", "ws-tabs");
  [["find", "找项目"], ["sources", "来源"], ["mine", mineCount ? `我的项目 · ${mineCount}` : "我的项目"]].forEach(([key, label]) => {
    const b = el("button", `ws-tab${key === active ? " on" : ""}`, label);
    b.type = "button";
    b.onclick = () => { S.projectTab = key; setView("projects"); };
    nav.appendChild(b);
  });
  return nav;
}

async function renderProjects() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  $app.innerHTML = "";
  $app.appendChild(skeleton(2));
  const [ctx, mine] = await Promise.all([
    api("GET", `/api/projects/context?uid=${S.uid}`).catch(() => null),
    api("GET", `/api/projects/mine?uid=${S.uid}`).catch(() => ({ projects: [] })),
  ]);
  if (stale(seq)) return;
  const tab = S.projectTab || "find";
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("项目", "学完一块之后，找一个有公开来源的真项目练手。成果打成一个压缩包交上来，按五条标准看它像不像这个项目要的东西。"));
  $app.appendChild(projectTabs(tab, (mine.projects || []).length));
  if (tab === "mine") { renderMine(mine.projects || []); return; }
  if (tab === "sources") { renderSources(); return; }

  const t = trail();
  const field = FIELD_TREES[t.code];
  const node = field ? currentOnPath(field, t.done) : null;
  const form = S.projectForm || {
    direction: (ctx && ctx.direction) || t.code || "ai",
    stage: ctx ? ctx.stage : 0,
    keywords: "",
  };
  S.projectForm = form;

  const panel = el("div", "panel project-form");
  panel.appendChild(el("h3", "section-label", "方向"));
  const dirs = el("div", "field-switch");
  const paintDirs = () => {
    dirs.innerHTML = "";
    Object.entries(FIELD_TREES).forEach(([code, f]) => {
      const b = el("button", "field-chip" + (code === form.direction ? " on" : ""), `<span>${esc(f.name)}</span>`);
      b.type = "button";
      b.onclick = () => { form.direction = code; paintDirs(); };
      dirs.appendChild(b);
    });
  };
  paintDirs();
  panel.appendChild(dirs);

  panel.appendChild(el("h3", "section-label", "你现在走到哪"));
  const stages = el("div", "stage-pick");
  stages.setAttribute("role", "radiogroup");
  const paintStages = () => {
    stages.innerHTML = "";
    STAGES.forEach((st) => {
      const b = el("button", "stage-opt" + (st.value === form.stage ? " on" : ""), `<b>${st.label}</b><small>${st.hint}</small>`);
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", st.value === form.stage ? "true" : "false");
      b.onclick = () => { form.stage = st.value; paintStages(); };
      stages.appendChild(b);
    });
  };
  paintStages();
  panel.appendChild(stages);
  if (ctx && ctx.reason) panel.appendChild(el("p", "form-note", `按你的记录预选：${esc(ctx.reason)}。不对就改。`));

  panel.appendChild(el("h3", "section-label", "想练的关键词（可选）"));
  const row = el("div", "chat-input-row");
  const kw = el("input");
  kw.value = form.keywords;
  kw.placeholder = node ? `例如：${node.label}` : "例如：数据可视化、问卷、证明";
  kw.maxLength = 40;
  kw.setAttribute("aria-label", "关键词");
  kw.addEventListener("input", () => { form.keywords = kw.value; });
  const go = el("button", "btn", "找项目");
  go.type = "button";
  row.append(kw, go);
  panel.appendChild(row);
  $app.appendChild(panel);

  const out = el("div", "project-results");
  $app.appendChild(out);

  const run = async () => {
    go.disabled = true; go.textContent = "正在查…";
    out.innerHTML = "";
    const wait = el("div", "panel");
    wait.appendChild(el("p", "panel-sub", "正在逐个来源检索公开项目，第一次大约十几秒。查到什么就给什么，查不到会如实写。"));
    out.appendChild(wait);
    try {
      const r = await api("POST", "/api/projects/search", {
        uid: S.uid, direction: form.direction, stage: form.stage, keywords: form.keywords.trim(),
      });
      if (stale(seq)) return;
      S.projectResult = r;
      paintResults(out, r);
    } catch (e) {
      out.innerHTML = "";
      out.appendChild(el("div", "note-box", `检索失败（如实说明）：${esc(e.message)}`));
    }
    go.disabled = false; go.textContent = "找项目";
  };
  go.onclick = run;
  kw.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) run(); });
  if (S.projectResult && S.projectResult.query && S.projectResult.query.direction === form.direction && S.projectResult.query.stage === form.stage) {
    paintResults(out, S.projectResult);
  }
}

function paintResults(out, r) {
  out.innerHTML = "";
  const list = r.sources || [];
  const live = list.filter((s) => s.ok && s.live).length;
  const snap = list.filter((s) => s.ok && s.snapshot).length;
  const bad = list.filter((s) => !s.ok).length;
  const sources = el("details", "source-status");
  sources.appendChild(el("summary", "", `查了 ${list.length} 个来源：实时 ${live} 个 · 快照 ${snap} 个${bad ? ` · 没查到 ${bad} 个` : ""}`));
  const chips = el("div", "src-chips");
  list.forEach((s) => {
    const ok = s.ok;
    chips.appendChild(el("span", `src-chip ${ok ? "ok" : "bad"}`,
      `${ok ? "✓" : "✕"} ${esc(s.name)}<i>${ok ? `${s.count} 条${s.snapshot ? " · 快照" : ""}` : esc(s.error || "没查到")}</i>`));
  });
  sources.appendChild(chips);
  const head = el("div", "results-head");
  head.appendChild(el("h3", "panel-title", r.items && r.items.length ? `找到 ${r.items.length} 个可以做的项目` : "这次没有找到合适的项目"));
  head.appendChild(el("p", "panel-sub", `${esc(r.query.direction_name)} · ${esc(r.query.stage_label)}${r.query.keywords ? ` · 「${esc(r.query.keywords)}」` : ""} · 检索于 ${fmtTime(r.retrieved_at)}${r.voice === "llm" ? "" : " · 规则版挑选"}`));
  out.append(head, sources);

  if (!r.items || !r.items.length) {
    out.appendChild(el("div", "note-box", esc(r.empty_reason || "来源里没有和这个方向、这个阶段对得上的公开项目。我们不补一个假的；可以换个关键词，或照下面的路线自己去看。")));
  }
  (r.items || []).forEach((p) => out.appendChild(projectCard(p)));

  if (r.routes && r.routes.length) {
    const routes = el("details", "panel routes");
    routes.open = !(r.items && r.items.length);
    routes.appendChild(el("summary", "", `去哪找更多 · ${r.routes.length} 个来源`));
    routes.appendChild(el("p", "panel-sub", "这些来源要你自己去看（需要登录、按届发布，或没有公开接口）。每条写了点哪里、搜什么。"));
    r.routes.forEach((rt) => {
      const item = el("div", "route");
      item.innerHTML = `<p class="route-name"><a href="${esc(rt.url)}" target="_blank" rel="noopener">${esc(rt.name)} ↗</a><span>${esc(rt.kind_label || "")}${rt.cadence ? " · " + esc(rt.cadence) : ""}</span></p><p class="route-how">${esc(rt.manual_route)}</p>${rt.search_terms && rt.search_terms.length ? `<p class="route-terms">搜：${rt.search_terms.map((t) => `<code>${esc(t)}</code>`).join(" ")}</p>` : ""}`;
      routes.appendChild(item);
    });
    out.appendChild(routes);
  }
}

function projectCard(p) {
  const card = el("article", "panel project-card");
  const top = el("div", "project-top");
  top.appendChild(el("h3", "project-name", `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>`));
  if (p.difficulty) top.appendChild(el("span", "badge plain", esc(p.difficulty)));
  card.appendChild(top);
  card.appendChild(el("p", "project-src", `${esc(p.source_name)} · 检索于 ${fmtTime(p.retrieved_at)}${p.snapshot ? " · 快照" : ""}${p.deadline ? ` · ${p.closed ? `已截止（${esc(p.deadline)}），可当练习` : `截止 ${esc(p.deadline)}`}` : ""}`));
  const dl = el("dl", "project-facts");
  dl.innerHTML = `<dt>在练什么</dt><dd>${esc(p.practices || "来源里没写明。")}</dd><dt>大概要做什么</dt><dd>${esc(p.todo || "来源里没写明，打开链接看原题。")}</dd>${p.why_fit ? `<dt>为什么是现在</dt><dd>${esc(p.why_fit)}</dd>` : ""}`;
  card.appendChild(dl);
  if (p.evidence_quote) card.appendChild(el("p", "project-quote", `原文：「${esc(p.evidence_quote)}」`));
  const acts = el("div", "submit-actions");
  const pick = el("button", "btn small", p.picked ? "已在我的项目里" : "就练这个");
  pick.type = "button";
  pick.disabled = !!p.picked;
  pick.onclick = async () => {
    pick.disabled = true;
    try {
      const saved = await api("POST", "/api/projects/pick", { uid: S.uid, id: p.id });
      p.picked = true;
      S.projectId = saved.id;
      setView("project");
    } catch (e) { toast(e.message); pick.disabled = false; }
  };
  const open = el("a", "btn small secondary", "打开来源 ↗");
  open.href = p.url; open.target = "_blank"; open.rel = "noopener";
  acts.append(pick, open);
  card.appendChild(acts);
  return card;
}

/* 「来源」标签页：/api/projects/sources 的全量来源清单（后端逐个人工核对过的地图） */
async function renderSources() {
  const seq = S.renderSeq;
  let reg = null;
  try {
    reg = await api("GET", "/api/projects/sources");
  } catch (e) {
    if (stale(seq)) return;
    $app.appendChild(el("div", "note-box", `来源清单读取失败（如实说明）：${esc(e.message)}`));
    return;
  }
  if (stale(seq)) return;
  const trailCode = trail().code;
  const list = reg.sources || [];
  const dirName = (code) => (FIELD_TREES[code] && FIELD_TREES[code].name) || code;
  const stageLabel = (v) => { const st = STAGES.find((s) => s.value === v); return st ? st.label : ""; };
  const inCurrent = (s) => (s.directions || []).includes(trailCode);
  const sorted = [...list].sort((a, b) => Number(inCurrent(b)) - Number(inCurrent(a)));

  const intro = el("p", "panel-sub sources-intro",
    `「找项目」背后的全部来源，共 ${list.length} 个，每条都由人工实际访问核对过（${fmtTime(reg.generated_at)}）。` +
    `其中一部分能实时检索，在「找项目」里直接出结果；其余按「怎么找」的路线自己去看。查不到就如实说查不到。`);
  $app.appendChild(intro);

  const grid = el("div", "src-grid");
  sorted.forEach((s) => {
    const card = el("article", "panel src-card");
    const top = el("div", "src-top");
    top.appendChild(el("h3", "src-name",
      s.home_url ? `<a href="${esc(s.home_url)}" target="_blank" rel="noopener">${esc(s.name)} ↗</a>` : esc(s.name)));
    if (s.kind && SRC_KIND_CN[s.kind]) top.appendChild(el("span", "kind-badge", SRC_KIND_CN[s.kind]));
    card.appendChild(top);

    if ((s.directions || []).length) {
      const chips = el("div", "src-chips-row");
      s.directions.forEach((c) => chips.appendChild(el("span", "mini-chip" + (c === trailCode ? " on" : ""), esc(dirName(c)))));
      card.appendChild(chips);
    }
    if ((s.stage_fit || []).length) {
      card.appendChild(el("p", "src-meta",
        `适合：${s.stage_fit.map((v) => stageLabel(v)).filter(Boolean).join(" / ")}`));
    }
    if (s.cadence) card.appendChild(el("p", "src-cadence", esc(s.cadence)));
    if (s.manual_route) card.appendChild(el("p", "route-how clamp", `怎么找：${esc(s.manual_route)}`));
    if ((s.search_terms || []).length) {
      const terms = el("p", "route-terms", "搜：" + s.search_terms.slice(0, 4).map((t) => `<code>${esc(t)}</code>`).join(" "));
      card.appendChild(terms);
    }
    grid.appendChild(card);
  });
  $app.appendChild(grid);
}

function renderMine(list) {
  const panel = el("div", "panel");
  if (!list.length) {
    panel.appendChild(el("p", "panel-sub", "还没有选定项目。在「找项目」里挑一个「就练这个」。"));
    const go = el("button", "btn ghost", "去找项目");
    go.type = "button";
    go.style.marginTop = "16px";
    go.onclick = () => { S.projectTab = "find"; setView("projects"); };
    panel.appendChild(go);
    $app.appendChild(panel);
    return;
  }
  const rows = el("div", "fact-list");
  list.forEach((p) => {
    const last = (p.reviews || [])[0];
    const row = el("button", "mine-row");
    row.type = "button";
    row.innerHTML = `<span class="mine-name">${esc(p.name)}</span><span class="mine-meta">${esc(p.source_name || "")} · ${last ? `最近一次 ${last.passed}/${last.total} 条做到` : "还没交"}</span>`;
    row.onclick = () => { S.projectId = p.id; setView("project"); };
    rows.appendChild(row);
  });
  panel.appendChild(rows);
  $app.appendChild(panel);
}

async function renderProject() {
  const seq = S.renderSeq;
  if (!S.projectId) { S.projectTab = "mine"; setView("projects"); return; }
  $app.innerHTML = "";
  $app.appendChild(skeleton(2));
  let p;
  try {
    p = await api("GET", `/api/projects/${S.projectId}?uid=${S.uid}`);
  } catch (e) {
    if (stale(seq)) return;
    S.projectTab = "mine"; setView("projects"); toast(e.message); return;
  }
  if (stale(seq)) return;
  $app.innerHTML = "";
  const back = el("button", "linkish back-link", "← 我的项目");
  back.type = "button";
  back.onclick = () => { S.projectTab = "mine"; setView("projects"); };
  $app.appendChild(back);
  $app.appendChild(workspaceHead(esc(p.name)));
  $app.appendChild(el("div", "ws-status", `<span><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.source_name)} ↗</a></span><span>检索于 ${fmtTime(p.retrieved_at)}</span>`));

  const spec = el("div", "panel");
  const dl = el("dl", "project-facts");
  dl.innerHTML = `<dt>在练什么</dt><dd>${esc(p.practices || "来源里没写明。")}</dd><dt>大概要做什么</dt><dd>${esc(p.todo || "来源里没写明，打开链接看原题。")}</dd>`;
  spec.appendChild(dl);
  spec.appendChild(el("h3", "section-label", "压缩包里至少要有"));
  const need = el("ul", "criteria");
  [
    "README.md（放在最外层）：题目和来源链接、我做了什么、结果在哪、怎么复现、还没做完的",
    "results/：你自己做出来的图、表、输出或报告，每个文件在 README 里有一句说明",
    "代码类项目放 src/ 或 .ipynb，并写清怎么运行；调查、写作类项目写清数据来源和方法",
    "只交 .zip，不超过 20 MB；大数据集只放样例，写下载链接",
  ].forEach((t) => need.appendChild(el("li", "", esc(t))));
  spec.appendChild(need);
  spec.appendChild(el("h3", "section-label", "怎么评"));
  const how = el("ul", "criteria");
  ["说清了要解决什么问题", "有自己做出来的结果", "和项目要求对得上", "别人能照着核对或复现", "说清了没做完的和下一步"]
    .forEach((t) => how.appendChild(el("li", "", t)));
  spec.appendChild(how);
  spec.appendChild(el("p", "form-note", "只看压缩包里的文件，不评价你这个人，也不猜你没写出来的东西。"));
  const acts = el("div", "submit-actions");
  const tpl = el("button", "btn small secondary", "下载 README 模板");
  tpl.type = "button";
  tpl.onclick = async () => {
    const res = await fetch(`/api/projects/${p.id}/readme?uid=${S.uid}`);
    if (!res.ok) { toast("模板下载失败"); return; }
    downloadBlob(await res.blob(), "README.md");
  };
  const sample = el("button", "btn small ghost", "看一份示例压缩包");
  sample.type = "button";
  sample.onclick = async () => {
    const res = await fetch(`/api/projects/${p.id}/sample.zip?uid=${S.uid}`);
    if (!res.ok) { toast("示例生成失败"); return; }
    downloadBlob(await res.blob(), "示例成果.zip");
  };
  acts.append(tpl, sample);
  spec.appendChild(acts);
  $app.appendChild(spec);

  const up = el("div", "panel");
  up.appendChild(el("h3", "panel-title", "交成果"));
  const drop = el("label", "dropzone");
  const file = el("input");
  file.type = "file"; file.accept = ".zip,application/zip"; file.hidden = true;
  drop.append(file, el("span", "", "把 .zip 拖到这里，或点这里选文件"));
  up.appendChild(drop);
  const result = el("div", "review-out");
  up.appendChild(result);
  $app.appendChild(up);

  const send = async (f) => {
    if (!f) return;
    if (!/\.zip$/i.test(f.name)) { toast("只收 .zip 文件"); return; }
    if (f.size > 20 * 1024 * 1024) { toast("压缩包超过 20 MB"); return; }
    drop.classList.add("busy");
    drop.querySelector("span").textContent = `正在看「${f.name}」…`;
    try {
      const res = await fetch(`/api/projects/${p.id}/submit?uid=${S.uid}`, {
        method: "POST", headers: { "Content-Type": "application/zip" }, body: f,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error((data && data.detail) || `提交失败 (${res.status})`);
      paintReview(result, data);
      result.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      result.innerHTML = "";
      result.appendChild(el("div", "note-box", esc(e.message)));
    }
    drop.classList.remove("busy");
    drop.querySelector("span").textContent = "再交一版：把 .zip 拖到这里，或点这里选文件";
    file.value = "";
  };
  file.onchange = () => send(file.files[0]);
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); send(e.dataTransfer.files[0]); });

  if (p.reviews && p.reviews.length) paintReview(result, p.reviews[0], true);
}

function paintReview(box, r, old) {
  box.innerHTML = "";
  const sec = el("section", "feedback");
  const head = el("div", "feedback-head");
  const hl = el("div");
  hl.appendChild(el("h3", "", old ? "上一次的评阅" : "评阅"));
  hl.appendChild(el("p", "", `${esc(r.summary || "")}${r.voice === "llm" ? "" : "（规则版）"}`));
  head.appendChild(hl);
  head.appendChild(el("div", "score-ring", `<span class="num">${r.passed}</span>/ ${r.total} 条做到`));
  sec.appendChild(head);
  if ((r.criteria || []).length) {
    const bar = el("div", "pass-bar");
    (r.criteria || []).forEach((c) => {
      const seg = c.status === "pass" ? "ok" : c.status === "partial" ? "part" : "bad";
      bar.appendChild(el("i", seg));
    });
    sec.appendChild(bar);
  }
  const list = el("div", "rubric-list");
  (r.criteria || []).forEach((c) => {
    const ev = (c.evidence || []).filter((e) => e.file)
      .map((e) => `<span class="ev"><code>${esc(e.file)}</code>${e.quote ? `「${esc(e.quote)}」` : ""}</span>`).join("");
    list.appendChild(el("div", `rubric-item ${c.status === "pass" ? "pass" : "fail"} is-${c.status}`,
      `<span class="rubric-mark" aria-label="${STATUS_CN[c.status]}">${STATUS_MARK[c.status]}</span><div><p class="rubric-crit">${esc(c.criterion)}<em>${STATUS_CN[c.status]}</em></p><p class="rubric-comment">${esc(c.comment)}</p>${ev ? `<p class="rubric-ev">${ev}</p>` : ""}${c.fix ? `<p class="rubric-fix">改：${esc(c.fix)}</p>` : ""}</div>`));
  });
  sec.appendChild(list);
  if (r.next_step) sec.appendChild(el("div", "why-box", `<b>下一步　</b>${esc(r.next_step)}`));
  const files = el("details", "inventory");
  if (!(r.inventory || []).length) files.hidden = true;
  files.appendChild(el("summary", "", `压缩包里的 ${(r.inventory || []).length} 个文件`));
  const ul = el("ul");
  (r.inventory || []).forEach((i) => ul.appendChild(el("li", "", `<code>${esc(i.path)}</code><span>${esc(i.kind)} · ${Math.max(1, Math.round(i.size / 1024))} KB</span>`)));
  files.appendChild(ul);
  (r.notes || []).forEach((n) => files.appendChild(el("p", "form-note", esc(n))));
  sec.appendChild(files);
  if (r.fact) {
    const fl = el("div", "fact-list");
    fl.appendChild(factCard(r.fact, false, !old));
    sec.appendChild(fl);
  }
  box.appendChild(sec);
}

/* ---------- 事实卡组件 ---------- */

function factCard(f, editable = false, isNew = false) {
  const card = el("div", `fact-card${isNew ? " new-fact" : ""}`);
  const valueHtml = editable
    ? `<input type="text" value="${esc(f.value)}" />`
    : `<div class="fact-value">${esc(f.value)}</div>`;
  const evidence = (f.evidence || []).map((e) => esc(e.quote ? `「${e.quote}」` : (e.type === "submission" ? `任务提交《${e.task_title || ""}》` : e.type === "project_submission" ? `项目成果《${e.task_title || ""}》` : e.type))).join("；");
  const when = f.source === "behavior" && f.created_at ? ` · ${esc(f.created_at.slice(5, 16).replace("T", " "))}` : "";
  card.innerHTML = `
    ${valueHtml}
    <div class="fact-meta">
      <span class="badge cat-${esc(f.category)}">${CAT_CN[f.category] || esc(f.category)}</span>
      <span class="badge plain">${SRC_CN[f.source] || esc(f.source)}${when}</span>
      ${f.status === "draft" ? '<span class="badge draft">待核对</span>' : ""}
    </div>
    ${evidence ? `<div class="fact-evidence">依据：${evidence}</div>` : ""}
    <div class="fact-actions"></div>`;
  if (!editable) {
    const acts = card.querySelector(".fact-actions");
    const edit = el("button", "linkish", "修改");
    edit.type = "button";
    const valueNode = card.querySelector(".fact-value");
    edit.onclick = async () => {
      if (valueNode.querySelector("input")) return;
      const input = el("input"); input.type = "text"; input.value = f.value;
      valueNode.innerHTML = ""; valueNode.appendChild(input); input.focus();
      const save = async () => {
        const v = input.value.trim();
        if (!v || v === f.value) { valueNode.textContent = f.value; return; }
        try {
          await api("PATCH", `/api/me/facts/${f.id}`, { uid: S.uid, value: v });
          f.value = v; valueNode.textContent = v;
          toast("已修改，之后读到的是新版本");
        } catch (e) { toast(e.message); valueNode.textContent = f.value; }
      };
      input.addEventListener("blur", save);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.isComposing) input.blur();
        if (e.key === "Escape") { input.value = f.value; input.blur(); }
      });
    };
    const del = el("button", "linkish danger", "删除");
    del.type = "button";
    del.onclick = async () => {
      try {
        await api("DELETE", `/api/me/facts/${f.id}?uid=${S.uid}`);
        card.classList.add("is-dismissed");
        del.disabled = true; del.textContent = "已删除"; edit.disabled = true;
        toast("已删除，之后不再读取这一条");
      } catch (e) { toast(e.message); }
    };
    acts.append(edit, del);
  }
  return card;
}

/* ---------- 导航 & 启动 ---------- */

document.querySelectorAll(".nav-btn").forEach((b) => {
  b.addEventListener("click", () => {
    if (!S.uid) return;
    if (b.dataset.workspace === "portrait") setView(S.portraitTab || "onboarding");
    else setView(b.dataset.view);
  });
});
document.getElementById("brandHome").addEventListener("click", () => setView("home"));

(async function boot() {
  const t0 = performance.now();
  try {
    const h = await api("GET", "/api/health");
    applyLlmPill(h.llm);
  } catch (_) { /* 健康检查失败不挡页面 */ }
  if (S.uid) {
    try {
      const st = await api("GET", `/api/onboard/result?uid=${S.uid}`);
      document.getElementById("userNickname").textContent = S.nickname;
      S.portraitTab = st.state && st.state.phase === "done" ? "confirm" : "onboarding";
      S.resume = "today";
      await ensurePortrait();
    } catch (_) {
      S.uid = "";
      S.resume = "login";
      localStorage.removeItem("rg_uid");
    }
  }
  setView("home");
  // 开场最多停 0.7 秒：数据到了就走，不再固定等 1.4 秒
  const splash = document.getElementById("boot");
  setTimeout(() => {
    if (!splash) return;
    splash.classList.add("out");
    setTimeout(() => splash.remove(), 600);
  }, Math.max(0, 700 - (performance.now() - t0)));
})();
