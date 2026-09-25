"""
SQLite database for ignored verification rows.

Stores a reference (_row from the main hutang table) plus a snapshot
of the row data so the user can review what was ignored.
"""
import os
import sqlite3

DB_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(DB_DIR, 'monitoring_hutang_ignore.db')


def _conn():
    return sqlite3.connect(DB_FILE)


def init_ignore_db():
    """Create the ignored table if it doesn't exist (adds masalah col if missing)."""
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ignored (
                hutang_row INTEGER PRIMARY KEY,
                r TEXT,
                rekanan TEXT,
                no_invoice TEXT,
                no_po TEXT,
                kategori TEXT,
                masalah TEXT,
                alasan TEXT,
                ignored_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.commit()
    # Migration: add masalah column if old DB doesn't have it
    try:
        with _conn() as conn:
            conn.execute('ALTER TABLE ignored ADD COLUMN masalah TEXT')
            conn.commit()
    except Exception:
        pass  # already exists
    # Migration: add kategori column if old DB doesn't have it
    try:
        with _conn() as conn:
            conn.execute('ALTER TABLE ignored ADD COLUMN kategori TEXT')
            conn.commit()
    except Exception:
        pass  # already exists
    # Migration: add project_id column if old DB doesn't have it
    try:
        with _conn() as conn:
            conn.execute('ALTER TABLE ignored ADD COLUMN project_id TEXT')
            conn.commit()
    except Exception:
        pass  # already exists
    # Vendors whose invoices are non-procurement (sewa, jasa, dll)
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ignored_vendors (
                vendor_norm TEXT PRIMARY KEY,
                vendor TEXT,
                alasan TEXT,
                ignored_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.commit()


def ignore_row(row_idx, row_data, alasan='', masalah='', project_id=None):
    """Insert a row into the ignored table (copy from main hutang data).

    project_id: None/'all' stores '' (global entry, applies to every scope);
                otherwise stores the project id so the ignore only applies
                while that project is active.
    """
    with _conn() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO ignored (hutang_row, r, rekanan, no_invoice, no_po, kategori, masalah, alasan, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            row_idx,
            row_data.get('R', ''),
            row_data.get('NAMA LEVELANSIR / REKANAN', ''),
            row_data.get('NO INVOICE', ''),
            row_data.get('NO PO / KONTRAK', ''),
            row_data.get('KATEGORI', ''),
            masalah,
            alasan,
            '' if project_id is None or str(project_id) == 'all' else str(project_id),
        ))
        conn.commit()


def unignore_row(row_idx):
    """Remove a row from the ignored table."""
    with _conn() as conn:
        conn.execute('DELETE FROM ignored WHERE hutang_row = ?', (row_idx,))
        conn.commit()


def get_ignored_set(project_id=None):
    """Return set of hutang_row values that are ignored.

    project_id: None/'all' → every ignored row (global scope);
                a project id → rows of that project plus legacy/global rows
                (project_id NULL or '').
    """
    with _conn() as conn:
        if project_id is None or str(project_id) == 'all':
            cur = conn.execute('SELECT hutang_row FROM ignored')
        else:
            cur = conn.execute(
                'SELECT hutang_row FROM ignored WHERE project_id = ? OR project_id IS NULL OR project_id = ?',
                (str(project_id), ''),
            )
        return {r[0] for r in cur.fetchall()}


def get_ignored_rows(project_id=None):
    """Return list of dicts for ignored rows, same scoping as get_ignored_set()."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        if project_id is None or str(project_id) == 'all':
            cur = conn.execute('SELECT * FROM ignored ORDER BY ignored_at DESC')
        else:
            cur = conn.execute(
                'SELECT * FROM ignored WHERE project_id = ? OR project_id IS NULL OR project_id = ? ORDER BY ignored_at DESC',
                (str(project_id), ''),
            )
        return cur.fetchall()


def count_ignored(project_id=None):
    """Return number of ignored rows, same scoping as get_ignored_set()."""
    with _conn() as conn:
        if project_id is None or str(project_id) == 'all':
            cur = conn.execute('SELECT COUNT(*) FROM ignored')
        else:
            cur = conn.execute(
                'SELECT COUNT(*) FROM ignored WHERE project_id = ? OR project_id IS NULL OR project_id = ?',
                (str(project_id), ''),
            )
        return cur.fetchone()[0]


def relink_ignored(row_map):
    """
    Update hutang_row references after data re-import.
    row_map: dict of old_hutang_row -> new_hutang_row
    """
    with _conn() as conn:
        for old_row, new_row in row_map.items():
            conn.execute(
                'UPDATE ignored SET hutang_row = ? WHERE hutang_row = ?',
                (new_row, old_row),
            )
        conn.commit()


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


# ── IGNORED VENDORS (belum-terdaftar kontrak) ────────────────────────

def normalize_vendor(v):
    """Normalize vendor name for matching: collapse whitespace + uppercase."""
    return ' '.join((v or '').split()).upper()


def ignore_vendor(vendor, alasan=''):
    norm = normalize_vendor(vendor)
    if not norm:
        return
    with _conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO ignored_vendors (vendor_norm, vendor, alasan) VALUES (?, ?, ?)',
            (norm, (vendor or '').strip(), alasan))
        conn.commit()


def unignore_vendor(vendor):
    with _conn() as conn:
        conn.execute('DELETE FROM ignored_vendors WHERE vendor_norm = ?',
                     (normalize_vendor(vendor),))
        conn.commit()


def get_ignored_vendor_set():
    with _conn() as conn:
        return {r[0] for r in conn.execute('SELECT vendor_norm FROM ignored_vendors')}


def get_ignored_vendors():
    with _conn() as conn:
        conn.row_factory = _dict_factory
        return conn.execute(
            'SELECT * FROM ignored_vendors ORDER BY ignored_at DESC').fetchall()
