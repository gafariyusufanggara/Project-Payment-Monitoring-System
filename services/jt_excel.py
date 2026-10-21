"""services/jt_excel.py — Laporan Jatuh Tempo Excel export.

Separate from laporan.py to keep that file focused on monthly / weekly LBP.
"""
import io
from datetime import date, datetime

from constants import sisa_belum_lunas
from services.laporan import _col_letter, build_jatuh_tempo_data


ACCOUNTING = '#,##0_);(#,##0);-'

COL_NO = 2
COL_REKANAN = 3
COL_TGL_BERKAS = 4
COL_INVOICE = 5
COL_PO = 6
COL_JTH = 7
COL_DESKRIPSI = 8
COL_HUTANG = 9
COL_PPN = 10
COL_PPH = 11
COL_TGL_BAYAR = 12
COL_BAYAR = 13
COL_SISA = 14
COL_STATUS = 15

# Columns on a vendor row that carry a SUBTOTAL over that vendor's invoice
# rows — the same concept as VENDOR_SUBTOTAL_COLS in services/laporan.py.
# J = Hutang DPP, K = PPN, L = PPH, N = Bayar DPP, O = Sisa Hutang DPP.
# Column P (Status JT) is deliberately excluded: it is a server-computed
# label, not an arithmetic result.
JT_SUBTOTAL_COLS = (COL_HUTANG, COL_PPN, COL_PPH, COL_BAYAR, COL_SISA)


def _parse_date_safe(val):
    """Return a date or None."""
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.strptime(str(val or ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _write_date(ws, row, col, value, fmt):
    dt = _parse_date_safe(value)
    if dt is None:
        ws.write(row, col, '', fmt)
        return
    ws.write_datetime(row, col, datetime(dt.year, dt.month, dt.day), fmt)


def _status_fmt(key, overdue_fmt, late_fmt, ok_fmt, neutral_fmt):
    """Map server-computed status_key to Excel cell format."""
    if key == 'overdue':
        return overdue_fmt
    if key == 'paid_late':
        return late_fmt
    if key == 'paid_ok':
        return ok_fmt
    return neutral_fmt


def build_jt_excel(month_key=None, project_id=None):
    """Build Excel export for Laporan Jatuh Tempo with vendor-breakdown detail.

    Layout mirrors the Rekap exports:
      title at Excel row 4, header rows 5-6, blank row 7 for filters,
      data starts at C8. Returns io.BytesIO positioned at 0.

    Money columns carry formulas, exactly like the DPP / PPN Rekap exports:

      detail row  O  =MAX(0,J-N)                      (Sisa Hutang DPP)
      vendor row  J..O (JT_SUBTOTAL_COLS)
                     =SUBTOTAL(109,J{first}:J{last})  (its own invoice block)
      TOTAL row   J..O (JT_SUBTOTAL_COLS)
                     =SUMPRODUCT(SUBTOTAL(103,OFFSET($C$8,
                        ROW($C$8:$C$last)-ROW($C$8),0)),J{first}:J{last})

    The TOTAL visibility anchor is ABSOLUTE ($C$8 = the NO column) so copying
    or moving the block never breaks the row test; the value range stays
    RELATIVE so it follows the block to whatever column it now lives in.
    No cached values are written (xlsxwriter default), matching DPP / PPN.
    """
    import xlsxwriter

    report_rows, _ = build_jatuh_tempo_data(project_id=project_id)

    now_key = month_key
    if now_key is None and report_rows:
        now_key = report_rows[-1]['key']
    mdata = next((r for r in report_rows if r['key'] == now_key), None)
    if mdata is None and report_rows:
        mdata = report_rows[-1]
    if mdata is None:
        mdata = {'key': '-', 'label': '-', 'rekanan_list': []}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_numbers': False})
    ws = wb.add_worksheet('Jatuh Tempo')

    # ── Formats ───────────────────────────────────────────
    title_fmt = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1e3a5f',
                               'bottom': 2, 'bottom_color': '#1e3a5f', 'valign': 'vcenter'})
    hdr_fmt = wb.add_format({'bold': True, 'font_size': 9, 'font_color': '#dbeafe',
                             'bg_color': '#334155', 'border': 1, 'align': 'center',
                             'valign': 'vcenter', 'text_wrap': True})
    cell_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'right'})
    cell_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'left'})
    date_fmt = wb.add_format({'font_size': 9, 'num_format': 'dd/mm/yyyy', 'border': 1,
                              'valign': 'vcenter', 'align': 'center'})
    num_fmt = wb.add_format({'font_size': 9, 'num_format': ACCOUNTING, 'border': 1,
                             'valign': 'vcenter', 'align': 'right'})
    sisa_pos_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': ACCOUNTING,
                                  'border': 1, 'font_color': '#dc2626',
                                  'valign': 'vcenter', 'align': 'right'})
    sisa_zero_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': ACCOUNTING,
                                   'border': 1, 'font_color': '#10b981',
                                   'valign': 'vcenter', 'align': 'right'})
    total_label_fmt = wb.add_format({'bold': True, 'font_size': 9, 'border': 1,
                                     'bg_color': '#f8fafc', 'valign': 'vcenter', 'align': 'left'})
    total_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': ACCOUNTING,
                               'border': 1, 'bg_color': '#f8fafc',
                               'valign': 'vcenter', 'align': 'right'})
    total_sisa_pos_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': ACCOUNTING,
                                        'border': 1, 'bg_color': '#f8fafc',
                                        'font_color': '#dc2626',
                                        'valign': 'vcenter', 'align': 'right'})
    total_sisa_zero_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': ACCOUNTING,
                                         'border': 1, 'bg_color': '#f8fafc',
                                         'font_color': '#10b981',
                                         'valign': 'vcenter', 'align': 'right'})

    status_overdue_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#dc2626',
                                        'bold': True, 'valign': 'vcenter', 'align': 'center',
                                        'bg_color': '#fef2f2'})
    status_late_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#a16207',
                                     'bold': True, 'valign': 'vcenter', 'align': 'center',
                                     'bg_color': '#fefce8'})
    status_ok_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#10b981',
                                   'bold': True, 'valign': 'vcenter', 'align': 'center',
                                   'bg_color': '#f0fdf4'})
    status_neutral_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#475569',
                                        'bold': True, 'valign': 'vcenter', 'align': 'center'})

    def band_formats(bg, status_fg):
        return {
            'num': wb.add_format({'font_size': 9, 'num_format': ACCOUNTING, 'border': 1,
                                  'bg_color': bg, 'font_color': '#1e3a5f',
                                  'bold': True, 'valign': 'vcenter', 'align': 'right'}),
            'left': wb.add_format({'font_size': 9, 'border': 1, 'bg_color': bg,
                                   'font_color': '#1e3a5f', 'bold': True,
                                   'valign': 'vcenter', 'align': 'left'}),
            'sisa_pos': wb.add_format({'font_size': 9, 'num_format': ACCOUNTING, 'border': 1,
                                       'bg_color': bg, 'font_color': '#dc2626',
                                       'bold': True, 'valign': 'vcenter', 'align': 'right'}),
            'sisa_zero': wb.add_format({'font_size': 9, 'num_format': ACCOUNTING, 'border': 1,
                                        'bg_color': bg, 'font_color': '#10b981',
                                        'bold': True, 'valign': 'vcenter', 'align': 'right'}),
            'status': wb.add_format({'font_size': 9, 'border': 1, 'bg_color': bg,
                                     'font_color': status_fg, 'bold': True,
                                     'valign': 'vcenter', 'align': 'center'}),
        }

    band_even = band_formats('#eef4ff', '#1e3a5f')
    band_odd = band_formats('#eafaf0', '#065f46')
    status_bands = {
        'overdue': band_formats('#fef2f2', '#dc2626'),
        'paid_late': band_formats('#fefce8', '#a16207'),
        'due_today': band_formats('#fffbeb', '#b45309'),
        'paid_ok': band_formats('#f0fdf4', '#10b981'),
    }

    # ── Column widths (C..P) ─────────────────────────────
    widths = [5, 32, 14, 18, 24, 14, 38, 16, 14, 12, 14, 16, 16, 24]
    for i, w in enumerate(widths):
        ws.set_column(COL_NO + i, COL_NO + i, w)

    # ── Title (Excel row 4) ──────────────────────────────
    ws.merge_range(3, COL_NO, 3, COL_STATUS,
                   f'LAPORAN JATUH TEMPO — {mdata["label"]}', title_fmt)
    ws.set_row(3, 26)

    # ── Header (Excel rows 5-6), blank row 7 ─────────────
    hr = 4
    ws.merge_range(hr, COL_NO, hr + 1, COL_NO, 'No.', hdr_fmt)
    ws.merge_range(hr, COL_REKANAN, hr + 1, COL_REKANAN, 'Levelansir / Rekanan', hdr_fmt)
    ws.merge_range(hr, COL_TGL_BERKAS, hr, COL_DESKRIPSI, 'Data Invoice', hdr_fmt)
    ws.merge_range(hr, COL_HUTANG, hr, COL_PPH, 'Nilai', hdr_fmt)
    ws.merge_range(hr, COL_TGL_BAYAR, hr, COL_BAYAR, 'Pembayaran', hdr_fmt)
    ws.merge_range(hr, COL_SISA, hr + 1, COL_SISA, 'Sisa Hutang DPP', hdr_fmt)
    ws.merge_range(hr, COL_STATUS, hr + 1, COL_STATUS, 'Status JT', hdr_fmt)
    ws.set_row(hr, 20)

    leaf = [
        (COL_TGL_BERKAS, 'Tgl Berkas Lengkap'),
        (COL_INVOICE, 'No. Invoice'),
        (COL_PO, 'PO / Kontrak'),
        (COL_JTH, 'Tgl Jatuh Tempo'),
        (COL_DESKRIPSI, 'Deskripsi'),
        (COL_HUTANG, 'Hutang DPP'),
        (COL_PPN, 'PPN'),
        (COL_PPH, 'PPH'),
        (COL_TGL_BAYAR, 'Tgl Bayar DPP'),
        (COL_BAYAR, 'Bayar DPP'),
    ]
    for col, label in leaf:
        ws.write(hr + 1, col, label, hdr_fmt)
    ws.set_row(hr + 1, 30)

    # ── Data (Excel row 8) ───────────────────────────────
    row = 7
    t_total_dpp = t_ppn = t_pph = t_bayar_dpp = t_sisa_dpp = 0
    no = 0

    # Vendor rows are emitted first and remembered in ``vendor_rows``; their
    # SUBTOTAL range can only be written once the invoice rows that follow them
    # are on the sheet and we know where each block ends.
    vendor_rows = []

    for idx, s in enumerate(mdata['rekanan_list']):
        no += 1
        fallback = band_even if idx % 2 == 0 else band_odd
        band = status_bands.get(s.get('status_key', ''), fallback)

        tot_ppn = sum(inv['ppn'] for inv in s['invoices'])
        tot_pph = sum(inv['pot_pph'] for inv in s['invoices'])

        # ── Vendor summary row (shaded band) ────────────
        # Money columns are written as SUBTOTAL formulas once this vendor's
        # invoice block is known, so only the placeholder goes in here.
        vrow = row
        ws.write(row, COL_NO, no, band['num'])
        ws.write(row, COL_REKANAN, s['rekanan'], band['left'])
        for col in (COL_TGL_BERKAS, COL_INVOICE, COL_PO, COL_JTH, COL_DESKRIPSI):
            ws.write(row, col, '', band['num'])
        for col in JT_SUBTOTAL_COLS:
            ws.write(row, col, None, band['num'])
        # Tgl Bayar DPP carries no vendor-level figure, but the cell still needs
        # the band format so the shading is continuous across the whole row
        # (and so the TOTAL row underneath lines up).
        ws.write(row, COL_TGL_BAYAR, '', band['num'])
        # Status JT is an invoice-level verdict: the vendor summary row leaves it
        # blank so only real invoice rows show a status.
        ws.write(row, COL_STATUS, '', band['status'])
        row += 1

        t_total_dpp += s['total_dpp']
        t_ppn += tot_ppn
        t_pph += tot_pph
        t_bayar_dpp += s['bayar_dpp']
        t_sisa_dpp += s['sisa_dpp']

        vendor_rows.append((vrow, s, band))

        for inv in s['invoices']:
            inv_sisa_dpp = max(0, inv['harga_excl'] - inv['bayar_dpp'])
            status_f = _status_fmt(inv.get('status_key', ''), status_overdue_fmt,
                                   status_late_fmt, status_ok_fmt, status_neutral_fmt)

            ws.write(row, COL_NO, '', cell_fmt)
            ws.write(row, COL_REKANAN, '', cell_fmt)
            _write_date(ws, row, COL_TGL_BERKAS, inv.get('tgl_berkas'), date_fmt)
            ws.write(row, COL_INVOICE, inv.get('invoice', '-'), cell_l_fmt)
            ws.write(row, COL_PO, inv.get('po', '-'), cell_l_fmt)
            _write_date(ws, row, COL_JTH, inv.get('jth_tempo'), date_fmt)
            ws.write(row, COL_DESKRIPSI, inv.get('deskripsi', '-'), cell_l_fmt)
            ws.write(row, COL_HUTANG, inv['harga_excl'], num_fmt)
            ws.write(row, COL_PPN, inv['ppn'], num_fmt)
            ws.write(row, COL_PPH, inv['pot_pph'], num_fmt)
            _write_date(ws, row, COL_TGL_BAYAR, inv.get('tgl_bayar_dpp'), date_fmt)
            ws.write(row, COL_BAYAR, inv['bayar_dpp'], num_fmt)
            # Sisa is derived, not imported: keep it as a live formula so editing
            # Hutang (J) or Bayar (N) by hand immediately fixes the outstanding
            # amount. MAX(0, …) mirrors the Python max(0, harga_excl - bayar_dpp)
            # exactly, so the displayed figure is unchanged.
            sisa_fmt = sisa_pos_fmt if sisa_belum_lunas(inv_sisa_dpp) else sisa_zero_fmt
            ws.write_formula(row, COL_SISA,
                             f'=MAX(0,{_col_letter(COL_HUTANG)}{row + 1}'
                             f'-{_col_letter(COL_BAYAR)}{row + 1})',
                             sisa_fmt)
            ws.write(row, COL_STATUS, inv.get('status_label', 'Tepat'), status_f)
            row += 1

    # ── Fill vendor SUBTOTAL formulas ───────────────────
    # Each vendor row aggregates exactly its own invoice rows. SUBTOTAL(109, …)
    # ignores rows hidden by a filter, so collapsing a vendor or filtering the
    # sheet keeps the numbers right — same behaviour as the DPP / PPN exports.
    for i, (vrow, s, band) in enumerate(vendor_rows):
        block_end = vendor_rows[i + 1][0] - 1 if i + 1 < len(vendor_rows) else row - 1
        first = vrow + 1           # first invoice row of this vendor (0-based)
        if block_end < first:
            # Vendor with no invoice rows: a SUBTOTAL over an inverted range
            # would emit #REF!, so fall back to the server-computed figures.
            ws.write(vrow, COL_HUTANG, s['total_dpp'], band['num'])
            ws.write(vrow, COL_PPN, sum(inv['ppn'] for inv in s['invoices']), band['num'])
            ws.write(vrow, COL_PPH, sum(inv['pot_pph'] for inv in s['invoices']), band['num'])
            ws.write(vrow, COL_BAYAR, s['bayar_dpp'], band['num'])
            sisa_fmt = band['sisa_pos'] if sisa_belum_lunas(s['sisa_dpp']) else band['sisa_zero']
            ws.write(vrow, COL_SISA, s['sisa_dpp'], sisa_fmt)
            continue
        for col in JT_SUBTOTAL_COLS:
            L = _col_letter(col)
            ws.write_formula(
                vrow, col,
                f'=SUBTOTAL(109,{L}{first + 1}:{L}{block_end + 1})',
                band['num'],
            )

    # ── TOTAL row ───────────────────────────────────────
    # SUM over the vendor subtotal cells only. A plain =SUM() would double-count
    # because those vendor cells already aggregate the invoice rows sitting in
    # the same column range. SUBTOTAL(103,OFFSET(...)) is a per-row visibility
    # test, so hidden / filtered-out vendors are excluded just like the vendor
    # subtotals themselves are.
    ws.write(row, COL_NO, '', total_label_fmt)
    ws.merge_range(row, COL_REKANAN, row, COL_DESKRIPSI, 'TOTAL', total_label_fmt)
    if vendor_rows:
        v_first = vendor_rows[0][0] + 1          # 1-based first vendor row
        v_last = vendor_rows[-1][0] + 1          # 1-based last vendor row
        anchor_col = _col_letter(COL_NO)         # C — the NO column
        anchor = f'${anchor_col}${v_first}'
        anchor_rng = f'${anchor_col}${v_first}:${anchor_col}${v_last}'
        for col in JT_SUBTOTAL_COLS:
            L = _col_letter(col)
            ws.write_formula(
                row, col,
                f'=SUMPRODUCT(SUBTOTAL(103,OFFSET({anchor},'
                f'ROW({anchor_rng})'
                f'-ROW({anchor}),0)),'
                f'{L}{v_first}:{L}{v_last})',
                total_fmt,
            )
    else:
        for col in JT_SUBTOTAL_COLS:
            ws.write(row, col, 0, total_fmt)
    ws.write(row, COL_TGL_BAYAR, '', total_label_fmt)
    ws.write(row, COL_STATUS, '', total_label_fmt)

    # ── Sheet / print setup ──────────────────────────────
    ws.freeze_panes(7, 4)   # rows 1-7 + cols A-D: No (C) & Levelansir (D) sticky
    ws.hide_gridlines(2)
    ws.set_landscape()
    ws.set_paper(9)
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(4, 5)
    ws.set_margins(0.3, 0.3, 0.5, 0.4)
    ws.center_horizontally()

    wb.close()
    buf.seek(0)
    return buf
