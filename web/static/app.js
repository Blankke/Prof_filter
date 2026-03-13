const PAGE_SIZE = 20;

const state = {
  overview: null,
  allTeachers: [],
  titleFilter: "",
  sortBy: "name",
  viewMode: "cards",
  page: 1,
};

const elements = {
  schoolSelect: document.getElementById("school-select"),
  queryInput: document.getElementById("query-input"),
  areaInput: document.getElementById("area-input"),
  applyButton: document.getElementById("apply-filters"),
  resetButton: document.getElementById("reset-filters"),
  teacherGrid: document.getElementById("teacher-grid"),
  resultsTitle: document.getElementById("results-title"),
  schoolOverview: document.getElementById("school-overview"),
  areaCloud: document.getElementById("area-cloud"),
  teacherTemplate: document.getElementById("teacher-card-template"),
  titleChips: document.getElementById("title-chips"),
  sortSelect: document.getElementById("sort-select"),
  viewCards: document.getElementById("view-cards"),
  viewCompact: document.getElementById("view-compact"),
  pagination: document.getElementById("pagination"),
};

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function buildQueryString() {
  const params = new URLSearchParams();
  if (elements.schoolSelect.value) params.set("school", elements.schoolSelect.value);
  if (elements.queryInput.value.trim()) params.set("query", elements.queryInput.value.trim());
  if (elements.areaInput.value.trim()) params.set("area", elements.areaInput.value.trim());
  const q = params.toString();
  return q ? `?${q}` : "";
}

function titleMatches(teacher) {
  if (!state.titleFilter) return true;
  const t = teacher.title;
  if (state.titleFilter === "教授") return t.includes("教授") && !t.includes("副教授") && !t.includes("助理教授");
  if (state.titleFilter === "副教授") return t.includes("副教授");
  if (state.titleFilter === "助理教授") return t.includes("助理教授");
  if (state.titleFilter === "讲师") return t.includes("讲师");
  return true;
}

function getTitleRank(title) {
  if (title.includes("助理教授")) return 2;
  if (title.includes("副教授")) return 1;
  if (title.includes("教授")) return 0;
  if (title.includes("研究员")) return 3;
  if (title.includes("讲师")) return 4;
  return 9;
}

function getSortedFiltered() {
  const filtered = state.allTeachers.filter(titleMatches);
  return filtered.sort((a, b) => {
    if (state.sortBy === "title") {
      const diff = getTitleRank(a.title) - getTitleRank(b.title);
      return diff !== 0 ? diff : a.name.localeCompare(b.name, "zh");
    }
    return a.name.localeCompare(b.name, "zh");
  });
}

function renderOverview(overview) {
  elements.schoolOverview.innerHTML = "";
  elements.areaCloud.innerHTML = "";

  overview.schools.forEach((school) => {
    const card = document.createElement("article");
    card.className = "overview-card";
    card.innerHTML = `
      <div class="overview-card-head">
        <h3>${school.name}</h3>
        <span>${school.top_areas.join(" / ") || "待补充"}</span>
      </div>
      <div class="metric-row">
        <div class="metric"><strong>${school.teacher_count}</strong><span>教师</span></div>
        <div class="metric"><strong>${school.lab_count}</strong><span>实验室</span></div>
        <div class="metric"><strong>${school.publication_count}</strong><span>论文</span></div>
      </div>
    `;
    elements.schoolOverview.append(card);
  });

  const areaCount = {};
  overview.schools.forEach((school) => {
    school.top_areas.forEach((area) => {
      areaCount[area] = (areaCount[area] || 0) + 1;
    });
  });

  Object.entries(areaCount)
    .sort((a, b) => b[1] - a[1])
    .forEach(([area]) => {
      const chip = document.createElement("button");
      chip.className = "area-chip";
      chip.textContent = area;
      chip.addEventListener("click", () => {
        elements.areaInput.value = area;
        loadTeachers();
      });
      elements.areaCloud.append(chip);
    });
}

function fillSchoolSelect(overview) {
  overview.schools.forEach((school) => {
    const option = document.createElement("option");
    option.value = school.id;
    option.textContent = school.name;
    elements.schoolSelect.append(option);
  });
}

function renderPagination(total) {
  elements.pagination.innerHTML = "";
  const pageCount = Math.ceil(total / PAGE_SIZE);
  if (pageCount <= 1) return;

  const createBtn = (label, page, disabled = false, active = false) => {
    const btn = document.createElement("button");
    btn.className = "page-btn" + (active ? " active" : "");
    btn.textContent = label;
    btn.disabled = disabled;
    btn.addEventListener("click", () => {
      state.page = page;
      render();
      document.getElementById("teacher-grid").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return btn;
  };

  elements.pagination.append(createBtn("←", state.page - 1, state.page === 1));

  const pages = new Set([1, pageCount]);
  for (let i = Math.max(1, state.page - 1); i <= Math.min(pageCount, state.page + 1); i++) pages.add(i);

  let prev = 0;
  [...pages].sort((a, b) => a - b).forEach((p) => {
    if (p - prev > 1) {
      const dots = document.createElement("span");
      dots.className = "page-dots";
      dots.textContent = "…";
      elements.pagination.append(dots);
    }
    elements.pagination.append(createBtn(p, p, false, p === state.page));
    prev = p;
  });

  elements.pagination.append(createBtn("→", state.page + 1, state.page === pageCount));

  const info = document.createElement("span");
  info.className = "page-info";
  const start = (state.page - 1) * PAGE_SIZE + 1;
  const end = Math.min(state.page * PAGE_SIZE, total);
  info.textContent = `${start}–${end} / ${total}`;
  elements.pagination.append(info);
}

function pickCardSize(teacher) {
  const summaryLen = (teacher.summary || "").trim().length;
  const areaCount = teacher.research_areas?.length || 0;
  const paperCount = teacher.recent_publications?.length || 0;
  const hasLab = Boolean(teacher.lab);

  let score = 0;
  if (summaryLen >= 120) score += 2;
  else if (summaryLen >= 60) score += 1;
  if (areaCount >= 6) score += 2;
  else if (areaCount >= 3) score += 1;
  if (paperCount >= 3) score += 2;
  else if (paperCount >= 1) score += 1;
  if (hasLab) score += 1;

  if (score >= 5) return "large";
  if (score >= 3) return "medium";
  return "small";
}

function renderCardView(teachers) {
  elements.teacherGrid.className = "teacher-grid";
  teachers.forEach((teacher) => {
    const fragment = elements.teacherTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".teacher-card");
    card.classList.add(`card-size-${pickCardSize(teacher)}`);

    fragment.querySelector(".teacher-school").textContent = teacher.school;
    fragment.querySelector(".teacher-name").textContent = teacher.name;
    fragment.querySelector(".teacher-title").textContent = teacher.title;
    fragment.querySelector(".teacher-faculty").textContent = teacher.faculty;
    fragment.querySelector(".teacher-lab").textContent = teacher.lab
      ? `实验室 / 团队：${teacher.lab}`
      : "实验室 / 团队：未明确提及";
    const summaryEl = fragment.querySelector(".teacher-summary");
    const summaryText = (teacher.summary || "").trim() || "暂无简介";
    summaryEl.textContent = summaryText;

    if (summaryText.length > 140) {
      summaryEl.classList.add("is-collapsible");
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "summary-toggle";
      toggle.textContent = "展开";
      toggle.setAttribute("aria-expanded", "false");
      toggle.addEventListener("click", () => {
        const expanded = summaryEl.classList.toggle("is-expanded");
        toggle.textContent = expanded ? "收起" : "展开";
        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      });
      const mainCol = fragment.querySelector(".teacher-main-col");
      mainCol.insertBefore(toggle, fragment.querySelector(".teacher-areas"));
    }

    const areaContainer = fragment.querySelector(".teacher-areas");
    teacher.research_areas.forEach((area) => {
      const tag = document.createElement("button");
      tag.className = "tag";
      tag.textContent = area;
      tag.addEventListener("click", () => {
        elements.areaInput.value = area;
        loadTeachers();
      });
      areaContainer.append(tag);
    });

    const paperList = fragment.querySelector(".paper-list");
    const visiblePapers = teacher.recent_publications.slice(0, 3);
    visiblePapers.forEach((paper, index) => {
      const item = document.createElement("article");
      item.className = "paper-item";
      if (index >= 2) item.classList.add("is-hidden");
      const titleEl = document.createElement(paper.link ? "a" : "strong");
      titleEl.textContent = paper.title;
      if (paper.link) {
        titleEl.href = paper.link;
        titleEl.target = "_blank";
        titleEl.rel = "noreferrer";
      }
      const meta = document.createElement("span");
      meta.textContent = `${paper.year} · ${paper.venue}`;
      item.append(titleEl, meta);
      paperList.append(item);
    });

    if (visiblePapers.length > 2) {
      const paperToggle = document.createElement("button");
      paperToggle.type = "button";
      paperToggle.className = "paper-toggle";
      paperToggle.textContent = "展开论文";
      paperToggle.setAttribute("aria-expanded", "false");
      paperToggle.addEventListener("click", () => {
        const expanded = paperList.classList.toggle("is-expanded");
        paperToggle.textContent = expanded ? "收起论文" : "展开论文";
        paperToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      });
      const sideCol = fragment.querySelector(".teacher-side-col");
      sideCol.insertBefore(paperToggle, fragment.querySelector(".teacher-links"));
    }

    const links = fragment.querySelector(".teacher-links");
    if (teacher.homepage) {
      const anchor = document.createElement("a");
      anchor.href = teacher.homepage;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      anchor.textContent = "个人主页";
      links.append(anchor);
    }

    elements.teacherGrid.append(fragment);
  });
}

function renderCompactView(teachers) {
  elements.teacherGrid.className = "teacher-list";
  teachers.forEach((teacher) => {
    const row = document.createElement("div");
    row.className = "teacher-row";

    const school = document.createElement("span");
    school.className = "row-school";
    school.textContent = teacher.school;

    const name = document.createElement("span");
    name.className = "row-name";
    name.textContent = teacher.name;

    const title = document.createElement("span");
    title.className = "row-title";
    title.textContent = teacher.title;

    const areas = document.createElement("span");
    areas.className = "row-areas";
    teacher.research_areas.slice(0, 4).forEach((area, i) => {
      if (i > 0) {
        const sep = document.createElement("span");
        sep.className = "row-sep";
        sep.textContent = " · ";
        areas.append(sep);
      }
      const btn = document.createElement("button");
      btn.className = "row-area-btn";
      btn.textContent = area;
      btn.addEventListener("click", () => {
        elements.areaInput.value = area;
        loadTeachers();
      });
      areas.append(btn);
    });

    row.append(school, name, title, areas);

    if (teacher.homepage) {
      const link = document.createElement("a");
      link.className = "row-link";
      link.href = teacher.homepage;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = "主页";
      row.append(link);
    } else {
      const placeholder = document.createElement("span");
      placeholder.className = "row-link";
      row.append(placeholder);
    }

    elements.teacherGrid.append(row);
  });
}

function render() {
  const sorted = getSortedFiltered();
  const total = sorted.length;
  const start = (state.page - 1) * PAGE_SIZE;
  const page = sorted.slice(start, start + PAGE_SIZE);

  elements.resultsTitle.textContent = `${total} 位老师`;
  elements.teacherGrid.innerHTML = "";

  if (total === 0) {
    elements.teacherGrid.className = "teacher-grid";
    elements.teacherGrid.innerHTML = `<article class="teacher-card"><p class="teacher-summary">当前筛选条件下没有结果。</p></article>`;
    elements.pagination.innerHTML = "";
    return;
  }

  if (state.viewMode === "compact") {
    renderCompactView(page);
  } else {
    renderCardView(page);
  }

  renderPagination(total);
}

async function loadTeachers() {
  const teachers = await getJson(`/api/teachers${buildQueryString()}`);
  state.allTeachers = teachers;
  state.page = 1;
  render();
}

async function bootstrap() {
  state.overview = await getJson("/api/overview");
  fillSchoolSelect(state.overview);
  renderOverview(state.overview);
  await loadTeachers();
}

elements.titleChips.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  elements.titleChips.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  chip.classList.add("active");
  state.titleFilter = chip.dataset.title;
  state.page = 1;
  render();
});

elements.sortSelect.addEventListener("change", () => {
  state.sortBy = elements.sortSelect.value;
  state.page = 1;
  render();
});

elements.viewCards.addEventListener("click", () => {
  state.viewMode = "cards";
  elements.viewCards.classList.add("active");
  elements.viewCompact.classList.remove("active");
  state.page = 1;
  render();
});

elements.viewCompact.addEventListener("click", () => {
  state.viewMode = "compact";
  elements.viewCompact.classList.add("active");
  elements.viewCards.classList.remove("active");
  state.page = 1;
  render();
});

elements.applyButton.addEventListener("click", loadTeachers);

elements.resetButton.addEventListener("click", async () => {
  elements.schoolSelect.value = "";
  elements.queryInput.value = "";
  elements.areaInput.value = "";
  elements.titleChips.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
  elements.titleChips.querySelector('.chip[data-title=""]').classList.add("active");
  state.titleFilter = "";
  state.sortBy = "name";
  elements.sortSelect.value = "name";
  await loadTeachers();
});

bootstrap().catch((error) => {
  elements.resultsTitle.textContent = "加载失败";
  elements.teacherGrid.innerHTML = `<article class="teacher-card"><p class="teacher-summary">${error.message}</p></article>`;
});
