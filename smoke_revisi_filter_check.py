# -*- coding: utf-8 -*-
"""Smoke check: checkbox "Sembunyikan Dokumen Revisi" pada Daftar Invoice.

Definisi REVISI (sama dengan badge sidebar, halaman Status Dokumen, dan
Verifikasi): field 'TGL TERIMA' (= Tgl Berkas Lengkap) masih kosong.
Lihat services/document_status.py (_COL_TGL_TERIMA) dan
services/verification.py (_COL_TGL_BERKAS_LENGKAP).

Yang diperiksa:
  1. /data-hutang render 200 dan memuat checkbox #filterRevisi + hook
     data-te-toolbar-after (kontrol ditempel di toolbar, sebelah tombol Kolom).
  2. Setiap <tr> tbody punya data-revisi="0|1".
  3. data-revisi per baris KONSISTEN dengan sel TGL TERIMA baris itu
     (data-v kosong => revisi).
  4. Jumlah data-revisi="1" sama dengan jumlah baris ber-TGL TERIMA kosong
     pada data yang dirender (silang dari controller).
  5. index.html: filterTable() memakai filterRevisi, dan Reset mengembalikannya.
  6. table-enhance.js: hook data-te-toolbar-after ada; table.css: .te-check ada.

Run:  python smoke_revisi_filter_check.py
Read-only terhadap data nyata.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import app as appmod
from services import auth as _auth

app = appmod.app
ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, 'templates', 'partials', '_data_table.html')
PAGE = os.path.join(ROOT, 'templates', 'index.html')
JS = os.path.join(ROOT, 'static', 'js', 'table-enhance.js')
CSS = os.path.join(ROOT, 'static', 'css', 'table.css')


def _is_blank(val):
    return val is None or str(val).strip() == ''


# --- 1. Halaman render + kontrol ada ---
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    r = c.get('/data-hutang')
    assert r.status_code == 200, f"/data-hutang -> {r.status_code}"
    html = r.data.decode('utf-8', 'replace')

assert 'id="filterRevisi"' in html, "checkbox #filterRevisi tidak ada di HTML"
assert 'Sembunyikan Dokumen Revisi' in html, "label checkbox tidak ada"
assert re.search(r'data-te-toolbar-after="#revisiToggleWrap"', html), \
    "atribut data-te-toolbar-after tidak ada pada tabel"
print("[1] /data-hutang 200 + checkbox & hook toolbar OK")


# --- 2 & 3. data-revisi ada di setiap baris dan konsisten dengan TGL TERIMA ---
tbody = html[html.index('<tbody>'):html.index('</tbody>')]
rows = re.findall(r'<tr\b.*?</tr>', tbody, re.S)
assert rows, "tbody kosong — tak ada baris untuk diperiksa"

flags = []
for chunk in rows:
    m = re.search(r'data-revisi="([01])"', chunk)
    assert m, "baris tanpa atribut data-revisi"
    flag = m.group(1)
    flags.append(flag)
    tds = re.findall(r'<td\b[^>]*>', chunk)
    assert len(tds) >= 8, f"baris terlalu sedikit sel: {len(tds)}"
    # Kolom index 7 = TGL TERIMA (Tgl Berkas Lengkap).
    vm = re.search(r'data-v="([^"]*)"', tds[7])
    assert vm, "sel TGL TERIMA tanpa data-v"
    expected = '1' if vm.group(1).strip() == '' else '0'
    assert flag == expected, \
        f"data-revisi={flag} tidak cocok dgn TGL TERIMA='{vm.group(1)}'"

n_revisi = flags.count('1')
print(f"[2] {len(rows)} baris punya data-revisi, konsisten dgn sel TGL TERIMA OK")
print(f"    {n_revisi} baris ditandai revisi (TGL TERIMA kosong)")


# --- 4. Silang jumlah terhadap data yang dirender controller ---
from flask import session as _fsession
from services.project_context import get_read_filter
from services.dashboard import build_dashboard_context

with app.test_request_context('/data-hutang'):
    _fsession[_auth.SESSION_KEY] = True
    ctx = build_dashboard_context(get_read_filter(), for_table=True)
data = ctx['data']
expected_n = sum(1 for row in data if _is_blank(row.get('TGL TERIMA')))
assert expected_n == n_revisi, \
    f"jumlah baris revisi tak cocok: HTML={n_revisi} vs data={expected_n}"
print(f"[4] jumlah revisi HTML == data ({expected_n}) OK")


# --- 5. Wiring di page script ---
with open(PAGE, encoding='utf-8') as f:
    page = f.read()
assert "getElementById('filterRevisi')?.checked" in page, \
    "filterTable() tidak membaca #filterRevisi"
assert 'revisiMatch' in page, "filterTable() tidak memakai revisiMatch"
assert 'jtMatch && revisiMatch' in page, \
    "revisiMatch tidak ikut dalam konjungsi match"
assert re.search(r"getElementById\('filterRevisi'\)\?\.addEventListener\('change', filterTable\)", page), \
    "checkbox tidak terhubung ke filterTable()"
assert re.search(r"const rv = document\.getElementById\('filterRevisi'\);\s*\n\s*if \(rv\) rv\.checked = false;", page), \
    "Reset tidak mengembalikan checkbox ke OFF"
assert "tr.dataset.filterPass === '0'" in page, \
    "updateFootTotals() tidak melewatkan baris tak-lolos-filter"
print("[5] index.html: filterTable + Reset + subtotal wiring OK")


# --- 6. Enhancer & CSS ---
with open(TPL, encoding='utf-8') as f:
    tpl = f.read()
assert tpl.index('id="revisiToggleWrap"') < tpl.index('class="table-scroll"'), \
    "kontrol harus berada di luar area scroll tabel"
assert re.search(r"data-revisi=\"\{\{ '1' if \(row\['TGL TERIMA'\] or ''\)", tpl), \
    "data-revisi tidak memakai field TGL TERIMA"

with open(JS, encoding='utf-8') as f:
    js = f.read()
assert 'data-te-toolbar-after' in js, "table-enhance.js tak membaca data-te-toolbar-after"
assert 'host.querySelectorAll(extraSel)' in js, "hook toolbar tak memindai node host"
# Kontrol harus mendarat TEPAT setelah tombol Kolom (sebelum spacer/info).
assert js.index('bar.appendChild(colBtn)') < js.index('data-te-toolbar-after') \
    < js.index("var info = el('div', 'te-info')"), \
    "hook toolbar tidak berada tepat setelah tombol Kolom"

with open(CSS, encoding='utf-8') as f:
    css = f.read()
assert '.te-toolbar-check {' in css, "table.css tak punya gaya .te-toolbar-check"
assert '.te-toolbar-check[hidden]' in css, \
    "tanpa [hidden]-guard kontrol bisa tampil sebelum enhancer memindahkannya"
assert css.count('.te-toolbar-check,') >= 2, \
    "ukuran sentuh .te-toolbar-check belum ikut breakpoint HP"
# Kelas checkbox panel "Kolom" (.te-check) tetap harus ada (tidak tertimpa).
assert '.te-check {' in css, "kelas .te-check panel Kolom hilang"
print("[6] table-enhance.js hook + .te-toolbar-check CSS OK")

print()
print('ALL CHECKS PASSED')
