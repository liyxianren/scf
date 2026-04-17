(function () {
  const slug = window.PROJECT_SLUG;
  const project = window.getProjectBySlug ? window.getProjectBySlug(slug) : null;
  const supplementalDetail = window.PROJECT_DETAIL_CONTENT ? window.PROJECT_DETAIL_CONTENT[slug] : null;
  const richDetailPage = project && (project.detailPage || (supplementalDetail && supplementalDetail.detailPage));

  if (!project) {
    document.body.innerHTML = `
      <div class="site-shell">
        <div class="empty-state">
          <h3>没有找到对应项目</h3>
          <p>请返回首页重新选择项目。</p>
          <a class="btn btn-primary" href="../index.html">返回首页</a>
        </div>
      </div>
    `;
    return;
  }

  document.title = `${project.name} | 暑期项目站`;

  const subjectOverlap = function subjectOverlap(target) {
    const sourceSubjects = project.subjects || [];
    const targetSubjects = target.subjects || [];
    return targetSubjects.filter((subject) => sourceSubjects.includes(subject)).length;
  };

  const relatedProjects = (window.SUMMER_PROJECTS || [])
    .filter((item) => item.slug !== project.slug)
    .map((item) => ({
      ...item,
      overlapCount: subjectOverlap(item)
    }))
    .filter((item) => item.overlapCount > 0)
    .sort((a, b) => {
      if (b.overlapCount !== a.overlapCount) return b.overlapCount - a.overlapCount;
      if (a.type === project.type && b.type !== project.type) return -1;
      if (b.type === project.type && a.type !== project.type) return 1;
      return a.name.localeCompare(b.name, "zh-CN");
    })
    .slice(0, 3);

  function downloadButton() {
    if (!project.planPath) {
      return `<span class="btn btn-outline btn-disabled">计划书整理中</span>`;
    }

    return `<a class="btn btn-primary" href="${encodeURI(`../${project.planPath}`)}" download>下载 PDF 计划书</a>`;
  }

  function planSection() {
    if (!project.planPath) {
      return `
        <div class="note-banner">
          当前项目详情页和子链接已经先开通，但正式计划书还在整理中。
          后续补齐文档后，这里会直接接入下载与二维码分享入口。
        </div>
      `;
    }

    return `
      <div class="note-banner">
        当前已接入标准版 PDF 计划书下载入口，首页和详情页都会索引到同一份正式文档。
      </div>
    `;
  }

  function renderSessionStrip() {
    if (!project.sessions || !project.sessions.length) return "";
    return `
      <div class="detail-session-strip">
        <span class="detail-session-strip__label">开课时间</span>
        <div class="detail-session-strip__list">
          ${project.sessions
            .map(
              (item) => `
                <div class="detail-session-card">
                  <em>${item.label}</em>
                  <strong>${item.date}</strong>
                </div>
              `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderSessionMetaItems() {
    if (!project.sessions || !project.sessions.length) return "";
    return project.sessions
      .map(
        (item) => `
          <div class="meta-item">
            <div class="meta-label">${item.label}</div>
            <div class="meta-value">${item.date}</div>
          </div>
        `
      )
      .join("");
  }

  function durationLabel() {
    return project.durationLabel || `${project.days} 天`;
  }

  function durationMetaLabel() {
    return project.durationMetaLabel || "天数";
  }

  const relatedHtml = relatedProjects.length
    ? relatedProjects
        .map(
          (item) => `
            <a class="related-card" href="${item.slug}.html">
              <span class="project-type">${item.type}</span>
              <h3>${item.name}</h3>
              <p>${item.summary}</p>
            </a>
          `
        )
        .join("")
    : `
      <div class="empty-state">
        <h3>相关项目稍后补充</h3>
        <p>后续会根据标签体系自动推荐同方向项目。</p>
      </div>
    `;

  const VISUAL_PLACEHOLDER = "assets/project-media/shared/project-placeholder.svg";

  function isPdfPreview(src) {
    return /pdf-page-\d+\.(png|jpe?g|webp)$/i.test(src || "");
  }

  function isPosterImage(src) {
    return /poster(-card)?\.(png|jpe?g|webp)$/i.test(src || "");
  }

  function normalizeVisualFrame(frame, fallbackTitle) {
    if (!frame || !frame.src) return null;
    return {
      src: frame.src,
      alt: frame.alt || frame.caption || fallbackTitle || project.name,
      caption: frame.caption || fallbackTitle || "",
      title: frame.title || fallbackTitle || "",
      description: frame.description || ""
    };
  }

  function buildVisualFrames(detailPage) {
    const explicitFrames = (detailPage.visualFrames || [])
      .map((frame, index) =>
        normalizeVisualFrame(
          frame,
          index === 0 ? "项目海报" : index === 1 ? "场景参考" : "成果参考"
        )
      )
      .filter(Boolean);

    if (explicitFrames.length) {
      const padded = explicitFrames.slice(0, 3);
      while (padded.length < 3) {
        const title = padded.length === 1 ? "应用场景" : "成果参考";
        padded.push({
          src: VISUAL_PLACEHOLDER,
          alt: title,
          caption: "资料补充中",
          title,
          description: ""
        });
      }
      return padded;
    }

    const seen = new Set();
    const frames = [];
    const pushFrame = function pushFrame(src, meta) {
      if (!src || seen.has(src)) return;
      seen.add(src);
      frames.push(
        normalizeVisualFrame(
          {
            src,
            alt: meta.alt,
            caption: meta.caption,
            title: meta.title,
            description: meta.description
          },
          meta.title
        )
      );
    };

    if (detailPage.heroImage && !isPdfPreview(detailPage.heroImage)) {
      pushFrame(detailPage.heroImage, {
        title: "项目海报",
        caption: detailPage.heroCaption || `${project.name} 项目海报`,
        alt: detailPage.heroAlt || `${project.name} 项目海报`,
        description: "这一张用于首页、详情页和线下外宣场景，优先展示项目整体风格。"
      });
    }

    (detailPage.gallery || []).forEach((item) => {
      if (!item || !item.src || isPdfPreview(item.src) || isPosterImage(item.src)) return;
      pushFrame(item.src, {
        title: frames.length === 1 ? "场景参考" : "成果参考",
        caption: item.caption || "",
        alt: item.alt || item.caption || project.name,
        description:
          frames.length === 1
            ? "建议放应用场景、官方案例或产品参考图，帮助家长快速理解“这是做什么的”。"
            : "建议放成果效果、交互界面或产品细节参考图，帮助家长理解最后会做成什么样。"
      });
    });

    const slots = [
      {
        title: "项目海报",
        description: ""
      },
      {
        title: "应用场景",
        description: ""
      },
      {
        title: "成果参考",
        description: ""
      }
    ];

    const finalFrames = [];
    for (let index = 0; index < 3; index += 1) {
      if (frames[index]) {
        finalFrames.push(frames[index]);
      } else {
        finalFrames.push({
          src: VISUAL_PLACEHOLDER,
          alt: slots[index].title,
          caption: "资料补充中",
          title: slots[index].title,
          description: ""
        });
      }
    }
    return finalFrames;
  }

  function renderQuickView(detailPage) {
    if (!detailPage.quickView || !detailPage.quickView.length) return "";
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Quick View</p>
          <h2>家长一分钟看懂</h2>
        </div>
        <div class="quick-view-grid">
          ${detailPage.quickView
            .map(
              (item) => `
                <div class="quick-view-card">
                  <span>${item.label}</span>
                  <p>${item.value}</p>
                </div>
              `
            )
            .join("")}
        </div>
      </article>
    `;
  }

  function renderDocumentPreview(section) {
    if (!section.image) return "";
    return `
      <figure class="document-preview">
        <button
          class="document-preview__frame zoomable-media"
          type="button"
          data-image-src="${encodeURI(`../${section.image}`)}"
          data-image-alt="${section.imageAlt || section.title}"
          data-image-caption="${section.imageCaption || section.imageAlt || section.title}"
        >
          <img src="${encodeURI(`../${section.image}`)}" alt="${section.imageAlt || section.title}" loading="lazy" decoding="async">
          <span class="zoom-badge">点击放大</span>
        </button>
        ${
          section.imageCaption
            ? `<figcaption>${section.imageCaption}</figcaption>`
            : ""
        }
      </figure>
    `;
  }

  function renderInsightSection(section) {
    const paragraphs = (section.paragraphs || [])
      .map((item) => `<p>${item}</p>`)
      .join("");
    const bullets = (section.bullets || []).length
      ? `
        <ul class="detail-highlight">
          ${section.bullets.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      `
      : "";
    const compare = section.compare
      ? `
        <div class="table-shell">
          <table class="compare-table">
            <thead>
              <tr>
                ${section.compare.headers.map((item) => `<th>${item}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${section.compare.rows
                .map(
                  (row) => `
                    <tr>
                      ${row
                        .map(
                          (cell, index) =>
                            `<td data-label="${section.compare.headers[index] || ""}">${cell}</td>`
                        )
                        .join("")}
                    </tr>
                  `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      `
      : "";

    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Why It Matters</p>
          <h2>${section.title}</h2>
        </div>
        <div class="rich-copy">
          ${paragraphs}
          ${bullets}
        </div>
        ${compare}
      </article>
    `;
  }

  function renderScheduleSection(section) {
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">5-Day Sprint</p>
          <h2>${section.title}</h2>
          ${section.intro ? `<p>${section.intro}</p>` : ""}
        </div>
        <div class="schedule-layout schedule-layout--single">
          <div class="schedule-grid">
            ${(section.days || [])
              .map(
                (item) => `
                  <article class="schedule-card">
                    <span>${item.day}</span>
                    <h3>${item.title}</h3>
                    <p>${item.detail}</p>
                    <strong>当日产出：${item.output}</strong>
                  </article>
                `
              )
              .join("")}
          </div>
        </div>
      </article>
    `;
  }

  function renderCardsSection(section) {
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Project Framing</p>
          <h2>${section.title}</h2>
          ${section.intro ? `<p>${section.intro}</p>` : ""}
        </div>
        <div class="topic-grid">
          ${(section.cards || [])
            .map(
              (card) => `
                <article class="topic-card">
                  <h3>${card.title}</h3>
                  <p>${card.text}</p>
                </article>
              `
            )
            .join("")}
        </div>
      </article>
    `;
  }

  function renderResultsSection(section) {
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Outcomes</p>
          <h2>${section.title}</h2>
        </div>
        <div class="results-grid">
          ${(section.cards || [])
            .map(
              (card) => `
                <article class="result-card">
                  <h3>${card.title}</h3>
                  <p>${card.text}</p>
                </article>
              `
            )
            .join("")}
        </div>
      </article>
    `;
  }

  function renderFitSection(section) {
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Who It Fits</p>
          <h2>${section.title}</h2>
        </div>
        <div class="fit-grid">
          <div class="fit-card">
            <span>特别适合</span>
            <ul class="detail-highlight">
              ${(section.goodFit || []).map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
          <div class="fit-card fit-card--muted">
            <span>不太适合</span>
            <ul class="detail-highlight">
              ${(section.notFit || []).map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </div>
        </div>
      </article>
    `;
  }

  function renderFaqSection(section) {
    return `
      <article class="section-card section-card--rich">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">FAQ</p>
          <h2>${section.title}</h2>
        </div>
        <div class="faq-layout faq-layout--single">
          <div class="faq-grid">
            ${(section.items || [])
              .map(
                (item) => `
                  <article class="faq-card">
                    <h3>${item.q}</h3>
                    <p>${item.a}</p>
                  </article>
                `
            )
            .join("")}
          </div>
        </div>
      </article>
    `;
  }

  function renderVisualFramework(detailPage) {
    const frames = buildVisualFrames(detailPage);
    if (!frames.length) return "";
    return `
      <section class="visual-framework-section">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Visual Framework</p>
          <h2>项目图集</h2>
          <p>通过海报、应用场景和成果参考，更直观看懂这个项目。</p>
        </div>
        <div class="visual-framework-grid">
          ${frames
            .map(
              (item) => `
                <figure class="visual-framework-card">
                  <div class="visual-framework-card__meta">
                    <span>${item.title}</span>
                  </div>
                  <button
                    class="visual-framework-card__button zoomable-media"
                    type="button"
                    data-image-src="${encodeURI(`../${item.src}`)}"
                    data-image-alt="${item.alt || item.title || project.name}"
                    data-image-caption="${item.caption || item.alt || item.title || project.name}"
                  >
                    <img src="${encodeURI(`../${item.src}`)}" alt="${item.alt || item.title || project.name}" loading="lazy" decoding="async">
                    <span class="zoom-badge">点击放大</span>
                  </button>
                  <figcaption>${item.caption || item.title || ""}</figcaption>
                </figure>
              `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function renderRichSections(sections) {
    if (!sections || !sections.length) return "";

    var insight = null;
    var schedule = null;
    var results = null;
    var fit = null;
    var faq = null;

    sections.forEach(function (s) {
      if (s.type === "insight" && !insight) insight = s;
      if (s.type === "schedule" && !schedule) schedule = s;
      if (s.type === "results" && !results) results = s;
      if (s.type === "fit" && !fit) fit = s;
      if (s.type === "faq" && !faq) faq = s;
    });

    var html = "";

    // Board 1: Overview (insight + results + fit merged)
    if (insight || results || fit) {
      var overviewParts = [];

      if (insight) {
        var paragraphs = (insight.paragraphs || []).map(function (p) { return "<p>" + p + "</p>"; }).join("");
        var bullets = (insight.bullets || []).length
          ? '<ul class="detail-highlight">' + insight.bullets.map(function (b) { return "<li>" + b + "</li>"; }).join("") + "</ul>"
          : "";
        overviewParts.push(paragraphs + bullets);
      }

      if (results) {
        var resultsHtml = '<div class="overview-results-grid">' +
          (results.cards || []).map(function (c) {
            return '<div class="overview-result-item"><strong>' + c.title + '</strong><span>' + c.text + '</span></div>';
          }).join("") + "</div>";
        overviewParts.push('<h3 class="overview-sub">' + results.title + '</h3>' + resultsHtml);
      }

      if (fit) {
        var goodFitHtml = (fit.goodFit || []).map(function (f) { return '<span class="overview-fit-tag overview-fit-tag--good">' + f + '</span>'; }).join("");
        var notFitHtml = (fit.notFit || []).map(function (f) { return '<span class="overview-fit-tag overview-fit-tag--muted">' + f + '</span>'; }).join("");
        overviewParts.push(
          '<h3 class="overview-sub">适合人群</h3>' +
          '<div class="overview-fit">' +
            '<div class="overview-fit-group"><span class="overview-fit-label">适合</span>' + goodFitHtml + '</div>' +
            (notFitHtml ? '<div class="overview-fit-group"><span class="overview-fit-label overview-fit-label--muted">不太适合</span>' + notFitHtml + '</div>' : '') +
          '</div>'
        );
      }

      html += '<article class="section-card section-card--rich">' +
        '<div class="rich-section__head">' +
          '<p class="eyebrow eyebrow--dark">Overview</p>' +
          '<h2>' + (insight ? insight.title : '项目概览') + '</h2>' +
        '</div>' +
        '<div class="rich-copy">' + overviewParts.join("") + '</div>' +
      '</article>';
    }

    // Board 2: Schedule (compact)
    if (schedule && schedule.days && schedule.days.length) {
      html += '<article class="section-card section-card--rich">' +
        '<div class="rich-section__head">' +
          '<p class="eyebrow eyebrow--dark">Schedule</p>' +
          '<h2>' + schedule.title + '</h2>' +
        '</div>' +
        '<div class="schedule-compact">' +
          schedule.days.map(function (d) {
            return '<div class="schedule-compact__item">' +
              '<span class="schedule-compact__day">' + d.day + '</span>' +
              '<div class="schedule-compact__content">' +
                '<strong>' + d.title + '</strong>' +
                '<span>' + d.output + '</span>' +
              '</div>' +
            '</div>';
          }).join("") +
        '</div>' +
      '</article>';
    }

    // Board 3: FAQ (accordion)
    if (faq && faq.items && faq.items.length) {
      html += '<article class="section-card section-card--rich">' +
        '<div class="rich-section__head">' +
          '<p class="eyebrow eyebrow--dark">FAQ</p>' +
          '<h2>' + faq.title + '</h2>' +
        '</div>' +
        '<div class="faq-accordion">' +
          faq.items.map(function (item, idx) {
            return '<div class="faq-accordion__item">' +
              '<button class="faq-accordion__toggle" type="button" data-faq-idx="' + idx + '">' +
                '<span>' + item.q + '</span>' +
                '<span class="faq-accordion__arrow">+</span>' +
              '</button>' +
              '<div class="faq-accordion__body" data-faq-body="' + idx + '">' +
                '<p>' + item.a + '</p>' +
              '</div>' +
            '</div>';
          }).join("") +
        '</div>' +
      '</article>';
    }

    return html;
  }

  function renderGallery(detailPage) {
    if (!detailPage.gallery || !detailPage.gallery.length) return "";
    return `
      <section class="gallery-section">
        <div class="rich-section__head">
          <p class="eyebrow eyebrow--dark">Visual Preview</p>
          <h2>资料页预览</h2>
          <p>先在网页里看核心信息，感兴趣再下载完整版 PDF 继续细看。</p>
        </div>
        <div class="gallery-grid">
          ${detailPage.gallery
            .map(
              (item) => `
                <figure class="gallery-card">
                  <button
                    class="gallery-card__button zoomable-media"
                    type="button"
                    data-image-src="${encodeURI(`../${item.src}`)}"
                    data-image-alt="${item.alt || item.caption}"
                    data-image-caption="${item.caption || item.alt || ""}"
                  >
                    <img src="${encodeURI(`../${item.src}`)}" alt="${item.alt || item.caption}" loading="lazy" decoding="async">
                    <span class="zoom-badge">点击放大</span>
                  </button>
                  <figcaption>${item.caption}</figcaption>
                </figure>
              `
            )
            .join("")}
        </div>
      </section>
    `;
  }

  function renderHeroMedia(detailPage) {
    if (!detailPage.heroImage) return "";

    if (detailPage.heroMode === "document") {
      return `
        <div class="media-card media-card--hero media-card--hero-document">
          <button
            class="gallery-card__button zoomable-media"
            type="button"
            data-image-src="${encodeURI(`../${detailPage.heroImage}`)}"
            data-image-alt="${detailPage.heroAlt || detailPage.heroCaption || project.name}"
            data-image-caption="${detailPage.heroCaption || project.name}"
          >
            <img src="${encodeURI(`../${detailPage.heroImage}`)}" alt="${detailPage.heroAlt || detailPage.heroCaption || project.name}" loading="eager" fetchpriority="high" decoding="async">
            <span class="zoom-badge">点击放大</span>
          </button>
          ${detailPage.heroCaption ? `<span>${detailPage.heroCaption}</span>` : ""}
        </div>
      `;
    }

    if (detailPage.heroMode === "poster") {
      return `
        <div class="media-card media-card--hero media-card--poster">
          <button
            class="gallery-card__button zoomable-media"
            type="button"
            data-image-src="${encodeURI(`../${detailPage.heroImage}`)}"
            data-image-alt="${detailPage.heroAlt || detailPage.heroCaption || project.name}"
            data-image-caption="${detailPage.heroCaption || project.name}"
          >
            <img src="${encodeURI(`../${detailPage.heroImage}`)}" alt="${detailPage.heroAlt || detailPage.heroCaption || project.name}" loading="eager" fetchpriority="high" decoding="async">
            <span class="zoom-badge">点击放大</span>
          </button>
          ${detailPage.heroCaption ? `<span>${detailPage.heroCaption}</span>` : ""}
        </div>
      `;
    }

    return `
      <div class="media-card media-card--hero">
        <img src="${encodeURI(`../${detailPage.heroImage}`)}" alt="${detailPage.heroAlt || detailPage.heroCaption || project.name}" loading="eager" fetchpriority="high" decoding="async">
        ${detailPage.heroCaption ? `<span>${detailPage.heroCaption}</span>` : ""}
      </div>
    `;
  }

  function renderRichDetailPage(detailPage) {
    return `
      <div class="site-shell">
        <header class="topbar-detail">
          <a class="brand" href="../index.html">
            <span class="brand-mark">SP</span>
            <span class="brand-text">
              <strong>Summer Project Studio</strong>
              <small>返回项目首页</small>
            </span>
          </a>
          <a class="detail-back" href="../index.html">返回项目矩阵</a>
        </header>

        <section class="detail-hero detail-hero--feature">
          <div>
            <p class="eyebrow">${detailPage.kicker || "Project Detail"}</p>
            <h1>${project.name}</h1>
            <p>${project.intro}</p>
            <div class="detail-meta">
              <span class="detail-chip">${project.type}</span>
              <span class="detail-chip">${project.grade} 年级</span>
              <span class="detail-chip">${project.direction}</span>
              <span class="detail-chip">${durationLabel()}</span>
            </div>
            <div class="chip-row chip-row--subjects" style="margin-top:14px;">
              ${(project.subjects || [])
                .map((subject) => `<span class="detail-chip detail-chip--subject">${subject}</span>`)
                .join("")}
            </div>
            <div class="detail-actions">
              ${downloadButton()}
              <a class="btn btn-secondary" href="../index.html">继续看其他项目</a>
            </div>
            ${renderSessionStrip()}
          </div>
          <aside class="detail-visual">
            ${renderHeroMedia(detailPage)}
          </aside>
        </section>

        ${renderQuickView(detailPage)}

        ${renderVisualFramework(detailPage)}

        <section class="detail-layout detail-layout--feature">
          <div class="detail-main detail-main--rich">
            ${renderRichSections(detailPage.sections)}

            <article class="section-card section-card--rich">
              <div class="rich-section__head">
                <p class="eyebrow eyebrow--dark">Download</p>
                <h2>想继续细看，就下载完整计划书</h2>
                <p>网页版先帮助家长快速判断项目值不值得看、适不适合孩子；如果准备进一步了解完整课时安排、资料结构和详细表格，再下载正式 PDF 即可。</p>
              </div>
              <div class="detail-actions">
                ${downloadButton()}
                <a class="btn btn-outline" href="../index.html">返回项目总览</a>
              </div>
            </article>
          </div>

          <aside class="detail-side">
            <div class="detail-card">
              <h3>项目信息</h3>
              <div class="meta-list">
                <div class="meta-item">
                  <div class="meta-label">学科范围</div>
                  <div class="meta-value">${(project.subjects || []).join(" / ")}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">适合年级</div>
                  <div class="meta-value">${project.grade}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">项目方向</div>
                  <div class="meta-value">${project.direction}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">人数</div>
                  <div class="meta-value">${project.seats} 人</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">${durationMetaLabel()}</div>
                  <div class="meta-value">${durationLabel()}</div>
                </div>
                ${renderSessionMetaItems()}
                <div class="meta-item">
                  <div class="meta-label">基础要求</div>
                  <div class="meta-value">${project.requirement}</div>
                </div>
                <div class="meta-item">
                  <div class="meta-label">资料状态</div>
                  <div class="meta-value">${project.status}</div>
                </div>
              </div>
            </div>

            <div class="detail-card">
              <h3>项目亮点</h3>
              <ul class="detail-highlight">
                ${project.focus.map((item) => `<li>${item}</li>`).join("")}
              </ul>
            </div>
          </aside>
        </section>

        <section>
          <div class="related-heading">
            <div>
              <p class="eyebrow" style="color: var(--rust);">Related Projects</p>
              <h2>相近学科项目</h2>
            </div>
            <a class="btn btn-outline" href="../index.html">返回总览</a>
          </div>
          <div class="related-grid">
            ${relatedHtml}
          </div>
        </section>

        <div class="image-lightbox" id="imageLightbox" hidden>
          <button class="image-lightbox__backdrop" type="button" data-lightbox-close></button>
          <div class="image-lightbox__dialog" role="dialog" aria-modal="true" aria-label="图片预览">
            <button class="image-lightbox__close" type="button" data-lightbox-close>关闭</button>
            <img id="lightboxImage" src="" alt="">
            <p id="lightboxCaption"></p>
          </div>
        </div>
      </div>
    `;
  }

  function bindImageLightbox() {
    const root = document.getElementById("projectDetailApp");
    const lightbox = document.getElementById("imageLightbox");
    const lightboxImage = document.getElementById("lightboxImage");
    const lightboxCaption = document.getElementById("lightboxCaption");

    if (!root || !lightbox || !lightboxImage || !lightboxCaption) return;

    root.addEventListener("click", (event) => {
      const trigger = event.target.closest(".zoomable-media");
      if (trigger) {
        lightboxImage.src = trigger.dataset.imageSrc || "";
        lightboxImage.alt = trigger.dataset.imageAlt || "";
        lightboxCaption.textContent = trigger.dataset.imageCaption || "";
        lightbox.hidden = false;
        document.body.classList.add("has-lightbox-open");
        return;
      }

      if (event.target.closest("[data-lightbox-close]")) {
        lightbox.hidden = true;
        lightboxImage.src = "";
        lightboxCaption.textContent = "";
        document.body.classList.remove("has-lightbox-open");
      }
    });
  }

  function bindFaqAccordion() {
    var root = document.getElementById("projectDetailApp");
    if (!root) return;
    root.addEventListener("click", function (event) {
      var toggle = event.target.closest(".faq-accordion__toggle");
      if (!toggle) return;
      var idx = toggle.dataset.faqIdx;
      var body = root.querySelector('[data-faq-body="' + idx + '"]');
      if (!body) return;
      var isOpen = body.classList.contains("is-open");
      body.classList.toggle("is-open");
      toggle.querySelector(".faq-accordion__arrow").textContent = isOpen ? "+" : "-";
    });
  }

  if (richDetailPage) {
    document.getElementById("projectDetailApp").innerHTML = renderRichDetailPage(richDetailPage);
    bindImageLightbox();
    bindFaqAccordion();
    return;
  }

  document.getElementById("projectDetailApp").innerHTML = `
    <div class="site-shell">
      <header class="topbar-detail">
        <a class="brand" href="../index.html">
          <span class="brand-mark">SP</span>
          <span class="brand-text">
            <strong>Summer Project Studio</strong>
            <small>返回项目首页</small>
          </span>
        </a>
        <a class="detail-back" href="../index.html">返回项目矩阵</a>
      </header>

      <section class="detail-hero">
        <div>
          <p class="eyebrow">Project Detail</p>
          <h1>${project.name}</h1>
          <p>${project.intro}</p>
          <div class="detail-meta">
            <span class="detail-chip">${project.type}</span>
            <span class="detail-chip">${project.grade} 年级</span>
            <span class="detail-chip">${project.direction}</span>
            <span class="detail-chip">${durationLabel()}</span>
          </div>
          <div class="chip-row chip-row--subjects" style="margin-top:14px;">
            ${(project.subjects || [])
              .map((subject) => `<span class="detail-chip detail-chip--subject">${subject}</span>`)
              .join("")}
          </div>
          <div class="detail-actions">
            ${downloadButton()}
            <a class="btn btn-secondary" href="../index.html">继续看其他项目</a>
          </div>
          ${renderSessionStrip()}
        </div>
        <aside class="detail-side">
          <div class="detail-card">
            <span class="status-pill ${project.planPath ? "download-pill available" : "download-pill pending"}">${project.status}</span>
            <strong style="display:block;margin-top:12px;font-size:1.35rem;">${project.summary}</strong>
            <p style="margin-top:12px;">当前先把子链接和基本展示做起来，后续再叠加标签、二维码和师资内容。</p>
          </div>
        </aside>
      </section>

      <section class="detail-layout">
        <div class="detail-main">
          <article class="section-card">
            <h2>项目亮点</h2>
            <ul class="detail-highlight">
              ${project.focus.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </article>

          <article class="section-card">
            <h2>学生能带走什么</h2>
            <ul class="detail-highlight">
              ${project.outcomes.map((item) => `<li>${item}</li>`).join("")}
            </ul>
          </article>

          <article class="section-card">
            <h2>计划书与资料</h2>
            <p>当前详情页已经支持资料位接入。后续如果补图片、二维码、课时和课程大纲，也会继续放在这一页。</p>
            ${planSection()}
          </article>
        </div>

        <aside class="detail-side">
          <div class="detail-card">
            <h3>项目信息</h3>
            <div class="meta-list">
              <div class="meta-item">
                <div class="meta-label">学科范围</div>
                <div class="meta-value">${(project.subjects || []).join(" / ")}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">适合年级</div>
                <div class="meta-value">${project.grade}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">项目方向</div>
                <div class="meta-value">${project.direction}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">人数</div>
                <div class="meta-value">${project.seats} 人</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">${durationMetaLabel()}</div>
                <div class="meta-value">${durationLabel()}</div>
              </div>
              ${renderSessionMetaItems()}
              <div class="meta-item">
                <div class="meta-label">基础要求</div>
                <div class="meta-value">${project.requirement}</div>
              </div>
              <div class="meta-item">
                <div class="meta-label">资料状态</div>
                <div class="meta-value">${project.status}</div>
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section>
        <div class="related-heading">
          <div>
            <p class="eyebrow" style="color: var(--rust);">Related Projects</p>
            <h2>相近学科项目</h2>
          </div>
          <a class="btn btn-outline" href="../index.html">返回总览</a>
        </div>
        <div class="related-grid">
          ${relatedHtml}
        </div>
      </section>
    </div>
  `;
})();
