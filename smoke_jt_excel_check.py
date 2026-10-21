"""smoke_jt_excel_check.py — Struktur export Excel Jatuh Tempo.

Memverifikasi layout standar Rekap: judul di baris 4, header baris 5-6,
baris 7 kosong, data mulai C8, label kolom sesuai UI, tanggal Excel,
format angka accounting, dan total yang konsisten.
"""

import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402
from services import jt_excel  # noqa: E402

FIXTURE = [{
    'key': '2026-10',
    'label': 'Oktober 2026',
    'rekanan_list': [{
        'rekanan': 'PT ALPHA',
        'count': 2,
        'total_dpp': 1000.0,
        'bayar_dpp': 200.0,
        'sisa_dpp': 800.0,
        'status_key': 'overdue',
        'status_label': 'Telat +5 hari',
        'invoices': [
            {
                'tgl_berkas': '2026-09-01', 'invoice': 'INV-001', 'po': 'PO-1',
                'jth_tempo': '2026-10-01', 'deskripsi': 'Barang A',
                'harga_excl': 600.0, 'ppn': 66.0, 'pot_pph': 6.0,
                'tgl_bayar_dpp': '', 'bayar_dpp': 0.0,
                'status_key': 'overdue', 'status_label': 'Telat +5 hari',
            },
            {
                'tgl_berkas': '2026-09-02', 'invoice': 'INV-002', 'po': 'PO-2',
                'jth_tempo': '2026-10-10', 'deskripsi': 'Barang B',
                'harga_excl': 400.0, 'ppn': 44.0, 'pot_pph': 4.0,
                'tgl_bayar_dpp': '2026-10-05', 'bayar_dpp': 200.0,
                'status_key': 'paid_late', 'status_label': 'Lunas Telat +1 hari',
            },
        ],
    }],
}]

# Aging is derived server-side (hari_lebih + bucket), so fill it through the
# REAL helper rather than hardcoding — the test then fails with the helper.
from services.laporan import jt_aging_bucket as _bucket  # noqa: E402

for _v in FIXTURE[0]['rekanan_list']:
    for _inv in _v['invoices']:
        _inv['hari_lebih'] = 45          # keduanya lewat jatuh tempo -> 31-60
        _inv['aging_bucket'] = _bucket(_inv['hari_lebih'])

_orig = jt_excel.build_jatuh_tempo_data
try:
    jt_excel.build_jatuh_tempo_data = lambda project_id=None: (FIXTURE, 2)
    buf = jt_excel.build_jt_excel(month_key='2026-10')
finally:
    jt_excel.build_jatuh_tempo_data = _orig

ws = openpyxl.load_workbook(io.BytesIO(buf.getvalue())).active
merged = {str(r) for r in ws.merged_cells.ranges}

assert ws['C4'].value == 'LAPORAN JATUH TEMPO — Oktober 2026', ws['C4'].value
assert 'C4:T4' in merged, merged
assert ws.max_column == 20, ws.max_column
assert all(ws.cell(7, c).value is None for c in range(3, 21)), 'baris 7 harus kosong'

headers = {
    'C5': 'No.', 'D5': 'Levelansir / Rekanan', 'E5': 'Data Invoice',
    'J5': 'Nilai', 'M5': 'Pembayaran', 'O5': 'Sisa Hutang DPP', 'T5': 'Status JT',
    'P5': 'Overdue',
    'E6': 'Tgl Berkas Lengkap', 'F6': 'No. Invoice', 'G6': 'PO / Kontrak',
    'H6': 'Tgl Jatuh Tempo', 'I6': 'Deskripsi', 'J6': 'Nilai DPP',
    'K6': 'PPN', 'L6': 'PPH', 'M6': 'Tgl Bayar DPP', 'N6': 'Bayar DPP',
    'P6': '1-30\nHari', 'Q6': '31-60\nHari', 'R6': '61-90\nHari', 'S6': '> 90\nHari',
}
for cell, expected in headers.items():
    assert ws[cell].value == expected, f'{cell}: {ws[cell].value!r} != {expected!r}'
assert ws['O6'].value is None and ws['T6'].value is None, 'leaf tidak boleh menimpa merge'
assert 'O5:O6' in merged and 'T5:T6' in merged, merged
assert 'P5:S5' in merged, 'overdue harus punya grup header P5:S5'
# "Due today" bukan overdue, jadi tidak boleh punya kolom sendiri.
assert 'Jatuh Tempo\nHari Ini' not in {ws.cell(6, c).value for c in range(3, 21)}, \
    'kolom "Jatuh Tempo Hari Ini" sudah dihapus'

assert ws['C8'].value == 1, ws['C8'].value
assert ws['D8'].value == 'PT ALPHA', ws['D8'].value

# Vendor row money cells are SUBTOTAL formulas over that vendor's own block,
# mirroring the DPP / PPN Rekap exports (J,K,L,N,O = Nilai,PPN,PPH,Bayar,Sisa).
assert ws['J8'].value == '=SUBTOTAL(109,J9:J10)', ws['J8'].value
assert ws['K8'].value == '=SUBTOTAL(109,K9:K10)', ws['K8'].value
assert ws['L8'].value == '=SUBTOTAL(109,L9:L10)', ws['L8'].value
assert ws['N8'].value == '=SUBTOTAL(109,N9:N10)', ws['N8'].value
assert ws['O8'].value == '=SUBTOTAL(109,O9:O10)', ws['O8'].value
# Overdue block on the vendor row aggregates its own invoice block too.
for col in ('P', 'Q', 'R', 'S'):
    assert ws[f'{col}8'].value == f'=SUBTOTAL(109,{col}9:{col}10)', (col, ws[f'{col}8'].value)

# Status JT only belongs to invoice rows. The vendor summary row carries a NO
# (nomor) and no status text, but its cell must still be shaded so the band
# colour stays continuous across the row.
assert ws['T8'].value in (None, ''), f'vendor row 8 tidak boleh berstatus: {ws["T8"].value!r}'
assert ws['T8'].fill.fgColor.rgb not in (None, '00000000'), 'T8 harus punya background'
assert ws['T9'].value == 'Telat +5 hari', ws['T9'].value
assert ws['T10'].value == 'Lunas Telat +1 hari', ws['T10'].value

# Invoice rows must be UNPAINTED: only vendor summary rows keep a band, so the
# sheet doesn't turn into a block of colour. Colour survives in the text.
for ref in ('C9', 'D9', 'E9', 'I9', 'J9', 'O9', 'P9', 'S9', 'T9'):
    assert ws[ref].fill.fgColor.rgb in (None, '00000000'), f'{ref} tidak boleh ber-background'
for ref in ('C8', 'D8', 'J8', 'P8', 'T8'):
    assert ws[ref].fill.fgColor.rgb not in (None, '00000000'), f'{ref} (vendor) harus ber-background'

# Tgl Bayar DPP has no vendor-level figure, but must keep the band shading so
# there is no unpainted gap in the vendor row.
assert ws['M8'].value in (None, ''), ws['M8'].value
assert ws['M8'].fill.fgColor.rgb not in (None, '00000000'), 'M8 harus punya background'

assert ws['E9'].value == datetime(2026, 9, 1), ws['E9'].value
assert ws['H9'].value == datetime(2026, 10, 1), ws['H9'].value
assert ws['M10'].value == datetime(2026, 10, 5), ws['M10'].value
assert ws['E9'].number_format == 'dd/mm/yyyy', ws['E9'].number_format
assert '#,##0' in ws['J9'].number_format, ws['J9'].number_format

# Detail Sisa Hutang DPP is a derived, live formula (not a frozen number).
assert ws['O9'].value == '=MAX(0,J9-N9)', ws['O9'].value
assert ws['O10'].value == '=MAX(0,J10-N10)', ws['O10'].value
assert ws['D11'].value == 'TOTAL', ws['D11'].value
assert 'D11:I11' in merged, merged

# ── Overdue block: one bucket per invoice, money == its own Sisa DPP ──
# The fixture's due dates (2026-10-01 / 2026-10-10) are long past, so both
# invoices land in a past-due bucket and must be fully bucketed.
AGE_COLS = ('P', 'Q', 'R', 'S')

for r in (9, 10):
    filled = [c for c in AGE_COLS if (ws[f'{c}{r}'].value or 0) > 0]
    assert len(filled) == 1, f'row {r}: invoice harus di tepat 1 bucket, dapat {filled}'
    expect_sisa = max(0, ws[f'J{r}'].value - ws[f'N{r}'].value)
    total = sum(ws[f'{c}{r}'].value or 0 for c in AGE_COLS)
    assert abs(total - expect_sisa) < 1, f'row {r}: bucket {total} != Sisa {expect_sisa}'

# Zero must be a real 0, not a blank: a blank cell inside the SUBTOTAL range
# would make the formula-driven totals silently disagree with the header.
assert all(isinstance(ws[f'{c}9'].value, (int, float)) for c in AGE_COLS), \
    'sel bucket harus angka 0, bukan kosong'

for col in ('J', 'K', 'L', 'N', 'O', 'P', 'Q', 'R', 'S'):
    expect = (f'=SUMPRODUCT(SUBTOTAL(103,OFFSET($C$8,'
              f'ROW($C$8:$C$8)-ROW($C$8),0)),{col}8:{col}8)')
    assert ws[f'{col}11'].value == expect, (col, ws[f'{col}11'].value)

print('JT Excel: C8, header 5-6, baris 7 kosong, label, tanggal, formula, total OK')
