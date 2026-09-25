"""
CONTROLLER — Main routes: dashboard, CRUD, stats, categories.

Thin layer: pulls data from services (model), passes to templates (view).
"""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash

import db
import db_audit
from constants import (
    COLUMNS, FORM_FIELDS, DATE_FIELDS, NUMERIC_FIELDS,
    CATEGORIES, STATUS_DPP, STATUS_PPN, KODE_BIAYA,
    save_categories, calc_sisa, round_currency, CURRENCY_FIELDS,
)
from services.dashboard import build_dashboard_context

bp = Blueprint('main', __name__)


# ── Dashboard / index ──────────────────────────────────

@bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))

@bp.route('/dashboard')
def dashboard():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    ctx = build_dashboard_context(pid)
    ctx.update(
        tab='tabDashboard',
        categories=CATEGORIES,
        status_dpp=STATUS_DPP,
        status_ppn=STATUS_PPN,
        form_fields=FORM_FIELDS,
        date_fields=DATE_FIELDS,
        numeric_fields=NUMERIC_FIELDS,
        audited_rows=sorted(db_audit.get_audited_rows()),
    )
    return render_template('index.html', **ctx)

@bp.route('/data-hutang')
def data_hutang():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    # Categories actually present in the DB (so new values appear in the filter).
    db_cats = sorted({r.get('KATEGORI', '') for r in db.read_data(pid) if r.get('KATEGORI')})
    # Union with configured categories so known ones still show even if currently unused.
    all_cats = sorted(set(CATEGORIES) | set(db_cats))
    audited_rows = sorted(db_audit.get_audited_rows())
    # Only show the Retensi column when at least one row actually has a value.
    rows = db.read_data(pid)
    has_retensi = any((r.get('POT. RETENSI') or '').strip() not in ('', '0', '0.0') for r in rows)
    ctx = build_dashboard_context(pid)
    ctx.update(
        tab='tabData',
        categories=all_cats,
        audited_rows=audited_rows,
        status_dpp=STATUS_DPP,
        status_ppn=STATUS_PPN,
        form_fields=FORM_FIELDS,
        date_fields=DATE_FIELDS,
        numeric_fields=NUMERIC_FIELDS,
        kode_biaya_list=KODE_BIAYA,
        has_retensi=has_retensi,
    )
    return render_template('index.html', **ctx)


# ── CRUD ───────────────────────────────────────────────

@bp.route('/edit/<int:row_idx>', methods=['GET'])
def edit_form(row_idx):
    data = db.read_data()
    row_data = next((r for r in data if r.get('_row') == row_idx), None)
    if row_data is None:
        return jsonify({'error': 'Row not found'}), 404
    # Round currency fields so the form shows whole Rupiah values.
    # Prevents false audit diffs when user saves without changes.
    round_currency(row_data)
    return jsonify(row_data)


@bp.route('/audit/row/<int:row_idx>')
def audit_row(row_idx):
    """Return audit change log for a single row as JSON."""
    entries = db_audit.get_audit_for_row(row_idx)
    return jsonify(entries)


@bp.route('/edit/<int:row_idx>', methods=['POST'])
def edit(row_idx):
    existing = db.read_data()
    row = next((r for r in existing if r.get('_row') == row_idx), None)
    if row is None:
        flash('Data tidak ditemukan!', 'error')
        return redirect(url_for('main.index'))

    # Start from the ORIGINAL full row (main DB is immutable).
    snapshot = {c: (row.get(c, '') if row.get(c) is not None else '') for c in COLUMNS}
    snapshot['R'] = row.get('R', '')

    # Apply only the fields the form can edit (FORM_FIELDS).
    for field in FORM_FIELDS:
        if field in request.form:
            snapshot[field] = request.form.get(field, '').strip()

    # Round currency fields to match DB values (prevents false audit diffs
    # when calc_sisa recalculates rounded amounts vs stored decimals).
    round_currency(snapshot)

    # Recompute auto fields from the (possibly edited) values.
    calc_sisa(snapshot)

    # Persist the full edited row as a COPY in the audit DB.
    # The main DB (db.hutang) is NEVER written here.
    # Pass the original row so the audit page can diff against the
    # true pre-edit baseline, even after the main DB is re-imported.
    sid = db_audit.save_snapshot(row_idx, snapshot, original_row=row)

    # Round original row for comparison — DB may store decimals
    # (e.g. 132653.06) while snapshot is already rounded (132653).
    orig_for_log = {c: row.get(c, '') for c in COLUMNS}
    round_currency(orig_for_log)
    db_audit.log_changes(row_idx, orig_for_log, snapshot)

    if sid:
        flash('Data berhasil diedit! Salinan tersimpan di DB Audit (DB utama tidak diubah).', 'success')
    else:
        flash('Gagal menyimpan ke DB Audit.', 'error')
    return redirect(url_for('main.index'))


@bp.route('/delete/<int:row_idx>', methods=['POST'])
def delete(row_idx):
    db.delete_row(row_idx)
    flash('Data berhasil dihapus!', 'success')
    return redirect(url_for('main.index'))


# ── AUDIT PAGE ───────────────────────────────────────

def _fmt_audit_val(field, val):
    """Rp formatting for currency-field diffs; raw text otherwise ('-' if empty)."""
    s = '' if val is None else str(val).strip()
    if not s or s == '-':
        return '-'
    if field in CURRENCY_FIELDS:
        try:
            return '{:,}'.format(int(float(s))).replace(',', '.')
        except (ValueError, TypeError):
            pass
    return s


@bp.route('/audit')
def audit():
    rows = db_audit.get_audit_page_data()
    for row in rows:
        for c in row['changed']:
            c['old_fmt'] = _fmt_audit_val(c['field'], c['old'])
            c['new_fmt'] = _fmt_audit_val(c['field'], c['new'])
    total_changed = sum(r['changed_count'] for r in rows)
    return render_template(
        'audit.html', audit_rows=rows, audit_count=len(rows),
        total_changed=total_changed,
        avg_changed=round(total_changed / len(rows), 1) if rows else 0,
        latest_edit=rows[0]['edited_at'] if rows else '-',
    )


@bp.route('/audit/clear/<int:row_idx>', methods=['POST'])
def audit_clear(row_idx):
    db_audit.delete_snapshots(row_idx)
    flash('Audit untuk data tersebut telah ditandai selesai.', 'success')
    return redirect(url_for('main.audit'))


@bp.route('/audit/clear-batch', methods=['POST'])
def audit_clear_batch():
    row_idxs = request.form.getlist('row_idxs', type=int)
    if not row_idxs:
        flash('Tidak ada data yang dipilih.', 'warning')
        return redirect(url_for('main.audit'))
    for row_idx in row_idxs:
        db_audit.delete_snapshots(row_idx)
    flash(f'{len(row_idxs)} audit telah ditandai selesai.', 'success')
    return redirect(url_for('main.audit'))


# ── LEVELANSIR / REKANAN RETENSI ──────────────────────

@bp.route('/levelansir-retensi')
def levelansir_retensi():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    levelansir_list = db.get_levelansir_retensi(pid)
    total_retensi = sum(lv['total_retensi'] for lv in levelansir_list)
    total_invoices = sum(lv['jumlah_invoice'] for lv in levelansir_list)
    total_setelah_retensi = sum(
        inv.get('total', 0)
        for lv in levelansir_list
        for inv in lv['invoices']
    )
    return render_template(
        'levelansir_retensi.html',
        levelansir_list=levelansir_list,
        total_retensi=total_retensi,
        total_setelah_retensi=total_setelah_retensi,
        total_levelansir=len(levelansir_list),
        total_invoices=total_invoices,
        active_project_id=pid,
    )


# ── ACTIVE PROJECT SWITCH (session) ────────────────────

@bp.route('/api/set-project', methods=['POST'])
def set_project():
    """Set the active project scope stored in the session.

    Body: {"project_id": <id|"all">}. Returns the new active value.
    All read paths consume session['active_project_id'] via project_context.
    """
    from services.project_context import set_active_project_id, get_active_project_id
    data = request.get_json(silent=True) or {}
    set_active_project_id(data.get('project_id'))
    return jsonify({'active_project_id': get_active_project_id()})


# ── API: stats ─────────────────────────────────────────

@bp.route('/api/stats')
def api_stats():
    from constants import safe_float, is_excluded_row
    from services.dashboard import _dedup_debt_rows
    data = [r for r in db.read_data() if not is_excluded_row(r)]
    deduped = _dedup_debt_rows(data)
    return jsonify({
        'total_records': len(data),
        'total_tagihan': sum(safe_float(r.get('TOTAL (INCLD)')) for r in deduped),
        'lunas': sum(1 for r in data if r.get('STATUS TERHADAP DPP') == 'Lunas'),
        'belum_lunas': sum(1 for r in data if r.get('STATUS TERHADAP DPP') == 'Belum Lunas'),
    })


# ── API: categories ────────────────────────────────────

@bp.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': CATEGORIES})


@bp.route('/api/categories', methods=['POST'])
def add_category():
    data = request.get_json()
    new_cat = data.get('name', '').strip()
    if not new_cat:
        return jsonify({'error': 'Nama kategori kosong'}), 400
    if new_cat in CATEGORIES:
        return jsonify({'error': 'Kategori sudah ada'}), 400
    CATEGORIES.append(new_cat)
    save_categories(CATEGORIES)
    return jsonify({'categories': CATEGORIES})


@bp.route('/api/categories/<name>', methods=['DELETE'])
def delete_category(name):
    if name not in CATEGORIES:
        return jsonify({'error': 'Kategori tidak ditemukan'}), 404
    CATEGORIES.remove(name)
    save_categories(CATEGORIES)
    return jsonify({'categories': CATEGORIES, 'message': f'Kategori "{name}" dihapus'})
