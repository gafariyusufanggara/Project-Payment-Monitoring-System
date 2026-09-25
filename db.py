"""
SQLite database layer for Monitoring Hutang Reguler.
"""
import os
import sqlite3
from datetime import datetime, date

from constants import COLUMNS, DATE_FIELDS, NUMERIC_FIELDS, safe_float, parse_date, calc_sisa, round_currency

DB_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(DB_DIR, 'monitoring_hutang.db')

# Build quoted column list once
_QCOLS = [f'"{c}"' for c in COLUMNS]


def _conn():
    return sqlite3.connect(DB_FILE)


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def init_db():
    """Create the hutang table if it doesn't exist, then run column migrations."""
    with _conn() as conn:
        # TEXT is fine for all fields; we parse on read/write as needed
        cols_def = ', '.join(f'"{c}" TEXT' for c in COLUMNS)
        conn.execute(f'''
            CREATE TABLE IF NOT EXISTS hutang (
                _row INTEGER PRIMARY KEY AUTOINCREMENT,
                {cols_def}
            )
        ''')
        conn.commit()
        _migrate_columns(conn)
        _ensure_indexes(conn)


def _ensure_indexes(conn):
    """Index pencarian untuk agregasi kontrak (idempotent).

    Agregasi kontrak (db_contract._fetch_invoice_rows, get_contract_invoices)
    mencocokkan nomor PO per baris; tanpa index ini SQLite scan seluruh tabel
    hutang tiap kali halaman kontrak dibuka.
    """
    try:
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hutang_no_po '
                     'ON hutang("NO PO / KONTRAK")')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_hutang_project '
                     'ON hutang(project_id)')
        conn.commit()
    except sqlite3.Error:
        # Kolom belum ada (DB sangat lama) — index dilewati, tidak fatal.
        pass


def _migrate_columns(conn):
    """Idempotent column renames/adds/drops to match current COLUMNS."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info('hutang')")}

    renames = [
        ('TGL TERIMA BERKAS LENGKAP', 'TGL TERIMA'),
        ('HARGA (EXCL)', 'HARGA (EXLD)'),
        ('PEMBAYARAN DPP VIA', 'PEMBAYARAN DPP VIA DIVISI'),
    ]
    for old, new in renames:
        if old in existing and new not in existing:
            try:
                conn.execute(f'ALTER TABLE hutang RENAME COLUMN "{old}" TO "{new}"')
            except Exception:
                pass

    drops = ['TGL INPUT NERACA', 'NO JURNAL', 'NOMOR BUKTI PMB', 'TGL PENYERAHAN KEU DIVISI']
    for col in drops:
        if col in existing:
            try:
                conn.execute(f'ALTER TABLE hutang DROP COLUMN "{col}"')
            except Exception:
                pass

    adds = ['POT. RETENSI', 'PEMBAYARAN POT. PPH', 'NILAI YG DITERIMA VENDOR',
            'NO INVOICE INTERNAL', 'project_id']
    for col in adds:
        if col not in existing:
            try:
                conn.execute(f'ALTER TABLE hutang ADD COLUMN "{col}" TEXT')
            except Exception:
                pass

    conn.commit()


def get_distinct_kode_biaya_prefixes(project_id):
    """Return distinct first-3-char prefixes of KODE BIAYA from hutang for a project.
    Falls back to KODE BIAYA2 when KODE BIAYA is empty.
    e.g. '500', '501', etc. Sorted ascending."""
    with _conn() as conn:
        rows = conn.execute('''
            SELECT DISTINCT SUBSTR(TRIM(COALESCE(NULLIF(TRIM(COALESCE("KODE BIAYA", '')), ''),
                                                  "KODE BIAYA2")), 1, 3) AS prefix
            FROM hutang
            WHERE project_id = ? AND project_id != ''
              AND "TGL TERIMA" IS NOT NULL AND "TGL TERIMA" != ''
              AND TRIM(COALESCE(NULLIF(TRIM(COALESCE("KODE BIAYA", '')), ''),
                                "KODE BIAYA2")) != ''
            ORDER BY prefix
        ''', (str(project_id),)).fetchall()
    return [r[0] for r in rows]


def get_hutang_kategoris(project_id=None):
    """Distinct non-empty values from hutang.'KATEGORI' column.
    project_id: str/int to restrict, None for global."""
    with _conn() as conn:
        if project_id is not None and str(project_id) != 'all' and str(project_id) != '':
            rows = conn.execute('''
                SELECT DISTINCT "KATEGORI" FROM hutang
                WHERE "project_id" = ?
                  AND "KATEGORI" IS NOT NULL AND "KATEGORI" <> ''
                ORDER BY "KATEGORI"
            ''', (str(project_id),)).fetchall()
        else:
            rows = conn.execute('''
                SELECT DISTINCT "KATEGORI" FROM hutang
                WHERE "KATEGORI" IS NOT NULL AND "KATEGORI" <> ''
                ORDER BY "KATEGORI"
            ''').fetchall()
    return [r[0] for r in rows]


def read_data(project_id=None):
    """Return list of dicts with _row + all COLUMNS keys.

    project_id: when given (str/int/'all'), restrict rows to that project.
                None or 'all' returns ALL rows across every project.
    """
    where = ''
    params = ()
    if project_id is not None and str(project_id) != 'all' and str(project_id) != '':
        where = 'WHERE "project_id" = ?'
        params = (str(project_id),)
    with _conn() as conn:
        conn.row_factory = _dict_factory
        cur = conn.execute(
            f'SELECT _row, {", ".join(_QCOLS)} FROM hutang {where} ORDER BY _row',
            params,
        )
        rows = cur.fetchall()
    # Convert date strings back to display format, parse dates for Jinja compatibility
    result = []
    for r in rows:
        d = {'_row': r['_row']}
        for c in COLUMNS:
            val = r[c] if c in r else None
            # Try to parse known patterns — keep as-is, just pass string
            d[c] = val
        result.append(d)
    return result


def get_next_r():
    """Get next sequential 'R' number."""
    with _conn() as conn:
        cur = conn.execute('SELECT MAX(CAST("R" AS INTEGER)) FROM hutang')
        val = cur.fetchone()[0]
        return (val or 0) + 1


def write_row(data_dict, row_idx=None):
    """
    Insert or update a row.
    If row_idx is None → INSERT.
    If row_idx is given → UPDATE that _row.
    """
    with _conn() as conn:
        round_currency(data_dict)
        keys = list(data_dict.keys())
        if row_idx is None:
            cols = ', '.join(f'"{k}"' for k in keys)
            placeholders = ', '.join('?' for _ in keys)
            conn.execute(f'INSERT INTO hutang ({cols}) VALUES ({placeholders})',
                         [data_dict[k] for k in keys])
        else:
            sets = ', '.join(f'"{k}" = ?' for k in keys)
            vals = [data_dict[k] for k in keys] + [row_idx]
            conn.execute(f'UPDATE hutang SET {sets} WHERE _row = ?', vals)
        conn.commit()


def delete_row(row_idx):
    """Delete a row by _row, then re-number R."""
    with _conn() as conn:
        conn.execute('DELETE FROM hutang WHERE _row = ?', (row_idx,))
        conn.commit()
        # Renumber R while connection is still open
        _renumber_r(conn)


def delete_all_data():
    """Delete all rows from hutang table (resets auto-increment)."""
    with _conn() as conn:
        conn.execute('DELETE FROM hutang')
        conn.commit()


def delete_rows_by_project(project_id):
    """Delete only hutang rows linked to a specific project (by project_id TEXT col).

    Used by per-project Excel re-import so other projects stay untouched.
    Returns count of deleted rows.
    """
    pid = str(project_id)
    with _conn() as conn:
        cur = conn.execute(
            'DELETE FROM hutang WHERE "project_id" = ?', (pid,)
        )
        deleted = cur.rowcount
        conn.commit()
        if deleted:
            _renumber_r(conn)
    return deleted


def _renumber_r(conn):
    """Re-assign sequential R numbers based on _row order."""
    cur = conn.execute('SELECT _row FROM hutang ORDER BY _row')
    rows = cur.fetchall()
    for idx, (rid,) in enumerate(rows, 1):
        conn.execute('UPDATE hutang SET "R" = ? WHERE _row = ?', (idx, rid))
    conn.commit()


def import_rows(rows_data):
    """
    Bulk-insert a list of dicts (each keyed by column name).
    Uses ALL keys present across ALL rows (not just first row)
    so columns with nulls in early rows aren't silently dropped.
    Returns the count of inserted rows.
    """
    if not rows_data:
        return 0
    inserted = 0
    with _conn() as conn:
        # Union of all keys across every row — prevents data loss
        # when the first row has None for a column (e.g. NO PO / KONTRAK).
        keys = sorted(set(k for rd in rows_data for k in rd.keys()))
        cols = ', '.join(f'"{k}"' for k in keys)
        placeholders = ', '.join('?' for _ in keys)
        for rd in rows_data:
            try:
                conn.execute(f'INSERT INTO hutang ({cols}) VALUES ({placeholders})',
                             [rd.get(k, '') for k in keys])
                inserted += 1
            except Exception:
                continue
        conn.commit()
    return inserted


def get_levelansir_retensi(project_id=None):
    """Return levelansir/rekanan with POT. RETENSI > 0, grouped by name.

    Returns list of dicts: {nama, total_retensi, jumlah_invoice, invoices: [...]}
    Each invoice entry: {row, no_invoice, no_po, nilai_retensi, harga_exld,
                         project_id, kode_biaya, deskripsi, sisa_hutang}
    Respects project_id filter (same semantics as read_data).
    """
    where = ''
    params = ()
    if project_id is not None and str(project_id) != 'all' and str(project_id) != '':
        where = 'AND "project_id" = ?'
        params = (str(project_id),)
    with _conn() as conn:
        conn.row_factory = _dict_factory
        rows = conn.execute(f'''
            SELECT _row,
                   "NAMA LEVELANSIR / REKANAN" AS nama,
                   "NO INVOICE"                 AS no_invoice,
                   "NO PO / KONTRAK"            AS no_po,
                   "POT. RETENSI"               AS retensi,
                   "HARGA (EXLD)"               AS harga_exld,
                   "project_id"                 AS project_id,
                   "KODE BIAYA2"                AS kode_biaya,
                   "DESKRIPSI"                  AS deskripsi,
                   "SISA HUTANG (INCLD PPN)"   AS sisa_hutang,
                   "STATUS TERHADAP DPP"        AS status_dpp
            FROM hutang
            WHERE CAST(COALESCE("POT. RETENSI", '0') AS REAL) > 0
              AND "NAMA LEVELANSIR / REKANAN" IS NOT NULL
              AND TRIM("NAMA LEVELANSIR / REKANAN") <> ''
              {where}
            ORDER BY "NAMA LEVELANSIR / REKANAN", _row
        ''', params).fetchall()

    # Group by nama
    grouped = {}
    for r in rows:
        key = (r['nama'] or '').strip()
        if key not in grouped:
            grouped[key] = {'nama': key, 'total_retensi': 0.0, 'jumlah_invoice': 0, 'invoices': []}
        ret = float(r['retensi'] or 0)
        grouped[key]['total_retensi'] += ret
        grouped[key]['jumlah_invoice'] += 1
        harga_exld = float(r['harga_exld'] or 0)
        grouped[key]['invoices'].append({
            '_row': r['_row'],
            'no_invoice': r['no_invoice'] or '',
            'no_po': r['no_po'] or '',
            'nilai_retensi': ret,
            'harga_exld': harga_exld,
            'project_id': r['project_id'] or '',
            'kode_biaya': r['kode_biaya'] or '',
            'deskripsi': r['deskripsi'] or '',
            'total': max(0, harga_exld - ret),
            'status_dpp': r['status_dpp'] or '',
        })

    return sorted(grouped.values(), key=lambda x: (-x['total_retensi'], x['nama']))
