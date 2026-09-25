"""
CONTROLLER — Verifikasi routes (Blueprint).

View layer: renders verifikasi.html showing rows with incomplete data.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash

from services.verification import (
    get_verification_data, check_row, find_rekanan_duplicates, find_true_duplicates,
)
from services.project_context import get_read_filter
from db_ignore import ignore_row, unignore_row, get_ignored_rows, count_ignored
from db_audit import get_audited_rows
import db

bp = Blueprint('verifikasi', __name__)


def _dup_context(pid):
    """Compute duplicate context once per request (data + names + row ids)."""
    data = db.read_data(project_id=pid)
    dup_groups = find_rekanan_duplicates(data=data)
    dup_names = {v['name'] for grp in dup_groups for v in grp['variants']}
    duplicate_row_ids = find_true_duplicates(data=data)
    return data, dup_names, duplicate_row_ids


@bp.route('/verifikasi')
def verifikasi():
    pid = get_read_filter()
    rows, counts, duplicates = get_verification_data(project_id=pid)
    return render_template(
        'verifikasi.html',
        rows=rows,
        counts=counts,
        duplicates=duplicates,
        ignored_count=count_ignored(pid),
        audited_rows=get_audited_rows(),
    )


@bp.route('/ignore/<int:row_idx>', methods=['POST'])
def ignore(row_idx):
    """Ignore a row — copy to ignore DB so it no longer appears in verification."""
    pid = get_read_filter()
    data, dup_names, duplicate_row_ids = _dup_context(pid)
    row_data = None
    for r in data:
        if r.get('_row') == row_idx:
            row_data = r
            break
    if row_data:
        alasan = request.form.get('alasan', '')
        # Compute the verification reasons so they appear in the ignore table
        _, reasons = check_row(row_data, duplicate_names=dup_names, duplicate_row_ids=duplicate_row_ids)
        masalah = '; '.join(reasons) if reasons else ''
        ignore_row(row_idx, row_data, alasan, masalah, project_id=pid)
        flash(f'Data R-{row_data.get("R", row_idx)} diabaikan dari verifikasi.', 'info')
    else:
        flash('Data tidak ditemukan. Segarkan halaman lalu coba lagi.', 'danger')
    return redirect(url_for('verifikasi.verifikasi'))


@bp.route('/ignore-batch', methods=['POST'])
def ignore_batch():
    """Ignore multiple rows at once."""
    row_idxs = request.form.getlist('row_idxs', type=int)
    alasan = request.form.get('alasan', '')
    if not row_idxs:
        flash('Tidak ada data yang dipilih.', 'warning')
        return redirect(url_for('verifikasi.verifikasi'))
    pid = get_read_filter()
    data, dup_names, duplicate_row_ids = _dup_context(pid)
    by_row = {r.get('_row'): r for r in data}
    ignored_count = 0
    for row_idx in row_idxs:
        row_data = by_row.get(row_idx)
        if not row_data:
            continue
        _, reasons = check_row(row_data, duplicate_names=dup_names, duplicate_row_ids=duplicate_row_ids)
        masalah = '; '.join(reasons) if reasons else ''
        ignore_row(row_idx, row_data, alasan, masalah, project_id=pid)
        ignored_count += 1
    flash(f'{ignored_count} data diabaikan dari verifikasi.', 'info')
    return redirect(url_for('verifikasi.verifikasi'))


@bp.route('/verifikasi/ignore')
def ignore_list():
    """Show list of ignored rows with undo capability."""
    pid = get_read_filter()
    ignored = get_ignored_rows(pid)
    return render_template('verifikasi_ignore.html', ignored=ignored, count=len(ignored))


@bp.route('/unignore/<int:row_idx>', methods=['POST'])
def unignore(row_idx):
    """Remove a row from the ignore list."""
    unignore_row(row_idx)
    flash(f'Data dikembalikan ke verifikasi.', 'success')
    return redirect(url_for('verifikasi.ignore_list'))


@bp.route('/unignore-batch', methods=['POST'])
def unignore_batch():
    """Restore multiple ignored rows at once."""
    row_idxs = request.form.getlist('row_idxs', type=int)
    if not row_idxs:
        flash('Tidak ada data yang dipilih.', 'warning')
        return redirect(url_for('verifikasi.ignore_list'))
    for row_idx in row_idxs:
        unignore_row(row_idx)
    flash(f'{len(row_idxs)} data dikembalikan ke verifikasi.', 'success')
    return redirect(url_for('verifikasi.ignore_list'))
