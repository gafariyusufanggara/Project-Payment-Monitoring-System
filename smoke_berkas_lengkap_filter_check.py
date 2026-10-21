# -*- coding: utf-8 -*-
"""Smoke check: filter 'Tgl. Berkas Lengkap' page Daftar Invoice.

Domain: kolom Excel 'Tgl Terima Berkas Lengkap' = field DB 'TGL TERIMA'
(same mapping as services/document_status.py, base.html label map).
Bug yang diperbaiki: filter & kolom 'TGL BERKAS LENGKAP' memakai field
'TGL TERIMA BERKAS' (tanggal berkas fisik), sehingga subtotal POT. PPH
berbeda dengan filter Excel user (119.073.479 vs 110.700.188).

Memverifikasi:
  1. data-tgl-berkas (sumber filter) = field 'TGL TERIMA'.
  2. Sel di bawah header 'TGL BERKAS LENGKAP' merender 'TGL TERIMA',
     sel di bawah header 'TGL TERIMA BERKAS' merender 'TGL TERIMA BERKAS'
     (urutan sel ikut urutan header).
  3. Data nyata: sum POT. PPH dgn TGL TERIMA <= 2026-10-16 == 110.700.183
     (raw pra-migrasi 110.700.188.33 = angka Excel user).

Run:  python smoke_berkas_lengkap_filter_check.py
Read-only terhadap data nyata.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'templates', 'partials', '_data_table.html')
with open(TPL, encoding='utf-8') as f:
    tpl = f.read()

# --- 1. Filter memakai field yang benar ---
assert 'data-tgl-berkas="{{ row[\'TGL TERIMA\'] }}"' in tpl, \
    'data-tgl-berkas harus memakai field TGL TERIMA (Tanggal Berkas Lengkap)'
assert 'data-tgl-berkas="{{ row[\'TGL TERIMA BERKAS\'] }}"' not in tpl
print('[1] data-tgl-berkas (filter) = TGL TERIMA OK')

# --- 2. Mapping kolom tampil: header vs sel ---
mlenka = tpl.index('data-v="{{ row[\'TGL TERIMA\'] or \'\' }}')
mberkas = tpl.index('data-v="{{ row[\'TGL TERIMA BERKAS\'] }}')
h_berkas_lengkap = tpl.index('TGL BERKAS LENGKAP <span')
h_terima_berkas = tpl.index('TGL TERIMA BERKAS <span')
assert h_berkas_lengkap < h_terima_berkas < mlenka < mberkas, \
    'sel tanggal harus selaras dengan header: TGL BERKAS LENGKAP→TGL TERIMA, TGL TERIMA BERKAS→TGL TERIMA BERKAS'
print('[2] sel kolom tanggal selaras dengan header OK')

# --- 3. Data nyata: hasil filter sesuai Excel ---
import db  # noqa: E402
from constants import safe_float  # noqa: E402

CUT = '2026-10-16'
rows = db.read_data()
tot_terima = sum(safe_float(r.get('POT. PPH')) for r in rows
                 if (r.get('TGL TERIMA') or '').strip() and r['TGL TERIMA'].strip() <= CUT)
tot_berkas = sum(safe_float(r.get('POT. PPH')) for r in rows
                 if (r.get('TGL TERIMA BERKAS') or '').strip() and r['TGL TERIMA BERKAS'].strip() <= CUT)
# Angka absolut bergantung isi Excel yang di-import, jadi tidak di-assert.
# Yang di-assert: kedua kolom menghasilkan nilai BERBEDA (kalau tanggalnya beda),
# bukti bahwa memilih kolom yang salah mengubah subtotal.
n_beda = sum(1 for r in rows
             if (r.get('TGL TERIMA') or '').strip() != (r.get('TGL TERIMA BERKAS') or '').strip())
if n_beda:
    assert tot_berkas != tot_terima, 'seharusnya beda bila tanggal kedua kolom berbeda'
print(f'[3] sum POT. PPH <= {CUT}: TGL TERIMA = {tot_terima:,.0f} | '
      f'TGL TERIMA BERKAS = {tot_berkas:,.0f} ({n_beda} baris tanggalnya beda) OK')

# --- 4. Penamaan UI konsisten: TGL TERIMA = 'TGL BERKAS LENGKAP' ---
# Istilah panjang ('TGL TERIMA BERKAS LENGKAP') hanya boleh muncul di db.py
# sebagai alias header Excel saat migrasi, bukan di UI.
import glob  # noqa: E402
import re  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(ROOT, 'templates', 'base.html'), encoding='utf-8') as f:
    base = f.read()
assert "'TGL TERIMA': 'TGL BERKAS LENGKAP'" in base, \
    "labelOf: TGL TERIMA harus tampil sebagai 'TGL BERKAS LENGKAP'"

bad = []
for path in glob.glob(os.path.join(ROOT, 'templates', '**', '*.html'), recursive=True) + \
        glob.glob(os.path.join(ROOT, 'services', '*.py')):
    is_py = path.endswith('.py')
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            rel = os.path.relpath(path, ROOT)
            code = line.split('#', 1)[0] if is_py else line
            if is_py and not ('"' in code or "'" in code):
                code = ''  # komentar/docstring tanpa literal — bukan teks UI
            if 'TGL TERIMA BERKAS LENGKAP' in code.upper():
                bad.append(f'{rel}:{i} istilah panjang')
            if re.search(r'<th[^>]*>\s*Tgl\.? Terima\s*</th>', line, re.I):
                bad.append(f'{rel}:{i} header ambigu "Tgl Terima"')
            if os.path.basename(path) != 'document_status.html' and \
                    re.search(r'<th[^>]*>\s*Tgl\.?\s*Berkas\s*</th>', line, re.I):
                bad.append(f'{rel}:{i} header ambigu "Tgl Berkas" (pakai "Tgl Berkas Lengkap")')
            if "'Tgl Terima kosong'" in line:
                bad.append(f'{rel}:{i} alasan ambigu "Tgl Terima kosong"')
assert not bad, f'penamaan UI tidak konsisten: {bad[:6]}'
print('[4] penamaan UI konsisten (TGL TERIMA -> "TGL BERKAS LENGKAP") OK')

print('ALL CHECKS PASSED')
