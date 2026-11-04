"""
LAYER — Rekap No PO (mirip sheet 'Rekap No PO' di Monitoring Pemenang LINK.xlsx).

Sumber data: vendor_contracts yang sudah ter-import dari Import Kontrak.
Tidak ada tabel baru; hitungan murni dari DB.

Periode:
  Tahun & bulan dipilih user (default bulan berjalan). Batas akhir
  'bulan ini' = hari terakhir bulan terpilih (tidak perlu tanggal hari ini
  supaya pengguna bisa melihat bulan kapan saja).

  S/D Bulan Lalu   : tanggal kontrak <= hari terakhir bulan sebelum
  Bulan Ini        : tanggal kontrak di bulan terpilih
  SD Bulan Ini     : tanggal kontrak <= hari terakhir bulan terpilih (= S/D lalu + Bulan ini)
  NILAI KONTRAK    : seluruh DPP kontrak yang sudah ada s/d akhir bulan terpilih.
  Kontrak yang tanggalnya setelah periode terpilih tidak ditampilkan.

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


def build_rekap(contracts, year, month):
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

    # --- Periode yang tersedia = bulan-bulan yang benar-benar ada di tanggal
    # kontrak. Dropdown hanya menampilkan periode ini (pola halaman Jatuh Tempo).
    # Bila periode terpilih tidak ada, pakai periode terakhir yang tersedia.
    seen_months = set()
    for r in rows:
        dt = _parse_dt(r['tgl_kontrak'])
        if dt is not None:
            seen_months.add((dt.year, dt.month))
    date_keys = sorted(seen_months)
    period_options = [
        {'key': '%04d-%02d' % (y, m), 'label': '%s %d' % (_MONTH_NAMES[m], y)}
        for (y, m) in date_keys
    ]
    if period_options and (year, month) not in seen_months:
        year, month = date_keys[-1]
    selected_key = '%04d-%02d' % (year, month) if period_options else ''

    month_start = date(year, month, 1)
    month_end = _days_in(year, month) - timedelta(days=1)
    prev_month_end = month_start - timedelta(days=1)

    for r in rows:
        dt = _parse_dt(r['tgl_kontrak'])
        r['visible'] = dt is None or dt <= month_end

    # hitung agregat per periode x bucket + nilai per baris untuk periodenya
    sdl = defaultdict(float)
    bln = defaultdict(float)
    sdi = defaultdict(float)
    all_bkt = defaultdict(float)

    empty_bkt = {b: 0.0 for b in ('kso', 'unit', 'pusat')}
    for r in rows:
        d = r['dpp']
        b = r['bucket']
        if not r['visible']:
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
                sdl[b] += d
                sdi[b] += d
                p_sdl[b] = d
                p_sdi[b] = d
            elif dt <= month_end:
                bln[b] += d
                sdi[b] += d
                p_bln[b] = d
                p_sdi[b] = d
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
        cy, cm = first.year, first.month
        # jangan pernah lewat dari bulan terpilih
        while (cy, cm) <= (year, month):
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
        while (cy, cm) <= (year, month):
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

    grand_sdl = sum(sdl.values())
    grand_bln = sum(bln.values())
    grand_sdi = sum(sdi.values())

    period_summaries = {
        'kontrak_kini': {b: float(all_bkt[b]) for b in ('kso', 'unit', 'pusat')},
        'sd_bulan_lalu': {b: float(sdl[b]) for b in ('kso', 'unit', 'pusat')},
        'bulan_ini': {b: float(bln[b]) for b in ('kso', 'unit', 'pusat')},
        'sd_bulan_ini': {b: float(sdi[b]) for b in ('kso', 'unit', 'pusat')},
    }
    grand_totals = {
        'kontrak_kini': float(sum(all_bkt.values())),
        'sd_bulan_lalu': grand_sdl,
        'bulan_ini': grand_bln,
        'sd_bulan_ini': grand_sdi,
    }

    bucket_order = ['kso', 'unit', 'pusat']
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
        'total_kontrak': sum(1 for r in rows if r['visible']),
        'nav_project_list': [],  # diisi via controller
        'nav_active': 'rekap',
    }
