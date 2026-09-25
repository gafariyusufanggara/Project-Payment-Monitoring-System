"""
MODEL — Laporan Bulanan (monthly report builder).

Pure computation over db.read_data(); no Flask, no rendering.
"""
from collections import defaultdict
from datetime import datetime, timedelta, date
import io
import re
import db
from constants import safe_float, effective_invoice


def _resolve_pay_period(pay_date_str, tgl_berkas_str, rekan_keyfn, cutoff_date=None):
    """Resolve which period a payment belongs to.

    Guarantees a payment is NEVER dropped and NEVER lands before its debt:

    * If the payment date is missing or unparseable (e.g. 'RC Divisi-12'),
      fall back to the debt date (TGL TERIMA) instead of silently discarding
      the amount — otherwise real money vanishes from the report.
    * If the payment date precedes the debt date, clamp it forward to the
      debt date so cumulative "bayar" can't exceed cumulative "hutang"
      (which would make sisa go negative and get eaten by max(0, …)).

    Returns the period key, or None when no usable anchor date exists.
    """
    def _parsed(s):
        try:
            return datetime.strptime(str(s), '%Y-%m-%d')
        except (ValueError, TypeError):
            return None

    pay_dt = _parsed(pay_date_str)
    berkas_dt = _parsed(tgl_berkas_str)

    if pay_dt is None or (berkas_dt is not None and pay_dt.date() < berkas_dt.date()):
        pay_dt = berkas_dt

    if pay_dt is None:
        return None
    if cutoff_date is not None and pay_dt.date() > cutoff_date:
        return None
    return rekan_keyfn(pay_dt)


def _build_cum(rekan_keyfn, filter_fn=None, project_id=None, cutoff_date=None):
    """Shared Pass 1 + 2: group by a period key, then compute cumulative
    per-rekanan balances across sorted periods.

    Args:
        rekan_keyfn: callable(date_str) -> period key string (e.g. '2026-07'
                     for months, or a week-id for weeks).
        filter_fn: optional callable(row_dict) -> bool; when provided, only
                   rows returning True are processed.
        project_id: optional project filter forwarded to db.read_data.
        cutoff_date: optional date/datetime; when set, only rows with
                     TGL TERIMA <= cutoff_date and TGL BAYAR DPP <= cutoff_date
                     are included.
    Returns: (rekan_cum dict, all_periods sorted list, sorted_rekan list, data)
    """
    data = db.read_data(project_id=project_id)
    from constants import is_excluded_row  # exclusion rules (Pengaturan)
    data = [r for r in data if not is_excluded_row(r)]
    if filter_fn:
        data = [r for r in data if filter_fn(r)]

    # Pass 1: group hutang by TGL BERKAS, bayar by TGL BAYAR
    hutang_rm = defaultdict(lambda: defaultdict(lambda: {'hutang': 0, 'harga_excl': 0, 'retensi': 0, 'pot_pph': 0, 'ppn': 0, 'invoices': []}))
    bayar_rm = defaultdict(lambda: defaultdict(lambda: {'bayar': 0, 'bayar_ppn': 0, 'pay_count': 0, 'paid_invs': set(), 'paid_ppn_invs': set()}))
    periods = set()
    seen_inv = set()  # (rekan, invoice) — GLOBAL dedup: one invoice = one debt

    for row in data:
        tgl_berkas = row.get('TGL TERIMA')
        if not tgl_berkas:
            continue
        try:
            dt = datetime.strptime(str(tgl_berkas), '%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        # Cutoff: skip hutang whose TGL TERIMA is after cutoff_date
        if cutoff_date is not None and dt.date() > cutoff_date:
            continue
        inv_key = rekan_keyfn(dt)

        rekan = (row.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip()
        if not rekan:
            rekan = 'Unknown'

        periods.add(inv_key)
        total = safe_float(row.get('TOTAL (INCLD)'))
        dp = safe_float(row.get('PEMBAYARAN DPP'))
        ppn_pay = safe_float(row.get('PEMBAYARAN PPN'))
        harga_excl = safe_float(row.get('HARGA (EXLD)'))
        retensi = safe_float(row.get('POT. RETENSI'))
        pot_pph = safe_float(row.get('POT. PPH'))
        ppn = safe_float(row.get('PPN'))
        po = (row.get('NO PO / KONTRAK') or '').strip()
        inv_no = effective_invoice(row)

        # Hutang by TGL BERKAS — GLOBAL dedup by (rekan, effective_invoice) so debt counted once
        rec = hutang_rm[rekan][inv_key]
        inv_dedup_key = (rekan, inv_no) if inv_no else None
        if inv_dedup_key is None or inv_dedup_key not in seen_inv:
            if inv_dedup_key:
                seen_inv.add(inv_dedup_key)
            rec['hutang'] += total
            rec['harga_excl'] += harga_excl
            rec['retensi'] += retensi
            rec['pot_pph'] += pot_pph
            rec['ppn'] += ppn
            # The invoice list is only appended on the FIRST occurrence of an
            # invoice, matching the debt dedup above. Appending every physical
            # row made the detail modal show (and sum) duplicate invoices that
            # the summary counts only once — modal totals then disagreed with
            # the report. Installment rows still contribute their payments
            # below, so no money is lost.
            rec['invoices'].append({
                'invoice': row.get('NO INVOICE') or '-',
                'po': row.get('NO PO / KONTRAK') or '-',
                'tgl_inv': str(row.get('TGL INV', '')),
                'tgl_berkas': str(row.get('TGL TERIMA', '')),
                'jth_tempo': str(row.get('JTH TEMPO', '')),
                'deskripsi': row.get('DESKRIPSI') or '-',
                'kode_biaya': row.get('KODE BIAYA2') or '-',
                'total': total,
                'bayar_dpp': dp,
                'bayar_ppn': ppn_pay,
                'tgl_bayar_dpp': str(row.get('TGL BAYAR DPP', '')),
                'tgl_bayar_ppn': str(row.get('TGL BAYAR PPN', '')),
                'sisa': safe_float(row.get('SISA HUTANG (INCLD PPN)')),
                'harga_excl': harga_excl,
                'retensi': retensi,
                'pot_pph': pot_pph,
                'ppn': ppn,
            })

        # Bayar DPP by TGL BAYAR DPP (clamped to debt date, never dropped)
        if dp > 0:
            dp_m = _resolve_pay_period(row.get('TGL BAYAR DPP'), tgl_berkas,
                                       rekan_keyfn, cutoff_date)
            if dp_m is not None:
                periods.add(dp_m)
                bayar_rm[rekan][dp_m]['bayar'] += dp
                bayar_rm[rekan][dp_m]['paid_invs'].add(str(row.get('NO INVOICE', '')))

        # Bayar PPN by TGL BAYAR PPN (clamped to debt date, never dropped)
        if ppn_pay > 0:
            ppn_m = _resolve_pay_period(row.get('TGL BAYAR PPN'), tgl_berkas,
                                        rekan_keyfn, cutoff_date)
            if ppn_m is not None:
                periods.add(ppn_m)
                bayar_rm[rekan][ppn_m]['bayar_ppn'] += ppn_pay
                bayar_rm[rekan][ppn_m]['paid_ppn_invs'].add(str(row.get('NO INVOICE', '')))

    all_periods = sorted(periods)
    sorted_rekan = sorted(set(hutang_rm.keys()) | set(bayar_rm.keys()))

    # Pass 2: cumulative per rekanan across all periods
    rekan_cum = {}
    for rekan in sorted_rekan:
        ch, cb = 0, 0               # ch = cumulative HARGA(EXLD), cb = cumulative PEMBAYARAN DPP
        chx, cret, cpph, cppn = 0, 0, 0, 0  # cumulative harga_excl, retensi, pot_pph, ppn
        cbp, cbpn = 0, 0            # cumulative bayar_dpp, bayar_ppn
        for pk in all_periods:
            lalu_h, lalu_b = ch, cb
            lalu_ppn, lalu_bayar_ppn = cppn, cbpn
            h_rec = hutang_rm[rekan].get(pk)
            b_rec = bayar_rm[rekan].get(pk)

            if h_rec:
                ch += h_rec['harga_excl']
                chx += h_rec['harga_excl']
                cret += h_rec['retensi']
                cpph += h_rec['pot_pph']
                cppn += h_rec['ppn']
            if b_rec:
                cb += b_rec['bayar']
                cbp += b_rec['bayar']
                cbpn += b_rec['bayar_ppn']

            # Dynamic sisa: cumulative harga_excl - pot_pph - bayar_dpp (by date)
            sisa_dpp = max(0, chx - cbp)
            sisa_ppn = max(0, cppn - cbpn)

            si_bayar = b_rec['bayar'] if b_rec else 0
            si_bayar_ppn = b_rec['bayar_ppn'] if b_rec else 0
            rekan_cum[(rekan, pk)] = {
                'lalu_hutang': lalu_h,
                'saat_ini_hutang': h_rec['harga_excl'] if h_rec else 0,
                'sd_hutang': ch,
                'lalu_bayar': lalu_b,
                'saat_ini_bayar': si_bayar,
                'sd_bayar': cb,
                'lalu_ppn': lalu_ppn,
                'saat_ini_ppn': h_rec['ppn'] if h_rec else 0,
                'sd_ppn': cppn,
                'lalu_bayar_ppn': lalu_bayar_ppn,
                'saat_ini_bayar_ppn': si_bayar_ppn,
                'sd_bayar_ppn': cbpn,
                'invoices': h_rec['invoices'] if h_rec else [],
                'count': len(h_rec['invoices']) if h_rec else 0,
                'pay_count': len(b_rec['paid_invs']) if b_rec else 0,
                'ppn_pay_count': len(b_rec['paid_ppn_invs']) if b_rec else 0,
                'sisa_dpp': sisa_dpp,
                'sisa_ppn': sisa_ppn,
            }

    return rekan_cum, all_periods, sorted_rekan, data


def build_laporan_data(project_id=None, cutoff_date=None):
    """Compute the full laporan dataset (monthly periods). Returns (report_rows, data_count).

    project_id: optional project filter forwarded to db.read_data.
    cutoff_date: optional date/datetime; when set, only data up to this date is included.
    """
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                   'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']

    # Month key: 'YYYY-MM'
    def month_keyfn(dt):
        return dt.strftime('%Y-%m')

    rekan_cum, all_months, sorted_rekan, data = _build_cum(month_keyfn, project_id=project_id, cutoff_date=cutoff_date)

    # Ensure current month is included so empty months still show carried-forward balances
    now_key = datetime.now().strftime('%Y-%m')
    if now_key not in all_months:
        all_months = sorted(all_months + [now_key])

    # Pass 3: build per-month report
    report_rows = []
    vendor_last = {}  # tracks the most recent rc per rekan for empty-month fallback
    for mk in all_months:
        y, m = mk.split('-')
        label = f'{month_names[int(m)]} {y}'

        rekanan_list = []
        tot_lalu_hutang = tot_saat_ini_hutang = tot_sd_hutang = 0
        tot_lalu_bayar = tot_saat_ini_bayar = tot_sd_bayar = 0
        tot_sisa_dpp = 0
        tot_sisa_ppn = 0
        month_total_count = 0
        month_total_pay_count = 0

        for rekan in sorted_rekan:
            key = (rekan, mk)
            rc = rekan_cum.get(key)
            if rc is None:
                # Fall back to last known cumulative state for empty months
                last = vendor_last.get(rekan)
                if last is None:
                    continue
                rc = {
                    'lalu_hutang': last['sd_hutang'],
                    'saat_ini_hutang': 0,
                    'sd_hutang': last['sd_hutang'],
                    'lalu_bayar': last['sd_bayar'],
                    'saat_ini_bayar': 0,
                    'sd_bayar': last['sd_bayar'],
                    'lalu_ppn': last['sd_ppn'],
                    'saat_ini_ppn': 0,
                    'sd_ppn': last['sd_ppn'],
                    'lalu_bayar_ppn': last['sd_bayar_ppn'],
                    'saat_ini_bayar_ppn': 0,
                    'sd_bayar_ppn': last['sd_bayar_ppn'],
                    'invoices': [],
                    'count': 0,
                    'pay_count': 0,
                    'ppn_pay_count': 0,
                    'sisa_dpp': last['sisa_dpp'],
                    'sisa_ppn': last['sisa_ppn'],
                }
            else:
                vendor_last[rekan] = rc
            # Skip vendors whose first invoice hasn't happened yet.
            if rc['sd_hutang'] == 0 and rc['sd_bayar'] == 0:
                continue

            tot_lalu_hutang += rc['lalu_hutang']
            tot_saat_ini_hutang += rc['saat_ini_hutang']
            tot_sd_hutang += rc['sd_hutang']
            tot_lalu_bayar += rc['lalu_bayar']
            tot_saat_ini_bayar += rc['saat_ini_bayar']
            tot_sd_bayar += rc['sd_bayar']
            tot_sisa_dpp += rc['sisa_dpp']
            tot_sisa_ppn += rc['sisa_ppn']

            # Include EVERY vendor that has any history up to/in this month, even
            # those with no new hutang/bayar activity this period (Lalu-only rows).
            # Footer totals then equal kpi.* (TOTAL HUTANG LALU / TOTAL BAYAR LALU).
            sisa = rc['sd_hutang'] - rc['sd_bayar']
            sisa_dpp = rc['sisa_dpp']
            sisa_ppn = rc['sisa_ppn']
            rekanan_list.append({
                'rekanan': rekan,
                'lalu_hutang': rc['lalu_hutang'],
                'saat_ini_hutang': rc['saat_ini_hutang'],
                'sd_hutang': rc['sd_hutang'],
                'lalu_bayar': rc['lalu_bayar'],
                'saat_ini_bayar': rc['saat_ini_bayar'],
                'sd_bayar': rc['sd_bayar'],
                'sisa': sisa,
                'sisa_dpp': sisa_dpp,
                'sisa_ppn': sisa_ppn,
                'invoices': rc['invoices'],
                'count': rc['count'],
                'pay_count': rc['pay_count'],
            })
            month_total_count += rc['count']
            month_total_pay_count += rc['pay_count']

        tot_sisa = tot_sd_hutang - tot_sd_bayar

        report_rows.append({
            'key': mk,
            'label': label,
            'rekanan_list': rekanan_list,
            'total_hutang': tot_saat_ini_hutang,
            'total_bayar': tot_saat_ini_bayar,
            'total_count': month_total_count,
            'total_pay_count': month_total_pay_count,
            'kpi': {
                'lalu_hutang': tot_lalu_hutang,
                'saat_ini_hutang': tot_saat_ini_hutang,
                'sd_hutang': tot_sd_hutang,
                'lalu_bayar': tot_lalu_bayar,
                'saat_ini_bayar': tot_saat_ini_bayar,
                'sd_bayar': tot_sd_bayar,
                'sisa': tot_sisa,
                'sisa_dpp': tot_sisa_dpp,
                'sisa_ppn': tot_sisa_ppn,
            },
        })

    return report_rows, len(data)


def _week_key(dt):
    """Return 'YYYY-Www' week id where a week STARTS on Sunday and ENDS on
    Saturday. The id uses the Monday-based ISO year/week of the Tuesday inside
    the (Sun..Sat) week, so consecutive weeks sort correctly."""
    # Convert to Sun=0..Sat=6, then find Sunday of this Sun-Sat week.
    sun_sat_wd = (dt.weekday() + 1) % 7          # Sun=0, Mon=1, …, Sat=6
    sunday = dt - timedelta(days=sun_sat_wd)      # Sunday of this week
    tuesday = sunday + timedelta(days=2)           # anchor inside the same week
    iso_year, iso_week, _ = tuesday.isocalendar()
    return f'{iso_year}-W{iso_week:02d}'


def build_mingguan_data(project_id=None):
    """Compute the weekly laporan dataset (period = Sunday..Saturday week).

    Same formulas as the monthly report, but grouped by week instead of month.
    project_id: optional project filter forwarded to db.read_data.
    Returns (report_rows, data_count).
    """
    def week_keyfn(dt):
        return _week_key(dt)

    rekan_cum, all_weeks, sorted_rekan, data = _build_cum(week_keyfn, project_id=project_id)

    # Ensure current week is included so empty weeks still show vendor data
    today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    wd       = (today.weekday() + 1) % 7   # Sun=0
    cur_sun  = today - timedelta(days=wd)
    cur_wk   = _week_key(cur_sun)
    if cur_wk not in all_weeks:
        all_weeks = sorted(all_weeks + [cur_wk])

    # Pass 3: build per-week report (week starts Sunday, closes Saturday)
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                   'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    report_rows = []
    vendor_last = {}  # tracks the most recent rc per rekan for empty-week fallback
    for wk in all_weeks:
        iso_year, wnum = wk.split('-W')
        # Monday of this ISO week, then back to its Sunday (week start)
        monday = datetime.fromisocalendar(int(iso_year), int(wnum), 1)
        start = monday - timedelta(days=1)   # Sunday
        end = start + timedelta(days=6)        # Saturday
        label = f'{start:%d %b}–{end:%d %b %Y}'
        # Calendar month/year this week belongs to = its closing Saturday's month.
        year = end.year
        month = end.month

        rekanan_list = []
        tot_lalu_hutang = tot_saat_ini_hutang = tot_sd_hutang = 0
        tot_lalu_bayar = tot_saat_ini_bayar = tot_sd_bayar = 0
        tot_sisa_dpp = 0
        tot_sisa_ppn = 0
        month_total_count = 0
        month_total_pay_count = 0

        for rekan in sorted_rekan:
            rc = rekan_cum.get((rekan, wk))
            if rc is None:
                # Fall back to last known cumulative state for empty weeks
                last = vendor_last.get(rekan)
                if last is None:
                    continue
                rc = {
                    'lalu_hutang': last['sd_hutang'],
                    'saat_ini_hutang': 0,
                    'sd_hutang': last['sd_hutang'],
                    'lalu_bayar': last['sd_bayar'],
                    'saat_ini_bayar': 0,
                    'sd_bayar': last['sd_bayar'],
                    'invoices': [],
                    'count': 0,
                    'pay_count': 0,
                    'sisa_dpp': last['sisa_dpp'],
                    'sisa_ppn': last['sisa_ppn'],
                }
            else:
                vendor_last[rekan] = rc
            # Skip vendors whose first invoice hasn't happened yet.
            # sd_hutang==0 AND sd_bayar==0 means no cumulative activity
            # before or during this week → vendor hasn't started.
            if rc['sd_hutang'] == 0 and rc['sd_bayar'] == 0:
                continue

            tot_lalu_hutang += rc['lalu_hutang']
            tot_saat_ini_hutang += rc['saat_ini_hutang']
            tot_sd_hutang += rc['sd_hutang']
            tot_lalu_bayar += rc['lalu_bayar']
            tot_saat_ini_bayar += rc['saat_ini_bayar']
            tot_sd_bayar += rc['sd_bayar']
            tot_sisa_dpp += rc['sisa_dpp']
            tot_sisa_ppn += rc['sisa_ppn']

            # Include EVERY vendor with any history up to/in this week (Lalu-only rows),
            # so totals match the KPI cumulative values.
            sisa = rc['sd_hutang'] - rc['sd_bayar']
            sisa_dpp = rc['sisa_dpp']
            sisa_ppn = rc['sisa_ppn']
            rekanan_list.append({
                'rekanan': rekan,
                'lalu_hutang': rc['lalu_hutang'],
                'saat_ini_hutang': rc['saat_ini_hutang'],
                'sd_hutang': rc['sd_hutang'],
                'lalu_bayar': rc['lalu_bayar'],
                'saat_ini_bayar': rc['saat_ini_bayar'],
                'sd_bayar': rc['sd_bayar'],
                'sisa': sisa,
                'sisa_dpp': sisa_dpp,
                'sisa_ppn': sisa_ppn,
                'invoices': rc['invoices'],
                'count': rc['count'],
                'pay_count': rc['pay_count'],
            })
            month_total_count += rc['count']
            month_total_pay_count += rc['pay_count']

        tot_sisa = tot_sd_hutang - tot_sd_bayar

        report_rows.append({
            'key': wk,
            'label': label,
            'year': year,
            'month': month,
            'rekanan_list': rekanan_list,
            'total_hutang': tot_saat_ini_hutang,
            'total_bayar': tot_saat_ini_bayar,
            'total_count': month_total_count,
            'total_pay_count': month_total_pay_count,
            'kpi': {
                'lalu_hutang': tot_lalu_hutang,
                'saat_ini_hutang': tot_saat_ini_hutang,
                'sd_hutang': tot_sd_hutang,
                'lalu_bayar': tot_lalu_bayar,
                'saat_ini_bayar': tot_saat_ini_bayar,
                'sd_bayar': tot_sd_bayar,
                'sisa': tot_sisa,
                'sisa_dpp': tot_sisa_dpp,
                'sisa_ppn': tot_sisa_ppn,
            },
        })

    # ── Fill missing calendar weeks so every Sun-Sat week appears ──
    if report_rows:
        def _sun_of_key(k):
            """Return the Sunday (datetime) for week key 'YYYY-Www'."""
            y, w = k.split('-W')
            mon = datetime.fromisocalendar(int(y), int(w), 1)
            return mon - timedelta(days=1)

        first_sun = _sun_of_key(report_rows[0]['key'])
        last_sun  = _sun_of_key(report_rows[-1]['key'])
        # Extend to cover current week so the button always appears
        today    = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        wd       = (today.weekday() + 1) % 7   # Sun=0
        cur_sun  = today - timedelta(days=wd)
        if cur_sun > last_sun:
            last_sun = cur_sun
        existing  = {r['key'] for r in report_rows}

        # Build lookup: report row by key
        report_by_key = {r['key']: r for r in report_rows}

        cursor = first_sun
        # Track the nearest prior real-week snapshot for fill carry-forward
        last_real = None
        last_kpi = {}
        last_rekan_list = []
        while cursor <= last_sun:
            wk = _week_key(cursor)
            real_row = report_by_key.get(wk)
            if real_row is not None:
                # This is a real data week — update snapshot for subsequent fills
                last_real = real_row
                last_kpi = real_row['kpi']
                last_rekan_list = real_row['rekanan_list']
                # Snapshot per vendor with NO new activity (filled weeks are
                # calendar gaps, not real periods). Copying (not aliasing) keeps
                # invoices from being re-counted as if they were received again.
                fill_list = []
                for _v in last_rekan_list:
                    _c = dict(_v)
                    _c['invoices'] = []
                    _c['count'] = 0
                    _c['pay_count'] = 0
                    fill_list.append(_c)
                last_rekan_list = fill_list
            elif wk not in existing:
                end   = cursor + timedelta(days=6)
                label = f'{cursor:%d %b}–{end:%d %b %Y}'
                # Carry forward last known cumulative totals, zero new-activity fields.
                # Uses the nearest prior real week (not the chronologically last one).
                report_rows.append({
                    'key': wk,
                    'label': label,
                    'year': end.year,
                    'month': end.month,
                    'rekanan_list': last_rekan_list,
                    'total_hutang': 0,
                    'total_bayar': 0,
                    'total_count': 0,
                    'total_pay_count': 0,
                    'kpi': {
                        'lalu_hutang': last_kpi.get('sd_hutang', 0),
                        'saat_ini_hutang': 0,
                        'sd_hutang': last_kpi.get('sd_hutang', 0),
                        'lalu_bayar': last_kpi.get('sd_bayar', 0),
                        'saat_ini_bayar': 0,
                        'sd_bayar': last_kpi.get('sd_bayar', 0),
                        'sisa': last_kpi.get('sd_hutang', 0) - last_kpi.get('sd_bayar', 0),
                        'sisa_dpp': last_kpi.get('sisa_dpp', 0),
                        'sisa_ppn': last_kpi.get('sisa_ppn', 0),
                    },
                })
                existing.add(wk)
            cursor += timedelta(days=7)

        report_rows.sort(key=lambda r: r['key'])

    return report_rows, len(data)


def _month_of(val):
    """Map 'YYYY-MM-DD' -> 'YYYY-MM' (month key)."""
    try:
        return datetime.strptime(str(val), '%Y-%m-%d').strftime('%Y-%m')
    except (ValueError, TypeError):
        return None


def _week_of(val):
    """Map 'YYYY-MM-DD' -> 'YYYY-Www' (Sunday-start week key)."""
    try:
        return _week_key(datetime.strptime(str(val), '%Y-%m-%d'))
    except (ValueError, TypeError):
        return None


def _po_sort_key(val):
    s = (val or '').strip()
    if not s:
        return ('',)
    parts = re.split(r'(\d+)', s)
    out = []
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            out.append(p.zfill(10))
        else:
            out.append(p.lower())
    return tuple(out)  # ponytail: fixed 10-digit pad; upgrade to max-len scan if PO numbers exceed 10 digits


def _col_letter(col):
    """0-based column index -> Excel letter(s): 0 -> 'A', 26 -> 'AA'."""
    s = ''
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return s


# Columns on a vendor row that carry a SUBTOTAL over that vendor's invoice rows.
# 15..22 = Lalu/Saat Ini/S.D (hutang & bayar), Sisa, Retensi; 24..25 = PPN, PPH.
# Col 23 is the blank spacer between Retensi and PPN and is deliberately excluded.
VENDOR_SUBTOTAL_COLS = (15, 16, 17, 18, 19, 20, 21, 22, 24, 25)


def _render_lbp(wb, ws, mdata, now_key, period_of, title_suffix='', project_id=None):
    """Shared LBP sheet renderer for monthly & weekly exports.

    Renders the selected period as a wide hierarchical table: one summary row
    per vendor (Lalu / Saat Ini / S.D Saat Ini for both hutang & bayar) plus one
    detail row per invoice, classified into Lalu vs Saat Ini using ``period_of``.
    Vendor rows are shaded so the reader can tell which data belongs to which.

    Args:
        wb: xlsxwriter Workbook (formats are registered here).
        ws: xlsxwriter Worksheet (already added, named 'LBP').
        mdata: selected period row dict (build_laporan_data / build_mingguan_data).
        now_key: period key string used to classify detail rows (== mdata['key']).
        period_of: callable('YYYY-MM-DD') -> period key, matching now_key's scheme.
        title_suffix: extra text appended to the big title (e.g. ' (Mingguan)').
    """
    # Full invoice history per rekan (detail rows) — deduped so detail rows match vendor summary.
    from services.dashboard import _dedup_debt_rows
    hist = defaultdict(list)
    for row in _dedup_debt_rows(db.read_data(project_id=project_id)):
        rekan = (row.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip() or 'Unknown'
        hist[rekan].append(row)

    # _resolve_pay_period hands its key function a datetime, while period_of
    # ('%Y-%m-%d' string -> key) takes a string. Without this adapter every
    # call returned None and payments silently fell back to their raw date.
    def period_of_dt(dt):
        return period_of(dt.strftime('%Y-%m-%d'))

    # ── Formats ───────────────────────────────────────────
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
    # Accounting (no symbol), no decimals: positives plain, negatives in parens.
    acct = '#,##0_);(#,##0);-'
    # Plain text/blank cells: no number format, so a stray value can never
    # inherit a currency mask it doesn't belong to.
    cell_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter',
                              'align': 'right'})
    vol_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter',
                             'align': 'right', 'num_format': '#,##0.00'})
    cell_l_fmt = wb.add_format({'font_size': 9, 'border': 1, 'valign': 'vcenter', 'align': 'left'})
    cell_money_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                                    'valign': 'vcenter', 'align': 'right'})
    num_h_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                               'font_color': '#1e40af', 'valign': 'vcenter', 'align': 'right'})
    num_p_fmt = wb.add_format({'font_size': 9, 'num_format': acct, 'border': 1,
                               'font_color': '#15803d', 'valign': 'vcenter', 'align': 'right'})
    sisa_pos_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': acct,
                                  'border': 1, 'font_color': '#dc2626',
                                  'valign': 'vcenter', 'align': 'right'})
    sisa_zero_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': acct,
                                   'border': 1, 'font_color': '#10b981',
                                   'valign': 'vcenter', 'align': 'right'})
    total_label_fmt = wb.add_format({'bold': True, 'font_size': 9, 'border': 1,
                                     'bg_color': '#f8fafc', 'valign': 'vcenter', 'align': 'left'})
    total_fmt = wb.add_format({'bold': True, 'font_size': 9, 'num_format': acct,
                               'border': 1, 'bg_color': '#f8fafc',
                               'valign': 'vcenter', 'align': 'right'})
    note_fmt = wb.add_format({'font_size': 7, 'font_color': '#94a3b8', 'italic': True})
    gap_fmt = wb.add_format({'font_size': 9, 'valign': 'vcenter', 'align': 'right'})

    # ── Vendor banding (alternating tints) ──────────────
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

    # ── Column widths (24 cols, starting at col C) ──
    # Item column inserted after Uraian, before Kode RBK/ERP.
    # Tgl Jatuh Tempo inserted after Tgl Berkas Lengkap.
    widths = [4, 26, 36, 14, 14, 16, 16, 14, 11, 6, 5, 14, 16, 13, 13, 14, 13, 13, 14, 14, 14, 6, 14, 14]
    for i, w in enumerate(widths):
        ws.set_column(2 + i, 2 + i, w)

    row = 0

    # ── Title row 4 (0-based row 3) spans C..Z (cols 2..25) ──
    ws.merge_range(3, 2, 3, 25,
        f'REKAP PRESTASI UTANG & PEMBAYARAN UTANG — {mdata["label"]}{title_suffix}', title_fmt)
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
    ws.merge_range(hr, 10, hr+1, 10, 'Tgl Jatuh\nTempo', hdr_fmt)
    ws.merge_range(hr, 11, hr+1, 11, 'Vol', hdr_fmt)
    ws.merge_range(hr, 12, hr+1, 12, 'Sat', hdr_fmt)
    ws.merge_range(hr, 13, hr+1, 13, 'Harga Satuan', hdr_fmt)
    ws.merge_range(hr, 14, hr+1, 14, 'Jumlah', hdr_fmt)
    ws.merge_range(hr, 15, hr, 17, 'Prestasi Utang', grp_h_fmt)
    ws.merge_range(hr, 18, hr, 20, 'Pembayaran Utang', grp_p_fmt)
    ws.merge_range(hr, 21, hr+1, 21, 'Sisa Hutang Total\n(DPP)', hdr_fmt)
    ws.merge_range(hr, 22, hr+1, 22, 'Retensi', hdr_fmt)
    ws.merge_range(hr, 23, hr+1, 23, '', gap_fmt)
    ws.merge_range(hr, 24, hr+1, 24, 'PPN', hdr_fmt)
    ws.merge_range(hr, 25, hr+1, 25, 'PPH', hdr_fmt)
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
    t_lalu_h = t_si_h = 0
    t_lalu_p = t_si_p = 0
    t_sisa = 0
    t_retensi = 0
    t_ppn = 0
    t_pph = 0
    no = 0

    # Vendor rows are emitted first and remembered in ``vendor_rows``; their
    # SUBTOTAL range can only be written once the invoice rows that follow them
    # are on the sheet and we know where each block ends.
    vendor_rows = []

    for idx, s in enumerate(mdata['rekanan_list']):
        rekan = s['rekanan']

        # ponytail: skip vendors whose first invoice is after selected period
        # (sd_hutang==0 and sd_bayar==0 means no activity up to now_key)
        if s['sd_hutang'] == 0 and s['sd_bayar'] == 0:
            continue

        no += 1
        even = (idx % 2 == 0)
        bf = band_even_fmt if even else band_odd_fmt        # numeric
        blf = band_even_l_fmt if even else band_odd_l_fmt   # label

        # Retensi cumulative for this vendor from detail invoices (up to selected period)
        ret_vendor = sum(
            safe_float(inv.get('POT. RETENSI'))
            for inv in hist.get(rekan, [])
            if (period_of(inv.get('TGL TERIMA')) or '') <= now_key
        )

        # ── Vendor summary row (shaded band) ────────────
        vrow = row
        ws.write(row, 2, no, bf)
        ws.write(row, 3, rekan, blf)
        for c in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
            ws.write(row, c, '', bf)
        # Money columns become =SUBTOTAL(109, …) once the detail block is known.
        for c in VENDOR_SUBTOTAL_COLS:
            ws.write(row, c, None, bf)
        ws.write(row, 23, '', gap_fmt)
        row += 1

        t_lalu_h += s['lalu_hutang']; t_si_h += s['saat_ini_hutang']
        t_lalu_p += s['lalu_bayar']; t_si_p += s['saat_ini_bayar']
        t_sisa += max(0, (s['lalu_hutang'] + s['saat_ini_hutang']) - (s['lalu_bayar'] + s['saat_ini_bayar']))
        vendor_rows.append((vrow, rekan, s, ret_vendor, bf))

        # ── Detail rows (per invoice) — only invoices up to selected period ──
        for inv in sorted(hist.get(rekan, []), key=lambda r: (_po_sort_key(r.get('NO PO / KONTRAK')), str(r.get('TGL TERIMA') or '9999-99-99'))):
            inv_m = period_of(inv.get('TGL TERIMA'))
            if inv_m and inv_m > now_key:
                continue
            dp = safe_float(inv.get('PEMBAYARAN DPP'))
            harga_excl = safe_float(inv.get('HARGA (EXLD)'))
            pot_pph = safe_float(inv.get('POT. PPH'))
            ppn = safe_float(inv.get('PPN'))
            pay_m = period_of(inv.get('TGL BAYAR DPP'))

            ws.write(row, 2, '', cell_fmt)
            ws.write(row, 3, '', cell_fmt)
            ws.write(row, 4, inv.get('DESKRIPSI') or '-', cell_l_fmt)
            ws.write(row, 5, inv.get('KODE BIAYA2') or '', cell_l_fmt)
            ws.write(row, 6, '', cell_fmt)      # Item — empty, manual input
            ws.write(row, 7, inv.get('NO PO / KONTRAK') or inv.get('NO INVOICE') or '', cell_l_fmt)
            ws.write(row, 8, inv.get('PEMBAYARAN DPP VIA DIVISI') or '', cell_l_fmt)
            ws.write(row, 9, inv.get('TGL TERIMA') or '', cell_l_fmt)
            ws.write(row, 10, inv.get('JTH TEMPO') or '', cell_l_fmt)
            vol = safe_float(inv.get('VOLUME PROGRESS'))
            harga_satuan = safe_float(inv.get('HARGA SATUAN'))
            ws.write(row, 11, vol if vol else '', vol_fmt)
            ws.write(row, 12, '', cell_fmt)      # Sat — no source column
            ws.write(row, 13, harga_satuan, num_h_fmt)
            ws.write(row, 14, harga_satuan * vol, num_h_fmt)

            # Hutang: classify by TGL TERIMA vs selected period, use HARGA(EXLD)
            h_lalu = h_si = 0.0
            if harga_excl:
                if inv_m == now_key:
                    h_si = harga_excl
                elif inv_m and inv_m < now_key:
                    h_lalu = harga_excl
            ws.write(row, 15, h_lalu, num_h_fmt)
            ws.write(row, 16, h_si, num_h_fmt)
            ws.write(row, 17, h_lalu + h_si, num_h_fmt)

            # Pembayaran: DPP by TGL BAYAR DPP.
            # Resolved through _resolve_pay_period — the SAME helper the vendor
            # summary uses — so a payment dated before its invoice (down payment)
            # is clamped to the debt date instead of landing in an earlier period.
            # Using period_of(TGL BAYAR DPP) directly made the detail rows
            # disagree with the vendor row for those invoices.
            # Classify via _resolve_pay_period — the same helper the vendor
            # summary uses. A payment dated BEFORE its invoice (down payment) is
            # clamped forward to the debt period; comparing TGL BAYAR DPP raw
            # put that money in an earlier period, so the detail rows disagreed
            # with the vendor row and with the cumulative "bayar" totals.
            p_lalu = p_si = 0.0
            if dp > 0:
                resolved_m = _resolve_pay_period(inv.get('TGL BAYAR DPP'),
                                                 inv.get('TGL TERIMA'),
                                                 period_of_dt)
                if resolved_m is None:
                    resolved_m = pay_m
                if resolved_m == now_key:
                    p_si = dp
                elif resolved_m and resolved_m < now_key:
                    p_lalu = dp
            ws.write(row, 18, p_lalu, num_p_fmt)
            ws.write(row, 19, p_si, num_p_fmt)
            ws.write(row, 20, p_lalu + p_si, num_p_fmt)
            ws.write(row, 21, max(0, (h_lalu + h_si) - (p_lalu + p_si)), cell_money_fmt)
            retensi = safe_float(inv.get('POT. RETENSI'))
            ws.write(row, 22, retensi, cell_money_fmt)
            ws.write(row, 23, '', gap_fmt)
            ws.write(row, 24, ppn, cell_money_fmt)
            ws.write(row, 25, pot_pph, cell_money_fmt)
            t_ppn += ppn
            t_pph += pot_pph
            t_retensi += retensi
            row += 1

    # ── Fill vendor SUBTOTAL formulas ───────────────────
    # Each vendor row aggregates exactly its own invoice rows (the block that
    # was written between this vendor row and the next one / the end of data).
    # SUBTOTAL(109, …) ignores rows hidden by a filter, so collapsing a vendor
    # or filtering the sheet keeps the numbers right.
    for i, (vrow, rekan, s, ret_vendor, bf) in enumerate(vendor_rows):
        block_end = vendor_rows[i + 1][0] - 1 if i + 1 < len(vendor_rows) else row - 1
        first = vrow + 1           # first invoice row of this vendor
        if block_end < first:
            # Vendor with no invoice rows: a SUBTOTAL over an inverted range
            # would emit #REF!, so fall back to the computed static figure.
            ws.write(vrow, 15, s['lalu_hutang'], bf)
            ws.write(vrow, 16, s['saat_ini_hutang'], bf)
            ws.write(vrow, 17, s['lalu_hutang'] + s['saat_ini_hutang'], bf)
            ws.write(vrow, 18, s['lalu_bayar'], bf)
            ws.write(vrow, 19, s['saat_ini_bayar'], bf)
            ws.write(vrow, 20, s['lalu_bayar'] + s['saat_ini_bayar'], bf)
            ws.write(vrow, 21, max(0, (s['lalu_hutang'] + s['saat_ini_hutang']) - (s['lalu_bayar'] + s['saat_ini_bayar'])), bf)
            ws.write(vrow, 22, ret_vendor, bf)
            ws.write(vrow, 24, 0, bf)
            ws.write(vrow, 25, 0, bf)
            continue
        for c in VENDOR_SUBTOTAL_COLS:
            L = _col_letter(c)
            ws.write_formula(
                vrow, c,
                f'=SUBTOTAL(109,{L}{first + 1}:{L}{block_end + 1})',
                bf,
            )

    # ── TOTAL row ───────────────────────────────────────
    # SUM over the vendor subtotal cells only. Using plain =SUM() here would
    # double-count, because the vendor cells already aggregate the invoice rows
    # sitting inside the same column range. The SUBTOTAL(103,OFFSET(...)) term
    # is a per-row visibility test, so hidden/filtered-out vendors are excluded
    # just like the subtotals themselves are.
    ws.write(row, 2, '', total_label_fmt)
    ws.merge_range(row, 3, row, 14, 'TOTAL', total_label_fmt)
    if vendor_rows:
        v_first = vendor_rows[0][0] + 1          # 1-based first vendor row
        v_last = vendor_rows[-1][0] + 1          # 1-based last vendor row
        for c in VENDOR_SUBTOTAL_COLS:
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
        for c in VENDOR_SUBTOTAL_COLS:
            ws.write(row, c, 0, total_fmt)
    ws.write(row, 23, '', gap_fmt)
    row += 1
# ── Footer note (removed per user request) ──────────



def build_excel_export(month_key=None, project_id=None):
    """Build the monthly LBP (Rekap Prestasi Utang & Pembayaran Utang) Excel report.

    Renders the selected month (default: current month) via the shared
    ``_render_lbp`` renderer. project_id filters the data. Returns io.BytesIO positioned at 0.
    """
    import xlsxwriter

    report_rows, _ = build_laporan_data(project_id=project_id)
    now_key = month_key or datetime.now().strftime('%Y-%m')
    mdata = next((r for r in report_rows if r['key'] == now_key), None)
    if mdata is None and report_rows:
        mdata = report_rows[-1]   # fallback: latest available month
    if mdata is None:
        mdata = {'label': '-', 'key': now_key, 'rekanan_list': []}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_numbers': False})
    ws = wb.add_worksheet('LBP')
    _render_lbp(wb, ws, mdata, now_key, _month_of, project_id=project_id)
    wb.close()
    buf.seek(0)
    return buf


def build_weekly_excel_export(week_key=None, project_id=None):
    """Build the weekly LBP (Rekap Prestasi Utang & Pembayaran Utang) Excel report.

    Same layout as the monthly export, but the period is a Sunday..Saturday week
    (key 'YYYY-Www'), classified per invoice via ``_week_of``. project_id filters the
    data. Defaults to the latest available week when no ``week_key`` is supplied. Returns io.BytesIO.
    """
    import xlsxwriter

    report_rows, _ = build_mingguan_data(project_id=project_id)
    now_key = week_key
    if now_key is None and report_rows:
        now_key = report_rows[-1]['key']   # default: latest week
    mdata = next((r for r in report_rows if r['key'] == now_key), None)
    if mdata is None and report_rows:
        mdata = report_rows[-1]
    if mdata is None:
        mdata = {'label': '-', 'key': now_key or '-', 'rekanan_list': []}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {'in_memory': True, 'strings_to_numbers': False})
    ws = wb.add_worksheet('LBP')
    _render_lbp(wb, ws, mdata, now_key, _week_of, title_suffix=' (Mingguan)', project_id=project_id)
    wb.close()
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════════════════════
# LAPORAN JATUH TEMPO
# ═══════════════════════════════════════════════════════════════

def _jt_status(hari_lebih, sisa_dpp):
    """Human-readable jatuh tempo status.

    Returns (label, key) where key drives color coding:
      overdue   — unpaid, past due          → 'Telat +N hari'
      due_today — unpaid, due today         → 'Jatuh Tempo Hari Ini'
      not_due   — unpaid, future due        → 'Belum JT (N hari lagi)'
      paid_late — paid after due date       → 'Lunas Telat +N hari'
      paid_ok   — paid on/before due date   → 'Lunas Tepat Waktu'
    """
    h = hari_lebih or 0
    if sisa_dpp > 0:
        if h > 0:
            return f'Telat +{h} hari', 'overdue'
        if h == 0:
            return 'Jatuh Tempo Hari Ini', 'due_today'
        return f'Belum JT ({-h} hari lagi)', 'not_due'
    if h > 0:
        return f'Lunas Telat +{h} hari', 'paid_late'
    return 'Lunas Tepat Waktu', 'paid_ok'


def build_jatuh_tempo_data(project_id=None):
    """Group invoices by JTH TEMPO month, then by rekanan.

    project_id: optional project filter forwarded to db.read_data.
    Returns (report_rows, data_count) where each report row is:
        { 'key': 'YYYY-MM', 'label': 'Jan 2026', 'rekanan_list': [...] }

    Each rekanan entry:
        { 'rekanan': str, 'invoices': [...], 'total': int, 'count': int }
    """
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                   'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    data = db.read_data(project_id=project_id)
    from constants import is_excluded_row  # exclusion rules (Pengaturan)
    data = [r for r in data if not is_excluded_row(r)]
    today = date.today()
    valid_count = 0

    # Group by JTH TEMPO month → rekanan → invoices
    jt_months = defaultdict(lambda: defaultdict(list))
    seen_inv = set()  # (rekan, invoice) — GLOBAL dedup: one invoice = one debt

    for row in data:
        jth = row.get('JTH TEMPO')
        if not jth:
            continue
        try:
            dt = datetime.strptime(str(jth), '%Y-%m-%d')
            mk = dt.strftime('%Y-%m')
        except (ValueError, TypeError):
            continue
        valid_count += 1

        rekan = (row.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip()
        if not rekan:
            rekan = 'Unknown'

        po = (row.get('NO PO / KONTRAK') or '-').strip()
        inv_no = effective_invoice(row)
        inv_key = (rekan, inv_no) if inv_no else None

        # Dedup debt values globally by (rekan, invoice) so debt counted once
        if inv_key and inv_key in seen_inv:
            total = 0
            harga_excl = 0
            pot_pph = 0
            ppn = 0
        else:
            if inv_key:
                seen_inv.add(inv_key)
            total = safe_float(row.get('TOTAL (INCLD)'))
            harga_excl = safe_float(row.get('HARGA (EXLD)'))
            pot_pph = safe_float(row.get('POT. PPH'))
            ppn = safe_float(row.get('PPN'))

        dp = safe_float(row.get('PEMBAYARAN DPP'))
        ppn_pay = safe_float(row.get('PEMBAYARAN PPN'))
        # Dynamic sisa per invoice (not relying on static DB calc)
        sisa_dpp = round(max(0, harga_excl - dp))
        sisa_ppn = round(max(0, ppn - ppn_pay))

        # Overdue days: today - JTH TEMPO (positive = overdue)
        hari_lebih = 0
        try:
            jt_dt = datetime.strptime(str(jth), '%Y-%m-%d').date()
            if sisa_dpp > 0:
                # Still owes → overdue from JTH TEMPO until today
                hari_lebih = (today - jt_dt).days
            else:
                # Fully paid → overdue from JTH TEMPO until payment date
                tgl_bayar = row.get('TGL BAYAR DPP', '')
                if tgl_bayar:
                    bayar_dt = datetime.strptime(str(tgl_bayar), '%Y-%m-%d').date()
                    hari_lebih = (bayar_dt - jt_dt).days
                else:
                    hari_lebih = (today - jt_dt).days
        except (ValueError, TypeError):
            pass

        jt_months[mk][rekan].append({
            'invoice': row.get('NO INVOICE') or '-',
            'po': po,
            'tgl_inv': str(row.get('TGL INV', '')),
            'tgl_berkas': str(row.get('TGL TERIMA', '')),
            'jth_tempo': str(row.get('JTH TEMPO', '')),
            'deskripsi': row.get('DESKRIPSI') or '-',
            'kode_biaya': row.get('KODE BIAYA2') or '-',
            'total': total,
            'harga_excl': harga_excl,
            'ppn': ppn,
            'pot_pph': pot_pph,
            'bayar_dpp': dp,
            'bayar_ppn': ppn_pay,
            # Total incl. PPN minus both payments (dedup-safe: parts are local)
            'sisa': round(total + ppn - dp - ppn_pay),
            'sisa_dpp': sisa_dpp,
            'sisa_ppn': sisa_ppn,
            'hari_lebih': hari_lebih,
            'status_label': _jt_status(hari_lebih, sisa_dpp)[0],
            'status_key': _jt_status(hari_lebih, sisa_dpp)[1],
            'tgl_bayar_dpp': str(row.get('TGL BAYAR DPP', '')),
            'tgl_bayar_ppn': str(row.get('TGL BAYAR PPN', '')),
            'blm_jatuh_tempo': safe_float(row.get('BLM JATUH TEMPO')),
            'd1_30': safe_float(row.get('1-30 HARI')),
            'd31_60': safe_float(row.get('31-60 HARI')),
            'd61_90': safe_float(row.get('61-90 HARI')),
            'd90plus': safe_float(row.get('LEBIH 90 HARI')),
        })

    all_months = sorted(jt_months.keys())

    report_rows = []
    for mk in all_months:
        y, m = mk.split('-')
        label = f'{month_names[int(m)]} {y}'

        rekanan_list = []
        for rekan in sorted(jt_months[mk].keys()):
            invs = jt_months[mk][rekan]
            rekan_total_dpp = sum(inv['harga_excl'] for inv in invs)
            rekan_bayar_dpp = sum(inv['bayar_dpp'] for inv in invs)
            rekan_sisa_dpp = rekan_total_dpp - rekan_bayar_dpp
            rekan_total = sum(inv['total'] for inv in invs)

            # STATUS from oldest unpaid invoice still outstanding.
            # If all paid, use the latest payment delay among paid invoices.
            # Negative hari_lebih = paid early / future due date.
            unpaid = [inv for inv in invs if inv['sisa_dpp'] > 0]
            if unpaid:
                oldest = min(unpaid, key=lambda x: x['jth_tempo'] or '9999-99-99')
                status_hari = oldest['hari_lebih']
            else:
                paid_late = [inv['hari_lebih'] for inv in invs if inv['hari_lebih'] > 0]
                status_hari = max(paid_late) if paid_late else 0
            sisa_vendor = max(0, rekan_sisa_dpp)  # clamp: overpayment must not hide unpaid debt
            status_label, status_key = _jt_status(status_hari, sisa_vendor)

            rekanan_list.append({
                'rekanan': rekan,
                'invoices': invs,
                'total': rekan_total,
                'total_dpp': rekan_total_dpp,
                'bayar_dpp': rekan_bayar_dpp,
                'sisa_dpp': sisa_vendor,
                'count': len(unpaid),
                'status_hari': status_hari,
                'status_label': status_label,
                'status_key': status_key,
            })

        report_rows.append({
            'key': mk,
            'label': label,
            'rekanan_list': rekanan_list,
        })

    return report_rows, valid_count
