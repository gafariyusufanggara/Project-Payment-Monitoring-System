"""
SQLite database layer for projects.
All tables are stored in the existing monitoring_hutang.db file.

Retensi tidak disimpan manual: nilainya diturunkan otomatis dari kolom
POT. RETENSI pada tabel hutang (lihat get_retensi_rows).
"""
import os
import sqlite3
from datetime import datetime

from constants import safe_float, effective_invoice, status_retensi, is_excluded_values, is_excluded_row

DB_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(DB_DIR, 'monitoring_hutang.db')


def _conn():
    return sqlite3.connect(DB_FILE)


def _dict_factory(cursor, row):
    d = {}
    for i, col in enumerate(cursor.description):
        d[col[0]] = row[i]
    return d


# ---------------------------------------------------------------------------
# INIT
# ---------------------------------------------------------------------------

def init_project_tables():
    """Create projects table if missing."""
    with _conn() as conn:
        # Fitur yang dihapus: tabelnya dibuang bila masih ada.
        # - project_budget      (anggaran/RAB)
        # - project_retention   (input retensi manual; kini otomatis dari POT. RETENSI)
        conn.execute('DROP TABLE IF EXISTS project_budget')
        conn.execute('DROP TABLE IF EXISTS project_retention')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_proyek   TEXT UNIQUE NOT NULL,
                nama_proyek   TEXT NOT NULL,
                lokasi        TEXT DEFAULT '',
                pemilik       TEXT DEFAULT '',
                nilai_kontrak REAL DEFAULT 0,
                tgl_mulai     TEXT DEFAULT '',
                tgl_selesai   TEXT DEFAULT '',
                status        TEXT DEFAULT 'Aktif',
                catatan       TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.commit()


# ---------------------------------------------------------------------------
# PROJECTS CRUD
# ---------------------------------------------------------------------------

def get_projects():
    """Return list of all projects with derived stats."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        rows = conn.execute('SELECT * FROM projects ORDER BY kode_proyek').fetchall()
    # Attach derived stats from hutang. Both use the same scope as the
    # DPP/PPN laporan & main dashboard (rows with TGL TERIMA, minus excluded),
    # so the portfolio totals match the reports.
    for p in rows:
        pid = p['id']
        # total realisasi = sum HARGA(EXLD) of countable invoices (deduped)
        p['total_realisasi'] = _sum_realisasi(pid)
        # sisa hutang = per-vendor max(0, DPP - bayar DPP)
        p['total_sisa'] = _sum_sisa(pid)
    return rows


def get_project(project_id):
    """Return a single project dict (or None) with derived stats."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        p = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
    if not p:
        return None
    p['total_realisasi'] = _sum_realisasi(project_id)
    p['total_sisa'] = _sum_sisa(project_id)
    return p


def create_project(kode, nama, lokasi='', pemilik='', nilai_kontrak=0,
                   tgl_mulai='', tgl_selesai='', status='Aktif', catatan=''):
    with _conn() as conn:
        conn.execute('''
            INSERT INTO projects (kode_proyek, nama_proyek, lokasi, pemilik,
                                  nilai_kontrak, tgl_mulai, tgl_selesai, status, catatan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (kode, nama, lokasi, pemilik, nilai_kontrak, tgl_mulai, tgl_selesai, status, catatan))
        conn.commit()
        return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def update_project(project_id, kode, nama, lokasi, pemilik, nilai_kontrak,
                   tgl_mulai, tgl_selesai, status, catatan):
    with _conn() as conn:
        conn.execute('''
            UPDATE projects SET kode_proyek=?, nama_proyek=?, lokasi=?, pemilik=?,
                                nilai_kontrak=?, tgl_mulai=?, tgl_selesai=?,
                                status=?, catatan=?
            WHERE id=?
        ''', (kode, nama, lokasi, pemilik, nilai_kontrak, tgl_mulai, tgl_selesai,
              status, catatan, project_id))
        conn.commit()


def delete_project(project_id):
    """Delete a project and clear its link on hutang rows."""
    with _conn() as conn:
        conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        # clear project_id from hutang table
        conn.execute('UPDATE hutang SET project_id = ? WHERE project_id = ?',
                     ('', str(project_id)))
        conn.commit()


def get_project_select():
    """Return list of (id, label) for dropdowns. label = 'kode — nama'."""
    with _conn() as conn:
        rows = conn.execute('SELECT id, kode_proyek, nama_proyek FROM projects ORDER BY kode_proyek').fetchall()
    return [(r[0], f'{r[1]} — {r[2]}' if r[2] else r[1]) for r in rows]


def project_exists(project_id):
    """Lightweight existence check — single-row lookup, no aggregates."""
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        return False
    with _conn() as conn:
        row = conn.execute('SELECT 1 FROM projects WHERE id = ?', (pid,)).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# RETENSI OTOMATIS (turunan dari kolom POT. RETENSI di tabel hutang)
# ---------------------------------------------------------------------------

def get_retensi_rows(project_id=None):
    """Return retention lines derived automatically from hutang.

    Tidak ada input manual: setiap baris hutang dengan POT. RETENSI > 0
    menjadi satu baris retensi, dikelompokkan per rekanan.

    Sama seperti halaman Levelansir/Retensi (db.get_levelansir_retensi):
    retensi adalah uang yang ditahan (bukan utang aktif), sehingga TIDAK
    disyaratkan TGL TERIMA. Aturan Exclude Invoice tetap berlaku: baris
    ter-exclude tidak dihitung, agar KPI retensi konsisten di semua halaman.

    Returns list of dicts: {nama, total_retensi, total_cair, total_sisa_retensi,
                            jumlah_invoice, status_retensi, invoices: [...]}
    Each invoice entry: {_row, no_invoice, tgl_terima, nilai_retensi,
                         harga_exld, bayar_dpp, status_retensi, sisa_retensi,
                         retensi_cair, kode_biaya, deskripsi, kategori}
    """
    where = ''
    params = ()
    if project_id is not None and str(project_id) not in ('all', ''):
        where = 'AND "project_id" = ?'
        params = (str(project_id),)
    with _conn() as conn:
        conn.row_factory = _dict_factory
        rows = conn.execute(f'''
            SELECT _row,
                   "NAMA LEVELANSIR / REKANAN" AS nama,
                   "NO INVOICE"                AS no_invoice,
                   "TGL TERIMA"                AS tgl_terima,
                   "POT. RETENSI"              AS retensi,
                   "HARGA (EXLD)"              AS harga_exld,
                   "PEMBAYARAN DPP"            AS bayar_dpp,
                   "KODE BIAYA2"               AS kode_biaya,
                   "DESKRIPSI"                 AS deskripsi,
                   "KATEGORI"                  AS kategori
            FROM hutang
            WHERE CAST(COALESCE("POT. RETENSI", '0') AS REAL) > 0
              AND "NAMA LEVELANSIR / REKANAN" IS NOT NULL
              AND TRIM("NAMA LEVELANSIR / REKANAN") <> ''
              {where}
            ORDER BY "NAMA LEVELANSIR / REKANAN", _row
        ''', params).fetchall()

    rows = [r for r in rows if not is_excluded_values(r['kategori'], r['nama'])]

    grouped = {}
    for r in rows:
        key = (r['nama'] or '').strip()
        if key not in grouped:
            grouped[key] = {
                'nama': key,
                'total_retensi': 0.0,
                'total_harga': 0.0,
                'total_bayar_dpp': 0.0,
                'total_cair': 0.0,
                'total_sisa_retensi': 0.0,
                'jumlah_invoice': 0,
                'invoices': [],
            }
        ret = float(r['retensi'] or 0)
        harga_exld = float(r['harga_exld'] or 0)
        bayar_dpp = float(r['bayar_dpp'] or 0)
        st_ret, sisa_ret, cair = status_retensi(harga_exld, ret, bayar_dpp)
        grouped[key]['total_retensi'] += ret
        grouped[key]['total_harga'] += harga_exld
        grouped[key]['total_bayar_dpp'] += bayar_dpp
        grouped[key]['total_cair'] += cair
        grouped[key]['total_sisa_retensi'] += sisa_ret
        grouped[key]['jumlah_invoice'] += 1
        grouped[key]['invoices'].append({
            '_row': r['_row'],
            'no_invoice': r['no_invoice'] or '',
            'tgl_terima': r['tgl_terima'] or '',
            'nilai_retensi': ret,
            'harga_exld': harga_exld,
            'bayar_dpp': bayar_dpp,
            'status_retensi': st_ret,
            'sisa_retensi': sisa_ret,
            'retensi_cair': cair,
            'kode_biaya': r['kode_biaya'] or '',
            'deskripsi': r['deskripsi'] or '',
            'kategori': r['kategori'] or '',
        })

    for g in grouped.values():
        statuses = [i['status_retensi'] for i in g['invoices']]
        g['status_retensi'] = (
            'Lunas' if g['total_sisa_retensi'] <= 1.0
            else 'Cair Sebagian' if g['total_cair'] > 1.0
            else 'Ditahan' if statuses and all(s == 'Ditahan' for s in statuses)
            else 'Belum Dibayar'
        )

    return sorted(grouped.values(), key=lambda x: (-x['total_retensi'], x['nama']))


# ---------------------------------------------------------------------------
# AGGREGATION HELPERS (used by project dashboard)
# ---------------------------------------------------------------------------

def _dedup_hutang_rows(rows):
    seen = set()
    out = []
    for r in rows:
        inv = effective_invoice(r)
        rekan = (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()
        key = (rekan, inv) if inv else None
        rr = dict(r)
        if key and key in seen:
            rr['HARGA (EXLD)'] = '0'
            rr['TOTAL (INCLD)'] = '0'
            rr['PPN'] = '0'
            rr['POT. RETENSI'] = '0'
            rr['POT. PPH'] = '0'
        else:
            if key:
                seen.add(key)
        out.append(rr)
    return out


def _project_rows(project_id):
    """Rows in scope for a project's aggregates.

    Same scope as the DPP/PPN laporan & main dashboard:
      * must have TGL TERIMA (tanggal berkas lengkap) — an invoice whose berkas
        is not complete yet is not a countable debt;
      * must NOT be excluded by the Exclude Invoice exclusion rules.
    Without these the project page totals disagreed with the reports.
    """
    import db as _db
    from constants import is_excluded_row
    rows = _db.read_data(project_id)
    return [r for r in rows
            if (r.get('TGL TERIMA') or '').strip() and not is_excluded_row(r)]


def _sum_realisasi(project_id):
    rows = _dedup_hutang_rows(_project_rows(project_id))
    return sum(safe_float(r.get('HARGA (EXLD)')) for r in rows)


def _sisa_per_vendor(rows, kolom_nilai, kolom_bayar):
    """Sisa hutang = Σ per-vendor max(0, Σ nilai − Σ bayar).

    Satu-satunya tempat klip per-vendor didefinisikan, dipakai bersama oleh
    Sisa DPP & Sisa PPN. Klip dilakukan PER VENDOR (bukan per invoice, bukan
    pada total) supaya kelebihan bayar satu vendor tidak menutupi utang vendor
    lain — sama seperti Laporan DPP/PPN dan dashboard utama
    (services/dashboard.py).
    """
    per_vendor = {}
    for r in rows:
        rek = (r.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip() or 'Unknown'
        per_vendor[rek] = (per_vendor.get(rek, 0.0)
                           + safe_float(r.get(kolom_nilai))
                           - safe_float(r.get(kolom_bayar)))
    return sum(max(0.0, v) for v in per_vendor.values())


def _sum_sisa(project_id):
    """Sisa hutang DPP = per-vendor max(0, sum HARGA(EXLD) - sum PEMBAYARAN DPP).

    Same per-vendor clip as the Laporan DPP (sisa_dpp) and the main dashboard
    (total_sisa_dpp): overpayment by one vendor must not hide unpaid debt by
    another, so the clip happens per vendor — not per invoice and not on the
    grand total.
    """
    rows = _dedup_hutang_rows(_project_rows(project_id))
    return _sisa_per_vendor(rows, 'HARGA (EXLD)', 'PEMBAYARAN DPP')


def get_project_finansial(project_id):
    """Ringkasan keuangan satu proyek, sebanding dgn dashboard utama.

    Memakai scope yang sama dengan laporan (TGL TERIMA wajib, baris ter-exclude
    dibuang, invoice di-dedup) dan metodologi persen yang sama dengan
    services/dashboard.py, sehingga:
      * total_dpp  == project['total_realisasi']  (angka di daftar proyek)
      * sisa_dpp   == project['total_sisa']       (angka di daftar proyek)
    Dijaga oleh smoke_project_dashboard_check.py agar tidak melenceng.

    Catatan PPN: total_ppn diambil dari kolom 'PPN' per baris — BUKAN 11% x DPP
    — supaya konsisten dengan dashboard utama & Laporan PPN.
    """
    rows = _dedup_hutang_rows(_project_rows(project_id))

    total_dpp = sum(safe_float(r.get('HARGA (EXLD)')) for r in rows)
    bayar_dpp = sum(safe_float(r.get('PEMBAYARAN DPP')) for r in rows)
    sisa_dpp = _sisa_per_vendor(rows, 'HARGA (EXLD)', 'PEMBAYARAN DPP')

    total_ppn = sum(safe_float(r.get('PPN')) for r in rows)
    bayar_ppn = sum(safe_float(r.get('PEMBAYARAN PPN')) for r in rows)
    sisa_ppn = _sisa_per_vendor(rows, 'PPN', 'PEMBAYARAN PPN')

    # Retensi & PPh adalah uang yang DITAHAN/DISETOR (pengurang tagihan), bukan
    # utang ke vendor — dihitung dari baris proyek yg sama, dgn aturan yang
    # sama seperti get_retensi_rows (tanpa syarat TGL TERIMA, tetap
    # mengecualikan baris Exclude Invoice) agar angka retensi proyek cocok
    # dgn halaman Levelansir/Retensi.
    import db as _db
    retensi_rows = [r for r in _db.read_data(project_id) if not is_excluded_row(r)]
    total_retensi = sum(safe_float(r.get('POT. RETENSI')) for r in retensi_rows)
    total_pph = sum(safe_float(r.get('POT. PPH')) for r in rows)
    total_pph_paid = sum(safe_float(r.get('PEMBAYARAN POT. PPH')) for r in rows)
    total_tagihan = sum(safe_float(r.get('TOTAL (INCLD)')) for r in rows)

    vendor = {(r.get('NAMA LEVELANSIR / REKANAN') or 'Unknown').strip() or 'Unknown'
              for r in rows}
    lunas = sum(1 for r in rows if r.get('STATUS TERHADAP DPP') == 'Lunas')

    # Persen: basis sama dgn dashboard utama (nilai total, bukan sisanya).
    dpp_pct = round(bayar_dpp / total_dpp * 100) if total_dpp else 0
    ppn_pct = round(bayar_ppn / total_ppn * 100) if total_ppn else 0
    sisa_dpp_pct = round(sisa_dpp / total_dpp * 100) if total_dpp else 0
    sisa_ppn_pct = round(sisa_ppn / total_ppn * 100) if total_ppn else 0

    return {
        'total_dpp': float(total_dpp),
        'bayar_dpp': float(bayar_dpp),
        'sisa_dpp': float(sisa_dpp),
        'total_ppn': float(total_ppn),
        'bayar_ppn': float(bayar_ppn),
        'sisa_ppn': float(sisa_ppn),
        'sisa_hutang': float(sisa_dpp + sisa_ppn),
        'total_tagihan': float(total_tagihan),
        'total_pph': float(total_pph),
        'total_pph_paid': float(total_pph_paid),
        'total_retensi': float(total_retensi),
        'jumlah_invoice': len(rows),
        'jumlah_vendor': len(vendor),
        'lunas_count': lunas,
        'belum_count': len(rows) - lunas,
        'dpp_pct': dpp_pct,
        'ppn_pct': ppn_pct,
        'sisa_dpp_pct': sisa_dpp_pct,
        'sisa_ppn_pct': sisa_ppn_pct,
    }


def get_realisasi_by_month(project_id):
    rows = _project_rows(project_id)
    deduped = _dedup_hutang_rows(rows)
    amap = {}
    for r in deduped:
        harga = safe_float(r.get('HARGA (EXLD)'))
        if harga == 0:
            continue
        bulan = (r.get('TGL TERIMA') or '')[:7]
        if len(bulan) != 7:
            continue
        amap[bulan] = amap.get(bulan, 0) + harga
    bmap = {}
    for r in rows:
        bayar = safe_float(r.get('PEMBAYARAN DPP'))
        if bayar == 0:
            continue
        bulan = (r.get('TGL BAYAR DPP') or '')[:7]
        if len(bulan) != 7:
            continue
        bmap[bulan] = bmap.get(bulan, 0) + bayar
    months = sorted(set(amap) | set(bmap))
    result = []
    for m in months:
        a = amap.get(m, 0)
        b = bmap.get(m, 0)
        result.append({'bulan': m, 'amount': a, 'bayar': b, 'sisa': a - b})
    return result


def get_pph_summary(project_id):
    rows = _dedup_hutang_rows(_project_rows(project_id))
    total_pph = sum(safe_float(r.get('POT. PPH')) for r in rows)
    total_dpp = sum(safe_float(r.get('HARGA (EXLD)')) for r in rows)
    return {'total_pph': float(total_pph), 'total_dpp': float(total_dpp)}
