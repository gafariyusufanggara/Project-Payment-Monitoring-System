"""smoke_rekap_date_check.py — Kolom tanggal export Rekap DPP & PPN harus
berisi datetime/serial date Excel dengan format dd/mm/yyyy (bukan string ISO).
Tidak perlu Text-to-Column.
"""

import io
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402
from services.laporan import build_excel_export  # noqa: E402
from services.laporan_ppn import build_ppn_excel_export  # noqa: E402


def _valid_date_value(v):
    """Accept either a real datetime/date object or an Excel serial integer."""
    if isinstance(v, (datetime, date)):
        return True
    if isinstance(v, int):
        # Reasonable Excel serial range: year 2000 → 43831, year 2030 → 54754
        return 30000 <= v <= 60000
    return False


def _scan_dates(ws, start_row, col_j, col_k, label):
    n_j_dt = 0
    n_k_dt = 0
    total_j = 0
    total_k = 0
    for row in range(start_row, ws.max_row + 1):
        vj = ws.cell(row, col_j).value
        vk = ws.cell(row, col_k).value
        if vj is None and vk is None:
            continue
        total_j += 1
        total_k += 1
        if vj is not None:
            assert _valid_date_value(vj), (
                f'{label} R{row} C{col_j} expected date value, got {type(vj).__name__}: {vj!r}')
            fmt = ws.cell(row, col_j).number_format
            assert fmt == 'dd/mm/yyyy', f'{label} R{row} C{col_j} format={fmt!r}'
            n_j_dt += 1
        if vk is not None:
            assert _valid_date_value(vk), (
                f'{label} R{row} C{col_k} expected date value, got {type(vk).__name__}: {vk!r}')
            fmt = ws.cell(row, col_k).number_format
            assert fmt == 'dd/mm/yyyy', f'{label} R{row} C{col_k} format={fmt!r}'
            n_k_dt += 1
    return n_j_dt, n_k_dt, total_j, total_k


# --- DPP Rekap ---
buf = build_excel_export()
ws = openpyxl.load_workbook(io.BytesIO(buf.getvalue())).active
# J=10 (Tgl Berkas Lengkap), K=11 (Tgl Jatuh Tempo)
n_j, n_k, t_j, t_k = _scan_dates(ws, 8, 10, 11, 'DPP')
assert n_j > 0, 'DPP: tidak ada tanggal di kolom TGL TERIMA (J)'
assert n_k > 0, 'DPP: tidak ada tanggal di kolom JTH TEMPO (K)'
print(f'DPP: {n_j}/{t_j} baris datetime di J (TGL TERIMA), {n_k}/{t_k} di K (JTH TEMPO) OK')

# --- PPN Rekap ---
buf = build_ppn_excel_export()
ws = openpyxl.load_workbook(io.BytesIO(buf.getvalue())).active
# J=10 (Tgl Berkas Lengkap), K=11 (Tgl Faktur Pajak)
n_j, n_k, t_j, t_k = _scan_dates(ws, 8, 10, 11, 'PPN')
assert n_j > 0, 'PPN: tidak ada tanggal di kolom TGL TERIMA (J)'
assert n_k > 0, 'PPN: tidak ada tanggal di kolom TGL FAKTUR PAJAK (K)'
print(f'PPN: {n_j}/{t_j} baris datetime di J (TGL TERIMA), {n_k}/{t_k} di K (TGL FAKTUR PAJAK) OK')

print('Rekap date check: PASS')
