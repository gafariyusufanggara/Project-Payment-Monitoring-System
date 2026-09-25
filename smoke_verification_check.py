# -*- coding: utf-8 -*-
"""Smoke check: verification single-pass analysis + ignore scoping.

Run:  python smoke_verification_check.py
Read-only against real data; ignore-scoping test uses a throwaway row in the
real ignore DB and removes it afterwards.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
import db_ignore
from services.verification import (
    get_verification_data, get_incomplete_rows, get_counts,
    find_rekanan_duplicates, find_true_duplicates, check_row,
)

# --- 1. Single-pass consistency on real data (global scope) ---
rows, counts, duplicates = get_verification_data('all')
assert len(rows) == counts['total_issues'], f"rows {len(rows)} != total {counts['total_issues']}"
assert counts['total_issues'] == sum(
    counts[k] for k in ('critical_count', 'completion_count', 'warning_count', 'duplicate_count'))
order = {'CRITICAL': 0, 'COMPLETION': 1, 'DUPLICATE': 2, 'WARNING': 3}
levels = [r['level'] for r in rows]
assert levels == sorted(levels, key=order.get), 'sort order broken'

# wrappers return the same as the single pass
assert get_counts('all') == counts
assert get_incomplete_rows('all') == rows
assert find_rekanan_duplicates(data=None) == find_rekanan_duplicates('all')
print(f'[1] global pass OK: {counts}  dup_groups={len(duplicates)}')

# --- 2. Per-project scope equals wrapper on that scope ---
projs = [r['project_id'] for r in db.read_data() if r.get('project_id')]
if projs:
    pid = projs[0]
    rows_p, counts_p, _ = get_verification_data(pid)
    assert counts_p == get_counts(pid)
    assert len(rows_p) == counts_p['total_issues']
    print(f'[2] project {pid!r} pass OK: {counts_p}')
else:
    print('[2] no projects in DB, skipped')

# --- 3. Ignore scoping in db_ignore (write + cleanup) ---
FAKE = {'R': 'SMOKE', 'NAMA LEVELANSIR / REKANAN': 'ZZ SMOKE', 'NO INVOICE': 'SMOKE-1',
        'NO PO / KONTRAK': '', 'KATEGORI': ''}
# Real DB may contain legacy rows (project_id NULL/'') visible from every scope,
# so all assertions are relative to the pre-insert baseline.
base_smoke = db_ignore.count_ignored('__smoke__')
base_other = db_ignore.count_ignored('other')
assert base_smoke == base_other, 'legacy baseline must be identical across scopes'
db_ignore.ignore_row(10**9, FAKE, 'test', 'test', project_id='__smoke__')
try:
    assert db_ignore.count_ignored('__smoke__') == base_smoke + 1, 'scoped count should see the new row'
    assert db_ignore.count_ignored('other') == base_other, 'other scope must not see the row'
    assert db_ignore.get_ignored_set('__smoke__') == db_ignore.get_ignored_set('other') | {10**9}
    assert 10**9 in db_ignore.get_ignored_set('all'), 'global scope sees everything'
    # legacy/global entry (project_id '') visible from every scope
    db_ignore.ignore_row(10**9 + 1, FAKE, 'legacy', 'legacy')  # project_id ''
    assert db_ignore.count_ignored('other') == base_other + 1, 'legacy row must stay global'
    assert db_ignore.count_ignored('__smoke__') == base_smoke + 2
    print('[3] ignore scoping OK')
finally:
    db_ignore.unignore_row(10**9)
    db_ignore.unignore_row(10**9 + 1)
    assert db_ignore.count_ignored('__smoke__') == base_smoke, 'cleanup failed'
    assert db_ignore.count_ignored('other') == base_other, 'cleanup failed'

# --- 4. check_row + sort: duplicate beats warning ---
row_dup = {'NAMA LEVELANSIR / REKANAN': 'PT A', 'NO INVOICE': 'INV-1', 'TGL INV': '2026-01-01',
           'NO PO / KONTRAK': '', 'PEMBAYARAN DPP': '', 'PEMBAYARAN PPN': '',
           'STATUS TERHADAP DPP': '', 'JTH TEMPO': '', 'TGL BAYAR DPP': '', 'TGL BAYAR PPN': '',
           'TGL TERIMA': '2026-01-02', 'NO BUKTI BAYAR DPP': '', 'VOLUME PROGRESS': '1',
           'TOTAL (INCLD)': '100', '_row': 1}
lvl, _ = check_row(row_dup, duplicate_row_ids={1})
assert lvl == 'DUPLICATE', lvl
print('[4] duplicate-over-warning precedence OK')

print('ALL CHECKS PASSED')
