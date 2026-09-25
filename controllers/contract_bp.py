"""
CONTROLLER (Blueprint) — Registri Kontrak Vendor (Procurement).

Routes:
  GET  /kontrak                     -> daftar kontrak + KPI
  GET  /kontrak/<id>                -> detail + daftar invoice yang cocok
  POST /kontrak/<id>                -> update / hapus
  GET  /kontrak/import              -> halaman import Excel
  POST /kontrak/import              -> upload + parse + upsert
  GET  /kontrak/belum-terdaftar     -> nomor kontrak di invoice tanpa registri
  POST /kontrak/belum-terdaftar/abaikan-vendor     -> abaikan vendor
  POST /kontrak/belum-terdaftar/kembalikan-vendor  -> batalkan abaikan
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for

import db_contract
import db_ignore
from constants import safe_float
from services import contract_excel

bp = Blueprint('contract', __name__, url_prefix='/kontrak')


def _projects():
    from db_project import get_project_select
    return get_project_select()


def _active_project_id():
    from services.project_context import get_read_filter
    return get_read_filter()


# ── LIST ─────────────────────────────────────────────────────────────

@bp.route('/')
def list_contracts():
    pid = _active_project_id()
    contracts = db_contract.get_contracts(pid)
    summary = db_contract.get_summary(pid)
    project_labels = {str(p_id): label for p_id, label in _projects()}
    return render_template('contracts.html',
                           contracts=contracts,
                           summary=summary,
                           project_labels=project_labels,
                           project_list=_projects())


# ── DETAIL ───────────────────────────────────────────────────────────

@bp.route('/<int:contract_id>')
def contract_detail(contract_id):
    c = db_contract.get_contract(contract_id)
    if not c:
        flash('Kontrak tidak ditemukan.', 'danger')
        return redirect(url_for('contract.list_contracts'))
    invoices = db_contract.get_contract_invoices(c['no_kontrak'])
    termins = db_contract.enrich_termins(db_contract.get_termins(contract_id), c)
    return render_template('contract_detail.html', contract=c, invoices=invoices,
                           termins=termins, project_list=_projects(),
                           ppn_rate=db_contract.PPN_RATE)


@bp.route('/<int:contract_id>', methods=['POST'])
def contract_action(contract_id):
    action = request.form.get('action', 'update')
    if action == 'delete':
        db_contract.delete_contract(contract_id)
        flash('Kontrak berhasil dihapus.', 'success')
        return redirect(url_for('contract.list_contracts'))

    c = db_contract.get_contract(contract_id)
    if not c:
        flash('Kontrak tidak ditemukan.', 'danger')
        return redirect(url_for('contract.list_contracts'))

    no = request.form.get('no_kontrak', '').strip()
    vendor = request.form.get('vendor', '').strip()
    if not no or not vendor:
        flash('No. Kontrak dan Vendor harus diisi.', 'danger')
        return redirect(url_for('contract.contract_detail', contract_id=contract_id))

    dup = db_contract.get_contract_by_no(no)
    if dup and dup['id'] != contract_id:
        flash(f'No. kontrak "{no}" sudah dipakai kontrak lain.', 'danger')
        return redirect(url_for('contract.contract_detail', contract_id=contract_id))

    try:
        db_contract.update_contract(
            contract_id, no, vendor,
            request.form.get('project_id', ''),
            safe_float(request.form.get('nilai_kontrak')),
            request.form.get('tgl_kontrak', ''),
            request.form.get('tgl_mulai', ''),
            request.form.get('tgl_selesai', ''),
            request.form.get('keterangan', ''),
            request.form.get('tipe_pekerjaan', ''),
            request.form.get('item_pekerjaan', ''),
            request.form.get('metode_pembayaran', ''),
            request.form.get('durasi_termin', ''),
            request.form.get('tipe_kontrak', ''),
            request.form.get('metode_penetapan', ''),
            request.form.get('ppn_rate', ''))
        flash('Kontrak berhasil diperbarui.', 'success')
    except Exception as e:
        flash(f'Gagal memperbarui kontrak: {e}', 'danger')
    return redirect(url_for('contract.contract_detail', contract_id=contract_id))


# ── IMPORT EXCEL ─────────────────────────────────────────────────────

@bp.route('/import', methods=['GET'])
def import_page():
    return render_template('contract_import.html', project_list=_projects())


@bp.route('/import/template')
def import_template():
    """Generate template Excel format procurement (kolom lengkap + petunjuk)."""
    import io
    from datetime import datetime
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Kontrak Vendor'  # dikenali detect_contract_sheet saat re-upload

    # Nama header HARUS tetap dikenali HEADER_ALIASES di services/contract_excel.py.
    # Format terbaru (docs/Template Kontrak Vendor Terbaru.csv).
    headers = ['No', 'Tipe Pekerjaan', 'Item Pekerjaan', 'No PO', 'Vendor',
               'Tipe Kontrak', 'Nilai Kontrak', 'Tgl Kontrak', 'Tgl Kontrak Selesai',
               'Metode Penetapan Nilai Kontrak', 'PPN (%)', 'Total DPP', 'Total PPN',
               'Metode Pembayaran', 'Termin', 'Tgl Maksimal Termin', 'Termin (%)',
               'Normalisasi Termin (%)', 'Nilai DPP Termin', 'Nilai PPN Termin',
               'Durasi Termin Pembayaran (Hari)', 'Total Tagihan (Exclude PPH)',
               'Retensi (5%)', 'Tgl Terima Berkas Lengkap', 'Keterangan']
    ws.append(headers)
    # start_color/end_color mengisi fgColor DAN bgColor sekaligus: pada OOXML,
    # solid fill memakai bgColor sebagai warna latar, jadi fgColor saja membuat
    # WPS Office / Excel versi lama menampilkan header HITAM (bgColor default).
    fill = PatternFill(fill_type='solid', start_color='0F172A', end_color='0F172A')
    thin = Border(*[Side(style='thin', color='CBD5E1')] * 4)
    for cell in ws[1]:
        cell.font = Font(color='FFFFFF', bold=True, size=10)
        cell.fill = fill
        cell.alignment = Alignment(vertical='center', horizontal='center',
                                   wrap_text=True)
    widths = (5, 14, 26, 34, 30, 12, 18, 12, 14, 16, 9, 18, 16, 18, 24, 14,
              10, 12, 18, 16, 12, 18, 12, 16, 30)
    for col, w in zip('ABCDEFGHIJKLMNOPQRSTUVWXY', widths):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = 'F2'
    # Sheet data sengaja KOSONG: contoh tidak ikut terimport secara tidak sengaja.
    # Kolom Total DPP/Total PPN/Total Tagihan/Retensi boleh dikosongkan —
    # dihitung ulang aplikasi saat import.

    # ── Sheet Petunjuk (tidak pernah diparse: detect_contract_sheet selalu
    #    memilih sheet "Kontrak Vendor" karena nama mengandung 'kontrak') ──
    guide = wb.create_sheet('Petunjuk')
    guide.sheet_properties.tabColor = 'F59E0B'
    rules = [
        'CARA ISI SHEET "Kontrak Vendor":',
        '1. Satu baris = satu termin pembayaran. Satu No PO boleh punya beberapa baris termin.',
        '2. No PO, Vendor, Nilai Kontrak, tanggal, dst cukup diisi di BARIS PERTAMA kontrak;',
        '    baris termin berikutnya cukup isi kolom "Termin", "Termin (%)", "Nilai DPP Termin", "Nilai PPN Termin".',
        '3. "Nilai Kontrak" = nilai total kontrak. PPN Exclude: sama dengan Total DPP;',
        '    PPN Include: sudah termasuk PPN (Total DPP lebih kecil).',
        '4. "Termin (%)" = persen mentah dari PO (tidak harus total 100%);',
        '    "Normalisasi Termin (%)" dihitung ulang otomatis oleh aplikasi (total selalu 100%).',
        '5. "Nilai DPP Termin" & "Nilai PPN Termin" = nilai per termin (wajib diisi).',
        '6. "PPN (%)" = tarif PPN kontrak (mis. 11%) — dipakai menghitung PPN bila Nilai PPN Termin kosong.',
        '7. Kolom "Total DPP", "Total PPN", "Total Tagihan (Exclude PPH)", "Retensi (5%)" boleh kosong (dihitung aplikasi).',
        '8. Metode Penetapan Nilai Kontrak: "PPN Exclude" / "PPN Include".',
        '    Metode Pembayaran: "PPN Include" / "PPN Reimburse" — menentukan Total Pembayaran.',
        '9. Format tanggal YYYY-MM-DD (contoh: 2025-12-24). Jangan mengubah baris header.',
        '',
        'CONTOH PENGISIAN:',
    ]
    for i, text in enumerate(rules, start=1):
        guide.cell(row=i, column=1, value=text).font = Font(bold=(i == 1), size=11)

    contoh = [
        headers,
        [1, 'Mech', 'Water Injection Pump', 'PB.001/PO/NK-WIKA/03/SINTONG/12/2025',
         'PT Sulzer Indonesia', 'Material', 20100000000, datetime(2025, 12, 24),
         datetime(2027, 1, 27), 'PPN Exclude', 0.11, 20100000000, 2211000000,
         'PPN Reimburse', 'Uang Muka', None, 0.10, 0.10, 2010000000, 221100000,
         60, 2231100000, None, datetime(2026, 1, 16), 'Lunas DPP, Lunas PPN'],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '', 'FAT', None,
         0.30, 0.27, 5427000000, 596970000, 60, 6023970000, None, None, ''],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '',
         'Material on Site/BASTB', datetime(2026, 10, 14), 0.60, 0.54,
         10854000000, 1193940000, 60, 12047940000, None, None, ''],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '', 'Commissioning',
         datetime(2027, 1, 27), 0.10, 0.09, 1809000000, 198990000, 60,
         2007990000, None, None, ''],
        [5, 'Inst', 'MPS', 'PB.005/PO/NK-WIKA/02/SINTONG/03/2026',
         'PT CONTROL SYSTEM ARENA PARA NUSA', 'Material', 1915000000,
         datetime(2026, 3, 10), datetime(2027, 5, 23), 'PPN Exclude', 0.11,
         1915000000, 210650000, 'PPN Include', 'Approval Doc', None, 0.20, 0.20,
         383000000, 42130000, 90, 425130000, None, datetime(2026, 9, 11),
         'Tertagih'],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '', 'FAT', None,
         0.20, 0.20, 383000000, 42130000, 90, 425130000, None, None, ''],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '',
         'Material on Site/BASTB', datetime(2026, 6, 16), 0.55, 0.55,
         1053250000, 115857500, 90, 1169107500, None, None, ''],
        ['', '', '', '', '', '', '', '', '', '', '', '', '', '', 'Commissioning',
         datetime(2027, 6, 30), 0.05, 0.05, 95750000, 10532500, 90, 106282500,
         None, None, ''],
    ]
    start = len(rules) + 1
    for r, row in enumerate(contoh, start=start):
        for c, val in enumerate(row, start=1):
            cell = guide.cell(row=r, column=c, value=(None if val == '' else val))
            cell.border = thin
            if r == start:
                cell.font = Font(color='FFFFFF', bold=True, size=10)
                cell.fill = fill
                cell.alignment = Alignment(wrap_text=True, vertical='center')
            if c in (7, 12, 13, 19, 20, 22, 23) and isinstance(val, (int, float)):
                cell.number_format = '#,##0'
            if c in (11, 17, 18) and isinstance(val, (int, float)):
                cell.number_format = '0.00%'
            if c in (8, 9, 16, 24) and isinstance(val, datetime):
                cell.number_format = 'yyyy-mm-dd'
    for col, w in zip('ABCDEFGHIJKLMNOPQRSTUVWXY', widths):
        guide.column_dimensions[col].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, as_attachment=True, download_name='template_kontrak_vendor.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@bp.route('/import', methods=['POST'])
def import_excel():
    if 'file' not in request.files:
        flash('Pilih file Excel terlebih dahulu!', 'danger')
        return redirect(url_for('contract.import_page'))

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('File harus .xlsx atau .xls!', 'danger')
        return redirect(url_for('contract.import_page'))

    # ── Project binding (required, sama seperti Import Invoice) ──
    project_id_raw = request.form.get('project_id', '').strip()
    if not project_id_raw:
        flash('Pilih Proyek terlebih dahulu! Import Kontrak kini terikat ke satu proyek.', 'danger')
        return redirect(url_for('contract.import_page'))
    try:
        project_id = int(project_id_raw)
    except (ValueError, TypeError):
        flash('ID Proyek tidak valid.', 'danger')
        return redirect(url_for('contract.import_page'))

    import db_project
    project = db_project.get_project(project_id)
    if not project:
        flash('Proyek tidak ditemukan.', 'danger')
        return redirect(url_for('contract.import_page'))
    pid_str = str(project_id)

    import openpyxl
    try:
        wb = openpyxl.load_workbook(file, data_only=True)
    except Exception as e:
        flash(f'Gagal membuka file: {e}', 'danger')
        return redirect(url_for('contract.import_page'))

    sheet_name = request.form.get('sheet_name', '')
    if sheet_name and sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb[contract_excel.detect_contract_sheet(wb)]

    result = contract_excel.parse_contract_sheet(ws, project_id=pid_str)
    wb.close()


    if result is None:
        flash('Header tidak dikenali. Pastikan sheet punya kolom '
              '"No. Kontrak" dan "Vendor" (nama kolom bebas, boleh '
              '"No SPK", "Rekanan", dll).', 'danger')
        return redirect(url_for('contract.import_page'))

    rows, imported, skipped = result
    if not rows:
        flash('Tidak ada baris kontrak yang ditemukan.', 'warning')
        return redirect(url_for('contract.import_page'))

    # Seluruh penyimpanan (kontrak + termin) dalam SATU transaksi atomik:
    # bila ada baris yang gagal, tidak ada kontrak yang "setengah tersimpan".
    try:
        stat = db_contract.import_contracts(rows)
    except Exception as e:
        flash(f'Gagal menyimpan import (perubahan dibatalkan): {e}', 'danger')
        return redirect(url_for('contract.import_page'))
    from constants import save_last_import as _stamp
    try:
        _stamp('kontrak', pid_str)
    except Exception:
        pass

    inserted = stat['inserted']
    updated = stat['updated']
    total_termin = stat['total_termin']
    warn = stat['warnings']
    vendor_kosong = stat.get('vendor_kosong', 0)

    flash(f'Import selesai: {len(rows)} kontrak ({inserted} baru, {updated} diperbarui) '
          f'dari {imported} baris Excel. Baris dilewati: {skipped}. '
          f'Jadwal termin tersimpan: {total_termin}.', 'success')
    if vendor_kosong:
        flash(f'{vendor_kosong} kontrak tanpa Nama Vendor di Excel — import tetap '
              f'disimpan, silakan lengkapi nama vendor di halaman Detail Kontrak.',
              'warning')
    warn_selisih = [w for w in warn if 'Vendor kosong' not in w]
    if warn_selisih:
        contoh = '; '.join(warn_selisih[:5])
        lagi = len(warn_selisih) - 5
        flash(f'Periksa {len(warn_selisih)} kontrak — total Nilai DPP Termin di Excel '
              f'tidak sama dengan Nilai (DPP) Kontrak: {contoh}'
              + (f' — dan {lagi} lainnya.' if lagi > 0 else '.'), 'warning')
    di_luar = stat.get('di_luar_excel') or []
    if di_luar:
        contoh = '; '.join(di_luar[:5])
        lagi = len(di_luar) - 5
        flash(f'{len(di_luar)} kontrak ada di aplikasi tapi TIDAK ada di file Excel '
              f'(kandidat data lama/duplikat) — periksa & hapus bila perlu: {contoh}'
              + (f' — dan {lagi} lainnya.' if lagi > 0 else '.'), 'warning')
    return redirect(url_for('contract.list_contracts'))


# ── NOMOR KONTRAK DI INVOICE TANPA REGISTRI ──────────────────────────

@bp.route('/belum-terdaftar')
def unmatched():
    pid = _active_project_id()
    missing = db_contract.get_unmatched_contract_nos(pid)
    return render_template('contract_unmatched.html', missing=missing,
                           ignored_vendors=db_ignore.get_ignored_vendors())


@bp.route('/belum-terdaftar/abaikan-vendor', methods=['POST'])
def ignore_vendor():
    vendor = request.form.get('vendor', '').strip()
    if vendor:
        db_ignore.ignore_vendor(vendor, request.form.get('alasan', '').strip())
        flash(f'Vendor "{vendor}" diabaikan dari daftar belum terdaftar.', 'success')
    return redirect(url_for('contract.unmatched'))


@bp.route('/belum-terdaftar/kembalikan-vendor', methods=['POST'])
def unignore_vendor():
    vendor = request.form.get('vendor', '')
    if vendor:
        db_ignore.unignore_vendor(vendor)
        flash(f'Vendor "{vendor}" tidak lagi diabaikan.', 'success')
    return redirect(url_for('contract.unmatched'))
