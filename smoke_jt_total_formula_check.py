"""smoke_jt_total_formula_check.py — Akurasi nominal formula Excel Jatuh Tempo.

Bukan sekadar cek "ada rumus": file ini MENGEVALUASI setiap formula di sheet
(vendor SUBTOTAL, detail MAX, TOTAL SUMPRODUCT) lalu membandingkan hasilnya
dengan angka yang dihitung Python dari data sumber. Jadi kalau nominalnya
ngaco (anchor salah, range bergeser, kolom ketuker, clamp hilang), test gagal.

Yang diverifikasi:
  [1] Pola formula: anchor TOTAL $C$8 absolut, range nilai relatif.
  [2] Detail O = MAX(0,J-N)  ->  nilainya == max(0, harga_excl - bayar_dpp).
  [3] Vendor J..O SUBTOTAL(109) rentangnya == blok invoice vendor itu sendiri.
  [4] Nilai vendor row hasil evaluasi == sum() detail blok tersebut.
  [5] Nilai TOTAL hasil evaluasi == jumlah vendor row (tidak double-count).
  [6] Simulasi geser 1 kolom: anchor tetap $C$8, range nilai ikut pindah.
  [7] Tidak ada #REF!/#NAME?/None di sel numerik.
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from services import jt_excel  # noqa: E402

HUTANG, PPN, PPH, BAYAR, SISA = 'J', 'K', 'L', 'N', 'O'
MONEY_COLS = (HUTANG, PPN, PPH, BAYAR, SISA)


# ── Fixture: 3 vendor dengan bentuk berbeda (multi-invoice, single, overpay) ──
def _inv(inv, hx, ppn, pph, bayar, berkas='2026-09-01', jth='2026-10-01',
         desk='Brg', status='overdue'):
    return {
        'tgl_berkas': berkas, 'invoice': inv, 'po': 'PO-' + inv,
        'jth_tempo': jth, 'deskripsi': desk,
        'harga_excl': hx, 'ppn': ppn, 'pot_pph': pph,
        'bayar_dpp': bayar, 'tgl_bayar_dpp': '2026-10-05' if bayar else '',
        'status_key': status, 'status_label': 'Telat +5 hari',
    }


FIXTURE = [{
    'key': '2026-10',
    'label': 'Oktober 2026',
    'rekanan_list': [
        {   # 2 invoice — blok invoice baris 9-10
            'rekanan': 'PT ALPHA', 'count': 2,
            'total_dpp': 1000.0, 'bayar_dpp': 200.0, 'sisa_dpp': 800.0,
            'status_key': 'overdue', 'status_label': 'Telat +5 hari',
            'invoices': [
                _inv('INV-001', 600.0, 66.0, 6.0, 0.0),
                _inv('INV-002', 400.0, 44.0, 4.0, 200.0, status='paid_late'),
            ],
        },
        {   # 1 invoice — blok baris 12 (vendor row 11)
            'rekanan': 'CV BETA', 'count': 1,
            'total_dpp': 2500.0, 'bayar_dpp': 2500.0, 'sisa_dpp': 0.0,
            'status_key': 'paid_ok', 'status_label': 'Lunas',
            'invoices': [
                _inv('INV-003', 2500.0, 275.0, 25.0, 2500.0, status='paid_ok'),
            ],
        },
        {   # 2 invoice, salah satunya OVERPAY -> MAX clamp wajib aktif
            'rekanan': 'PT GAMMA', 'count': 2,
            'total_dpp': 1500.0, 'bayar_dpp': 1400.0, 'sisa_dpp': 200.0,
            'status_key': 'due_today', 'status_label': 'Jatuh tempo hari ini',
            'invoices': [
                _inv('INV-004', 1000.0, 110.0, 10.0, 1200.0, status='paid_late'),
                _inv('INV-005', 500.0, 55.0, 5.0, 200.0, status='overdue'),
            ],
        },
    ],
}]


_orig = jt_excel.build_jatuh_tempo_data
try:
    jt_excel.build_jatuh_tempo_data = lambda month_key=None, project_id=None: (FIXTURE, 5)
    try:
        buf = jt_excel.build_jt_excel(month_key='2026-10')
        kw = {}
    except TypeError:
        jt_excel.build_jatuh_tempo_data = lambda project_id=None: (FIXTURE, 5)
        buf = jt_excel.build_jt_excel(month_key='2026-10')
finally:
    jt_excel.build_jatuh_tempo_data = _orig

wb = openpyxl.load_workbook(io.BytesIO(buf.getvalue()))
ws = wb.active


# ── Evaluator formula minimal (cukup untuk bentuk yang kita tulis) ────────────
def _num(v):
    return 0.0 if v is None or v == '' else float(v)


def cell_value(ref):
    raw = ws[ref].value
    if not isinstance(raw, str) or not raw.startswith('='):
        return _num(raw)
    return evaluate(ref, raw)


def evaluate(ref, raw):
    f = raw[1:]

    m = re.fullmatch(r'SUBTOTAL\(109,([A-Z]+)(\d+):([A-Z]+)(\d+)\)', f)
    if m:
        c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        assert c1 == c2, f'{ref}: SUBTOTAL lintas kolom tidak diharapkan'
        col = openpyxl.utils.column_index_from_string(c1)
        return sum(cell_value(f'{c1}{r}') for r in range(r1, r2 + 1))

    m = re.fullmatch(r'MAX\(0,([A-Z]+)(\d+)-([A-Z]+)(\d+)\)', f)
    if m:
        return max(0.0, cell_value(m.group(1) + m.group(2)) - cell_value(m.group(3) + m.group(4)))

    m = re.fullmatch(
        r'SUMPRODUCT\(SUBTOTAL\(103,OFFSET\(\$([A-Z]+)\$(\d+),'
        r'ROW\(\$\1\$\d+:\$\1\$(\d+)\)-ROW\(\$\1\$\d+\),0\)\),'
        r'([A-Z]+)(\d+):([A-Z]+)(\d+)\)', f)
    if m:
        anchor_c, anchor_r, rng_first = m.group(1), int(m.group(2)), None
        col, r1, col2, r2 = m.group(4), int(m.group(5)), m.group(6), int(m.group(7))
        assert col == col2, f'{ref}: range nilai lintas kolom'
        # SUBTOTAL(103, OFFSET($C$anchor, k, 0)) = 1 hanya bila sel ANCHOR pada
        # baris anchor+k terisi (COUNTA>0). Inilah yang membuat TOTAL hanya
        # menjumlah baris VENDOR (kolom C berisi nomor) dan melewati baris
        # DETAIL (kolom C kosong). Evaluator WAJIB meniru ini; kalau tidak,
        # semua baris ikut terjumlah dan nominalnya dobel.
        total = 0.0
        for r in range(r1, r2 + 1):
            k = r - anchor_r                  # offset relatif terhadap anchor
            anchor_ref = f'{anchor_c}{anchor_r + k}'
            counted = 0.0 if ws[anchor_ref].value in (None, '') else 1.0
            total += counted * cell_value(f'{col}{r}')
        return total

    raise AssertionError(f'bentuk formula tak terduga di {ref}: {raw}')


# ── Peta baris: vendor row + blok invoice-nya, dari angka Python ─────────────
expected = []          # [(vendor_row, [invoice_rows], vendor_dict)]
r = 8
for s in FIXTURE[0]['rekanan_list']:
    vrow = r
    inv_rows = list(range(vrow + 1, vrow + 1 + len(s['invoices'])))
    expected.append((vrow, inv_rows, s))
    r = inv_rows[-1] + 1 if inv_rows else vrow + 1
total_row = r

# ── [1] Pola formula TOTAL: anchor $C$8 absolut, range nilai relatif ─────────
TOTAL_RE = re.compile(
    r'^=SUMPRODUCT\(SUBTOTAL\(103,OFFSET\(\$C\$8,'
    r'ROW\(\$C\$8:\$C\$\d+\)-ROW\(\$C\$8\),0\)\),([A-Z]+)\d+:([A-Z]+)\d+\)$')
for col in MONEY_COLS:
    raw = ws[f'{col}{total_row}'].value
    m = TOTAL_RE.match(raw or '')
    assert m, f'{col}{total_row}: pola TOTAL salah -> {raw}'
    assert m.group(1) == m.group(2) == col, f'{col}{total_row}: range nilai bukan kolom sendiri'
print(f'[1] TOTAL row {total_row}: pola $C$8 absolut + range relatif OK')

# ── [2] Detail O = MAX(0,J-N) & nilainya benar ──────────────────────────────
n_detail = 0
for vrow, inv_rows, s in expected:
    for irow, inv in zip(inv_rows, s['invoices']):
        assert ws[f'O{irow}'].value == f'=MAX(0,J{irow}-N{irow})', \
            f'O{irow}: {ws[f"O{irow}"].value}'
        want = max(0.0, inv['harga_excl'] - inv['bayar_dpp'])
        got = cell_value(f'O{irow}')
        assert abs(got - want) < 1e-6, f'O{irow}: {got} != {want}'
        n_detail += 1
print(f'[2] Detail MAX(0,J-N): {n_detail} baris, semua nominal == max(0, harga-bayar) OK')

# ── [3] Rentang SUBTOTAL vendor == blok invoice-nya sendiri ─────────────────
for vrow, inv_rows, s in expected:
    for col in MONEY_COLS:
        raw = ws[f'{col}{vrow}'].value
        want = f'=SUBTOTAL(109,{col}{inv_rows[0]}:{col}{inv_rows[-1]})'
        assert raw == want, f'{col}{vrow}: {raw} != {want}'
print('[3] Rentang SUBTOTAL tiap vendor tepat pada blok invoice-nya OK')

# ── [4] Nilai vendor row hasil evaluasi == penjumlahan detail blok ──────────
for vrow, inv_rows, s in expected:
    want = {
        HUTANG: sum(inv['harga_excl'] for inv in s['invoices']),
        PPN: sum(inv['ppn'] for inv in s['invoices']),
        PPH: sum(inv['pot_pph'] for inv in s['invoices']),
        BAYAR: sum(inv['bayar_dpp'] for inv in s['invoices']),
        SISA: sum(max(0.0, inv['harga_excl'] - inv['bayar_dpp']) for inv in s['invoices']),
    }
    for col in MONEY_COLS:
        got = cell_value(f'{col}{vrow}')
        assert abs(got - want[col]) < 1e-6, \
            f'{s["rekanan"]} {col}: hasil formula {got} != Python {want[col]}'
print('[4] Nilai vendor row (hasil evaluasi formula) == jumlah detail OK')

# ── [5] TOTAL == jumlah vendor row, tanpa double-count ──────────────────────
for col in MONEY_COLS:
    want = sum(cell_value(f'{col}{vrow}') for vrow, _, _ in expected)
    got = cell_value(f'{col}{total_row}')
    assert abs(got - want) < 1e-6, f'TOTAL {col}: {got} != {want}'
    # sanity: harus sama dengan agregat seluruh detail (bukti tidak double-count)
    raw_sum = sum(cell_value(f'{col}{irow}') for _, rows, _ in expected for irow in rows)
    assert abs(got - raw_sum) < 1e-6, f'TOTAL {col}: {got} != total detail {raw_sum}'
print(f'[5] TOTAL row {total_row} == jumlah vendor == jumlah detail (tanpa double-count) OK')

# Nominal konkret yang harus muncul di sheet (regresi anti-ngaco).
assert cell_value(f'J{total_row}') == 5000.0, cell_value(f'J{total_row}')
assert cell_value(f'K{total_row}') == 550.0, cell_value(f'K{total_row}')
assert cell_value(f'L{total_row}') == 50.0, cell_value(f'L{total_row}')
assert cell_value(f'N{total_row}') == 4100.0, cell_value(f'N{total_row}')
# Sisa = (600-0) + (400-200) + (2500-2500) + MAX(0,1000-1200)=0 + (500-200) = 1100
assert cell_value(f'O{total_row}') == 1100.0, cell_value(f'O{total_row}')
print('[5b] Nominal TOTAL konkret: J=5000 K=550 L=50 N=4100 O=1100 OK')

# ── [6] Simulasi geser 1 kolom: anchor tetap, range nilai ikut pindah ───────
shifted = []
for col in MONEY_COLS:
    raw = ws[f'{col}{total_row}'].value
    new_col = get_column_letter(openpyxl.utils.column_index_from_string(col) + 1)
    # Excel menggeser range relatif; anchor absolut tidak bergerak.
    moved = re.sub(r'([A-Z]+)(\d+):([A-Z]+)(\d+)\)$',
                   lambda mm: f'{new_col}{mm.group(2)}:{new_col}{mm.group(4)})', raw)
    assert '$C$8' in moved, f'{col}: anchor hilang setelah geser -> {moved}'
    m = TOTAL_RE.match(moved)
    assert m and m.group(1) == m.group(2) == new_col, f'{col}: range tidak ikut geser -> {moved}'
    shifted.append(moved)
print('[6] Simulasi geser 1 kolom: anchor $C$8 tetap, range nilai ikut berpindah OK')

# ── [7] Tidak ada error / sel kosong pada kolom nominal ─────────────────────
for sheet_row in range(8, total_row + 1):
    for col in MONEY_COLS:
        raw = ws[f'{col}{sheet_row}'].value
        assert raw is not None, f'{col}{sheet_row} kosong'
        if isinstance(raw, str):
            assert '#REF' not in raw and '#NAME' not in raw and '#VALUE' not in raw, \
                f'{col}{sheet_row}: {raw}'
print('[7] Tidak ada #REF!/#NAME?/#VALUE! dan tidak ada sel nominal kosong OK')

# ── [8] Vendor tanpa invoice: jatuh ke angka statis, bukan #REF! ────────────
EMPTY = [{
    'key': '2026-10', 'label': 'Oktober 2026',
    'rekanan_list': [{
        'rekanan': 'PT KOSONG', 'count': 0,
        'total_dpp': 123.0, 'bayar_dpp': 23.0, 'sisa_dpp': 100.0,
        'status_key': 'overdue', 'status_label': 'Telat',
        'invoices': [],
    }],
}]
_orig = jt_excel.build_jatuh_tempo_data
try:
    try:
        jt_excel.build_jatuh_tempo_data = lambda month_key=None, project_id=None: (EMPTY, 0)
        b2 = jt_excel.build_jt_excel(month_key='2026-10')
    except TypeError:
        jt_excel.build_jatuh_tempo_data = lambda project_id=None: (EMPTY, 0)
        b2 = jt_excel.build_jt_excel(month_key='2026-10')
finally:
    jt_excel.build_jatuh_tempo_data = _orig
ws2 = openpyxl.load_workbook(io.BytesIO(b2.getvalue())).active
assert ws2['J8'].value == 123.0, ws2['J8'].value
assert ws2['O8'].value == 100.0, ws2['O8'].value

# Vendor ada tapi tanpa invoice: baris vendor diisi angka statis server, dan
# TOTAL tetap menjumlahkannya (bukan 0, bukan #REF!). Yang diuji: formula valid
# dan hasilnya == angka vendor tsb.
_ws_main, ws = ws, ws2
try:
    expect_total = {HUTANG: 123.0, PPN: 0.0, PPH: 0.0, BAYAR: 23.0, SISA: 100.0}
    for col in MONEY_COLS:
        raw = ws[f'{col}9'].value
        assert isinstance(raw, str) and '#REF' not in raw, f'{col}9: {raw}'
        got = cell_value(f'{col}9')
        assert abs(got - expect_total[col]) < 1e-9, \
            f'TOTAL {col} tanpa invoice = {got}, harus {expect_total[col]}'
finally:
    ws = _ws_main
print('[8] Vendor tanpa invoice -> angka statis, TOTAL menjumlahkannya (bukan #REF!) OK')

# Kasus benar-benar kosong (tanpa vendor sama sekali): TOTAL harus literal 0.
_orig = jt_excel.build_jatuh_tempo_data
try:
    try:
        jt_excel.build_jatuh_tempo_data = lambda month_key=None, project_id=None: ([], 0)
        b3 = jt_excel.build_jt_excel(month_key='2026-10')
    except TypeError:
        jt_excel.build_jatuh_tempo_data = lambda project_id=None: ([], 0)
        b3 = jt_excel.build_jt_excel(month_key='2026-10')
finally:
    jt_excel.build_jatuh_tempo_data = _orig
ws3 = openpyxl.load_workbook(io.BytesIO(b3.getvalue())).active
for col in MONEY_COLS:
    assert ws3[f'{col}8'].value == 0, f'{col}8 tanpa vendor: {ws3[f"{col}8"].value}'
print('[8b] Tanpa vendor sama sekali: TOTAL literal 0, tidak ada SUBTOTAL terbalik OK')

print('\nJT Excel nominal akurat: 5 kolom x semua baris, formula == hitungan Python OK')
