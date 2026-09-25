"""
SQLite audit-log database — tracks every field-level change on edit.
Stored in a separate .db file so the main data stays clean.
"""
import os
import sqlite3
from datetime import datetime

DB_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(DB_DIR, 'monitoring_hutang_audit.db')


def _conn():
    return sqlite3.connect(DB_FILE)


def init_audit_db():
    """Create the audit tables if they don't exist."""
    from constants import COLUMNS
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                hutang_row INTEGER NOT NULL,
                field_name TEXT    NOT NULL,
                old_value  TEXT,
                new_value  TEXT,
                changed_at TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            )
        ''')
        # Full-row snapshots: latest edited state of each MAIN-DB row.
        # The main DB is immutable; edits are stored here as copies.
        cols_def = ', '.join(f'"{c}" TEXT' for c in COLUMNS)
        conn.execute(f'''
            CREATE TABLE IF NOT EXISTS audit_snapshots (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                hutang_row INTEGER NOT NULL,
                edited_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                {cols_def}
            )
        ''')
        # Store original (pre-edit) row at edit time so the audit page
        # can show a correct diff even after the main DB is re-imported.
        # JSON column — kept simple, no schema expansion.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_originals (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                hutang_row INTEGER NOT NULL UNIQUE,
                original_data TEXT
            )
        ''')
        # Migrate: add project_id to audit_snapshots if missing (added to COLUMNS later).
        try:
            conn.execute('ALTER TABLE audit_snapshots ADD COLUMN "project_id" TEXT')
        except Exception:
            pass  # already exists
        conn.commit()


def log_changes(hutang_row, old_data, new_data):
    """
    Compare old_data and new_data dicts (keyed by column name).
    Insert one row per changed field into audit_log.
    Skips AUTO_FIELDS (recalculated by calc_sisa) — only log
    fields the user explicitly edited.
    Returns number of changed fields logged.
    """
    from constants import COLUMNS, AUTO_FIELDS
    skip = set(AUTO_FIELDS)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    with _conn() as conn:
        for key in COLUMNS:
            if key in skip:
                continue
            old_val = str(old_data.get(key, '')) if old_data.get(key) is not None else ''
            new_val = str(new_data.get(key, '')) if new_data.get(key) is not None else ''
            if old_val != new_val:
                conn.execute('''
                    INSERT INTO audit_log (hutang_row, field_name, old_value, new_value, changed_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (hutang_row, key, old_val, new_val, timestamp))
                count += 1
        conn.commit()
    return count


def get_audit_for_row(hutang_row):
    """Return list of dicts for all changes to a specific row, newest first."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        # Return diff same as audit page: compare latest snapshot vs original
        cur = conn.execute(
            'SELECT hutang_row, MAX(id) AS max_id FROM audit_snapshots WHERE hutang_row = ? GROUP BY hutang_row',
            (hutang_row,)
        )
        row = cur.fetchone()
        if not row:
            return []
        cur2 = conn.execute('SELECT * FROM audit_snapshots WHERE id = ?', (row['max_id'],))
        snap = cur2.fetchone()
        if not snap:
            return []
        from constants import COLUMNS, CURRENCY_FIELDS
        import json
        cur3 = conn.execute('SELECT original_data FROM audit_originals WHERE hutang_row = ?', (hutang_row,))
        orig_row = cur3.fetchone()
        orig_raw = orig_row['original_data'] if orig_row else '{}'
        try:
            orig = json.loads(orig_raw)
        except Exception:
            orig = {}
        def _norm(v):
            if v is None:
                return ''
            s = str(v).strip()
            return '' if s in ('', '-') else s
        if orig:
            for c in CURRENCY_FIELDS:
                if c in orig and orig[c] not in (None, ''):
                    try:
                        v = float(orig[c])
                        orig[c] = str(int(v + (0.5 if v >= 0 else -0.5)))
                    except (ValueError, TypeError):
                        pass
            changed = []
            for c in COLUMNS:
                old = _norm(orig.get(c, ''))
                new = _norm(snap.get(c, ''))
                if old != new:
                    changed.append({'field_name': c, 'old_value': old, 'new_value': new, 'changed_at': snap.get('edited_at', '')})
            # Return newest-first
            changed.reverse()
            return changed
        # Fallback: audit_log
        cur4 = conn.execute(
            'SELECT * FROM audit_log WHERE hutang_row = ? ORDER BY id',
            (hutang_row,)
        )
        return cur4.fetchall()


def get_all_audit(limit=500):
    """Return recent audit entries, newest first."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        cur = conn.execute(
            'SELECT * FROM audit_log ORDER BY changed_at DESC LIMIT ?',
            (limit,)
        )
        return cur.fetchall()


def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def save_snapshot(hutang_row, row_dict, original_row=None):
    """
    Store a full copy of a main-DB row (with the latest edits applied) into
    audit_snapshots. The main DB is never modified by edit; only this copy is.

    row_dict must contain all COLUMNS keys (use constants.COLUMNS).
    If original_row is provided, it is stored in audit_originals so the
    audit page can diff against the true pre-edit baseline even after
    the main DB is re-imported.
    Returns the new snapshot id.
    """
    from constants import COLUMNS, round_currency
    round_currency(row_dict)
    cols = ['hutang_row'] + list(COLUMNS)
    placeholders = ', '.join('?' for _ in cols)
    vals = [hutang_row] + [str(row_dict.get(c, '')) if row_dict.get(c) is not None else '' for c in COLUMNS]
    with _conn() as conn:
        cur = conn.execute(
            f'INSERT INTO audit_snapshots ({", ".join(chr(34)+c+chr(34) for c in cols)}) VALUES ({placeholders})',
            vals
        )
        # Store/update the original pre-edit row (always the latest "before" state)
        if original_row is not None:
            import json
            orig_clean = {c: str(original_row.get(c, '')) if original_row.get(c) is not None else '' for c in COLUMNS}
            conn.execute(
                'INSERT OR REPLACE INTO audit_originals (hutang_row, original_data) VALUES (?, ?)',
                (hutang_row, json.dumps(orig_clean, ensure_ascii=False)),
            )
        conn.commit()
        return cur.lastrowid


def get_audit_page_data():
    """
    Build audit-page rows: for each snapshot, show WHO and WHAT changed
    (diff between the original pre-edit row and the edited snapshot).

    Uses audit_originals (stored at edit time) as baseline instead of the
    current main DB, so the diff stays correct even after re-import.

    Returns list of dicts (newest edits first):
        {'hutang_row','R','rekanan','invoice','edited_at',
         'changed':[{'field','old','new'}], 'changed_count':int}
    """
    from constants import COLUMNS, CURRENCY_FIELDS
    import json

    with _conn() as conn:
        conn.row_factory = _dict_factory
        cur = conn.execute(
            "SELECT s.* FROM audit_snapshots s "
            "INNER JOIN (SELECT hutang_row, MAX(id) AS max_id "
            "FROM audit_snapshots GROUP BY hutang_row) m "
            "ON s.id = m.max_id ORDER BY s.id DESC"
        )
        snapshots = cur.fetchall()

        cur2 = conn.execute('SELECT hutang_row, original_data FROM audit_originals')
        originals = {r['hutang_row']: r['original_data'] for r in cur2.fetchall()}

    def _norm(v):
        if v is None:
            return ''
        s = str(v).strip()
        return '' if s in ('', '-') else s

    result = []
    for snap in snapshots:
        row_idx = snap['hutang_row']
        orig_raw = originals.get(row_idx, '{}')
        try:
            orig = json.loads(orig_raw)
        except Exception:
            orig = {}
        changed = []
        if orig:
            # Normal path: compare original vs snapshot
            # Round original currency fields so decimals (132653.06)
            # don't false-match against already-rounded snapshot (132653).
            for c in CURRENCY_FIELDS:
                if c in orig and orig[c] not in (None, ''):
                    try:
                        v = float(orig[c])
                        orig[c] = str(int(v + (0.5 if v >= 0 else -0.5)))
                    except (ValueError, TypeError):
                        pass
            for c in COLUMNS:
                old = _norm(orig.get(c, ''))
                new = _norm(snap.get(c, ''))
                if old != new:
                    changed.append({'field': c, 'old': old, 'new': new})
        else:
            # Fallback for pre-migration entries (no audit_originals):
            # use audit_log which stores old/new per changed field.
            from constants import COLUMNS as _COLS
            col_set = set(_COLS)
            with _conn() as conn:
                conn.row_factory = _dict_factory
                cur3 = conn.execute(
                    'SELECT field_name, old_value, new_value FROM audit_log WHERE hutang_row = ? ORDER BY id',
                    (row_idx,)
                )
                log_entries = cur3.fetchall()
            seen_fields = set()
            for le in log_entries:
                field = le['field_name']
                if field not in col_set or field in seen_fields:
                    continue
                seen_fields.add(field)
                changed.append({
                    'field': field,
                    'old': _norm(le.get('old_value', '')),
                    'new': _norm(le.get('new_value', '')),
                })
        result.append({
            'hutang_row': row_idx,
            'R': snap.get('R', ''),
            'rekanan': snap.get('NAMA LEVELANSIR / REKANAN') or '-',
            'invoice': snap.get('NO INVOICE') or '-',
            'edited_at': snap.get('edited_at', ''),
            'changed': changed,
            'changed_count': len(changed),
        })
    return result


def get_audit_count():
    """Number of distinct main-DB rows that have been edited (have a snapshot)."""
    with _conn() as conn:
        cur = conn.execute('SELECT COUNT(DISTINCT hutang_row) FROM audit_snapshots')
        return cur.fetchone()[0] or 0


def delete_snapshots(hutang_row):
    """Remove all audit snapshots for a row (mark its audit as resolved/cleared)."""
    with _conn() as conn:
        conn.execute('DELETE FROM audit_snapshots WHERE hutang_row = ?', (hutang_row,))
        conn.execute('DELETE FROM audit_log WHERE hutang_row = ?', (hutang_row,))
        conn.execute('DELETE FROM audit_originals WHERE hutang_row = ?', (hutang_row,))
        conn.commit()


def get_audited_rows():
    """Set of hutang_row values that have at least one audit snapshot."""
    with _conn() as conn:
        cur = conn.execute('SELECT DISTINCT hutang_row FROM audit_snapshots')
        return {r[0] for r in cur.fetchall()}


def relink_audit(row_map):
    """
    Update hutang_row references in audit_snapshots, audit_log AND
    audit_originals after data re-import.
    row_map: dict of old -> new hutang_row.
    """
    with _conn() as conn:
        for old_row, new_row in row_map.items():
            for tbl in ('audit_snapshots', 'audit_log', 'audit_originals'):
                try:
                    conn.execute(
                        f'UPDATE {tbl} SET hutang_row = ? WHERE hutang_row = ?',
                        (new_row, old_row),
                    )
                except Exception:
                    pass  # table may not exist yet (pre-migration)
        conn.commit()
