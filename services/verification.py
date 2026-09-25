"""
MODEL - Data completeness verification.

Pure computation over db.read_data(); no Flask, no rendering.

Rules (per user spec):
  CRITICAL:
    - Ada PEMBAYARAN DPP (>0) tapi TGL BAYAR DPP / PEMBAYARAN DPP VIA kosong.
    - Ada PEMBAYARAN PPN (>0) tapi TGL BAYAR PPN / PEMBAYARAN PPN VIA / NO BUKTI BAYAR PPN kosong.
    - Ada transaksi (ada rekanan) tapi NO INVOICE / TGL INV kosong.
    - Status Belum Lunas tapi JTH TEMPO kosong (tidak bisa hitung aging).
  COMPLETION:
    - TGL TERIMA BERKAS LENGKAP kosong (berkas fisik belum lengkap).
    - NO BUKTI BAYAR DPP mengandung kata "uang pinjaman" (dokumen belum dibukukan).
  WARNING:
    - Tidak ada NO PO / KONTRAK.
    - Nama rekanan tidak konsisten (beda kapitalisasi/karakter/spasi).
  DUPLICATE:
    - Nomor Invoice (efektif) sama, Rekanan sama, semua VOLUME PROGRESS = 1 (bukan cicilan).
    - Baris data identik (field inti sama — Rekanan, Invoice, Total, Pembayaran, PO).
"""
import re
from collections import defaultdict

import db
from constants import safe_float, effective_invoice


# Column keys used in rules
_COL_PEMB_DPP           = 'PEMBAYARAN DPP'
_COL_TGL_DPP            = 'TGL BAYAR DPP'
_COL_VIA_DPP            = 'PEMBAYARAN DPP VIA DIVISI'
_COL_INVOICE            = 'NO INVOICE'
_COL_TGL_INV            = 'TGL INV'
_COL_PO                 = 'NO PO / KONTRAK'
_COL_REKANAN            = 'NAMA LEVELANSIR / REKANAN'
_COL_TGL_BERKAS_LENGKAP = 'TGL TERIMA'
_COL_VOLUME             = 'VOLUME PROGRESS'
_COL_TOTAL              = 'TOTAL (INCLD)'
_COL_BUKTI_DPP          = 'NO BUKTI BAYAR DPP'
_COL_PEMB_DPP_VAL       = 'PEMBAYARAN DPP'
_COL_PEMB_PPN           = 'PEMBAYARAN PPN'
_COL_TGL_PPN            = 'TGL BAYAR PPN'
_COL_VIA_PPN            = 'PEMBAYARAN PPN VIA'
_COL_BUKTI_PPN          = 'NO BUKTI BAYAR PPN'
_COL_STATUS_DPP         = 'STATUS TERHADAP DPP'
_COL_JTH_TEMPO          = 'JTH TEMPO'


def _is_blank(val):
    """True if value is None or empty/whitespace string."""
    if val is None:
        return True
    s = str(val).strip()
    return s == ''


def _has_value(val):
    return not _is_blank(val)


def _has_amount(val):
    """True if numeric value parses to > 0."""
    return safe_float(val, 0) > 0


def _normalize_rekanan(name):
    """
    Normalize rekanan name for comparison:
    - lowercase
    - strip leading/trailing whitespace
    - collapse multiple spaces into one
    - remove dots after common prefixes (PT. -> PT)
    - remove trailing punctuation
    """
    if not name:
        return ''
    s = str(name).lower().strip()
    # collapse multiple spaces
    s = re.sub(r'\s+', ' ', s)
    # normalize PT. CV. UD. prefixes
    s = re.sub(r'\b(pt|cv|ud|pd|cv)\.\s*', r'\1 ', s)
    # remove trailing punctuation/whitespace
    s = s.strip(' .,-;:')
    return s


# ---------------------------------------------------------------------------
# Per-row completeness checks
# ---------------------------------------------------------------------------

def check_row(row, duplicate_names=None, duplicate_row_ids=None):
    """
    Evaluate a single data row against completeness rules.

    Parameters:
        row: dict of column values
        duplicate_names: set of rekanan names that have duplicate variants
                         (optional, injected by get_incomplete_rows)
        duplicate_row_ids: set of _row values identified as true duplicates
                           (optional, injected by get_incomplete_rows)

    Returns (level, reasons) where level is 'CRITICAL' | 'COMPLETION' | 'WARNING' | 'DUPLICATE' | 'OK'
    and reasons is a list of human-readable Indonesian strings.
    """
    reasons = []
    critical = False
    completion = False
    warning = False
    duplicate = False

    # Detect "uang pinjaman" in NO BUKTI BAYAR DPP + VIA kosong (dokumen belum dibukukan)
    bukti_dpp = (row.get(_COL_BUKTI_DPP) or '').strip().lower()
    is_pinjaman = bool(bukti_dpp and 'uang pinjaman' in bukti_dpp and _is_blank(row.get(_COL_VIA_DPP)))

    # CRITICAL: pembayaran DPP tanpa kelengkapan (skip if "uang pinjaman" — dokumen belum dibukukan)
    if not is_pinjaman and _has_amount(row.get(_COL_PEMB_DPP)):
        missing = []
        if _is_blank(row.get(_COL_TGL_DPP)):
            missing.append('Tgl Bayar DPP')
        if _is_blank(row.get(_COL_VIA_DPP)):
            missing.append('Dibayar via Divisi')
        if missing:
            critical = True
            reasons.append('Pembayaran DPP sudah terisi tapi ' + ' / '.join(missing) + ' masih kosong')

    # CRITICAL: pembayaran PPN tanpa kelengkapan (TGL / VIA / NO BUKTI)
    if _has_amount(row.get(_COL_PEMB_PPN)):
        missing = []
        if _is_blank(row.get(_COL_TGL_PPN)):
            missing.append('Tgl Bayar PPN')
        if _is_blank(row.get(_COL_VIA_PPN)):
            missing.append('Pembayaran PPN Via')
        if _is_blank(row.get(_COL_BUKTI_PPN)):
            missing.append('No. Bukti Bayar PPN')
        if missing:
            critical = True
            reasons.append('Pembayaran PPN sudah terisi tapi ' + ' / '.join(missing) + ' masih kosong')

    # CRITICAL: ada transaksi tapi NO INVOICE atau TGL INV kosong
    if _has_value(row.get(_COL_REKANAN)):
        inv_blank = _is_blank(row.get(_COL_INVOICE))
        tgl_blank = _is_blank(row.get(_COL_TGL_INV))
        if inv_blank or tgl_blank:
            critical = True
            parts = []
            if inv_blank:
                parts.append('No. Invoice')
            if tgl_blank:
                parts.append('Tgl Invoice')
            reasons.append('Nama rekanan sudah terisi tapi ' + ' / '.join(parts) + ' masih kosong')

    # CRITICAL: Belum Lunas tapi JTH TEMPO kosong (tidak bisa hitung aging)
    status_dpp = (row.get(_COL_STATUS_DPP) or '').strip()
    jth = (row.get(_COL_JTH_TEMPO) or '').strip()
    if status_dpp == 'Belum Lunas' and not jth:
        critical = True
        reasons.append('Status Belum Lunas tapi Jth. Tempo kosong')

    # COMPLETION: TGL TERIMA BERKAS LENGKAP kosong (berkas fisik belum lengkap)
    if _is_blank(row.get(_COL_TGL_BERKAS_LENGKAP)):
        completion = True
        reasons.append('Tgl Terima kosong')

    # COMPLETION: NO BUKTI BAYAR DPP mengandung "uang pinjaman" (dokumen belum dibukukan)
    if is_pinjaman:
        completion = True
        reasons.append('Bukti bayar masih "uang pinjaman" dan Dibayar via Divisi kosong')

    # WARNING: tidak ada nomor PO / kontrak
    if _is_blank(row.get(_COL_PO)):
        warning = True
        reasons.append('No. PO / Kontrak kosong')

    # WARNING: nama rekanan duplikat (beda kapitalisasi/karakter)
    if duplicate_names and row.get(_COL_REKANAN) in duplicate_names:
        warning = True
        reasons.append('Nama rekanan punya beberapa ejaan')

    # DUPLICATE: true duplicate — same invoice+rekanan, all vol=1, or identical rows
    if duplicate_row_ids and row.get('_row') in duplicate_row_ids:
        duplicate = True
        reasons.append('Invoice dan rekanan sama dengan baris lain')

    if critical:
        return 'CRITICAL', reasons
    if completion:
        return 'COMPLETION', reasons
    if duplicate:
        return 'DUPLICATE', reasons
    if warning:
        return 'WARNING', reasons
    return 'OK', []


# ---------------------------------------------------------------------------
# True duplicate detection — same (effective_invoice, rekanan) with vol >= 1
# or identical key fields
# ---------------------------------------------------------------------------

def find_true_duplicates(project_id=None, data=None):
    """Return set of _row values that are true duplicates.

    Three detection modes:

    1. Same effective_invoice() + same Nama Rekanan → >1 rows, ALL with
       VOLUME PROGRESS = 1 (or empty/blank, treated as 1).
       These are not cicilan — cicilan always has volume < 1.

    2. Identical rows — rows that share the same (rekanan, invoice, total,
       pembayaran_dpp, po) values, regardless of volume.

    3. Over-allocated volume — rows sharing (effective_invoice, rekanan)
       whose VOLUME PROGRESS sums to more than 1.0. A single invoice can
       never be allocated more than 100%, so any excess is a duplicate.
       This closes the gap where Mode 1 stays silent because one row has
       volume < 1 while another carries 1 (e.g. 0.5 + 1, or 1 + 1).
       Legitimate cicilan always sum to exactly 1.0, so they are unaffected
       (0.01 tolerance absorbs float rounding).

    data: optional pre-read rows (db.read_data result) to avoid a second
          read when the caller already has them. project_id is ignored
          when data is given.
    """
    data = db.read_data(project_id=project_id) if data is None else data
    if not data:
        return set()

    dup_ids = set()

    # --- Mode 1: same (effective invoice, rekanan), all vol >= 1 ---
    groups = defaultdict(list)  # (inv_eff, rekan_normalized) -> [(row_id, vol_float)]
    for row in data:
        inv = effective_invoice(row)
        rekan_raw = row.get(_COL_REKANAN, '')
        rekan = _normalize_rekanan(rekan_raw)
        if not inv or not rekan:
            continue
        vol_raw = (row.get(_COL_VOLUME) or '').strip()
        try:
            vol_f = float(vol_raw) if vol_raw else 1.0
        except (ValueError, TypeError):
            vol_f = 1.0
        groups[(inv, rekan)].append((row.get('_row'), vol_f))

    for (inv, rekan), rows in groups.items():
        if len(rows) <= 1:
            continue
        all_vol_ge1 = all(vol >= 1 for _, vol in rows)
        if all_vol_ge1:
            for rid, _ in rows:
                dup_ids.add(rid)

    # --- Mode 2: identical key fields ---
    # Rekanan normalized like Mode 1/3 so casing/space variants match.
    ident_groups = defaultdict(list)
    for row in data:
        rekan = _normalize_rekanan(row.get(_COL_REKANAN) or '')
        inv = effective_invoice(row)
        total = (row.get(_COL_TOTAL) or '').strip()
        pemb = (row.get(_COL_PEMB_DPP_VAL) or '').strip()
        po = (row.get(_COL_PO) or '').strip()
        key = (rekan, inv, total, pemb, po)
        if not rekan and not inv:
            continue
        ident_groups[key].append(row.get('_row'))

    for key, row_ids in ident_groups.items():
        if len(row_ids) >= 2:
            for rid in row_ids:
                dup_ids.add(rid)

    # --- Mode 3: over-allocated volume (catches duplicates Mode 1 misses) ---
    # Mode 1 only fires when EVERY row in the group has VOLUME PROGRESS >= 1.
    # Two rows sharing an invoice where one has volume 0.5 and the other 1
    # (or 1 and 1) slip through, even though the second is clearly an
    # over-allocation: a single invoice's volume parts can never exceed 1.0.
    # Legitimate cicilan always sum to exactly 1.0, so any group whose volumes
    # add up to more than 1 is a genuine duplicate.
    for (inv, rekan), rows in groups.items():
        if len(rows) <= 1:
            continue
        total_vol = sum(vol for _, vol in rows)
        if total_vol > 1.01:   # 0.01 tolerance for float rounding
            for rid, _ in rows:
                dup_ids.add(rid)

    return dup_ids


# ---------------------------------------------------------------------------
# Invoice-Rekanan conflict check (same invoice, different rekanan)
# Kept for reference in ignore reasons but no longer used for DUPLICATE level.
# ---------------------------------------------------------------------------

def find_invoice_rekanan_conflicts(project_id=None):
    """Return set of (invoice, rekanan) pairs that are in conflict.

    When the same NO INVOICE appears with >1 distinct Nama Levelansir/Rekanan,
    it's likely a data entry error — even if NO INVOICE INTERNAL is filled
    as a workaround, the underlying error still exists.
    Returns all distinct (invoice, rekanan) tuples that participate.

    project_id: when given, restricts the scan to a single project's rows.
    """
    data = db.read_data(project_id=project_id)
    inv_rekanans = defaultdict(set)  # invoice -> set of distinct rekanan
    for row in data:
        inv = (row.get(_COL_INVOICE) or '').strip()
        if not inv:
            continue
        rekan = (row.get(_COL_REKANAN) or '').strip()
        if not rekan:
            continue
        inv_rekanans[inv].add(rekan)

    conflicts = set()
    for inv, rekan_set in inv_rekanans.items():
        if len(rekan_set) > 1:
            for rekan in rekan_set:
                conflicts.add((inv, rekan))
    return conflicts


# ---------------------------------------------------------------------------
# Rekanan name consistency check
# ---------------------------------------------------------------------------


def find_rekanan_duplicates(project_id=None, data=None):
    """
    Group rekanan names by normalized key and return duplicate groups.

    Returns list of dicts:
        {
            'normalized': 'pt xyz konstruksi',
            'variants': [
                {'name': 'PT. XYZ Konstruksi', 'count': 5, 'row_indices': [...]},
                {'name': 'PT XYZ KONSTRUKSI', 'count': 2, 'row_indices': [...]},
            ],
            'suggested': 'PT. XYZ Konstruksi',   # most common spelling
        }

    project_id: when given, restricts the scan to a single project's rows.
    data: optional pre-read rows; skips the db.read_data() call when given.
    """
    data = db.read_data(project_id=project_id) if data is None else data

    # Group: normalized_key -> {original_name -> [row_indices]}
    groups = defaultdict(lambda: defaultdict(list))
    for row in data:
        raw = row.get(_COL_REKANAN, '')
        if _is_blank(raw):
            continue
        key = _normalize_rekanan(raw)
        if key:
            groups[key][str(raw).strip()].append(row.get('_row'))

    # Filter to groups with >1 distinct spelling
    duplicates = []
    for key, variants in sorted(groups.items()):
        if len(variants) <= 1:
            continue
        var_list = []
        for name, indices in sorted(variants.items(), key=lambda x: -len(x[1])):
            var_list.append({
                'name': name,
                'count': len(indices),
                'row_indices': indices,
            })
        duplicates.append({
            'normalized': key,
            'variants': var_list,
            'suggested': var_list[0]['name'],  # most common
        })

    return duplicates


# ---------------------------------------------------------------------------
# Ignore-list helpers
# ---------------------------------------------------------------------------

def _get_ignored_set(project_id=None):
    """Return set of _row values ignored for this scope (empty set on failure)."""
    try:
        from db_ignore import get_ignored_set
        return get_ignored_set(project_id)
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Aggregate results — single pass
# ---------------------------------------------------------------------------

_LEVEL_ORDER = {'CRITICAL': 0, 'COMPLETION': 1, 'DUPLICATE': 2, 'WARNING': 3}
_COUNT_KEY = {'CRITICAL': 'critical_count', 'COMPLETION': 'completion_count',
              'WARNING': 'warning_count', 'DUPLICATE': 'duplicate_count'}


def _analyze(project_id=None):
    """Single-pass analysis over one db.read_data() call.

    Returns (rows, counts, duplicates):
      rows:       problem rows for the verifikasi table (see get_incomplete_rows)
      counts:     level counts + total_issues (see get_counts)
      duplicates: rekanan spelling groups (see find_rekanan_duplicates)
    """
    data = db.read_data(project_id=project_id)
    ignored = _get_ignored_set(project_id)
    duplicates = find_rekanan_duplicates(data=data)
    dup_names = {v['name'] for grp in duplicates for v in grp['variants']}
    duplicate_row_ids = find_true_duplicates(data=data)

    rows = []
    counts = {
        'critical_count': 0,
        'completion_count': 0,
        'warning_count': 0,
        'duplicate_count': 0,
    }
    for row in data:
        row_idx = row.get('_row')
        if row_idx in ignored:
            continue
        level, reasons = check_row(row, duplicate_names=dup_names, duplicate_row_ids=duplicate_row_ids)
        if level == 'OK':
            continue
        rows.append({
            'row': row,
            'level': level,
            'reasons': reasons,
            'r': row.get('R', ''),
            'row_idx': row_idx,
        })
        counts[_COUNT_KEY[level]] += 1
    # CRITICAL → COMPLETION → DUPLICATE → WARNING (matches check_row precedence)
    rows.sort(key=lambda x: _LEVEL_ORDER.get(x['level'], 99))
    counts['total_issues'] = sum(counts.values())
    return rows, counts, duplicates


def get_incomplete_rows(project_id=None):
    """
    Return list of dicts for incomplete rows only (excludes OK rows and ignored rows).

    Each dict: { 'row': original_data, 'level': 'CRITICAL'|'COMPLETION'|'WARNING'|'DUPLICATE',
                 'reasons': [...], 'r': R-number, 'row_idx': _row }
    Sorted CRITICAL → COMPLETION → DUPLICATE → WARNING (matches check_row precedence).

    project_id: when given, restricts the scan to a single project's rows.
    """
    rows, _counts, _duplicates = _analyze(project_id)
    return rows


def get_counts(project_id=None):
    """Return dict with critical_count, completion_count, warning_count, duplicate_count, total_issues for badge.

    project_id: when given, restricts the scan to a single project's rows.
    """
    _rows, counts, _duplicates = _analyze(project_id)
    return counts


def get_verification_data(project_id=None):
    """Return (rows, counts, duplicates) in one pass — for the /verifikasi page."""
    return _analyze(project_id)
