"""smoke_jt_sisa_check.py — Regression: sisa Jatuh Tempo = per-invoice net clamp.

Memverifikasi:
  1. Overpay satu invoice TIDAK menutupi hutang invoice lain (bukan vendor-net).
  2. Pembayaran terpisah di baris duplikat (rekan, invoice) sama dijumlah →
     sisa 0 dan hanya 1 entri invoice (modal tidak dobel).
  3. Integritas data nyata: KPI == aging == jumlah modal per bulan, dan
     overdue == Σ bucket 1-30..>90.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db  # noqa: E402
from services.laporan import build_jatuh_tempo_data  # noqa: E402


def _row(rekan, inv, harga, dp, jth, internal):
    return {
        'NAMA LEVELANSIR / REKANAN': rekan,
        'NO INVOICE': inv,
        'NO INVOICE INTERNAL': internal,
        'HARGA (EXLD)': harga,
        'PEMBAYARAN DPP': dp,
        'TOTAL (INCLD)': harga,
        'PPN': 0,
        'POT. PPH': 0,
        'JTH TEMPO': jth,
        'TGL TERIMA': '2026-01-01',
        'TGL BAYAR DPP': '2026-01-01' if dp else '',
        'KATEGORI': '',
    }


_orig_read = db.read_data
try:
    db.read_data = lambda project_id=None: [
        _row('R', 'INV-A', 100, 150, '2030-01-01', 'A'),
        _row('R', 'INV-B', 100, 0, '2030-01-01', 'B'),
    ]
    rows, _ = build_jatuh_tempo_data(project_id='all')
    sec = rows[-1]
    s = sec['rekanan_list'][0]
    assert s['sisa_dpp'] == 100, f"harus 100 (per-invoice), dapat {s['sisa_dpp']}"
    assert s['total_dpp'] == 200 and s['bayar_dpp'] == 150, "nominal hutang/bayar rekanan salah"
    assert sec['aging']['belum_jt'] == 100, "aging belum_jt harus 100"
    assert sec['overdue_sisa'] == 0, "belum jatuh tempo → overdue harus 0"
    print("[1] overpay satu invoice tidak menutupi hutang invoice lain OK")

    db.read_data = lambda project_id=None: [
        _row('S', 'INV-C', 100, 0, '2020-01-01', 'C'),
        _row('S', 'INV-C', 100, 100, '2020-01-01', 'C'),
    ]
    rows, _ = build_jatuh_tempo_data(project_id='all')
    s = rows[-1]['rekanan_list'][0]
    assert len(s['invoices']) == 1, f"harus 1 entri invoice, dapat {len(s['invoices'])}"
    assert s['sisa_dpp'] == 0, f"lunas → sisa 0, dapat {s['sisa_dpp']}"
    assert s['count'] == 0, "invoice lunas tidak boleh dihitung sebagai Invoice JT"
    print("[2] bayar di baris duplikat dijumlah + entri invoice tunggal OK")
finally:
    db.read_data = _orig_read

rows, _ = build_jatuh_tempo_data(project_id='all')
for r in rows:
    kpi = sum(s['sisa_dpp'] for s in r['rekanan_list'])
    aging = sum(r['aging'].values())
    modal = sum(max(0, i['harga_excl'] - i['bayar_dpp'])
                for s in r['rekanan_list'] for i in s['invoices'])
    overdue = sum(r['aging'][k] for k in ('d1_30', 'd31_60', 'd61_90', 'd90plus'))
    assert round(kpi) == round(aging) == round(modal), \
        f"{r['key']}: KPI/aging/modal beda ({kpi}/{aging}/{modal})"
    assert round(overdue) == round(r['overdue_sisa']), \
        f"{r['key']}: overdue != SUM bucket ({overdue}/{r['overdue_sisa']})"
print(f"[3] integritas {len(rows)} bulan: KPI == aging == modal, overdue == SUM bucket OK")

# [4] Strip tunggakan PERIODE LALU: total & count = invoice JTH lewat hanya
#     untuk bulan < bulan berjalan (bulan berjalan tidak dihitung).
from pathlib import Path as _P
from datetime import date as _date
_nowk = _date.today().strftime('%Y-%m')
_tpl = (_P(__file__).with_name('templates') / 'laporan_jatuh_tempo.html').read_text(encoding='utf-8')
assert 'lp-jt-alert' in _tpl and 'selectMonth' in _tpl, "strip tunggakan tidak ada di template"
_past = [r for r in rows if r['key'] < _nowk]
_ov_total = sum(r['overdue_sisa'] for r in _past)
_ov_cnt = sum(r['overdue_count'] for r in _past)
_ov_exp = sum(1 for r in _past for s in r['rekanan_list']
              for i in s['invoices'] if i['sisa_dpp'] > 0 and i['hari_lebih'] > 0)
assert _ov_cnt == _ov_exp, f"overdue_count != jumlah invoice telat ({_ov_cnt}/{_ov_exp})"
_nmonths = sum(1 for r in _past if r['overdue_sisa'] > 0)
print(f"[4] strip tunggakan periode lalu: {_ov_total} · {_ov_cnt} invoice di {_nmonths} bulan OK")

print("\nALL CHECKS PASSED")
