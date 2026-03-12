const state = {
  overview: null,
  teachers: [],
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
};

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function buildQueryString() {
  const params = new URLSearchParams();
  if (elements.schoolSelect.value) {
    params.set("school", elements.schoolSelect.value);
  }
  if (elements.queryInput.value.trim()) {
    params.set("query", elements.queryInput.value.trim());
  }
  if (elements.areaInput.value.trim()) {
    params.set("area", elements.areaInput.value.trim());
  }
  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
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

  const uniqueAreas = new Set();
  overview.schools.forEach((school) => {
    school.top_areas.forEach((area) => uniqueAreas.add(area));
  });

  [...uniqueAreas].forEach((area) => {
    const chip = document.createElement("span");
    chip.className = "area-chip";
    chip.textContent = area;
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

function renderTeachers(teachers) {
  elements.teacherGrid.innerHTML = "";
  elements.resultsTitle.textContent = `${teachers.length} 位老师`;

  if (teachers.length === 0) {
    elements.teacherGrid.innerHTML = `<article class="teacher-card"><p class="teacher-summary">当前筛选条件下没有结果。</p></article>`;
    return;
  }

  teachers.forEach((teacher) => {
    const fragment = elements.teacherTemplate.content.cloneNode(true);
    fragment.querySelector(".teacher-school").textContent = teacher.school;
    fragment.querySelector(".teacher-name").textContent = teacher.name;
    fragment.querySelector(".teacher-title").textContent = teacher.title;
    fragment.querySelector(".teacher-faculty").textContent = teacher.faculty;
    fragment.querySelector(".teacher-lab").textContent = teacher.lab
      ? `实验室 / 团队：${teacher.lab}`
      : "实验室 / 团队：未明确提及";
    fragment.querySelector(".teacher-summary").textContent = teacher.summary;

    const areaContainer = fragment.querySelector(".teacher-areas");
    teacher.research_areas.forEach((area) => {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = area;
      areaContainer.append(tag);
    });

    const paperList = fragment.querySelector(".paper-list");
    teacher.recent_publications.slice(0, 3).forEach((paper) => {
      const item = document.createElement("article");
      item.className = "paper-item";
      item.innerHTML = `<strong>${paper.title}</strong><span>${paper.year} · ${paper.venue} · ${paper.source}</span>`;
      paperList.append(item);
    });

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

async function loadTeachers() {
  const teachers = await getJson(`/api/teachers${buildQueryString()}`);
  state.teachers = teachers;
  renderTeachers(teachers);
}

async function bootstrap() {
  state.overview = await getJson("/api/overview");
  fillSchoolSelect(state.overview);
  renderOverview(state.overview);
  await loadTeachers();
}

elements.applyButton.addEventListener("click", loadTeachers);
elements.resetButton.addEventListener("click", async () => {
  elements.schoolSelect.value = "";
  elements.queryInput.value = "";
  elements.areaInput.value = "";
  await loadTeachers();
});

bootstrap().catch((error) => {
  elements.resultsTitle.textContent = "加载失败";
  elements.teacherGrid.innerHTML = `<article class="teacher-card"><p class="teacher-summary">${error.message}</p></article>`;
});
