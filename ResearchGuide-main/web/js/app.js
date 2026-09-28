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
  if (name !== "cards") document.getElementById("nodeSheet")?.remove();
  const header = document.querySelector(".site-header");
  const footer = document.querySelector(".site-footer");
  if (header) header.hidden = home;
  if (footer) footer.hidden = home;
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.workspace === WORKSPACE[name]);
    b.disabled = !S.uid;
  });
  $nav.hidden = !inApp;
  $header.hidden = home || !S.uid;
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function render() {
  if (S.view === "home") { renderHome(); return; }
  if (!S.uid && S.view !== "login") { renderLogin(); return; }
  switch (S.view) {
    case "login": renderLogin(); break;
    case "onboarding": renderOnboarding(); break;
    case "confirm": await renderConfirm(); break;
    case "cards": await renderCards(); break;
    case "workbench": await renderWorkbench(); break;
    case "me": await renderMe(); break;
    case "today":
    default: await renderToday(); break;
  }
}

/* ---------- 首页：六屏下滑，粒子随滚动重组 ---------- */

const HOME_PAGES = [
  {
    kicker: "00",
    title: "先认识你，<br>再走下一步。",
    lead: "面向本科一、二年级。它不是问答框，而是一条可以回头看的科研入门。",
    extra: `<div class="marquee" aria-hidden="true"><div>问答画像<span></span>方向推荐<span></span>小任务<span></span>获取反馈<span></span>持续成长<span></span>问答画像<span></span>方向推荐<span></span>小任务</div></div><p class="snap-hint">继续往下。形状会散开，再聚成下一步。</p><ol class="beat-list"><li><b>01</b><div><strong>问答画像</strong><p class="line">先用几轮对话问清你现在的位置、已有基础，和对什么好奇。</p></div></li><li><b>02</b><div><strong>方向推荐</strong><p class="line">直接给出此刻值得试的方向，并写明为什么是你。</p></div></li><li><b>03</b><div><strong>小任务</strong><p class="line">不先丢一长串材料。只派一件二十分钟内能做完的事。</p></div></li><li><b>04</b><div><strong>获取反馈</strong><p class="line">按事先说好的标准看你交上来的东西，不评价你这个人。</p></div></li><li><b>05</b><div><strong>持续成长</strong><p class="line">把这次结果记下来，再决定下一件最值得做的事。</p></div></li></ol>`,
  },
  {
    kicker: "01",
    title: "问答画像",
    lead: "几轮对话，勾出你现在的位置、基础和好奇。它只记你自己说的，不替你编一段人设。",
    extra: `<ul class="transcript"><li><i>问</i>你现在在哪，对什么好奇？可以点选项，也可以自己说。</li><li><i>答</i>说得具体最好。年级、卡在哪、想试什么，都算数。</li><li><i>或</i>不知道也可以。它会记下“还不确定”，而不是替你填一个答案。</li></ul><ul class="field-list"><li><div><b>位置</b><p class="line">年级、专业，或者你现在停在哪一步。</p></div></li><li><div><b>基础</b><p class="line">已经会的，和明确还没碰过的。</p></div></li><li><div><b>好奇</b><p class="line">想试的问题。一时说不清，也先留着。</p></div></li></ul>`,
  },
  {
    kicker: "02",
    title: "方向推荐",
    lead: "直接给出此刻值得试的方向。每条都要能对上你刚说过的话，不拿一段通用介绍来凑。",
    extra: `<ul class="spec-list tall"><li><b>01</b><div><strong>为什么是你</strong><p class="line">理由引用你的原话：你的位置、基础或好奇，至少对上其中一件。</p></div></li><li><b>02</b><div><strong>相关的真实课程</strong><p class="line">从北大教务公开课里找。找不到就说找不到，不编课名和老师。</p></div></li><li><b>03</b><div><strong>一篇入门读物</strong><p class="line">先给读得动的那一篇，用来上手，不是一份书单。</p></div></li></ul>`,
  },
  {
    kicker: "03",
    title: "小任务",
    lead: "方向先不展开成阅读清单。它只给你一件二十分钟内能做完的事。",
    extra: `<p class="stat"><em>20</em><span>分钟</span></p><p class="note">可能是读一小节、跑一个小例子，或回答一个具体问题。做完要留下看得见的结果：一段话、一张图，或一个跑出来的输出。没做完也可以交，它只根据你交上来的东西说话，不根据你“本来可以怎样”。</p><ol class="time-bars"><li><b>05</b><i></i></li><li><b>10</b><i></i></li><li><b>15</b><i></i></li><li><b>20</b><i></i></li></ol><ul class="check-rows"><li class="ok"><i></i><div><strong>做完</strong><p class="line">只一件事，做到能交为止。</p></div></li><li><i></i><div><strong>留下</strong><p class="line">结果要能被看见，空口说做了不算。</p></div></li><li><i></i><div><strong>记下</strong><p class="line">这次实际做了什么，写回你的画像。</p></div></li></ul>`,
  },
  {
    kicker: "04",
    title: "获取反馈",
    lead: "按标准逐条看过你的提交。评价的是这件事做成了没有，不是你这个人适不适合做科研。",
    extra: `<ul class="rubric-rows"><li><span>对事</span><p class="line">只看这一次交上来的内容，不翻旧账，也不推测你的潜力。</p><b style="width:86%"></b></li><li><span>标准</span><p class="line">事先说好的那几条。做到哪条、缺哪条，分开写。</p><b style="width:64%"></b></li><li><span>证据</span><p class="line">用你留下的结果说话。没有结果，就明确说缺证据。</p><b style="width:72%"></b></li><li class="no"><span>不对人</span><p class="line">不说你行不行、聪不聪明、适不适合。人不是被打分的对象。</p><b style="width:18%"></b></li></ul>`,
  },
  {
    kicker: "05",
    title: "持续成长",
    lead: "记住这次证据，再决定下一件最值得做的事。下一步仍然只是一件事，不是一份新计划。",
    extra: `<ol class="grow-stack"><li><b>01</b><div><strong>认识</strong><p class="line">你说过的位置、基础和好奇还在，不用每次从头介绍自己。</p></div></li><li><b>02</b><div><strong>行动</strong><p class="line">做过的那件小任务留着，完成与否都以提交为准。</p></div></li><li><b>03</b><div><strong>记住</strong><p class="line">反馈写回画像。下一次先看这些证据，再开口。</p></div></li><li><b>04</b><div><strong>再下一步</strong><p class="line">只再给一件最值得做的事。做完，再进入下一轮。</p></div></li></ol>`,
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
    sec.innerHTML = `<p class="hero-kicker">${i === 0 ? "启研 · AI RESEARCH MENTOR" : page.kicker}</p><h2>${page.title}</h2><p class="land-lead">${page.lead}</p>${page.extra}`;
    if (i === HOME_PAGES.length - 1) {
      const btn = el("button", "btn land-cta", "立即开始体验");
      btn.onclick = beginExperience;
      sec.appendChild(btn);
    }
    snap.appendChild(sec);
  });
  const rail = el("div", "fella-index");
  const mark = el("span", "fella-mark");
  rail.appendChild(mark);
  HOME_PAGES.forEach((page, i) => {
    const b = el("button", "fella-no" + (i === 0 ? " on" : ""), page.kicker);
    b.type = "button";
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
  stopField = runField(canvas, snap, rail, progress);
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

function unitHash(i, salt) {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

function pathSegs(pts, closed) {
  const n = pts.length;
  const seg = [];
  let total = 0;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % n];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1e-4;
    seg.push({ a, b, len });
    total += len;
  }
  return { seg, total };
}

function ink(pts, opt = {}) {
  const closed = !!opt.closed;
  const step = opt.step || 0.00128;
  const width = opt.width || 0.0072;
  const rows = opt.rows || 5;
  const { seg, total } = pathSegs(pts, closed);
  if (!seg.length || total < 1e-4) return [];
  const count = Math.max(rows, Math.round(total / step));
  const out = [];
  for (let k = 0; k < count; k++) {
    let d = ((k + 0.5) / count) * total;
    let s = seg[0];
    for (const item of seg) {
      if (d <= item.len) { s = item; break; }
      d -= item.len;
      s = item;
    }
    const t = d / s.len;
    const x = s.a[0] + (s.b[0] - s.a[0]) * t;
    const y = s.a[1] + (s.b[1] - s.a[1]) * t;
    const dx = s.b[0] - s.a[0];
    const dy = s.b[1] - s.a[1];
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len;
    const ny = dx / len;
    for (let r = 0; r < rows; r++) {
      const off = (rows === 1 ? 0 : (r / (rows - 1) - 0.5)) * width;
      const j = (unitHash(k * rows + r, opt.salt || 3) - 0.5) * width * 0.18;
      out.push([x + nx * (off + j), y + ny * (off + j)]);
    }
  }
  return out;
}

function circle(cx, cy, r, opt) {
  const pts = [];
  const n = Math.max(28, Math.round((Math.PI * 2 * r) / ((opt && opt.step) || 0.00128)));
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  return ink(pts, { ...opt, closed: true });
}

function arcPts(cx, cy, r, a0, a1, n) {
  const pts = [];
  const steps = n || Math.max(12, Math.round(Math.abs(a1 - a0) * r / 0.012));
  for (let i = 0; i <= steps; i++) {
    const a = a0 + (a1 - a0) * (i / steps);
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  return pts;
}

function ellipsePts(cx, cy, rx, ry, rot = 0) {
  const pts = [];
  const n = Math.max(24, Math.round((Math.PI * 2 * Math.max(rx, ry)) / 0.012));
  const c = Math.cos(rot);
  const s = Math.sin(rot);
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const x = Math.cos(a) * rx;
    const y = Math.sin(a) * ry;
    pts.push([cx + x * c - y * s, cy + x * s + y * c]);
  }
  return pts;
}

function smoothOpen(pts, passes = 2) {
  let cur = pts.map((p) => p.slice());
  for (let p = 0; p < passes; p++) {
    const next = [cur[0]];
    for (let i = 0; i < cur.length - 1; i++) {
      const a = cur[i];
      const b = cur[i + 1];
      next.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
      next.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    next.push(cur[cur.length - 1]);
    cur = next;
  }
  return cur;
}

function smoothClosed(pts, passes = 3) {
  let cur = pts.map((p) => p.slice());
  for (let p = 0; p < passes; p++) {
    const next = [];
    const n = cur.length;
    for (let i = 0; i < n; i++) {
      const a = cur[i];
      const b = cur[(i + 1) % n];
      next.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
      next.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    cur = next;
  }
  return cur;
}

function roundRect(x0, y0, x1, y1, r) {
  r = Math.min(r, Math.abs(x1 - x0) / 2, Math.abs(y1 - y0) / 2);
  const pts = [];
  const corners = [
    [x1 - r, y0 + r, -Math.PI / 2, 0],
    [x1 - r, y1 - r, 0, Math.PI / 2],
    [x0 + r, y1 - r, Math.PI / 2, Math.PI],
    [x0 + r, y0 + r, Math.PI, Math.PI * 1.5],
  ];
  corners.forEach(([cx, cy, a0, a1]) => {
    for (let i = 0; i <= 7; i++) {
      const a = a0 + (a1 - a0) * (i / 7);
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
  });
  return pts;
}

function doorPts(x, top, w, h) {
  const r = w * 0.5;
  const left = x - r;
  const right = x + r;
  const bottom = top + h;
  const spring = top + r;
  const pts = [[left, bottom], [left, spring]];
  for (let i = 0; i <= 18; i++) {
    const a = Math.PI + (Math.PI * i) / 18;
    pts.push([x + Math.cos(a) * r, spring + Math.sin(a) * r]);
  }
  pts.push([right, bottom], [left, bottom]);
  return pts;
}

function cat(parts) {
  const out = [];
  parts.forEach((part) => { if (part) part.forEach((p) => out.push(p)); });
  return out;
}

const LINE = { step: 0.00092, width: 0.0082, rows: 6 };
const FINE = { step: 0.00115, width: 0.0056, rows: 4 };

function figureRaw(kind) {
  if (kind === 0) {
    const head = [-0.4, -0.22];
    return cat([
      circle(head[0], head[1], 0.09, LINE),
      ink(arcPts(head[0], 0.08, 0.2, Math.PI * 1.05, Math.PI * 1.95, 40), LINE),
      ink([[head[0], -0.128], [head[0], -0.08]], FINE),
      ink([[-0.18, 0.28], [-0.02, 0.16], [0.16, 0.02], [0.34, -0.12]], LINE),
      circle(-0.18, 0.28, 0.045, LINE),
      circle(-0.02, 0.16, 0.05, LINE),
      circle(0.16, 0.02, 0.055, LINE),
      circle(0.34, -0.12, 0.06, LINE),
      ink(doorPts(0.56, -0.46, 0.22, 0.58), LINE),
      ink([[0.56, -0.46], [0.56, 0.12]], FINE),
    ]);
  }
  if (kind === 1) {
    const face = smoothClosed([
      [-0.02, 0.4], [0.02, 0.24], [0.04, 0.12], [0.1, 0.05],
      [0.12, -0.01], [0.07, -0.045], [0.14, -0.08], [0.22, -0.12],
      [0.14, -0.16], [0.08, -0.2], [0.06, -0.28], [0.0, -0.38],
      [-0.12, -0.48], [-0.26, -0.46], [-0.38, -0.34], [-0.4, -0.16],
      [-0.36, 0.02], [-0.3, 0.2], [-0.2, 0.38],
    ], 3);
    const bubbles = [
      roundRect(0.3, -0.5, 0.74, -0.24, 0.045),
      roundRect(0.26, -0.08, 0.68, 0.16, 0.04),
    ];
    return cat([
      ink(face, { ...LINE, closed: true }),
      circle(0.05, -0.2, 0.018, FINE),
      ink(arcPts(-0.3, -0.12, 0.055, Math.PI * 0.65, Math.PI * 1.45, 16), FINE),
      ink(bubbles[0], { ...LINE, closed: true }),
      ink(bubbles[1], { ...LINE, closed: true }),
      ink([[0.3, -0.3], [0.2, -0.16], [0.3, -0.24]], FINE),
      ink([[0.26, 0.02], [0.16, 0.08], [0.26, 0.1]], FINE),
      circle(0.42, -0.37, 0.012, FINE),
      circle(0.5, -0.37, 0.012, FINE),
      circle(0.58, -0.37, 0.012, FINE),
      circle(0.38, 0.04, 0.012, FINE),
      circle(0.46, 0.04, 0.012, FINE),
      circle(0.54, 0.04, 0.012, FINE),
    ]);
  }
  if (kind === 2) {
    const c = [0.02, 0.02];
    const dest = [[-0.42, -0.5], [0.62, -0.02], [0.18, 0.55]];
    const ticks = [];
    for (let k = 0; k < 12; k++) {
      const a = -Math.PI / 2 + (k / 12) * Math.PI * 2;
      const inner = k % 3 === 0 ? 0.3 : 0.35;
      const outer = k === 0 ? 0.48 : 0.42;
      ticks.push(ink([
        [c[0] + Math.cos(a) * inner, c[1] + Math.sin(a) * inner],
        [c[0] + Math.cos(a) * outer, c[1] + Math.sin(a) * outer],
      ], k % 3 === 0 ? LINE : FINE));
    }
    const paths = [
      [[c[0] - 0.08, c[1] - 0.38], [-0.36, -0.22], dest[0]],
      [[c[0] + 0.4, c[1]], [0.42, -0.2], dest[1]],
      [[c[0] + 0.08, c[1] + 0.38], [0.28, 0.28], dest[2]],
    ];
    return cat([
      circle(c[0], c[1], 0.42, LINE),
      circle(c[0], c[1], 0.1, LINE),
      ...ticks,
      ink([[c[0], c[1]], [c[0] + 0.2, c[1] - 0.2]], LINE),
      ink([[c[0], c[1]], [c[0] - 0.1, c[1] + 0.1]], FINE),
      ink([[c[0] - 0.028, c[1] - 0.56], [c[0] - 0.028, c[1] - 0.68], [c[0] + 0.03, c[1] - 0.56], [c[0] + 0.03, c[1] - 0.68]], FINE),
      ...paths.map((p) => ink(smoothOpen([p[0], p[1], p[2]], 2), LINE)),
      ...dest.flatMap((p) => [circle(p[0], p[1], 0.07, LINE), circle(p[0], p[1], 0.028, FINE)]),
    ]);
  }
  if (kind === 3) {
    const c = [0.16, -0.02];
    const ticks = [];
    for (let k = 0; k < 12; k++) {
      const a = -Math.PI / 2 + (k / 12) * Math.PI * 2;
      const inner = k % 3 === 0 ? 0.3 : 0.35;
      ticks.push(ink([
        [c[0] + Math.cos(a) * inner, c[1] + Math.sin(a) * inner],
        [c[0] + Math.cos(a) * 0.42, c[1] + Math.sin(a) * 0.42],
      ], k % 3 === 0 ? LINE : FINE));
    }
    const hand = (deg, len) => {
      const a = (deg * Math.PI) / 180;
      return [c[0] + Math.sin(a) * len, c[1] - Math.cos(a) * len];
    };
    const boxes = [[-0.62, -0.28], [-0.62, 0.0], [-0.62, 0.28]];
    return cat([
      circle(c[0], c[1], 0.46, LINE),
      ...ticks,
      ink([c, hand(0, 0.16)], LINE),
      ink([c, hand(120, 0.28)], LINE),
      circle(c[0], c[1], 0.028, LINE),
      ...boxes.flatMap((p, i) => {
        const s = 0.1;
        const box = [[p[0], p[1]], [p[0] + s, p[1]], [p[0] + s, p[1] + s], [p[0], p[1] + s]];
        const bits = [ink(box, { ...LINE, closed: true }), ink([[p[0] + 0.16, p[1] + 0.05], [p[0] + 0.26, p[1] + 0.05]], FINE)];
        if (i === 0) bits.push(ink([[p[0] + 0.02, p[1] + 0.05], [p[0] + 0.045, p[1] + 0.08], [p[0] + 0.09, p[1] + 0.02]], LINE));
        return bits;
      }),
    ]);
  }
  if (kind === 4) {
    const card = roundRect(-0.5, -0.48, 0.34, 0.5, 0.06);
    const lines = [-0.28, -0.12, 0.04, 0.2].map((y, i) => ink([[-0.36, y], [-0.36 + (0.42 - i * 0.06), y]], FINE));
    const mark = [0.5, -0.16];
    return cat([
      ink(card, { ...LINE, closed: true }),
      ...lines,
      circle(mark[0], mark[1], 0.16, LINE),
      ink([[mark[0] - 0.07, mark[1] + 0.01], [mark[0] - 0.02, mark[1] + 0.07], [mark[0] + 0.08, mark[1] - 0.08]], LINE),
      ink(arcPts(-0.16, 0.28, 0.16, Math.PI * 0.85, Math.PI * 2.35, 28), LINE),
      circle(-0.02, 0.18, 0.016, FINE),
    ]);
  }
  const trunk = [-0.22, 0.08];
  const leaves = [
    [-0.4, -0.02, 0.4], [-0.08, 0.02, -0.3],
    [-0.34, -0.2, 0.6], [-0.12, -0.22, -0.5],
    [-0.28, -0.38, 0.2], [-0.16, -0.4, -0.4],
    [-0.22, -0.5, 0.1],
  ];
  const nodes = [[-0.02, 0.42], [0.14, 0.22], [0.28, 0.0], [0.4, -0.22], [0.52, -0.44]];
  return cat([
    ink([[trunk[0], 0.52], [trunk[0], -0.05]], LINE),
    ink([[trunk[0], 0.18], [-0.4, -0.02]], LINE),
    ink([[trunk[0], 0.18], [-0.06, 0.02]], LINE),
    ink([[trunk[0], -0.02], [-0.34, -0.22]], LINE),
    ink([[trunk[0], -0.02], [-0.1, -0.18]], LINE),
    ink([[trunk[0], -0.2], [-0.28, -0.42]], LINE),
    ink([[trunk[0], 0.52], [-0.34, 0.66]], FINE),
    ink([[trunk[0], 0.52], [-0.08, 0.64]], FINE),
    ...leaves.map((p) => ink(ellipsePts(p[0], p[1], 0.075, 0.04, p[2]), { ...FINE, closed: true })),
    ink(smoothOpen(nodes, 2), LINE),
    ...nodes.map((p, i) => circle(p[0], p[1], 0.028 + i * 0.008, LINE)),
  ]);
}

const FIGURE_RGB = [
  [0.78, 0.94, 1.0],
  [0.55, 1.0, 0.82],
  [0.62, 0.78, 1.0],
  [0.9, 0.96, 1.0],
  [0.45, 0.95, 0.95],
  [0.7, 1.0, 0.78],
];

function packFigure(raw, rgb, scale, maxN) {
  const pos = new Float32Array(maxN * 3);
  const on = new Float32Array(maxN);
  const col = new Float32Array(maxN * 3);
  const accent = [0.92, 1.0, 0.98];
  for (let i = 0; i < maxN; i++) {
    let x;
    let y;
    let z;
    if (i < raw.length) {
      x = raw[i][0] * scale;
      y = -raw[i][1] * scale;
      z = (unitHash(i, 8) - 0.5) * 0.16;
      on[i] = 1;
    } else {
      const ang = unitHash(i, 2) * Math.PI * 2;
      const rad = 0.4 + unitHash(i, 3) * 2.6;
      x = Math.cos(ang) * rad * 0.85;
      y = (unitHash(i, 5) - 0.42) * 3.1;
      z = (unitHash(i, 4) - 0.5) * 2.4;
      on[i] = 0;
      x += Math.cos(ang) * 0.2;
      y += Math.sin(ang) * rad * 0.15;
    }
    const spark = i % 11 === 0 ? 0.85 : i % 19 === 0 ? 0.4 : 0;
    pos[i * 3] = x;
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = z;
    col[i * 3] = rgb[0] * (1 - spark) + accent[0] * spark;
    col[i * 3 + 1] = rgb[1] * (1 - spark) + accent[1] * spark;
    col[i * 3 + 2] = rgb[2] * (1 - spark) + accent[2] * spark;
  }
  return { pos, on, col, count: raw.length };
}

function scrollPhase(scroller) {
  const secs = [...scroller.querySelectorAll(".snap")];
  const tops = secs.map((s) => s.offsetTop);
  const max = Math.max(1, tops.length - 1);
  const limit = Math.max(1, scroller.scrollHeight - scroller.clientHeight);
  const st = scroller.scrollTop;
  const p = Math.min(1, st / limit);
  if (st >= tops[tops.length - 1]) return { a: max - 1, travel: 1, p };
  let a = 0;
  while (a < max - 1 && st >= tops[a + 1]) a += 1;
  const span = Math.max(1, tops[a + 1] - tops[a]);
  const raw = Math.min(1, Math.max(0, (st - tops[a]) / span));
  let travel = 0;
  const hold = 0.22;
  if (raw >= 0.98) travel = 1;
  else if (raw > hold) travel = (raw - hold) / (0.98 - hold);
  return { a, travel, p };
}

function runField(canvas, scroller, rail, progress) {
  let aborted = false;
  let stop = () => {};
  import("/static/vendor/three.module.js").then((THREE) => {
    if (aborted || !canvas.isConnected) return;
    stop = mountCloud(THREE, canvas, scroller, rail, progress);
  }).catch((err) => console.error(err));
  return () => { aborted = true; stop(); };
}

function mountCloud(THREE, canvas, scroller, rail, progress) {
  const scale = 2.9;
  const raws = [0, 1, 2, 3, 4, 5].map((k) => figureRaw(k));
  const maxN = raws.reduce((m, pts) => Math.max(m, pts.length), 1);
  const shapes = raws.map((pts, i) => packFigure(pts, FIGURE_RGB[i], scale, maxN));

  const geo = new THREE.BufferGeometry();
  const copyAttr = (name, src, size) => {
    geo.setAttribute(name, new THREE.BufferAttribute(src.slice(), size));
  };
  copyAttr("position", shapes[0].pos, 3);
  copyAttr("aNext", shapes[1].pos, 3);
  copyAttr("aOn", shapes[0].on, 1);
  copyAttr("aOnNext", shapes[1].on, 1);
  copyAttr("aColor", shapes[0].col, 3);
  copyAttr("aColorNext", shapes[1].col, 3);

  const uniforms = {
    uMorph: { value: 0 },
    uTime: { value: 0 },
    uMouse: { value: new THREE.Vector3(40, 40, 0) },
    uSize: { value: 1.8 },
  };
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    depthTest: false,
    uniforms,
    vertexShader: `
      attribute vec3 aNext;
      attribute float aOn;
      attribute float aOnNext;
      attribute vec3 aColor;
      attribute vec3 aColorNext;
      uniform float uMorph;
      uniform float uTime;
      uniform vec3 uMouse;
      uniform float uSize;
      varying vec3 vColor;
      varying float vAlpha;
      varying float vGlow;
      float hash(vec3 p){
        p = fract(p * 0.3183099 + vec3(0.11, 0.17, 0.13));
        p *= 17.0;
        return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
      }
      float noise(vec3 p){
        vec3 i = floor(p);
        vec3 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(
          mix(mix(hash(i), hash(i+vec3(1.0,0.0,0.0)), f.x),
              mix(hash(i+vec3(0.0,1.0,0.0)), hash(i+vec3(1.0,1.0,0.0)), f.x), f.y),
          mix(mix(hash(i+vec3(0.0,0.0,1.0)), hash(i+vec3(1.0,0.0,1.0)), f.x),
              mix(hash(i+vec3(0.0,1.0,1.0)), hash(i+vec3(1.0,1.0,1.0)), f.x), f.y),
          f.z);
      }
      vec3 flow(vec3 p){
        float e = 0.2;
        float n1 = noise(p);
        float nx = noise(p + vec3(e, 0.0, 0.0));
        float ny = noise(p + vec3(0.0, e, 0.0));
        float nz = noise(p + vec3(0.0, 0.0, e));
        return vec3(ny - n1, nz - n1, n1 - nx);
      }
      void main(){
        float s1 = fract(sin(float(gl_VertexID) * 12.9898) * 43758.5453);
        float s2 = fract(sin(float(gl_VertexID) * 78.233) * 43758.5453);
        float s3 = fract(sin(float(gl_VertexID) * 45.164) * 43758.5453);
        float t = clamp((uMorph - s1 * 0.08) / 0.92, 0.0, 1.0);
        float arc = sin(t * 3.14159265);
        vec3 burst = vec3(s1, s2, s3) - 0.5;
        vec3 mid = (position + aNext) * 0.5;
        mid.x += burst.x * 7.2 + abs(burst.x) * 5.4 + 1.4;
        mid.y += burst.y * 9.2;
        mid.z += 3.4 + abs(burst.z) * 6.2;
        mid.xy += vec2(-burst.y, burst.x) * 3.2;
        mid += flow(vec3(s1 * 2.2, s2 * 2.2, s3 + uTime * 0.18)) * arc * 2.2;
        mid.x = max(mid.x, -0.15);
        vec3 p = mix(mix(position, mid, t), mix(mid, aNext, t), t);
        p += flow(p * 0.5 + vec3(uTime * 0.05, s2, 0.0)) * (0.004 + arc * 0.42);
        vec2 home = mix(position.xy, aNext.xy, t);
        vec2 d = p.xy - uMouse.xy;
        float dist = length(d);
        float push = 1.0 - smoothstep(0.0, 0.85, dist);
        vec2 dir = normalize(d + vec2(0.0001));
        p.xy += dir * push * 0.28;
        p.xy += vec2(-dir.y, dir.x) * sin(dist * 14.0 - uTime * 5.0) * push * 0.04;
        float flown = length(p.xy - home);
        float stay = aOn * aOnNext;
        float leave = aOn * (1.0 - aOnNext);
        float arrive = aOnNext * (1.0 - aOn);
        float alphaMul = stay
          + leave * (1.0 - smoothstep(0.08, 0.46, t))
          + arrive * smoothstep(0.52, 0.92, t);
        vColor = mix(aColor, aColorNext, smoothstep(0.28, 0.72, t));
        float awayDim = mix(1.0, 0.62, smoothstep(0.9, 4.6, flown));
        vAlpha = alphaMul * awayDim;
        vGlow = push * 0.35;
        if (vAlpha < 0.02) {
          gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
          gl_PointSize = 0.0;
          return;
        }
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        float ndcX = gl_Position.x / max(0.0001, gl_Position.w);
        float side = smoothstep(-1.0, 1.0, ndcX);
        vAlpha *= mix(0.78, 1.0, side);
        float px = uSize * (0.82 + s1 * 0.28) * (1.0 + arc * 0.45);
        gl_PointSize = px * (8.6 / max(0.2, -mv.z));
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vAlpha;
      varying float vGlow;
      void main(){
        vec2 uv = gl_PointCoord - 0.5;
        float d = length(uv);
        if (d > 0.5) discard;
        float core = smoothstep(0.5, 0.02, d);
        float halo = smoothstep(0.5, 0.18, d);
        vec3 col = vColor * (0.72 + core * 1.15) + vec3(vGlow * 0.35);
        gl_FragColor = vec4(col, (halo * 0.42 + core * 0.95) * vAlpha);
      }
    `,
  });

  material.blending = THREE.AdditiveBlending;
  const points = new THREE.Points(geo, material);
  const rig = new THREE.Group();
  rig.add(points);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 40);
  camera.position.set(0, 0, 8.2);
  scene.add(rig);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    premultipliedAlpha: false,
  });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));

  const nos = [...rail.querySelectorAll(".fella-no")];
  const mark = rail.querySelector(".fella-mark");
  const bar = progress.querySelector("i");
  const mouse = uniforms.uMouse.value;
  let raf = 0;
  let slot = -1;

  const onMove = (e) => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    const ndcX = (e.clientX / w) * 2 - 1;
    const ndcY = -((e.clientY / h) * 2 - 1);
    const halfH = Math.tan((camera.fov * Math.PI) / 360) * camera.position.z;
    const halfW = halfH * camera.aspect;
    mouse.x = ndcX * halfW - rig.position.x;
    mouse.y = ndcY * halfH - rig.position.y;
  };
  window.addEventListener("pointermove", onMove);

  const resize = () => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setSize(w, h, false);
    canvas.style.width = "100vw";
    canvas.style.height = "100vh";
    rig.position.set(w < 920 ? 0.2 : 1.9, w < 920 ? -1.05 : 0.04, 0);
    uniforms.uSize.value = (w < 920 ? 1.45 : 1.72) * renderer.getPixelRatio();
  };
  resize();
  window.addEventListener("resize", resize);

  const put = (name, src) => {
    geo.getAttribute(name).array.set(src);
    geo.getAttribute(name).needsUpdate = true;
  };
  const loop = (now) => {
    if (!canvas.isConnected) return;
    const phase = scrollPhase(scroller);
    const max = Math.max(1, HOME_PAGES.length - 1);
    const next = Math.min(phase.a + 1, max);
    if (phase.a !== slot) {
      slot = phase.a;
      put("position", shapes[phase.a].pos);
      put("aNext", shapes[next].pos);
      put("aOn", shapes[phase.a].on);
      put("aOnNext", shapes[next].on);
      put("aColor", shapes[phase.a].col);
      put("aColorNext", shapes[next].col);
    }
    uniforms.uMorph.value = phase.travel;
    uniforms.uTime.value = now * 0.001;
    renderer.render(scene, camera);
    const active = phase.travel > 0.62 ? next : phase.a;
    nos.forEach((d, i) => d.classList.toggle("on", i === active));
    if (mark && nos[active]) mark.style.transform = `translateY(${nos[active].offsetTop}px)`;
    if (bar) bar.style.width = `${phase.p * 100}%`;
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);

  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("resize", resize);
    geo.dispose();
    material.dispose();
    renderer.dispose();
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
  const hero = el("section", "hero");
  const dust = el("canvas", "dust");
  dust.setAttribute("aria-hidden", "true");
  hero.appendChild(dust);
  hero.appendChild(el("p", "hero-kicker", "YOUR NAME"));
  hero.appendChild(el("h2", "", "怎么称呼你？"));
  hero.appendChild(el("p", "hero-lead", "不用真实姓名。进去之后是五个工作区：今日、画像、方向、任务、记录。按你现在要做的事选一个，随时可以换。"));
  const row = el("div", "login-row");
  const input = el("input"); input.placeholder = "你的昵称，例如：小北"; input.maxLength = 24;
  const btn = el("button", "btn", "进入启研");
  btn.onclick = async () => {
    const nick = input.value.trim();
    if (!nick) { toast("先起个昵称吧"); return; }
    btn.disabled = true; btn.textContent = "进入中…";
    try {
      const r = await api("POST", "/api/auth/login", { nickname: nick });
      S.uid = r.uid; S.nickname = r.nickname;
      localStorage.setItem("rg_uid", r.uid);
      localStorage.setItem("rg_nick", r.nickname);
      await api("POST", "/api/onboard/start", { uid: S.uid });
      toast(`你好，${r.nickname}`);
      $nav.hidden = false; $header.hidden = false;
      document.getElementById("userNickname").textContent = r.nickname;
      setView("today");
    } catch (e) { toast(e.message); btn.disabled = false; btn.textContent = "进入启研"; }
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") btn.click(); });
  row.append(input, btn);
  const link = el("button", "linkish llm-open", "连接模型 API");
  link.type = "button";
  link.onclick = () => openConnect();
  const back = el("button", "linkish llm-open", "返回首页");
  back.type = "button";
  back.onclick = () => setView("home");
  hero.append(row, link, back);
  $app.appendChild(hero);
  startDust(dust);
  input.focus();
}

function placeHowMark(list, mark, index) {
  const items = [...list.querySelectorAll("li")];
  const li = items[index];
  if (!li) return;
  mark.style.transform = `translateY(${li.offsetTop + 18}px)`;
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

function startDust(canvas, count = 42) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dots = Array.from({ length: count }, () => ({
    x: Math.random(), y: Math.random(),
    r: 0.6 + Math.random() * 1.6,
    v: 0.00015 + Math.random() * 0.00035,
    a: 0.15 + Math.random() * 0.35,
  }));
  let frame = 0;
  const draw = () => {
    if (!canvas.isConnected) return;
    const w = canvas.clientWidth; const h = canvas.clientHeight;
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    ctx.clearRect(0, 0, w, h);
    dots.forEach((d, i) => {
      d.y -= d.v;
      if (d.y < 0) d.y = 1;
      const pull = Math.sin(frame / 80 + i) * 0.01;
      ctx.beginPath();
      ctx.fillStyle = i % 5 === 0 ? `rgba(224,122,61,${d.a})` : `rgba(15,118,110,${d.a * 0.7})`;
      ctx.arc((d.x + pull) * w, d.y * h, d.r, 0, Math.PI * 2);
      ctx.fill();
    });
    frame += 1;
    requestAnimationFrame(draw);
  };
  draw();
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
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("画像"));
  $app.appendChild(await portraitBar());
  $app.appendChild(portraitTabs("onboarding"));
  const wrap = el("div", "two-col");
  const chat = el("div", "panel");

  const scroll = el("div", "chat-scroll");
  const hint = el("p", "chat-hint");
  const options = el("div", "chat-options");
  const inputRow = el("div", "chat-input-row");
  const input = el("input"); input.placeholder = "或者直接打字告诉我…"; input.maxLength = 200;
  const sendBtn = el("button", "btn small", "发送");
  inputRow.append(input, sendBtn);
  chat.append(scroll, hint, options, inputRow);

  const side = el("div", "panel");
  const sideList = el("div", "fact-list");
  side.appendChild(sideList);

  wrap.append(chat, side);
  $app.appendChild(wrap);

  const r = await api("GET", `/api/onboard/result?uid=${S.uid}`);
  S.onboard = r;
  r.messages.forEach((m) => addBubble(m.role === "user" ? "user" : "ai", m.text));
  r.facts.filter((f) => f.status === "draft").forEach((f) => sideList.appendChild(factCard(f)));
  sideList.scrollTop = sideList.scrollHeight;

  if (r.state.phase === "done") {
    hint.textContent = "";
    const go = el("button", "btn", "去核对");
    go.onclick = () => setView("confirm");
    options.innerHTML = ""; options.appendChild(go);
    input.disabled = true; sendBtn.disabled = true;
    return;
  }

  const turn = await api("POST", "/api/onboard/message", { uid: S.uid, msg: "" });
  // msg 为空时后端会重新返回当前轮问题——演示上直接显示 hint/options
  showTurn(turn, sideList);

  const send = async (text) => {
    if (!text.trim()) return;
    addBubble("user", text);
    input.value = "";
    input.disabled = true; sendBtn.disabled = true;
    options.innerHTML = "";
    scroll.appendChild(el("div", "typing", "AI 正在思考…"));
    scroll.scrollTop = scroll.scrollHeight;
    try {
      const t = await api("POST", "/api/onboard/message", { uid: S.uid, msg: text });
      document.querySelector(".typing")?.remove();
      addBubble("ai", t.reply);
      if (t.facts) t.facts.forEach((f) => { S.onboard.facts.push(f); sideList.appendChild(factCard(f)); });
      sideList.scrollTop = sideList.scrollHeight;
      showTurn(t, sideList);
    } catch (e) {
      document.querySelector(".typing")?.remove();
      toast(e.message);
    }
    input.disabled = false; sendBtn.disabled = false; input.focus();
  };

  function showTurn(t, list) {
    hint.textContent = t.hint || "";
    options.innerHTML = "";
    if (t.done) {
      const go = el("button", "btn", "去核对");
      go.onclick = () => setView("confirm");
      options.appendChild(go);
      return;
    }
    (t.options || []).forEach((label) => {
      const b = el("button", "chip", esc(label));
      b.onclick = () => send(label);
      options.appendChild(b);
    });
  }

  function addBubble(kind, text) {
    scroll.appendChild(el("div", `bubble ${kind}`, esc(text)));
    scroll.scrollTop = scroll.scrollHeight;
  }

  sendBtn.onclick = () => send(input.value);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(input.value); });
}

/* ---------- ③ 确认页 ---------- */

async function renderConfirm() {
  const r = await api("GET", `/api/onboard/result?uid=${S.uid}`);
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("画像"));
  $app.appendChild(await portraitBar());
  $app.appendChild(portraitTabs("confirm"));
  const main = el("div", "panel");

  const list = el("div", "fact-list");
  const drafts = r.facts.filter((f) => f.status === "draft");
  const others = r.facts.filter((f) => f.status === "confirmed" || f.status === "active");
  const edits = {};
  const dismissed = new Set();

  drafts.forEach((f) => {
    const card = factCard(f, true);
    const input = card.querySelector("input");
    input.value = f.value;
    input.addEventListener("input", () => { edits[f.id] = input.value; });
    const del = el("button", "linkish danger", "不属实，删除");
    del.onclick = () => {
      dismissed.has(f.id) ? dismissed.delete(f.id) : dismissed.add(f.id);
      card.style.opacity = dismissed.has(f.id) ? 0.45 : 1;
      del.textContent = dismissed.has(f.id) ? "恢复" : "不属实，删除";
    };
    card.querySelector(".fact-actions").appendChild(del);
    list.appendChild(card);
  });
  main.appendChild(list);

  const bar = el("div", "submit-actions");
  const ok = el("button", "btn", "保存核对");
  ok.onclick = async () => {
    const payload = Object.entries(edits).map(([id, value]) => ({ id, value }))
      .concat([...dismissed].map((id) => ({ id, dismissed: true })));
    try {
      await api("POST", "/api/onboard/confirm", { uid: S.uid, edits: payload });
      toast("已保存");
    } catch (e) { toast(e.message); }
  };
  const later = el("button", "btn secondary", "去方向区");
  later.onclick = () => setView("cards");
  bar.append(ok, later);
  main.appendChild(bar);

  if (others.length) others.forEach((f) => list.appendChild(factCard(f, false)));
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
  const { levels, byId } = flattenField(field.root);
  const box = el("div", "frontier");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "frontier-svg");
  const layer = el("div", "frontier-nodes");
  const COL = 172;
  const ROW = 62;
  const height = Math.max(280, Math.max(...levels.map((col) => col.length)) * ROW + 28);
  const width = 28 + levels.length * COL;
  box.style.height = height + "px";
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", String(width));
  svg.setAttribute("height", String(height));
  const placed = [];
  levels.forEach((col, ci) => {
    col.forEach((node, ri) => {
      const top = (height - col.length * ROW) / 2 + ri * ROW + 8;
      placed.push({ ...node, left: 16 + ci * COL, top });
    });
  });
  const pos = Object.fromEntries(placed.map((n) => [n.id, n]));
  placed.forEach((node) => {
    if (!node.parent || !pos[node.parent]) return;
    const a = pos[node.parent];
    const x1 = a.left + 132;
    const y1 = a.top + 20;
    const x2 = node.left;
    const y2 = node.top + 20;
    const mid = (x1 + x2) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const onPath = picked && (picked === node.id || picked.startsWith(node.id + "."));
    path.setAttribute("d", `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`);
    path.setAttribute("class", "frontier-link" + (onPath ? " is-hot" : "") + (animate ? " reveal" : ""));
    if (animate) path.style.setProperty("--d", String(node.depth));
    svg.appendChild(path);
  });
  const done = new Set((progress && progress.done) || []);
  const here = progress && progress.here;
  placed.forEach((node) => {
    const onPath = picked && (picked === node.id || picked.startsWith(node.id + "."));
    const flags = [
      "frontier-node",
      node.id === picked ? "is-pick" : "",
      onPath ? "is-path" : "",
      done.has(node.id) ? "is-past" : "",
      here === node.id ? "is-now" : "",
      animate ? "reveal" : "",
    ].filter(Boolean).join(" ");
    const btn = el("button", flags, esc(node.label));
    btn.type = "button";
    btn.style.left = node.left + "px";
    btn.style.top = node.top + "px";
    if (animate) btn.style.setProperty("--d", String(node.depth));
    if (here === node.id) btn.appendChild(el("small", "", "你在这里"));
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
  if (node.id === field.root.id) {
    const courses = el("div", "course-block");
    courses.appendChild(el("h4", "", "课程"));
    courses.appendChild(el("div", "course-status", "检索中"));
    sheet.appendChild(courses);
    loadCourses(courses, field.query);
    const choose = el("button", "btn", ctx.chosen ? "已是当前方向" : (ctx.hasCurrent ? "确认切换方向" : "确认这个方向"));
    choose.type = "button";
    choose.disabled = !!ctx.chosen;
    choose.onclick = () => ctx.onChoose();
    sheet.appendChild(choose);
  }
}

async function renderCards() {
  await ensurePortrait();
  let saved = trail();
  try {
    const taskRes = await api("GET", `/api/tasks?uid=${S.uid}`);
    if (saved.code) {
      const merged = mergeTrail(saved.code, taskRes.tasks || []);
      if (merged.done.join(",") !== saved.done.join(",")) saveTrail(merged);
    }
  } catch (_) { /* 树先按本地进度画 */ }
  saved = trail();
  let chosenCode = saved.code && FIELD_TREES[saved.code] ? saved.code : "";
  let cards = [];
  let recommended = new Set();
  let current = chosenCode || "ai";
  let picked = null;
  let grew = true;

  $app.innerHTML = "";
  $app.appendChild(workspaceHead("方向"));
  const switcher = el("div", "field-switch");
  const recLine = el("div", "rec-line");
  const confirmBar = el("div", "switch-bar");
  const stage = el("div", "forest-stage");
  $app.append(switcher, recLine, confirmBar, stage);

  const paint = () => {
    switcher.innerHTML = "";
    Object.entries(FIELD_TREES).forEach(([code, field]) => {
      const b = el("button", "field-chip" + (code === current ? " on" : ""));
      b.type = "button";
      b.appendChild(el("span", "", field.name));
      if (code === chosenCode) b.appendChild(el("i", "", "当前"));
      else if (recommended.has(code)) b.appendChild(el("i", "", "建议"));
      b.onclick = () => {
        current = code;
        picked = null;
        grew = true;
        document.getElementById("nodeSheet")?.remove();
        paint();
      };
      switcher.appendChild(b);
    });
    confirmBar.innerHTML = "";
    if (!chosenCode || current !== chosenCode) {
      const viewing = FIELD_TREES[current];
      const note = el("p", "", chosenCode
        ? `正在预览「${viewing.name}」。当前方向仍是「${FIELD_TREES[chosenCode].name}」。`
        : `正在看「${viewing.name}」。确认之后，它才会成为当前方向。`);
      const ok = el("button", "btn", chosenCode ? "确认切换方向" : "确认这个方向");
      ok.type = "button";
      ok.onclick = () => chooseField();
      confirmBar.append(note, ok);
    }
    stage.innerHTML = "";
    const hereTrail = trail();
    const fieldNow = FIELD_TREES[current];
    const here = hereTrail.code === current ? currentOnPath(fieldNow, hereTrail.done) : null;
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
      paint();
      document.getElementById("nodeSheet")?.remove();
    } catch (e) { toast(e.message); }
  };

  const show = (id) => {
    const field = FIELD_TREES[current];
    const node = flattenField(field.root).byId[id];
    if (!node) return;
    picked = id;
    paint();
    const card = cards.find((c) => c.direction && c.direction.code === current);
    openNodeSheet(field, node, {
      why: card && card.why_you,
      chosen: current === chosenCode,
      hasCurrent: !!chosenCode,
      onPick: show,
      onChoose: chooseField,
    });
  };

  paint();
  api("GET", `/api/onboard/result?uid=${S.uid}`).then((onboard) => {
    if (S.view !== "cards") return;
    const facts = ((onboard && onboard.facts) || []).filter((f) => f.status !== "deleted" && f.status !== "dismissed");
    const dirs = facts.filter((f) => (f.key || "").startsWith("direction:") && (f.status === "confirmed" || f.status === "active"));
    const chosen = dirs[dirs.length - 1];
    const code = chosen ? chosen.key.split(":")[1] : "";
    if (code && FIELD_TREES[code] && !trail().code) {
      saveTrail({ code, done: [], tasks: {} });
      chosenCode = code;
      current = code;
      grew = true;
      paint();
    } else if (trail().code) {
      chosenCode = trail().code;
      paint();
    }
  }).catch(() => {});
  api("GET", `/api/directions/recommend?uid=${S.uid}`).then((rec) => {
    if (S.view !== "cards") return;
    cards = rec.cards || [];
    recommended = new Set(cards.map((c) => c.direction && c.direction.code).filter(Boolean));
    recLine.innerHTML = "";
    if (!cards.length) {
      recLine.appendChild(el("p", "", "这份画像还没有可对照的兴趣。先在画像里把对话做完，建议才会按这份画像分开。"));
    } else {
      const names = cards.map((c) => {
        const code = c.direction && c.direction.code;
        return (FIELD_TREES[code] && FIELD_TREES[code].name) || (c.direction && c.direction.name) || "";
      }).filter(Boolean);
      recLine.appendChild(el("p", "", `这份画像更贴近${names.join("、")}。${cards[0].why_you || ""}`));
    }
    paint();
  }).catch(() => {});
}

async function dirCard(c) {
  const card = el("div", "dir-card");
  card.id = "dir-" + c.direction.code;
  card.appendChild(el("h3", "dir-name", esc(c.direction.name)));
  card.appendChild(el("p", "dir-ref", esc(c.direction.discipline_ref)));
  card.appendChild(el("p", "dir-blurb", esc(c.direction.blurb)));

  const why = el("div", "why-box", `<b>为什么是你：</b>${esc(c.why_you)}`);
  card.appendChild(why);

  // 课程：真实检索（懒加载）
  const cb = el("div", "course-block");
  cb.appendChild(el("h4", "", "课程"));
  cb.appendChild(el("div", "course-status", "检索中"));
  card.appendChild(cb);
  loadCourses(cb, c.direction.course_query);

  const rd = el("div", "reading-box", `<b>第一篇读物：</b>${esc(c.reading.title)}<br>${esc(c.reading.why)}`);
  card.appendChild(rd);

  const choose = el("button", "btn", "记下这个方向");
  choose.onclick = async () => {
    try {
      choose.disabled = true;
      await api("POST", "/api/directions/choose", { uid: S.uid, code: c.direction.code });
      S.lastTask = await api("POST", "/api/tasks/generate", { uid: S.uid, direction: c.direction.code, level: 1 });
      choose.textContent = "已记下";
      toast(`已记下「${c.direction.name}」`);
      const open = el("button", "btn secondary", "去任务区");
      open.onclick = () => setView("workbench");
      choose.after(open);
    } catch (e) { toast(e.message); choose.disabled = false; }
  };
  card.appendChild(choose);
  return card;
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

async function renderWorkbench() {
  await ensurePortrait();
  $app.innerHTML = "";
  const wrap = el("div", "stagger");
  wrap.appendChild(workspaceHead("任务"));
  $app.appendChild(wrap);
  const [taskRes, onboard] = await Promise.all([
    api("GET", `/api/tasks?uid=${S.uid}`).catch(() => ({ tasks: [] })),
    api("GET", `/api/onboard/result?uid=${S.uid}`).catch(() => null),
  ]);
  const facts = ((onboard && onboard.facts) || []).filter((f) => f.status !== "deleted" && f.status !== "dismissed");
  const dirs = facts.filter((f) => (f.key || "").startsWith("direction:") && (f.status === "confirmed" || f.status === "active"));
  const chosen = dirs[dirs.length - 1];
  let t = trail();
  if (!t.code && chosen) {
    const adopted = chosen.key.split(":")[1];
    if (FIELD_TREES[adopted]) {
      t = { code: adopted, done: [], tasks: {} };
      saveTrail(t);
    }
  }
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
    const p = el("div", "panel");
    p.appendChild(el("p", "panel-sub", "还没有方向。先在方向区选定一棵树。"));
    const b = el("button", "btn", "去方向区");
    b.type = "button";
    b.onclick = () => setView("cards");
    p.appendChild(b);
    wrap.appendChild(p);
    return;
  }
  const field = FIELD_TREES[code];
  const node = currentOnPath(field, t.done);
  if (!node) {
    const p = el("div", "panel");
    p.appendChild(el("p", "panel-sub", "这条方向上的节点都走完了。"));
    wrap.appendChild(p);
    return;
  }
  const expect = node.label.slice(0, 40);
  const tasks = listed;
  const boundId = (t.tasks || {})[node.id];
  let task = boundId ? tasks.find((tk) => tk.id === boundId) : null;
  if (task && task.title !== expect) task = null;
  if (!task) task = [...tasks].reverse().find((tk) => tk.title === expect && tk.direction === code) || null;
  if (!task) {
    task = await api("POST", "/api/tasks/generate", {
      uid: S.uid, direction: code, level: 1, title: node.label, brief: node.intro,
    });
  }
  if (!task || task.title !== expect) {
    const p = el("div", "panel");
    p.appendChild(el("p", "panel-sub", `当前节点是「${node.label}」，但任务服务还在用旧题目。请重新启动本地服务后再打开任务区。`));
    wrap.appendChild(p);
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
  const p = el("div", "panel");
  wrap.appendChild(p);

  const paintHead = () => {
    const head = el("div", "task-head");
    const hl = el("div");
    hl.appendChild(el("h2", "task-title", esc(node.label)));
    hl.appendChild(el("p", "task-brief", esc(node.intro || task.brief)));
    head.appendChild(hl);
    head.appendChild(el("span", "badge", `⏱ ${task.time_budget_min} 分钟 · 难度 ${"★".repeat(task.difficulty)}`));
    p.appendChild(head);
  };

  const showFinished = () => {
    p.innerHTML = "";
    paintHead();
    const next = currentOnPath(field, t.done.concat(node.id));
    p.appendChild(el("div", "note-box", next
      ? `「${node.label}」这一节点已经完成。下一节点是「${next.label}」。进入之后才会安排那一阶段的任务。`
      : `「${node.label}」是这条方向上的最后一个节点。`));
    if (S.lastFeedback && S.lastFeedbackTaskId === task.id) renderFeedbackInto(p, false);
    if (next) {
      const go = el("button", "btn", `进入「${next.label}」`);
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
      p.appendChild(go);
    }
  };

  if (task.status === "done") {
    showFinished();
    return;
  }

  paintHead();

  p.appendChild(el("h3", "panel-sub", "步骤"));
  const steps = el("div", "step-list");
  task.steps.forEach((st) => {
    const row = el("div", "step");
    const cb = el("input"); cb.type = "checkbox";
    row.append(cb, el("span", "", esc(st)));
    steps.appendChild(row);
  });
  p.appendChild(steps);

  p.appendChild(el("h3", "panel-sub", "标准"));
  const rub = el("div", "rubric-list");
  task.rubric.forEach((r2) => rub.appendChild(el("div", "rubric-item pass",
    `<span class="rubric-mark">·</span><div><p class="rubric-crit">${esc(r2.criterion)}</p></div>`)));
  p.appendChild(rub);

  const box = el("div", "submit-box");
  const ta = el("textarea"); ta.placeholder = "在这里写下你的过程与发现（例子、原因分析、总结）。至少写几句话再提交。";
  const demo = el("button", "btn small secondary", "填入演示示例");
  demo.type = "button";
  demo.onclick = () => {
    ta.value =
      "10 条弹幕：「太好哭了」「就这？」「编剧封神」「注水严重」「封神」「看不下去了」「细节绝了」「一般」「泪目」「神剧」\n\n" +
      "不一致例子 1：「太好哭了」——规则判积极（含「哭」可能误判消极），模型判积极。原因：规则把「哭」当消极词，但语境是感动。\n" +
      "不一致例子 2：「就这？」——规则因为无情感词判中性，模型判消极。原因：反问语气规则抓不到，模型学了语料里的讽刺用法。\n" +
      "不一致例子 3：「封神」——规则词表里没有，判中性；模型判积极。原因：网络新词，词表更新慢，模型能从上下文推断。\n\n" +
      "总结：模型的错误多来自词表覆盖与语境缺失两类；因为规则的可解释性和模型的表达力正好互补，可以互为校验。所以每次重要判断最好两个方法都跑一遍，不一致的例子就是最有价值的学习样本。";
  };
  const actions = el("div", "submit-actions");
  const submit = el("button", "btn", "提交给 AI 导师");
  submit.type = "button";
  submit.onclick = async (ev) => {
    ev.preventDefault();
    if (ta.value.trim().length < 10) { toast("至少写一句话再提交"); return; }
    submit.disabled = true; submit.textContent = "AI 正在逐条评审…";
    try {
      const fb = await api("POST", `/api/tasks/${task.id}/submit`, { uid: S.uid, payload: ta.value });
      S.lastFeedback = fb;
      S.lastFeedbackTaskId = task.id;
      sessionStorage.setItem("rg_fb_" + task.id, JSON.stringify(fb));
      S.newFactIds = (fb.learned_facts || []).map((f) => f.id);
      task.status = "done";
      showFinished();
      setTimeout(() => document.getElementById("fbPanel")?.scrollIntoView({ behavior: "smooth" }), 80);
    } catch (e) { toast(e.message); submit.disabled = false; submit.textContent = "提交给 AI 导师"; }
  };
  actions.append(demo, submit, el("span", "hint", "提交后 AI 按 rubric 逐条反馈，并把这次行为写入对你的认知。"));
  box.append(ta, actions);
  p.appendChild(box);
}

/* ---------- ⑦ 反馈 ---------- */

function renderFeedbackInto(p, withNav = true) {
  const fb = S.lastFeedback;
  if (!fb) return;
  const box = el("div", "panel", ""); box.id = "fbPanel";
  box.style.marginTop = "18px";
  const head = el("div", "task-head");
  const hl = el("div");
  hl.appendChild(el("h2", "panel-title", "AI 反馈"));
  hl.appendChild(el("p", "panel-sub", esc(fb.encouragement)));
  head.appendChild(hl);
  head.appendChild(el("div", "score-ring", `<span class="num">${fb.score}</span><span style="color:var(--muted)">/100</span>`));
  box.appendChild(head);

  const rub = el("div", "rubric-list");
  (fb.rubric || []).forEach((r) => {
    rub.appendChild(el("div", `rubric-item ${r.pass ? "pass" : "fail"}`,
      `<span class="rubric-mark">${r.pass ? "✓" : "✗"}</span><div><p class="rubric-crit">${esc(r.criterion)}</p><p class="rubric-comment">${esc(r.comment)}</p></div>`));
  });
  box.appendChild(rub);

  const hint = el("div", "why-box", `<b>下一步：</b>${esc(fb.next_hint)}`);
  box.appendChild(hint);

  if (fb.learned_facts && fb.learned_facts.length) {
    box.appendChild(el("hr", "divider"));
    const fl = el("div", "fact-list");
    fb.learned_facts.forEach((f) => fl.appendChild(factCard(f, false, true)));
    box.appendChild(fl);
  }

  if (withNav) {
    const acts = el("div", "submit-actions");
    const me = el("button", "btn secondary", "看记录");
    me.onclick = () => setView("me");
    const next = el("button", "btn", "回今日");
    next.onclick = () => setView("today");
    acts.append(next, me);
    box.appendChild(acts);
  }
  p.appendChild(box);
}

/* ---------- 今日 / ⑨ NBA ---------- */

async function renderToday() {
  await ensurePortrait();
  let saved = trail();
  try {
    const taskRes = await api("GET", `/api/tasks?uid=${S.uid}`);
    if (saved.code) {
      const merged = mergeTrail(saved.code, taskRes.tasks || []);
      if (merged.done.join(",") !== saved.done.join(",")) {
        saveTrail(merged);
        saved = trail();
      }
    }
  } catch (_) { /* 进度先用本地记录 */ }
  const field = FIELD_TREES[saved.code];
  const node = field ? currentOnPath(field, saved.done) : null;
  $app.innerHTML = "";
  const wrap = el("div", "stagger");
  wrap.appendChild(workspaceHead("今日"));
  const status = el("div", "ws-status");
  status.appendChild(el("span", "", field ? field.name : "还没有方向"));
  status.appendChild(el("span", "", node ? `正在「${node.label}」` : (field ? "这条路径已走完" : "先去方向区")));
  wrap.appendChild(status);
  const p = el("div", "panel");
  p.appendChild(el("h2", "panel-title", "建议"));
  const card = el("div", "nba-card");
  card.appendChild(el("h3", "nba-title", esc(node ? `继续「${node.label}」` : (field ? "这条方向已经走到头" : "先选定一个方向"))));
  card.appendChild(el("p", "nba-why", esc(node ? node.intro : "方向区里有六棵树。记下其中一棵，任务会从它的起点开始。")));
  const act = el("div", "submit-actions");
  const go = el("button", "btn", node ? "去任务区" : "去方向区");
  go.onclick = () => setView(node ? "workbench" : "cards");
  act.appendChild(go);
  card.appendChild(act);
  p.appendChild(card);
  wrap.appendChild(p);
  $app.appendChild(wrap);
}

/* ---------- ⑧ me 页 ---------- */

async function renderMe() {
  const r = await api("GET", `/api/me/facts?uid=${S.uid}`);
  const facts = r.facts.filter((f) => f.status !== "deleted");
  $app.innerHTML = "";
  $app.appendChild(workspaceHead("记录"));
  const main = el("div", "panel");

  const groups = {};
  facts.forEach((f) => { (groups[f.category] = groups[f.category] || []).push(f); });
  Object.keys(CAT_CN).forEach((cat) => {
    if (!groups[cat] || !groups[cat].length) return;
    main.appendChild(el("h3", "panel-sub", `${CAT_CN[cat]}`));
    const list = el("div", "fact-list");
    groups[cat].forEach((f) => list.appendChild(factCard(f, false, S.newFactIds.includes(f.id))));
    main.appendChild(list);
  });
  if (!facts.length) {
    main.appendChild(el("div", "note-box", "还没有记录。"));
    const go = el("button", "btn", "去画像");
    go.onclick = () => setView("onboarding");
    main.appendChild(go);
  }

  $app.appendChild(main);
}

/* ---------- 事实卡组件 ---------- */

function factCard(f, editable = false, isNew = false) {
  const card = el("div", `fact-card${isNew ? " new-fact" : ""}`);
  const valueHtml = editable
    ? `<input type="text" value="${esc(f.value)}" />`
    : `<div class="fact-value">${esc(f.value)}</div>`;
  card.innerHTML = `
    ${valueHtml}
    <div class="fact-meta">
      <span class="badge cat-${esc(f.category)}">${CAT_CN[f.category] || f.category}</span>
      ${f.status === "draft" ? '<span class="badge draft">待确认</span>' : ""}
    </div>
    ${f.evidence && f.evidence.length ? `<div class="fact-evidence">证据：${f.evidence.map((e) => esc(e.quote ? `「${e.quote}」` : (e.type === "submission" ? `任务提交《${e.task_title || ""}》` : e.type))).join("；")}</div>` : ""}
    <div class="fact-actions"></div>`;
  if (!editable) {
    const acts = card.querySelector(".fact-actions");
    const edit = el("button", "linkish", "修改");
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
          toast("已修改——AI 之后读到的是新版本");
        } catch (e) { toast(e.message); valueNode.textContent = f.value; }
      };
      input.addEventListener("blur", save);
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") input.blur(); });
    };
    const del = el("button", "linkish danger", "删除");
    del.onclick = async () => {
      try {
        await api("DELETE", `/api/me/facts/${f.id}?uid=${S.uid}`);
        card.style.opacity = 0.4;
        del.disabled = true; del.textContent = "已删除";
        toast("已删除（软删除），AI 不再读取");
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
  const splash = document.getElementById("boot");
  setTimeout(() => splash && splash.classList.add("out"), 1400);
  setTimeout(() => splash && splash.remove(), 2100);
  try {
    const h = await api("GET", "/api/health");
    applyLlmPill(h.llm);
  } catch (_) { /* 健康检查失败不挡页面 */ }
  if (S.uid) {
    try {
      await api("GET", `/api/me/facts?uid=${S.uid}`);
      document.getElementById("userNickname").textContent = S.nickname;
      const st = await api("GET", `/api/onboard/result?uid=${S.uid}`);
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
})();
