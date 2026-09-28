/* 学科瞭望 — 一级 / 二级学科 + 北大相关课程搜索 */
let DATA = null;
let activeCategory = "ALL";
let activeId = null; // "L1:110" | "L2:110.21"
let query = "";
let terms = [];
let selectedTerm = "";

const $ = (id) => document.getElementById(id);

async function boot() {
  const res = await fetch("data/disciplines.json");
  DATA = await res.json();
  $("standardLabel").textContent = DATA.standard;
  $("statsLabel").textContent =
    `${DATA.stats.categoryCount} 个门类 · ${DATA.stats.level1Count} 个一级 · ${DATA.stats.level2Count} 个二级`;
  $("noteText").textContent = DATA.note;
  renderChips();
  renderList();
  $("search").addEventListener("input", (e) => {
    query = e.target.value.trim().toLowerCase();
    renderList();
  });
  loadTerms().catch(() => {});
}

async function loadTerms() {
  try {
    const res = await fetch("/api/terms");
    if (!res.ok) return;
    const data = await res.json();
    terms = data.items || [];
    if (terms.length && !selectedTerm) selectedTerm = terms[0].value;
    const sel = document.getElementById("courseTerm");
    if (sel && terms.length) {
      sel.innerHTML = terms
        .map(
          (t) =>
            `<option value="${t.value}" ${
              t.value === selectedTerm ? "selected" : ""
            }>${escapeHtml(t.label || t.value)}</option>`
        )
        .join("");
    }
  } catch (_) {
    /* 静态预览时没有 API，课程区会提示用 server.py 启动 */
  }
}

function renderChips() {
  const box = $("categoryChips");
  box.innerHTML = "";
  box.appendChild(chipButton("ALL", "全部", DATA.disciplines.length, true));
  DATA.categories.forEach((cat) => {
    const count = DATA.disciplines.filter((d) => d.category === cat.id).length;
    box.appendChild(chipButton(cat.id, cat.name, count, false));
  });
}

function chipButton(id, label, count, active) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "chip" + (active ? " active" : "");
  btn.dataset.id = id;
  btn.innerHTML = `${label}<span class="count">${count}</span>`;
  btn.addEventListener("click", () => {
    activeCategory = id;
    [...$("categoryChips").children].forEach((c) => {
      c.classList.toggle("active", c.dataset.id === id);
    });
    renderList();
  });
  return btn;
}

function findL1(code) {
  return DATA.disciplines.find((d) => d.code === code);
}

function findL2(dottedCode) {
  const parent = dottedCode.slice(0, 3);
  const d = findL1(parent);
  if (!d) return null;
  const child = (d.children || []).find((c) => c.code === dottedCode);
  return child ? { parent: d, child } : null;
}

function filtered() {
  const q = query;
  return DATA.disciplines
    .filter((d) => activeCategory === "ALL" || d.category === activeCategory)
    .map((d) => {
      if (!q) return { discipline: d, matchedChildren: d.children || [] };
      const selfHit =
        `${d.code} ${d.name} ${d.blurb}`.toLowerCase().includes(q);
      const matchedChildren = (d.children || []).filter((c) =>
        `${c.code} ${c.name} ${c.blurb}`.toLowerCase().includes(q)
      );
      if (selfHit || matchedChildren.length) {
        return {
          discipline: d,
          matchedChildren: selfHit ? d.children || [] : matchedChildren,
        };
      }
      return null;
    })
    .filter(Boolean);
}

function renderList() {
  const list = $("disciplineList");
  const empty = $("emptyState");
  list.innerHTML = "";
  const items = filtered();
  empty.hidden = items.length > 0;
  if (!items.length) return;

  const byCat = {};
  DATA.categories.forEach((c) => {
    byCat[c.id] = [];
  });
  items.forEach((row) => byCat[row.discipline.category].push(row));

  DATA.categories.forEach((cat) => {
    const group = byCat[cat.id];
    if (!group.length) return;
    const title = document.createElement("div");
    title.className = "group-title";
    title.textContent = `${cat.id} · ${cat.name}`;
    title.style.borderLeftColor = cat.color;
    title.style.color = cat.color;
    list.appendChild(title);

    group.forEach(({ discipline: d, matchedChildren }) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "item" + (activeId === `L1:${d.code}` ? " active" : "");
      const n2 = (d.children || []).length;
      btn.innerHTML = `
        <span class="code">${d.code} · 一级 · ${n2} 个二级</span>
        <span class="name">${d.name}</span>
        <span class="blurb">${d.blurb}</span>`;
      btn.addEventListener("click", () => selectL1(d.code));
      list.appendChild(btn);

      // 搜索命中二级时，在列表里露出可点的二级
      if (query && matchedChildren.length && matchedChildren.length <= 12) {
        matchedChildren.slice(0, 8).forEach((c) => {
          const sub = document.createElement("button");
          sub.type = "button";
          sub.className =
            "item sub-item" + (activeId === `L2:${c.code}` ? " active" : "");
          sub.innerHTML = `
            <span class="code">${c.code}</span>
            <span class="name">${c.name}</span>`;
          sub.addEventListener("click", (e) => {
            e.stopPropagation();
            selectL2(c.code);
          });
          list.appendChild(sub);
        });
      }
    });
  });
}

function selectL1(code) {
  activeId = `L1:${code}`;
  const d = findL1(code);
  const cat = DATA.categories.find((c) => c.id === d.category);
  renderList();

  const children = (d.children || [])
    .map(
      (c) => `
      <button type="button" class="child-card" data-code="${c.code}">
        <span class="child-code">${c.code}</span>
        <span class="child-name">${c.name}</span>
        <span class="child-blurb">${escapeHtml(c.blurb || "")}</span>
      </button>`
    )
    .join("");

  $("detailPanel").innerHTML = `
    <div class="detail-top">
      <div>
        <p class="detail-code">一级学科 · ${d.code}</p>
        <h2 class="detail-title">${d.name}</h2>
        <p class="detail-blurb">${d.blurb}</p>
      </div>
      <span class="badge" style="background:${cat.color}18;color:${cat.color}">${cat.id} ${cat.name}</span>
    </div>
    ${courseBlock(d.name, d.courseQuery || d.name)}
    <section class="section">
      <h3>这门学科在研究什么</h3>
      <p>${d.what}</p>
    </section>
    <section class="section highlight">
      <h3>当前科研概况（导读）</h3>
      <p>${d.researchNow}</p>
    </section>
    <section class="section">
      <h3>给大一 / 大二的起步建议</h3>
      <p>${d.forFreshman}</p>
    </section>
    <section class="section">
      <h3>二级学科（共 ${(d.children || []).length} 个，点进去看介绍）</h3>
      <div class="child-grid">${children || "<p>暂无二级学科数据</p>"}</div>
    </section>`;

  $("detailPanel").querySelectorAll(".child-card").forEach((el) => {
    el.addEventListener("click", () => selectL2(el.dataset.code));
  });
  finishDetail();
}

function selectL2(dottedCode) {
  const hit = findL2(dottedCode);
  if (!hit) return;
  const { parent: d, child: c } = hit;
  const cat = DATA.categories.find((x) => x.id === d.category);
  activeId = `L2:${c.code}`;
  renderList();

  $("detailPanel").innerHTML = `
    <div class="detail-top">
      <div>
        <p class="detail-code">
          <button type="button" class="linkish" id="backToL1">← ${d.name}（${d.code}）</button>
          · 二级学科 ${c.code}
        </p>
        <h2 class="detail-title">${c.name}</h2>
        <p class="detail-blurb">${c.blurb}</p>
      </div>
      <span class="badge" style="background:${cat.color}18;color:${cat.color}">${cat.id} ${cat.name}</span>
    </div>
    ${courseBlock(c.name, c.courseQuery || c.name)}
    <section class="section">
      <h3>这个方向在研究什么</h3>
      <p>${c.what}</p>
    </section>
    ${
      c.sourceNote
        ? `<section class="section">
      <h3>国标要点（摘录）</h3>
      <p>${escapeHtml(c.sourceNote)}</p>
    </section>`
        : ""
    }
    <section class="section highlight">
      <h3>如何贴近当前科研</h3>
      <p>${c.researchNow}</p>
    </section>
    <section class="section">
      <h3>给大一 / 大二的起步建议</h3>
      <p>${c.forFreshman}</p>
    </section>`;

  $("backToL1").addEventListener("click", () => selectL1(d.code));
  finishDetail();
}

function finishDetail() {
  wireCourseSearch();
  $("detailPanel").scrollTop = 0;
  const course = document.getElementById("courseSection");
  if (course) course.classList.add("course-pulse");
}

function courseBlock(title, defaultQuery) {
  const termOptions = terms.length
    ? terms
        .map(
          (t) =>
            `<option value="${t.value}" ${
              t.value === selectedTerm ? "selected" : ""
            }>${escapeHtml(t.label || t.value)}</option>`
        )
        .join("")
    : `<option value="">加载学期中…若一直空白请确认已用 server.py 启动</option>`;

  return `
    <section class="section course-section" id="courseSection">
      <div class="course-head">
        <h3>搜北大相关课程</h3>
        <span class="course-pill">公开课表 · 非培养方案</span>
      </div>
      <p class="course-hint">想了解「${escapeHtml(
        title
      )}」可以上哪些课？填关键词后点右侧绿色按钮。</p>
      <div class="course-controls">
        <label class="course-field">
          <span>学期</span>
          <select id="courseTerm">${termOptions}</select>
        </label>
        <label class="course-field grow">
          <span>关键词</span>
          <input id="courseQuery" type="search" value="${escapeAttr(
            defaultQuery
          )}" placeholder="课程名或课号关键词" />
        </label>
        <button type="button" class="course-btn" id="courseSearchBtn">搜索课程</button>
      </div>
      <div id="courseStatus" class="course-status"></div>
      <div id="courseResults" class="course-results"></div>
    </section>`;
}

function wireCourseSearch() {
  const btn = $("courseSearchBtn");
  if (!btn) return;
  const termEl = $("courseTerm");
  if (termEl) {
    termEl.addEventListener("change", () => {
      selectedTerm = termEl.value;
    });
  }
  btn.addEventListener("click", () => searchCourses());
  $("courseQuery").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchCourses();
  });
}

async function searchCourses() {
  const status = $("courseStatus");
  const box = $("courseResults");
  const q = ($("courseQuery").value || "").trim();
  const term = ($("courseTerm") && $("courseTerm").value) || selectedTerm;
  if (!q) {
    status.textContent = "请先填写关键词。";
    return;
  }
  status.textContent = "正在查询北大教务公开课表…";
  box.innerHTML = "";
  try {
    const url = new URL("/api/courses", window.location.origin);
    url.searchParams.set("query", q);
    if (term) url.searchParams.set("term", term);
    url.searchParams.set("limit", "10");
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      status.textContent =
        data.error ||
        "查询失败。请确认已用 python server.py 启动（不要只用 http.server）。";
      return;
    }
    const items = data.items || [];
    selectedTerm = data.term || term;
    status.textContent = items.length
      ? `学期 ${data.term} · 找到 ${data.total} 门相关开课（本页 ${items.length}）`
      : `学期 ${data.term} · 没有匹配课程，可换更短关键词再试。`;
    box.innerHTML = items
      .map(
        (it) => `
      <article class="course-card">
        <h4>${escapeHtml(it.name || "")}</h4>
        <p>${escapeHtml(it.teachers || "教师信息暂缺")}</p>
        <p class="course-ref">${escapeHtml(it.ref || "")}</p>
      </article>`
      )
      .join("");
    if (data.next_offset != null) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "course-btn secondary";
      more.textContent = "加载更多";
      more.addEventListener("click", () => searchCoursesMore(q, data.term, data.next_offset));
      box.appendChild(more);
    }
  } catch (err) {
    status.textContent =
      "无法连接课程 API。请在 product/discipline-map 下运行：python server.py";
    console.error(err);
  }
}

async function searchCoursesMore(q, term, offset) {
  const box = $("courseResults");
  const status = $("courseStatus");
  status.textContent = "加载更多…";
  try {
    const url = new URL("/api/courses", window.location.origin);
    url.searchParams.set("query", q);
    url.searchParams.set("term", term);
    url.searchParams.set("offset", String(offset));
    url.searchParams.set("limit", "10");
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      status.textContent = data.error || "加载失败";
      return;
    }
    status.textContent = `学期 ${data.term} · 共 ${data.total} 门`;
    const moreBtn = box.querySelector(".course-btn.secondary");
    if (moreBtn) moreBtn.remove();
    (data.items || []).forEach((it) => {
      const el = document.createElement("article");
      el.className = "course-card";
      el.innerHTML = `
        <h4>${escapeHtml(it.name || "")}</h4>
        <p>${escapeHtml(it.teachers || "教师信息暂缺")}</p>
        <p class="course-ref">${escapeHtml(it.ref || "")}</p>`;
      box.appendChild(el);
    });
    if (data.next_offset != null) {
      const more = document.createElement("button");
      more.type = "button";
      more.className = "course-btn secondary";
      more.textContent = "加载更多";
      more.addEventListener("click", () =>
        searchCoursesMore(q, data.term, data.next_offset)
      );
      box.appendChild(more);
    }
  } catch (err) {
    status.textContent = "加载失败";
    console.error(err);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

boot().catch((err) => {
  $("statsLabel").textContent = "数据加载失败";
  console.error(err);
});
