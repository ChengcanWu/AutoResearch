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
    hint: "向下滚动",
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
      .map(([k, v]) => `<li><b>${k}</b><span>${v}</span></li>`).join("");
    sec.innerHTML = `<p class="hero-kicker">${page.kicker}</p><h2>${page.title}</h2>`
      + `<p class="land-lead">${page.lead}</p>`
      + (points ? `<ul class="land-points">${points}</ul>` : "")
      + (page.hint ? `<p class="snap-hint">${page.hint}</p>` : "");
    if (i === HOME_PAGES.length - 1) {
      const btn = el("button", "btn land-cta", "立即开始体验");
      btn.type = "button";
      btn.onclick = beginExperience;
      sec.appendChild(btn);
    }
    snap.appendChild(sec);
  });
  const rail = el("div", "fella-index");
  rail.appendChild(el("span", "fella-mark"));
  HOME_PAGES.forEach((page, i) => {
    const b = el("button", "fella-no" + (i === 0 ? " on" : ""), String(i).padStart(2, "0"));
    b.type = "button";
    b.setAttribute("aria-label", `第 ${i + 1} 屏`);
    b.onclick = () => {
      const sec = snap.querySelectorAll(".snap")[i];
      snap.scrollTo({ top: sec ? sec.offsetTop : 0, behavior: "smooth" });
    };
    rail.appendChild(b);
  });
  const progress = el("div", "home-progress");
  progress.appendChild(el("i"));
  land.append(canvas, snap, rail, progress);
  $app.appendChild(land);
  stopField = mountSketch(canvas, snap, rail, progress);
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
  // 00 台阶通向一扇门：先认识你，再走下一步
  () => {
    const door = [[0.22, 0.12], [0.22, -0.46], ...arcPts(0.5, -0.46, 0.28, Math.PI, Math.PI * 2, 32), [0.78, 0.12]];
    const inner = [[0.3, 0.12], [0.3, -0.44], ...arcPts(0.5, -0.44, 0.2, Math.PI, Math.PI * 2, 28), [0.7, 0.12]];
    const stairs = [[-0.95, 0.74], [-0.62, 0.74], [-0.62, 0.53], [-0.3, 0.53], [-0.3, 0.32], [0.02, 0.32], [0.02, 0.12], [0.95, 0.12]];
    return [
      { pts: stairs },
      { pts: door },
      { pts: inner, accent: true },
      { pts: ring(-0.46, 0.38, 0.05, 20), accent: true },
    ];
  },
  // 01 一问一答的两个气泡
  () => {
    const q = [...arcPts(-0.36, -0.5, 0.1, Math.PI * 1.05, Math.PI * 2.25, 28), [-0.36, -0.33], [-0.36, -0.28]];
    return [
      { pts: bubble(-0.92, -0.78, 0.18, -0.12, 0.12, -0.62, -1) },
      { pts: q, accent: true },
      { pts: ring(-0.36, -0.2, 0.018, 8), accent: true },
      { pts: bubble(-0.18, 0.06, 0.92, 0.62, 0.12, 0.56, 1) },
      { pts: [[0.0, 0.22], [0.72, 0.22]] },
      { pts: [[0.0, 0.34], [0.6, 0.34]] },
      { pts: [[0.0, 0.46], [0.38, 0.46]] },
    ];
  },
  // 02 罗盘：指针指向一个方向
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
    out.push({ pts: [l, n, rr], accent: true });
    out.push({ pts: [l, s, rr] });
    out.push({ pts: ring(0, 0.04, 0.035, 12) });
    out.push({ pts: [[-0.05, -0.8], [-0.05, -0.96], [0.05, -0.8], [0.05, -0.96]] });
    return out;
  },
  // 03 秒表：二十分钟
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
    out.push({ pts: arcPts(c[0], c[1], 0.4, -Math.PI / 2, Math.PI / 6, 40), accent: true });
    out.push({ pts: [c, [c[0] + Math.cos(Math.PI / 6) * 0.44, c[1] + Math.sin(Math.PI / 6) * 0.44]], accent: true });
    out.push({ pts: ring(c[0], c[1], 0.03, 12) });
    return out;
  },
  // 04 一页提交，逐条打勾
  () => {
    const page = [[-0.58, -0.8], [0.2, -0.8], [0.44, -0.56], [0.44, 0.8], [-0.58, 0.8], [-0.58, -0.8]];
    const out = [{ pts: page }, { pts: [[0.2, -0.8], [0.2, -0.56], [0.44, -0.56]] }];
    [-0.3, 0.02, 0.34].forEach((y, i) => {
      if (i < 2) out.push({ pts: [[-0.42, y], [-0.35, y + 0.07], [-0.22, y - 0.08]], accent: true });
      else out.push({ pts: ring(-0.33, y, 0.06, 20) });
      out.push({ pts: [[-0.1, y], [0.28, y]] });
    });
    out.push({ pts: [[-0.42, 0.6], [0.1, 0.6]] });
    return out;
  },
  // 05 一棵往右长的树，走过的路用主色
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
    return [
      node(R, 0.06, true), edge(R, A, true), node(A, 0.055, true), edge(A, A2, true), node(A2, 0.055, true),
      edge(A2, C2, true), node(C2, 0.05, true),
      edge(A, A1), node(A1, 0.05), edge(A2, C1), node(C1, 0.05),
      edge(R, B), node(B, 0.055), edge(B, B1), node(B1, 0.05), edge(B, B2), node(B2, 0.05),
    ];
  },
];

function strokeLength(pts) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  return L;
}

function sampleSketch(strokes, n) {
  // 沿全部笔画等距取 n 个点；返回 {xy, acc}，顺序即笔画顺序
  const lens = strokes.map((s) => strokeLength(s.pts));
  const total = lens.reduce((a, b) => a + b, 0) || 1;
  const xy = new Float32Array(n * 2);
  const acc = new Uint8Array(n);
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
      k += 1;
    }
  });
  return { xy, acc, length: total };
}

function scrollTarget(scroller) {
  // 每屏前 40% 停住不动（读字），40%–85% 之间换图，之后停在新图上
  const secs = [...scroller.querySelectorAll(".snap")];
  const st = scroller.scrollTop;
  let a = 0;
  while (a < secs.length - 2 && st >= secs[a + 1].offsetTop) a += 1;
  const span = Math.max(1, secs[a + 1].offsetTop - secs[a].offsetTop);
  const raw = (st - secs[a].offsetTop) / span;
  const t = Math.min(1, Math.max(0, (raw - 0.4) / 0.45));
  return Math.min(secs.length - 1, a + t);
}

function mountSketch(canvas, scroller, rail, progress) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const nos = [...rail.querySelectorAll(".fella-no")];
  const mark = rail.querySelector(".fella-mark");
  const bar = progress.querySelector("i");
  const INK = "rgb(237, 241, 238)";
  const ACCENT = "rgb(127, 209, 194)";
  let W = 0; let H = 0; let cx = 0; let cy = 0; let size = 0; let dot = 1.35;
  let figs = [];
  let N = 0;
  let shown = [];
  let phase = 0;
  let target = 0;
  let intro = still ? 1 : 0;
  let raf = 0;
  let introStart = 0;

  const build = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth; H = window.innerHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const narrow = W < 920;
    size = narrow ? Math.min(W * 0.34, H * 0.2) : Math.min(H * 0.32, W * 0.2);
    cx = narrow ? W * 0.5 : W * 0.66;
    cy = narrow ? H * 0.27 : H * 0.5;
    dot = narrow ? 1.15 : 1.35;
    const spacing = narrow ? 4.2 : 4.6;
    const raws = SKETCHES.map((f) => f());
    const need = raws.map((st) => Math.ceil((st.reduce((s, x) => s + strokeLength(x.pts), 0) * size) / spacing));
    N = Math.max(...need);
    figs = raws.map((st, k) => {
      const f = sampleSketch(st, N);
      // 每张图只点亮 need[k] 颗，保证各图点距一致；其余粒子跟着走但不可见
      const vis = new Uint8Array(N);
      for (let j = 0; j < need[k]; j++) vis[Math.floor((j * N) / need[k])] = 1;
      f.vis = vis;
      return f;
    });
    shown = Array.from({ length: N }, (_, i) => {
      const ang = unitHash(i, 2) * Math.PI * 2;
      const rad = 1.2 + unitHash(i, 3) * 0.9;
      return [Math.cos(ang) * rad, Math.sin(ang) * rad];
    });
  };

  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  const draw = () => {
    ctx.clearRect(0, 0, W, H);
    const a = Math.min(figs.length - 1, Math.floor(phase));
    const b = Math.min(figs.length - 1, a + 1);
    const T = phase - a;
    const A = figs[a];
    const B = figs[b];
    const introE = ease(intro);
    let lastStyle = "";
    for (let i = 0; i < N; i++) {
      const f = i / N;
      const local = still ? (T > 0.5 ? 1 : 0) : ease(Math.min(1, Math.max(0, (T - f * 0.35) / 0.65)));
      const ax = A.xy[i * 2]; const ay = A.xy[i * 2 + 1];
      const bx = B.xy[i * 2]; const by = B.xy[i * 2 + 1];
      let x = ax + (bx - ax) * local;
      let y = ay + (by - ay) * local;
      const lift = Math.sin(Math.PI * local);
      if (lift > 0.001) {
        const dx = bx - ax; const dy = by - ay;
        const len = Math.hypot(dx, dy) || 1;
        const amp = (0.08 + unitHash(i, 7) * 0.14) * (unitHash(i, 9) > 0.5 ? 1 : -1) * lift;
        x += (-dy / len) * amp;
        y += (dx / len) * amp;
      }
      if (introE < 1) {
        x = shown[i][0] + (x - shown[i][0]) * Math.min(1, Math.max(0, (intro - f * 0.3) / 0.7));
        y = shown[i][1] + (y - shown[i][1]) * Math.min(1, Math.max(0, (intro - f * 0.3) / 0.7));
      }
      const vis = A.vis[i] + (B.vis[i] - A.vis[i]) * local;
      const alpha = vis * (1 - 0.35 * lift) * Math.min(1, intro * 1.4);
      if (alpha < 0.03) continue;
      const style = (local < 0.5 ? A.acc[i] : B.acc[i]) ? ACCENT : INK;
      if (style !== lastStyle) { ctx.fillStyle = style; lastStyle = style; }
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.arc(cx + x * size, cy + y * size, dot * (1 - 0.2 * lift), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  };

  const syncRail = () => {
    const active = Math.min(nos.length - 1, Math.round(phase));
    nos.forEach((d, i) => d.classList.toggle("on", i === active));
    if (mark && nos[active]) mark.style.transform = `translateY(${nos[active].offsetTop}px)`;
    const limit = Math.max(1, scroller.scrollHeight - scroller.clientHeight);
    if (bar) bar.style.width = `${Math.min(1, scroller.scrollTop / limit) * 100}%`;
  };

  const tick = (now) => {
    raf = 0;
    if (!canvas.isConnected) return;
    let moving = false;
    if (intro < 1) {
      if (!introStart) introStart = now;
      intro = Math.min(1, (now - introStart) / 1600);
      moving = true;
    }
    const gap = target - phase;
    if (Math.abs(gap) > 0.0005) {
      phase += still ? gap : gap * 0.14;
      moving = true;
    } else {
      phase = target;
    }
    draw();
    syncRail();
    if (moving) raf = requestAnimationFrame(tick);
  };
  const wake = () => { if (!raf) raf = requestAnimationFrame(tick); };
  const onScroll = () => { target = scrollTarget(scroller); wake(); };
  const onResize = () => { build(); onScroll(); };

  build();
  target = scrollTarget(scroller);
  phase = target;
  scroller.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onResize);
  wake();

  return () => {
    cancelAnimationFrame(raf);
    raf = 0;
    scroller.removeEventListener("scroll", onScroll);
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
  hero.appendChild(el("p", "hero-kicker", "启研 · 第一步"));
  hero.appendChild(el("h2", "", "怎么称呼你？"));
  hero.appendChild(el("p", "hero-lead", "不用真实姓名。进去之后是六个工作区：今日、画像、方向、任务、项目、记录，随时可以换。"));
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
    <p class="panel-sub">OpenAI 兼容接口，改的是整台服务器用的模型。密钥只写在服务器的 .env，不会出现在页面回显里。只有在服务器本机，或填了管理员口令才能改。</p>
    <label>接口地址<input name="base" value="https://api.deepseek.com/v1" /></label>
    <label>API Key<input name="key" type="password" placeholder="sk-…" autocomplete="off" /></label>
    <label>模型名<input name="model" value="deepseek-flash" /></label>
    <label>管理员口令<input name="admin" type="password" placeholder="服务器设了 ADMIN_TOKEN 才需要" autocomplete="off" /></label>
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
      // 管理员口令走请求头，所以这里不用 api()
      const res = await fetch("/api/llm/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": box.admin.value.trim() },
        body: JSON.stringify({ base_url: box.base.value.trim(), api_key: box.key.value.trim(), model: box.model.value.trim() }),
      });
      let r = null;
      try { r = await res.json(); } catch (_) { /* no body */ }
      if (!res.ok) throw new Error((r && r.detail) || `请求失败 (${res.status})`);
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

Object.entries(FIELD_TREES).forEach(([code, f]) => { f.code = code; });

/* 任务 4 的方向路径（docs/paths/）：有路径的方向画成「6 步主干 + 原有节点」。
   主干讲「这一学期走到哪」，原有节点讲「二十分钟能做什么」，两种尺度分开画。
   原有节点挂到哪一步，照 docs/paths/改树建议.md §3、§4、§7、§8 的改动清单。 */
const CHAIN_ATTACH = {
  math: { 1: ["定义", "证明"], 3: ["结构"] },
  ai: { 2: ["数据", "模型怎么学/评价"], 3: ["模型怎么学/损失"], 6: ["用起来"] },
  psy: { 1: ["知觉/错觉"], 2: ["知觉/注意", "记忆", "决策"] },
  econ: { 1: ["约束"], 2: ["激励"], 3: ["市场"] },
};

function findTwig(root, labelPath) {
  let node = root;
  for (const label of labelPath.split("/")) {
    node = (node.children || []).find((c) => c.label === label);
    if (!node) return null;
  }
  return node;
}

function cloneTwig(node) {
  return { label: node.label, intro: node.intro, children: (node.children || []).map(cloneTwig) };
}

function applyPaths(paths) {
  Object.entries(CHAIN_ATTACH).forEach(([code, attach]) => {
    const field = FIELD_TREES[code];
    const path = paths && paths[code];
    if (!field || !path || field.chain || !(path.steps || []).length) return;
    const old = field.root;
    const steps = path.steps.map((st) => ({
      label: st.name,
      intro: `先弄懂：${st.focus}`,
      done_when: st.done_when,
      stage: st.step,
      main: true,
      // 挂上来的整支和这一步同名（如经济第 2 步「激励」挂「激励」）时，直接挂它的子节点，免得出现「激励 — 激励」
      children: (attach[st.step] || []).map((lp) => findTwig(old, lp)).filter(Boolean).map(cloneTwig)
        .flatMap((tw) => (tw.label === st.name.split("：")[0] && tw.children.length ? tw.children : [tw])),
    }));
    field.root = stampTree({ label: path.name, intro: path.goal, virtual: true, children: steps }, code);
    field.chain = true;
    field.sourceDoc = path.source_doc;
  });
}

function entryNode(field) {
  return pathNodes(field)[0];
}

function stepOf(field, nodeId) {
  // 节点所在的主干步骤：主干步骤的 id 是「方向.序号」，往下的节点都以它为前缀
  if (!field.chain || !nodeId) return null;
  const parts = nodeId.split(".");
  return flattenField(field.root).byId[parts.slice(0, 2).join(".")] || null;
}

function findProjectsForStep(code, step) {
  S.projectForm = { direction: code, stage: { 1: 0, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3 }[step] || 0, pathStep: step, keywords: "" };
  S.projectResult = null;
  S.projectTab = "find";
  setView("projects");
}

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
    if (!node.virtual) out.push(node);  // 主干的虚拟根只用来挂六步，不算一个节点
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
  const MAIN_W = narrow ? 140 : 212;
  const NODE_H = 34;
  const PAD = narrow ? 24 : 30;
  const shift = field.root.virtual ? 1 : 0;
  const colX = (depth) => {
    const d = depth - shift;
    if (!field.chain) return d * COL;
    return d === 0 ? 0 : MAIN_W + (COL - NODE_W) + (d - 1) * COL;
  };
  const wOf = (node) => (node.main ? MAIN_W : NODE_W);
  const pos = {};
  let row = 0;
  let depthMax = 0;
  const place = (node, depth) => {
    depthMax = Math.max(depthMax, depth);
    const kids = node.children || [];
    if (!kids.length) {
      pos[node.id] = { x: colX(depth), y: row * ROW };
      row += 1;
      return;
    }
    kids.forEach((k) => place(k, depth + 1));
    const first = pos[kids[0].id].y;
    const last = pos[kids[kids.length - 1].id].y;
    // 主干步骤放在它那组节点的第一行，六步从上到下排成一条线
    pos[node.id] = { x: colX(depth), y: node.main ? first : (first + last) / 2 };
  };
  place(field.root, 0);
  const width = colX(depthMax) + (depthMax - shift === 0 ? MAIN_W : NODE_W) + PAD * 2;
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

  if (field.chain) {
    // 主干：六步之间一条粗线，走过的部分用主色
    const mains = Object.values(byId).filter((n) => n.main).sort((m, n) => m.stage - n.stage);
    mains.slice(1).forEach((node, i) => {
      const a = pos[mains[i].id];
      const b = pos[node.id];
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", String(PAD + 18)); line.setAttribute("x2", String(PAD + 18));
      line.setAttribute("y1", String(PAD + a.y + NODE_H)); line.setAttribute("y2", String(PAD + b.y));
      const passed = done.has(mains[i].id) && (done.has(node.id) || here === node.id || (here || "").startsWith(node.id + "."));
      line.setAttribute("class", "frontier-trunk" + (passed ? " is-past" : ""));
      svg.appendChild(line);
    });
  }

  Object.values(byId).forEach((node) => {
    if (!node.parent || byId[node.parent].virtual) return;
    const a = pos[node.parent];
    const b = pos[node.id];
    const x1 = PAD + a.x + wOf(byId[node.parent]);
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
    if (node.virtual) return;
    const flags = [
      "frontier-node",
      node.main ? "is-main" : "",
      node.id === picked ? "is-pick" : "",
      onPickPath(node.id) && node.id !== picked ? "is-path" : "",
      done.has(node.id) ? "is-past" : "",
      here === node.id ? "is-now" : "",
      animate ? "reveal" : "",
    ].filter(Boolean).join(" ");
    const short = node.main ? node.label.split("：")[0] : node.label;
    const btn = el("button", flags, node.main ? `<b class="step-no">${node.stage}</b><span>${esc(short)}</span>` : esc(node.label));
    btn.type = "button";
    btn.title = node.main ? `第 ${node.stage} 步 · ${node.label}` : node.label;
    btn.style.left = PAD + pos[node.id].x + "px";
    btn.style.top = PAD + pos[node.id].y + "px";
    btn.style.width = wOf(node) + "px";
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
  const entry = entryNode(field);
  if (node.main) sheet.appendChild(el("p", "sheet-label", `主干 · 第 ${node.stage} 步（这一学期走到哪）`));
  sheet.appendChild(el("h3", "", esc(node.label)));
  sheet.appendChild(el("p", "sheet-intro", esc(node.intro || "")));
  if (node.main && node.done_when) {
    sheet.appendChild(el("div", "why-box", `<b>做完怎样算过了　</b>${esc(node.done_when)}`));
    const find = el("button", "btn secondary", "找能交出这一步的项目");
    find.type = "button";
    find.onclick = () => { document.getElementById("nodeSheet")?.remove(); findProjectsForStep(field.code, node.stage); };
    sheet.appendChild(find);
  }
  if (node.id === entry.id && ctx.why) {
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
  const courses = el("div", "course-block");
  courses.appendChild(el("h4", "", "课程"));
  courses.appendChild(el("div", "course-status", "检索中"));
  sheet.appendChild(courses);
  loadCourses(courses, node.label || field.query);
  if (node.id === entry.id && !ctx.chosen) {
    const choose = el("button", "btn", ctx.hasCurrent ? "确认切换方向" : "确认这个方向");
    choose.type = "button";
    choose.onclick = () => ctx.onChoose();
    sheet.appendChild(choose);
  }
  sheet.querySelector(".sheet-x").focus({ preventScroll: true });
}

async function renderCards() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  let saved = trail();
  let serverTasks = [];
  try {
    const taskRes = await api("GET", `/api/tasks?uid=${S.uid}`);
    if (stale(seq)) return;
    serverTasks = taskRes.tasks || [];
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
  const legend = el("div", "tree-legend");
  $app.append(switcher, recLine, confirmBar, stage, legend);

  const paint = () => {
    const chain = FIELD_TREES[current].chain;
    legend.innerHTML = (chain ? '<span class="main"><i>1</i>主干：这一学期走到哪（任务 4 的路径）</span>' : "")
      + '<span class="now"><i></i>你在这里</span><span class="past"><i></i>已走过</span><span><i></i>还可以去</span>'
      + `<span>${chain ? "节点：二十分钟一件事；点主干看过关标准" : "点任一节点看说明"}</span>`;
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
        ? `已切换到「${field.name}」，从「${entryNode(field).label}」重新开始`
        : `已确认「${field.name}」，从「${entryNode(field).label}」开始`);
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
      // 第一次在方向区接过服务端已选的方向时，顺手按已交的任务把进度对上
      saveTrail(mergeTrail(code, serverTasks));
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
    const r = await api("GET", `/api/explore/courses?query=${encodeURIComponent(query)}&limit=6`);
    if (!r.ok) { status.textContent = `检索失败（如实说明）：${r.error || "未知错误"}`; return; }
    status.remove();
    const mark = r.source === "catalog" ? "快照" : "实时";
    const head = box.querySelector("h4");
    if (head) head.dataset.source = mark;
    if (!r.items || !r.items.length) {
      box.appendChild(el("div", "course-status", `「${query}」没有对上的课。查的是本学期公开课快照，对不上就空着。`));
      return;
    }
    r.items.forEach((it) => {
      const name = it.name || it.courseName || "(未命名课程)";
      const names = it.teacher_names && it.teacher_names.length ? it.teacher_names : [];
      const teacher = names.length ? names.map((n) => `<button type="button" class="teacher-link" data-teacher="${esc(n)}">${esc(n)}</button>`).join(" ") : esc(it.teacher || it.teachers || "");
      const dept = it.department || it.dept || "";
      const row = el("div", "course-item",
        `${esc(name)}<br><span class="meta">${teacher}${teacher && dept ? " · " : ""}${esc(dept)}${r.term ? " · " + esc(r.term) : ""}</span>`);
      row.querySelectorAll(".teacher-link").forEach((b) => {
        b.onclick = () => showTeacher(b.dataset.teacher);
      });
      box.appendChild(row);
    });
  } catch (e) {
    status.textContent = `检索失败（如实说明）：${e.message}`;
  }
}

async function showTeacher(name) {
  document.getElementById("teacherSheet")?.remove();
  const sheet = el("div", "node-sheet teacher-sheet");
  sheet.id = "teacherSheet";
  sheet.innerHTML = `<div class="sheet-head"><span class="sheet-kicker">授课老师</span><button class="sheet-x" type="button">关闭</button></div>`;
  sheet.querySelector(".sheet-x").onclick = () => sheet.remove();
  sheet.appendChild(el("h3", "", esc(name)));
  const status = el("p", "sheet-intro", "正在读本学期快照…");
  sheet.appendChild(status);
  document.body.appendChild(sheet);
  try {
    const r = await api("GET", `/api/explore/teachers?name=${encodeURIComponent(name)}`);
    if (!r.ok) { status.textContent = r.error || "快照里没有这位老师。"; return; }
    status.remove();
    if (r.departments && r.departments.length) {
      sheet.appendChild(el("p", "sheet-kicker", esc(r.departments.join(" · "))));
    }
    if (r.bio) sheet.appendChild(el("p", "sheet-intro", esc(r.bio)));
    else sheet.appendChild(el("p", "sheet-intro", "没有对上北京大学的公开学者简介，这里只列出本学期教的课。"));
    sheet.appendChild(el("p", "sheet-label", `本学期课程 · ${r.term || ""}`));
    (r.courses || []).forEach((c) => {
      sheet.appendChild(el("div", "course-item", `${esc(c.name || "")}<br><span class="meta">${esc([c.department, c.credits].filter(Boolean).join(" · "))}</span>`));
    });
  } catch (e) {
    status.textContent = e.message;
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

  const stepNote = () => {
    const step = stepOf(field, node.id);
    if (!step) return;
    // 主干步骤要交的是一学期尺度的东西；二十分钟任务只是入门，过关材料去「项目」里找
    const note = el("div", "note-box step-note");
    note.innerHTML = `${node.main ? "这是" : "这一节点属于"}路径第 ${step.stage} 步「${esc(step.label)}」。这一步做完要交：${esc(step.done_when)}`;
    const find = el("button", "linkish", "找能交出它的项目");
    find.type = "button";
    find.onclick = () => findProjectsForStep(code, step.stage);
    note.appendChild(find);
    p.appendChild(note);
  };

  const showFinished = () => {
    p.innerHTML = "";
    paintHead();
    if (S.lastFeedback && S.lastFeedbackTaskId === task.id) renderFeedbackInto(p);
    if (node.main) stepNote();
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
    const doneHere = listed.filter((tk) => tk.status === "done" && tk.direction === code && tk.id !== task.id).length + 1;
    if (doneHere >= PROJECT_AFTER_TASKS || !next) {
      const proj = el("button", next ? "btn secondary" : "btn", "学完一块了，找个项目练手");
      proj.type = "button";
      proj.title = `在「${field.name}」交过 ${doneHere} 次小任务`;
      proj.onclick = () => goFindProjects();
      acts.appendChild(proj);
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
  stepNote();

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

function goFindProjects(keywords) {
  // 进「项目 · 找项目」，方向和阶段交给服务端按记录预选（/api/projects/context）
  S.projectForm = null;
  S.projectResult = null;
  S.projectTab = "find";
  if (keywords) S.projectKeywords = keywords;
  setView("projects");
}

function openProject(pid) {
  S.projectId = pid;
  setView("project");
}

const PROJECT_AFTER_TASKS = 3; // 在一个方向交过几次小任务之后，开始建议找项目练手

async function renderToday() {
  const seq = S.renderSeq;
  await ensurePortrait();
  if (stale(seq)) return;
  const [taskRes, onboard, mine] = await Promise.all([
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
  const doneTasks = ((taskRes && taskRes.tasks) || []).filter((t) => t.status === "done" && t.direction === saved.code).length;
  const projects = (mine && mine.projects) || [];
  const toFix = projects.find((p) => p.status === "reviewed" && p.reviews[0] && p.reviews[0].passed < p.reviews[0].total);
  const toSubmit = projects.find((p) => p.status === "picked");

  // 每条建议：一个主动作 + 至多一个备选，落到一件具体的事
  let title; let why; let primary; let alt = null;
  const goView = (label, view) => ({ label, run: () => setView(view) });
  if (!field && !talked) {
    title = "先聊五个问题";
    why = "它还不认识你。五个问题，大约五分钟：年级、基础、好奇什么、习惯怎么学。每一问都可以选「不知道」。";
    primary = goView("去画像", "onboarding");
  } else if (!field && drafts) {
    title = `核对它记下的 ${drafts} 条`;
    why = "对话里记下的内容还是草稿。改掉不对的、划掉不属实的，方向建议才会按你来。";
    primary = goView("去核对", "confirm");
  } else if (!field) {
    title = "选定一个方向";
    why = "方向区有六棵树，已经按你的画像标出建议。确认其中一棵，任务会从它的起点开始。";
    primary = goView("去方向区", "cards");
  } else if (toFix) {
    let detail = null;
    try { detail = await api("GET", `/api/projects/${toFix.id}?uid=${S.uid}`); } catch (_) { /* 拿不到详情就用概要 */ }
    if (stale(seq)) return;
    const last = (detail && detail.reviews && detail.reviews[0]) || toFix.reviews[0];
    title = `把《${toFix.name}》再改一处`;
    why = `上次评阅 ${last.passed} / ${last.total} 条做到。${last.next_step || "按评阅里第一条没做到的标准补一处，再交一版。"}`;
    primary = { label: "去改这一处", run: () => openProject(toFix.id) };
    if (node) alt = { label: `先继续「${node.label}」`, run: () => setView("workbench") };
  } else if (toSubmit) {
    title = `交《${toSubmit.name}》的成果`;
    why = "这个项目已经选定，还没交。按项目页的要求打成一个 .zip：README、results/、代码或方法。没做完也可以先交一版，评阅会指出先补哪里。";
    primary = { label: "去交成果", run: () => openProject(toSubmit.id) };
    if (node) alt = { label: `先继续「${node.label}」`, run: () => setView("workbench") };
  } else if (doneTasks >= PROJECT_AFTER_TASKS) {
    title = "找一个项目练手";
    why = `你在「${field.name}」已经交过 ${doneTasks} 次小任务。二十分钟的任务练的是一个点，项目练的是把点连起来：从公开来源找一个真题，做完交一个压缩包。`;
    primary = { label: "去找项目", run: () => goFindProjects() };
    if (node) alt = { label: `先继续「${node.label}」`, run: () => setView("workbench") };
  } else if (node) {
    title = `继续「${node.label}」`;
    why = node.intro;
    primary = goView("去做这一步", "workbench");
  } else {
    title = `「${field.name}」这条路已经走到头`;
    why = "可以找一个项目把这一路学的用起来，或者回方向区换一棵树。";
    primary = { label: "去找项目", run: () => goFindProjects() };
    alt = { label: "回方向区", run: () => setView("cards") };
  }

  $app.innerHTML = "";
  const wrap = el("div", "stagger");
  wrap.appendChild(workspaceHead("今日"));
  const status = el("div", "ws-status");
  status.appendChild(el("span", "", field ? esc(field.name) : "还没有方向"));
  if (node) status.appendChild(el("span", "", `正在「${esc(node.label)}」`));
  if (doneTasks) status.appendChild(el("span", "", `交过 ${doneTasks} 次小任务`));
  if (projects.length) status.appendChild(el("span", "", `${projects.length} 个项目`));
  wrap.appendChild(status);
  const card = el("div", "nba-card");
  card.appendChild(el("h3", "nba-title", esc(title)));
  card.appendChild(el("p", "nba-why", esc(why)));
  const act = el("div", "submit-actions");
  const go = el("button", "btn", esc(primary.label));
  go.type = "button";
  go.onclick = primary.run;
  act.appendChild(go);
  if (alt) {
    const other = el("button", "btn ghost", esc(alt.label));
    other.type = "button";
    other.onclick = alt.run;
    act.appendChild(other);
  }
  card.appendChild(act);
  wrap.appendChild(card);
  $app.appendChild(wrap);
}

/* ---------- ⑧ me 页 ---------- */

async function renderMe() {
  const seq = S.renderSeq;
  const r = await api("GET", `/api/me/facts?uid=${S.uid}`);
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
  [["find", "找项目"], ["mine", mineCount ? `我的项目 · ${mineCount}` : "我的项目"]].forEach(([key, label]) => {
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

  const t = trail();
  const field = FIELD_TREES[t.code];
  const node = field ? currentOnPath(field, t.done) : null;
  const pathsBy = (ctx && ctx.paths) || {};
  const form = S.projectForm || {
    direction: (ctx && ctx.direction) || t.code || "ai",
    stage: ctx ? ctx.stage : 0,
    keywords: S.projectKeywords || "",
  };
  S.projectKeywords = "";
  // 任务 4 的路径：有路径的方向按「第几步」选，没有的按四个阶段选
  const defaultStep = (stage) => ({ 0: 1, 1: 2, 2: 3, 3: 5 }[stage] || 1);
  // 优先按方向树上的位置（当前节点属于路径第几步），其次按服务端记录推
  const treeStep = field && field.chain && node && t.code === form.direction ? stepOf(field, node.id) : null;
  if (!form.pathStep) {
    form.pathStep = treeStep ? treeStep.stage : ((ctx && ctx.path_step) || defaultStep(form.stage));
    form.fromTree = !!treeStep;
  }
  S.projectForm = form;

  const panel = el("div", "panel project-form");
  panel.appendChild(el("h3", "section-label", "方向"));
  const dirs = el("div", "field-switch");
  const paintDirs = () => {
    dirs.innerHTML = "";
    Object.entries(FIELD_TREES).forEach(([code, f]) => {
      const b = el("button", "field-chip" + (code === form.direction ? " on" : ""), `<span>${esc(f.name)}</span>`);
      b.type = "button";
      b.onclick = () => { form.direction = code; paintDirs(); paintStages(); };
      dirs.appendChild(b);
    });
  };
  paintDirs();
  panel.appendChild(dirs);

  const stageLabel = el("h3", "section-label");
  const stages = el("div", "stage-pick");
  stages.setAttribute("role", "radiogroup");
  const stageNote = el("p", "form-note");
  const radio = (b, on) => { b.type = "button"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", on ? "true" : "false"); };
  function paintStages() {
    stages.innerHTML = "";
    const path = pathsBy[form.direction];
    stages.classList.toggle("path", !!path);
    if (path) {
      stageLabel.textContent = "你在路径的哪一步";
      path.steps.forEach((st) => {
        const on = st.step === form.pathStep;
        const b = el("button", "stage-opt" + (on ? " on" : ""), `<i>第 ${st.step} 步</i><b>${esc(st.name)}</b><small>过关：${esc(st.done_when)}</small>`);
        radio(b, on);
        b.onclick = () => { form.pathStep = st.step; form.stage = st.project_stage; paintStages(); };
        stages.appendChild(b);
      });
      const cur = path.steps.find((st) => st.step === form.pathStep);
      if (cur) form.stage = cur.project_stage;
      const why = form.fromTree && form.pathStep === (treeStep && treeStep.stage)
        ? `按你在方向树上的位置预选：第 ${form.pathStep} 步，不对就改。`
        : (ctx && ctx.reason ? `按你的记录预选：${ctx.reason}，不对就改。` : "");
      stageNote.textContent = `六步来自任务 4 的「${path.name}」路径（${path.source_doc}）。按你选的这一步找能交出它过关材料的项目。${why}`;
    } else {
      stageLabel.textContent = "你现在走到哪";
      STAGES.forEach((st) => {
        const on = st.value === form.stage;
        const b = el("button", "stage-opt" + (on ? " on" : ""), `<b>${st.label}</b><small>${st.hint}</small>`);
        radio(b, on);
        b.onclick = () => { form.stage = st.value; form.pathStep = defaultStep(st.value); paintStages(); };
        stages.appendChild(b);
      });
      stageNote.textContent = ctx && ctx.reason ? `按你的记录预选：${ctx.reason}。不对就改。` : "";
    }
  }
  paintStages();
  panel.append(stageLabel, stages, stageNote);

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
        path_step: pathsBy[form.direction] ? form.pathStep : 0,
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
  if (S.projectResult && S.projectResult.query && S.projectResult.query.direction === form.direction && S.projectResult.query.stage === form.stage
    && (S.projectResult.query.path_step || 0) === (pathsBy[form.direction] ? form.pathStep : 0)) {
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
  head.appendChild(el("p", "panel-sub", `${esc(r.query.direction_name)} · ${r.query.path_step ? `路径第 ${r.query.path_step} 步「${esc(r.query.path_step_name)}」` : esc(r.query.stage_label)}${r.query.keywords ? ` · 「${esc(r.query.keywords)}」` : ""} · 检索于 ${fmtTime(r.retrieved_at)}${r.voice === "llm" ? "" : " · 规则版挑选"}`));
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
  card.appendChild(el("p", "project-src", `${p.path_step ? `对应路径第 ${p.path_step} 步 · ` : ""}${esc(p.source_name)} · 检索于 ${fmtTime(p.retrieved_at)}${p.snapshot ? " · 快照" : ""}${p.deadline ? ` · ${p.closed ? `已截止（${esc(p.deadline)}），可当练习` : `截止 ${esc(p.deadline)}`}` : ""}`));
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

function renderMine(list) {
  const panel = el("div", "panel");
  if (!list.length) {
    panel.appendChild(el("p", "panel-sub", "还没有选定项目。在「找项目」里挑一个「就练这个」。"));
    $app.appendChild(panel);
    return;
  }
  const rows = el("div", "fact-list");
  list.forEach((p) => {
    const last = (p.reviews || [])[0];
    const row = el("button", "mine-row");
    row.type = "button";
    const state = p.status === "done" ? `做完了 · ${last.passed}/${last.total} 条做到` : (last ? `最近一次 ${last.passed}/${last.total} 条做到，还可以再改` : "还没交");
    row.innerHTML = `<span class="mine-name">${esc(p.name)}</span><span class="mine-meta">${esc(p.source_name || "")} · ${state}</span>`;
    row.onclick = () => { S.projectId = p.id; setView("project"); };
    rows.appendChild(row);
  });
  panel.appendChild(rows);
  $app.appendChild(panel);
}

async function renderProject() {
  const seq = S.renderSeq;
  if (!S.projectId) { S.projectTab = "mine"; setView("projects"); return; }
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
      paintReview(result, data, false, (p.reviews || [])[0]);
      p.reviews = [data].concat(p.reviews || []);
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

  if (p.reviews && p.reviews.length) paintReview(result, p.reviews[0], true, p.reviews[1]);
}

function paintReview(box, r, old, prev) {
  box.innerHTML = "";
  const sec = el("section", "feedback");
  if (prev && typeof prev.passed === "number") {
    const d = r.passed - prev.passed;
    sec.appendChild(el("p", `review-delta ${d > 0 ? "up" : d < 0 ? "down" : ""}`,
      d > 0 ? `比上一版多做到 ${d} 条（${prev.passed} → ${r.passed}）` : d < 0 ? `比上一版少了 ${-d} 条（${prev.passed} → ${r.passed}），看看是不是漏交了文件` : `和上一版一样是 ${r.passed} 条，看下面「下一步」改的那一处有没有落到文件里`));
  }
  const head = el("div", "feedback-head");
  const hl = el("div");
  hl.appendChild(el("h3", "", old ? "上一次的评阅" : "评阅"));
  hl.appendChild(el("p", "", `${esc(r.summary || "")}${r.voice === "llm" ? "" : "（规则版）"}`));
  head.appendChild(hl);
  head.appendChild(el("div", "score-ring", `<span class="num">${r.passed}</span>/ ${r.total} 条做到`));
  sec.appendChild(head);
  const list = el("div", "rubric-list");
  (r.criteria || []).forEach((c) => {
    const ev = (c.evidence || []).filter((e) => e.file)
      .map((e) => `<span class="ev"><code>${esc(e.file)}</code>${e.quote ? `「${esc(e.quote)}」` : ""}</span>`).join("");
    list.appendChild(el("div", `rubric-item ${c.status === "pass" ? "pass" : "fail"} is-${c.status}`,
      `<span class="rubric-mark" aria-label="${STATUS_CN[c.status]}">${STATUS_MARK[c.status]}</span><div><p class="rubric-crit">${esc(c.criterion)}<em>${STATUS_CN[c.status]}</em></p><p class="rubric-comment">${esc(c.comment)}</p>${ev ? `<p class="rubric-ev">${ev}</p>` : ""}${c.fix ? `<p class="rubric-fix">改：${esc(c.fix)}</p>` : ""}</div>`));
  });
  sec.appendChild(list);
  if (r.next_step) sec.appendChild(el("div", "why-box", `<b>下一步　</b>${esc(r.next_step)}`));
  if (r.passed === r.total) {
    const acts = el("div", "submit-actions");
    const nextOne = el("button", "btn", "找下一个项目（难一档）");
    nextOne.type = "button";
    nextOne.onclick = () => {
      const f = S.projectForm || {};
      S.projectForm = f.direction ? { ...f, stage: Math.min(3, (f.stage || 0) + 1), pathStep: Math.min(6, (f.pathStep || 1) + 1) } : null;
      S.projectResult = null; S.projectTab = "find"; setView("projects");
    };
    const today = el("button", "btn ghost", "回今日");
    today.type = "button";
    today.onclick = () => setView("today");
    acts.append(nextOne, today);
    sec.appendChild(acts);
  }
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
    const [h, paths] = await Promise.all([api("GET", "/api/health"), api("GET", "/api/paths").catch(() => null)]);
    applyLlmPill(h.llm);
    if (paths) applyPaths(paths.paths);
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
