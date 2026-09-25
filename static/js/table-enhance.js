/*!
 * table-enhance.js — progressive enhancement for server-rendered Jinja tables
 * ---------------------------------------------------------------------------
 * Zero dependencies. Opt-in via <table data-enhance>.
 *
 * Provides:
 *   1. Pagination         (25 / 50 / 100 / Semua, default 25, persisted)
 *   2. Column visibility  (checkbox dropdown — tables here have 18-22 columns)
 *   3. Compact density    (always on — no toggle)
 *   4. Frozen columns     (measures col #1 and publishes --frozen-1)
 *
 * Integration contract with existing page code:
 *   - filterTable() must mark each row with data-filter-pass="1|0".
 *     The enhancement then paginates ONLY rows that passed the filter.
 *   - After a DOM reorder (sorting), call resetPage() then refresh().
 *   - Row-number cells are repainted on every page render so the "#" column
 *     stays sequential across pages.
 */

(function () {
  'use strict';

  var STORE = 'tbl-enhance:';
  var DEFAULTS = { pageSize: 25 };

  /* ---------- tiny helpers ---------- */

  function readStore(key, fallback) {
    try {
      var v = localStorage.getItem(STORE + key);
      return v === null ? fallback : v;
    } catch (e) {
      return fallback;
    }
  }

  function writeStore(key, val) {
    try {
      localStorage.setItem(STORE + key, val);
    } catch (e) {
      /* private mode / quota — enhancement still works, just not persisted */
    }
  }

  /** Visible rows are those the host page's filter did not hide. */
  function passingRows(body) {
    return Array.prototype.filter.call(body.querySelectorAll('tr'), function (tr) {
      return tr.dataset.filterPass !== '0';
    });
  }

  /** Header label without the sort glyph baked into the markup. */
  function headerLabel(th) {
    var clone = th.cloneNode(true);
    var arrow = clone.querySelector('.sort-arrow');
    if (arrow) arrow.remove();
    return (clone.textContent || '').replace(/\s+/g, ' ').trim() || 'Kolom';
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* ---------- overlay panel (escapes overflow/sticky ancestors) ---------- */

  function Panel(anchor) {
    var self = this;
    this.node = el('div', 'te-panel');
    this.node.setAttribute('role', 'dialog');
    this.open = false;

    document.body.appendChild(this.node);

    this._docClick = function (e) {
      if (self.open && !self.node.contains(e.target) && !anchor.contains(e.target)) {
        self.hide();
      }
    };
    this._reposition = function () {
      if (self.open) self.show();
      else self.hide();
    };

    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      self.toggle();
    });
    anchor.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') self.hide();
    });
    document.addEventListener('click', this._docClick);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && self.open) {
        self.hide();
        anchor.focus();
      }
    });
    window.addEventListener('resize', this._reposition);
    window.addEventListener('scroll', this._reposition, true);
  }

  Panel.prototype.showAt = function (anchorRect) {
    this._anchorRect = anchorRect;
    var p = this.node;
    p.style.visibility = 'hidden';
    p.style.display = 'block';
    p.classList.add('is-open');

    var h = p.offsetHeight;
    var w = p.offsetWidth;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var gap = 6;

    var left = anchorRect.left;
    if (left + w > vw - 8) left = Math.max(8, vw - w - 8);

    var below = vh - anchorRect.bottom;
    var top =
      below < h + gap && anchorRect.top > below
        ? Math.max(8, anchorRect.top - h - gap)
        : anchorRect.bottom + gap;

    p.style.left = left + 'px';
    p.style.top = top + 'px';
    p.style.visibility = 'visible';
    this.open = true;
  };

  Panel.prototype.toggle = function () {
    if (this.open) this.hide();
    else this.show();
  };

  Panel.prototype.show = function () {
    var r = this._anchor && this._anchor.getBoundingClientRect();
    if (r) this.showAt(r);
  };

  Panel.prototype.hide = function () {
    this.node.classList.remove('is-open');
    this.node.style.display = 'none';
    this.open = false;
  };

  function makePanel(anchor) {
    var p = new Panel(anchor);
    p._anchor = anchor;
    p.node.style.display = 'none';
    return p;
  }

  /* ---------- per-table enhancement ---------- */

  function enhance(table) {
    var id = table.id || table.getAttribute('data-enhance') || 'tbl' + Math.random().toString(36).slice(2, 8);
    var body = table.tBodies[0];
    if (!body) return;

    var head = table.tHead;
    var headers = head ? Array.prototype.slice.call(head.rows[head.rows.length - 1].cells) : [];
    var scroll = table.closest('.table-scroll') || table.parentElement;
    var host = scroll && scroll.parentElement ? scroll.parentElement : table.parentElement;
    var _isLaporan = !!table.closest('.lp-body');

    /* ---- persisted state ---- */
    var pageSize = parseInt(readStore(id + ':pageSize', DEFAULTS.pageSize), 10) || DEFAULTS.pageSize;

    var hidden = {};
    if (!_isLaporan) (readStore(id + ':hidden', '') || '').split(',').forEach(function (i) {
      if (i !== '') hidden[parseInt(i, 10)] = true;
    });

    var page = 1;

    /* ---- toolbar ---- */
    var bar = el('div', 'te-toolbar');
    bar.setAttribute('role', 'toolbar');
    bar.setAttribute('aria-label', 'Kontrol tabel');

    /* column toggle — disabled on laporan pages (.lp-body) */
    if (headers.length && !_isLaporan) {
      var colBtn = el('button', 'te-btn');
      colBtn.type = 'button';
      colBtn.setAttribute('aria-haspopup', 'true');
      colBtn.setAttribute('aria-expanded', 'false');
      colBtn.innerHTML = '<i class="bi bi-columns-gap"></i> Kolom';

      var colPanel = makePanel(colBtn);
      var colHead = el('div', 'te-panel-head');
      colHead.appendChild(el('span', null, 'Tampilkan kolom'));
      var resetCols = el('button', 'te-link', 'Reset');
      resetCols.type = 'button';
      colHead.appendChild(resetCols);
      colPanel.node.appendChild(colHead);

      var colList = el('div', 'te-panel-list');
      headers.forEach(function (th, i) {
        var label = headerLabel(th);
        var row = el('label', 'te-check');
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !hidden[i];
        cb.disabled = th.classList.contains('te-col-locked');
        cb.addEventListener('change', function () {
          if (cb.checked) delete hidden[i];
          else hidden[i] = true;
          writeStore(id + ':hidden', Object.keys(hidden).join(','));
          applyColumns();
        });
        row.appendChild(cb);
        row.appendChild(el('span', null, label));
        colList.appendChild(row);
      });
      colPanel.node.appendChild(colList);

      resetCols.addEventListener('click', function () {
        hidden = {};
        writeStore(id + ':hidden', '');
        colList.querySelectorAll('input').forEach(function (cb) {
          cb.checked = true;
        });
        applyColumns();
      });

      bar.appendChild(colBtn);
      colBtn.addEventListener('click', function () {
        colBtn.setAttribute('aria-expanded', colPanel.open ? 'false' : 'true');
      });
    }

    var info = el('div', 'te-info');
    if (_isLaporan) {
      info.classList.add('te-info--hdr');
      var _hdr = host ? host.querySelector('.lp-tbl-hdr') : null;
      if (_hdr) {
        var _hint = _hdr.querySelector('.lp-hint');
        if (_hint) _hint.remove();
        _hdr.appendChild(info);
      } else {
        bar.appendChild(info);
      }
    } else {
      var spacer = el('div', 'te-spacer');
      bar.appendChild(spacer);
      bar.appendChild(info);
    }

    /* ---- pagination bar ---- */
    var pager = el('div', 'te-pager');
    var sizeSel = el('select', 'te-select');
    sizeSel.setAttribute('aria-label', 'Baris per halaman');
    // Report tables are short (laporan_mingguan averages ~20 rows/week table),
    // so 10 and 15 are offered to make pagination useful there too.
    [10, 15, 25, 50, 100, 0].forEach(function (n) {
      var o = document.createElement('option');
      o.value = String(n);
      o.textContent = n === 0 ? 'Semua' : n + ' / hal';
      sizeSel.appendChild(o);
    });
    sizeSel.value = String(pageSize);
    sizeSel.addEventListener('change', function () {
      pageSize = parseInt(sizeSel.value, 10);
      writeStore(id + ':pageSize', String(pageSize));
      page = 1;
      render();
    });
    pager.appendChild(sizeSel);

    var prevBtn = el('button', 'te-page-btn');
    prevBtn.type = 'button';
    prevBtn.innerHTML = '<i class="bi bi-chevron-left"></i>';
    prevBtn.setAttribute('aria-label', 'Halaman sebelumnya');
    prevBtn.addEventListener('click', function () {
      if (page > 1) {
        page--;
        render();
      }
    });
    pager.appendChild(prevBtn);

    var pagerNums = el('div', 'te-page-nums');
    pager.appendChild(pagerNums);

    var nextBtn = el('button', 'te-page-btn');
    nextBtn.type = 'button';
    nextBtn.innerHTML = '<i class="bi bi-chevron-right"></i>';
    nextBtn.setAttribute('aria-label', 'Halaman berikutnya');
    nextBtn.addEventListener('click', function () {
      if (page < pageCount()) {
        page++;
        render();
      }
    });
    pager.appendChild(nextBtn);

    /* ---- mount ---- */
    if (host) {
      if (_isLaporan) {
        bar.style.display = 'none';
      } else {
        host.insertBefore(bar, scroll);
      }
      if (scroll.nextSibling) host.insertBefore(pager, scroll.nextSibling);
      else host.appendChild(pager);
    }

    /* ---- behaviour ---- */

    var cellCache = null;
    function cells() {
      if (cellCache) return cellCache;
      cellCache = [];
      var headRow = head ? head.rows[head.rows.length - 1] : null;
      for (var i = 0; i < headers.length; i++) {
        var col = { head: headRow ? headRow.cells[i] : null, body: [] };
        Array.prototype.forEach.call(body.rows, function (tr) {
          col.body.push(tr.cells[i] || null);
        });
        cellCache.push(col);
      }
      return cellCache;
    }

    function applyColumns() {
      cells().forEach(function (col, i) {
        var d = hidden[i] ? 'none' : '';
        if (col.head) col.head.style.display = d;
        col.body.forEach(function (td) {
          if (td) td.style.display = d;
        });
      });
      measureFrozen();
    }

    /* Density is fixed: every table renders compact. The toggle was removed —
       financial tables are scanned, and compact was the preferred setting. */
    function applyDensity() {
      table.classList.add('te-compact');
      table.style.setProperty('--te-pad-y', '4px');
      table.style.setProperty('--te-pad-x', '7px');
      measureFrozen();
    }

    function pageCount() {
      if (!pageSize) return 1;
      return Math.max(1, Math.ceil(passingRows(body).length / pageSize));
    }

    function render() {
      var rows = passingRows(body);
      var total = rows.length;
      var pages = pageSize ? Math.max(1, Math.ceil(total / pageSize)) : 1;
      if (page > pages) page = pages;

      var start = pageSize ? (page - 1) * pageSize : 0;
      var end = pageSize ? start + pageSize : total;

      // Hide everything first, then reveal the active window.
      Array.prototype.forEach.call(body.rows, function (tr) {
        tr.style.display = 'none';
      });

      var shown = 0;
      rows.forEach(function (tr, idx) {
        if (idx < start || idx >= end) return;
        tr.style.display = '';
        tr.dataset.teIndex = String(idx + 1);
        // Renumber sequentially over the filtered set so "#" reads 1..n per page,
        // and keep the raw sort value in sync with what is displayed.
        var numSpan = tr.querySelector('.row-num');
        if (numSpan) {
          numSpan.textContent = String(idx + 1);
          var numCell = numSpan.closest('td');
          if (numCell && numCell.dataset.type === 'num') numCell.dataset.v = String(idx + 1);
        }
        shown++;
      });

      // info
      if (!total) info.textContent = 'Tidak ada data';
      else if (!pageSize) info.textContent = total + ' baris';
      else
        info.textContent =
          total === 0
            ? 'Tidak ada data'
            : 'Menampilkan ' + (start + 1) + '–' + Math.min(end, total) + ' dari ' + total;

      // pager
      // Pager is ALWAYS visible so every table looks the same, even when all
      // rows fit on one page. (Hiding it made laporan_mingguan look broken —
      // its 45 per-week tables average ~20 rows, so the pager never appeared.)
      pager.style.display = '';
      if (pageSize && total > pageSize) buildPageNums(pages);
      else pagerNums.innerHTML = '';

      // Keep the controls rendered (uniform look) but visibly inert at bounds.
      prevBtn.disabled = page <= 1;
      nextBtn.disabled = pages <= 1 || page >= pages;
      prevBtn.classList.toggle('is-disabled', page <= 1);
      nextBtn.classList.toggle('is-disabled', pages <= 1 || page >= pages);

      measureFrozen();
    }

    function buildPageNums(pages) {
      pagerNums.innerHTML = '';
      var list = [];
      if (pages <= 7) {
        for (var i = 1; i <= pages; i++) list.push(i);
      } else {
        list.push(1);
        if (page > 3) list.push('…');
        for (var j = Math.max(2, page - 1); j <= Math.min(pages - 1, page + 1); j++) list.push(j);
        if (page < pages - 2) list.push('…');
        list.push(pages);
      }
      list.forEach(function (p) {
        if (p === '…') {
          pagerNums.appendChild(el('span', 'te-gap', '…'));
          return;
        }
        var b = el('button', 'te-page-num' + (p === page ? ' is-current' : ''));
        b.type = 'button';
        b.textContent = String(p);
        if (p === page) b.setAttribute('aria-current', 'page');
        b.addEventListener('click', function () {
          page = p;
          render();
        });
        pagerNums.appendChild(b);
      });
    }

    /* ---- frozen column offset (replaces hard-coded left: 40px) ---- */
    function measureFrozen() {
      if (!head) return;
      var lastRow = head.rows[head.rows.length - 1];
      if (!lastRow || !lastRow.cells.length) return;
      var first = lastRow.cells[0];
      var w = first.getBoundingClientRect().width;
      // jsdom (and display:none ancestors) report 0 — fall back to the inline
      // width the template declares, then to the previous value, then 40px.
      if (!w) w = parseFloat(first.style.width) || 0;
      if (!w) w = parseFloat(table.style.getPropertyValue('--frozen-1')) || 40;
      table.style.setProperty('--frozen-1', Math.round(w) + 'px');
    }

    /* ---- init ---- */
    applyColumns();
    applyDensity();
    render();

    api.instances[id] = { render: render, table: table, resetPage: function () { page = 1; } };
  }

  /* ---------- public API ---------- */

  var api = {
    instances: {},
    refresh: function (id) {
      var keys = id ? [id] : Object.keys(api.instances);
      keys.forEach(function (k) {
        var inst = api.instances[k];
        if (inst && inst.table && inst.table.isConnected) inst.render();
      });
    },
    resetPage: function (id) {
      var keys = id ? [id] : Object.keys(api.instances);
      keys.forEach(function (k) {
        var inst = api.instances[k];
        if (inst) inst.resetPage();
      });
    },
    enhanceAll: function (root) {
      (root || document).querySelectorAll('table[data-enhance]').forEach(function (t, i) {
        if (t.dataset.teReady) return;
        t.dataset.teReady = '1';
        // laporan_mingguan renders one table per week section, all sharing the
        // same data-enhance value. Suffix so each gets its own persisted state
        // instead of 45 tables fighting over one localStorage key.
        var key = t.getAttribute('data-enhance') || '';
        if (key) t.setAttribute('data-enhance', key + '-' + i);
        enhance(t);
      });
    }
  };

  window.TableEnhance = api;

  function boot() {
    api.enhanceAll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
