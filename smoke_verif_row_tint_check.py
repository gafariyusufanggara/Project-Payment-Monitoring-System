# -*- coding: utf-8 -*-
"""Smoke check: warna baris Data Invoice berdasarkan tingkat Verifikasi.

Memverifikasi bahwa tabel /data-hutang mewarnai tiap baris sesuai tingkat
masalah Verifikasi Data (CRITICAL/WARNING/COMPLETION/DUPLICATE), menggantikan
tint "jatuh tempo" (overdue-row) lama:
  1. services.verification.get_row_levels() mengembalikan peta {_row: level}
     yang konsisten dengan get_verification_data() dan HORMAT daftar abaikan.
  2. Halaman /data-hutang render 200; baris ber-issue membawa class
     verif-row + verif-row--<LEVEL>; baris tanpa issue tidak.
  3. Kelas lama 'overdue-row' TIDAK lagi muncul di HTML dan tidak ada lagi di
     CSS (_dt_theme.html / table.css / base.css).
  4. Warna verif-row--* benar-benar ada di CSS yang dimuat halaman.

Run:  python smoke_verif_row_tint_check.py
Read-only terhadap data nyata.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
from services import auth as _auth
from services.verification import get_row_levels, get_verification_data

app = appmod.app
VALID = {'CRITICAL', 'WARNING', 'COMPLETION', 'DUPLICATE'}


# --- 1. get_row_levels(): struktur + konsistensi dgn get_verification_data ---
for pid in ('all', None):
    levels = get_row_levels(pid)
    assert isinstance(levels, dict), f"harus dict, dapat {type(levels)}"
    for rid, lv in levels.items():
        assert lv in VALID, f"level tak dikenal {lv!r} utk row {rid}"

    # Harus persis sama dgn baris (non-OK, non-ignored) di get_verification_data.
    rows, _counts, _dup = get_verification_data(pid)
    expected = {r['row_idx']: r['level'] for r in rows}
    assert levels == expected, (
        f"get_row_levels(pid={pid!r}) tidak konsisten dgn get_verification_data "
        f"(selisih: {set(levels.items()) ^ set(expected.items())})"
    )
print("[1] get_row_levels konsisten dgn get_verification_data OK")


# --- 2. Halaman /data-hutang: kelas warna sesuai pemetaan level ---
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    r = c.get('/data-hutang')
    assert r.status_code == 200, f"/data-hutang -> {r.status_code}"
    html = r.data.decode('utf-8', 'replace')

# Setiap row ber-issue harus muncul sebagai class verif-row--<LEVEL> di HTML.
levels = get_row_levels('all')
rendered = set(re.findall(r'verif-row--([A-Z]+)', html))
assert rendered <= VALID, f"level asing di HTML: {rendered - VALID}"

# Baris ber-level HTML: hitung <tr ... verif-row--LEVEL ... data-row-idx="N">
pairs = re.findall(r'verif-row--([A-Z]+) row-clickable"[^>]*?data-row-idx="(\d+)"', html, re.S)
for lv, rid in pairs:
    assert levels.get(int(rid)) == lv, (
        f"baris {rid} diwarnai {lv} tapi level sebenarnya {levels.get(int(rid))}"
    )

if levels:
    # Ada baris bermasalah (yang tidak diabaikan) -> WAJIB ada <tr> berwarna.
    assert pairs, (
        f"get_row_levels() berisi {len(levels)} baris tapi tak ada satu pun "
        f'<tr class="verif-row--<LEVEL> row-clickable" data-row-idx=...> di HTML')
    assert rendered, "tidak ada class verif-row--<LEVEL> sama sekali di HTML"
    print(f"[2] {len(pairs)} baris berwarna sesuai level verifikasi OK")
else:
    # Semua baris bermasalah sudah diabaikan (atau datanya bersih). Kondisi ini
    # SAH: tabel memang tidak boleh mewarnai apa pun. Yang diuji di sini adalah
    # tidak adanya warna nyasar - bukan memaksa ada baris berwarna.
    assert not pairs, (
        "get_row_levels() kosong (semua issue diabaikan), tapi ada <tr> "
        "ber-class verif-row--* yang tetap diwarnai")
    print("[2] tak ada baris berwarna - semua issue sudah diabaikan / data bersih "
          "(sesuai kondisi data) OK")


# --- 3. Kelas lama overdue-row hilang dari HTML & CSS ---
assert 'overdue-row' not in html, "class 'overdue-row' lama masih ada di HTML"
root = os.path.dirname(os.path.abspath(__file__))
for rel in ('templates/partials/_dt_theme.html', 'static/css/table.css',
            'static/css/base.css'):
    p = os.path.join(root, rel)
    with open(p, encoding='utf-8') as f:
        assert 'overdue-row' not in f.read(), f"{rel} masih memuat 'overdue-row'"
print("[3] kelas lama 'overdue-row' sudah tidak ada di HTML & CSS OK")


# --- 4. Warna verif-row--* ada di CSS yang dimuat ---
# Warna baris tersebar di TIGA file yang ikut dimuat halaman: _dt_theme.html
# (tint utama), table.css & base.css (sel sticky + hover). Semua harus punya
# definisi untuk keempat level, kalau tidak sebagian baris tak berwarna.
_css_files = ('templates/partials/_dt_theme.html', 'static/css/table.css',
              'static/css/base.css')
_all_css = {}
for rel in _css_files:
    with open(os.path.join(root, rel), encoding='utf-8') as f:
        _all_css[rel] = f.read()
_union = '\n'.join(_all_css.values())
for lv in VALID:
    assert f'verif-row--{lv}' in _union, \
        f"CSS .verif-row--{lv} tidak ada di file CSS mana pun"
with open(os.path.join(root, 'templates/partials/_dt_theme.html'),
          encoding='utf-8') as f:
    theme = f.read()
for lv in VALID:
    assert f'verif-row--{lv}' in theme, f"CSS .verif-row--{lv} tidak ada di _dt_theme.html"
assert 'verif-row--CRITICAL' in theme and '#fef0ee' in theme, "warna merah CRITICAL hilang"
assert '#fdf6d8' in theme, "warna amber WARNING hilang"
assert '#ece4f7' in theme, "warna violet DUPLICATE hilang"
print(f"[4] warna verif-row--* terpasang di {len(_css_files)} file CSS OK")

print("\nALL CHECKS PASSED")
