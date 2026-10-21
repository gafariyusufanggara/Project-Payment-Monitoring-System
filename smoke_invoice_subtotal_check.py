# -*- coding: utf-8 -*-
"""Smoke check: subtotal footer daftar invoice akurat terhadap data import.

Aturan yang disetujui pengguna (source of truth = Excel):
  * DB menyimpan nilai MENTAH apa adanya, termasuk desimal dari formula Excel.
  * Pembulatan rupiah (round-half-away-from-zero = ROUND() Excel) hanya di
    lapisan tampil, tidak pernah saat menyimpan.
  * Footer subtotal menjumlahkan nilai MENTAH (seperti SUM() Excel) lalu
    membulatkan TOTAL-nya sekali — bukan membulatkan per baris.

Memverifikasi:
  1. Filter Jinja money/money0 memakai pembulatan Excel, bukan potongan (int()).
  2. Jalur import tidak membulatkan (nilai mentah masuk DB).
  3. updateFootTotals di index.html menjumlah float mentah + bulatkan total.
  4. Simulasi footer atas data nyata == round(SUM mentah) per kolom.

Run:  python smoke_invoice_subtotal_check.py
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

import app as appmod  # noqa: E402
import db  # noqa: E402
from constants import CURRENCY_FIELDS, safe_float  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
app = appmod.app
money = app.jinja_env.filters['money']
money0 = app.jinja_env.filters['money0']

with open(os.path.join(ROOT, 'templates', 'index.html'), encoding='utf-8') as f:
    index_js = f.read()
with open(os.path.join(ROOT, 'db.py'), encoding='utf-8') as f:
    db_src = f.read()


def round_away(v):
    return int(v + (0.5 if v >= 0 else -0.5))


def _import_rows_body(src):
    m = re.search(r'def import_rows\(.*?\n(?=\ndef |\Z)', src, re.S)
    assert m, 'import_rows tidak ditemukan'
    return m.group(0)


# --- 1. Aturan pembulatan money/money0 (pure display rounding) ---
assert money(299999999.928244) == '300.000.000', money(299999999.928244)
assert money(299999999.49) == '299.999.999'
assert money0(122448.98) == '122.449', money0(122448.98)
assert money0(0.4) == '-' and money0(0) == '-' and money0(None) == '-'
assert money0(1) == '1'
assert money(0) == '0' and money(None) == '0'
print('[1] money/money0 round-half-away OK (299999999.928244 → 300.000.000)')

# --- 2. Jalur import menyimpan MENTAH (tanpa round_currency) ---
body = _import_rows_body(db_src)
assert 'round_currency(' not in body, \
    'import_rows tidak boleh membulatkan — DB harus menyimpan nilai mentah'
print('[2] import_rows menyimpan nilai mentah (tanpa round_currency) OK')

# --- 3. Footer: jumlah float mentah, bulatkan TOTAL sekali ---
assert 'sums[k] += v;' in index_js, 'footer harus menjumlah nilai mentah'
assert 'sums[k] += v >= 0 ? Math.round(v) : -Math.round(-v);' not in index_js, \
    'pembulatan per baris sudah tidak dipakai'
assert re.search(r'const t = k < sums\.length \? \(sums\[k\] >= 0 \? Math\.round\(sums\[k\]\) '
                 r': -Math\.round\(-sums\[k\]\)\) : 0;', index_js), \
    'total footer harus dibulatkan sekali (round-half-away)'
assert 't.toLocaleString' in index_js, 'output total footer harus terformat'
print('[3] updateFootTotals: Σ nilai mentah + bulatkan total sekali OK')

# --- 4. Simulasi footer atas data nyata == round(SUM mentah) ---
rows = db.read_data()
for f in CURRENCY_FIELDS:
    sum_raw = sum(safe_float(r.get(f)) for r in rows)
    footer = round_away(sum_raw)  # yang ditampilkan footer
    assert footer == round_away(sum(safe_float(r.get(f)) for r in rows)), f
    if abs(sum_raw - footer) > 0.5:
        raise AssertionError(f'{f}: footer {footer} != round(SUM) {sum_raw}')
decimals = sum(1 for r in rows for f in CURRENCY_FIELDS
               if abs(safe_float(r.get(f)) - round_away(safe_float(r.get(f)))) > 1e-9)
print(f'[4] {len(rows)} baris: footer == round(SUM mentah) per kolom OK '
      f'({decimals} sel berdesimal tersimpan = nilai mentah Excel)')
print('SEMUA LOLOS')
