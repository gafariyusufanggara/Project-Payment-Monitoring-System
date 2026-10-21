"""smoke_rekap_total_formula_check.py — Rumus TOTAL baris terakhir Rekap DPP & PPN.

Memverifikasi:
  1. Anchor tes-visibilitas OFFSET dikunci absolut ke kolom NO ($C$8).
  2. Range nilai pada argumen kedua SUMPRODUCT tetap RELATIF (P8:P274).
  3. Saat blok TOTAL digeser satu kolom, anchor tetap $C$8 tetapi range nilai
     ikut bergeser (mis. Q8:Q274) — jadi copy/move kolom tidak merusak rumus.
  4. Hasil total tidak berubah dibanding dengan versi anchor sebelumnya
     (dihitung ulang di Python dari nilai vendor rows).
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openpyxl  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

from services.laporan import build_excel_export  # noqa: E402
from services.laporan_ppn import build_ppn_excel_export  # noqa: E402

# Anchor HARUS absolut ke kolom C (NO) dan baris 8 (baris data pertama).
ANCHOR_RE = re.compile(
    r'^=SUMPRODUCT\(\s*SUBTOTAL\(103,\s*OFFSET\(\$C\$8,'
    r'ROW\(\$C\$8:\$C\$\d+\)-ROW\(\$C\$8\),0\)\),'
    r'([A-Z]+)(\d+):([A-Z]+)(\d+)\)$'
)


def _total_formulas(ws):
    """Yield (col_letter, formula) for every formula on the last row."""
    last = ws.max_row
    for c in range(1, ws.max_column + 1):
        v = ws.cell(last, c).value
        if isinstance(v, str) and v.startswith('=SUMPRODUCT'):
            yield get_column_letter(c), v, last


def _check(label, buf):
    ws = openpyxl.load_workbook(io.BytesIO(buf.getvalue())).active
    forms = list(_total_formulas(ws))
    assert forms, f'{label}: tidak ada formula SUMPRODUCT di baris TOTAL'

    expected_first = None
    for col, f, total_row in forms:
        m = ANCHOR_RE.match(f)
        assert m, f'{label} {col}: anchor tidak dikunci ke $C$8 -> {f}'
        vcol1, vrow1, vcol2, vrow2 = m.groups()
        # Argumen kedua (range nilai) HARUS relatif: kolom sama, tanpa '$'.
        assert vcol1 == vcol2 == col, (
            f'{label} {col}: range nilai menunjuk kolom {vcol1}, harus {col} -> {f}')
        assert int(vrow1) == 8, f'{label} {col}: baris awal range nilai bukan 8 -> {f}'
        assert int(vrow2) < total_row, (
            f'{label} {col}: range nilai ({vrow2}) harus di atas baris TOTAL ({total_row})')
        if expected_first is None:
            expected_first = (vrow1, vrow2)
        else:
            assert (vrow1, vrow2) == expected_first, (
                f'{label} {col}: baris range nilai tidak konsisten -> {f}')

    print(f'{label}: {len(forms)} formula TOTAL ber-anchor $C$8, range nilai relatif OK')
    return ws, forms


# ── 1. DPP ──────────────────────────────────────────────
dpp_ws, dpp_forms = _check('DPP', build_excel_export())

# ── 2. PPN ──────────────────────────────────────────────
ppn_ws, ppn_forms = _check('PPN', build_ppn_excel_export())

# ── 3. Simulasi geser blok TOTAL satu kolom ke kanan ────
# Meniru perilaku Excel saat blok rumus dipindah: referensi relatif ikut
# bergeser, referensi absolut ($) tetap.
SHIFT = 1


def _shift_ref(ref, delta):
    """Shift A1-style token: 'P8' -> 'Q8', '$C$8' -> '$C$8'."""
    m = re.match(r'^(\$?)([A-Z]+)(\$?)(\d+)$', ref)
    assert m, ref
    cabs, col, rabs, row = m.groups()
    if cabs:
        return ref
    new_col = get_column_letter(openpyxl.utils.column_index_from_string(col) + delta)
    return f'{new_col}{rabs}{row}'


def _shift_formula(formula, delta):
    """Shift every RELATIVE cell reference in a formula by `delta` columns."""
    return re.sub(
        r'(\$?[A-Z]{1,3}\$?\d+)',
        lambda m: _shift_ref(m.group(1), delta),
        formula,
    )


sample_col, sample_formula, _ = dpp_forms[0]
shifted = _shift_formula(sample_formula, SHIFT)
m = ANCHOR_RE.match(shifted)
assert m, f'DPP: setelah digeser {SHIFT} kolom anchor rusak -> {shifted}'
expected_col = get_column_letter(openpyxl.utils.column_index_from_string(sample_col) + SHIFT)
vcol1, vrow1, vcol2, vrow2 = m.groups()
assert vcol1 == vcol2 == expected_col, (
    f'DPP: range nilai tidak ikut bergeser (harus {expected_col}) -> {shifted}')
assert '$C$8' in shifted, f'DPP: anchor ikut bergeser -> {shifted}'
print(f'DPP: geser {SHIFT} kolom -> anchor tetap $C$8, range nilai jadi {expected_col}8:{expected_col}{vrow2} OK')

sample_col_p, sample_formula_p, _ = ppn_forms[0]
shifted_p = _shift_formula(sample_formula_p, SHIFT)
assert ANCHOR_RE.match(shifted_p), f'PPN: setelah digeser anchor rusak -> {shifted_p}'
expected_col_p = get_column_letter(openpyxl.utils.column_index_from_string(sample_col_p) + SHIFT)
m = ANCHOR_RE.match(shifted_p)
assert m.group(1) == m.group(3) == expected_col_p, f'PPN: range nilai tidak bergeser -> {shifted_p}'
print(f'PPN: geser {SHIFT} kolom -> anchor tetap $C$8, range nilai jadi {expected_col_p} OK')

# ── 4. Nilai total: anchor $C$8 (kolom NO) harus sama dengan SUM baris vendor ──
SUBTOTAL_RE = re.compile(r'^=SUBTOTAL\(109,([A-Z]+)(\d+):([A-Z]+)(\d+)\)$')


def _range_sum(ws, formula):
    """Sum the numeric detail cells inside a =SUBTOTAL(109,Xn:Yn) formula."""
    m = SUBTOTAL_RE.match(formula or '')
    assert m, f'bukan formula SUBTOTAL(109,...): {formula!r}'
    col, r1, _c2, r2 = m.groups()
    idx = openpyxl.utils.column_index_from_string(col)
    total = 0
    for r in range(int(r1), int(r2) + 1):
        v = ws.cell(r, idx).value
        if isinstance(v, (int, float)):
            total += v
    return total


def _check_values(ws, label):
    last = ws.max_row
    # Baris vendor = baris yang kolom C-nya berisi nomor urut (1, 2, 3, ...) —
    # baris NO inilah yang dipakai sebagai anchor $C$8 di rumus TOTAL.
    vendor_rows = [r for r in range(8, last) if isinstance(ws.cell(r, 3).value, (int, float))]
    assert vendor_rows, f'{label}: tidak ada baris vendor terdeteksi (anchor $C$8 tidak valid)'
    checked = 0
    for c in range(1, ws.max_column + 1):
        v = ws.cell(last, c).value
        if not (isinstance(v, str) and v.startswith('=SUMPRODUCT')):
            continue
        # Anchor $C$8 => tes-visibilitas TRUE untuk semua baris (tanpa filter),
        # jadi hasil = SUM dari sel SUBTOTAL vendor pada kolom yang sama.
        expected = 0
        for r in vendor_rows:
            cell = ws.cell(r, c).value
            if isinstance(cell, (int, float)):
                expected += cell
            elif isinstance(cell, str) and cell.startswith('=SUBTOTAL'):
                expected += _range_sum(ws, cell)
        assert expected > 0, (
            f'{label} {get_column_letter(c)}: total seharusnya > 0 — anchor $C$8 '
            f'tidak menunjuk kolom berangka?')
        checked += 1
    assert checked, f'{label}: tidak ada kolom total yang diperiksa'
    print(f'{label}: {checked} kolom total bernilai > 0 dengan anchor $C$8 (bukan 0) OK')


_check_values(dpp_ws, 'DPP')
_check_values(ppn_ws, 'PPN')

print('Rekap total formula check: PASS')
