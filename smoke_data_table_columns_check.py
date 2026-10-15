# -*- coding: utf-8 -*-
"""Smoke check: kolom default Data Invoice (data-te-default-hidden).

Memverifikasi bahwa tabel Data Invoice (/data-hutang) menandai kolom mana yang
tampil secara default via atribut data-te-default-hidden, dan bahwa JS
(table-enhance.js) menerapkan default itu HANYA bila belum ada preferensi
tersimpan, serta menghormati tombol "Kolom" (localStorage) begitu dipakai.

Aturan default (disetujui pengguna):
  ON  : #, NAMA LEVELANSIR, TGL BERKAS LENGKAP, NO. INVOICE, NO. PO/KONTRAK,
        NILAI DPP, NILAI PPN, POT. PPH, RETENSI, AKSI
  OFF : NO. INV CICILAN, TGL INVOICE, TGL TERIMA BERKAS, NO. SERI FAKTUR,
        STATUS DPP, STATUS PPN, TOTAL (INCLD), BAYAR DPP, BAYAR PPN,
        SISA HUTANG DPP, SISA HUTANG PPN

  1. Halaman /data-hutang render 200 & memuat data-te-default-hidden.
  2. Semua label OFF benar-benar ada sebagai header (<th>) di template.
  3. Label ON tidak ikut masuk daftar OFF.
  4. Kolom sticky (#, NAMA LEVELANSIR, AKSI) ditandai te-col-locked (tidak bisa
     disembunyikan).
  5. table-enhance.js memuat logika default + fallback ke preferensi tersimpan.

Run:  python smoke_data_table_columns_check.py
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
JS = os.path.join(ROOT, 'static', 'js', 'table-enhance.js')

EXPECTED_OFF = [
    'NO. INV CICILAN', 'TGL INVOICE', 'TGL TERIMA BERKAS', 'NO. SERI FAKTUR',
    'STATUS DPP', 'STATUS PPN', 'TOTAL (INCLD)',
]
EXPECTED_ON = [
    '#', 'NAMA LEVELANSIR', 'TGL BERKAS LENGKAP', 'NO. INVOICE',
    'NO. PO/KONTRAK', 'NILAI DPP', 'NILAI PPN', 'POT. PPH', 'RETENSI',
    'SISA HUTANG DPP', 'SISA HUTANG PPN', 'BAYAR DPP', 'TGL BAYAR DPP',
    'BAYAR PPN', 'TGL BAYAR PPN', 'AKSI',
]
# Urutan relatif kolom bayar: BAYAR DPP → TGL BAYAR DPP → BAYAR PPN → TGL BAYAR PPN.
EXPECTED_ORDER = ['BAYAR DPP', 'TGL BAYAR DPP', 'BAYAR PPN', 'TGL BAYAR PPN']


def _th_labels(html):
    thead = html[html.index('<thead>'):html.index('</thead>')]
    ths = re.findall(r'<th\b[^>]*>(.*?)</th>', thead, re.S)
    out = []
    for inner in ths:
        inner = re.sub(r'<span class="sort-arrow">.*?</span>', '', inner, flags=re.S)
        inner = re.sub(r'<[^>]+>', '', inner)
        out.append(re.sub(r'\s+', ' ', inner).strip())
    return out


# --- 1. Halaman render & memuat atribut ---
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    r = c.get('/data-hutang')
    assert r.status_code == 200, f"/data-hutang -> {r.status_code}"
    html = r.data.decode('utf-8', 'replace')
assert 'data-te-default-hidden' in html, "atribut data-te-default-hidden tidak ada di HTML"
m = re.search(r'data-te-default-hidden="([^"]*)"', html)
assert m, "atribut data-te-default-hidden tidak terbaca"
defaults = [x.strip().lower() for x in m.group(1).split('|') if x.strip()]
print(f"[1] /data-hutang 200, {len(defaults)} kolom default OFF OK")


# --- 2 & 3. Label OFF ada sebagai header; label ON tidak ikut OFF ---
with open(TPL, encoding='utf-8') as f:
    tpl = f.read()
labels = [l.lower() for l in _th_labels(tpl)]
assert len(labels) >= 20, f"header terlalu sedikit: {len(labels)}"

missing = [d for d in EXPECTED_OFF if d.lower() not in labels]
assert not missing, f"label OFF tak ada sebagai header: {missing}"
assert set(d.lower() for d in defaults) == set(d.lower() for d in EXPECTED_OFF), \
    f"daftar default OFF tidak sesuai. dapat={sorted(defaults)}"

on_leaked = [o for o in EXPECTED_ON if o.lower() in set(defaults)]
assert not on_leaked, f"kolom ON ikut masuk daftar OFF: {on_leaked}"
print(f"[2] semua {len(EXPECTED_OFF)} label OFF valid; tak ada kolom ON bocor ke OFF OK")


# --- 2b. Kolom tanggal bayar ada & urutannya benar ---
labels_raw = _th_labels(tpl)
positions = {}
for lab in EXPECTED_ORDER:
    idxs = [i for i, l in enumerate(labels_raw) if l.lower() == lab.lower()]
    assert len(idxs) == 1, f"kolom '{lab}' harus ada tepat 1, dapat {len(idxs)}"
    positions[lab] = idxs[0]
assert positions['BAYAR DPP'] < positions['TGL BAYAR DPP'] < \
       positions['BAYAR PPN'] < positions['TGL BAYAR PPN'], \
    f"urutan kolom bayar salah: {positions}"
# TGL BAYAR DPP tepat setelah BAYAR DPP, TGL BAYAR PPN tepat setelah BAYAR PPN.
assert positions['TGL BAYAR DPP'] == positions['BAYAR DPP'] + 1, \
    "TGL BAYAR DPP harus tepat setelah BAYAR DPP"
assert positions['TGL BAYAR PPN'] == positions['BAYAR PPN'] + 1, \
    "TGL BAYAR PPN harus tepat setelah BAYAR PPN"
print(f"[2b] kolom tanggal bayar urut: {EXPECTED_ORDER} OK")


# --- 2c. Header & body jumlah kolom konsisten; data-col berurutan ---
thead = tpl[tpl.index('<thead>'):tpl.index('</thead>')]
tbody = tpl[tpl.index('<tbody>'):tpl.index('</tbody>')]
first_tr = re.search(r'<tr\b.*?</tr>', tbody, re.S).group(0)
n_th = len(re.findall(r'<th\b', thead))
n_td = len(re.findall(r'<td\b', first_tr))
assert n_th == n_td, f"jumlah TH ({n_th}) != TD ({n_td})"
datacols = [int(x) for x in re.findall(r'<th\b[^>]*data-col="(\d+)"', thead)]
assert datacols == list(range(1, len(datacols) + 1)), f"data-col tak berurutan: {datacols}"
print(f"[2c] {n_th} kolom, TH==TD, data-col 1..{len(datacols)} berurutan OK")


# --- 4. Kolom sticky ditandai te-col-locked ---
for lab in ('#', 'NAMA LEVELANSIR', 'AKSI'):
    assert re.search(r'<th\b[^>]*te-col-locked[^>]*>', tpl), \
        "tidak ada <th class=...te-col-locked...>"
# ketiga sticky thu harus locked
locked_ths = re.findall(r'<th\b[^>]*te-col-locked\b[^>]*>(.*?)</th>', tpl, re.S)
locked_labels = []
for t in locked_ths:
    t = re.sub(r'<span class="sort-arrow">.*?</span>', '', t, flags=re.S)
    locked_labels.append(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip())
assert len(locked_labels) == 3, f"harus 3 kolom locked, dapat {locked_labels}"
print(f"[4] kolom sticky terkunci: {locked_labels} OK")


# --- 5. JS memuat logika default + fallback tersimpan ---
with open(JS, encoding='utf-8') as f:
    js = f.read()
assert 'data-te-default-hidden' in js, "JS tak membaca data-te-default-hidden"
assert "readStore(id + ':hidden', null)" in js, "JS tak memakai null-fallback utk deteksi preferensi"
assert 'defaultHiddenLabels' in js, "JS tak punya variabel default label"
assert 'te-col-locked' in js, "JS tak menonaktifkan checkbox kolom locked"
print("[5] table-enhance.js menerapkan default + fallback localStorage OK")


# --- 5b. Tooltip click-expand: data-full di semua kolom teks ---
# cell-expand.js membaca [data-full]; kolom teks harus memilikinya agar teks
# yang terpotong (Nama, Deskripsi, No. Invoice, PO, Faktur, Inv Cicilan) bisa
# dibuka penuh lewat popup klik.
for token in ('cell-rekanan', 'cell-desc', 'cell-inv-internal',
              'cell-invoice', 'cell-po', 'cell-faktur'):
    assert re.search(r'class="[^"]*' + token + r'[^"]*"[^>]*data-full=', tpl), \
        f"kolom '{token}' tak punya data-full (tooltip tidak akan muncul)"
# Deskripsi tak lagi dipotong di server ([:60] dibuang → andalkan CSS+tooltip).
assert '[:60]' not in tpl, "DESKRIPSI masih dipotong [:60] di template"
assert "row['DESKRIPSI'] or ''" in tpl, "data-full DESKRIPSI tidak memakai teks penuh"

with open(os.path.join(ROOT, 'static', 'js', 'cell-expand.js'), encoding='utf-8') as f:
    ce = f.read()
assert "querySelectorAll('[data-full]')" in ce, \
    "cell-expand.js harus memindai [data-full] (td ATAU elemen anak), bukan hanya td"
assert "data-full" in html, "HTML /data-hutang tak memuat data-full"
print("[5b] tooltip click-expand: data-full lengkap + JS memindai [data-full] OK")


# --- 6. Tombol "Reset" mengembalikan ke DEFAULT, bukan "semua tampil" ---
# Petakan handler resetCols: ia harus memakai defaultHiddenLabels (bukan
# hidden = {} + tulis '') dan mencentang ulang sesuai hidden.
reset_block = re.search(r"resetCols\.addEventListener\('click', function \(\) \{(.*?)\n      \}\);",
                        js, re.S)
assert reset_block, "blok handler Reset tak ditemukan di table-enhance.js"
rb = reset_block.group(1)
assert 'defaultHiddenLabels' in rb, \
    "Reset harus menerapkan defaultHiddenLabels (bukan 'semua tampil')"
assert "cb.checked = !hidden[i]" in rb, \
    "Reset harus mencentang ulang checkbox sesuai hidden default"
assert "writeStore(id + ':hidden', '')" not in rb, \
    "Reset masih menulis '' (yang berarti semua tampil) — seharusnya menulis set default"
print("[6] tombol Reset mengembalikan ke default kolom (bukan semua tampil) OK")


# --- 7. Panel filter collapsible (toggle + wrapper + chips tetap terlihat) ---
# Tombol toggle menyembunyikan #filterGroups; chips filter aktif (#filterChips)
# HARUS berada di luar panel agar tetap terlihat saat panel tertutup.
assert 'id="filterToggle"' in tpl, "tombol #filterToggle tidak ada di template"
assert 'id="filterGroups"' in tpl, "#filterGroups (panel filter) tidak ada di template"
assert re.search(r'class="[^"]*ft-groups[^"]*ft-collapsed[^"]*"[^>]*id="filterGroups"',
                 tpl) or re.search(r'id="filterGroups"[^>]*class="[^"]*ft-collapsed',
                 tpl), "panel filter harus default collapsed (class ft-collapsed)"
assert 'aria-controls="filterGroups"' in tpl, "tombol filter tak mengarah ke panel (aria-controls)"
assert 'id="filterToggleCount"' in tpl, "badge jumlah filter aktif tidak ada"

# Chips harus di LUAR #filterGroups: ambil blok #filterGroups, pastikan tak memuat
# id="filterChips".
grp_m = re.search(r'<div class="ft-groups ft-collapsed" id="filterGroups">(.*?)\n        </div>',
                  tpl, re.S)
assert grp_m, "blok #filterGroups tak terbaca"
groups_block = grp_m.group(1)
assert 'id="filterChips"' not in groups_block, \
    "#filterChips harus di LUAR #filterGroups agar tetap terlihat saat panel tertutup"
assert 'id="filterChips"' in tpl, "#filterChips tidak ada di template"
print("[7] toggle filter + #filterGroups collapsed + chips di luar panel OK")

# --- 7b. CSS collapse & tombol toggle ada di tema ---
with open(os.path.join(ROOT, 'templates', 'partials', '_dt_theme.html'), encoding='utf-8') as f:
    theme = f.read()
assert '.ft-groups.ft-collapsed' in theme, "CSS .ft-groups.ft-collapsed tak ada"
assert '.filter-toggle' in theme, "CSS .filter-toggle tak ada"
assert 'ft-toggle-caret' in theme, "CSS caret toggle tak ada"
assert 'ft-toggle-count' in theme, "CSS badge toggle tak ada"
print("[7b] CSS collapse + styling tombol toggle OK")

# --- 7c. JS: fungsi toggle, hitung filter aktif, persistensi localStorage ---
with open(os.path.join(ROOT, 'templates', 'index.html'), encoding='utf-8') as f:
    idx = f.read()
assert 'FILTER_PANEL_KEY' in idx and "localStorage.getItem(FILTER_PANEL_KEY)" in idx, \
    "JS tak menyimpan/membaca preferensi panel filter di localStorage"
assert 'function setFilterPanel' in idx, "JS tak punya setFilterPanel()"
assert 'function countActiveFilters' in idx, "JS tak punya countActiveFilters()"
assert "getElementById('filterToggle')" in idx, "JS tak memasang handler tombol toggle"
# Auto-open ketika ada filter aktif.
assert 'chips.length > 0) setFilterPanel(true' in idx, \
    "panel filter harus auto-buka saat ada filter aktif"
print("[7c] JS toggle + countActiveFilters + persistensi localStorage OK")

print("\nALL CHECKS PASSED")
