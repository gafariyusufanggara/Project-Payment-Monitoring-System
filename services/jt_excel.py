"""services/jt_excel.py — Laporan Jatuh Tempo Excel export.

Separate from laporan.py to keep that file focused on monthly / weekly LBP.
"""
import io
from collections import defaultdict
from datetime import date, datetime
from constants import safe_float
import db
from services.laporan import build_jatuh_tempo_data


def _parse_date_safe(val):
    """Return a date or None."""
    try:
        return datetime.strptime(str(val or ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _status_fmt(key, overdue_fmt, ok_fmt, neutral_fmt):
    """Map server-computed status_key to Excel cell format.

    Keys come from _jt_status in services/laporan.py:
      overdue/paid_late → red; paid_ok → green; due_today/not_due → neutral.
    """
    if key in ('overdue', 'paid_late'):
        return overdue_fmt
    if key == 'paid_ok':
        return ok_fmt
    return neutral_fmt


def build_jt_excel(month_key=None, project_id=None):
    """Build Excel export for Laporan Jatuh Tempo with vendor-breakdown detail.

    Hierarchical layout (matching LBP pattern):
      1. Vendor summary row (banded) — totals per rekanan
      2. Detail rows underneath — one row per invoice
      3. TOTAL footer row

    Returns io.BytesIO positioned at 0.
    """
    import xlsxwriter

    report_rows, _ = build_jatuh_tempo_data(project_id=project_id)

    now_key = month_key
    if now_key is None and report_rows:
        now_key = report_rows[-1]['key']   # default: latest month
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
    subtitle_fmt = wb.add_format({'font_size': 9, 'font_color': '#64748b', 'italic': True})
    hdr_fmt = wb.add_format({'bold': True, 'font_size': 9, 'font_color': '#dbeafe',
                             'bg_color': '#334155', 'border': 1, 'align': 'center',
                             'valign': 'vcenter', 'text_wrap': True})
    cell_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'right'})
    cell_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'left'})
    num_fmt = wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                            'valign': 'vcenter', 'align': 'right'})
    total_label_fmt = wb.add_format({'bold': True, 'font_size': 9, 'border': 1,
                                    'bg_color': '#f8fafc', 'valign': 'vcenter', 'align': 'left'})
    total_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                              'border': 1, 'bg_color': '#f8fafc',
                              'valign': 'vcenter', 'align': 'right'})

    sisa_pos_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                  'border': 1, 'font_color': '#dc2626',
                                  'valign': 'vcenter', 'align': 'right'})
    sisa_zero_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                   'border': 1, 'font_color': '#10b981',
                                   'valign': 'vcenter', 'align': 'right'})
    band_even_sisa_pos = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                       'border': 1, 'font_color': '#dc2626',
                                       'bg_color': '#eef4ff',
                                       'valign': 'vcenter', 'align': 'right'})
    band_even_sisa_zero = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                         'border': 1, 'font_color': '#10b981',
                                         'bg_color': '#eef4ff',
                                         'valign': 'vcenter', 'align': 'right'})
    band_odd_sisa_pos = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                      'border': 1, 'font_color': '#dc2626',
                                      'bg_color': '#eafaf0',
                                      'valign': 'vcenter', 'align': 'right'})
    band_odd_sisa_zero = wb.add_format({'bold': True, 'font_size': 9, 'num_format': '#,##0',
                                        'border': 1, 'font_color': '#10b981',
                                        'bg_color': '#eafaf0',
                                        'valign': 'vcenter', 'align': 'right'})

    band_even_fmt = wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                                   'bg_color': '#eef4ff', 'font_color': '#1e3a5f',
                                   'bold': True, 'valign': 'vcenter', 'align': 'right'})
    band_even_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#eef4ff',
                                    'font_color': '#1e3a5f', 'bold': True,
                                    'valign': 'vcenter', 'align': 'left'})
    band_odd_fmt = wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                                  'bg_color': '#eafaf0', 'font_color': '#065f46',
                                  'bold': True, 'valign': 'vcenter', 'align': 'right'})
    band_odd_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#eafaf0',
                                    'font_color': '#065f46', 'bold': True,
                                    'valign': 'vcenter', 'align': 'left'})

    # Vendor band-row status tints — background color carries the status signal
    # on the levelansir summary row (no status text there). Sisa keeps its own
    # pos/zero font color on top of the tint.
    def _status_band(bg):
        return (
            wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                           'bg_color': bg, 'font_color': '#1e3a5f',
                           'bold': True, 'valign': 'vcenter', 'align': 'right'}),
            wb.add_format({'font_size': 9, 'border': 1, 'bg_color': bg,
                           'font_color': '#1e3a5f', 'bold': True,
                           'valign': 'vcenter', 'align': 'left'}),
            wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                           'bg_color': bg, 'font_color': '#dc2626',
                           'bold': True, 'valign': 'vcenter', 'align': 'right'}),
            wb.add_format({'font_size': 9, 'num_format': '#,##0', 'border': 1,
                           'bg_color': bg, 'font_color': '#10b981',
                           'bold': True, 'valign': 'vcenter', 'align': 'right'}),
        )

    status_bands = {
        'overdue': _status_band('#fef2f2'),   # red tint — telat
        'paid_late': _status_band('#fff7ed'), # orange tint — lunas telat
        'due_today': _status_band('#fffbeb'), # amber tint — JT hari ini
        'paid_ok': _status_band('#f0fdf4'),   # green tint — lunas tepat
    }

    status_overdue_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#dc2626',
                                        'bold': True, 'valign': 'vcenter', 'align': 'center',
                                        'bg_color': '#fef2f2'})
    status_ok_fmt = wb.add_format({'font_size': 9, 'border': 1, 'font_color': '#10b981',
                                    'bold': True, 'valign': 'vcenter', 'align': 'center',
                                    'bg_color': '#f0fdf4'})

    # ── Column widths (15 cols) ──
    widths = [5, 32, 14, 22, 20, 14, 32, 16, 14, 14, 16, 16, 16, 14]
    for i, w in enumerate(widths):
        ws.set_column(i, i, w)

    row = 0

    # ── Title ─────────────────────────────────────────────
    ws.merge_range(row, 0, row, 13,
                   f'LAPORAN JATUH TEMPO — {mdata["label"]}', title_fmt)
    ws.set_row(row, 26)
    row += 1
    ws.merge_range(row, 0, row, 13, 'Monitoring Hutang Reguler', subtitle_fmt)
    row += 1

    # ── Header (2 rows, merged groups) ──────────────────
    hr = row
    ws.merge_range(hr, 0, hr+1, 0, 'NO', hdr_fmt)
    ws.merge_range(hr, 1, hr+1, 1, 'Nama Levelansir / Rekanan', hdr_fmt)
    ws.merge_range(hr, 2, hr, 6, 'Data Invoice', hdr_fmt)
    ws.merge_range(hr, 7, hr, 9, 'Nilai', hdr_fmt)
    ws.merge_range(hr, 10, hr, 11, 'Pembayaran DPP', hdr_fmt)
    ws.merge_range(hr, 12, hr+1, 12, 'Sisa Hutang DPP', hdr_fmt)
    ws.merge_range(hr, 13, hr+1, 13, 'Status', hdr_fmt)
    ws.set_row(hr, 16)
    row += 1

    leaf = ['Tgl Berkas', 'No Invoice', 'PO / Kontrak', 'Jth Tempo', 'Deskripsi',
            'Hutang DPP', 'PPN', 'PPH',
            'Tgl Bayar DPP', 'Bayar DPP', 'Sisa Hutang DPP', 'Status']
    for i, lab in enumerate(leaf):
        ws.write(row, 2 + i, lab, hdr_fmt)
    ws.set_row(row, 20)
    row += 1

    # ── Data ─────────────────────────────────────────────
    t_total_dpp = t_ppn = t_pph = t_bayar_dpp = t_sisa_dpp = 0
    no = 0

    for idx, s in enumerate(mdata['rekanan_list']):
        no += 1
        even = (idx % 2 == 0)
        bf = band_even_fmt if even else band_odd_fmt
        blf = band_even_l_fmt if even else band_odd_l_fmt

        tot_ppn = sum(inv['ppn'] for inv in s['invoices'])
        tot_pph = sum(inv['pot_pph'] for inv in s['invoices'])

        # Vendor summary row — whole band tinted by status_key (no status text;
        # the background color carries the signal). Falls back to zebra band.
        band = status_bands.get(s.get('status_key', ''))
        if band is None:
            bf, blf = (band_even_fmt, band_even_l_fmt) if even else (band_odd_fmt, band_odd_l_fmt)
            sb_pos = band_even_sisa_pos if even else band_odd_sisa_pos
            sb_zero = band_even_sisa_zero if even else band_odd_sisa_zero
        else:
            bf, blf, sb_pos, sb_zero = band
        ws.write(row, 0, no, bf)
        ws.write(row, 1, s['rekanan'], blf)
        for c in (2, 3, 4, 5, 6):
            ws.write(row, c, '', bf)
        ws.write(row, 7, s['total_dpp'], bf)
        ws.write(row, 8, tot_ppn, bf)
        ws.write(row, 9, tot_pph, bf)
        ws.write(row, 10, '', bf)          # Tgl Bayar DPP — shown in detail rows only
        ws.write(row, 11, s['bayar_dpp'], bf)
        fmt_sisa = sb_pos if s['sisa_dpp'] > 0 else sb_zero
        ws.write(row, 12, s['sisa_dpp'], fmt_sisa)
        ws.write(row, 13, '', bf)          # Status: empty on vendor row, color = signal
        row += 1

        t_total_dpp += s['total_dpp']
        t_ppn += tot_ppn
        t_pph += tot_pph
        t_bayar_dpp += s['bayar_dpp']
        t_sisa_dpp += s['sisa_dpp']

        # ── Detail rows (per invoice) ──────────────────
        for inv in s['invoices']:
            inv_sisa_dpp = max(0, inv['harga_excl'] - inv['bayar_dpp'])
            inv_jt = _parse_date_safe(inv['jth_tempo'])
            inv_jt_str = inv_jt.strftime('%d/%m/%Y') if inv_jt else ''

            status_str = inv.get('status_label', 'Tepat')
            status_f = _status_fmt(inv.get('status_key', ''), status_overdue_fmt, status_ok_fmt, cell_l_fmt)

            ws.write(row, 0, '', cell_fmt)
            ws.write(row, 1, '', cell_fmt)
            ws.write(row, 2, str(inv.get('tgl_berkas', '') or ''), cell_l_fmt)
            ws.write(row, 3, inv.get('invoice', '-'), cell_l_fmt)
            ws.write(row, 4, inv.get('po', '-'), cell_l_fmt)
            ws.write(row, 5, inv_jt_str, cell_l_fmt)
            ws.write(row, 6, inv.get('deskripsi', '-'), cell_l_fmt)
            ws.write(row, 7, inv['harga_excl'], num_fmt)
            ws.write(row, 8, inv['ppn'], num_fmt)
            ws.write(row, 9, inv['pot_pph'], num_fmt)
            ws.write(row, 10, str(inv.get('tgl_bayar_dpp', '') or ''), cell_l_fmt)
            ws.write(row, 11, inv['bayar_dpp'], num_fmt)
            ws.write(row, 12, inv_sisa_dpp, cell_fmt)
            ws.write(row, 13, status_str, status_f)
            row += 1

    # ── TOTAL row ────────────────────────────────────────
    ws.write(row, 0, '', total_label_fmt)
    ws.merge_range(row, 1, row, 6, 'TOTAL', total_label_fmt)
    ws.write(row, 7, t_total_dpp, total_fmt)
    ws.write(row, 8, t_ppn, total_fmt)
    ws.write(row, 9, t_pph, total_fmt)
    ws.write(row, 10, '', total_label_fmt)
    ws.write(row, 11, t_bayar_dpp, total_fmt)
    ws.write(row, 12, t_sisa_dpp, total_fmt)
    ws.write(row, 13, '', total_label_fmt)
    row += 1

    wb.close()
    buf.seek(0)
    return buf
