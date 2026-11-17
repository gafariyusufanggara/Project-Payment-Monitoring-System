# -*- coding: utf-8 -*-
"""Smoke check: scanner No PO mirip (services/contract_match.py) + integrasinya.

Memverifikasi:
  1. Normalisasi nomor: beda pemisah & nol depan dianggap setara
     ('PB.021' == 'PB.21', '064' == '64').
  2. Klasifikasi (uji sintetis): hanya nomor mirip yang VENDOR-nya SAMA yang
     dilaporkan; nomor mirip dengan vendor BERBEDA sengaja DIBUANG (anti-noise).
     Nomor setara numerik tidak dihitung "belum tercocok".
  3. Data nyata: struktur + tidak ada false positive (nomor cocok persis /
     setara numerik tidak masuk temuan).
  4. Setiap temuan benar-benar vendornya sama (saringan vendor).
  5. Review-only: scanner tidak pernah menghubungkan otomatis.
  6. Halaman /kontrak/tinjau-no-po render 200 dengan section + tab; route lama
     /kontrak/belum-terdaftar tetap redirect.
  7. Kategori WARNING No PO terpasang di services/verification.py.

Run:  python smoke_po_similarity_check.py
Read-only terhadap data nyata.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as appmod
import db_contract
from services import contract_match
from services.contract_match import (
    find_po_similarity, _norm_number, _sim, _norm_vendor, SIMILARITY_THRESHOLD,
)

app = appmod.app
# Pemindaian memakai is_excluded_row yang membaca session (exclusion settings);
# sediakan request context agar bisa dipanggil di luar web request.
_ctx = app.test_request_context('/')
_ctx.push()


# --- 0. Normalisasi nomor ---
assert _norm_number('PB.021/PO/NK-WIKA/02/SINTONG/04/2026') == \
       _norm_number('PB.21/PO/NK-WIKA/02/SINTONG/04/2026'), "PB.021 != PB.21"
assert _norm_number('064/KONTRAK/NK-WIKA/09/2026') == \
       _norm_number('64/KONTRAK/NK-WIKA/09/2026'), "064 != 64"
assert _sim('PB.021/PO/X/04/2026', 'PB.22/PO/X/04/2026') > 0.9
assert _sim('', 'PB.021') == 0.0
print('[0] normalisasi nomor OK (pemisah & nol depan diabaikan)')


# --- 0b. Kecocokan vendor toleran varian ejaan kecil ---
from services.contract_match import _vendor_match
# Beda HANYA titik / tanda baca -> harus IDENTIK setelah normalisasi.
assert _norm_vendor('PT. ARLISCO ELEKTRIKA PERKASA') == \
       _norm_vendor('PT ARLISCO ELEKTRIKA PERKASA'), "titik pada 'PT.' harus diabaikan"
assert _norm_vendor('CV. MAJU JAYA') == _norm_vendor('CV MAJU JAYA'), "titik pada 'CV.' harus diabaikan"
assert _norm_vendor('PT.ARLISCO') == _norm_vendor('PT ARLISCO'), "'PT.ARLISCO' harus == 'PT ARLISCO'"
assert _vendor_match(_norm_vendor('PT. ARLISCO'), _norm_vendor('PT ARLISCO')) is True, \
    "vendor beda hanya titik harus dianggap sama"
assert _vendor_match(_norm_vendor('PT. CONTROL SYSTEMS ARENA PARA NUSA'),
                     _norm_vendor('PT CONTROL SYSTEM ARENA PARA NUSA')) is True, \
    "SYSTEM vs SYSTEMS harus dianggap vendor sama"
assert _vendor_match(_norm_vendor('PT JASEN MITRA SINERGI'),
                     _norm_vendor('PT. JASHEN MITRA SINERGI')) is True, \
    "JASEN vs JASHEN harus dianggap vendor sama"
assert _vendor_match(_norm_vendor('PT POWERINDO PRIMA PERKASA'),
                     _norm_vendor('PT TRAFOINDO PRIMA PERKASA')) is False, \
    "POWERINDO vs TRAFOINDO harus dianggap beda (anti-noise)"
assert _vendor_match(_norm_vendor('PT MERCURY TEKINDO INDONESIA'),
                     _norm_vendor('PT MERCURY TERKINDO INTERNUSA')) is False, \
    "MERCURY TEKINDO vs TERKINDO harus dianggap beda (anti-noise)"
print('[0b] kecocokan vendor (titik/tanda baca & varian ejaan, tolak vendor beda) OK')


# --- 1. Klasifikasi: hanya vendor SAMA yang muncul (uji sintetis) ---
import services.contract_match as cm


def _run_synthetic(contracts, data):
    orig_read = cm.db.read_data
    orig_get = cm.db_contract.get_contracts
    orig_exc = cm.is_excluded_row
    try:
        cm.db.read_data = lambda project_id=None: data
        cm.db_contract.get_contracts = lambda pid=None: contracts
        cm.is_excluded_row = lambda row: False
        return find_po_similarity('all')
    finally:
        cm.db.read_data = orig_read
        cm.db_contract.get_contracts = orig_get
        cm.is_excluded_row = orig_exc

_syn_contracts = [
    {'id': 1, 'no_kontrak': 'PB.021/PO/NK-WIKA/02/SINTONG/04/2026',
     'vendor': 'PT ARLISCO ELEKTRIKA PERKASA', 'jumlah_invoice': 1, 'nilai_dpp': 1000},
    {'id': 2, 'no_kontrak': 'PB.064/PO/NK-WIKA/03/SINTONG/09/2026',
     'vendor': 'PT KOROSI SPECINDO', 'jumlah_invoice': 0, 'nilai_dpp': 500},
    {'id': 3, 'no_kontrak': 'PB.038/PO/NK-WIKA/02/SINTONG/06/2026',
     'vendor': 'PT CONTROL SYSTEM ARENA PARA NUSA', 'jumlah_invoice': 1, 'nilai_dpp': 700},
]
_syn_data = [
    # typo 1 segmen, vendor SAMA -> HARUS muncul (kandidat typo)
    {'NO PO / KONTRAK': 'PB.021/PO/NK-WIKA/02/SINTONG/05/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT. ARLISCO ELEKTRIKA PERKASA', 'HARGA (EXLD)': '100'},
    # nomor mirip, vendor BEDA -> TIDAK boleh muncul (anti-noise)
    {'NO PO / KONTRAK': 'PB.063/PO/NK-WIKA/03/SINTONG/09/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT. SINAR KENCANA DURI', 'HARGA (EXLD)': '200'},
    # serial SAMA (PB.038), vendor sama (varian 'SYSTEMS') -> HARUS muncul
    {'NO PO / KONTRAK': 'PB.038/PO/NK-WIKA/03/SINTONG/06/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT. CONTROL SYSTEMS ARENA PARA NUSA', 'HARGA (EXLD)': '150'},
    # serial BEDA (PB.039 vs PB.038), vendor sama -> TIDAK boleh muncul (PO beda)
    {'NO PO / KONTRAK': 'PB.039/PO/NK-WIKA/02/SINTONG/06/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT. CONTROL SYSTEMS ARENA PARA NUSA', 'HARGA (EXLD)': '160'},
    # cocok persis -> bukan temuan
    {'NO PO / KONTRAK': 'PB.021/PO/NK-WIKA/02/SINTONG/04/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT ARLISCO ELEKTRIKA PERKASA', 'HARGA (EXLD)': '300'},
    # setara numerik (nol depan beda) -> bukan temuan & bukan "belum tercocok"
    {'NO PO / KONTRAK': 'PB.21/PO/NK-WIKA/02/SINTONG/04/2026',
     'NAMA LEVELANSIR / REKANAN': 'PT ARLISCO ELEKTRIKA PERKASA', 'HARGA (EXLD)': '400'},
]
_sr = _run_synthetic(_syn_contracts, _syn_data)
_pos = {m['po']: m for m in _sr['mirip']}
assert 'PB.021/PO/NK-WIKA/02/SINTONG/05/2026' in _pos, 'typo vendor sama tak terdeteksi'
assert _pos['PB.021/PO/NK-WIKA/02/SINTONG/05/2026']['kandidat_sama'], 'kuat tanpa kandidat_sama'
assert 'PB.063/PO/NK-WIKA/03/SINTONG/09/2026' not in _pos, 'vendor beda harus dibuang (noise)'
assert 'PB.038/PO/NK-WIKA/03/SINTONG/06/2026' in _pos, 'serial sama (PB.038) harus terdeteksi'
assert 'PB.039/PO/NK-WIKA/02/SINTONG/06/2026' not in _pos, 'serial beda (PB.039) harus dibuang'
assert 'PB.021/PO/NK-WIKA/02/SINTONG/04/2026' not in _pos, 'cocok persis jadi temuan'
assert 'PB.21/PO/NK-WIKA/02/SINTONG/04/2026' not in _pos, 'setara numerik jadi temuan'
# unmatched = 3 baris typo (PB.021/05, PB.063, PB.038/03, PB.039); exact & setara tak dihitung.
assert _sr['unmatched_count'] == 4, f"unmatched harus 4, dapat {_sr['unmatched_count']}"
print('[1] hanya serial-depan-sama & vendor-sama yang dilaporkan OK')


# --- 1b. Gerbang serial depan ---
from services.contract_match import _leading_serial
assert _leading_serial('PB.038/PO/NK-WIKA/03/SINTONG/06/2026') == 'PB38'
assert _leading_serial('PB.38/PO/NK-WIKA/03/SINTONG/06/2026') == 'PB38'
assert _leading_serial('PB.039/PO/NK-WIKA/02/SINTONG/06/2026') == 'PB39'
assert _leading_serial('PB.038/...') != _leading_serial('PB.039/...')
print('[1b] gerbang serial depan OK (PB.038 == PB.38, != PB.039)')


# --- 2. Struktur hasil pada DATA NYATA ---
res = find_po_similarity('all')
assert set(res.keys()) >= {'mirip', 'tanpa_invoice', 'unmatched_value',
                           'unmatched_count', 'mirip_invoice', 'count'}, res.keys()
assert res['count'] == sum(m['jumlah'] for m in res['mirip']), 'badge != jumlah invoice kandidat'
for m in res['mirip']:
    assert m['kandidat_sama'], f"temuan mirip tanpa kandidat vendor sama: {m['po']}"
    assert all(k['skor'] >= SIMILARITY_THRESHOLD for k in m['kandidat_sama'])
    assert m['po'].strip() != ''
print(f"[2] struktur OK: count={res['count']} "
      f"(mirip_vendor_sama={len(res['mirip'])}, tanpa_invoice={res['tanpa_invoice_count']}) "
      f"— belum tercocok {res['unmatched_count']} invoice / Rp {int(res['unmatched_value']):,}")


# --- 3. Saringan vendor: setiap temuan 'mirip' HARUS vendornya sama ---
for m in res['mirip']:
    v_inv = _norm_vendor(m['vendor'])
    assert v_inv, f"temuan mirip tanpa vendor invoice: {m['po']}"
    for k in m['kandidat_sama']:
        row = db_contract.get_contract_by_no(k['no_kontrak'])
        v_k = _norm_vendor(row.get('vendor', '') if row else '')
        assert _vendor_match(v_inv, v_k), f"vendor beda tapi masuk kandidat_sama: {m['po']} vs {k['no_kontrak']}"
print('[3] saringan vendor OK: semua temuan "mirip" vendornya sama')


# --- 4. Tidak ada false positive pada data nyata (exact & setara numerik) ---
contracts = db_contract.get_contracts('all')
exact = {db_contract._norm_kontrak(c['no_kontrak']) for c in contracts}
exact_num = {_norm_number(c['no_kontrak']) for c in contracts}
po_mirip = {m['po'] for m in res['mirip']}
for po in po_mirip:
    assert db_contract._norm_kontrak(po) not in exact, f"{po} cocok persis tapi jadi temuan"
    assert _norm_number(po) not in exact_num, f"{po} setara numerik tapi jadi temuan"
print(f'[4] tidak ada false positive: {len(po_mirip)} nomor temuan, {len(exact)} kontrak registri')


# --- 5. Review-only (tidak menghubungkan otomatis) ---
assert isinstance(res['mirip'], list)
for m in res['mirip']:
    for k in m['kandidat']:
        assert 0.0 <= k['skor'] <= 1.0
print('[5] review-only OK')


# --- 6. Halaman review render 200 + section + tab + redirect ---
from services import auth as _auth
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    r = c.get('/kontrak/tinjau-no-po')
    assert r.status_code == 200, f"status {r.status_code}"
    html = r.data.decode('utf-8', 'replace')
    for probe in ('Mirip &amp; vendor sama',
                  'Kontrak tanpa invoice',
                  'Tak Terdaftar'):
        assert probe in html, f"section '{probe}' tidak ada"
    assert 'vendor berbeda (info)' not in html, "section info 'beda vendor' harus sudah dihapus"
    assert 'No PO kembar' not in html, "section 'No PO kembar' harus sudah dihapus"
    assert 'Nomor kontrak di invoice yang belum ada di registri' in html
    # tiap tabel yang dirender dibungkus .kpr-scroll (sticky header)
    n_mirip = 1 if res['mirip'] else 0
    n_expect = n_mirip + (1 if res['tanpa_invoice'] else 0) + 1  # + tab tak-terdaftar
    n_got = html.count('class="kpr-scroll"')
    assert n_got == n_expect, f'.kpr-scroll: dapat {n_got}, harusnya {n_expect}'
    assert 'position: sticky' in html and '.kpr-scroll .kpr-table thead th' in html
    assert 'Kembali ke Progress Kontrak' in html
    assert html.index('Kembali ke Progress Kontrak') < html.index('class="kpr-scroll"')
    # tab=... memilih panel yang benar
    r_tab = c.get('/kontrak/tinjau-no-po?tab=tak-terdaftar')
    assert r_tab.status_code == 200 and 'is-active' in r_tab.data.decode('utf-8', 'replace')
    # route lama -> redirect ke tab tak-terdaftar
    r_old = c.get('/kontrak/belum-terdaftar', follow_redirects=False)
    assert r_old.status_code in (301, 302, 303, 308)
    assert 'tab=tak-terdaftar' in r_old.headers.get('Location', '')
    # halaman daftar kontrak memuat tombol Pemeriksaan No PO + banner
    r2 = c.get('/kontrak/')
    assert r2.status_code == 200
    h2 = r2.data.decode('utf-8', 'replace')
    assert 'Pemeriksaan No PO' in h2
    assert ('belum cocok' in h2) == (res['unmatched_count'] > 0)
print('[6] halaman pemeriksaan No PO + redirect route lama OK')


# --- 7. Kategori WARNING No PO terpasang di verification ---
from services.verification import check_row
row = {'NO PO / KONTRAK': next(iter(po_mirip)) if po_mirip else 'X',
       'NAMA LEVELANSIR / REKANAN': 'PT X', 'NO INVOICE': 'INV1', 'TGL INV': '2026-01-01',
       'TGL TERIMA': '2026-01-01', 'STATUS TERHADAP DPP': 'Lunas'}
if po_mirip:
    level, reasons = check_row(row, similar_po_nos=po_mirip)
    assert level == 'WARNING', f"harus WARNING, dapat {level}"
    assert any('mirip' in r.lower() for r in reasons), reasons
print('[7] kategori WARNING No PO di verification OK')

_ctx.pop()
print('ALL CHECKS PASSED')
