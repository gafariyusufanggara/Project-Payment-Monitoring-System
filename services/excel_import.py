"""
MODEL — Excel parser shared by web-import and migrate.

Single source of truth for sheet detection, data-range scan and row
extraction.  No Flask, no I/O side effects (caller persists rows).
"""
import os
from datetime import datetime, date

from constants import IMPORT_COL_MAP, calc_sisa


def detect_sheet(wb, preferred=('', 'Monitoring Hutang', 'UTANG', 'Monitoring Hutang Reguler')):
    """Pick the best sheet name from a workbook."""
    for c in preferred:
        if c and c in wb.sheetnames:
            return c
    return wb.sheetnames[0]


def find_data_range(ws, start_row=3):
    """Return (data_start, last_data_row) using header auto-detect + empty-streak bound."""
    data_start = start_row
    for check_row in range(start_row, min(start_row + 50, ws.max_row + 1)):
        name_val = ws.cell(row=check_row, column=3).value
        if name_val and 'Nama Levelansir' in str(name_val):
            skip = 0
            for sr in range(check_row + 1, check_row + 5):
                tv = ws.cell(row=sr, column=20).value
                if tv and str(tv) in ('Total', '(Incld)'):
                    skip += 1
                else:
                    break
            data_start = check_row + 1 + skip
            break

    last_data_row = data_start - 1
    empty_streak = 0
    for check_row in range(data_start, ws.max_row + 1):
        name = ws.cell(row=check_row, column=3).value
        total = ws.cell(row=check_row, column=19).value
        if name or total:
            last_data_row = check_row
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= 30:
                break
    return data_start, last_data_row


def extract_rows(ws, data_start, last_data_row, start_r=1, project_id=''):
    """Yield (row_dict, r_number) for every valid data row in the range.

    project_id: if set, stamped onto every yielded row so it links to a project.
    """
    col_map = IMPORT_COL_MAP
    r_counter = start_r
    pid = str(project_id) if project_id else ''
    for row_idx in range(data_start, last_data_row + 1):
        row_data = {'R': r_counter}
        for src_col, dst_col in col_map.items():
            val = ws.cell(row=row_idx, column=src_col).value
            if val is not None:
                if isinstance(val, (datetime, date)):
                    val = val.strftime('%Y-%m-%d')
            else:
                val = ''
            row_data[dst_col] = val
        if not row_data.get('NAMA LEVELANSIR / REKANAN') and not row_data.get('TOTAL (INCLD)'):
            continue
        if pid:
            row_data['project_id'] = pid
        calc_sisa(row_data)
        yield row_data, r_counter
        r_counter += 1


def parse_worksheet(ws, start_row=3, project_id=''):
    """Parse a worksheet into (batch_list, imported_count, skipped_count).
    Returns None if no data found.
    project_id: when set, every imported row is stamped with this project link.
    """
    data_start, last_data_row = find_data_range(ws, start_row)
    if last_data_row < data_start:
        return None

    batch = []
    skipped = 0
    imported = 0
    for row_dict, _ in extract_rows(ws, data_start, last_data_row, project_id=project_id):
        # Count skipped as rows we don't have (implicit from data_start..last_data_row)
        batch.append(row_dict)
        imported += 1
    # Skipped = (total range rows) - (imported rows)
    total_range = last_data_row - data_start + 1
    skipped = total_range - imported
    return batch, imported, skipped


def migrate_from_excel(xlsx_path=None):
    """One-time migration from Excel to SQLite.
    Auto-discovers any .xlsx file in the project root (preferring
    the first alphabetically) when no path given and the old
    default file name doesn't exist.
    Returns batch list (or empty list) if migration needed, None if skipped.
    """
    import openpyxl
    import db
    import glob

    if xlsx_path is None:
        # __file__ = .../services/excel_import.py → go up one level to project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Legacy default
        xlsx_path = os.path.join(base_dir, 'monitoring_hutang_reguler.xlsx')
        if not os.path.exists(xlsx_path):
            # Auto-discover any .xlsx in project root (skip temp ~$ files)
            candidates = sorted(glob.glob(os.path.join(base_dir, '*.xlsx')))
            live = [p for p in candidates if not os.path.basename(p).startswith('~$')]
            if live:
                xlsx_path = live[0]
    if not os.path.exists(xlsx_path):
        return None

    existing = db.read_data()
    if existing:
        return None

    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    except Exception:
        return None

    ws = wb[detect_sheet(wb)]
    data_start, last_data_row = find_data_range(ws)
    if last_data_row < data_start:
        wb.close()
        return None

    batch = []
    for row_dict, _ in extract_rows(ws, data_start, last_data_row):
        batch.append(row_dict)

    wb.close()

    if batch:
        db.import_rows(batch)
    return batch
