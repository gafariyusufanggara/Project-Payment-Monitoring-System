/* cell-expand.js — reveal the full value of a truncated table cell on click.
 *
 * Report modals (laporan DPP / PPN / jatuh tempo) rebuild their <tbody> from
 * JS. Any <td data-full="…"> inside such a table becomes clickable and opens a
 * small floating box holding the FULL value, so nothing is lost to the
 * ellipsis and the table layout never shifts. This mirrors the behaviour the
 * No. Invoice column has always had, extended to PO / Kontrak and Deskripsi.
 *
 * A cell only gets the pointer affordance (`cx-on`) when it actually
 * overflows — either it was truncated in JS (text ends with …) or the rendered
 * text is wider than the cell (scrollWidth > clientWidth). Short values stay
 * inert. The box is position:fixed, so the modal's own scroll cannot drag it.
 */
(function () {
  'use strict';
  if (window.CellExpand) return;

  var pop = null;       // singleton floating box
  var openCell = null;  // the cell currently expanded

  function esc(s) {
    return String(s == null ? '-' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* Build a <td>. `cls` are the base classes; `n` is the soft truncation
     length used for display. The FULL text always goes into data-full. When we
     truncate, the cell is immediately marked clickable (`cx-on`); refresh()
     later re-checks by real pixel overflow too, covering values that are short
     in characters but still clipped by a narrow column. */
  function td(text, cls, n) {
    var full = String(text == null || text === '' ? '-' : text);
    var limit = n || 40;
    var cut = full.length > limit;
    var shown = cut ? full.slice(0, limit) + '…' : full;
    var klass = (cls || 'l') + (cut ? ' cx-on' : '');
    return '<td class="' + esc(klass) + '" data-full="' + esc(full) + '">' +
           esc(shown) + '</td>';
  }

  function overflowing(cell) {
    if (cell.scrollWidth > cell.clientWidth + 1) return true;
    return /…\s*$/.test(cell.textContent || '');
  }

  function refresh(root) {
    var cells = (root || document).querySelectorAll('td[data-full]');
    for (var i = 0; i < cells.length; i++) {
      var c = cells[i];
      if (overflowing(c)) {
        c.classList.add('cx-on');
        if (c.getAttribute('tabindex') === null) {
          c.setAttribute('tabindex', '0');
          c.setAttribute('role', 'button');
          c.setAttribute('aria-label', 'Lihat teks lengkap');
        }
      } else {
        c.classList.remove('cx-on');
      }
    }
  }

  function ensurePop() {
    if (!pop) {
      pop = document.createElement('div');
      pop.className = 'lp-cellpop';
      pop.setAttribute('role', 'tooltip');
      document.body.appendChild(pop);
    }
    return pop;
  }

  function place(cell) {
    var p = ensurePop();
    var r = cell.getBoundingClientRect();
    p.style.visibility = 'hidden';
    p.style.left = '0px';
    p.style.top = '0px';
    var pw = p.offsetWidth, ph = p.offsetHeight;
    var vw = window.innerWidth, vh = window.innerHeight;
    var left = r.left;
    if (left + pw > vw - 8) left = vw - pw - 8;
    if (left < 8) left = 8;
    var up = (r.bottom + ph + 10 > vh) && (r.top - ph - 10 > 0);
    var top = up ? (r.top - ph - 8) : (r.bottom + 8);
    p.style.left = Math.round(left) + 'px';
    p.style.top = Math.round(top) + 'px';
    p.classList.toggle('lp-cellpop--up', up);
    p.style.visibility = '';
  }

  function open(cell) {
    if (openCell === cell) { close(); return; }
    close();
    var full = cell.getAttribute('data-full');
    if (full == null) return;
    var p = ensurePop();
    p.textContent = full;
    cell.classList.add('is-open');
    openCell = cell;
    place(cell);
  }

  function close() {
    if (openCell) openCell.classList.remove('is-open');
    openCell = null;
    if (pop) { pop.remove(); pop = null; }
  }

  /* Capture phase: intercept the click before any row-level handler, and keep
     clicks inside the box (for text selection) from closing it. */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (t.closest('.lp-cellpop')) return;
    var cell = t.closest('td[data-full]');
    if (cell && cell.classList.contains('cx-on')) {
      e.preventDefault(); e.stopPropagation(); open(cell); return;
    }
    close();
  }, true);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { close(); return; }
    if ((e.key === 'Enter' || e.key === ' ') && e.target && e.target.closest) {
      var cell = e.target.closest('td[data-full]');
      if (cell && cell.classList.contains('cx-on')) { e.preventDefault(); open(cell); }
    }
  });

  /* The box is anchored to a viewport rect, so dismiss it whenever the layout
     underneath could move (scroll / resize) or the modal goes away. */
  window.addEventListener('resize', function () { close(); refresh(); }, true);
  window.addEventListener('scroll', close, true);
  document.addEventListener('show.bs.modal', close, true);
  document.addEventListener('hidden.bs.modal', close, true);
  /* Re-measure once the modal is actually laid out (clientWidth is 0 while
     hidden, so overflow can only be detected here). */
  document.addEventListener('shown.bs.modal', function () { refresh(document); }, true);

  function boot() {
    refresh(document);
    if (window.MutationObserver) {
      new MutationObserver(function () { refresh(document); })
        .observe(document.body, { childList: true, subtree: true });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.CellExpand = { td: td, refresh: refresh, open: open, close: close };
})();
