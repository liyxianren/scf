(function () {
  const projects = window.SUMMER_PROJECTS || [];
  const state = {
    type: "全部",
    subject: "全部",
    grade: "全部",
    viewMode: localStorage.getItem("scf_view_mode") || "simple"
  };

  const typeOptions = ["全部", "纯软", "软硬"];
  const subjectCatalog = [
    "计算机",
    "人工智能",
    "机械工程",
    "航空航天工程",
    "电子工程",
    "电子信息",
    "生物医学",
    "心理学",
    "应用数学",
    "统计学",
    "应用物理",
    "教育学",
    "通信工程",
    "运筹学",
    "电气工程",
    "经济/金融/商业",
    "环境/环保/生态",
    "生物/化学"
  ];
  const subjectOptions = ["全部"].concat(
    subjectCatalog.filter((subject) =>
      projects.some((project) => (project.subjects || []).includes(subject))
    )
  );
  const gradeOptions = ["全部", "5-8", "9-11"];

  const typeContainer = document.getElementById("typeFilters");
  const subjectContainer = document.getElementById("subjectFilters");
  const gradeContainer = document.getElementById("gradeFilters");
  const summaryEl = document.getElementById("filterSummary");
  const gridEl = document.getElementById("projectGrid");
  const statsGrid = document.getElementById("statsGrid");

  if (statsGrid) {
    statsGrid.innerHTML = "";
  }

  function renderFilters(container, options, key) {
    container.innerHTML = options
      .map((option) => {
        const active = state[key] === option ? "is-active" : "";
        return `<button class="filter-chip ${active}" type="button" data-key="${key}" data-value="${option}">${option}</button>`;
      })
      .join("");
  }

  function getFilteredProjects() {
    return projects.filter((project) => {
      const typeOk = state.type === "全部" || project.type === state.type;
      const subjectOk =
        state.subject === "全部" || (project.subjects || []).includes(state.subject);
      const gradeOk = state.grade === "全部" || project.grade === state.grade;
      return typeOk && subjectOk && gradeOk;
    });
  }

  function planButton(project) {
    if (!project.planPath) {
      return `<span class="btn btn-outline btn-disabled">资料整理中</span>`;
    }

    return `<a class="btn btn-outline" href="${encodeURI(project.planPath)}" download>下载 PDF</a>`;
  }

  function scheduleBlock(project) {
    if (!project.sessions || !project.sessions.length) return "";
    return `
      <div class="project-card__schedule">
        <span>开课时间</span>
        <div class="project-card__sessions">
          ${project.sessions
            .map(
              (session) => `
                <div class="project-card__session">
                  <em>${session.label}</em>
                  <strong>${session.date}</strong>
                </div>
              `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function durationLabel(project) {
    return project.durationLabel || `${project.days} 天`;
  }

  function durationMetaLabel(project) {
    return project.durationMetaLabel || "天数";
  }

  function renderListItem(project) {
    const subjects = project.subjects || [];
    const maxTags = 3;
    const visibleTags = subjects.slice(0, maxTags);
    const extraCount = subjects.length - maxTags;

    const tagsHtml = visibleTags
      .map((s) => `<span class="project-list-item__tag">${s}</span>`)
      .join("") +
      (extraCount > 0 ? `<span class="project-list-item__tag project-list-item__tag--more">+${extraCount}</span>` : "");

    const scheduleHtml = (project.sessions || [])
      .map((s) => `${s.date}`)
      .join("<br>");

    return `
      <a class="project-list-item project-list-item--${project.type}" href="/summer/${project.slug}" target="_top">
        <div class="project-list-item__main">
          <div class="project-list-item__name">
            <span class="project-list-item__type">${project.type}</span>
            ${project.name}
          </div>
          <div class="project-list-item__desc">${project.summary}</div>
        </div>
        <div class="project-list-item__tags">${tagsHtml}</div>
        <div class="project-list-item__schedule">${scheduleHtml || "待定"}</div>
        <div class="project-list-item__grade">${project.grade}</div>
      </a>
    `;
  }

  function renderListView(filtered) {
    gridEl.className = "project-list";
    gridEl.innerHTML =
      `<div class="project-list-header">
        <span>项目</span>
        <span>学科标签</span>
        <span>开课时间</span>
        <span>年级</span>
      </div>` +
      filtered.map(renderListItem).join("");
  }

  function renderCardView(filtered) {
    gridEl.className = "project-grid";
    gridEl.innerHTML = filtered
      .map(
        (project) => {
          const posterPath = `assets/project-media/${project.slug}/poster.jpg`;
          return `
          <article class="project-card project-card--${project.type}">
            <a class="project-card__poster" href="/summer/${project.slug}" target="_top" aria-label="查看 ${project.name} 详情">
              <img src="${encodeURI(posterPath)}" alt="${project.name} 项目海报" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='assets/project-media/shared/project-placeholder.svg';">
            </a>
            <div class="project-card__top">
              <span class="project-type">${project.type}</span>
              <span class="status-pill ${project.planPath ? "download-pill available" : "download-pill pending"}">${project.status}</span>
            </div>
            <div>
              <h3>${project.name}</h3>
              <p>${project.summary}</p>
            </div>
            <div class="chip-row">
              <span class="detail-chip">${project.grade} 年级</span>
              <span class="detail-chip">${project.direction}</span>
            </div>
            <div class="chip-row chip-row--subjects">
              ${(project.subjects || [])
                .map((subject) => `<span class="detail-chip detail-chip--subject">${subject}</span>`)
                .join("")}
            </div>
            ${scheduleBlock(project)}
            <div class="project-card__meta">
              <div><span>人数</span><strong>${project.seats} 人</strong></div>
              <div><span>${durationMetaLabel(project)}</span><strong>${durationLabel(project)}</strong></div>
              <div><span>基础要求</span><strong>${project.requirement}</strong></div>
            </div>
            <div class="project-card__actions">
              <a class="btn btn-primary" href="/summer/${project.slug}" target="_top">查看详情</a>
              ${planButton(project)}
            </div>
          </article>
        `;
        }
      )
      .join("");
  }

  function renderProjects() {
    const filtered = getFilteredProjects();
    const hasFilter =
      state.type !== "全部" || state.subject !== "全部" || state.grade !== "全部";

    summaryEl.textContent = hasFilter
      ? "已按当前条件筛选项目。可以继续调整项目类型、学科方向和适合年级。"
      : "可按项目类型、学科方向和适合年级快速筛选。";

    if (!filtered.length) {
      gridEl.className = state.viewMode === "simple" ? "project-list" : "project-grid";
      gridEl.innerHTML = `
        <div class="empty-state">
          <h3>当前条件下没有匹配项目</h3>
          <p>可以先切回"全部"，再重新组合筛选条件查看。</p>
        </div>
      `;
      return;
    }

    if (state.viewMode === "simple") {
      renderListView(filtered);
    } else {
      renderCardView(filtered);
    }
  }

  function syncViewToggle() {
    var toggleEl = document.getElementById("viewToggle");
    if (!toggleEl) return;
    toggleEl.querySelectorAll(".view-btn").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.dataset.view === state.viewMode);
    });
  }

  function bindViewToggle() {
    var toggleEl = document.getElementById("viewToggle");
    if (!toggleEl) return;
    toggleEl.addEventListener("click", function (event) {
      var btn = event.target.closest(".view-btn");
      if (!btn || btn.dataset.view === state.viewMode) return;
      state.viewMode = btn.dataset.view;
      localStorage.setItem("scf_view_mode", state.viewMode);
      syncViewToggle();
      renderProjects();
    });
  }

  function syncFilters() {
    renderFilters(typeContainer, typeOptions, "type");
    renderFilters(subjectContainer, subjectOptions, "subject");
    renderFilters(gradeContainer, gradeOptions, "grade");
  }

  function bindFilterEvents() {
    [typeContainer, subjectContainer, gradeContainer].forEach((container) => {
      container.addEventListener("click", (event) => {
        const button = event.target.closest(".filter-chip");
        if (!button) return;
        const key = button.dataset.key;
        const value = button.dataset.value;
        state[key] = value;
        syncFilters();
        renderProjects();
      });
    });
  }

  syncFilters();
  syncViewToggle();
  renderProjects();
  bindFilterEvents();
  bindViewToggle();
})();
