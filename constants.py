"""
Shared constants and utility functions.
"""
import os
import json
from datetime import datetime, date

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

# ========== KODE BIAYA (Fixed codes for RAB) ==========
KODE_BIAYA = [
    ('500', 'BAHAN'),
    ('501', 'UPAH'),
    ('502', 'PERALATAN'),
    ('503', 'SUB KONTRAKTOR'),
    ('504', 'BANK'),
    ('505', 'BIAYA UMUM(BAU) PROYEK'),
    ('506', 'BIAYA RUPA-RUPA'),
    ('507', 'PPH FINAL'),
]
KODE_BIAYA_MAP = dict(KODE_BIAYA)  # '500' -> 'BAHAN', etc.

# ========== COLUMN DEFINITIONS (Sesuai Template Asli) ==========
COLUMNS = [
    'R',
    'TGL TERIMA BERKAS',
    'NAMA LEVELANSIR / REKANAN',
    'STATUS TERHADAP DPP',
    'STATUS TERHADAP PPN',
    'KETERANGAN PPN',
    'NO INVOICE INTERNAL',
    'NO INVOICE',
    'NO PO / KONTRAK',
    'TGL INV',
    'TGL TERIMA',
    'JTH TEMPO',
    'DESKRIPSI',
    'KODE BIAYA',
    'VOLUME PROGRESS',
    'HARGA SATUAN',
    'HARGA (EXLD)',
    'POT. RETENSI',
    'POT. PPH',
    'PPN',
    'TOTAL (INCLD)',
    'NO SERI FAKTUR PAJAK',
    'TGL FAKTUR PAJAK',
    'PEMBAYARAN DPP VIA DIVISI',
    'NO BUKTI BAYAR DPP',
    'TGL BAYAR DPP',
    'PEMBAYARAN PPN VIA',
    'NO BUKTI BAYAR PPN',
    'TGL BAYAR PPN',
    'PEMBAYARAN DPP',
    'PEMBAYARAN POT. PPH',
    'NILAI YG DITERIMA VENDOR',
    'PEMBAYARAN PPN',
    'SISA HUTANG (INCLD PPN)',
    'SISA HUTANG DPP',
    'SISA HUTANG PPN',
    'BLM JATUH TEMPO',
    '1-30 HARI',
    '31-60 HARI',
    '61-90 HARI',
    'LEBIH 90 HARI',
    'KATEGORI',
    'TGL MASUK DIVISI',
    'KETERANGAN',
    'KODE BIAYA2',
    'project_id',
]

# Auto-generated column position→name map for import (1-based)
IMPORT_COL_MAP = {i+1: name for i, name in enumerate(COLUMNS)}

DATE_FIELDS = [
    'TGL TERIMA BERKAS', 'TGL TERIMA', 'TGL INV',
    'JTH TEMPO', 'TGL FAKTUR PAJAK',
    'TGL BAYAR DPP', 'TGL BAYAR PPN',
]

NUMERIC_FIELDS = [
    'VOLUME PROGRESS', 'HARGA SATUAN', 'HARGA (EXLD)', 'POT. RETENSI', 'POT. PPH',
    'PPN', 'TOTAL (INCLD)', 'PEMBAYARAN DPP', 'PEMBAYARAN POT. PPH',
    'NILAI YG DITERIMA VENDOR', 'PEMBAYARAN PPN',
    'SISA HUTANG (INCLD PPN)', 'SISA HUTANG DPP', 'SISA HUTANG PPN',
    'BLM JATUH TEMPO', '1-30 HARI', '31-60 HARI', '61-90 HARI', 'LEBIH 90 HARI',
]

# Currency amounts are stored rounded to whole Rupiah (no decimals), like Excel.
# VOLUME PROGRESS is intentionally excluded (kept decimal) and aging buckets are counts.
CURRENCY_FIELDS = [
    'HARGA SATUAN', 'HARGA (EXLD)', 'POT. RETENSI', 'POT. PPH', 'PPN', 'TOTAL (INCLD)',
    'PEMBAYARAN DPP', 'PEMBAYARAN POT. PPH', 'NILAI YG DITERIMA VENDOR',
    'PEMBAYARAN PPN', 'SISA HUTANG (INCLD PPN)',
    'SISA HUTANG DPP', 'SISA HUTANG PPN',
]

AUTO_FIELDS = [
    'SISA HUTANG (INCLD PPN)', 'SISA HUTANG DPP', 'SISA HUTANG PPN',
    'BLM JATUH TEMPO', '1-30 HARI', '31-60 HARI', '61-90 HARI', 'LEBIH 90 HARI',
]

FORM_FIELDS = [c for c in COLUMNS if c not in AUTO_FIELDS and c != 'R']

COL_WIDTHS = {
    'R': 5, 'TGL TERIMA BERKAS': 14, 'NAMA LEVELANSIR / REKANAN': 28,
    'STATUS TERHADAP DPP': 14, 'STATUS TERHADAP PPN': 14, 'KETERANGAN PPN': 14,
    'NO INVOICE INTERNAL': 20, 'NO INVOICE': 30, 'NO PO / KONTRAK': 24, 'TGL INV': 12,
    'TGL TERIMA': 14, 'JTH TEMPO': 12, 'DESKRIPSI': 30,
    'KODE BIAYA': 12, 'VOLUME PROGRESS': 10, 'HARGA SATUAN': 14,
    'HARGA (EXLD)': 16, 'POT. RETENSI': 12, 'POT. PPH': 12, 'PPN': 12, 'TOTAL (INCLD)': 16,
    'NO SERI FAKTUR PAJAK': 18, 'TGL FAKTUR PAJAK': 14,
    'PEMBAYARAN DPP VIA DIVISI': 16, 'NO BUKTI BAYAR DPP': 18, 'TGL BAYAR DPP': 14,
    'PEMBAYARAN PPN VIA': 16, 'NO BUKTI BAYAR PPN': 18, 'TGL BAYAR PPN': 14,
    'PEMBAYARAN DPP': 16, 'PEMBAYARAN POT. PPH': 14, 'NILAI YG DITERIMA VENDOR': 16,
    'PEMBAYARAN PPN': 14,
    'SISA HUTANG (INCLD PPN)': 16, 'SISA HUTANG DPP': 14, 'SISA HUTANG PPN': 14,
    'BLM JATUH TEMPO': 14, '1-30 HARI': 10, '31-60 HARI': 10, '61-90 HARI': 10, 'LEBIH 90 HARI': 11,
    'KATEGORI': 16, 'TGL MASUK DIVISI': 14, 'KETERANGAN': 30, 'KODE BIAYA2': 12,
}

STATUS_DPP = ['Lunas', 'Belum Lunas']
STATUS_PPN = ['Ada PPN', 'Tidak ada PPN', 'Ditanggung Rekanan']


# ========== CONFIG HELPERS ==========

def load_categories():
    default_cats = [
        'BUA', 'Material', 'Jasa', 'Tiket Karyawan', 'Bahan', 'Sewa Kendaraan',
        'Overhead', 'MANDOR', 'MCU', 'Seragam Karyawan', 'Sewa Alat GPS', 'Lainnya',
    ]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('categories', default_cats)
        except Exception:
            pass
    return default_cats


def save_categories(cats):
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg['categories'] = cats
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def save_excluded(cats, rekanan):
    """Persist exclusion lists (kategori & rekanan) to config.json."""
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg['excluded_categories'] = list(cats)
    cfg['excluded_rekanan'] = list(rekanan)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def load_last_import():
    """Return (invoice_map, kontrak_map): {project_id_str: 'YYYY-MM-DD HH:MM'}."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return cfg.get('last_import_invoice', {}) or {}, cfg.get('last_import_kontrak', {}) or {}
        except Exception:
            pass
    return {}, {}


def save_last_import(kind, project_id):
    """Stamp last import time for invoice|kontrak + project scope."""
    if kind not in ('invoice', 'kontrak'):
        return
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            pass
    from datetime import datetime as _dt
    key = 'last_import_invoice' if kind == 'invoice' else 'last_import_kontrak'
    m = cfg.get(key) or {}
    m[str(project_id or '')] = _dt.now().strftime('%Y-%m-%d %H:%M')
    cfg[key] = m
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


_UPDATE_BULAN = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
                 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']


def format_update_label(ts):
    """'2026-09-24 14:30' → '24 Sep 2026'. Kosong/gagal → ''."""
    try:
        d = datetime.strptime(str(ts).strip(), '%Y-%m-%d %H:%M')
        return f'{d.day} {_UPDATE_BULAN[d.month]} {d.year}'
    except (ValueError, TypeError):
        return ''


def format_update_detail(ts):
    """'2026-09-24 14:30' → '24 Sep 2026, 14:30'. Gagal → string mentah."""
    try:
        d = datetime.strptime(str(ts).strip(), '%Y-%m-%d %H:%M')
        return f'{d.day} {_UPDATE_BULAN[d.month]} {d.year}, {d.strftime("%H:%M")}'
    except (ValueError, TypeError):
        return str(ts or '')


CATEGORIES = load_categories()


def load_excluded():
    """Load exclusion lists — rows whose KATEGORI or rekanan matches are
    skipped by all aggregations (dashboard + laporan), but stay visible in tables."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return cfg.get('excluded_categories', []), cfg.get('excluded_rekanan', [])
        except Exception:
            pass
    return [], []


EXCLUDED_CATEGORIES, EXCLUDED_REKANAN = load_excluded()


def is_excluded_row(row):
    """True if row's KATEGORI or NAMA LEVELANSIR/REKANAN is excluded (case-insensitive)."""
    kat = (row.get('KATEGORI') or '').strip()
    if kat and kat.lower() in {c.lower() for c in EXCLUDED_CATEGORIES}:
        return True
    rek = (row.get('NAMA LEVELANSIR / REKANAN') or '').strip()
    if rek and rek.lower() in {r.lower() for r in EXCLUDED_REKANAN}:
        return True
    return False


# ========== VALUE HELPERS ==========

def safe_float(val, default=0):
    if val is None or val == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_date(val):
    if not val or val == '':
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.strptime(str(val).strip(), '%Y-%m-%d')
    except ValueError:
        return None


def calc_sisa(data):
    """Auto-calculate sisa hutang + aging bucket fields."""
    total = safe_float(data.get('TOTAL (INCLD)'))
    harga = safe_float(data.get('HARGA (EXLD)'))
    retensi = safe_float(data.get('POT. RETENSI'))
    pph = safe_float(data.get('POT. PPH'))
    ppn = safe_float(data.get('PPN'))
    bayar_dpp = safe_float(data.get('PEMBAYARAN DPP'))
    bayar_ppn = safe_float(data.get('PEMBAYARAN PPN'))
    # round half away from zero (Excel-style), floor at 0
    def _r(x):
        x = max(0, x)
        return int(x + 0.5)
    data['SISA HUTANG (INCLD PPN)'] = _r(total - bayar_dpp - bayar_ppn)
    data['SISA HUTANG DPP'] = _r(harga - bayar_dpp)
    data['SISA HUTANG PPN'] = _r(ppn - bayar_ppn)

    # Aging buckets (auto-calculated from JTH TEMPO)
    today = date.today()
    jth = parse_date(data.get('JTH TEMPO'))
    data['BLM JATUH TEMPO'] = data['1-30 HARI'] = data['31-60 HARI'] = data['61-90 HARI'] = data['LEBIH 90 HARI'] = 0
    if data.get('STATUS TERHADAP DPP') == 'Belum Lunas' and jth is not None:
        if isinstance(jth, datetime):
            jth_date = jth.date()
        else:
            jth_date = jth
        days = (today - jth_date).days
        if days < 0:
            data['BLM JATUH TEMPO'] = 1
        elif days <= 30:
            data['1-30 HARI'] = 1
        elif days <= 60:
            data['31-60 HARI'] = 1
        elif days <= 90:
            data['61-90 HARI'] = 1
        else:
            data['LEBIH 90 HARI'] = 1


def effective_invoice(row):
    """Return the effective dedup identity — NO INVOICE INTERNAL if filled, else NO INVOICE."""
    inv_int = (row.get('NO INVOICE INTERNAL') or '').strip()
    if inv_int:
        return inv_int
    return (row.get('NO INVOICE') or '').strip()


def round_currency(data):
    """Round all currency amount fields to whole Rupiah in place (no decimals).

    Uses round-half-away-from-zero (like Excel), not banker's rounding.
    VOLUME PROGRESS stays decimal; aging buckets are integer counts.
    """
    for f in CURRENCY_FIELDS:
        if f in data and data[f] not in (None, ''):
            try:
                v = float(data[f])
                # round half away from zero: e.g. 10.5 -> 11, -10.5 -> -11
                r = int(v + (0.5 if v >= 0 else -0.5))
                data[f] = str(r)
            except (ValueError, TypeError):
                pass
    return data
