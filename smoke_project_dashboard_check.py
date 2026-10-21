# -*- coding: utf-8 -*-
"""Smoke check: Dashboard Proyek (project_dashboard.html).

Memverifikasi bahwa KPI dashboard proyek mengikuti pola dashboard utama
(partials/_dashboard.html):

- hero Total Sisa Hutang (Incld PPN) + bar progres DPP/PPN, dengan
  sisa_hutang == sisa_dpp + sisa_ppn;
- 9 KPI dalam 3 grup berurutan: DPP -> PPN -> Umum, tiap grup tepat 3 kartu;
- Nilai Kontrak TIDAK lagi di blok KPI (hanya di info strip, tepat 1x) supaya
  tidak disandingkan dgn realisasi (basisnya beda: 25 kontrak vendor);
- invarian per grup: Terbayar + Sisa Hutang == Total (toleransi Rp 1 di sel);
- persentase = round(bayar/total*100) dan sisa% + bayar% ~ 100;
- angka proyek konsisten dgn halaman daftar proyek
  (total_dpp == total_realisasi, sisa_dpp == total_sisa) — anti-drift;
- klip per-vendor: sisa tidak pernah negatif;
- kelas ds-kpi--warn (tidak terdefinisi di app.css) sudah tidak dipakai;
- tanggal info strip terformat (filter tgl), bukan YYYY-MM-DD mentah.

Run:  python smoke_project_dashboard_check.py
Read-only terhadap data nyata.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
import db_project
from services.auth import SESSION_KEY

app = appmod.app
app.config['TESTING'] = True

PROJECTS = db_project.get_projects()
assert PROJECTS, 'tidak ada proyek di database — smoke check tidak bermakna'

money_f = app.jinja_env.filters['money']
tgl_f = app.jinja_env.filters['tgl']


def _idr(text):
    """Nilai rupiah dari string berformat Indonesia."""
    return float(re.sub(r'[^0-9-]', '', text) or 0)


def render(pid):
    with app.test_client() as c:
        with c.session_transaction() as s:
            s[SESSION_KEY] = True
        r = c.get(f'/project/{pid}/dashboard')
        return r.status_code, r.get_data(as_text=True)


def body_of(html):
    """Badan template saja: tanpa <style> dan tanpa komentar HTML.

    Komentar (mis. blok THESIS/CATATAN KPI di kepala template) menyebut nama
    label, sehingga bila tidak dibuang ia akan dihitung sebagai markup hidup.
    """
    s = re.sub(r'<style>.*?</style>', '', html, flags=re.S)
    return re.sub(r'<!--.*?-->', '', s, flags=re.S)


# ── 1. Hero: Total Sisa Hutang + invarian sisa_hutang = sisa_dpp + sisa_ppn ──
for p in PROJECTS:
    status, html = render(p['id'])
    assert status == 200, f"{p['kode_proyek']}: GET dashboard -> {status}"
    k = db_project.get_project_finansial(p['id'])
    assert abs(k['sisa_hutang'] - k['sisa_dpp'] - k['sisa_ppn']) < 0.01, \
        f"{p['kode_proyek']}: sisa_hutang != sisa_dpp + sisa_ppn"
    body = body_of(html)
    assert 'prj-hero' in body, f"{p['kode_proyek']}: hero hilang"
    assert 'Total Sisa Hutang (Include PPN)' in body, 'label hero hilang'
    assert f"Rp {money_f(k['sisa_hutang'])}" in body, \
        f"{p['kode_proyek']}: nilai hero != {money_f(k['sisa_hutang'])}"
    assert 'role="progressbar"' in body, 'bar progres hero hilang'
print(f'[1] hero Total Sisa Hutang + bar progres OK ({len(PROJECTS)} proyek)')

# ── 1b. Kartu hero (progress DPP/PPN) SERAGAM dgn hero dashboard ──
# Dulu .prj-hero memakai background var(--ds-accent) (teal #0f766e) sehingga
# kartu berisi bar DPP/PPN di halaman proyek berwarna beda dgn .dash-hero
# di /dashboard yang navy #16324f. Disamakan ke navy + geometry yang sama.
_ROOT = os.path.dirname(os.path.abspath(__file__))
_pj_hero_css = io.open(os.path.join(_ROOT, 'static', 'css', 'project.css'),
                       encoding='utf-8').read()
_dash_tpl = io.open(os.path.join(_ROOT, 'templates', 'partials', '_dashboard.html'),
                    encoding='utf-8').read()


def _hero_block(css, sel):
    i = css.find(sel)
    if i < 0:
        return None
    o = css.index('{', i)
    return ' '.join(css[i:css.index('}', o) + 1].split())


_pj_hero = _hero_block(_pj_hero_css, '.prj-hero {')
_dash_hero = _hero_block(_dash_tpl, '.dash-hero {')
assert _pj_hero, 'hero proyek (.prj-hero) tidak ditemukan'
assert _dash_hero, 'hero dashboard (.dash-hero) tidak ditemukan'
assert 'linear-gradient(135deg, #16324f 0%, #16324f 100%)' in _pj_hero, \
    'hero proyek harus navy #16324f seperti .dash-hero (bukan teal --ds-accent)'
assert 'var(--ds-accent)' not in _pj_hero, \
    'hero proyek masih memakai var(--ds-accent) (teal) - beda dgn dashboard'
for prop in ('padding: 20px 24px', 'gap: 24px', 'color: #fff'):
    assert prop in _pj_hero, f'hero proyek kehilangan "{prop}" seperti dashboard'
assert 'border-radius: var(--ds-r-xl)' in _pj_hero, \
    'radius hero proyek harus --ds-r-xl (=16px, sama dgn dashboard)'
print('[1b] kartu hero (bar DPP/PPN) seragam dgn hero dashboard: navy + geometry sama')

# ── 2. 3 grup KPI, urutan DPP -> PPN -> Umum ──
for p in PROJECTS:
    _, html = render(p['id'])
    body = body_of(html)
    groups = re.findall(r'class="prj-group-label"[^>]*>\s*([^<]+?)\s*</div>', body)
    expect = ['DPP — Harga Pokok', 'PPN — Pajak', 'Umum — Volume Data']
    assert len(groups) == 3, f"{p['kode_proyek']}: {len(groups)} grup, harusnya 3: {groups}"
    assert groups == expect, f"{p['kode_proyek']}: urutan grup {groups} != {expect}"
print('[2] 3 grup KPI berurutan: DPP -> PPN -> Umum')

# ── 3. Tiap grup tepat 3 kartu (total 9) ──
for p in PROJECTS:
    _, html = render(p['id'])
    body = body_of(html)
    n_cards = len(re.findall(r'class="[^"]*\bprj-kpi\b(?!__)[^"]*"', body))
    assert n_cards == 9, f"{p['kode_proyek']}: {n_cards} kartu KPI, harusnya 9"
    # kartu per grup: potong per label grup
    parts = re.split(r'class="prj-group-label"[^>]*>[^<]+</div>', body)[1:]
    for lbl, part in zip(['DPP', 'PPN', 'Umum'], parts):
        n = len(re.findall(r'class="[^"]*\bprj-kpi\b(?!__)[^"]*"', part))
        assert n == 3, f"{p['kode_proyek']}: grup {lbl} punya {n} kartu, harusnya 3"
print('[3] tiap grup tepat 3 kartu KPI (total 9)')

# ── 4. Nilai Kontrak keluar dari KPI, tinggal di info strip (tepat 1x) ──
for p in PROJECTS:
    _, html = render(p['id'])
    body = body_of(html)
    assert body.count('Nilai Kontrak') == 1, (
        f"{p['kode_proyek']}: 'Nilai Kontrak' muncul {body.count('Nilai Kontrak')}x, "
        'harusnya 1x (info strip saja, tidak dobel di KPI)')
    labels = re.findall(r'class="prj-kpi__label">\s*([^<]+?)\s*</div>', body)
    assert 'Nilai Kontrak' not in labels, \
        f"{p['kode_proyek']}: Nilai Kontrak masih jadi kartu KPI"
    assert 'akumulasi kontrak vendor' not in body, \
        'catatan "akumulasi kontrak vendor" di info strip sudah dihapus'
print('[4] Nilai Kontrak hanya di info strip (1x), tidak di blok KPI')

# ── 5. Invarian per grup: Terbayar + Sisa Hutang == Total ──
for p in PROJECTS:
    k = db_project.get_project_finansial(p['id'])
    for lbl, total, bayar, sisa in (
            ('DPP', k['total_dpp'], k['bayar_dpp'], k['sisa_dpp']),
            ('PPN', k['total_ppn'], k['bayar_ppn'], k['sisa_ppn'])):
        r_, b_, s_ = _idr(money_f(total)), _idr(money_f(bayar)), _idr(money_f(sisa))
        assert abs(r_ - b_ - s_) <= 2, (
            f"{p['kode_proyek']} {lbl}: Terbayar + Sisa != Total "
            f'({b_:,.0f} + {s_:,.0f} != {r_:,.0f})')
        assert s_ >= 0, f"{p['kode_proyek']} {lbl}: sisa negatif"
print('[5] invarian Terbayar + Sisa Hutang = Total OK untuk DPP & PPN')

# ── 6. Persentase konsisten dgn angka & bar ──
for p in PROJECTS:
    k = db_project.get_project_finansial(p['id'])
    for lbl, total, bayar, pct in (
            ('DPP', k['total_dpp'], k['bayar_dpp'], k['dpp_pct']),
            ('PPN', k['total_ppn'], k['bayar_ppn'], k['ppn_pct'])):
        want = round(bayar / total * 100) if total else 0
        assert pct == want, f"{p['kode_proyek']} {lbl}: pct {pct} != {want}"
        assert 0 <= pct <= 100, f"{p['kode_proyek']} {lbl}: pct {pct} di luar 0..100"
    _, html = render(p['id'])
    body = body_of(html)
    for pct in (k['dpp_pct'], k['ppn_pct']):
        assert f'width:{pct}%' in body, f"{p['kode_proyek']}: bar width {pct}% hilang"
print('[6] persentase = round(bayar/total*100) dan bar memakai nilai yang sama')

# ── 7. Konsistensi antar halaman: dashboard vs daftar proyek ──
for p in PROJECTS:
    k = db_project.get_project_finansial(p['id'])
    assert abs(k['total_dpp'] - float(p['total_realisasi'] or 0)) < 0.01, (
        f"{p['kode_proyek']}: total_dpp {k['total_dpp']:,.0f} != "
        f"total_realisasi {float(p['total_realisasi'] or 0):,.0f}")
    assert abs(k['sisa_dpp'] - float(p['total_sisa'] or 0)) < 0.01, (
        f"{p['kode_proyek']}: sisa_dpp {k['sisa_dpp']:,.0f} != "
        f"total_sisa {float(p['total_sisa'] or 0):,.0f}")
print('[7] angka dashboard == angka daftar proyek (total_dpp & sisa_dpp)')

# ── 8. Klip per-vendor: overpay satu vendor tidak bikin sisa negatif ──
rows = [{'NAMA LEVELANSIR / REKANAN': 'A', 'HARGA (EXLD)': 100, 'PEMBAYARAN DPP': 300,
         'PPN': 10, 'PEMBAYARAN PPN': 50},
        {'NAMA LEVELANSIR / REKANAN': 'B', 'HARGA (EXLD)': 500, 'PEMBAYARAN DPP': 0,
         'PPN': 55, 'PEMBAYARAN PPN': 0}]
assert db_project._sisa_per_vendor(rows, 'HARGA (EXLD)', 'PEMBAYARAN DPP') == 500, \
    'klip per-vendor DPP salah (overpay A tidak boleh menutupi utang B)'
assert db_project._sisa_per_vendor(rows, 'PPN', 'PEMBAYARAN PPN') == 55, \
    'klip per-vendor PPN salah'
# klip per-vendor, bukan per invoice: satu vendor 2 baris saling menutup
rows2 = [{'NAMA LEVELANSIR / REKANAN': 'A', 'HARGA (EXLD)': 100, 'PEMBAYARAN DPP': 0,
          'PPN': 0, 'PEMBAYARAN PPN': 0},
         {'NAMA LEVELANSIR / REKANAN': 'A', 'HARGA (EXLD)': 100, 'PEMBAYARAN DPP': 200,
          'PPN': 0, 'PEMBAYARAN PPN': 0}]
assert db_project._sisa_per_vendor(rows2, 'HARGA (EXLD)', 'PEMBAYARAN DPP') == 0, \
    'klip harus per-vendor (dua baris vendor sama saling menutup), bukan per baris'
print('[8] klip sisa per-vendor benar (bukan per baris, tidak pernah negatif)')

# ── 9. Kelas ds-kpi--warn (tak terdefinisi) tidak dipakai lagi ──
for p in PROJECTS:
    _, html = render(p['id'])
    assert 'ds-kpi--warn' not in html, \
        'ds-kpi--warn masih dipakai (kelas ini tidak ada di app.css)'
    body = body_of(html)
    # grup DPP/PPN tetap memakai --ok (terbayar) & --err (sisa), seperti referensi
    assert body.count('prj-kpi--ok') == 2, 'harus ada 2 kartu Terbayar dgn ds-kpi--ok'
    assert body.count('prj-kpi--err') == 2, 'harus ada 2 kartu Sisa dgn ds-kpi--err'
print('[9] ds-kpi--warn tidak dipakai; --ok/--err sesuai referensi')

# ── 9b. Warna hijau kartu KPI IDENTIK dgn dashboard utama ──
# Kartu "Terbayar" di halaman proyek harus memakai warna yang sama dgn kartu
# "Terbayar DPP/PPN" di dashboard (/dashboard), bukan hex terpisah. Karena
# keduanya kini memakai token, cukup pastikan project.css memakai TOKEN itu
# dan TIDAK lagi meng-hardcode hijau.
ROOT = os.path.dirname(os.path.abspath(__file__))
_pj_css = io.open(os.path.join(ROOT, 'static', 'css', 'project.css'),
                  encoding='utf-8').read()
_app_css = io.open(os.path.join(ROOT, 'static', 'css', 'app.css'),
                   encoding='utf-8').read()

assert '.prj-kpi--ok::before { background: var(--ds-ok); }' in _pj_css, \
    'aksen hijau KPI proyek harus memakai var(--ds-ok), bukan hex hardcode'
assert '.prj-kpi--err::before { background: var(--ds-err); }' in _pj_css, \
    'aksen merah KPI proyek harus memakai var(--ds-err)'
assert '.prj-kpi__ico--green { background: var(--success-soft); color: var(--accent-dark); }' in _pj_css, \
    'ikon hijau KPI proyek harus memakai token --success-soft/--accent-dark'
# dashboard memakai token yg sama
assert '.ds-kpi--ok::before' in _app_css and 'var(--ds-ok)' in _app_css, \
    'dashboard harus memakai var(--ds-ok) untuk aksen hijau'
# bentuk aksen disamakan: garis ATAS (bukan garis kiri)
assert 'top: 0; left: 0; right: 0; height: 3px' in _pj_css, \
    'aksen KPI proyek harus garis atas 3px seperti .ds-kpi dashboard'
assert 'inset: 0 auto 0 0' not in _pj_css, \
    'aksen KPI proyek masih memakai garis kiri (bukan gaya dashboard)'
print('[9b] hijau KPI proyek = hijau dashboard (token --ds-ok/--success-soft, garis atas)')

# ── 10. Tanggal info strip terformat & nilai KPI tampil ──
for p in PROJECTS:
    _, html = render(p['id'])
    body = body_of(html)
    k = db_project.get_project_finansial(p['id'])
    for nilai, lbl in ((k['total_dpp'], 'Total DPP'), (k['bayar_dpp'], 'Terbayar DPP'),
                       (k['sisa_dpp'], 'Sisa Hutang DPP'), (k['total_ppn'], 'Total PPN'),
                       (k['bayar_ppn'], 'Terbayar PPN'), (k['sisa_ppn'], 'Sisa Hutang PPN'),
                       (k['total_tagihan'], 'Total Tagihan (Incld PPN)')):
        assert lbl in body, f"{p['kode_proyek']}: label '{lbl}' hilang"
        assert money_f(nilai) in body, f"{p['kode_proyek']}: nilai '{lbl}' tidak tampil"
    # tanggal terformat, bukan ISO mentah
    if p.get('tgl_mulai'):
        assert str(p['tgl_mulai']) not in body, (
            f"{p['kode_proyek']}: tanggal masih ISO mentah "
            f"({p['tgl_mulai']}), harusnya {tgl_f(p['tgl_mulai'])}")
        assert tgl_f(p['tgl_mulai']) in body, \
            f"{p['kode_proyek']}: tanggal mulai terformat tidak tampil"
print('[10] nilai KPI tampil & tanggal info strip terformat (bukan ISO mentah)')

print('\nALL CHECKS PASSED')
