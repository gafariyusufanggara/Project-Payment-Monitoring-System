"""
MODEL — Scanner No PO / Kontrak yang "mirip tapi tidak cocok".

Read-only. Membandingkan nomor PO yang dipakai di invoice (tabel hutang)
dengan nomor kontrak di registri (vendor_contracts), lalu melaporkan pola
yang perlu ditinjau MANUSIA:

  A. MIRIP_VENDOR_SAMA  (satu-satunya temuan "mirip")
     Nomor PO invoice mirip (>= ambang) dengan nomor kontrak DAN vendor-nya
     SAMA (setelah normalisasi 'PT.'='PT', spasi, kapitalisasi). Inilah
     kandidat typo yang sesungguhnya — mis. PB.021/.../02/... vs
     PB.021/.../03/... milik PT ARLISCO yang sama.
     Nomor yang mirip tapi vendornya BERBEDA sengaja TIDAK dilaporkan: itu
     hampir selalu kontrak berbeda (nomor urut berdekatan), bukan typo.
     HANYA dilaporkan — TIDAK pernah menghubungkan otomatis.

  B. KONTRAK_TANPA_INVOICE
     Kontrak di registri yang belum punya satu invoice pun. Bisa berarti
     invoicenya belum diinput, atau nomor PO-nya beda/typo.

Tidak ada dependensi Flask — murni komputasi, agar mudah diuji.
"""
import time
from difflib import SequenceMatcher

import db
import db_contract
from constants import safe_float

# Ambang kemiripan (0..1). 0.90 dipilih konservatif: cukup tinggi untuk
# menangkap typo 1-2 karakter, tapi tidak menandai nomor yang strukturnya
# jauh berbeda. Sesuai keputusan pengguna.
SIMILARITY_THRESHOLD = 0.90

_COL_PO = 'NO PO / KONTRAK'
_COL_REKANAN = 'NAMA LEVELANSIR / REKANAN'
_COL_HARGA = 'HARGA (EXLD)'


def _norm_vendor(name):
    """Normalisasi nama vendor: lowercase, spasi dirapatkan, 'pt.'->'pt'.

    Sengaja memakai ulang aturan _normalize_rekanan milik verification.py agar
    konsisten dengan halaman Verifikasi Data ('PT. ARLISCO' == 'PT ARLISCO').
    """
    if not name:
        return ''
    s = str(name).lower().strip()
    s = ' '.join(s.split())
    for pref in ('pt.', 'cv.', 'ud.', 'pd.'):
        if s.startswith(pref):
            s = s.replace(pref, pref[:-1] + ' ', 1)
    s = ' '.join(s.split())
    return s.strip(' .,-;:')


def _sim(a, b):
    """Kemiripan dua nomor secara case-insensitive (0..1)."""
    return SequenceMatcher(None, str(a or '').upper(), str(b or '').upper()).ratio()


def find_po_similarity(project_id=None):
    """Jalankan pemindaian.

    Return dict:
        {
          'mirip':            [ {po, vendor, jumlah, kandidat:[{no_kontrak,
                                vendor, skor}], kandidat_sama:[...]} ... ],  # A (vendor sama)
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
    contracts = db_contract.get_contracts(project_id if project_id not in (None, '', 'all') else 'all')

    # Nomor kontrak + vendor, dengan versi normalized untuk exact-match.
    kontrak_norm = {}
    kontrak_list = []
    kontrak_vendor_norm = {}  # no_kontrak -> vendor normalized
    for c in contracts:
        no = (c.get('no_kontrak') or '').strip()
        if not no:
            continue
        kontrak_list.append(no)
        kontrak_norm[db_contract._norm_kontrak(no)] = c
        kontrak_vendor_norm[no] = _norm_vendor(c.get('vendor'))

    # Kumpulkan No PO dari invoice + vendor + jumlah + nilai HARGA (EXLD).
    po_slots = {}
    unmatched_value = 0.0
    unmatched_count = 0
    for r in data:
        po = (r.get(_COL_PO) or '').strip()
        if not po:
            continue
        slot = po_slots.setdefault(po, {'po': po, 'vendor': '', 'jumlah': 0,
                                        'vendor_set': set()})
        slot['jumlah'] += 1
        rekan = (r.get(_COL_REKANAN) or '').strip()
        if rekan:
            slot['vendor_set'].add(rekan)
        # Ringkasan nilai yang belum tercocok kontrak mana pun.
        if db_contract._norm_kontrak(po) not in kontrak_norm:
            unmatched_value += safe_float(r.get(_COL_HARGA))
            unmatched_count += 1

    # --- Pola A: mirip + vendor sama (kandidat typo) ---
    mirip = []
    for po, slot in po_slots.items():
        if db_contract._norm_kontrak(po) in kontrak_norm:
            continue  # cocok persis (setelah normalize) — bukan temuan
        vendor_inv_norm = _norm_vendor(' / '.join(sorted(slot['vendor_set'])))
        scored = []
        for no in kontrak_list:
            s = _sim(po, no)
            if s >= SIMILARITY_THRESHOLD:
                scored.append((s, no))
        if not scored:
            continue
        scored.sort(reverse=True)
        # Vendor yang SAMA dengan invoice menentukan kandidat typo. Nomor mirip
        # tapi vendor beda sengaja DIABAIKAN (hampir selalu kontrak berbeda).
        same_vendor = [(s, no) for s, no in scored
                       if vendor_inv_norm and kontrak_vendor_norm.get(no)
                       and kontrak_vendor_norm.get(no) == vendor_inv_norm]
        if not same_vendor:
            continue
        entry = {
            'po': po,
            'vendor': ' / '.join(sorted(slot['vendor_set'])) or '(vendor kosong)',
            'jumlah': slot['jumlah'],
            'kandidat': [
                {'no_kontrak': no,
                 'vendor': (kontrak_norm.get(db_contract._norm_kontrak(no), {}) or {}).get('vendor', ''),
                 'skor': round(s, 3)}
                for s, no in scored[:3]
            ],
            'kandidat_sama': [
                {'no_kontrak': no,
                 'vendor': (kontrak_norm.get(db_contract._norm_kontrak(no), {}) or {}).get('vendor', ''),
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
        # kandidat typo (mirip & vendor sama). Inilah "yang bermasalah" —
        # bukan total temuan, bukan jumlah kontrak.
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
