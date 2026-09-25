"""
CONTROLLER (Blueprint) — Project management, retention, and project dashboard.
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify

import db_project
from constants import safe_float

bp = Blueprint('project', __name__, url_prefix='/project')


# ── HELPERS ──────────────────────────────────────────────────────────

def _get_projects_for_dropdown():
    """Return list of (id, label) for select inputs."""
    return db_project.get_project_select()


def _render(project_id=None):
    """Common check: if project_id is given, ensure it exists."""
    if project_id is not None:
        p = db_project.get_project(project_id)
        if not p:
            flash('Proyek tidak ditemukan.', 'danger')
            return redirect(url_for('project.list_projects'))
    return None


# ── LIST ─────────────────────────────────────────────────────────────

@bp.route('/')
def list_projects():
    projects = db_project.get_projects()
    return render_template('projects.html', projects=projects)


# ── CREATE ───────────────────────────────────────────────────────────

@bp.route('/create', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        kode = request.form.get('kode_proyek', '').strip()
        nama = request.form.get('nama_proyek', '').strip()
        if not kode or not nama:
            flash('Kode Proyek dan Nama Proyek harus diisi.', 'danger')
            return render_template('project_detail.html', project=None)
        lokasi = request.form.get('lokasi', '')
        pemilik = request.form.get('pemilik', '')
        nilai_kontrak = safe_float(request.form.get('nilai_kontrak'))
        tgl_mulai = request.form.get('tgl_mulai', '')
        tgl_selesai = request.form.get('tgl_selesai', '')
        status = request.form.get('status', 'Aktif')
        catatan = request.form.get('catatan', '')
        try:
            pid = db_project.create_project(kode, nama, lokasi, pemilik, nilai_kontrak,
                                            tgl_mulai, tgl_selesai, status, catatan)
            flash(f'Proyek {kode} berhasil dibuat.', 'success')
            return redirect(url_for('project.edit_project', project_id=pid))
        except Exception as e:
            flash(f'Gagal membuat proyek: {e}', 'danger')
            return render_template('project_detail.html', project=None)
    return render_template('project_detail.html', project=None)


# ── EDIT ─────────────────────────────────────────────────────────────

@bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    p = db_project.get_project(project_id)
    if not p:
        flash('Proyek tidak ditemukan.', 'danger')
        return redirect(url_for('project.list_projects'))

    if request.method == 'POST':
        action = request.form.get('action', 'update')
        if action == 'update':
            kode = request.form.get('kode_proyek', '').strip()
            nama = request.form.get('nama_proyek', '').strip()
            if not kode or not nama:
                flash('Kode dan Nama Proyek harus diisi.', 'danger')
                return render_template('project_detail.html', project=p)
            lokasi = request.form.get('lokasi', '')
            pemilik = request.form.get('pemilik', '')
            nilai_kontrak = safe_float(request.form.get('nilai_kontrak'))
            tgl_mulai = request.form.get('tgl_mulai', '')
            tgl_selesai = request.form.get('tgl_selesai', '')
            status = request.form.get('status', 'Aktif')
            catatan = request.form.get('catatan', '')
            try:
                db_project.update_project(project_id, kode, nama, lokasi, pemilik, nilai_kontrak,
                                         tgl_mulai, tgl_selesai, status, catatan)
                flash('Proyek berhasil diperbarui.', 'success')
            except Exception as e:
                flash(f'Gagal memperbarui proyek: {e}', 'danger')
        elif action == 'delete':
            db_project.delete_project(project_id)
            flash('Proyek berhasil dihapus.', 'success')
            return redirect(url_for('project.list_projects'))

        p = db_project.get_project(project_id)  # refresh
        return render_template('project_detail.html', project=p)

    return render_template('project_detail.html', project=p)


# ── DELETE (GET confirmation helper) ──────────────────────────────────

@bp.route('/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    db_project.delete_project(project_id)
    flash('Proyek berhasil dihapus.', 'success')
    return redirect(url_for('project.list_projects'))


# ── PROJECT DASHBOARD ────────────────────────────────────────────────

@bp.route('/<int:project_id>/dashboard')
def project_dashboard(project_id):
    p = db_project.get_project(project_id)
    if not p:
        flash('Proyek tidak ditemukan.', 'danger')
        return redirect(url_for('project.list_projects'))

    monthly = db_project.get_realisasi_by_month(project_id)
    pph = db_project.get_pph_summary(project_id)
    total_retensi = db_project.get_retensi_from_hutang(project_id)
    retensi_groups = db_project.get_retensi_rows(project_id)

    total_realisasi = float(p.get('total_realisasi') or 0)

    total_cf_amount = sum(float(m['amount']) for m in monthly)
    cash_flow = []
    cum_amount = 0.0
    cum_bayar = 0.0
    for m in monthly:
        a = float(m['amount'])
        b = float(m['bayar'])
        cum_amount += a
        cum_bayar += b
        cash_flow.append({
            'bulan': m['bulan'],
            'amount': a,
            'bayar': b,
            'sisa': a - b,
            'cum_realisasi': cum_amount,
            'cum_bayar': cum_bayar,
            'cum_sisa': cum_amount - cum_bayar,
        })

    pph_rate = (pph['total_pph'] / pph['total_dpp'] * 100) if pph['total_dpp'] > 0 else 0
    # Retensi otomatis dari POT. RETENSI: seluruhnya masih ditahan (belum ada
    # pelacakan pengembalian), jadi outstanding = total potongan.
    retensi_count = sum(g['jumlah_invoice'] for g in retensi_groups)
    retensi_total = sum(float(g['total_retensi']) for g in retensi_groups)

    return render_template('project_dashboard.html',
                           project=p,
                           total_realisasi=total_realisasi,
                           cash_flow=cash_flow,
                           total_cf_amount=total_cf_amount,
                           pph_total=pph['total_pph'],
                           pph_dpp=pph['total_dpp'],
                           pph_rate=pph_rate,
                           retensi_outstanding=retensi_count,
                           retensi_total=retensi_total,
                           total_retensi_hutang=total_retensi)


# ── RETENSI (otomatis dari POT. RETENSI, read-only) ──────────────────

@bp.route('/<int:project_id>/retention')
def list_retention(project_id):
    p = db_project.get_project(project_id)
    if not p:
        flash('Proyek tidak ditemukan.', 'danger')
        return redirect(url_for('project.list_projects'))
    retensi_groups = db_project.get_retensi_rows(project_id)
    total_retensi = db_project.get_retensi_from_hutang(project_id)
    total_invoice = sum(g['jumlah_invoice'] for g in retensi_groups)
    return render_template('project_retention.html', project=p,
                           retensi_groups=retensi_groups,
                           total_retensi_hutang=total_retensi,
                           total_invoice=total_invoice)


# ── API: return project list for dropdown ────────────────────────────

@bp.route('/api/list')
def api_project_list():
    projects = db_project.get_project_select()
    return jsonify([{'id': pid, 'label': label} for pid, label in projects])
