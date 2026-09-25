"""
MODEL — Dashboard analytics for the index page.

Pure computation over db.read_data(); no Flask, no rendering.
"""
from datetime import datetime, date

import db
from constants import safe_float, effective_invoice, is_excluded_row


def _dedup_debt_rows(data):
    """Return list of dicts where debt fields are zeroed for duplicate invoice rows.

    One invoice = one debt. Payments stay per-row (installments).
    Dedup key: (rekanan, effective_invoice). First row keeps debt; subsequent rows get 0.
    """
    seen = set()
    result = []
    for row in data:
        r = dict(row)
        rekan = (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()
        inv = effective_invoice(r)
        key = (rekan, inv) if inv else None
        if key and key in seen:
            r['HARGA (EXLD)'] = 0
            r['TOTAL (INCLD)'] = 0
            r['PPN'] = 0
            r['POT. RETENSI'] = 0
            r['POT. PPH'] = 0
            r['SISA HUTANG (INCLD PPN)'] = 0
            r['SISA HUTANG DPP'] = 0
            r['SISA HUTANG PPN'] = 0
        else:
            if key:
                seen.add(key)
        result.append(r)
    return result


def build_dashboard_context(project_id=None):
    """Return dict of everything needed by index.html.

    project_id: optional filter — None or 'all' shows every project (consolidated).
    """
    data = db.read_data(project_id)
    # Exclusion rules (Pengaturan): rows whose KATEGORI/rekanan is excluded
    # stay visible in tables but are dropped from every aggregation below.
    # TGL TERIMA (tanggal berkas lengkap) must be present — same scope as the
    # DPP/PPN laporan (_build_cum skips rows without TGL TERIMA). An invoice
    # whose berkas is not complete yet is not yet a countable debt, so counting
    # it here would make the dashboard KPIs disagree with the reports.
    calc = [r for r in data if not is_excluded_row(r) and r.get('TGL TERIMA')]
    excluded_rows = {r.get('_row') for r in data if is_excluded_row(r)}
    _exc = [r for r in data if is_excluded_row(r)]
    excluded_row_count = len(_exc)
    excluded_rekanan_count = len({(r.get('NAMA LEVELANSIR / REKANAN') or '').strip() for r in _exc if (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()})
    deduped = _dedup_debt_rows(calc)
    today = date.today()

    total_count = len(calc)
    total_tagihan = sum(safe_float(r.get('TOTAL (INCLD)')) for r in deduped)
    # Total Retensi: matches the Levelansir/Retensi page (db.get_levelansir_retensi).
    # Retensi = uang yang ditahan (bukan utang aktif), sehingga dihitung dari
    # SEMUA baris dengan POT. RETENSI > 0 — tanpa syarat TGL TERIMA, tanpa
    # aturan exclude, dan tanpa dedup.
    total_retensi = sum(safe_float(r.get('POT. RETENSI')) for r in data)
    total_pph = sum(safe_float(r.get('POT. PPH')) for r in data)
    total_dpp_paid = sum(safe_float(r.get('PEMBAYARAN DPP')) for r in calc)
    total_ppn_paid = sum(safe_float(r.get('PEMBAYARAN PPN')) for r in calc)
    total_harga_excl_raw = sum(safe_float(r.get('HARGA (EXLD)')) for r in deduped)
    # Per-vendor sisa DPP (matches laporan bulanan _build_cum methodology).
    # max(0, total_debt - total_payment) per vendor, then sum — prevents
    # overpayment on one vendor from hiding unpaid debt on another.
    _vs = {}
    _vp = {}
    for r in deduped:
        rek = r.get('NAMA LEVELANSIR / REKANAN') or 'Unknown'
        _vs[rek] = _vs.get(rek, 0) + safe_float(r.get('HARGA (EXLD)')) - safe_float(r.get('PEMBAYARAN DPP'))
        _vp[rek] = _vp.get(rek, 0) + safe_float(r.get('PPN')) - safe_float(r.get('PEMBAYARAN PPN'))
    total_sisa_dpp = sum(max(0, v) for v in _vs.values())
    # Same per-vendor clip for PPN (matches Laporan PPN sisa_ppn = max(0, sum
    # PPN - sum bayar PPN) per rekanan). Using the stored SISA HUTANG PPN column
    # instead produced a 1-rupiah rounding drift versus the report.
    total_sisa_ppn = sum(max(0, v) for v in _vp.values())
    sisa_hutang = total_sisa_dpp + total_sisa_ppn
    lunas_count = sum(1 for r in calc if r.get('STATUS TERHADAP DPP') == 'Lunas')
    belum_count = sum(1 for r in calc if r.get('STATUS TERHADAP DPP') == 'Belum Lunas')

    total_ppn_raw = sum(safe_float(r.get('PPN')) for r in deduped)
    total_harga_excl = total_harga_excl_raw
    total_ppn_val = total_ppn_raw
    _dpp_base = total_harga_excl_raw or 1
    _ppn_base = total_ppn_raw or 1
    status_dpp_pct = round(total_dpp_paid / _dpp_base * 100)
    status_ppn_pct = round(total_ppn_paid / _ppn_base * 100)
    sisa_dpp_pct = round(total_sisa_dpp / _dpp_base * 100)
    sisa_ppn_pct = round(total_sisa_ppn / _ppn_base * 100)

    return {
        'data': data,
        'total_count': total_count,
        'total_tagihan': total_tagihan,
        'total_dpp_paid': total_dpp_paid,
        'total_ppn_paid': total_ppn_paid,
        'total_sisa_dpp': total_sisa_dpp,
        'total_sisa_ppn': total_sisa_ppn,
        'total_retensi': total_retensi,
        'total_pph': total_pph,
        'sisa_hutang': sisa_hutang,
        'lunas_count': lunas_count,
        'belum_count': belum_count,
        'status_dpp_pct': status_dpp_pct,
        'status_ppn_pct': status_ppn_pct,
        'sisa_dpp_pct': sisa_dpp_pct,
        'sisa_ppn_pct': sisa_ppn_pct,
        'total_harga_excl': total_harga_excl,
        'total_dpp': total_harga_excl_raw,
        'total_ppn_val': total_ppn_val,
        'unique_rekanan_count': _unique_rekanan_count(calc),
        'kategori_data': _kategori_breakdown(calc),
        'rekanan_detail_sorted': _rekanan_breakdown(calc),
        'aging': _aging(calc, today),
        'overdue_list': _overdue(calc, today),
        'overdue_rows': _overdue_set(calc, today),
        'monthly_data': _monthly_data(calc),
        'daily_data': _daily_data(calc),
        'excluded_rows': sorted(excluded_rows),
        'excluded_row_count': excluded_row_count,
        'excluded_rekanan_count': excluded_rekanan_count,
    }


def _kategori_breakdown(data):
    deduped = _dedup_debt_rows(data)
    kategori_data = {}
    for row in deduped:
        kat = row.get('KATEGORI') or 'Lainnya'
        if kat not in kategori_data:
            kategori_data[kat] = {'count': 0, 'total': 0}
        kategori_data[kat]['count'] += 1
        kategori_data[kat]['total'] += safe_float(row.get('TOTAL (INCLD)'))
    return kategori_data


def _rekanan_breakdown(data):
    deduped = _dedup_debt_rows(data)
    rekanan_detail = {}
    for row in deduped:
        rek = row.get('NAMA LEVELANSIR / REKANAN') or 'Unknown'
        if rek not in rekanan_detail:
            rekanan_detail[rek] = {'jumlah': 0, 'total_dpp': 0, 'total_pph': 0, 'total_ppn': 0,
                                   'sisa_dpp': 0, 'sisa_ppn': 0,
                                   'total_bayar_dpp': 0, 'total_bayar_ppn': 0}
        rekanan_detail[rek]['jumlah'] += 1
        rekanan_detail[rek]['total_dpp'] += safe_float(row.get('HARGA (EXLD)'))
        rekanan_detail[rek]['total_pph'] += safe_float(row.get('POT. PPH'))
        rekanan_detail[rek]['total_ppn'] += safe_float(row.get('PPN'))
        rekanan_detail[rek]['sisa_dpp'] += safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
        rekanan_detail[rek]['sisa_ppn'] += safe_float(row.get('SISA HUTANG PPN'))
        rekanan_detail[rek]['total_bayar_dpp'] += safe_float(row.get('PEMBAYARAN DPP'))
        rekanan_detail[rek]['total_bayar_ppn'] += safe_float(row.get('PEMBAYARAN PPN'))
    # Clamp sisa_dpp to 0 minimum — dedup rows may produce negative partial sums
    for v in rekanan_detail.values():
        v['sisa_dpp'] = max(0, v['sisa_dpp'])
    # Urut A→Z berdasarkan nama levelansir/rekanan (case-insensitive, stabil).
    return sorted(rekanan_detail.items(), key=lambda x: (x[0] or '').strip().lower())


def _unique_rekanan_count(data):
    return len({row.get('NAMA LEVELANSIR / REKANAN') for row in data
                if row.get('NAMA LEVELANSIR / REKANAN')})


def _aging(data, today):
    aging = {'belum_jatuh_tempo': 0, '1-30': 0, '31-60': 0, '61-90': 0, '>90': 0}
    for row in data:
        if row.get('STATUS TERHADAP DPP') != 'Belum Lunas' or not row.get('JTH TEMPO'):
            continue
        try:
            jth = datetime.strptime(str(row['JTH TEMPO']), '%Y-%m-%d').date()
            days = (today - jth).days
            if days < 0:
                aging['belum_jatuh_tempo'] += 1
            elif days <= 30:
                aging['1-30'] += 1
            elif days <= 60:
                aging['31-60'] += 1
            elif days <= 90:
                aging['61-90'] += 1
            else:
                aging['>90'] += 1
        except (ValueError, TypeError):
            pass
    return aging


def _overdue(data, today):
    overdue_list = []
    for row in data:
        if row.get('STATUS TERHADAP DPP') != 'Belum Lunas' or not row.get('JTH TEMPO'):
            continue
        try:
            jth = datetime.strptime(str(row['JTH TEMPO']), '%Y-%m-%d').date()
            days = (today - jth).days
            if days > 0:
                overdue_list.append({
                    'rekanan': row.get('NAMA LEVELANSIR / REKANAN', ''),
                    'invoice': row.get('NO INVOICE', ''),
                    'jth': str(row['JTH TEMPO']),
                    'days': days,
                    'total': safe_float(row.get('TOTAL (INCLD)')),
                })
        except (ValueError, TypeError):
            pass
    overdue_list.sort(key=lambda x: x['days'], reverse=True)
    return overdue_list[:10]


def _overdue_set(data, today):
    out = set()
    for row in data:
        if row.get('STATUS TERHADAP DPP') != 'Belum Lunas' or not row.get('JTH TEMPO'):
            continue
        try:
            if (today - datetime.strptime(str(row['JTH TEMPO']), '%Y-%m-%d').date()).days > 0:
                out.add(row.get('_row'))
        except (ValueError, TypeError):
            pass
    return sorted(out)


def _monthly_data(data):
    deduped = _dedup_debt_rows(data)
    monthly_data = {}
    for row in deduped:
        jth = row.get('JTH TEMPO')
        if not jth:
            continue
        try:
            dt = datetime.strptime(str(jth), '%Y-%m-%d')
            key = dt.strftime('%Y-%m')
            label = dt.strftime('%b %Y')
        except (ValueError, TypeError):
            continue
        if key not in monthly_data:
            monthly_data[key] = {'label': label, 'total_hutang_dpp': 0, 'total_bayar_dpp': 0, 'sisa_dpp': 0}
        monthly_data[key]['total_hutang_dpp'] += safe_float(row.get('HARGA (EXLD)'))
        monthly_data[key]['total_bayar_dpp'] += safe_float(row.get('PEMBAYARAN DPP'))
        monthly_data[key]['sisa_dpp'] += safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
    for k in monthly_data:
        monthly_data[k]['sisa_dpp'] = max(0, monthly_data[k]['sisa_dpp'])
    return sorted(monthly_data.items(), key=lambda x: x[0])


def _daily_data(data):
    deduped = _dedup_debt_rows(data)
    daily_data = {}
    for row in deduped:
        jth = row.get('JTH TEMPO')
        if not jth:
            continue
        try:
            dt = datetime.strptime(str(jth), '%Y-%m-%d')
            key = dt.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            continue
        if key not in daily_data:
            daily_data[key] = {'tgl': key, 'hutang_jt_dpp': 0, 'bayar_jt_dpp': 0, 'sisa_dpp': 0, 'sisa_ppn': 0}
        daily_data[key]['hutang_jt_dpp'] += safe_float(row.get('HARGA (EXLD)'))
        daily_data[key]['bayar_jt_dpp'] += safe_float(row.get('PEMBAYARAN DPP'))
        daily_data[key]['sisa_dpp'] += safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
        daily_data[key]['sisa_ppn'] += safe_float(row.get('SISA HUTANG PPN'))
    for k in daily_data:
        daily_data[k]['sisa_dpp'] = max(0, daily_data[k]['sisa_dpp'])
    return sorted(daily_data.items(), key=lambda x: x[0])
