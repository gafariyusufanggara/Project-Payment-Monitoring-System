"""
LAYER — Rekap No PO (mirip sheet 'Rekap No PO' di Monitoring Pemenang LINK.xlsx).

Sumber data: vendor_contracts yang sudah ter-import dari Import Kontrak.
Tidak ada tabel baru; hitungan murni dari DB.

Periode:
  Default 'Semua Bulan' = seluruh kontrak s/d bulan berjalan saat ini.
  Dropdown berisi 'Semua Bulan' + bulan-bulan yang benar-benar ada di data
  TGL Kontrak. Saat memilih bulan tertentu, bulan aktif mengikuti pilihan
  tersebut. Chart tetap berhenti di bulan data terakhir yang tersedia.

  S/D Bulan Lalu   : tanggal kontrak <= hari terakhir bulan sebelum
  Bulan Ini        : tanggal kontrak di bulan terpilih
  SD Bulan Ini     : tanggal kontrak <= hari terakhir bulan terpilih (= S/D lalu + Bulan ini)
  NILAI KONTRAK    : seluruh DPP kontrak yang sudah ada s/d akhir bulan terpilih.
  Kontrak yang tanggalnya setelah periode terpilih tidak ditampilkan.

  KPI Rekap:
    Nilai Kontrak s/d bulan aktif = S/D Bulan Lalu + Bulan Ini.
    S/D Bulan Lalu = kumulatif sebelum bulan aktif, bukan nominal satu bulan.

Bucket (sesuai sheet):
  KSO   : DPP < 300 juta
  UB    : 300 juta <= DPP <= 2,5 miliar
  PS    : DPP > 2,5 miliar

Kolom yang BUKAN sumber (dibuang per permintaan):
  Anggaran PPP, Uraian, Prioritas, Deviasi.

Return dict dipetakan ke template rekap_po.html dengan kunci yang sama.
"""
from datetime import date, datetime, timedelta
from collections import defaultdict

# Ambang bucket — sesuai sheet.
_KSO_MAX = 300_000_000
_UNIT_MAX = 2_500_000_000

_BUCKET_LABELS = {'kso': 'KSO (<300 Jt)', 'unit': 'Unit Bisnis (300 Jt–2,5 M)', 'pusat': 'Pusat (>2,5 M)'}
_BUCKET_SHORT = {'kso': 'KSO', 'unit': 'UB', 'pusat': 'PS'}
_BUCKET_COLOR = {'kso': '#E5B800', 'unit': '#16324f', 'pusat': '#0F766E'}
_COLORS = ['#E5B800', '#16324f', '#0F766E']
_MONTH_NAMES = [
    '', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
    'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'
]


def _bucket_of(dpp):
    dpp = dpp or 0.0
    if dpp < _KSO_MAX:
        return 'kso'
    if dpp <= _UNIT_MAX:
        return 'unit'
    return 'pusat'


def _parse_dt(val):
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return datetime.strptime(str(val)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def _days_in(y, m):
    if m == 12:
        return date(y + 1, 1, 1)
    return date(y, m + 1, 1)


def build_rekap(contracts, year, month, all_months=False, today=None):
    """Bangun data halaman Rekap Kontrak.

    Args:
        contracts: list dict hasil db_contract.get_contracts(project_id).
        year: int tahun
        month: int bulan (1-12)

    Returns:
        dict yang siap diteruskan ke render_template('rekap_po.html', ...).
    """
    rows = []
    for c in contracts:
        dpp = c.get('nilai_dpp') or 0.0
        bkt = _bucket_of(float(dpp))
        dt = _parse_dt(c.get('tgl_kontrak'))
        rows.append({
            'id': c.get('id'),
            'no_kontrak': c.get('no_kontrak') or '',
            'vendor': c.get('vendor') or '',
            'item_pekerjaan': c.get('item_pekerjaan') or '',
            'tgl_kontrak': dt.isoformat() if dt else '',
            'tgl_display': dt.strftime('%d %b %Y') if dt else '—',
            'dpp': float(dpp),
            'bucket': bkt,
            'jumlah_invoice': int(c.get('jumlah_invoice') or 0),
        })

    # --- Periode: 'Semua Bulan' + bulan-bulan yang benar-benar ada di data
    # TGL Kontrak. Bulan tanpa kontrak tidak dimasukkan agar sumbu chart tidak
    # memanjang ke bulan kosong.
    seen_months = set()
    for r in rows:
        dt = _parse_dt(r['tgl_kontrak'])
        if dt is not None:
            seen_months.add((dt.year, dt.month))
    date_keys = sorted(seen_months)
    today = today or date.today()
    current_key = (today.year, today.month)
    period_options = [{'key': 'all', 'label': 'Semua Bulan'}] + [
        {'key': '%04d-%02d' % (y, m), 'label': '%s %d' % (_MONTH_NAMES[m], y)}
        for (y, m) in date_keys
    ]
    if all_months or (year, month) not in seen_months:
        all_months = True
        year, month = current_key
        selected_key = 'all'
    else:
        selected_key = '%04d-%02d' % (year, month)
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_month_label = _MONTH_NAMES[prev_month] + ' ' + str(prev_year)
    month_start = date(year, month, 1)
    month_end = _days_in(year, month) - timedelta(days=1)
    prev_month_start = date(prev_year, prev_month, 1)
    prev_month_end = month_start - timedelta(days=1)

    for r in rows:
        dt = _parse_dt(r['tgl_kontrak'])
        if all_months:
            r['visible'] = True
        else:
            r['visible'] = dt is not None and (dt.year, dt.month) == (year, month)
        r['counted'] = dt is None or dt <= month_end

    # hitung agregat per periode x bucket + nilai per baris untuk periodenya
    # foot_* = jumlah baris yang TAMPIL (footer tabel)
    # kpi_*  = kumulatif s/d akhir periode (KPI, tidak ikut penyaringan baris)
    foot_sdl = defaultdict(float)
    foot_bln = defaultdict(float)
    foot_sdi = defaultdict(float)
    kpi_sdl = defaultdict(float)
    kpi_bln = defaultdict(float)
    kpi_sdi = defaultdict(float)
    all_bkt = defaultdict(float)

    empty_bkt = {b: 0.0 for b in ('kso', 'unit', 'pusat')}
    for r in rows:
        d = r['dpp']
        b = r['bucket']
        if not r['counted']:
            r['periods'] = {
                'kini': dict(empty_bkt), 'sdl': dict(empty_bkt),
                'bln': dict(empty_bkt), 'sdi': dict(empty_bkt),
            }
            continue
        all_bkt[b] += d
        dt = _parse_dt(r['tgl_kontrak'])
        # nilai per baris: hanya kolom bucket baris ini yang terisi
        p_kini = dict(empty_bkt); p_kini[b] = d
        p_sdl = dict(empty_bkt)
        p_bln = dict(empty_bkt)
        p_sdi = dict(empty_bkt)
        if dt is not None:
            if dt <= prev_month_end:
                kpi_sdl[b] += d
                kpi_sdi[b] += d
                p_sdl[b] = d
                p_sdi[b] = d
            elif dt <= month_end:
                kpi_bln[b] += d
                kpi_sdi[b] += d
                p_bln[b] = d
                p_sdi[b] = d
        if r['visible']:
            for p, acc in ((p_sdl, foot_sdl), (p_bln, foot_bln), (p_sdi, foot_sdi)):
                if p[b]:
                    acc[b] += d
        r['periods'] = {'kini': p_kini, 'sdl': p_sdl, 'bln': p_bln, 'sdi': p_sdi}

    # rows: satu baris = satu kontrak. Total per periode ditampilkan footer tabel.

    # --- Seri bulanan (semua bulan) untuk chart batang bertumpuk per bucket ---
    # Rentang: dari bulan kontrak paling awal s/d bulan terpilih.
    monthly = {b: defaultdict(float) for b in ('kso', 'unit', 'pusat')}
    dated = [_parse_dt(r['tgl_kontrak']) for r in rows]
    dated = [d for d in dated if d is not None]
    bars_labels = []
    bars_years = []
    bars_datasets = []
    if dated:
        first = min(dated)
        last = max(dated)
        bars_end = min((year, month), (last.year, last.month))
        cy, cm = first.year, first.month
        # jangan pernah lewat dari bulan terpilih / bulan data terakhir
        while (cy, cm) <= bars_end:
            bars_labels.append(_MONTH_NAMES[cm])
            bars_years.append(str(cy))
            for b in ('kso', 'unit', 'pusat'):
                monthly[b][(cy, cm)] = 0.0
            if cm == 12:
                cy, cm = cy + 1, 1
            else:
                cm += 1
        # isi nilai per bulan x bucket
        for r in rows:
            dt = _parse_dt(r['tgl_kontrak'])
            if dt is None:
                continue
            key = (dt.year, dt.month)
            if key in monthly[r['bucket']]:
                monthly[r['bucket']][key] += r['dpp']
        ordered_keys = []
        cy, cm = first.year, first.month
        while (cy, cm) <= bars_end:
            ordered_keys.append((cy, cm))
            if cm == 12:
                cy, cm = cy + 1, 1
            else:
                cm += 1
        for b in ('kso', 'unit', 'pusat'):
            bars_datasets.append({
                'label': _BUCKET_LABELS[b],
                'data': [float(monthly[b][k]) for k in ordered_keys],
                'backgroundColor': _BUCKET_COLOR[b],
                'borderColor': _BUCKET_COLOR[b],
                'borderWidth': 1,
                'maxBarThickness': 46,
            })

    period_summaries = {
        'kontrak_kini': {b: float(all_bkt[b]) for b in ('kso', 'unit', 'pusat')},
        'sd_bulan_lalu': {b: float(foot_sdl[b]) for b in ('kso', 'unit', 'pusat')},
        'bulan_ini': {b: float(foot_bln[b]) for b in ('kso', 'unit', 'pusat')},
        'sd_bulan_ini': {b: float(foot_sdi[b]) for b in ('kso', 'unit', 'pusat')},
    }
    grand_totals = {
        'kontrak_kini': float(sum(all_bkt.values())),
        'sd_bulan_lalu': float(sum(kpi_sdl.values())),
        'bulan_ini': float(sum(kpi_bln.values())),
        'sd_bulan_ini': float(sum(kpi_sdi.values())),
    }

    bucket_order = ['kso', 'unit', 'pusat']
    visible_count = sum(1 for r in rows if r['visible'])
    return {
        'rows': rows,
        'bucket_order': bucket_order,
        'period_summaries': period_summaries,
        'grand_totals': grand_totals,
        'bars_labels': bars_labels,
        'bars_years': bars_years,
        'bars_datasets': bars_datasets,
        'donut_labels': [_BUCKET_LABELS[b] for b in bucket_order],
        'donut_data': [float(all_bkt[b]) for b in bucket_order],
        'donut_colors': _COLORS,
        'year': year,
        'month': month,
        'period_options': period_options,
        'selected_key': selected_key,
        'month_label': _MONTH_NAMES[month] + ' ' + str(year),
        'prev_month_label': prev_month_label,
        'period_label': 'Semua Bulan' if all_months else _MONTH_NAMES[month] + ' ' + str(year),
        'all_year': current_key[0],
        'all_month': current_key[1],
        'total_kontrak': visible_count,
        'total_vendor': len({
            (r['vendor'] or '').strip()
            for r in rows
            if r['visible'] and (r['vendor'] or '').strip()
        }),
        'nav_project_list': [],  # diisi via controller
        'nav_active': 'rekap',
    }
