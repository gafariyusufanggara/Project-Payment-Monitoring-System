"""
MODEL — Laporan PPN Bulanan & Mingguan (PPN report builders).

Reuses the shared _build_cum from laporan.py, then builds per-month (and
per-week) PPN aggregations (same period grouping as DPP Bulanan/Mingguan).
"""
from collections import defaultdict
from datetime import datetime, timedelta

import db
from services.laporan import _build_cum


def build_ppn_data(project_id=None):
    """Compute the monthly PPN laporan dataset.

    Grouping uses TGL BERKAS (same as DPP bulanan) so months align.
    Reuses _build_cum which now tracks PPN cumulative fields.

    project_id: None = all projects (consolidated); otherwise int project id.
    Returns (report_rows, data_count) where each report row is:
        { 'key': 'YYYY-MM', 'label': 'Jul 2026', 'rekanan_list': [...],
          'kpi': { 'lalu_ppn', 'saat_ini_ppn', 'sd_ppn',
                   'lalu_bayar_ppn', 'saat_ini_bayar_ppn', 'sd_bayar_ppn',
                   'sisa_ppn' } }
    """
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                   'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

    def month_keyfn(dt):
        return dt.strftime('%Y-%m')

    def _has_ppn(row):
        st = (row.get('STATUS TERHADAP PPN') or '').strip()
        return st != 'Tidak ada PPN' and st != ''
    rekan_cum, all_months, sorted_rekan, data = _build_cum(month_keyfn, filter_fn=_has_ppn, project_id=project_id)

    report_rows = []
    for mk in all_months:
        y, m = mk.split('-')
        label = f'{month_names[int(m)]} {y}'

        rekanan_list = []
        tot_lalu_ppn = tot_saat_ini_ppn = tot_sd_ppn = 0
        tot_lalu_bayar_ppn = tot_saat_ini_bayar_ppn = tot_sd_bayar_ppn = 0
        tot_sisa_ppn = 0
        month_total_count = 0
        month_total_ppn_pay_count = 0

        for rekan in sorted_rekan:
            rc = rekan_cum.get((rekan, mk))
            if rc is None:
                continue

            tot_lalu_ppn += rc['lalu_ppn']
            tot_saat_ini_ppn += rc['saat_ini_ppn']
            tot_sd_ppn += rc['sd_ppn']
            tot_lalu_bayar_ppn += rc['lalu_bayar_ppn']
            tot_saat_ini_bayar_ppn += rc['saat_ini_bayar_ppn']
            tot_sd_bayar_ppn += rc['sd_bayar_ppn']
            tot_sisa_ppn += rc['sisa_ppn']

            rekanan_list.append({
                'rekanan': rekan,
                'lalu_ppn': rc['lalu_ppn'],
                'saat_ini_ppn': rc['saat_ini_ppn'],
                'sd_ppn': rc['sd_ppn'],
                'lalu_bayar_ppn': rc['lalu_bayar_ppn'],
                'saat_ini_bayar_ppn': rc['saat_ini_bayar_ppn'],
                'sd_bayar_ppn': rc['sd_bayar_ppn'],
                'sisa_ppn': rc['sisa_ppn'],
                'invoices': rc['invoices'],
                'count': rc['count'],
                'ppn_pay_count': rc['ppn_pay_count'],
            })
            month_total_count += rc['count']
            month_total_ppn_pay_count += rc['ppn_pay_count']

        report_rows.append({
            'key': mk,
            'label': label,
            'rekanan_list': rekanan_list,
            'total_count': month_total_count,
            'total_ppn_pay_count': month_total_ppn_pay_count,
            'kpi': {
                'lalu_ppn': tot_lalu_ppn,
                'saat_ini_ppn': tot_saat_ini_ppn,
                'sd_ppn': tot_sd_ppn,
                'lalu_bayar_ppn': tot_lalu_bayar_ppn,
                'saat_ini_bayar_ppn': tot_saat_ini_bayar_ppn,
                'sd_bayar_ppn': tot_sd_bayar_ppn,
                'sisa_ppn': tot_sisa_ppn,
            },
        })

    return report_rows, len(data)


def build_ppn_mingguan_data(project_id=None):
    """Compute the WEEKLY PPN laporan dataset (period = Sunday..Saturday week).

    Same content as build_ppn_data (PPN fields only), but grouped by week
    using the shared _week_key so weeks line up with Laporan DPP Mingguan.
    Grouping uses TGL TERIMA (same as PPN bulanan), payments by TGL BAYAR PPN.

    project_id: None = all projects (consolidated); otherwise int project id.
    Returns (report_rows, data_count) where each report row is:
        { 'key': 'YYYY-Www', 'label': '05 Jan–11 Jan 2026', 'year': 2026,
          'month': 1, 'rekanan_list': [...], 'kpi': {...PPN...} }
    """
    from services.laporan import _week_key

    def _has_ppn(row):
        st = (row.get('STATUS TERHADAP PPN') or '').strip()
        return st != 'Tidak ada PPN' and st != ''

    def week_keyfn(dt):
        return _week_key(dt)

    rekan_cum, all_weeks, sorted_rekan, data = _build_cum(
        week_keyfn, filter_fn=_has_ppn, project_id=project_id)

    # Ensure current week is included so empty weeks still show vendor data
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    wd = (today.weekday() + 1) % 7   # Sun=0
    cur_sun = today - timedelta(days=wd)
    cur_wk = _week_key(cur_sun)
    if cur_wk not in all_weeks:
        all_weeks = sorted(all_weeks + [cur_wk])

    report_rows = []
    vendor_last = {}  # most recent rc per rekan, for empty-week fallback
    for wk in all_weeks:
        iso_year, wnum = wk.split('-W')
        # Monday of this ISO week, then back to its Sunday (week start)
        monday = datetime.fromisocalendar(int(iso_year), int(wnum), 1)
        start = monday - timedelta(days=1)          # Sunday
        end = start + timedelta(days=6)             # Saturday
        label = f'{start:%d %b}–{end:%d %b %Y}'
        # Calendar month/year this week belongs to = its closing Saturday's month.
        year = end.year
        month = end.month

        rekanan_list = []
        tot_lalu_ppn = tot_saat_ini_ppn = tot_sd_ppn = 0
        tot_lalu_bayar_ppn = tot_saat_ini_bayar_ppn = tot_sd_bayar_ppn = 0
        tot_sisa_ppn = 0
        month_total_count = 0
        month_total_ppn_pay_count = 0

        for rekan in sorted_rekan:
            rc = rekan_cum.get((rekan, wk))
            if rc is None:
                # Fall back to last known cumulative state for empty weeks.
                # All seven PPN fields must be carried over here — copying only
                # the DPP ones would show a vendor's PPN as 0 on quiet weeks.
                last = vendor_last.get(rekan)
                if last is None:
                    continue
                rc = {
                    'lalu_ppn': last['sd_ppn'],
                    'saat_ini_ppn': 0,
                    'sd_ppn': last['sd_ppn'],
                    'lalu_bayar_ppn': last['sd_bayar_ppn'],
                    'saat_ini_bayar_ppn': 0,
                    'sd_bayar_ppn': last['sd_bayar_ppn'],
                    'invoices': [],
                    'count': 0,
                    'ppn_pay_count': 0,
                    'sisa_ppn': last['sisa_ppn'],
                }
            else:
                vendor_last[rekan] = rc
            # Skip vendors with no PPN activity at all up to/in this week.
            if rc['sd_ppn'] == 0 and rc['sd_bayar_ppn'] == 0:
                continue

            tot_lalu_ppn += rc['lalu_ppn']
            tot_saat_ini_ppn += rc['saat_ini_ppn']
            tot_sd_ppn += rc['sd_ppn']
            tot_lalu_bayar_ppn += rc['lalu_bayar_ppn']
            tot_saat_ini_bayar_ppn += rc['saat_ini_bayar_ppn']
            tot_sd_bayar_ppn += rc['sd_bayar_ppn']
            tot_sisa_ppn += rc['sisa_ppn']

            rekanan_list.append({
                'rekanan': rekan,
                'lalu_ppn': rc['lalu_ppn'],
                'saat_ini_ppn': rc['saat_ini_ppn'],
                'sd_ppn': rc['sd_ppn'],
                'lalu_bayar_ppn': rc['lalu_bayar_ppn'],
                'saat_ini_bayar_ppn': rc['saat_ini_bayar_ppn'],
                'sd_bayar_ppn': rc['sd_bayar_ppn'],
                'sisa_ppn': rc['sisa_ppn'],
                'invoices': rc['invoices'],
                'count': rc['count'],
                'ppn_pay_count': rc['ppn_pay_count'],
            })
            month_total_count += rc['count']
            month_total_ppn_pay_count += rc['ppn_pay_count']

        report_rows.append({
            'key': wk,
            'label': label,
            'year': year,
            'month': month,
            'rekanan_list': rekanan_list,
            'total_count': month_total_count,
            'total_ppn_pay_count': month_total_ppn_pay_count,
            'kpi': {
                'lalu_ppn': tot_lalu_ppn,
                'saat_ini_ppn': tot_saat_ini_ppn,
                'sd_ppn': tot_sd_ppn,
                'lalu_bayar_ppn': tot_lalu_bayar_ppn,
                'saat_ini_bayar_ppn': tot_saat_ini_bayar_ppn,
                'sd_bayar_ppn': tot_sd_bayar_ppn,
                'sisa_ppn': tot_sisa_ppn,
            },
        })

    # ── Fill missing calendar weeks so every Sun-Sat week appears ──
    # Without this the week dropdown has holes: a week with zero PPN activity
    # would simply not exist, and the month filter could land on nothing.
    if report_rows:
        def _sun_of_key(k):
            """Return the Sunday (datetime) for week key 'YYYY-Www'."""
            y, w = k.split('-W')
            mon = datetime.fromisocalendar(int(y), int(w), 1)
            return mon - timedelta(days=1)

        first_sun = _sun_of_key(report_rows[0]['key'])
        last_sun = _sun_of_key(report_rows[-1]['key'])
        cur_sun = today - timedelta(days=(today.weekday() + 1) % 7)
        if cur_sun > last_sun:
            last_sun = cur_sun
        existing = {r['key'] for r in report_rows}
        report_by_key = {r['key']: r for r in report_rows}

        cursor = first_sun
        last_kpi = {}
        last_rekan_list = []
        while cursor <= last_sun:
            wk = _week_key(cursor)
            real_row = report_by_key.get(wk)
            if real_row is not None:
                last_kpi = real_row['kpi']
                last_rekan_list = real_row['rekanan_list']
                # Snapshot per vendor with NO new activity (filled weeks are
                # calendar gaps, not real periods). Copying (not aliasing) keeps
                # invoices from being re-counted as if received again.
                fill_list = []
                for _v in last_rekan_list:
                    _c = dict(_v)
                    _c['invoices'] = []
                    _c['count'] = 0
                    _c['ppn_pay_count'] = 0
                    fill_list.append(_c)
                last_rekan_list = fill_list
            elif wk not in existing:
                end = cursor + timedelta(days=6)
                label = f'{cursor:%d %b}–{end:%d %b %Y}'
                report_rows.append({
                    'key': wk,
                    'label': label,
                    'year': end.year,
                    'month': end.month,
                    'rekanan_list': last_rekan_list,
                    'total_count': 0,
                    'total_ppn_pay_count': 0,
                    'kpi': {
                        'lalu_ppn': last_kpi.get('sd_ppn', 0),
                        'saat_ini_ppn': 0,
                        'sd_ppn': last_kpi.get('sd_ppn', 0),
                        'lalu_bayar_ppn': last_kpi.get('sd_bayar_ppn', 0),
                        'saat_ini_bayar_ppn': 0,
                        'sd_bayar_ppn': last_kpi.get('sd_bayar_ppn', 0),
                        'sisa_ppn': last_kpi.get('sisa_ppn', 0),
                    },
                })
                existing.add(wk)
            cursor += timedelta(days=7)

        report_rows.sort(key=lambda r: r['key'])

    return report_rows, len(data)


import io
import xlsxwriter


# Columns on a vendor row that carry a SUBTOTAL over that vendor's invoice rows.
# 15..21 = PPN Lalu/Saat Ini/S.D, Bayar Lalu/Saat Ini/S.D, Sisa PPN.
PPN_VENDOR_SUBTOTAL_COLS = (15, 16, 17, 18, 19, 20, 21)


def _render_ppn(wb, ws, mdata, now_key, period_of, title_suffix='', project_id=None):
    """Render PPN export sheet in DPP-style hierarchical layout.

    Same geometry as DPP export (_render_lbp): starts at col C, title on
    Excel row 4, 2-row header on rows 5-6, data from row 11 (rows 7-10
    left blank for manual customization).
      Cols C-O  — NO, Vendor, Uraian, Kode, Item, PO/SPK/Invoice,
                  Metode Bayar, Tgl Berkas, Tgl Faktur Pajak,
                  Vol, Sat, Harga Satuan, Jumlah
      Cols P-R  — PPN (Lalu / Saat Ini / S.D Saat Ini)
      Cols S-U  — Pembayaran PPN (Lalu / Saat Ini / S.D Saat Ini)
      Col V     — Sisa PPN
      Col W     — gap
    Vendor rows carry =SUBTOTAL(109, …) over their own invoice block and
    the TOTAL row aggregates vendors with the same filter-aware SUMPRODUCT
    pattern as DPP, so filtering keeps the numbers right.
    """
    from services.dashboard import _dedup_debt_rows
    from services.laporan import _col_letter, _po_sort_key, _resolve_pay_period
    from constants import safe_float

    raw = db.read_data(project_id=project_id)
    raw = [r for r in raw if (r.get('STATUS TERHADAP PPN') or '').strip() not in ('Tidak ada PPN', '')]
    hist = defaultdict(list)
    for row in _dedup_debt_rows(raw):
        rekan = (row.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip() or 'Unknown'
        hist[rekan].append(row)

    def period_of_dt(dt):
        return period_of(dt.strftime('%Y-%m-%d'))

    acct = '#,##0_);(#,##0);-'
    title_fmt = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1e3a5f',
                               'bottom': 2, 'bottom_color': '#1e3a5f', 'valign': 'vcenter'})
    subtitle_fmt = wb.add_format({'font_size': 9, 'font_color': '#64748b', 'italic': True})
    hdr_fmt = wb.add_format({'bold': True, 'font_size': 8, 'font_color': '#dbeafe',
                             'bg_color': '#334155', 'border': 1, 'align': 'center',
                             'valign': 'vcenter', 'text_wrap': True})
    grp_h_fmt = wb.add_format({'bold': True, 'font_size': 9, 'font_color': '#1e40af',
                               'bg_color': '#dbeafe', 'border': 1, 'align': 'center',
                               'valign': 'vcenter', 'text_wrap': True})
    grp_p_fmt = wb.add_format({'bold': True, 'font_size': 9, 'font_color': '#15803d',
                               'bg_color': '#dcfce7', 'border': 1, 'align': 'center',
                               'valign': 'vcenter', 'text_wrap': True})
    cell_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'right'})
    vol_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter',
                             'align': 'right', 'num_format': '#,##0.00'})
    cell_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'left'})
    cell_money_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                                    'valign': 'vcenter', 'align': 'right'})
    num_h_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                               'font_color': '#1e40af', 'valign': 'vcenter', 'align': 'right'})
    num_p_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                               'font_color': '#15803d', 'valign': 'vcenter', 'align': 'right'})
    total_label_fmt = wb.add_format({'bold': True, 'font_size': 9, 'border': 1,
                                     'bg_color': '#f8fafc', 'valign': 'vcenter', 'align': 'left'})
    total_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': acct,
                               'border': 1, 'bg_color': '#f8fafc',
                               'valign': 'vcenter', 'align': 'right'})
    gap_fmt = wb.add_format({'font_size': 9, 'valign': 'vcenter', 'align': 'right'})
    band_even_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                                   'bg_color': '#eef4ff', 'font_color': '#1e3a5f',
                                   'bold': True, 'valign': 'vcenter', 'align': 'right'})
    band_even_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#eef4ff',
                                     'font_color': '#1e3a5f', 'bold': True,
                                     'valign': 'vcenter', 'align': 'left'})
    band_odd_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                                  'bg_color': '#eafaf0', 'font_color': '#065f46',
                                  'bold': True, 'valign': 'vcenter', 'align': 'right'})
    band_odd_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'bg_color': '#eafaf0',
                                    'font_color': '#065f46', 'bold': True,
                                    'valign': 'vcenter', 'align': 'left'})

    # ── Column widths (21 cols, starting at col C) — DPP geometry plus
    # Tgl Faktur Pajak (col K) in place of the DPP Item column. ──
    widths = [4, 26, 36, 14, 14, 16, 16, 14, 14, 6, 5, 14, 16, 13, 13, 14, 13, 13, 14, 14, 6]
    for i, w in enumerate(widths):
        ws.set_column(2 + i, 2 + i, w)

    # ── Title row 4 (0-based row 3) spans C..W (cols 2..22) ──
    ws.merge_range(3, 2, 3, 22,
        f'REKAP PPN & PEMBAYARAN PPN — {mdata["label"]}{title_suffix}', title_fmt)
    ws.set_row(3, 26)

    # ── Header (2 rows) at Excel rows 5-6 (0-based 4-5) ──
    # Rows 7-10 are intentionally left blank for manual customization.
    # Data starts at Excel row 11 (0-based row 10).
    hr = 4
    ws.merge_range(hr, 2, hr+1, 2, 'NO', hdr_fmt)
    ws.merge_range(hr, 3, hr+1, 3, 'Vendor', hdr_fmt)
    ws.merge_range(hr, 4, hr+1, 4, 'Uraian Pengadaan / Pekerjaan', hdr_fmt)
    ws.merge_range(hr, 5, hr+1, 5, 'Kode RBK/ERP', hdr_fmt)
    ws.merge_range(hr, 6, hr+1, 6, 'Item', hdr_fmt)
    ws.merge_range(hr, 7, hr+1, 7, 'Nomor PO/SPK/Invoice', hdr_fmt)
    ws.merge_range(hr, 8, hr+1, 8, 'Metode Bayar', hdr_fmt)
    ws.merge_range(hr, 9, hr+1, 9, 'Tgl Berkas\nLengkap', hdr_fmt)
    ws.merge_range(hr, 10, hr+1, 10, 'Tgl Faktur\nPajak', hdr_fmt)
    ws.merge_range(hr, 11, hr+1, 11, 'Vol', hdr_fmt)
    ws.merge_range(hr, 12, hr+1, 12, 'Sat', hdr_fmt)
    ws.merge_range(hr, 13, hr+1, 13, 'Harga Satuan', hdr_fmt)
    ws.merge_range(hr, 14, hr+1, 14, 'Jumlah', hdr_fmt)
    ws.merge_range(hr, 15, hr, 17, 'PPN', grp_h_fmt)
    ws.merge_range(hr, 18, hr, 20, 'Pembayaran PPN', grp_p_fmt)
    ws.merge_range(hr, 21, hr+1, 21, 'Sisa PPN', hdr_fmt)
    ws.merge_range(hr, 22, hr+1, 22, '', gap_fmt)
    ws.set_row(hr, 16)
    leaf = ['Lalu\nJumlah', 'Saat Ini\nJumlah', 'S.D Saat Ini\nJumlah',
            'Lalu\nJumlah', 'Saat Ini\nJumlah', 'S.D Saat Ini\nJumlah']
    leaf_row = hr + 1
    for i, lab in enumerate(leaf):
        fmt = grp_h_fmt if i < 3 else grp_p_fmt
        ws.write(leaf_row, 15 + i, lab, fmt)
    ws.set_row(leaf_row, 26)
    row = 10  # Data starts at Excel row 11 (0-based row 10)

    # ── Data ─────────────────────────────────────────────
    vendor_rows = []

    no = 0

    for idx, s in enumerate(mdata['rekanan_list']):
        rekan = s['rekanan']

        # skip vendors with no PPN activity up to this period
        if s['sd_ppn'] == 0 and s['sd_bayar_ppn'] == 0:
            continue

        no += 1
        even = (idx % 2 == 0)
        bf = band_even_fmt if even else band_odd_fmt
        blf = band_even_l_fmt if even else band_odd_l_fmt

        # ── Vendor summary row (shaded band; SUBTOTAL filled after block) ──
        vrow = row
        ws.write(row, 2, no, bf)
        ws.write(row, 3, rekan, blf)
        for c in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            ws.write(row, c, '', bf)
        for c in PPN_VENDOR_SUBTOTAL_COLS:
            ws.write(row, c, None, bf)
        ws.write(row, 22, '', gap_fmt)
        row += 1
        vendor_rows.append((vrow, rekan, s, bf))

        # Detail rows — per invoice, filtered up to selected period,
        # sorted by PO/SPK then TGL TERIMA (same order as DPP export).
        for inv in sorted(hist.get(rekan, []), key=lambda r: (_po_sort_key(r.get('NO PO / KONTRAK')), str(r.get('TGL TERIMA') or '9999-99-99'))):
            inv_m = period_of(inv.get('TGL TERIMA'))
            if inv_m and inv_m > now_key:
                continue

            ppn = safe_float(inv.get('PPN'))
            bayar_ppn = safe_float(inv.get('PEMBAYARAN PPN'))

            p_lalu = p_si = 0.0
            if ppn:
                if inv_m == now_key:
                    p_si = ppn
                elif inv_m and inv_m < now_key:
                    p_lalu = ppn

            # Bayar PPN resolved through _resolve_pay_period — the SAME helper
            # the vendor summary uses — so a payment dated before its invoice
            # is clamped to the debt date instead of landing earlier.
            bp_lalu = bp_si = 0.0
            if bayar_ppn > 0:
                resolved_m = _resolve_pay_period(inv.get('TGL BAYAR PPN'),
                                                 inv.get('TGL TERIMA'),
                                                 period_of_dt)
                if resolved_m is None:
                    resolved_m = period_of(inv.get('TGL BAYAR PPN'))
                if resolved_m == now_key:
                    bp_si = bayar_ppn
                elif resolved_m and resolved_m < now_key:
                    bp_lalu = bayar_ppn

            vol = safe_float(inv.get('VOLUME PROGRESS'))
            harga_satuan = safe_float(inv.get('HARGA SATUAN'))

            ws.write(row, 2, '', cell_fmt)
            ws.write(row, 3, '', cell_fmt)
            ws.write(row, 4, inv.get('DESKRIPSI') or '-', cell_l_fmt)
            ws.write(row, 5, inv.get('KODE BIAYA2') or '', cell_l_fmt)
            ws.write(row, 6, '', cell_fmt)      # Item — empty, manual input
            ws.write(row, 7, inv.get('NO PO / KONTRAK') or inv.get('NO INVOICE') or '', cell_l_fmt)
            ws.write(row, 8, inv.get('PEMBAYARAN PPN VIA') or inv.get('PEMBAYARAN DPP VIA DIVISI') or '', cell_l_fmt)
            ws.write(row, 9, inv.get('TGL TERIMA') or '', cell_l_fmt)
            ws.write(row, 10, inv.get('TGL FAKTUR PAJAK') or '', cell_l_fmt)
            ws.write(row, 11, vol if vol else '', vol_fmt)
            ws.write(row, 12, '', cell_fmt)      # Sat — no source column
            ws.write(row, 13, harga_satuan, num_h_fmt)
            ws.write(row, 14, harga_satuan * vol, num_h_fmt)
            ws.write(row, 15, p_lalu, num_h_fmt)
            ws.write(row, 16, p_si, num_h_fmt)
            ws.write(row, 17, p_lalu + p_si, num_h_fmt)
            ws.write(row, 18, bp_lalu, num_p_fmt)
            ws.write(row, 19, bp_si, num_p_fmt)
            ws.write(row, 20, bp_lalu + bp_si, num_p_fmt)
            ws.write(row, 21, max(0, (p_lalu + p_si) - (bp_lalu + bp_si)), cell_money_fmt)
            ws.write(row, 22, '', gap_fmt)
            row += 1

    # ── Fill vendor SUBTOTAL formulas ───────────────────
    # Each vendor row aggregates exactly its own invoice rows (the block that
    # was written between this vendor row and the next one / the end of data).
    # SUBTOTAL(109, …) ignores rows hidden by a filter, so collapsing a vendor
    # or filtering the sheet keeps the numbers right.
    for i, (vrow, rekan, s, bf) in enumerate(vendor_rows):
        block_end = vendor_rows[i + 1][0] - 1 if i + 1 < len(vendor_rows) else row - 1
        first = vrow + 1           # first invoice row of this vendor
        if block_end < first:
            # Vendor with no invoice rows: fall back to computed static figures.
            ws.write(vrow, 15, s['lalu_ppn'], bf)
            ws.write(vrow, 16, s['saat_ini_ppn'], bf)
            ws.write(vrow, 17, s['sd_ppn'], bf)
            ws.write(vrow, 18, s['lalu_bayar_ppn'], bf)
            ws.write(vrow, 19, s['saat_ini_bayar_ppn'], bf)
            ws.write(vrow, 20, s['sd_bayar_ppn'], bf)
            ws.write(vrow, 21, max(0, s['sisa_ppn']), bf)
            continue
        for c in PPN_VENDOR_SUBTOTAL_COLS:
            L = _col_letter(c)
            ws.write_formula(
                vrow, c,
                f'=SUBTOTAL(109,{L}{first + 1}:{L}{block_end + 1})',
                bf,
            )

    # ── TOTAL row ───────────────────────────────────────
    # SUM over the vendor subtotal cells only (same filter-aware SUMPRODUCT
    # pattern as DPP, anchored on the Vendor column).
    ws.write(row, 2, '', total_label_fmt)
    ws.merge_range(row, 3, row, 14, 'TOTAL', total_label_fmt)
    if vendor_rows:
        v_first = vendor_rows[0][0] + 1          # 1-based first vendor row
        v_last = vendor_rows[-1][0] + 1          # 1-based last vendor row
        for c in PPN_VENDOR_SUBTOTAL_COLS:
            L = _col_letter(c)
            ws.write_formula(
                row, c,
                f'=SUMPRODUCT(SUBTOTAL(103,OFFSET({_col_letter(3)}{v_first},'
                f'ROW({_col_letter(3)}{v_first}:{_col_letter(3)}{v_last})'
                f'-ROW({_col_letter(3)}{v_first}),0)),'
                f'{L}{v_first}:{L}{v_last})',
                total_fmt,
            )
    else:
        for c in PPN_VENDOR_SUBTOTAL_COLS:
            ws.write(row, c, 0, total_fmt)
    ws.write(row, 22, '', gap_fmt)
    row += 1


def build_ppn_excel_export(month_key=None, project_id=None):
    """Build Excel export for Laporan PPN Bulanan — DPP-aligned hierarchical layout.

    Same 21-column structure as DPP export (21 cols from C..W):
      Cols C-O   — NO, Vendor, Uraian, Kode, Item, PO/SPK/Invoice,
                   Metode Bayar, Tgl Berkas, Tgl Faktur Pajak,
                   Vol, Sat, Harga Satuan, Jumlah
      Cols P-R   — PPN (Lalu / Saat Ini / S.D Saat Ini)
      Cols S-U   — Pembayaran PPN (Lalu / Saat Ini / S.D Saat Ini)
      Col V      — Sisa PPN (= SUBTOTAL over detail Sisa PPN)
      Col W      — gap
    TGL FAKTUR PAJAK is output as a human-readable date cell next to
    TGL TERIMA. Vendor and TOTAL rows use =SUBTOTAL formulas so filtered
    sheets stay correct, matching DPP.

    project_id: None = all projects; otherwise int project id.
    Returns io.BytesIO positioned at 0.
    """
    report_rows, _ = build_ppn_data(project_id=project_id)

    now_key = month_key
    if now_key is None and report_rows:
        now_key = report_rows[-1]['key']
    mdata = next((r for r in report_rows if r['key'] == now_key), None)
    if mdata is None and report_rows:
        mdata = report_rows[-1]
    if mdata is None:
        mdata = {'label': '-', 'key': now_key or '-', 'rekanan_list': []}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_numbers': False})
    ws = wb.add_worksheet('PPN')
    _render_ppn(wb, ws, mdata, now_key, _month_key, project_id=project_id)
    wb.close()
    buf.seek(0)
    return buf


def _month_key(val):
    """Map 'YYYY-MM-DD' -> 'YYYY-MM' or None."""
    try:
        return datetime.strptime(str(val), '%Y-%m-%d').strftime('%Y-%m')
    except (ValueError, TypeError):
        return None


def _week_key_of(val):
    """Map 'YYYY-MM-DD' -> 'YYYY-Www' (Sunday-start week key) or None.

    Delegates to services.laporan._week_key so the weekly PPN export groups
    invoices into exactly the same weeks as Laporan PPN Mingguan and
    Laporan DPP Mingguan.
    """
    from services.laporan import _week_key
    try:
        return _week_key(datetime.strptime(str(val), '%Y-%m-%d'))
    except (ValueError, TypeError):
        return None


def build_ppn_mingguan_excel_export(week_key=None, project_id=None):
    """Build Excel export for Laporan PPN Mingguan.

    Identical DPP-aligned layout to the monthly PPN export; only the period
    differs (a Sunday..Saturday week, key 'YYYY-Www').

    project_id: None = all projects; otherwise int project id.
    Returns io.BytesIO positioned at 0.
    """
    report_rows, _ = build_ppn_mingguan_data(project_id=project_id)

    now_key = week_key
    if now_key is None and report_rows:
        now_key = report_rows[-1]['key']       # default: latest week
    mdata = next((r for r in report_rows if r['key'] == now_key), None)
    if mdata is None and report_rows:
        mdata = report_rows[-1]
    if mdata is None:
        mdata = {'label': '-', 'key': now_key or '-', 'rekanan_list': []}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_numbers': False})
    ws = wb.add_worksheet('PPN Mingguan')
    _render_ppn(wb, ws, mdata, now_key, _week_key_of, title_suffix=' (Mingguan)',
                project_id=project_id)
    wb.close()
    buf.seek(0)
    return buf
