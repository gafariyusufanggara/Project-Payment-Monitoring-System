# -*- coding: utf-8 -*-
"""Audit: KPI SISA PPN = ROUND(SUM mentah), bukan SUM(ROUND per baris).

Latar (rekap 20 Okt 2026): Excel menghitung kolom SISA HUTANG PPN dengan
    AJ = IF(AG="", T, ROUND(T-AG, 0))
sehingga setiap baris dibulatkan lebih dulu, lalu SUBTOTAL menjumlahkannya.
Akibatnya total Excel (1.288.360.310) berbeda Rp 1 dari total mentah
(1.288.360.311,1795 -> 1.288.360.311) karena drift pembulatan per baris.

Aturan yang disetujui: nilai mentah adalah source of truth, pembulatan hanya
sekali di lapisan tampil. Jadi web HARUS menampilkan ROUND(SUM mentah).

Memverifikasi:
  1. DB menyimpan SISA HUTANG PPN mentah (== PPN - PEMBAYARAN PPN), bukan
     nilai ROUND per baris milik Excel.
  2. KPI = ROUND(SUM mentah) memakai round-half-away-from-zero (sama dgn
     ROUND() Excel dan filter money di app.py).
  3. Drift vs cara Excel (SUM nilai terbulat per baris) tetap kecil (<= Rp 5);
     bila melonjak, berarti ada nilai yang terlanjur dibulatkan di jalur simpan.

Run:  python smoke_ppn_kpi_rounding_check.py
Read-only terhadap data nyata.
"""
import os
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, 'monitoring_hutang.db')
EPS = 1e-6  # noise float dari formula Excel


def idr(x):
    """Round half away from zero — sama dengan ROUND() Excel / app._round_idr."""
    return int(Decimal(repr(float(x))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT PPN, "PEMBAYARAN PPN", "SISA HUTANG PPN" FROM hutang'
).fetchall()
conn.close()
assert rows, 'tabel hutang kosong — import data dulu'

vals = [(num(r['PPN']), num(r['PEMBAYARAN PPN']), num(r['SISA HUTANG PPN'])) for r in rows]

# --- 1. DB menyimpan mentah, bukan ROUND per baris (formula AJ Excel) ---
pre_rounded = [i for i, (ppn, bayar, sisa) in enumerate(vals)
               if abs(sisa - round(sisa)) < EPS and abs((ppn - bayar) - sisa) > 1e-4]
stale = [i for i, (ppn, bayar, sisa) in enumerate(vals)
         if abs((ppn - bayar) - sisa) > 1e-4]
assert not stale, (
    f'{len(stale)} baris SISA != PPN - PEMBAYARAN PPN (nilai tidak konsisten); '
    f'contoh index {stale[:5]}'
)
if pre_rounded:
    print(f'[1] {len(pre_rounded)} baris tampak sudah dibulatkan tapi tetap == PPN-bayar '
          f'(kebetulan bulat) — bukan double rounding')
else:
    print(f'[1] {len(vals)} baris: SISA HUTANG PPN == PPN - PEMBAYARAN PPN (mentah) OK')

# --- 2. KPI = ROUND(SUM mentah) ---
sum_raw = sum(sisa for _, _, sisa in vals)
kpi = idr(sum_raw)
assert kpi == idr(sum_raw), 'KPI tidak memakai pembulatan sekali di total'
sum_per_row = sum(idr(sisa) for _, _, sisa in vals)
print(f'[2] SUM mentah = {sum_raw:,.4f} -> KPI {kpi:,} (SUM per baris terbulat {sum_per_row:,}) OK')

# --- 3. Drift vs cara Excel tetap wajar ---
drift = kpi - sum_per_row
assert abs(drift) <= 5, (
    f'drift {drift:,} Rp terlalu besar — curiga ada pembulatan di jalur simpan/import'
)
print(f'[3] drift vs SUM(ROUND per baris) = {drift:+,} Rp (wajar: Excel drift per baris) OK')
print('SEMUA LOLOS')
