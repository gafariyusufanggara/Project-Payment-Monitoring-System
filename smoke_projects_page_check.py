# -*- coding: utf-8 -*-
"""Smoke check: halaman Daftar Proyek (projects.html).

Memverifikasi:
- KPI ringkasan (Total Proyek / Total Realisasi / Total Sisa Hutang) sudah
  DIHAPUS dari page utama — termasuk CSS mati-nya, bukan sekadar disembunyikan;
- progress bar "Progres thd Nilai Kontrak" sudah DIHAPUS, beserta sisa markup
  (label, catatan, dan variabel denom/pct/bar_class di template);
- kartu menampilkan tiga angka keuangan dengan urutan yang benar:
  Realisasi, Terbayar, Sisa Hutang;
- nilai_kontrak TIDAK ditampilkan di kartu (alasannya: ia menjumlah seluruh
  kontrak vendor sehingga bila disandingkan dengan realisasi terbaca seolah
  "kontrak baru terserap beberapa persen" - angka yang menyesatkan);
- invarian angka: Terbayar == Realisasi - Sisa Hutang (dan tidak negatif);
- tombol Edit tidak lagi ada di daftar; hanya Dashboard (Edit ada di Dashboard);
- periode rencana tampil terformat (pakai filter `tgl`).

Run:  python smoke_projects_page_check.py
Read-only terhadap data nyata.
"""
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


def render_page():
    with app.test_client() as c:
        with c.session_transaction() as s:
            s[SESSION_KEY] = True
        r = c.get('/project/')
        return r.status_code, r.get_data(as_text=True)


status, html = render_page()
assert status == 200, f'GET /project/ -> {status}, harusnya 200'

# Badan template saja (tanpa blok <style>) untuk assert teks/markup, supaya
# nama selector di CSS tidak dianggap sebagai markup yang masih hidup.
body = re.sub(r'<style>.*?</style>', '', html, flags=re.S)

# --- 1. KPI ringkasan benar-benar dihapus ---
for needle in ('prj-kpis', 'ds-kpi', 'kpi-ico', 'ds-kpi--compact'):
    assert needle not in body, f'markup KPI masih ada di body: {needle}'
assert 'prj-kpis' not in html, 'CSS .prj-kpis masih tertinggal di <style>'
assert 'ds-kpi' not in html, 'CSS .ds-kpi masih tertinggal di <style>'
assert 'kpi-ico' not in html, 'CSS .kpi-ico masih tertinggal di <style>'
print('[1] KPI ringkasan halaman daftar proyek sudah dihapus (markup + CSS)')

# --- 2. Progress terhadap nilai kontrak dihapus ---
for needle in ('prj-progress', 'prj-prog-lbl', 'prj-prog-note',
               'role="progressbar"', 'Progres thd Nilai Kontrak',
               'Isi Nilai Kontrak untuk melihat progres'):
    assert needle not in html, f'sisa progress masih ada: {needle}'
assert 'bar_class' not in html and 'denom' not in html, \
    'variabel progress (denom/bar_class) masih dihitung di template'
print('[2] progress thd nilai kontrak sudah dihapus (markup + CSS + variabel)')

# --- 3. KPI/progress memang tidak dirender, tapi grid & toolbar tetap ---
assert 'prj-grid' in body, 'grid kartu hilang'
assert '/project/create' in body, 'tombol Proyek Baru hilang'
print('[3] grid kartu + tombol Proyek Baru tetap utuh')

# --- 4. Tiga angka keuangan, urutan: Realisasi -> Terbayar -> Sisa Hutang ---
labels = re.findall(r'class="prj-money-label">\s*([^<]+?)\s*</div>', body)
assert len(labels) == 3 * len(PROJECTS), \
    f'jumlah label angka: {len(labels)}, harusnya {3 * len(PROJECTS)}'
EXPECTED = ['Realisasi', 'Terbayar', 'Sisa Hutang']
for i in range(len(PROJECTS)):
    got = labels[i * 3:(i + 1) * 3]
    assert got == EXPECTED, f'urutan label proyek ke-{i + 1}: {got} != {EXPECTED}'
print(f'[4] urutan angka benar di {len(PROJECTS)} kartu: {" -> ".join(EXPECTED)}')

# --- 5. Nilai kontrak tidak ditampilkan di kartu ---
assert 'Nilai Kontrak' not in body, \
    'label "Nilai Kontrak" masih muncul di kartu (sengaja dikeluarkan)'
for p in PROJECTS:
    nk = '{:,.0f}'.format(round(float(p.get('nilai_kontrak') or 0))).replace(',', '.')
    if nk.strip('0.') == '':      # nilai kontrak nol -> tidak bermakna diuji
        continue
    assert nk not in body, f'nilai kontrak proyek {p["kode_proyek"]} ({nk}) bocor ke kartu'
print('[5] nilai kontrak tidak ditampilkan di kartu')

# --- 6. Invarian angka: Terbayar == Realisasi - Sisa Hutang ---
money_f = app.jinja_env.filters['money']
sisa_f = app.jinja_env.filters['has_sisa']


def _idr(text):
    """Kembalikan nilai rupiah dari string berformat Indonesia."""
    return float(re.sub(r'[^0-9-]', '', text) or 0)


values = re.findall(r'class="prj-money-value[^"]*">\s*([\d.]+)\s*</div>', body)
assert len(values) == 3 * len(PROJECTS), \
    f'jumlah nilai angka: {len(values)}, harusnya {3 * len(PROJECTS)}'

for idx, p in enumerate(PROJECTS):
    realisasi = float(p.get('total_realisasi') or 0)
    sisa = float(p.get('total_sisa') or 0)
    terbayar = realisasi - sisa
    got_r, got_b, got_s = (_idr(v) for v in values[idx * 3:(idx + 1) * 3])
    assert got_r == _idr(money_f(realisasi)), \
        f'{p["kode_proyek"]}: realisasi {got_r} != {money_f(realisasi)}'
    assert got_b == _idr(money_f(terbayar)), \
        f'{p["kode_proyek"]}: terbayar {got_b} != {money_f(terbayar)}'
    assert got_s == _idr(money_f(sisa)), \
        f'{p["kode_proyek"]}: sisa {got_s} != {money_f(sisa)}'
    # Invarian di level angka yang DITAMPILKAN (bukan hanya di level data):
    # selisih pembulatan per-sel maksimal 1 rupiah di tiap sisi.
    assert abs(got_r - got_b - got_s) <= 2, (
        f'{p["kode_proyek"]}: Terbayar+M Sisa != Realisasi '
        f'({got_b:,.0f} + {got_s:,.0f} != {got_r:,.0f})')
    assert got_b >= 0, f'{p["kode_proyek"]}: Terbayar negatif ({got_b:,.0f})'
print(f'[6] invarian Terbayar + Sisa Hutang = Realisasi OK '
      f'({len(PROJECTS)} proyek, selisih <= 1 rupiah/sel)')

# --- 7. Warna Sisa Hutang: merah hanya bila ada sisa signifikan ---
sisa_cells = re.findall(
    r'<div class="prj-money-label">Sisa Hutang</div>\s*'
    r'<div class="prj-money-value([^"]*)">', body)
assert len(sisa_cells) == len(PROJECTS), f'jumlah sel sisa: {len(sisa_cells)}'
for idx, p in enumerate(PROJECTS):
    want = ' prj-money-value--neg' if sisa_f(p.get('total_sisa')) else ''
    assert sisa_cells[idx] == want, (
        f'{p["kode_proyek"]}: kelas warna sisa {sisa_cells[idx]!r} != {want!r}')
print('[7] pewarnaan Sisa Hutang mengikuti has_sisa (merah hanya bila ada sisa)')

# --- 8. Aksi: hanya Dashboard; Edit tidak lagi di daftar ---
assert 'project_dashboard' in body or '/dashboard' in body, 'link Dashboard hilang'
# Catat: base.html punya JS modal edit invoice ('/edit/' + rowIdx) yang membawa
# kata "/edit" di seluruh halaman. Yang diuji di sini adalah LINK di zona aksi
# kartu proyek, bukan sekadar keberadaan string "/edit" di mana pun.
card_links = re.findall(r'<div class="prj-card-actions">(.*?)</div>', body, flags=re.S)
assert len(card_links) == len(PROJECTS), \
    f'jumlah zona aksi: {len(card_links)}, harusnya {len(PROJECTS)}'
for idx, block in enumerate(card_links):
    hrefs = re.findall(r'href="([^"]+)"', block)
    assert len(hrefs) == 1, f'kartu ke-{idx + 1}: {len(hrefs)} link, harusnya 1 (Dashboard)'
    assert '/dashboard' in hrefs[0], \
        f'kartu ke-{idx + 1}: link {hrefs[0]!r} bukan Dashboard'
    assert '/edit' not in block, f'kartu ke-{idx + 1}: link Edit masih ada'
# Link Edit proyek (/project/<id>/edit) tidak boleh muncul sama sekali.
assert not re.search(r'/project/\d+/edit', body), \
    'link edit proyek masih ada di halaman daftar'
print('[8] aksi kartu: hanya Dashboard (Edit tersedia di halaman Dashboard)')

# --- 9. Periode rencana terformat via filter tgl ---
tgl_f = app.jinja_env.filters['tgl']
periods = re.findall(r'class="prj-period">.*?<span>(.*?)</span>', body, flags=re.S)
assert len(periods) == len(PROJECTS), f'jumlah periodo: {len(periods)}'
for idx, p in enumerate(PROJECTS):
    want = f'{tgl_f(p.get("tgl_mulai"))} &ndash; {tgl_f(p.get("tgl_selesai"))}'
    want = want.replace('&ndash;', '\u2013')
    got = periods[idx].replace('&ndash;', '\u2013').replace('\u00a0', ' ')
    assert got.strip() == want.strip(), \
        f'{p["kode_proyek"]}: periode {got!r} != {want!r}'
print('[9] periode rencana tampil terformat (filter tgl, kosong -> em dash)')

print('\nALL CHECKS PASSED')
