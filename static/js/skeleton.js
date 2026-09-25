/* ============================================================
   SKELETON - placeholder saat tabel/area memuat
   ============================================================
   Terpisah dari table-enhance.js supaya tidak mengganggu logika inti
   (pagination, sorting, frozen columns) yang sudah teruji.

   API:
     Skeleton.overlay(el, opts)  -> tampilkan skeleton di atas el
     Skeleton.clear(el)          -> hapus skeleton
     Skeleton.rows(n)            -> string HTML n baris skeleton

   Dipakai otomatis untuk:
   - tabel besar (>= 200 baris) saat render pertama
   - tombol export (sudah punya spinner sendiri)
   ============================================================ */
(function () {
  'use strict';

  function rows(n, widths) {
    widths = widths || [92, 78, 85, 64, 70];
    var out = '';
    for (var i = 0; i < n; i++) {
      var w = widths[i % widths.length];
      out += '<div class="ds-skel ds-skel-row" style="width:' + w + '%"></div>';
    }
    return out;
  }

  function overlay(el, opts) {
    if (!el) return null;
    opts = opts || {};
    // jangan tumpuk
    var old = el.querySelector(':scope > .ds-skel-overlay');
    if (old) old.parentNode.removeChild(old);

    el.classList.add('ds-skel-wrap');

    var ov = document.createElement('div');
    ov.className = 'ds-skel-overlay';
    ov.setAttribute('aria-hidden', 'true');
    ov.innerHTML = rows(opts.rows || 6);

    el.appendChild(ov);

    // visibilitas: bila el tidak punya tinggi, beri tinggi minimum
    if (el.clientHeight < 40) el.style.minHeight = '120px';

    return ov;
  }

  function clear(el) {
    if (!el) return;
    var ov = el.querySelector(':scope > .ds-skel-overlay');
    if (ov) ov.parentNode.removeChild(ov);
    el.classList.remove('ds-skel-wrap');
    if (el.style.minHeight === '120px') el.style.minHeight = '';
  }

  /* ── Auto: skeleton saat pemuatan awal tabel besar ──────────
     Tabel besar butuh waktu untuk di-enhance. Tampilkan skeleton
     sebentar lalu hapus setelah render selesai, supaya user tidak
     melihat halaman kosong berkedip. */
  function autoBoot() {
    var tables = document.querySelectorAll('table[data-enhance]');
    Array.prototype.forEach.call(tables, function (tbl) {
      var wrap = tbl.closest('.table-scroll') || tbl.parentNode;
      if (!wrap) return;
      var n = tbl.tBodies[0] ? tbl.tBodies[0].rows.length : 0;
      if (n < 200) return; // tabel kecil selesai instan - tak perlu skeleton

      var ov = overlay(wrap, { rows: 8 });
      // tunggu 2 frame supaya browser sempat menggambar skeleton,
      // lalu hapus (karena TableEnhance sudah merender sinkron).
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          if (ov && ov.parentNode) clear(wrap);
        });
      });
    });
  }

  window.Skeleton = {
    rows: rows,
    overlay: overlay,
    clear: clear,
    autoBoot: autoBoot
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoBoot);
  } else {
    autoBoot();
  }
})();
