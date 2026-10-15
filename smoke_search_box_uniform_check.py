# -*- coding: utf-8 -*-
"""Smoke check: kotak pencarian seragam di seluruh halaman daftar.

Memverifikasi bahwa halaman Status Dokumen, Progress Cicilan, Retensi,
Verifikasi Kelengkapan, Progress Kontrak, Catatan Audit, Data yang Diabaikan,
dan Daftar Invoice memakai markup + styling kotak pencarian yang SAMA
(partials/_search_box.html), sehingga tampilannya konsisten dengan
form pencarian Daftar Invoice.

Run:  python smoke_search_box_uniform_check.py
Read-only.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
from services import auth as authmod

app = appmod.app

# (path, penanda input id, penanda halaman/kelas unik)
PAGES = [
    ('/status-dokumen',     'dsSearch',  'ds-search'),
    ('/invoice-cicilan',    'icSearch',  'cic-toolbar'),
    ('/levelansir-retensi', 'lrSearch',  'cic-toolbar'),
    ('/verifikasi',         'vfSearch',  'vf-toolbar'),
    ('/kontrak/',           'kcSearch',  'kc-page'),
    ('/audit',              'auSearch',  'au-toolbar'),
    ('/verifikasi/ignore',  'igSearch',  'ig-toolbar'),
    ('/data-hutang',        'searchInput', 'dt-invoice'),
]

client = app.test_client()
with client.session_transaction() as s:
    s[authmod.SESSION_KEY] = True

fail = 0
for path, input_id, page_marker in PAGES:
    resp = client.get(path)
    assert resp.status_code == 200, f'{path}: HTTP {resp.status_code}'
    html = resp.get_data(as_text=True)

    # Beberapa halaman hanya menampilkan toolbar+pencarian bila ada data
    # (mis. /audit saat belum ada catatan). Deteksi keberadaan MARKUP kotak
    # (bukan sekadar CSS partial yang selalu ikut ter-render).
    has_box = re.search(r'class="[^"]*\bft-search\b', html) is not None

    checks = {
        'page marker (' + page_marker + ')': page_marker in html,
        'CSS partial (.ft-search .ft-search-clear)':
            ('.ft-search .ft-search-clear' in html) or path in ('/data-hutang',),
    }
    if has_box:
        checks['ft-search (kelas box)'] = re.search(r'class="[^"]*\bft-search\b', html)
        if input_id:
            checks['input id=' + input_id] = re.search(
                r'id="' + re.escape(input_id) + r'"', html)
        checks['tombol ft-search-clear'] = 'ft-search-clear' in html
        checks['ikon bi-x-lg'] = 'bi-x-lg' in html
        checks['hint ft-search-kbd'] = 'ft-search-kbd' in html

    for name, ok in checks.items():
        if not ok:
            print(f'  FAIL {path}: {name}')
            fail += 1

    # Tidak boleh ada sisa kelas lama `.search-clear` (tombol bulat &times;).
    if re.search(r'class="search-clear"', html):
        print(f'  FAIL {path}: masih memakai kelas lama .search-clear')
        fail += 1

print()

# 3. Dua sumber styling (invoice + partial) harus menyepakati lebar ~320-400px.
root = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(root, 'templates', 'partials', '_search_box.html'),
          encoding='utf-8') as f:
    partial = f.read()
with open(os.path.join(root, 'templates', 'partials', '_dt_theme.html'),
          encoding='utf-8') as f:
    dt = f.read()

if 'flex: 1 1 320px' in partial and 'max-width: 400px' in partial:
    print('[width] partial: flex 1 1 320px / max-width 400px OK')
else:
    print('  FAIL partial: lebar bukan 320-400px'); fail += 1

if 'max-width: 400px' in dt:
    print('[width] Daftar Invoice (_dt_theme): max-width 400px OK')
else:
    print('  FAIL _dt_theme: Daftar Invoice belum dipendekkan ke 400px'); fail += 1

# 4. Tinggi input seragam 34px di kedua sumber.
if partial.count('height: 34px') >= 1 and dt.count('height: 34px') >= 1:
    print('[height] input 34px OK di partial & invoice theme')
else:
    print('  FAIL tinggi input 34px tidak konsisten'); fail += 1

print()
if fail:
    print(f'{fail} CHECK(S) FAILED')
    sys.exit(1)
print('ALL CHECKS PASSED')
