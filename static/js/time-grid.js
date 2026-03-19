/**
 * TimeGrid - Reusable weekly time selection grid component.
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
    this.mode = options.mode || "available";
    this.readonly = options.readonly || false;

    this.totalSlots = Math.floor(
      ((this.endHour - this.startHour) * 60) / this.slotMinutes
    );
    this.cells = {};
    for (let day = 0; day < 7; day++) {
      this.cells[day] = {};
      for (let slot = 0; slot < this.totalSlots; slot++) {
        this.cells[day][slot] = null;
      }
    }

    this._isPainting = false;
    this._paintValue = null;
    this._lastPaintedKey = null;
    this._activePointerId = null;
    this._supportsPointer = typeof window !== "undefined" && "PointerEvent" in window;

    this._render();
    if (!this.readonly) {
      this._bindEvents();
    }
  }

  _dayNames() {
    return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  }

  _slotTime(index) {
    const totalMinutes = this.startHour * 60 + index * this.slotMinutes;
    const hour = Math.floor(totalMinutes / 60);
    const minute = totalMinutes % 60;
    return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
  }

  _render() {
    const days = this._dayNames();
    const style = document.createElement("style");
    style.textContent = `
      .tg-wrapper{overflow-x:auto}
      .tg-table{border-collapse:collapse;width:100%;min-width:480px;user-select:none;touch-action:none}
      .tg-table th{padding:8px 4px;font-size:.78rem;font-weight:700;color:#6b7280;text-align:center;background:#f8fafc;border:1px solid #e5e7eb}
      .tg-table td{padding:0;border:1px solid #e5e7eb;text-align:center}
      .tg-time-label{padding:6px 8px!important;font-size:.78rem;font-weight:600;color:#6b7280;background:#f8fafc;white-space:nowrap;min-width:52px}
      .tg-cell{width:100%;height:36px;cursor:pointer;transition:background .1s;position:relative}
      .tg-cell:hover{opacity:.88}
      .tg-cell[data-state="available"]{background:#bae6fd}
      .tg-cell[data-state="preferred"]{background:#bbf7d0}
      .tg-cell.tg-readonly{cursor:default}
    `;
    this.container.innerHTML = "";
    this.container.appendChild(style);

    const wrapper = document.createElement("div");
    wrapper.className = "tg-wrapper";

    const table = document.createElement("table");
    table.className = "tg-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const cornerTh = document.createElement("th");
    cornerTh.textContent = "时间";
    headerRow.appendChild(cornerTh);
    days.forEach((name) => {
      const th = document.createElement("th");
      th.textContent = name;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    for (let slot = 0; slot < this.totalSlots; slot++) {
      const tr = document.createElement("tr");
      const timeTd = document.createElement("td");
      timeTd.className = "tg-time-label";
      timeTd.textContent = this._slotTime(slot);
      tr.appendChild(timeTd);

      for (let day = 0; day < 7; day++) {
        const td = document.createElement("td");
        const cell = document.createElement("div");
        cell.className = "tg-cell" + (this.readonly ? " tg-readonly" : "");
        cell.dataset.day = day;
        cell.dataset.slot = slot;
        cell.dataset.state = "";
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
    cell.dataset.state = state || "";
  }

  _setCellState(day, slot, nextValue) {
    this.cells[day][slot] = nextValue;
    this._updateCellVisual(day, slot);
  }

  _startPaint(cell, pointerId = null) {
    if (!cell || this.readonly) return;
    const day = Number(cell.dataset.day);
    const slot = Number(cell.dataset.slot);
    const current = this.cells[day][slot];

    this._isPainting = true;
    this._paintValue = current === this.mode ? null : this.mode;
    this._lastPaintedKey = null;
    this._activePointerId = pointerId;
    this._paintCell(cell);
  }

  _paintCell(cell) {
    if (!cell || this.readonly || !this._isPainting) return;
    const day = Number(cell.dataset.day);
    const slot = Number(cell.dataset.slot);
    const key = `${day}:${slot}`;
    if (this._lastPaintedKey === key) return;
    this._lastPaintedKey = key;
    this._setCellState(day, slot, this._paintValue);
  }

  _stopPaint(pointerId = null) {
    if (pointerId !== null && this._activePointerId !== null && pointerId !== this._activePointerId) {
      return;
    }
    this._isPainting = false;
    this._paintValue = null;
    this._lastPaintedKey = null;
    this._activePointerId = null;
  }

  _bindPointerEvents() {
    this._table.addEventListener("pointerdown", (event) => {
      const cell = event.target.closest(".tg-cell");
      if (!cell) return;
      event.preventDefault();
      this._startPaint(cell, event.pointerId);
      if (this._table.setPointerCapture) {
        try {
          this._table.setPointerCapture(event.pointerId);
        } catch (err) {
          // Ignore browsers that reject capture on table elements.
        }
      }
    });

    this._table.addEventListener("pointerover", (event) => {
      if (!this._isPainting) return;
      const cell = event.target.closest(".tg-cell");
      if (!cell) return;
      this._paintCell(cell);
    });

    this._table.addEventListener("pointerup", (event) => {
      this._stopPaint(event.pointerId);
    });

    this._table.addEventListener("pointercancel", (event) => {
      this._stopPaint(event.pointerId);
    });

    document.addEventListener("pointerup", (event) => {
      this._stopPaint(event.pointerId);
    });
  }

  _bindLegacyEvents() {
    this._table.addEventListener("mousedown", (event) => {
      const cell = event.target.closest(".tg-cell");
      if (!cell) return;
      event.preventDefault();
      this._startPaint(cell);
    });

    this._table.addEventListener("mouseover", (event) => {
      if (!this._isPainting) return;
      const cell = event.target.closest(".tg-cell");
      if (!cell) return;
      this._paintCell(cell);
    });

    document.addEventListener("mouseup", () => {
      this._stopPaint();
    });

    this._table.addEventListener(
      "touchstart",
      (event) => {
        const touch = event.touches[0];
        if (!touch) return;
        const element = document.elementFromPoint(touch.clientX, touch.clientY);
        const cell = element && element.closest(".tg-cell");
        if (!cell) return;
        event.preventDefault();
        this._startPaint(cell);
      },
      { passive: false }
    );

    this._table.addEventListener(
      "touchmove",
      (event) => {
        if (!this._isPainting) return;
        const touch = event.touches[0];
        if (!touch) return;
        const element = document.elementFromPoint(touch.clientX, touch.clientY);
        const cell = element && element.closest(".tg-cell");
        if (!cell) return;
        event.preventDefault();
        this._paintCell(cell);
      },
      { passive: false }
    );

    this._table.addEventListener("touchend", () => {
      this._stopPaint();
    });
  }

  _bindEvents() {
    if (this._supportsPointer) {
      this._bindPointerEvents();
      return;
    }
    this._bindLegacyEvents();
  }

  /**
   * Get selected slots, merged into ranges per day.
   * @param {string} filterMode - optional, 'available' or 'preferred'. If omitted, returns all.
   * @returns {Array} [{day: 0, start: "14:00", end: "16:00", mode: "available"}, ...]
   */
  getSlots(filterMode) {
    const result = [];
    for (let day = 0; day < 7; day++) {
      let rangeStart = null;
      let rangeMode = null;
      for (let slot = 0; slot <= this.totalSlots; slot++) {
        const state = slot < this.totalSlots ? this.cells[day][slot] : null;
        const matches = filterMode ? state === filterMode : state !== null;
        if (matches && state === rangeMode) {
          continue;
        }

        if (rangeStart !== null) {
          result.push({
            day: day,
            start: this._slotTime(rangeStart),
            end: this._slotTime(slot),
            mode: rangeMode,
          });
        }

        if (matches) {
          rangeStart = slot;
          rangeMode = state;
        } else {
          rangeStart = null;
          rangeMode = null;
        }
      }
    }
    return result;
  }

  /**
   * Set slots on the grid.
   * @param {Array} slots - [{day, start, end, mode?}, ...]
   * @param {string} mode - override mode for all slots (optional)
   */
  setSlots(slots, mode) {
    if (!Array.isArray(slots)) return;
    slots.forEach((slot) => {
      const day = slot.day;
      if (day < 0 || day > 6) return;
      const slotMode = mode || slot.mode || "available";
      const startIdx = this._timeToSlotIndex(slot.start);
      const endIdx = this._timeToSlotIndex(slot.end);
      if (startIdx === null || endIdx === null) return;
      for (let index = startIdx; index < endIdx && index < this.totalSlots; index++) {
        this._setCellState(day, index, slotMode);
      }
    });
  }

  _timeToSlotIndex(timeStr) {
    if (!timeStr) return null;
    const parts = timeStr.split(":");
    if (parts.length < 2) return null;
    const hour = Number(parts[0]);
    const minute = Number(parts[1]);
    const totalMinutes = hour * 60 + minute;
    const startMinutes = this.startHour * 60;
    const index = Math.floor((totalMinutes - startMinutes) / this.slotMinutes);
    if (index < 0) return 0;
    if (index >= this.totalSlots) return this.totalSlots;
    return index;
  }

  clear() {
    for (let day = 0; day < 7; day++) {
      for (let slot = 0; slot < this.totalSlots; slot++) {
        this._setCellState(day, slot, null);
      }
    }
  }

  setMode(mode) {
    this.mode = mode;
  }
}
