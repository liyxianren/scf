/**
 * TimeGrid - Reusable weekly time selection grid component
 *
 * Usage:
 *   const grid = new TimeGrid(containerEl, { startHour: 8, endHour: 22 });
 *   grid.getSlots()        // [{day:0, start:"14:00", end:"16:00"}, ...]
 *   grid.setSlots(slots)   // load slots
 *   grid.clear()           // clear all
 *   grid.setMode(mode)     // 'available' or 'preferred'
 */
class TimeGrid {
  constructor(container, options = {}) {
    this.container = container;
    this.startHour = options.startHour || 8;
    this.endHour = options.endHour || 22;
    this.slotMinutes = options.slotMinutes || 60;
    this.mode = options.mode || 'available';
    this.readonly = options.readonly || false;

    // Internal state: cells[day][hourIndex] = 'available' | 'preferred' | null
    this.totalSlots = Math.floor((this.endHour - this.startHour) * 60 / this.slotMinutes);
    this.cells = {};
    for (let d = 0; d < 7; d++) {
      this.cells[d] = {};
      for (let s = 0; s < this.totalSlots; s++) {
        this.cells[d][s] = null;
      }
    }

    this._isDragging = false;
    this._dragMode = null; // 'select' or 'deselect'

    this._render();
    if (!this.readonly) this._bindEvents();
  }

  _dayNames() {
    return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  }

  _slotTime(index) {
    const totalMin = this.startHour * 60 + index * this.slotMinutes;
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
  }

  _render() {
    const days = this._dayNames();
    const style = document.createElement('style');
    style.textContent = `
      .tg-wrapper{overflow-x:auto}
      .tg-table{border-collapse:collapse;width:100%;min-width:480px;user-select:none}
      .tg-table th{padding:8px 4px;font-size:.78rem;font-weight:700;color:#6b7280;text-align:center;background:#f8fafc;border:1px solid #e5e7eb}
      .tg-table td{padding:0;border:1px solid #e5e7eb;text-align:center}
      .tg-time-label{padding:6px 8px!important;font-size:.78rem;font-weight:600;color:#6b7280;background:#f8fafc;white-space:nowrap;min-width:52px}
      .tg-cell{width:100%;height:36px;cursor:pointer;transition:background .1s;position:relative}
      .tg-cell:hover{opacity:.85}
      .tg-cell[data-state="available"]{background:#bae6fd}
      .tg-cell[data-state="preferred"]{background:#bbf7d0}
      .tg-cell.tg-readonly{cursor:default}
    `;
    this.container.innerHTML = '';
    this.container.appendChild(style);

    const wrapper = document.createElement('div');
    wrapper.className = 'tg-wrapper';

    const table = document.createElement('table');
    table.className = 'tg-table';

    // Header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    const cornerTh = document.createElement('th');
    cornerTh.textContent = '时间';
    headerRow.appendChild(cornerTh);
    days.forEach(name => {
      const th = document.createElement('th');
      th.textContent = name;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body
    const tbody = document.createElement('tbody');
    for (let s = 0; s < this.totalSlots; s++) {
      const tr = document.createElement('tr');
      const timeTd = document.createElement('td');
      timeTd.className = 'tg-time-label';
      timeTd.textContent = this._slotTime(s);
      tr.appendChild(timeTd);

      for (let d = 0; d < 7; d++) {
        const td = document.createElement('td');
        const cell = document.createElement('div');
        cell.className = 'tg-cell' + (this.readonly ? ' tg-readonly' : '');
        cell.dataset.day = d;
        cell.dataset.slot = s;
        cell.dataset.state = '';
        td.appendChild(cell);
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    wrapper.appendChild(table);
    this.container.appendChild(wrapper);

    this._table = table;
  }

  _getCell(day, slot) {
    return this._table.querySelector(`.tg-cell[data-day="${day}"][data-slot="${slot}"]`);
  }

  _updateCellVisual(day, slot) {
    const cell = this._getCell(day, slot);
    if (!cell) return;
    const state = this.cells[day][slot];
    cell.dataset.state = state || '';
  }

  _toggleCell(day, slot) {
    if (this.readonly) return;
    const current = this.cells[day][slot];
    if (this._dragMode === 'select') {
      this.cells[day][slot] = this.mode;
    } else if (this._dragMode === 'deselect') {
      this.cells[day][slot] = null;
    } else {
      // single click toggle
      if (current === this.mode) {
        this.cells[day][slot] = null;
      } else {
        this.cells[day][slot] = this.mode;
      }
    }
    this._updateCellVisual(day, slot);
  }

  _bindEvents() {
    const self = this;

    // Prevent text selection while dragging
    this._table.addEventListener('mousedown', function(e) {
      const cell = e.target.closest('.tg-cell');
      if (!cell || self.readonly) return;
      e.preventDefault();
      self._isDragging = true;
      const day = parseInt(cell.dataset.day);
      const slot = parseInt(cell.dataset.slot);
      const current = self.cells[day][slot];
      self._dragMode = (current === self.mode) ? 'deselect' : 'select';
      self._toggleCell(day, slot);
    });

    this._table.addEventListener('mouseover', function(e) {
      if (!self._isDragging) return;
      const cell = e.target.closest('.tg-cell');
      if (!cell || self.readonly) return;
      const day = parseInt(cell.dataset.day);
      const slot = parseInt(cell.dataset.slot);
      self._toggleCell(day, slot);
    });

    document.addEventListener('mouseup', function() {
      self._isDragging = false;
      self._dragMode = null;
    });

    // Touch support
    this._table.addEventListener('touchstart', function(e) {
      const cell = e.target.closest('.tg-cell');
      if (!cell || self.readonly) return;
      e.preventDefault();
      self._isDragging = true;
      const day = parseInt(cell.dataset.day);
      const slot = parseInt(cell.dataset.slot);
      const current = self.cells[day][slot];
      self._dragMode = (current === self.mode) ? 'deselect' : 'select';
      self._toggleCell(day, slot);
    }, { passive: false });

    this._table.addEventListener('touchmove', function(e) {
      if (!self._isDragging) return;
      const touch = e.touches[0];
      const el = document.elementFromPoint(touch.clientX, touch.clientY);
      if (!el) return;
      const cell = el.closest('.tg-cell');
      if (!cell || self.readonly) return;
      e.preventDefault();
      const day = parseInt(cell.dataset.day);
      const slot = parseInt(cell.dataset.slot);
      self._toggleCell(day, slot);
    }, { passive: false });

    this._table.addEventListener('touchend', function() {
      self._isDragging = false;
      self._dragMode = null;
    });
  }

  /**
   * Get selected slots, merged into ranges per day
   * @param {string} filterMode - optional, 'available' or 'preferred'. If omitted, returns all.
   * @returns {Array} [{day: 0, start: "14:00", end: "16:00", mode: "available"}, ...]
   */
  getSlots(filterMode) {
    const result = [];
    for (let d = 0; d < 7; d++) {
      let rangeStart = null;
      let rangeMode = null;
      for (let s = 0; s <= this.totalSlots; s++) {
        const state = s < this.totalSlots ? this.cells[d][s] : null;
        const matches = filterMode ? (state === filterMode) : (state !== null);
        if (matches && state === rangeMode) {
          // continue range
        } else {
          // close previous range
          if (rangeStart !== null) {
            result.push({
              day: d,
              start: this._slotTime(rangeStart),
              end: this._slotTime(s),
              mode: rangeMode
            });
          }
          if (matches) {
            rangeStart = s;
            rangeMode = state;
          } else {
            rangeStart = null;
            rangeMode = null;
          }
        }
      }
    }
    return result;
  }

  /**
   * Set slots on the grid
   * @param {Array} slots - [{day, start, end, mode?}, ...]
   * @param {string} mode - override mode for all slots (optional)
   */
  setSlots(slots, mode) {
    if (!Array.isArray(slots)) return;
    slots.forEach(slot => {
      const d = slot.day;
      if (d < 0 || d > 6) return;
      const slotMode = mode || slot.mode || 'available';
      const startIdx = this._timeToSlotIndex(slot.start);
      const endIdx = this._timeToSlotIndex(slot.end);
      if (startIdx === null || endIdx === null) return;
      for (let s = startIdx; s < endIdx && s < this.totalSlots; s++) {
        this.cells[d][s] = slotMode;
        this._updateCellVisual(d, s);
      }
    });
  }

  _timeToSlotIndex(timeStr) {
    if (!timeStr) return null;
    const parts = timeStr.split(':');
    if (parts.length < 2) return null;
    const h = parseInt(parts[0]);
    const m = parseInt(parts[1]);
    const totalMin = h * 60 + m;
    const startMin = this.startHour * 60;
    const idx = Math.floor((totalMin - startMin) / this.slotMinutes);
    if (idx < 0) return 0;
    if (idx >= this.totalSlots) return this.totalSlots;
    return idx;
  }

  clear() {
    for (let d = 0; d < 7; d++) {
      for (let s = 0; s < this.totalSlots; s++) {
        this.cells[d][s] = null;
        this._updateCellVisual(d, s);
      }
    }
  }

  setMode(mode) {
    this.mode = mode;
  }
}
