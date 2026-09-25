/* ============================================================
   TOAST - notifikasi non-blocking (pengganti alert())
   ============================================================
   Dipakai global. API:
     Toast.ok('Berhasil disimpan')
     Toast.err('Gagal memuat data')
     Toast.warn('Perhatian')
     Toast.info('Info')
     Toast.show('pesan', 'ok' | 'err' | 'warn' | 'info', durasiMs)

   Perilaku:
   - Auto-dismiss (default 8 detik; error 10 detik).
   - Klik tombol x untuk menutup cepat.
   - Kumpulkan maksimal 4 toast, sisanya yang tertua dibuang.
   - Aman dipanggil sebelum DOM siap (menunggu DOMContentLoaded).
   - Wajib ada .ds-toast-host; dibuat otomatis bila belum ada.
   ============================================================ */
(function () {
  'use strict';

  var ICON = { ok: 'bi-check-circle-fill', err: 'bi-x-circle-fill',
               warn: 'bi-exclamation-triangle-fill', info: 'bi-info-circle-fill' };
  var MAX = 4;

  function host() {
    var h = document.querySelector('.ds-toast-host');
    if (!h) {
      h = document.createElement('div');
      h.className = 'ds-toast-host';
      h.setAttribute('role', 'status');
      h.setAttribute('aria-live', 'polite');
      document.body.appendChild(h);
    }
    return h;
  }

  function show(msg, kind, ms) {
    kind = kind || 'info';
    if (ms == null) ms = kind === 'err' ? 10000 : 8000;

    var h = host();
    while (h.children.length >= MAX) h.removeChild(h.firstChild);

    var t = document.createElement('div');
    t.className = 'ds-toast ds-toast--' + kind;
    t.setAttribute('role', kind === 'err' ? 'alert' : 'status');

    var i = document.createElement('i');
    i.className = 'bi ' + (ICON[kind] || ICON.info);
    i.setAttribute('aria-hidden', 'true');

    var m = document.createElement('div');
    m.className = 'ds-toast__msg';
    m.textContent = String(msg == null ? '' : msg);

    var x = document.createElement('button');
    x.type = 'button';
    x.className = 'ds-toast__close';
    x.setAttribute('aria-label', 'Tutup notifikasi');
    x.innerHTML = '&times;';

    t.appendChild(i);
    t.appendChild(m);
    t.appendChild(x);
    h.appendChild(t);

    var timer = setTimeout(close, ms);

    function close() {
      clearTimeout(timer);
      if (!t.parentNode) return;
      t.classList.add('is-out');
      setTimeout(function () {
        if (t.parentNode) t.parentNode.removeChild(t);
      }, 180);
    }

    x.addEventListener('click', close);
    return close;
  }

  // ── Terjemahkan banner flash Flask menjadi toast ──
  // base.html tetap merender .alert untuk kompatibilitas, lalu skrip ini
  // mengubahnya jadi toast supaya tidak memakan ruang di konten.
  function absorbFlash() {
    var nodes = document.querySelectorAll(
      '.content-area > .alert, [data-flash] .alert'
    );
    Array.prototype.forEach.call(nodes, function (a) {
      var cls = a.className || '';
      var kind = 'info';
      if (/alert-danger/.test(cls)) kind = 'err';
      else if (/alert-success/.test(cls)) kind = 'ok';
      else if (/alert-warning/.test(cls)) kind = 'warn';

      // ambil teks saja (buang ikon & tombol close)
      var body = a.querySelector('span, div');
      var txt = ((body || a).textContent || '').replace(/\s+/g, ' ').trim();
      if (!txt) txt = (a.textContent || '').replace(/\s+/g, ' ').trim();

      if (txt) show(txt, kind);
      if (a.parentNode) a.parentNode.removeChild(a);
    });
  }

  var API = {
    show: show,
    ok: function (m, ms) { return show(m, 'ok', ms); },
    err: function (m, ms) { return show(m, 'err', ms); },
    warn: function (m, ms) { return show(m, 'warn', ms); },
    info: function (m, ms) { return show(m, 'info', ms); },
    absorbFlash: absorbFlash
  };

  window.Toast = API;

  function boot() { try { absorbFlash(); } catch (e) { /* jangan sampai merusak halaman */ } }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
  // Flash ikut masuk lewat konten yang di-swap HTMX — serap juga setiap swap
  // (DOMContentLoaded tidak ter-trigger ulang pada navigasi AJAX).
  document.addEventListener('htmx:afterSwap', boot);
})();
