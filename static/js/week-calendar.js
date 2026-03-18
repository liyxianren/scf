/**
 * WeekCalendar - Reusable read-only week calendar view for dashboards
 *
 * Usage:
 *   const cal = new WeekCalendar(containerEl, {
 *     fetchUrl: '/auth/api/teacher/my-schedule',
 *     progressMap: {},     // optional: { scheduleId: { session_number, total, is_ending } }
 *     onCourseClick: null, // optional: function(course)
 *   });
 *   cal.render();
 *   cal.prev() / cal.next() / cal.today()
 */
class WeekCalendar {
  constructor(container, options = {}) {
    this.container = container;
    this.progressMap = options.progressMap || {};
    this.onCourseClick = options.onCourseClick || null;
    this.teacherFilter = options.teacherFilter || null; // filter courses by teacher name
    this.emptyText = options.emptyText || '本周暂无课程'; // shown when no courses

    this.GRID_START = 8;
    this.GRID_END = 21;
    this.HOUR_HEIGHT = 56;
    this.DAY_NAMES = ['周一','周二','周三','周四','周五','周六','周日'];

    this.weekStart = this._getWeekStart(new Date());
    this.scheduleData = [];

    this._injectStyles();
    this._buildDOM();
  }

  /* ===== Public ===== */
  async render() {
    await this._loadData();
    this._renderHeader();
    this._renderBody();
    this._renderEmptyOverlay();
    this._scrollToFirstCourse();
  }

  prev() { this.weekStart.setDate(this.weekStart.getDate() - 7); this.render(); }
  next() { this.weekStart.setDate(this.weekStart.getDate() + 7); this.render(); }
  today() { this.weekStart = this._getWeekStart(new Date()); this.render(); }

  setProgressMap(pm) { this.progressMap = pm; }

  /* ===== DOM ===== */
  _buildDOM() {
    this.container.innerHTML = '';
    this.container.classList.add('wc-root');

    // Nav bar
    const nav = document.createElement('div');
    nav.className = 'wc-nav';
    nav.innerHTML = `
      <button class="wc-nav-btn" data-action="prev"><span class="material-icons" style="font-size:1.1rem">chevron_left</span></button>
      <button class="wc-nav-btn wc-text-btn" data-action="today">今天</button>
      <button class="wc-nav-btn" data-action="next"><span class="material-icons" style="font-size:1.1rem">chevron_right</span></button>
      <span class="wc-week-label" id="wcLabel"></span>`;
    nav.addEventListener('click', e => {
      const btn = e.target.closest('[data-action]');
      if (!btn) return;
      this[btn.dataset.action]();
    });
    this.container.appendChild(nav);

    // Grid container
    const grid = document.createElement('div');
    grid.className = 'wc-grid-container';
    grid.innerHTML = `
      <div class="wc-header" id="wcHeader"></div>
      <div class="wc-body-scroll">
        <div class="wc-body" id="wcBody"></div>
      </div>`;
    this.container.appendChild(grid);

    // Tooltip
    const tip = document.createElement('div');
    tip.className = 'wc-tooltip';
    tip.id = 'wcTooltip';
    tip.innerHTML = '<div class="wct-name"></div><div class="wct-time"></div><div class="wct-teacher"></div><div class="wct-students"></div>';
    this.container.appendChild(tip);
  }

  /* ===== Data ===== */
  async _loadData() {
    const days = this._getWeekDays();
    const start = this._fmt(days[0]);
    const end = this._fmt(days[6]);
    try {
      const res = await fetch(`/oa/api/schedules/by-date?start=${start}&end=${end}`);
      const json = await res.json();
      if (json.success) {
        let data = json.data;
        if (this.teacherFilter) {
          data = data.filter(s => s.teacher === this.teacherFilter);
        }
        this.scheduleData = data;
      }
    } catch(e) { console.error(e); }
  }

  /* ===== Render ===== */
  _renderHeader() {
    const days = this._getWeekDays();
    const today = new Date();
    const label = this.container.querySelector('#wcLabel');
    if (label) {
      const s = days[0], e = days[6];
      label.textContent = `${s.getFullYear()}年${s.getMonth()+1}月${s.getDate()}日 — ${e.getMonth()+1}月${e.getDate()}日`;
    }

    const header = this.container.querySelector('#wcHeader');
    let html = '<div class="wc-corner"></div>';
    days.forEach((d, i) => {
      const isToday = this._sameDay(d, today);
      html += `<div class="wc-hcell${isToday ? ' wc-today' : ''}">
        <div class="wc-hday">${this.DAY_NAMES[i]}</div>
        <div class="wc-hdate">${d.getDate()}</div>
      </div>`;
    });
    header.innerHTML = html;
  }

  _renderBody() {
    const days = this._getWeekDays();
    const body = this.container.querySelector('#wcBody');
    const totalH = this.GRID_END - this.GRID_START;
    const gridHeight = totalH * this.HOUR_HEIGHT;

    // Time col
    let timeHtml = '<div class="wc-timecol" style="position:relative;">';
    for (let h = this.GRID_START; h <= this.GRID_END; h++) {
      const top = (h - this.GRID_START) * this.HOUR_HEIGHT;
      timeHtml += `<div class="wc-tlabel" style="position:absolute;top:${top}px;left:0;right:0;">${String(h).padStart(2,'0')}:00</div>`;
    }
    timeHtml += '</div>';

    // Day cols
    let dayHtml = '';
    days.forEach((d) => {
      const dateStr = this._fmt(d);
      const dayCourses = this.scheduleData.filter(s => s.date === dateStr);

      let col = `<div class="wc-daycol" style="position:relative;height:${gridHeight}px;">`;
      // Hour lines
      for (let h = this.GRID_START; h <= this.GRID_END; h++) {
        const top = (h - this.GRID_START) * this.HOUR_HEIGHT;
        col += `<div class="wc-hline" style="top:${top}px;"></div>`;
      }

      // Courses
      const laid = this._layout(dayCourses);
      laid.forEach(c => {
        const pos = this._blockPos(c.time_start, c.time_end);
        const color = c.color_tag || 'blue';
        const colW = (100 - 1) / (c._totalCols || 1);
        const colL = (c._col || 0) * colW;
        const narrow = c._totalCols >= 3 ? ' narrow' : '';
        const prog = this.progressMap[c.id];
        const ending = (prog && prog.is_ending) ? ' wc-ending' : '';
        const progHtml = prog ? `<div class="wc-prog">第${prog.session_number}/${prog.total}节</div>` : '';
        const showStudents = pos.height > 50;
        const esc = this._esc;

        col += `<div class="wc-block ${color}${ending}${narrow}"
          style="top:${pos.top}px;height:${pos.height}px;width:${colW}%;left:${colL}%;"
          data-name="${esc(c.course_name)}" data-time="${c.time_start}-${c.time_end}"
          data-teacher="${esc(c.teacher||'')}" data-students="${esc(c.students||'')}">
          <div class="wc-bname">${esc(c.course_name)}</div>
          ${progHtml}
          <div class="wc-btime">${c.time_start}-${c.time_end}</div>
          ${c.teacher ? `<div class="wc-bteacher">${esc(c.teacher)}</div>` : ''}
          ${showStudents && c.students ? `<div class="wc-bstudents">${esc(c.students)}</div>` : ''}
        </div>`;
      });

      col += '</div>';
      dayHtml += col;
    });

    body.innerHTML = timeHtml + dayHtml;
    body.style.height = gridHeight + 'px';
    this._bindTooltips(body);
  }

  _renderEmptyOverlay() {
    let overlay = this.container.querySelector('.wc-empty-overlay');
    if (this.scheduleData.length > 0) {
      if (overlay) overlay.remove();
      return;
    }
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'wc-empty-overlay';
    }
    overlay.innerHTML = `<span class="material-icons" style="font-size:2.4rem;color:#cbd5e1">event_busy</span><p>${this.emptyText}</p>`;
    const scroll = this.container.querySelector('.wc-body-scroll');
    if (scroll) scroll.appendChild(overlay);
  }

  _scrollToFirstCourse() {
    if (!this.scheduleData.length) return;
    const scroll = this.container.querySelector('.wc-body-scroll');
    if (!scroll) return;
    // Find earliest start time this week
    let earliest = 23;
    this.scheduleData.forEach(c => {
      const h = parseInt(c.time_start.split(':')[0]);
      if (h < earliest) earliest = h;
    });
    // Scroll to 1 hour before the earliest course
    const targetHour = Math.max(earliest - 1, this.GRID_START);
    const scrollTop = (targetHour - this.GRID_START) * this.HOUR_HEIGHT;
    scroll.scrollTop = scrollTop;
  }

  /* ===== Layout (Google Calendar overlap) ===== */
  _layout(courses) {
    if (!courses.length) return courses;
    courses.sort((a, b) => a.time_start.localeCompare(b.time_start) || a.time_end.localeCompare(b.time_end));
    const groups = [];
    let gEnd = null, cur = [];
    courses.forEach(c => {
      if (gEnd !== null && c.time_start >= gEnd) { groups.push(cur); cur = []; gEnd = null; }
      cur.push(c);
      gEnd = gEnd === null ? c.time_end : (c.time_end > gEnd ? c.time_end : gEnd);
    });
    if (cur.length) groups.push(cur);

    groups.forEach(g => {
      const cols = [];
      g.forEach(c => {
        let placed = false;
        for (let i = 0; i < cols.length; i++) {
          if (c.time_start >= cols[i]) { cols[i] = c.time_end; c._col = i; placed = true; break; }
        }
        if (!placed) { c._col = cols.length; cols.push(c.time_end); }
      });
      g.forEach(c => c._totalCols = cols.length);
    });
    return courses;
  }

  _blockPos(start, end) {
    const [sh, sm] = start.split(':').map(Number);
    const [eh, em] = end.split(':').map(Number);
    const sOff = (sh - this.GRID_START) + sm / 60;
    const eOff = (eh - this.GRID_START) + em / 60;
    return { top: sOff * this.HOUR_HEIGHT, height: Math.max((eOff - sOff) * this.HOUR_HEIGHT, 18) };
  }

  /* ===== Tooltips ===== */
  _bindTooltips(container) {
    const tip = this.container.querySelector('#wcTooltip');
    if (!tip) return;
    container.querySelectorAll('.wc-block').forEach(block => {
      block.addEventListener('mouseenter', function(e) {
        tip.querySelector('.wct-name').textContent = this.dataset.name;
        tip.querySelector('.wct-time').textContent = this.dataset.time;
        tip.querySelector('.wct-teacher').textContent = this.dataset.teacher ? '教师: ' + this.dataset.teacher : '';
        tip.querySelector('.wct-students').textContent = this.dataset.students ? '学生: ' + this.dataset.students : '';
        tip.style.display = 'block';
        moveTip(e);
      });
      block.addEventListener('mousemove', moveTip);
      block.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    });
    function moveTip(e) {
      let x = e.clientX + 12, y = e.clientY + 12;
      if (x + 220 > window.innerWidth) x = e.clientX - 232;
      if (y + 100 > window.innerHeight) y = e.clientY - 112;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    }
  }

  /* ===== Helpers ===== */
  _getWeekStart(d) {
    const dt = new Date(d);
    const day = dt.getDay();
    dt.setDate(dt.getDate() - (day === 0 ? 6 : day - 1));
    dt.setHours(0,0,0,0);
    return dt;
  }

  _getWeekDays() {
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(this.weekStart);
      d.setDate(d.getDate() + i);
      days.push(d);
    }
    return days;
  }

  _fmt(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }

  _sameDay(a, b) {
    return a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate();
  }

  _esc(s) {
    if (!s) return '';
    const d = document.createElement('div'); d.textContent = s; return d.innerHTML;
  }

  /* ===== Styles ===== */
  _injectStyles() {
    if (document.getElementById('wc-styles')) return;
    const style = document.createElement('style');
    style.id = 'wc-styles';
    style.textContent = `
.wc-root{position:relative}
.wc-nav{display:flex;align-items:center;gap:8px;margin-bottom:14px}
.wc-nav-btn{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:8px;border:1px solid #d1d5db;background:#fff;cursor:pointer;transition:.15s}
.wc-nav-btn:hover{border-color:#0ea5e9;color:#0ea5e9}
.wc-text-btn{width:auto;padding:0 14px;font-size:.82rem;font-weight:700}
.wc-week-label{font-size:.95rem;font-weight:700;color:#111827;margin-left:8px}
.wc-grid-container{background:#fff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden}
.wc-header{display:grid;grid-template-columns:50px repeat(7,1fr);border-bottom:2px solid #e5e7eb;background:#f9fafb}
.wc-corner{padding:10px 4px}
.wc-hcell{padding:8px 4px;text-align:center;border-left:1px solid #e5e7eb}
.wc-hday{font-size:.72rem;color:#6b7280;font-weight:500}
.wc-hdate{font-size:1rem;font-weight:700;color:#1f2937;margin-top:1px}
.wc-hcell.wc-today{background:#eff6ff}
.wc-hcell.wc-today .wc-hdate{background:#0ea5e9;color:#fff;display:inline-block;width:26px;height:26px;line-height:26px;border-radius:50%;text-align:center}
.wc-body-scroll{overflow-y:auto;max-height:560px;position:relative}
.wc-body{display:grid;grid-template-columns:50px repeat(7,1fr);position:relative}
.wc-timecol{border-right:1px solid #e5e7eb}
.wc-tlabel{font-size:.68rem;color:#9ca3af;font-weight:500;display:flex;align-items:flex-start;justify-content:center;position:relative;top:-7px}
.wc-daycol{position:relative;border-left:1px solid #e5e7eb}
.wc-hline{position:absolute;left:0;right:0;border-top:1px solid #f3f4f6}
.wc-block{position:absolute;border-radius:5px;padding:3px 5px;cursor:default;overflow:hidden;font-size:.72rem;line-height:1.3;z-index:2;transition:box-shadow .15s;border-left:3px solid;box-sizing:border-box}
.wc-block:hover{box-shadow:0 2px 8px rgba(0,0,0,.15);z-index:3}
.wc-bname{font-weight:600}
.wc-btime{font-size:.65rem;opacity:.8}
.wc-bteacher{font-size:.67rem;margin-top:1px}
.wc-bstudents{font-size:.65rem;opacity:.7;margin-top:1px}
.wc-prog{font-size:.6rem;opacity:.7}
.wc-block.blue{background:#dbeafe;color:#1e40af;border-color:#3b82f6}
.wc-block.green{background:#dcfce7;color:#166534;border-color:#22c55e}
.wc-block.purple{background:#f3e8ff;color:#7c3aed;border-color:#8b5cf6}
.wc-block.orange{background:#fed7aa;color:#9a3412;border-color:#f97316}
.wc-block.red{background:#fee2e2;color:#991b1b;border-color:#ef4444}
.wc-block.teal{background:#ccfbf1;color:#115e59;border-color:#14b8a6}
.wc-block.narrow .wc-bteacher,.wc-block.narrow .wc-bstudents{display:none}
.wc-block.wc-ending{border:2px solid #ef4444!important;border-left-width:3px!important;animation:wc-breathe 2.5s ease-in-out infinite}
@keyframes wc-breathe{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}50%{box-shadow:0 0 8px 3px rgba(239,68,68,.35)}}
.wc-tooltip{position:fixed;z-index:1000;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:8px 12px;width:220px;box-shadow:0 4px 16px rgba(0,0,0,.12);pointer-events:none;font-size:.82rem;line-height:1.5;display:none}
.wct-name{font-weight:600;font-size:.88rem;margin-bottom:2px}
.wct-time{color:#6b7280}
.wct-teacher{color:#374151}
.wct-students{color:#6b7280;font-size:.78rem}
.wc-empty-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(248,250,252,.85);z-index:5;border-radius:0 0 14px 14px}
.wc-empty-overlay p{margin:8px 0 0;font-size:.95rem;color:#94a3b8;font-weight:600}
@media(max-width:640px){.wc-header,.wc-body{grid-template-columns:40px repeat(7,1fr)}.wc-block{font-size:.65rem;padding:2px 3px}}
`;
    document.head.appendChild(style);
  }
}
