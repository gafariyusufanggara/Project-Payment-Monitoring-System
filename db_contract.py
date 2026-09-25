"""
SQLite database layer for vendor contracts (procurement).

Satu baris = satu kontrak vendor. Pencocokan ke invoice dilakukan lewat
kolom "NO PO / KONTRAK" pada tabel hutang (exact match, case-insensitive
setelah di-trim) — tidak ada tabel penghubung tambahan.

Jadwal termin disimpan di tabel vendor_contract_termin (1 baris Excel = 1
termin). Nilai Kontrak dari Excel DIPERTAHANKAN apa adanya; jumlah termin
hanya dipakai sebagai cadangan bila kolom Nilai Kontrak kosong. PPN Include
membuat Nilai Kontrak lebih besar dari jumlah Nilai DPP Termin, jadi keduanya
memang boleh berbeda. Lihat services/contract_excel.py.

Tabel disimpan di DB yang sama dengan hutang (monitoring_hutang.db).
"""
import os
import sqlite3
from datetime import date

from constants import safe_float, effective_invoice

DB_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(DB_DIR, 'monitoring_hutang.db')


def _conn():
    return sqlite3.connect(DB_FILE)


def _dict_factory(cursor, row):
    d = {}
    for i, col in enumerate(cursor.description):
        d[col[0]] = row[i]
    return d


def _norm_kontrak(val):
    """Kunci pencocokan nomor kontrak: trim + upper."""
    return (str(val or '')).strip().upper()


# ---------------------------------------------------------------------------
# INIT
# ---------------------------------------------------------------------------

def init_contract_tables():
    """Create vendor_contracts + vendor_contract_termin if missing."""
    with _conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS vendor_contracts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                no_kontrak    TEXT UNIQUE NOT NULL,
                vendor        TEXT NOT NULL,
                project_id    TEXT DEFAULT '',
                nilai_kontrak REAL DEFAULT 0,
                tgl_kontrak   TEXT DEFAULT '',
                tgl_mulai     TEXT DEFAULT '',
                tgl_selesai   TEXT DEFAULT '',
                keterangan    TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_kontrak_no
            ON vendor_contracts (no_kontrak)
        ''')
        # Jadwal termin per kontrak (dokumentasi): 1 baris Excel = 1 termin.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS vendor_contract_termin (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                urutan      INTEGER DEFAULT 0,
                label       TEXT DEFAULT '',
                persen      REAL DEFAULT 0,
                nilai       REAL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_termin_contract
            ON vendor_contract_termin (contract_id)
        ''')
        # Migrasi ringan: kolom tambahan format procurement (idempotent).
        existing = {r[1] for r in conn.execute('PRAGMA table_info(vendor_contracts)')}
        for col, ddl in (('tipe_pekerjaan', "TEXT DEFAULT ''"),
                         ('item_pekerjaan', "TEXT DEFAULT ''"),
                         ('metode_pembayaran', "TEXT DEFAULT ''"),
                         ('durasi_termin', 'REAL DEFAULT 0'),
                         ('tipe_kontrak', "TEXT DEFAULT ''"),
                         ('metode_penetapan', "TEXT DEFAULT ''"),
                         ('ppn_rate', 'REAL DEFAULT 0'),
                         ('total_dpp', 'REAL DEFAULT 0'),
                         ('total_ppn', 'REAL DEFAULT 0')):
            if col not in existing:
                conn.execute(f'ALTER TABLE vendor_contracts ADD COLUMN {col} {ddl}')
        # PPN per termin: diambil dari kolom 'PPN per Termin' Excel bila ada;
        # bila 0, diturunkan saat tampil dari tarif DEFAULT_PPN_RATE.
        tcols = {r[1] for r in conn.execute('PRAGMA table_info(vendor_contract_termin)')}
        if 'ppn_nilai' not in tcols:
            conn.execute('ALTER TABLE vendor_contract_termin ADD COLUMN ppn_nilai REAL DEFAULT 0')
        if 'tgl_termin' not in tcols:
            conn.execute("ALTER TABLE vendor_contract_termin ADD COLUMN tgl_termin TEXT DEFAULT ''")
        conn.commit()


# ---------------------------------------------------------------------------
# INVOICE AGGREGATION (dari tabel hutang)
# ---------------------------------------------------------------------------

def _fetch_invoice_rows(project_id=None):
    """Ambil baris hutang untuk agregasi kontrak, dengan cache per-request.

    project_id: 'all'/None → semua proyek. Selain itu filter project_id.
    Hasil di-cache pada flask.g selama satu request: halaman daftar kontrak
    memanggil ini beberapa kali (get_contracts + get_summary), cukup query
    sekali. Di luar request context (script/test) cache dilewati.
    Mengembalikan list dict; [] bila tabel hutang belum ada.
    """
    cache_key = f'_ctr_inv_rows::{"" if project_id is None else project_id}'
    try:
        from flask import g, has_request_context
    except ImportError:
        g = has_request_context = None
    if has_request_context and has_request_context():
        cached = getattr(g, 'contract_invoice_cache', None)
        if cached is None:
            cached = {}
            g.contract_invoice_cache = cached
        if cache_key in cached:
            return cached[cache_key]
        rows = _query_invoice_rows(project_id)
        cached[cache_key] = rows
        return rows
    return _query_invoice_rows(project_id)


def _query_invoice_rows(project_id=None):
    """Query sebenarnya ke tabel hutang (tanpa cache)."""
    where = ''
    params = ()
    if project_id is not None and str(project_id) not in ('all', ''):
        where = 'WHERE "project_id" = ?'
        params = (str(project_id),)
    try:
        with _conn() as conn:
            conn.row_factory = _dict_factory
            return conn.execute(f'''
                SELECT _row,
                       "NO PO / KONTRAK"              AS no_kontrak,
                       "NAMA LEVELANSIR / REKANAN"    AS rekanan,
                       "NO INVOICE"                   AS no_invoice,
                       "NO INVOICE INTERNAL"          AS no_invoice_internal,
                       "HARGA (EXLD)"                 AS harga,
                       "PEMBAYARAN DPP"               AS bayar,
                       "PEMBAYARAN PPN"               AS bayar_ppn,
                       "TOTAL (INCLD)"                AS total,
                       "STATUS TERHADAP DPP"          AS status_dpp,
                       "JTH TEMPO"                    AS jth_tempo,
                       "VOLUME PROGRESS"              AS volume,
                       "TGL TERIMA"                   AS tgl_terima,
                       "TGL INV"                      AS tgl_inv,
                       "DESKRIPSI"                    AS deskripsi,
                       "KODE BIAYA2"                  AS kode_biaya,
                       "project_id"                   AS project_id
                FROM hutang
                {where}
                ORDER BY _row
            ''', params).fetchall()
    except sqlite3.Error:
        # Tabel hutang belum dibuat (init_db belum jalan) — kontrak tetap tampil.
        return []


def _invoice_identity(r):
    """Identitas invoice untuk dedup, dari hasil alias _fetch_invoice_rows.

    Tidak bisa memakai constants.effective_invoice() mentah: fungsi itu
    membaca nama kolom asli ('NO INVOICE' / 'NO INVOICE INTERNAL'), sedangkan
    _fetch_invoice_rows meng-alias keduanya. Logikanya tetap sama persis:
    NO INVOICE INTERNAL kalau ada, selain itu NO INVOICE.
    """
    inv_int = (r.get('no_invoice_internal') or '').strip()
    if inv_int:
        return inv_int
    return (r.get('no_invoice') or '').strip()

def _dedup_key(r):
    """Kunci dedup invoice yang SERAGAM untuk agregasi & daftar invoice.

    Identitas = (rekanan uppercase, no invoice efektif). Bila invoice kosong,
    fallback ke _row baris agar baris tanpa nomor tetap dihitung sekali.
    Dipakai _aggregate, get_contract_invoices, dan _linked_invoice_counts
    supaya ketiganya tidak menyimpang satu sama lain.
    """
    rekan = (r.get('rekanan') or '').strip().upper()
    inv = _norm_kontrak(_invoice_identity(r))
    if inv:
        return (rekan, inv)
    return (rekan, f'__row_{r.get("_row")}')


def _aggregate(invoice_rows):
    """Kelompokkan baris hutang per nomor kontrak.

    Return: {norm_no_kontrak: {tertagih, dibayar, sisa_hutang, jumlah_invoice}}
    Dedup identik dengan db_project._dedup_hutang_rows: nilai HARGA (EXLD)
    dihitung sekali per (rekanan, invoice efektif), sedangkan PEMBAYARAN DPP
    dijumlahkan dari semua baris (cicilan dibayar per baris).
    """
    agg = {}
    seen = {}
    for r in invoice_rows:
        key = _norm_kontrak(r.get('no_kontrak'))
        if not key:
            continue
        slot = agg.setdefault(key, {'tertagih': 0.0, 'tertagih_ppn': 0.0,
                                    'dibayar': 0.0, 'dibayar_ppn': 0.0,
                                    'sisa_hutang': 0.0, 'jumlah_invoice': 0})
        seen.setdefault(key, set())
        dedup_key = _dedup_key(r)
        if dedup_key in seen[key]:
            pass  # baris duplikat — nilai tidak dihitung lagi
        else:
            seen[key].add(dedup_key)
            slot['tertagih'] += safe_float(r.get('harga'))
            # PPN tertagih = TOTAL (INCLD) - HARGA (EXLD); duplikat sudah
            # di-nol-kan di _fetch_invoice_rows sehingga selisihnya 0.
            slot['tertagih_ppn'] += (safe_float(r.get('total'))
                                     - safe_float(r.get('harga')))
            slot['jumlah_invoice'] += 1
        slot['dibayar'] += safe_float(r.get('bayar'))
        slot['dibayar_ppn'] += safe_float(r.get('bayar_ppn'))
    for slot in agg.values():
        slot['sisa_hutang'] = max(0.0, slot['tertagih'] - slot['dibayar'])
    return agg


# ---------------------------------------------------------------------------
# CONTRACTS CRUD
# ---------------------------------------------------------------------------

def get_contracts(project_id=None):
    """Return all contracts with derived progress (tertagih, sisa, status)."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        rows = conn.execute('SELECT * FROM vendor_contracts ORDER BY no_kontrak').fetchall()

    agg = _aggregate(_fetch_invoice_rows(project_id))
    out = []
    for c in rows:
        key = _norm_kontrak(c.get('no_kontrak'))
        a = agg.get(key, {'tertagih': 0.0, 'tertagih_ppn': 0.0,
                          'dibayar': 0.0, 'dibayar_ppn': 0.0,
                          'sisa_hutang': 0.0, 'jumlah_invoice': 0})
        nilai = safe_float(c.get('nilai_kontrak'))
        # Basis DPP: Total DPP dari Excel; fallback nilai_kontrak bila kosong
        # (Nilai Kontrak kadang sudah termasuk PPN, kadang tidak).
        dpp = safe_float(c.get('total_dpp')) or nilai
        c['nilai_dpp'] = dpp
        # Aturan fallback sama dengan get_summary agar jumlah kolom = KPI.
        c['nilai_ppn'] = (safe_float(c.get('total_ppn'))
                          or dpp * safe_float(c.get('ppn_rate')) / 100.0)
        c['sisa_ppn'] = c['nilai_ppn'] - a['tertagih_ppn']
        tertagih = a['tertagih']
        c['tertagih'] = tertagih
        c['tertagih_ppn'] = a['tertagih_ppn']
        c['dibayar'] = a['dibayar']
        c['dibayar_ppn'] = a['dibayar_ppn']
        c['sisa_hutang'] = a['sisa_hutang']
        c['jumlah_invoice'] = a['jumlah_invoice']
        c['sisa_kontrak'] = dpp - tertagih
        # Progres = pembayaran (PEMBAYARAN DPP), bukan nilai invoice —
        # invoice belum dibayar tidak menaikkan progres.
        c['progres'] = (a['dibayar'] / dpp * 100) if dpp > 0 else 0.0
        # Progres PPN = pembayaran PPN terhadap Total PPN kontrak.
        c['progres_ppn'] = ((a['dibayar_ppn'] / c['nilai_ppn'] * 100)
                            if c['nilai_ppn'] > 0 else 0.0)
        c['over_ppn'] = bool(c['nilai_ppn'] > 0 and a['dibayar_ppn'] > c['nilai_ppn'])
        c['status_invoice'] = 'Ada Invoice' if a['jumlah_invoice'] > 0 else 'Belum Ada Invoice'
        c['over'] = bool(dpp > 0 and a['dibayar'] > dpp)
        out.append(c)

    if project_id is not None and str(project_id) not in ('all', ''):
        pid = str(project_id)
        # Tampilkan juga kontrak yang BELUM diikat proyek (project_id kosong)
        # dan kontrak yang punya invoice di proyek ini — supaya data yang baru
        # diimport tanpa memilih proyek tidak "hilang" dari daftar.
        out = [c for c in out
               if str(c.get('project_id') or '') == pid
               or str(c.get('project_id') or '') == ''
               or (c.get('jumlah_invoice') or 0) > 0]
    return out


def get_contract(contract_id):
    with _conn() as conn:
        conn.row_factory = _dict_factory
        c = conn.execute('SELECT * FROM vendor_contracts WHERE id = ?',
                         (contract_id,)).fetchone()
    if not c:
        return None
    a = _aggregate(_fetch_invoice_rows()).get(
        _norm_kontrak(c.get('no_kontrak')),
        {'tertagih': 0.0, 'tertagih_ppn': 0.0, 'dibayar': 0.0,
         'dibayar_ppn': 0.0, 'sisa_hutang': 0.0, 'jumlah_invoice': 0})
    nilai = safe_float(c.get('nilai_kontrak'))
    # Basis DPP, konsisten dengan get_contracts.
    dpp = safe_float(c.get('total_dpp')) or nilai
    c['nilai_dpp'] = dpp
    c['nilai_ppn'] = (safe_float(c.get('total_ppn'))
                      or dpp * safe_float(c.get('ppn_rate')) / 100.0)
    c['sisa_ppn'] = c['nilai_ppn'] - a['tertagih_ppn']
    tertagih = a['tertagih']
    c['tertagih'] = tertagih
    c['tertagih_ppn'] = a['tertagih_ppn']
    c['dibayar'] = a['dibayar']
    c['dibayar_ppn'] = a['dibayar_ppn']
    c['sisa_hutang'] = a['sisa_hutang']
    c['jumlah_invoice'] = a['jumlah_invoice']
    c['sisa_kontrak'] = dpp - tertagih
    c['progres'] = (a['dibayar'] / dpp * 100) if dpp > 0 else 0.0
    c['progres_ppn'] = ((a['dibayar_ppn'] / c['nilai_ppn'] * 100)
                        if c['nilai_ppn'] > 0 else 0.0)
    c['over_ppn'] = bool(c['nilai_ppn'] > 0 and a['dibayar_ppn'] > c['nilai_ppn'])
    c['status_invoice'] = 'Ada Invoice' if a['jumlah_invoice'] > 0 else 'Belum Ada Invoice'
    c['over'] = bool(dpp > 0 and a['dibayar'] > dpp)
    return c


def get_contract_by_no(no_kontrak):
    with _conn() as conn:
        conn.row_factory = _dict_factory
        return conn.execute(
            'SELECT * FROM vendor_contracts WHERE UPPER(TRIM(no_kontrak)) = ?',
            (_norm_kontrak(no_kontrak),)).fetchone()


def create_contract(no_kontrak, vendor, project_id='', nilai_kontrak=0,
                    tgl_kontrak='', tgl_mulai='', tgl_selesai='', keterangan='',
                    tipe_pekerjaan='', item_pekerjaan='', metode_pembayaran='',
                    durasi_termin=0, tipe_kontrak='', metode_penetapan='',
                    ppn_rate=0):
    # tgl_mulai tidak dipakai lagi (kolom DB dibiarkan kosong) — dipertahankan
    # di signature agar 3 call-site (create/update/import) tidak perlu diubah.
    with _conn() as conn:
        cur = conn.execute('''
            INSERT INTO vendor_contracts (no_kontrak, vendor, project_id,
                                          nilai_kontrak, tgl_kontrak,
                                          tgl_selesai, keterangan, tipe_pekerjaan,
                                          item_pekerjaan, metode_pembayaran,
                                          durasi_termin, tipe_kontrak,
                                          metode_penetapan, ppn_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (no_kontrak.strip(), vendor.strip(), str(project_id or ''),
              nilai_kontrak, tgl_kontrak, tgl_selesai, keterangan,
              tipe_pekerjaan.strip(), item_pekerjaan.strip(),
              metode_pembayaran.strip(), safe_float(durasi_termin),
              tipe_kontrak.strip(), metode_penetapan.strip(), safe_float(ppn_rate)))
        conn.commit()
        return cur.lastrowid


def update_contract(contract_id, no_kontrak, vendor, project_id, nilai_kontrak,
                    tgl_kontrak, tgl_mulai, tgl_selesai, keterangan,
                    tipe_pekerjaan='', item_pekerjaan='', metode_pembayaran='',
                    durasi_termin=0, tipe_kontrak='', metode_penetapan='',
                    ppn_rate=0):
    # tgl_mulai diabaikan — lihat create_contract.
    # Edit manual adalah sumber kebenaran: setelah user mengubah Nilai Kontrak,
    # total_dpp/total_ppn dari file Excel lama (bila ada) jadi usang, jadi ikut
    # di-reset. total_dpp = nilai_kontrak; total_ppn = 0 (diturunkan dari
    # ppn_rate saat ditampilkan). Tanpa ini, KPI/progres tetap memakai nilai
    # Excel lama dan perubahan user terabaikan.
    with _conn() as conn:
        conn.execute('''
            UPDATE vendor_contracts
               SET no_kontrak=?, vendor=?, project_id=?, nilai_kontrak=?,
                   tgl_kontrak=?, tgl_selesai=?, keterangan=?,
                   tipe_pekerjaan=?, item_pekerjaan=?, metode_pembayaran=?,
                   durasi_termin=?, tipe_kontrak=?, metode_penetapan=?, ppn_rate=?,
                   total_dpp=?, total_ppn=0
             WHERE id=?
        ''', (no_kontrak.strip(), vendor.strip(), str(project_id or ''),
              nilai_kontrak, tgl_kontrak, tgl_selesai,
              keterangan, tipe_pekerjaan.strip(), item_pekerjaan.strip(),
              metode_pembayaran.strip(), safe_float(durasi_termin),
              tipe_kontrak.strip(), metode_penetapan.strip(), safe_float(ppn_rate),
              safe_float(nilai_kontrak), contract_id))
        conn.commit()


def delete_contract(contract_id):
    with _conn() as conn:
        conn.execute('DELETE FROM vendor_contracts WHERE id = ?', (contract_id,))
        conn.execute('DELETE FROM vendor_contract_termin WHERE contract_id = ?',
                     (contract_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# TERMIN (jadwal pembayaran — dokumentasi)
# ---------------------------------------------------------------------------

def replace_termins(contract_id, termins):
    """Ganti seluruh termin kontrak (delete-then-insert, sesuai filosofi
    import 'replace, bukan akumulasi').

    termins: list dict {label, persen, nilai[, ppn_nilai]} — urutan list =
    urutan termin. Nilai kontrak di-recalc = SUM(nilai termin) bila ada
    minimal satu termin dengan nilai > 0; persen di-recalc = nilai/total
    bila kosong.
    """
    with _conn() as conn:
        conn.execute('DELETE FROM vendor_contract_termin WHERE contract_id = ?',
                     (contract_id,))
        for i, t in enumerate(termins or [], start=1):
            conn.execute('''
                INSERT INTO vendor_contract_termin
                    (contract_id, urutan, label, persen, nilai, ppn_nilai, tgl_termin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (contract_id, i,
                  (t.get('label') or '').strip(),
                  safe_float(t.get('persen')),
                  safe_float(t.get('nilai')),
                  safe_float(t.get('ppn_nilai')),
                  (t.get('tgl_termin') or '').strip()))
        total = conn.execute(
            'SELECT SUM(nilai) FROM vendor_contract_termin WHERE contract_id = ?',
            (contract_id,)).fetchone()[0] or 0.0
        # Hanya isi nilai_kontrak bila masih KOSONG. Kolom "Nilai Kontrak" dari
        # Excel harus dipertahankan: pada PPN Include nilainya LEBIH BESAR dari
        # jumlah Nilai DPP Termin, jadi jangan ditimpa dengan total termin.
        if total > 0:
            conn.execute(
                'UPDATE vendor_contracts SET nilai_kontrak = ? '
                'WHERE id = ? AND (nilai_kontrak IS NULL OR nilai_kontrak = 0)',
                (total, contract_id))
        conn.commit()
    _recalc_percent(contract_id)


def _recalc_percent(contract_id):
    """Isi persen dari nilai bila kolom % kosong (dan sebaliknya tak diubah)."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        terms = conn.execute(
            'SELECT id, persen, nilai FROM vendor_contract_termin '
            'WHERE contract_id = ? ORDER BY urutan', (contract_id,)).fetchall()
    total = sum(t['nilai'] for t in terms)
    if total <= 0:
        return
    update = []
    for t in terms:
        if not t['persen'] and t['nilai']:
            update.append((t['nilai'] / total * 100, t['id']))
    if update:
        with _conn() as conn:
            conn.executemany('UPDATE vendor_contract_termin SET persen = ? WHERE id = ?',
                             update)
            conn.commit()


def get_termins(contract_id):
    with _conn() as conn:
        conn.row_factory = _dict_factory
        return conn.execute(
            'SELECT * FROM vendor_contract_termin WHERE contract_id = ? '
            'ORDER BY urutan, id', (contract_id,)).fetchall()


PPN_RATE = 0.12   # tarif PPN berlaku (UU HPP)


def enrich_termins(termins, contract=None):
    """Turunkan kolom tampilan termin dari data yang tersimpan.

    Ditambahkan per baris:
      * normalisasi — persen terhadap nilai kontrak (Total Termin / Nilai
        Kontrak x 100). Ini yang dipakai untuk PPN, bukan persen mentah,
        karena file procurement bisa menulis total persen != 100%.
      * ppn_nilai   — dari file bila ada, selain itu Total Termin x PPN_RATE.
      * total_bayar — Total Termin + PPN bila metode 'PPN Include',
        selain itu Total Termin saja (PPN Reimburse ditagihkan terpisah).
    """
    # Basis DPP (Total DPP dari Excel; fallback nilai_kontrak bila kosong)
    # supaya normalisasi konsisten dengan halaman daftar kontrak.
    nilai_kontrak = (safe_float((contract or {}).get('total_dpp'))
                     or safe_float((contract or {}).get('nilai_kontrak')))
    metode = ((contract or {}).get('metode_pembayaran') or '').strip().lower()
    include = 'include' in metode
    # Tarif PPN fallback: dari kolom 'PPN (%)' file (disimpan sebagai persen,
    # mis. 11.0) bila ada, selain itu tarif global PPN_RATE (fraksi).
    rate_pct = safe_float((contract or {}).get('ppn_rate'))
    rate = rate_pct / 100.0 if rate_pct > 0 else PPN_RATE
    out = []
    for i, t in enumerate(termins or [], start=1):
        d = dict(t)
        nilai = safe_float(d.get('nilai'))
        if nilai_kontrak > 0:
            d['normalisasi'] = round(nilai / nilai_kontrak * 100, 4)
        else:
            d['normalisasi'] = safe_float(d.get('persen'))
        if safe_float(d.get('ppn_nilai')):
            d['ppn'] = safe_float(d.get('ppn_nilai'))
        else:
            d['ppn'] = round(nilai * rate, 2)
        # PPN (%) = PPN per Termin / Nilai Kontrak x 100 (sesuai file procurement).
        if nilai_kontrak > 0:
            d['ppn_persen'] = round(d['ppn'] / nilai_kontrak * 100, 4)
        else:
            d['ppn_persen'] = round(d['normalisasi'] * rate, 4)
        d['total_bayar'] = nilai + d['ppn'] if include else nilai
        d['urutan_no'] = i
        out.append(d)
    return out


def upsert_contract(no_kontrak, vendor, project_id='', nilai_kontrak=0,
                    tgl_kontrak='', tgl_mulai='', tgl_selesai='', keterangan='',
                    tipe_pekerjaan='', item_pekerjaan='', metode_pembayaran='',
                    durasi_termin=0, tipe_kontrak='', metode_penetapan='',
                    ppn_rate=0, total_dpp=0, total_ppn=0):
    """Insert-or-replace untuk import Excel.

    Nilai kontrak DIGANTI (bukan diakumulasi) karena satu file bisa berisi
    ulang kontrak yang sudah pernah diimport.
    Return (outcome, contract_id) dengan outcome 'inserted' | 'updated'.
    """
    key = _norm_kontrak(no_kontrak)
    if not key:
        return None, None
    with _conn() as conn:
        conn.row_factory = _dict_factory
        row = conn.execute(
            'SELECT id FROM vendor_contracts WHERE UPPER(TRIM(no_kontrak)) = ?',
            (key,)).fetchone()
        if row:
            conn.execute('''
                UPDATE vendor_contracts
                   SET vendor=?, project_id=?, nilai_kontrak=?,
                       tgl_kontrak=?, tgl_mulai=?, tgl_selesai=?, keterangan=?,
                       tipe_pekerjaan=?, item_pekerjaan=?, metode_pembayaran=?,
                       durasi_termin=?, tipe_kontrak=?, metode_penetapan=?,
                       ppn_rate=?, total_dpp=?, total_ppn=?
                 WHERE id=?
             ''', (vendor.strip(), str(project_id or ''), nilai_kontrak,
                   tgl_kontrak, tgl_mulai, tgl_selesai, keterangan,
                   tipe_pekerjaan.strip(), item_pekerjaan.strip(),
                   metode_pembayaran.strip(), safe_float(durasi_termin),
                   tipe_kontrak.strip(), metode_penetapan.strip(),
                   safe_float(ppn_rate), safe_float(total_dpp),
                   safe_float(total_ppn), row['id']))
            conn.commit()
            return 'updated', row['id']
        cur = conn.execute('''
            INSERT INTO vendor_contracts (no_kontrak, vendor, project_id,
                                          nilai_kontrak, tgl_kontrak, tgl_mulai,
                                          tgl_selesai, keterangan, tipe_pekerjaan,
                                          item_pekerjaan, metode_pembayaran,
                                          durasi_termin, tipe_kontrak,
                                          metode_penetapan, ppn_rate, total_dpp,
                                          total_ppn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (no_kontrak.strip(), vendor.strip(), str(project_id or ''),
              nilai_kontrak, tgl_kontrak, tgl_mulai, tgl_selesai, keterangan,
              tipe_pekerjaan.strip(), item_pekerjaan.strip(),
              metode_pembayaran.strip(), safe_float(durasi_termin),
              tipe_kontrak.strip(), metode_penetapan.strip(), safe_float(ppn_rate),
              safe_float(total_dpp), safe_float(total_ppn)))
        conn.commit()
        return 'inserted', cur.lastrowid


def import_contracts(rows):
    """Simpan hasil parse import Excel dalam SATU transaksi atomik.

    rows: list dict dari services.contract_excel.parse_contract_sheet.

    Menggabungkan upsert_contract + replace_termins sehingga bila salah satu
    baris gagal, seluruh import di-rollback (tidak ada kontrak "setengah
    tersimpan"). Return dict statistik:
        {'inserted', 'updated', 'total_termin', 'warnings', 'vendor_kosong',
         'di_luar_excel'}
    warnings: daftar string kontrak yang total Nilai DPP Termin-nya tidak sama
    dengan Nilai (DPP) kontrak (validasi ringan, seperti sebelumnya), plus
    kontrak yang Nama Vendor-nya kosong di Excel.
    di_luar_excel: daftar kontrak yang ada di DB tapi TIDAK ada di file Excel
    (kandidat data lama/duplikat) — hanya untuk pelaporan, tidak dihapus.
    """
    inserted = updated = total_termin = vendor_kosong = 0
    warn = []
    with _conn() as conn:
        conn.row_factory = _dict_factory
        for r in rows:
            key = _norm_kontrak(r['no_kontrak'])
            if not key:
                continue
            existing = conn.execute(
                'SELECT id FROM vendor_contracts WHERE UPPER(TRIM(no_kontrak)) = ?',
                (key,)).fetchone()
            if existing:
                cid = existing['id']
                conn.execute('''
                    UPDATE vendor_contracts
                       SET vendor=?, project_id=?, nilai_kontrak=?,
                           tgl_kontrak=?, tgl_mulai=?, tgl_selesai=?, keterangan=?,
                           tipe_pekerjaan=?, item_pekerjaan=?, metode_pembayaran=?,
                           durasi_termin=?, tipe_kontrak=?, metode_penetapan=?,
                           ppn_rate=?, total_dpp=?, total_ppn=?
                     WHERE id=?
                 ''', (r['vendor'].strip(), str(r.get('project_id') or ''),
                       r['nilai_kontrak'], r.get('tgl_kontrak', ''),
                       r.get('tgl_mulai', ''), r.get('tgl_selesai', ''),
                       r.get('keterangan', ''), r.get('tipe_pekerjaan', '').strip(),
                       r.get('item_pekerjaan', '').strip(),
                       r.get('metode_pembayaran', '').strip(),
                       safe_float(r.get('durasi_termin', 0)),
                       r.get('tipe_kontrak', '').strip(),
                       r.get('metode_penetapan', '').strip(),
                       safe_float(r.get('ppn_rate', 0)),
                       safe_float(r.get('total_dpp', 0)),
                       safe_float(r.get('total_ppn', 0)), cid))
                updated += 1
            else:
                cur = conn.execute('''
                    INSERT INTO vendor_contracts (no_kontrak, vendor, project_id,
                          nilai_kontrak, tgl_kontrak, tgl_mulai, tgl_selesai,
                          keterangan, tipe_pekerjaan, item_pekerjaan,
                          metode_pembayaran, durasi_termin, tipe_kontrak,
                          metode_penetapan, ppn_rate, total_dpp, total_ppn)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (r['no_kontrak'].strip(), r['vendor'].strip(),
                      str(r.get('project_id') or ''), r['nilai_kontrak'],
                      r.get('tgl_kontrak', ''), r.get('tgl_mulai', ''),
                      r.get('tgl_selesai', ''), r.get('keterangan', ''),
                      r.get('tipe_pekerjaan', '').strip(),
                      r.get('item_pekerjaan', '').strip(),
                      r.get('metode_pembayaran', '').strip(),
                      safe_float(r.get('durasi_termin', 0)),
                      r.get('tipe_kontrak', '').strip(),
                      r.get('metode_penetapan', '').strip(),
                      safe_float(r.get('ppn_rate', 0)),
                      safe_float(r.get('total_dpp', 0)),
                      safe_float(r.get('total_ppn', 0))))
                cid = cur.lastrowid
                inserted += 1

            # Ganti termin kontrak (delete-then-insert) dalam transaksi yang sama.
            conn.execute('DELETE FROM vendor_contract_termin WHERE contract_id = ?',
                         (cid,))
            termins = r.get('termins') or []
            for i, t in enumerate(termins, start=1):
                conn.execute('''
                    INSERT INTO vendor_contract_termin
                        (contract_id, urutan, label, persen, nilai, ppn_nilai, tgl_termin)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (cid, i, (t.get('label') or '').strip(),
                      safe_float(t.get('persen')), safe_float(t.get('nilai')),
                      safe_float(t.get('ppn_nilai')),
                      (t.get('tgl_termin') or '').strip()))
            total_termin += len(termins)

            # Isi nilai_kontrak bila kosong (jangan timpa nilai Excel).
            total_nilai = sum(safe_float(t.get('nilai')) for t in termins)
            if total_nilai > 0:
                conn.execute(
                    'UPDATE vendor_contracts SET nilai_kontrak = ? '
                    'WHERE id = ? AND (nilai_kontrak IS NULL OR nilai_kontrak = 0)',
                    (total_nilai, cid))

            # Validasi ringan: total DPP termin vs Nilai (DPP) kontrak.
            nilai_ref = safe_float(r.get('total_dpp')) or safe_float(r['nilai_kontrak'])
            if nilai_ref > 0 and total_nilai > 0 and abs(total_nilai - nilai_ref) > 1:
                warn.append(f"{r['no_kontrak']} — termin {total_nilai:,.0f} "
                            f"vs nilai DPP {nilai_ref:,.0f} "
                            f"(selisih {total_nilai - nilai_ref:+,.0f})")

            # Kontrak tanpa Nama Vendor di Excel: tetap diimport (data termin &
            # nilai tetap tersimpan), tapi dilaporkan agar pengguna melengkapi
            # nama vendor di Detail Kontrak. TIDAK diisi placeholder buatan.
            if not (r.get('vendor') or '').strip() or r.get('vendor_kosong'):
                vendor_kosong += 1
                warn.append(f"{r['no_kontrak']} — Nama Vendor kosong di Excel, "
                            f"lengkapi di Detail Kontrak")

        conn.commit()

        # Kontrak di DB yang TIDAK ada di file Excel = kandidat data lama/sampah
        # atau duplikat (mis. salah ketik No PO). Hanya DILAPORKAN, tidak
        # dihapus otomatis, supaya pengguna bisa periksa dulu di daftar kontrak.
        excel_keys = {_norm_kontrak(r['no_kontrak']) for r in rows
                      if _norm_kontrak(r['no_kontrak'])}
        di_luar = []
        for row in conn.execute(
                'SELECT no_kontrak, vendor FROM vendor_contracts ORDER BY no_kontrak'):
            k = _norm_kontrak(row['no_kontrak'])
            if k not in excel_keys:
                v = (row['vendor'] or '').strip() or '(vendor kosong)'
                di_luar.append(f"{row['no_kontrak']} ({v})")
    _recalc_percent_all()
    return {'inserted': inserted, 'updated': updated,
            'total_termin': total_termin, 'warnings': warn,
            'vendor_kosong': vendor_kosong, 'di_luar_excel': di_luar}


def _recalc_percent_all():
    """Isi persen kosong dari nilai untuk SEMUA termin (sekali, setelah import)."""
    with _conn() as conn:
        conn.row_factory = _dict_factory
        rows = conn.execute(
            'SELECT id, contract_id, persen, nilai FROM vendor_contract_termin '
            'ORDER BY contract_id, urutan').fetchall()
    totals = {}
    for r in rows:
        totals[r['contract_id']] = totals.get(r['contract_id'], 0.0) + (r['nilai'] or 0.0)
    update = []
    for r in rows:
        if not r['persen'] and r['nilai'] and totals.get(r['contract_id'], 0) > 0:
            update.append((r['nilai'] / totals[r['contract_id']] * 100, r['id']))
    if update:
        with _conn() as conn:
            conn.executemany('UPDATE vendor_contract_termin SET persen = ? WHERE id = ?',
                             update)
            conn.commit()


# ---------------------------------------------------------------------------
# INVOICE PER KONTRAK
# ---------------------------------------------------------------------------

def get_contract_invoices(no_kontrak):
    """Daftar invoice yang memakai nomor kontrak ini (exact match)."""
    key = _norm_kontrak(no_kontrak)
    out = []
    seen = set()
    for r in _fetch_invoice_rows():
        if _norm_kontrak(r.get('no_kontrak')) != key:
            continue
        inv = _invoice_identity(r)
        rekan = (r.get('rekanan') or '').strip()
        dedup_key = _dedup_key(r)
        is_dup = dedup_key in seen
        seen.add(dedup_key)
        out.append({
            '_row': r.get('_row'),
            'rekanan': rekan,
            'no_invoice': inv,
            'tgl_terima': r.get('tgl_terima') or '',
            'tgl_inv': r.get('tgl_inv') or '',
            'deskripsi': r.get('deskripsi') or '',
            'kode_biaya': r.get('kode_biaya') or '',
            'harga': 0.0 if is_dup else safe_float(r.get('harga')),
            'total': 0.0 if is_dup else safe_float(r.get('total')),
            'bayar': safe_float(r.get('bayar')),
            'bayar_ppn': safe_float(r.get('bayar_ppn')),
            'volume': r.get('volume') or '',
            'status_dpp': r.get('status_dpp') or '',
            'project_id': r.get('project_id') or '',
            'dup': is_dup,
        })
    return out


def _linked_invoice_counts(project_id, known_keys):
    """Jumlah invoice terhubung kontrak: belum lunas & jatuh tempo.

    Belum lunas = sisa DPP > 0 (HARGA (EXLD) - PEMBAYARAN DPP).
    Jatuh tempo = belum lunas dan JTH TEMPO <= hari ini.
    Dedup per (rekanan, invoice efektif) — sighting ganda tidak dihitung dua kali.
    """
    from constants import parse_date
    import datetime as _dt
    today = _dt.date.today()
    belum = jatuh = 0
    seen = set()
    for r in _fetch_invoice_rows(project_id):
        if _norm_kontrak(r.get('no_kontrak')) not in known_keys:
            continue
        dk = _dedup_key(r)
        if dk in seen:
            continue
        seen.add(dk)
        sisa = safe_float(r.get('harga')) - safe_float(r.get('bayar'))
        if sisa <= 0.005:
            continue
        belum += 1
        jth = parse_date((r.get('jth_tempo') or '').strip())
        if jth and jth.date() <= today:
            jatuh += 1
    return belum, jatuh


def get_summary(project_id=None):
    """Ringkasan untuk KPI halaman daftar kontrak.

    KPI = Σ Total DPP / Total PPN kolom Excel, persis seperti di file.
    Kontrak tanpa Total DPP (kolom kosong di Excel) tidak ikut dijumlahkan;
    PPN fallback = DPP x ppn_rate bila kolom Total PPN kosong.
    """
    contracts = get_contracts(project_id)
    total_dpp = total_ppn = 0.0
    for c in contracts:
        dpp = safe_float(c.get('total_dpp'))
        ppn = safe_float(c.get('total_ppn'))
        if not ppn and dpp:
            ppn = dpp * safe_float(c.get('ppn_rate')) / 100.0
        total_dpp += dpp
        total_ppn += ppn
    total_tertagih = sum(float(c.get('tertagih') or 0) for c in contracts)
    total_tertagih_ppn = sum(float(c.get('tertagih_ppn') or 0) for c in contracts)
    # Pembayaran & sisa hutang — DPP dan PPN selalu dipisah, tidak pernah digabung.
    total_dibayar = sum(float(c.get('dibayar') or 0) for c in contracts)
    total_dibayar_ppn = sum(float(c.get('dibayar_ppn') or 0) for c in contracts)
    total_sisa_dpp = sum(float(c.get('sisa_hutang') or 0) for c in contracts)
    total_sisa_ppn = sum(max(0.0, float(c.get('tertagih_ppn') or 0)
                             - float(c.get('dibayar_ppn') or 0)) for c in contracts)
    known_keys = {_norm_kontrak(c.get('no_kontrak')) for c in contracts}
    belum_lunas, jatuh_tempo = _linked_invoice_counts(project_id, known_keys)
    belum = sum(1 for c in contracts if c.get('status_invoice') == 'Belum Ada Invoice')
    return {
        'total_kontrak': len(contracts),
        'total_dpp': total_dpp,
        'total_ppn': total_ppn,
        'total_tertagih': total_tertagih,
        'total_tertagih_ppn': total_tertagih_ppn,
        'total_sisa': total_dpp - total_tertagih,
        'total_dibayar': total_dibayar,
        'total_dibayar_ppn': total_dibayar_ppn,
        'total_sisa_dpp': total_sisa_dpp,
        'total_sisa_ppn': total_sisa_ppn,
        'belum_lunas': belum_lunas,
        'jatuh_tempo': jatuh_tempo,
        'belum_invoice': belum,
    }


def get_unmatched_contract_nos(project_id=None):
    """Nomor kontrak di tabel hutang yang TIDAK ada di registri kontrak.

    Berguna untuk memastikan registri procurement lengkap.
    """
    known = set()
    for c in get_contracts('all'):
        known.add(_norm_kontrak(c.get('no_kontrak')))
    import db_ignore
    ignored_vendors = db_ignore.get_ignored_vendor_set()
    missing = {}
    for r in _fetch_invoice_rows(project_id):
        if db_ignore.normalize_vendor(r.get('rekanan')) in ignored_vendors:
            continue
        key = _norm_kontrak(r.get('no_kontrak'))
        if key and key not in known:
            slot = missing.setdefault(key, {'no_kontrak': (r.get('no_kontrak') or '').strip(),
                                            'rekanan': (r.get('rekanan') or '').strip(),
                                            'jumlah': 0})
            slot['jumlah'] += 1
    return sorted(missing.values(), key=lambda x: x['no_kontrak'])
