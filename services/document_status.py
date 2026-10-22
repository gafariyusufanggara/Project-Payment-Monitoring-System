"""
MODEL - Status Dokumen (revisi dokumen).

Pure computation over db.read_data(); no Flask, no rendering.

Definisi "revisi dokumen" (sesuai spec pengguna):
  Sebuah baris masih berstatus REVISI DOKUMEN bila TANGGAL BERKAS LENGKAP
  belum diisi. Field ini adalah 'TGL TERIMA' — sama persis dengan penanda
  "Kelengkapan" pada halaman Verifikasi Data (lihat
  services/verification.py: _COL_TGL_BERKAS_LENGKAP = 'TGL TERIMA').

  Dengan kata lain: TGL TERIMA kosong => dokumen belum lengkap => revisi.

Baris yang diabaikan di Verifikasi (db_ignore) juga tidak muncul di sini,
supaya konsisten dengan halaman Verifikasi dan seluruh badge di aplikasi.

Nominal penting (DPP / PPN / PPh / Retensi / Total) ikut dihitung per baris
dan sebagai akumulasi, agar pengguna tahu berapa nilai dokumen yang masih
dalam proses revisi.
"""
from constants import safe_float, is_excluded_row

import db


# Field keys (samakan dengan kolom di db.read_data)
_COL_TGL_TERIMA     = 'TGL TERIMA'          # = TANGGAL BERKAS LENGKAP (acuan revisi)
_COL_TGL_BERKAS     = 'TGL TERIMA BERKAS'   # tanggal fisik berkas diterima (info)
_COL_REKANAN        = 'NAMA LEVELANSIR / REKANAN'
_COL_INVOICE        = 'NO INVOICE'
_COL_INVOICE_INT    = 'NO INVOICE INTERNAL'
_COL_PO             = 'NO PO / KONTRAK'
_COL_TGL_INV        = 'TGL INV'
_COL_DESKRIPSI      = 'DESKRIPSI'
_COL_STATUS_DPP     = 'STATUS TERHADAP DPP'
_COL_STATUS_PPN     = 'STATUS TERHADAP PPN'
_COL_DPP            = 'HARGA (EXLD)'        # Nilai DPP (harga sebelum PPN)
_COL_PPN            = 'PPN'                 # Nilai PPN
_COL_PPH            = 'POT. PPH'            # Potongan PPh
_COL_RETENSI        = 'POT. RETENSI'        # Retensi
_COL_TOTAL          = 'TOTAL (INCLD)'       # Total termasuk PPN


def _is_blank(val):
    """True if value is None or empty/whitespace string."""
    if val is None:
        return True
    return str(val).strip() == ''


def _num(val):
    """Parse nominal to float (0 on failure)."""
    return safe_float(val, 0)


def _get_document_status(data, project_id=None):
    """Core: ekstrak baris revisi + nominal dari data yang sudah dibaca."""
    rows = []
    nominal = {
        'dpp': 0.0,
        'ppn': 0.0,
        'pph': 0.0,
        'retensi': 0.0,
        'total': 0.0,
    }
    rekanan_set = set()

    for row in data:
        # Acuan revisi: TGL TERIMA (Tanggal Berkas Lengkap) masih kosong.
        if not _is_blank(row.get(_COL_TGL_TERIMA)):
            continue

        dpp = _num(row.get(_COL_DPP))
        ppn = _num(row.get(_COL_PPN))
        pph = _num(row.get(_COL_PPH))
        retensi = _num(row.get(_COL_RETENSI))
        total = _num(row.get(_COL_TOTAL))

        nominal['dpp'] += dpp
        nominal['ppn'] += ppn
        nominal['pph'] += pph
        nominal['retensi'] += retensi
        nominal['total'] += total

        rekanan = (row.get(_COL_REKANAN) or '').strip()
        if rekanan:
            rekanan_set.add(rekanan)

        rows.append({
            'row_idx': row.get('_row'),
            'r': row.get('R', ''),
            'rekanan': rekanan,
            'no_invoice': (row.get(_COL_INVOICE) or '').strip(),
            'no_invoice_internal': (row.get(_COL_INVOICE_INT) or '').strip(),
            'no_po': (row.get(_COL_PO) or '').strip(),
            'tgl_invoice': (row.get(_COL_TGL_INV) or '').strip(),
            'tgl_berkas': (row.get(_COL_TGL_BERKAS) or '').strip(),
            'deskripsi': (row.get(_COL_DESKRIPSI) or '').strip(),
            'status_dpp': (row.get(_COL_STATUS_DPP) or '').strip(),
            'status_ppn': (row.get(_COL_STATUS_PPN) or '').strip(),
            'dpp': dpp,
            'ppn': ppn,
            'pph': pph,
            'retensi': retensi,
            'total': total,
            'project_id': row.get('project_id'),
        })

    # Urutkan: rekanan (A-Z) lalu nomor R numerik naik — stabil & mudah dibaca.
    def _sort_key(r):
        try:
            ridx = int(r['row_idx'])
        except (ValueError, TypeError):
            ridx = 0
        return ((r['rekanan'] or '~').lower(), ridx)

    rows.sort(key=_sort_key)

    summary = {
        'revisi_count': len(rows),
        'rekanan_count': len(rekanan_set),
        **nominal,
    }
    return rows, summary


def get_document_status(project_id=None, data=None):
    """Return (rows, summary) for the Status Dokumen page.

    rows:    daftar dict baris yang masih revisi dokumen (TGL TERIMA kosong),
             lengkap dengan nominal DPP/PPN/PPh/Retensi/Total per baris.
    summary: { revisi_count, rekanan_count, dpp, ppn, pph, retensi, total }

    project_id: bila diberikan, batasi ke satu proyek. None = semua proyek.
    data:       baris db.read_data() yang sudah dibaca (opsional, hindari
                pembacaan ganda). project_id diabaikan bila data diberikan.

    Baris yang diabaikan di Verifikasi (db_ignore) dikecualikan agar konsisten.
    """
    data = db.read_data(project_id=project_id) if data is None else data
    if not data:
        return [], {
            'revisi_count': 0, 'rekanan_count': 0,
            'dpp': 0.0, 'ppn': 0.0, 'pph': 0.0, 'retensi': 0.0, 'total': 0.0,
        }

    ignored = _get_ignored_set(project_id)
    if ignored:
        data = [row for row in data if row.get('_row') not in ignored]

    # Exclude Invoice: baris ter-exclude tidak ikut perhitungan nominal.
    data = [row for row in data if not is_excluded_row(row)]

    return _get_document_status(data, project_id=project_id)


def count_document_revisi(project_id=None):
    """Jumlah baris yang masih revisi dokumen — untuk badge sidebar.

    Ringan: satu db.read_data() + filter, tanpa menghitung duplikat/rekanan.
    """
    try:
        data = db.read_data(project_id=project_id)
    except Exception:
        return 0
    if not data:
        return 0
    ignored = _get_ignored_set(project_id)
    n = 0
    for row in data:
        if row.get('_row') in ignored:
            continue
        if is_excluded_row(row):
            continue
        if _is_blank(row.get(_COL_TGL_TERIMA)):
            n += 1
    return n


def _get_ignored_set(project_id=None):
    """Return set of _row values ignored for this scope (empty set on failure)."""
    try:
        from db_ignore import get_ignored_set
        return get_ignored_set(project_id)
    except Exception:
        return set()
