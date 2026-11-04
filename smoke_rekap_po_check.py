# -*- coding: utf-8 -*-
"""Smoke check: halaman Rekap Kontrak (/kontrak/rekap-no-po).

Verifikasi:
  1. Klasifikasi bucket: KSO < 300 jt, UB 300 jt..2,5 M, PS > 2,5 M.
  2. build_rekap — total per periode = Σ nilai baris; identitas
     SD Bulan Ini = S/D Bulan Lalu + Bulan Ini; NILAI KONTRAK = Σ DPP
     kontrak yang sudah ada s/d periode.
  3. Nilai per baris hanya terisi di kolom bucket baris itu.
  4. Halaman render HTTP 200, menu sidebar + canvas chart ada.

Run:  python smoke_rekap_po_check.py   (read-only data nyata)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
import db_contract
from services import rekap_po

# --- 1. Bucket boundaries ---
_cases = [
    (0, 'kso'),
    (299_999_999, 'kso'),
    (300_000_000, 'unit'),
    (1_000_000_000, 'unit'),
    (2_500_000_000, 'unit'),
    (2_500_000_001, 'pusat'),
    (30_000_000_000, 'pusat'),
]
for _v, _want in _cases:
    _got = rekap_po._bucket_of(_v)
    assert _got == _want, f"bucket({_v:,}) = {_got}, harus {_want}"
print(f'[1] bucket OK: {len(_cases)} batas diuji')

# --- 2/3. build_rekap sintetis (kontrol penuh) ---
_contracts = [
    {'no_kontrak': 'A/1', 'vendor': 'V1', 'item_pekerjaan': 'I1',
     'tgl_kontrak': '2026-01-15', 'nilai_dpp': 100_000_000},          # KSO, s/d lalu
    {'no_kontrak': 'B/2', 'vendor': 'V2', 'item_pekerjaan': 'I2',
     'tgl_kontrak': '2026-10-05', 'nilai_dpp': 500_000_000},          # UB, bulan ini
    {'no_kontrak': 'C/3', 'vendor': 'V3', 'item_pekerjaan': 'I3',
     'tgl_kontrak': '2026-09-30', 'nilai_dpp': 3_000_000_000},        # PS, s/d lalu
    {'no_kontrak': 'D/4', 'vendor': 'V4', 'item_pekerjaan': 'I4',
     'tgl_kontrak': '2026-10-31', 'nilai_dpp': 200_000_000},          # KSO, bulan ini
    {'no_kontrak': 'E/5', 'vendor': 'V5', 'item_pekerjaan': 'I5',
     'tgl_kontrak': '', 'nilai_dpp': 50_000_000},                     # tanpa tanggal -> bukan periode
]
_r = rekap_po.build_rekap(_contracts, 2026, 10)

assert _r['total_kontrak'] == 5, f"total_kontrak {_r['total_kontrak']} != 5"
assert _r['grand_totals']['kontrak_kini'] == 3_850_000_000, _r['grand_totals']
# S/D lalu = A(100jt) + C(3M) = 3,1M ; Bulan ini = B(500jt) + D(200jt) = 700jt
assert _r['grand_totals']['sd_bulan_lalu'] == 3_100_000_000, _r['grand_totals']
assert _r['grand_totals']['bulan_ini'] == 700_000_000, _r['grand_totals']
assert _r['grand_totals']['sd_bulan_ini'] == 3_800_000_000, _r['grand_totals']
# identitas: SD Bulan Ini = S/D lalu + Bulan ini
assert (_r['grand_totals']['sd_bulan_ini']
        == _r['grand_totals']['sd_bulan_lalu'] + _r['grand_totals']['bulan_ini']), \
    'SD Bulan Ini != S/D Bulan Lalu + Bulan Ini'

# bucket terisi konsisten per baris
_row_a = next(x for x in _r['rows'] if x['no_kontrak'] == 'A/1')
assert _row_a['bucket'] == 'kso', _row_a['bucket']
assert _row_a['periods']['kini']['kso'] == 100_000_000
assert _row_a['periods']['sdl']['kso'] == 100_000_000
assert _row_a['periods']['bln']['kso'] == 0
assert _row_a['periods']['sdi']['kso'] == 100_000_000
assert _row_a['periods']['kini']['unit'] == 0 and _row_a['periods']['kini']['pusat'] == 0, \
    'baris KSO tidak boleh punya nilai di bucket lain'
_row_b = next(x for x in _r['rows'] if x['no_kontrak'] == 'B/2')
assert _row_b['bucket'] == 'unit' and _row_b['periods']['bln']['unit'] == 500_000_000
assert _row_b['periods']['sdi']['unit'] == 500_000_000 and _row_b['periods']['sdl']['unit'] == 0
_row_e = next(x for x in _r['rows'] if x['no_kontrak'] == 'E/5')
assert all(_row_e['periods']['sdl'][b] == 0 and _row_e['periods']['bln'][b] == 0
           for b in ('kso', 'unit', 'pusat')), 'kontrak tanpa tanggal tidak masuk periode'
# Periode lama = snapshot: kontrak setelah periode tidak dihitung, yang tanpa
# tanggal tetap tampil agar tidak hilang permanen.
_old = rekap_po.build_rekap(_contracts, 2026, 1)
assert _old['total_kontrak'] == 2, _old['total_kontrak']
assert _old['grand_totals']['kontrak_kini'] == 150_000_000, _old['grand_totals']
_old_b = next(x for x in _old['rows'] if x['no_kontrak'] == 'B/2')
assert _old_b['visible'] is False, 'kontrak setelah periode harus tidak tampil'
assert all(v == 0 for v in _old_b['periods']['kini'].values()), \
    'baris tersembunyi tidak boleh menyumbang NILAI KONTRAK'
print('[2] build_rekap OK: periode + identitas SD = lalu + ini + bucket per baris')

# --- 4. Halaman render nyata (data DB) ---
app = appmod.app
client = app.test_client()
with client.session_transaction() as s:
    s['authed'] = True
_html = client.get('/kontrak/rekap-no-po').get_data(as_text=True)
assert client.get('/kontrak/rekap-no-po').status_code == 200, \
    'halaman Rekap Kontrak tidak HTTP 200'
for _needle in ('id="rpTable"', 'id="rpChartBar"', 'id="rpChartDonut"',
                'NILAI KONTRAK', 'S/D BULAN LALU', 'BULAN INI', 'SD BULAN INI',
                'id="rpKpiCount"', 'id="rpKpiKontrak"', 'data-period-visible='):
    assert _needle in _html, f'elemen {_needle!r} tidak ada di halaman'
_n_contracts = len(db_contract.get_contracts('all'))
_n_rows = len(re.findall(r'data-bucket="', _html))
assert _n_rows == _n_contracts, f'baris tabel {_n_rows} != kontrak {_n_contracts}'
assert 'data-period-visible="0"' not in _html, \
    'periode terbaru harus menampilkan semua kontrak'

# --- 6. Struktur tabel: header bucket tidak disingkat, No. PO digabung ke vendor ---
assert 'No. PO / Kontrak' not in _html, 'kolom No. PO / Kontrak masih terpisah'
for _label in ('<th class="text-center">Unit Bisnis</th>', '<th class="text-center">Pusat</th>'):
    assert _label in _html, f'header {_label!r} tidak ditemukan (masih disingkat?)'
assert '<th class="text-center">UB</th>' not in _html, 'header UB masih disingkat'
assert '<th class="text-center">PS</th>' not in _html, 'header PS masih disingkat'
assert 'rp-vend-no' in _html, 'nomor kontrak tidak tampil di bawah nama vendor'
_tbody = re.search(r'<tbody id="rpBody">(.*?)</tbody>', _html, re.S)
assert _tbody, 'tbody #rpBody tidak ditemukan'
_body_rows = re.findall(r'<tr data-search=.*?</tr>', _tbody.group(1), re.S)
assert _body_rows, 'tidak ada baris data'
for _tr in _body_rows:
    _vend = re.search(r'<div class="rp-vend-name"[^>]*>(.*?)</div>', _tr, re.S)
    assert _vend, 'nama vendor tidak ditemukan di baris'
    assert '<a href="/kontrak/' in _vend.group(1) or 'Vendor belum diisi' in _vend.group(1), \
        'nama vendor yang terisi harus menjadi link ke detail kontrak'
    assert len(re.findall(r'<td\b', _tr)) == 18, \
        f'jumlah <td> baris != 18: {len(re.findall(r"<td\\b", _tr))}'
_th_row2 = re.search(r'</tr>\s*<tr>\s*(<th.*?)</tr>', _html, re.S)
assert _th_row2 and len(re.findall(r'<th\b', _th_row2.group(1))) == 18, \
    'jumlah <th> baris kedua != 18'
# Tgl Kontrak masuk blok identitas, tepat setelah Item Pekerjaan.
_th2 = _th_row2.group(1)
assert '<th class="text-center">Tgl Kontrak</th>' in _th2, 'kolom Tgl Kontrak tidak ada'
assert _th2.index('Item Pekerjaan') < _th2.index('Tgl Kontrak') < _th2.index('>KSO<'), \
    'Tgl Kontrak harus setelah Item Pekerjaan dan sebelum NILAI KONTRAK'
assert 'class="rp-date" data-type="date" data-v="' in _html, 'sel tanggal kontrak tidak render'
# Kolom sticky kanan: Kategori (kanan-2) lalu Invoice (paling kanan).
assert _th2.rindex('>Invoice</th>') > _th2.rindex('>Kategori</th>'), \
    'Invoice harus jadi kolom paling kanan'
assert 'col-sticky-right-2 text-center">Kategori' in _html, \
    'kolom Kategori harus beku kanan di kiri Invoice'
assert 'col-sticky-right text-center" title="Jumlah invoice' in _html, \
    'kolom Invoice tidak beku kanan'
assert 'box-shadow: inset 1px 0 0 var(--dt-border)' in _html, \
    'garis vertikal kolom beku kanan belum ada'
assert 'class="rp-stat-pill ' in _body_rows[0], 'sel Invoice tidak render di baris'
assert len(re.findall(r'class="rp-stat-pill ', _html)) == len(_body_rows), \
    'setiap baris kontrak harus punya tepat satu pill Invoice'
# Baris grup header harus menutup SEMUA kolom (18). Kalau kurang, area header
# transparan dan isi kolom Bucket tembus ke atas saat tabel di-scroll.
_grp_row = re.search(r'<tr class="rp-grp-row">(.*?)</tr>', _html, re.S)
assert _grp_row, 'baris grup header tidak ditemukan'
_spans = [int(x) for x in re.findall(r'colspan="(\d+)"', _grp_row.group(1))]
assert sum(_spans) == 18, f'colspan grup header {sum(_spans)} != 18 kolom ({_spans})'
assert '<span class="rp-bkt-pill rp-bkt--unit">Unit Bisnis</span>' in _html, \
    'pill bucket masih menampilkan singkatan UB'
assert '<span class="rp-bkt-pill rp-bkt--pusat">Pusat</span>' in _html, \
    'pill bucket masih menampilkan singkatan PS'
print(f'[5] struktur tabel OK: 18 kolom, Tgl Kontrak setelah Item, Invoice sticky kanan + garis, header Kategori + pill kategori nama penuh')

# menu sidebar di halaman mana pun
_dash = client.get('/dashboard').get_data(as_text=True)
assert 'id="navRekapKontrak"' in _dash and 'Rekap PO Kontrak' in _dash, \
    'menu sidebar Rekap PO Kontrak tidak render'
print(f'[3] halaman OK: {_n_rows} baris, chart + menu sidebar ada')

# --- 5. Filter periode ganti bulan mengubah angka (Des vs Okt) ---
_o = client.get('/kontrak/rekap-no-po?year=2026&month=10').get_data(as_text=True)
_d = client.get('/kontrak/rekap-no-po?year=2025&month=12').get_data(as_text=True)
assert _o != _d, 'ganti periode tidak mengubah halaman'
# Periode lama = snapshot: baris setelah periode disembunyikan, KPI menghitung
# baris yang tampil saja.
_old_ctx = rekap_po.build_rekap(db_contract.get_contracts('all'), 2025, 12)
_n_rows_all = len(db_contract.get_contracts('all'))
assert _old_ctx['total_kontrak'] < _n_rows_all, 'periode lama harus menyembunyikan kontrak'
assert f'id="rpKpiCount">{_old_ctx["total_kontrak"]}<' in _d, \
    'KPI Total Kontrak tidak mengikuti periode'
_n_hidden = _n_rows_all - _old_ctx['total_kontrak']
assert _d.count('data-period-visible="0"') == _n_hidden, \
    'jumlah baris tersembunyi tidak sesuai periode'
assert _d.count('data-filter-pass="0"') == _n_hidden, \
    'baris tersembunyi belum ditandai untuk TableEnhance'
assert 'KONTRAK KINI' not in _d and 'Kontrak Kini' not in _d, \
    'label KONTRAK KINI masih ada'
assert 'NILAI KONTRAK' in _d, 'label NILAI KONTRAK tidak ada'
print('[4] filter periode OK')

# --- 7. Filter periode client-side (pola halaman Jatuh Tempo) ---
_base = client.get('/dashboard').get_data(as_text=True)
assert "'/kontrak/rekap-no-po'" in _base, \
    'rute Rekap Kontrak belum terdaftar di HTMX_READY_ROUTES'
for _needle in ('function applyPeriod', 'function buildSeries', 'rpUpdateBarChart',
                'rpUpdateDonut', 'rpFilterRows', 'tds[4 + i]',
                'data-period-visible=', 'data-tgl=', 'data-foot="sdl.kso"',
                'data-foot="kini.kso"', 'id="rpKpiSd"', 'id="rpKpiCount"',
                'id="rpKpiKontrak"', 'name="period"', 'id="rpFilterBucket"',
                "getElementById('rpFilterBucket')", 'rpRefreshFilteredSummary',
                'moneyNumber', "filterPass !== '1'"):
    assert _needle in _html, f'{_needle!r} tidak ada (filter client-side belum lengkap)'
assert 'rpPeriodGo' not in _html and 'rpPeriodSubmit' not in _html, \
    'ganti periode masih memakai navigasi halaman, bukan hitung ulang di tempat'
assert _html.index('id="rpPeriod"') < _html.index('id="rpFilterBucket"') < _html.index('id="rpSearch"'), \
    'filter kategori harus berada setelah periode dan sebelum pencarian'
for _opt in ('Semua Kategori', 'value="kso"', 'value="unit"', 'value="pusat"'):
    assert _opt in _html, f'opsi filter kategori {_opt!r} tidak ada'
assert 'te.instances[rpTable.id]' in _html, \
    'filter periode harus cek instance TableEnhance milik rpTable'
assert 'per Kategori' in _html and '>Bucket</th>' not in _html, \
    'label Bucket belum diganti Kategori'
assert 'name="month"' not in _html and 'name="year"' not in _html, \
    'masih ada dua dropdown bulan/tahun terpisah'
assert 'data-step=' not in _html, 'tombol prev/next lama masih ada'
# Badge periode terpilih: sejajar toolbar, teks ikut dropdown saat diganti.
assert 'id="rpPeriodBadge"' in _html and 'id="rpPeriodBadgeText"' in _html, \
    'badge periode terpilih tidak ada di toolbar'
_badge = re.search(r'id="rpPeriodBadgeText">([^<]+)</span>', _html)
assert _badge and _badge.group(1).strip(), 'badge periode kosong'
_sel_opt = re.search(r'<option value="(\d{4}-\d{2})" selected>([^<]+)</option>', _html)
assert _sel_opt and _badge.group(1).strip() == _sel_opt.group(2).strip(), \
    'teks badge periode tidak sama dengan opsi terpilih'
assert "getElementById('rpPeriodBadgeText')" in _html, \
    'badge periode tidak diperbarui saat periode diganti'
assert "'rpChartBar'" in _base, 'chart Rekap tidak dibersihkan saat HTMX swap'
# Label sumbu-X harus nama bulan, bukan indeks tick (Chart.js memberi index
# mentah ke callback; tanpa getLabelForValue yang tampil "1 2 3").
assert 'this.getLabelForValue(value)' in _html, \
    'label bulan chart tidak diambil dari getLabelForValue (bisa tampil 1 2 3)'
assert "return val + '\\n' + yr" not in _html, 'callback sumbu-X masih memakai indeks mentah'
assert 'autoSkip: true' in _html and 'maxRotation: 0' in _html, \
    'tick sumbu-X belum dirapikan (autoSkip / tanpa rotasi)'
print('[6] filter periode OK: satu dropdown, hitung ulang tabel/KPI/chart di tempat')

# --- 8. Opsi dropdown = bulan yang ada di tanggal kontrak ---
_periods = re.findall(r'<option value="(\d{4}-\d{2})"', _html)
_ctract_months = sorted({str(c.get('tgl_kontrak'))[:7] for c in db_contract.get_contracts('all')
                         if str(c.get('tgl_kontrak') or '')[:4].isdigit()})
assert _periods == _ctract_months, \
    f'opsi periode {_periods} != bulan tanggal kontrak {_ctract_months}'
_selected = re.search(r'<option value="(\d{4}-\d{2})" selected>', _html)
assert _selected, 'tidak ada periode terpilih di dropdown'
assert _selected.group(1) in _periods, 'periode terpilih tidak ada di daftar opsi'

# period= sama dengan year/month; periode tak tersedia jatuh ke bulan terakhir
_a = client.get('/kontrak/rekap-no-po?period=2026-10').get_data(as_text=True)
_b = client.get('/kontrak/rekap-no-po?year=2026&month=10').get_data(as_text=True)
assert _a == _b, 'parameter period tidak menghasilkan halaman yang sama dengan year/month'
_latest = _periods[-1]
_fallback = client.get('/kontrak/rekap-no-po?period=2000-01').get_data(as_text=True)
assert f'<option value="{_latest}" selected>' in _fallback, \
    'periode tak tersedia tidak jatuh ke bulan terakhir yang ada data'
print(f'[7] dropdown periode OK: {len(_periods)} bulan dari tanggal kontrak, default {_latest}')

print('ALL CHECKS PASSED')
