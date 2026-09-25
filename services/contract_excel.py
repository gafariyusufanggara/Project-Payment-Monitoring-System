"""
MODEL — Parser Excel daftar kontrak procurement.

Berbeda dengan services/excel_import.py (parser invoice yang pakai posisi
kolom tetap), file procurement tidak punya template baku. Parser ini
mendeteksi header secara longgar lalu membaca kolom berdasarkan NAMA.

Aturan bisnis yang disepakati:
  * Satu kontrak boleh muncul di BEBERAPA baris (termin/paket).
  * Nilai tiap baris DIJUMLAHKAN menjadi nilai_kontrak.
  * Identitas kontrak (vendor, tanggal, proyek) diambil dari baris pertama
    yang memuat nomor kontrak tersebut; baris berikutnya hanya menambah nilai.
  * Jika ada kolom Termin/Tahap atau Persen (%), SETIAP baris juga disimpan
    sebagai jadwal termin (vendor_contract_termin) — dokumentasi pembayaran.
"""

import re
from datetime import datetime, date

# Tarif PPN default. Dipakai untuk menghitung PPN per termin
# bila file tidak memuat kolom PPN sendiri.
DEFAULT_PPN_RATE = 0.12
# Sinonim header → field internal.
# Kunci perbandingan memakai _norm_key: lowercase, buang non-alnum KECUALI '%',
# supaya 'Termin' dan 'Termin (%)' tidak menabrak satu sama lain.
HEADER_ALIASES = {
    'no_kontrak': ['no kontrak', 'nomor kontrak', 'no. kontrak', 'no kontrak',
                   'no po', 'nomor po', 'no. po', 'no spk', 'nomor spk',
                   'no. spk', 'no perjanjian', 'nomor perjanjian', 'kode kontrak'],
    'vendor': ['vendor', 'rekanan', 'nama vendor', 'nama rekanan', 'supplier',
               'penyedia', 'nama penyedia', 'levelansir', 'nama levelansir',
               'perusahaan', 'nama perusahaan'],
    'nilai': ['nilai', 'nilai kontrak', 'nilai (rp)', 'nilai rp', 'total',
              'total nilai', 'jumlah', 'nilai pekerjaan', 'harga', 'amount',
              'nilai kontrak (rp)', 'sub total', 'subtotal'],
    'total_dpp': ['total dpp', 'total dpp (rp)', 'dpp kontrak'],
    'total_ppn': ['total ppn', 'total ppn (rp)', 'ppn kontrak'],
    'tgl_kontrak': ['tgl kontrak', 'tanggal kontrak', 'tgl. kontrak',
                    'tanggal po', 'tgl po', 'tgl. po', 'tanggal spk', 'tgl spk'],
    'tgl_selesai': ['tgl selesai', 'tanggal selesai', 'selesai', 'tgl end',
                    'end', 'tanggal selesai kontrak', 'berakhir', 'tgl berakhir',
                    'tgl kontrak selesai', 'tanggal kontrak selesai'],
    'keterangan': ['keterangan', 'deskripsi', 'uraian', 'pekerjaan',
                   'jenis pekerjaan', 'catatan', 'keterangan pekerjaan'],
    'project': ['proyek', 'project', 'nama proyek', 'kode proyek', 'lokasi'],
    'tipe_pekerjaan': ['tipe pekerjaan', 'tipe'],
    'item_pekerjaan': ['item pekerjaan', 'item'],
    'metode_pembayaran': ['metode pembayaran', 'metode'],
    'durasi_termin': ['durasi termin (hari)', 'durasi termin', 'durasi hari',
                      'durasi', 'termin hari', 'durasi termin pembayaran (hari)'],
    'ppn_nilai': ['ppn per termin', 'ppn per termin (rp)', 'ppn termin',
                  'ppn termin (rp)', 'ppn (rp)', 'nilai ppn termin'],
    'termin_persen': ['termin (%)', 'termin %', 'termin persen', 'persen termin'],
    'termin_nilai': ['total termin (rp)', 'total termin', 'nilai termin',
                     'termin (rp)', 'nilai termin (rp)', 'nilai dpp termin'],
    'tgl_termin': ['tgl maksimal termin', 'tanggal maksimal termin',
                   'tgl maks termin', 'tgl termin', 'tanggal termin'],
    'tipe_kontrak': ['tipe kontrak', 'jenis kontrak'],
    'metode_penetapan': ['metode penetapan nilai kontrak', 'metode penetapan',
                         'penetapan'],
    'ppn_rate': ['ppn (%)', 'ppn', 'tarif ppn', 'ppn persen'],
    'termin': ['termin', 'termin pembayaran', 'tahap', 'tahapan', 'tahap pembayaran',
               'syarat pembayaran', 'keterangan termin', 'payment term', 'milestone'],
    'persen': ['%', 'persen', 'persen (%)', 'persentase', 'prosentase', 'bobot',
               'progress', 'porsi', 'share'],
}

# Urutan pencocokan per kolom: field yang lebih spesifik dicek lebih dulu.
FIELD_ORDER = ['no_kontrak', 'vendor', 'nilai', 'total_dpp', 'total_ppn', 'tgl_kontrak', 'tgl_selesai',
               'tipe_pekerjaan', 'item_pekerjaan', 'metode_pembayaran',
               'durasi_termin', 'termin_persen', 'termin_nilai', 'ppn_nilai',
               'tgl_termin', 'tipe_kontrak', 'metode_penetapan', 'ppn_rate',
               'termin', 'persen', 'project', 'keterangan']

_MONEY_RE = re.compile(r'[^0-9\-.]')
_PCT_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*%')


def _norm(s):
    """Lowercase & squash whitespace for header comparison."""
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def _norm_key(s):
    """Kunci header: lowercase, buang non-alnum KECUALI '%'.

    '%' sengaja dipertahankan supaya 'Termin' (label) dan 'Termin (%)'
    (persentase) menjadi dua field berbeda, bukan tabrakan alias.
    """
    return re.sub(r'[^a-z0-9%]', '', _norm(s))


def _alias_keys(field):
    return {_norm_key(a) for a in HEADER_ALIASES[field]}


def _find_header(ws, max_scan=30):
    """Cari baris header: baris dengan >= 2 sel yang cocok alias kita.

    Return (row_idx, {field: col_idx}) atau (None, {}).
    """
    best_row, best_map, best_score = None, {}, 0
    for row_idx in range(1, min(max_scan, ws.max_row + 1) + 1):
        found = {}
        for col_idx in range(1, min(ws.max_column, 60) + 1):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is None:
                continue
            k = _norm_key(val)
            if not k:
                continue
            for field in FIELD_ORDER:
                if field in found:
                    continue
                if k in _alias_keys(field):
                    found[field] = col_idx
                    break
        # 'no_kontrak' + 'vendor' + 'nilai' adalah minimum yang masuk akal
        if {'no_kontrak', 'vendor'} <= found.keys() and len(found) > best_score:
            best_row, best_map, best_score = row_idx, found, len(found)
    return best_row, best_map


def _to_float(val):
    """Rupiah → float. Tahan terhadap '1.000.000', 'Rp 1,000,000.50', '(50000)'."""
    if val is None or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    neg = s.startswith('(') and s.endswith(')')
    s = s.strip('()')
    s = re.sub(r'(?i)rp\.?', '', s)
    s = re.sub(r'\s', '', s)
    s = s.rstrip('-')          # trailing minus (format akuntansi)
    s = re.sub(r'[^0-9.,\-]', '', s)
    if not s:
        return 0.0

    # Tentukan pemisah DESIMAL: '.' atau ',' terakhir yang diikuti 1-2 digit
    # di ujung string. Kalau tidak ada, berarti semua separator adalah ribuan.
    dec_sep = None
    m = re.search(r'[.,](\d{1,2})$', s)
    if m:
        dec_sep = s[m.start()]
    if dec_sep:
        thou = ',' if dec_sep == '.' else '.'
        s = s.replace(thou, '').replace(dec_sep, '.')
    else:
        s = s.replace('.', '').replace(',', '')
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if neg else v


def _to_percent(val):
    """'10%' / '10' / '10,5' → 10.0 ; '0.1' (pecahan tanpa %) → 10.0."""
    if val is None or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        v = float(val)
        return v * 100 if 0 < v <= 1 else v
    s = str(val).strip()
    if not s:
        return 0.0
    has_pct = '%' in s
    m = _PCT_RE.search(s)
    if m:
        s = m.group(1)
    else:
        s = re.sub(r'[^0-9.,\-]', '', s)
    s = s.replace(',', '.')
    try:
        v = float(s)
    except ValueError:
        return 0.0
    if not has_pct and 0 < v <= 1:
        v *= 100
    return v


def _pct_from_text(text):
    """Ambil '10%' di awal teks label seperti '10% Approval Engineering Doc'."""
    m = _PCT_RE.search(str(text or ''))
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(',', '.'))
    except ValueError:
        return 0.0


# Bulan Indonesia (dan varian umum) untuk tanggal teks seperti '24 Des 2025'.
_IDN_MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'jun': 6,
               'jul': 7, 'agu': 8, 'ags': 8, 'agt': 8, 'aug': 8, 'sep': 9,
               'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12}


def _to_date_str(val):
    if val is None or val == '':
        return ''
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
                '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    # Fallback: '24 Des 2025' / '14-Okt-2026' (bulan Indonesia, locale C tak kenal).
    m = re.match(r'^(\d{1,2})[\s\-./]+([A-Za-z]+)[\s\-./]+(\d{4})$', s)
    if m:
        mon = _IDN_MONTHS.get(m.group(2)[:3].lower())
        if mon:
            return f'{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}'
    return ''


def parse_contract_sheet(ws, project_id=''):
    """Parse worksheet -> (contracts, imported_rows, skipped_rows).

    contracts: list dict siap upsert, sudah digabung per no_kontrak.

    Format yang didukung:
      * BARU (docs/Template Kontrak Vendor Terbaru.csv): No / Tipe
        Pekerjaan / Item Pekerjaan / No PO / Vendor / Tipe Kontrak / Nilai
        Kontrak / Tgl Kontrak / Tgl Kontrak Selesai / Metode Penetapan Nilai
        Kontrak / PPN (%) / Total DPP / Total PPN / Metode Pembayaran / Termin /
        Tgl Maksimal Termin / Termin (%) / Normalisasi Termin (%) / Nilai DPP
        Termin / Nilai PPN Termin / Durasi Termin Pembayaran (Hari) / Total
        Tagihan (Exclude PPH) / Retensi (5%) / Tgl Terima Berkas Lengkap /
        Keterangan.
      * LAMA (docs/Template Kontrak Vendor.xlsx): tetap dikenali
        (No PO / Vendor / Nilai Kontrak / Termin / Termin (%) / Total Termin (Rp)).
      * Nilai kontrak hanya ditulis di baris pertama; baris termin lanjutan
        di-forward-fill (No PO kosong = lanjutan kontrak di atasnya).
      * Baris termin dengan label kosong dilewati (penjaga baris kosong Excel).
    """
    header_row, cmap = _find_header(ws)
    if header_row is None:
        return None

    col_no = cmap.get('no_kontrak')
    col_vendor = cmap.get('vendor')
    col_nilai = cmap.get('nilai')
    col_total_dpp = cmap.get('total_dpp')
    col_total_ppn = cmap.get('total_ppn')
    col_tgl = cmap.get('tgl_kontrak')
    col_selesai = cmap.get('tgl_selesai')
    col_ket = cmap.get('keterangan')
    col_termin = cmap.get('termin')
    col_persen = cmap.get('persen')
    col_termin_persen = cmap.get('termin_persen')
    col_termin_nilai = cmap.get('termin_nilai')
    col_ppn_nilai = cmap.get('ppn_nilai')
    col_tgl_termin = cmap.get('tgl_termin')
    col_tipe_kontrak = cmap.get('tipe_kontrak')
    col_penetapan = cmap.get('metode_penetapan')
    col_ppn_rate = cmap.get('ppn_rate')

    def _row_text(row_idx, col):
        if not col:
            return ''
        v = ws.cell(row=row_idx, column=col).value
        return '' if v is None else str(v).strip()

    def _row_date(row_idx, col):
        return _to_date_str(ws.cell(row=row_idx, column=col).value) if col else ''

    def _termin_entry(row_idx):
        """Data termin dari satu baris: (label, persen, nilai) — boleh kosong."""
        label = _row_text(row_idx, col_termin) or _row_text(row_idx, col_ket)
        # Total Termin (Rp) adalah sumber nilai paling tepercaya; Nilai Kontrak
        # dipakai hanya bila kolom termin-nilai tidak ada.
        if col_termin_nilai:
            nilai = _to_float(ws.cell(row=row_idx, column=col_termin_nilai).value)
        elif col_nilai:
            nilai = _to_float(ws.cell(row=row_idx, column=col_nilai).value)
        else:
            nilai = 0.0
        # Termin (%) dipakai untuk persen; kolom 'Persen' generik sebagai fallback.
        if col_termin_persen:
            persen = _to_percent(ws.cell(row=row_idx, column=col_termin_persen).value)
        elif col_persen:
            persen = _to_percent(ws.cell(row=row_idx, column=col_persen).value)
        else:
            persen = 0.0
        if not persen:
            persen = _pct_from_text(label)
        ppn = _to_float(ws.cell(row=row_idx, column=col_ppn_nilai).value) if col_ppn_nilai else 0.0
        tgl_termin = _row_date(row_idx, col_tgl_termin) if col_tgl_termin else ''
        return {'label': label, 'persen': persen, 'nilai': nilai, 'ppn_nilai': ppn,
                'tgl_termin': tgl_termin}

    def _is_blank_row(row_idx):
        for col_idx in range(1, min(ws.max_column, 60) + 1):
            v = ws.cell(row=row_idx, column=col_idx).value
            if v is not None and str(v).strip() != '':
                return False
        return True

    order = []
    merged = {}
    imported = 0
    skipped = 0
    empty_streak = 0
    last_no = ''      # forward-fill nomor PO untuk baris termin lanjutan

    for row_idx in range(header_row + 1, ws.max_row + 1):
        no = ws.cell(row=row_idx, column=col_no).value if col_no else None
        vendor = ws.cell(row=row_idx, column=col_vendor).value if col_vendor else None
        no_s = str(no).strip() if no is not None else ''
        vendor_s = str(vendor).strip() if vendor is not None else ''

        # Baris termin lanjutan: nomor PO kosong (format procurement lazim).
        if not no_s and last_no:
            no_s = last_no
        elif no_s:
            last_no = no_s
        elif _is_blank_row(row_idx):
            empty_streak += 1
            if empty_streak >= 40:
                break
            skipped += 1
            continue
        else:
            empty_streak = 0
            skipped += 1
            continue

        empty_streak = 0
        if not no_s:
            skipped += 1
            continue

        imported += 1
        key = no_s.upper()
        slot = merged.get(key)
        if slot is None:
            slot = {
                'no_kontrak': no_s,
                'vendor': vendor_s,
                'project_id': str(project_id or ''),
                'nilai_kontrak': 0.0,
                'total_dpp': _to_float(ws.cell(row=row_idx, column=col_total_dpp).value) if col_total_dpp else 0.0,
                'total_ppn': _to_float(ws.cell(row=row_idx, column=col_total_ppn).value) if col_total_ppn else 0.0,
                'tipe_pekerjaan': _row_text(row_idx, cmap.get('tipe_pekerjaan')),
                'item_pekerjaan': _row_text(row_idx, cmap.get('item_pekerjaan')),
                'tipe_kontrak': _row_text(row_idx, col_tipe_kontrak),
                'metode_penetapan': _row_text(row_idx, col_penetapan),
                'ppn_rate': _to_percent(ws.cell(row=row_idx, column=col_ppn_rate).value) if col_ppn_rate else 0.0,
                'metode_pembayaran': _row_text(row_idx, cmap.get('metode_pembayaran')),
                'durasi_termin': _row_text(row_idx, cmap.get('durasi_termin')),
                'tgl_kontrak': _row_date(row_idx, col_tgl),
                'tgl_mulai': '',
                'tgl_selesai': _row_date(row_idx, col_selesai),
                'keterangan': _row_text(row_idx, col_ket),
                'termins': [],
                'has_termin_col': bool(col_termin or col_persen
                                       or col_termin_persen or col_termin_nilai),
                # Penanda: baris kontrak ini tidak punya Nama Vendor di Excel.
                # Disimpan apa adanya (string kosong) TANPA placeholder buatan,
                # supaya pengguna tahu harus melengkapi di Detail Kontrak.
                'vendor_kosong': not vendor_s,
            }
            merged[key] = slot
            order.append(key)
        else:
            # Baris lanjutan: identitas diisi jika kosong.
            if not slot['vendor'] and vendor_s:
                slot['vendor'] = vendor_s
                slot['vendor_kosong'] = False
            if not slot['tipe_pekerjaan']:
                slot['tipe_pekerjaan'] = _row_text(row_idx, cmap.get('tipe_pekerjaan'))
            if not slot['item_pekerjaan']:
                slot['item_pekerjaan'] = _row_text(row_idx, cmap.get('item_pekerjaan'))
            if not slot['tipe_kontrak']:
                slot['tipe_kontrak'] = _row_text(row_idx, col_tipe_kontrak)
            if not slot['metode_penetapan']:
                slot['metode_penetapan'] = _row_text(row_idx, col_penetapan)
            if not slot['ppn_rate']:
                slot['ppn_rate'] = _to_percent(ws.cell(row=row_idx, column=col_ppn_rate).value) if col_ppn_rate else 0.0
            if not slot['total_dpp'] and col_total_dpp:
                slot['total_dpp'] = _to_float(ws.cell(row=row_idx, column=col_total_dpp).value)
            if not slot['total_ppn'] and col_total_ppn:
                slot['total_ppn'] = _to_float(ws.cell(row=row_idx, column=col_total_ppn).value)
            if not slot['metode_pembayaran']:
                slot['metode_pembayaran'] = _row_text(row_idx, cmap.get('metode_pembayaran'))
            if not slot['durasi_termin']:
                slot['durasi_termin'] = _row_text(row_idx, cmap.get('durasi_termin'))
            if not slot['tgl_kontrak']:
                slot['tgl_kontrak'] = _row_date(row_idx, col_tgl)
            if not slot['tgl_selesai']:
                slot['tgl_selesai'] = _row_date(row_idx, col_selesai)
            if not slot['keterangan']:
                slot['keterangan'] = _row_text(row_idx, col_ket)

        # Nilai kontrak: hanya dari baris yang memuat angka di kolom Nilai
        # Kontrak. Baris termin lanjutan memakai Total Termin (Rp), jadi tidak
        # boleh ikut menambah nilai kontrak (format procurement menulis total
        # sekali di baris pertama).
        if col_nilai and not col_termin_nilai:
            slot['nilai_kontrak'] += _to_float(ws.cell(row=row_idx, column=col_nilai).value)
        elif col_nilai and col_termin_nilai:
            v = _to_float(ws.cell(row=row_idx, column=col_nilai).value)
            if v:
                slot['nilai_kontrak'] = v

        if slot['has_termin_col']:
            entry = _termin_entry(row_idx)
            # Penjaga: baris tanpa label DAN tanpa nilai bukan termin.
            if entry['label'] or entry['nilai'] or entry['persen']:
                slot['termins'].append(entry)

    out = [merged[k] for k in order]
    # File tanpa kolom termin/persen: perilaku lama (baris lanjutan dijumlahkan,
    # tidak ada jadwal termin yang disimpan).
    for slot in out:
        if not slot.pop('has_termin_col', False):
            slot['termins'] = []
    return out, imported, skipped


def detect_contract_sheet(wb, preferred=('kontrak', 'contract', 'procurement', 'po', 'spk')):
    """Pilih sheet yang paling mirip daftar kontrak."""
    for name in wb.sheetnames:
        n = _norm(name)
        for p in preferred:
            if p in n:
                return name
    return wb.sheetnames[0]
