"""
MODEL — Scanner No PO / Kontrak yang "mirip tapi tidak cocok".

Read-only. Membandingkan nomor PO yang dipakai di invoice (tabel hutang)
dengan nomor kontrak di registri (vendor_contracts), lalu melaporkan kandidat
typo yang perlu ditinjau MANUSIA:

  A. MIRIP & VENDOR SAMA  (satu-satunya temuan "mirip")
     Nomor PO invoice mirip (>= ambang) dengan nomor kontrak, SERIAL DEPAN-nya
     SAMA (mis. sama-sama 'PB.038'), DAN vendor-nya SAMA (setelah normalisasi
     nama: tanda baca/titik diabaikan & toleran varian ejaan kecil seperti
     'SYSTEM' vs 'SYSTEMS'). Inilah kandidat typo yang sesungguhnya — mis.
     PB.038/.../02/... vs PB.038/.../03/... milik PT CONTROL SYSTEM yang sama.

     Yang sengaja TIDAK dilaporkan (agar tidak menjadi noise):
       - nomor mirip tetapi SERIAL DEPAN berbeda (PB.038 vs PB.039) — itu PO
         berbeda, bukan typo;
       - nomor mirip tetapi vendornya BERBEDA — hampir selalu kontrak berbeda.
     HANYA dilaporkan, TIDAK pernah menghubungkan otomatis.

  B. KONTRAK_TANPA_INVOICE
     Kontrak di registri yang belum punya satu invoice pun. Bisa berarti
     invoicenya belum diinput, atau nomor PO-nya beda/typo.

Pencocokan memakai NORMALISASI NOMOR (lihat _norm_number): beda pemisah
('.'/'/'/'-'/' ') dan beda nol depan tiap segmen angka dianggap SAMA
('PB.021' == 'PB.21', '064' == '64'). Dengan begitu nomor yang sebenarnya sama
tetapi ditulis beda format tidak lagi dianggap "belum terdaftar", sedangkan
nomor yang mirip (kandidat typo) tetap muncul untuk diperiksa.

Tidak ada dependensi Flask — murni komputasi, agar mudah diuji.
"""
import re
import time
from difflib import SequenceMatcher

import db
import db_contract
from constants import safe_float, is_excluded_row

# Ambang kemiripan (0..1) pada nomor yang SUDAH dinormalisasi. 0.85 dipilih
# agar typo 1-2 karakter / beda 1 segmen angka ikut tertangkap. Karena hanya
# kandidat dengan VENDOR SAMA yang dilaporkan, ambang rendah tidak menambah
# noise berarti.
SIMILARITY_THRESHOLD = 0.85

# Ambang kemiripan NAMA VENDOR (0..1) setelah normalisasi. Vendor dianggap
# "sama" bila persis sama ATAU mirip di atas ambang ini — menangkap variasi
# ejaan seperti 'SYSTEM' vs 'SYSTEMS', 'JASEN' vs 'JASHEN'. 0.90 cukup tinggi
# sehingga vendor yang benar-benar berbeda (mis. 'POWERINDO' vs 'TRAFOINDO'
# ~0.85, 'MERCURY TEKINDO' vs 'MERCURY TERKINDO' ~0.84) tetap dianggap beda.
VENDOR_SIMILARITY_THRESHOLD = 0.90

_COL_PO = 'NO PO / KONTRAK'
_COL_REKANAN = 'NAMA LEVELANSIR / REKANAN'
_COL_HARGA = 'HARGA (EXLD)'


def _norm_vendor(name):
    """Normalisasi nama vendor agar varian ejaan yang setara menjadi IDENTIK.

    - lower-case
    - SEMUA tanda baca/titik ('.', ',', '-', '/', '&', '(', ')', dll) diubah
      menjadi spasi, sehingga 'PT.' == 'PT', 'CV.' == 'CV', 'UD.' == 'UD',
      'PT.ARLISCO' == 'PT ARLISCO', dan titik di mana pun tidak lagi membedakan.
    - spasi dirapatkan (termasuk spasi ganda / di ujung).

    Contoh: 'PT. CONTROL SYSTEMS ARENA PARA NUSA'
         -> 'pt control systems arena para nusa'
    """
    if not name:
        return ''
    s = str(name).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split()).strip()


def _norm_number(val):
    """Normalisasi nomor untuk perbandingan (case-insensitive).

    - upper-case
    - buang nol depan pada tiap deret angka ('021' -> '21', '04' -> '4')
    - buang semua karakter non-alfanumerik (pemisah . / - spasi diabaikan)

    Hasil berupa string "padat" sehingga 'PB.021/PO/...' == 'PB.21/PO/...'.
    """
    s = str(val or '').upper()
    s = re.sub(r'\d+', lambda m: str(int(m.group(0))), s)
    s = re.sub(r'[^A-Z0-9]', '', s)
    return s


def _sim(a, b):
    """Kemiripan dua nomor SETELAH normalisasi (0..1)."""
    na, nb = _norm_number(a), _norm_number(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def _vendor_match(v_norm_inv, v_norm_kontrak):
    """Apakah dua vendor (sudah dinormalisasi) dianggap SAMA.

    Persis sama -> True. Selain itu, dinilai mirip bila skor kemiripan teks
    >= VENDOR_SIMILARITY_THRESHOLD (menangkap typo/varian ejaan seperti
    'SYSTEM' vs 'SYSTEMS'). Vendor yang benar-benar beda tetap False.
    """
    if not v_norm_inv or not v_norm_kontrak:
        return False
    if v_norm_inv == v_norm_kontrak:
        return True
    return SequenceMatcher(None, v_norm_inv, v_norm_kontrak).ratio() >= VENDOR_SIMILARITY_THRESHOLD


def _leading_serial(no):
    """Ambil SERIAL DEPAN nomor PO/kontrak (segmen sebelum '/' pertama),
    dinormalisasi: upper-case, buang nol depan pada deret angka, buang
    non-alfanumerik. Contoh: 'PB.038/PO/...' -> 'PB38', 'PB.38/...' -> 'PB38'.

    Dipakai sebagai gerbang: nomor PO invoice hanya boleh dianggap kandidat
    typo bila SERIAL DEPAN-nya SAMA dengan nomor kontrak. Nomor dengan serial
    depan berbeda (mis. PB.038 vs PB.039) adalah PO BERBEDA — bukan typo —
    sehingga tidak perlu muncul sebagai kandidat (mengurangi noise).
    """
    seg = str(no or '').strip().split('/')[0].upper()
    seg = re.sub(r'\d+', lambda m: str(int(m.group(0))), seg)
    return re.sub(r'[^A-Z0-9]', '', seg)


def find_po_similarity(project_id=None):
    """Jalankan pemindaian.

    Return dict:
        {
          'mirip':            [ {po, vendor, jumlah, kandidat:[{no_kontrak,
                                vendor, skor}], kandidat_sama:[...]} ... ],  # A
          'tanpa_invoice':    [ {id, no_kontrak, vendor, nilai_dpp} ... ],   # B
          'unmatched_value':  float,  # total HARGA (EXLD) invoice yg PO-nya
                                      # tidak cocok kontrak mana pun
          'unmatched_count':  int,    # jumlah invoice (baris) yg belum tercocok
          'mirip_invoice':    int,    # jumlah invoice pada kandidat typo (A)
          'tanpa_invoice_count': int, # jumlah kontrak tanpa invoice (B)
          'count':            int,    # angka badge = invoice kandidat typo (A)
        }
    """
    data = db.read_data(project_id=project_id)
    # Exclude Invoice: baris ter-exclude tidak ikut perhitungan nilai/nomor PO.
    data = [r for r in data if not is_excluded_row(r)]
    contracts = db_contract.get_contracts(project_id if project_id not in (None, '', 'all') else 'all')

    # Peta nomor kontrak: exact (trim+upper) & normalized-number, plus vendor.
    kontrak_by_norm = {}      # _norm_kontrak(no) -> contract
    kontrak_by_num = {}       # _norm_number(no)  -> contract (setara numerik)
    kontrak_list = []
    kontrak_vendor_norm = {}  # no_kontrak -> vendor normalized
    for c in contracts:
        no = (c.get('no_kontrak') or '').strip()
        if not no:
            continue
        kontrak_list.append(no)
        kontrak_by_norm[db_contract._norm_kontrak(no)] = c
        kontrak_by_num.setdefault(_norm_number(no), c)
        kontrak_vendor_norm[no] = _norm_vendor(c.get('vendor'))

    def _is_exact(po):
        """Nomor invoice dianggap SUDAH cocok kontrak bila sama persis
        (trim+upper) ATAU setara secara numerik (beda nol-depan/pemisah)."""
        return (db_contract._norm_kontrak(po) in kontrak_by_norm
                or _norm_number(po) in kontrak_by_num)

    # Kumpulkan No PO dari invoice + vendor + jumlah + nilai HARGA (EXLD).
    po_slots = {}
    unmatched_value = 0.0
    unmatched_count = 0
    for r in data:
        po = (r.get(_COL_PO) or '').strip()
        if not po:
            continue
        slot = po_slots.setdefault(po, {'po': po, 'jumlah': 0, 'vendor_set': set()})
        slot['jumlah'] += 1
        rekan = (r.get(_COL_REKANAN) or '').strip()
        if rekan:
            slot['vendor_set'].add(rekan)
        # Ringkasan nilai yang belum tercocok kontrak mana pun.
        if not _is_exact(po):
            unmatched_value += safe_float(r.get(_COL_HARGA))
            unmatched_count += 1

    # --- Pola A: mirip + vendor sama (kandidat typo) ---
    mirip = []
    for po, slot in po_slots.items():
        if _is_exact(po):
            continue  # cocok persis / setara numerik — bukan temuan
        vendor_inv_norm = _norm_vendor(' / '.join(sorted(slot['vendor_set'])))
        if not vendor_inv_norm:
            continue  # tanpa vendor, tak bisa dipastikan sama — hindari noise
        scored = []
        for no in kontrak_list:
            s = _sim(po, no)
            if s >= SIMILARITY_THRESHOLD:
                scored.append((s, no))
        if not scored:
            continue
        scored.sort(reverse=True)
        # Hanya serial depan yang SAMA yang bisa jadi kandidat typo. Serial
        # depan berbeda = PO berbeda, bukan typo — dibuang agar tidak jadi noise.
        po_serial = _leading_serial(po)
        scored = [(s, no) for s, no in scored if _leading_serial(no) == po_serial]
        if not scored:
            continue
        # Vendor yang SAMA dengan invoice menentukan kandidat typo. Nomor mirip
        # tapi vendor beda sengaja DIABAIKAN (hampir selalu kontrak berbeda).
        same_vendor = [(s, no) for s, no in scored
                       if _vendor_match(vendor_inv_norm, kontrak_vendor_norm.get(no))]
        if not same_vendor:
            continue
        entry = {
            'po': po,
            'vendor': ' / '.join(sorted(slot['vendor_set'])) or '(vendor kosong)',
            'jumlah': slot['jumlah'],
            'kandidat': [
                {'no_kontrak': no,
                 'vendor': (kontrak_by_norm.get(db_contract._norm_kontrak(no), {}) or {}).get('vendor', ''),
                 'skor': round(s, 3)}
                for s, no in scored[:3]
            ],
            'kandidat_sama': [
                {'no_kontrak': no,
                 'vendor': (kontrak_by_norm.get(db_contract._norm_kontrak(no), {}) or {}).get('vendor', ''),
                 'skor': round(s, 3)}
                for s, no in same_vendor[:3]
            ],
        }
        mirip.append(entry)
    mirip.sort(key=lambda x: (-x['kandidat_sama'][0]['skor'], x['po']))

    # --- Pola B: kontrak tanpa invoice ---
    tanpa_invoice = []
    for c in contracts:
        if (c.get('jumlah_invoice') or 0) == 0:
            tanpa_invoice.append({
                'id': c.get('id'),
                'no_kontrak': (c.get('no_kontrak') or '').strip(),
                'vendor': (c.get('vendor') or '').strip() or '(vendor kosong)',
                'nilai_dpp': c.get('nilai_dpp') or 0,
            })
    tanpa_invoice.sort(key=lambda x: x['no_kontrak'])

    return {
        'mirip': mirip,
        'tanpa_invoice': tanpa_invoice,
        'unmatched_value': unmatched_value,
        'unmatched_count': unmatched_count,
        # Angka badge di halaman Progress Kontrak = jumlah INVOICE yang masuk
        # kandidat typo (mirip & vendor sama). Inilah "yang bermasalah".
        'mirip_invoice': sum(m['jumlah'] for m in mirip),
        'tanpa_invoice_count': len(tanpa_invoice),
        'count': sum(m['jumlah'] for m in mirip),
    }


def count_findings(project_id=None):
    """Jumlah ringkas temuan untuk badge di halaman daftar kontrak."""
    res = find_po_similarity(project_id)
    return res['count']


# ── Cache in-process untuk badge sidebar ────────────────────────────
# Sidebar dirender di SETIAP halaman, tapi pemindaian kemiripan No PO cukup
# berat (invoice x kontrak). Cache TTL pendek agar tidak dihitung ulang tiap
# request, tapi tetap segar setelah import/edit. Key = project_id (bisa None).
_CACHE_TTL = 30.0  # detik
_cache = {}  # { project_id: (timestamp, count) }


def count_cached(project_id=None):
    """Seperti count_findings(), tetapi dengan cache TTL pendek.

    Dipakai khusus untuk badge sidebar agar tiap request tidak memicu
    pemindaian ulang penuh.
    """
    now = time.time()
    hit = _cache.get(project_id)
    if hit and (now - hit[0]) < _CACHE_TTL:
        return hit[1]
    try:
        count = find_po_similarity(project_id)['count']
    except Exception:
        count = 0
    _cache[project_id] = (now, count)
    return count


def invalidate_cache():
    """Kosongkan cache (dipanggil setelah import/ubah kontrak bila perlu)."""
    _cache.clear()
