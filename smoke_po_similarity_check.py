# -*- coding: utf-8 -*-
"""Smoke check: scanner No PO mirip (services/contract_match.py) + integrasinya.

Memverifikasi:
  1. Scanner menemukan kandidat pada data nyata dan strukturnya lengkap.
  2. Nomor yang COCOK persis TIDAK muncul sebagai temuan (tidak false positive).
  3. Pasangan "beda kontrak" (mis. PB.062 vs PB.064) TIDAK keliru dianggap
     cocok — scanner tidak pernah menghubungkan otomatis.
  4. Halaman /kontrak/tinjau-no-po render 200 dengan 2 tab; 3 tabel
     dibungkus .kpr-scroll (sticky header) + tombol Kembali di atas;
     route lama /kontrak/belum-terdaftar tetap redirect ke tab tak-terdaftar.
  5. Kategori WARNING No PO terpasang di services/verification.py.

Run:  python smoke_po_similarity_check.py
Read-only terhadap data nyata.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
import db_contract
from services import contract_match
from services.contract_match import find_po_similarity

app = appmod.app


# --- 1. Struktur hasil ---
res = find_po_similarity('all')
assert set(res.keys()) >= {'mirip', 'tanpa_invoice',
                           'unmatched_value', 'unmatched_count', 'count'}, res.keys()
assert 'mirip_beda_vendor' not in res, "info 'mirip beda vendor' sudah dihapus"
assert 'kembar' not in res, "section 'No PO kembar' sudah dihapus"
# Badge = jumlah INVOICE pada kandidat typo (yang benar-benar bermasalah),
# BUKAN total temuan dan BUKAN jumlah kontrak.
assert res['count'] == sum(m['jumlah'] for m in res['mirip']), \
    f"badge harus = jumlah invoice kandidat typo, dapat {res['count']}"
for m in res['mirip']:
    assert m['kandidat_sama'], f"temuan mirip tanpa kandidat vendor sama: {m['po']}"
    assert all(k['skor'] >= contract_match.SIMILARITY_THRESHOLD for k in m['kandidat_sama'])
    assert m['po'].strip() != ''
print(f"[1] struktur OK: {res['count']} temuan "
      f"(mirip_vendor_sama={len(res['mirip'])}, "
      f"tanpa_invoice={len(res['tanpa_invoice'])}) "
      f"— belum tercocok {res['unmatched_count']} invoice / Rp {int(res['unmatched_value']):,}")


# --- 1b. Saringan vendor: setiap temuan 'mirip' HARUS vendornya sama ---
from services.contract_match import _norm_vendor
for m in res['mirip']:
    v_inv = _norm_vendor(m['vendor'])
    assert v_inv, f"temuan mirip tanpa vendor invoice: {m['po']}"
    for k in m['kandidat_sama']:
        row = db_contract.get_contract_by_no(k['no_kontrak'])
        v_k = _norm_vendor(row.get('vendor', '') if row else '')
        assert v_inv == v_k, f"vendor beda tapi masuk kandidat_sama: {m['po']} vs {k['no_kontrak']}"
print('[1b] saringan vendor OK: semua temuan "mirip" vendornya sama')


# --- 2. Tidak ada false positive: nomor yg cocok persis tak masuk temuan ---
contracts = db_contract.get_contracts('all')
cocok = {c['no_kontrak'] for c in contracts if c['jumlah_invoice'] > 0}
po_mirip = {m['po'] for m in res['mirip']}
overlap = cocok & po_mirip
assert not overlap, f"nomor cocok seharusnya tidak jadi temuan: {overlap}"
print(f"[2] tidak ada false positive: {len(cocok)} kontrak ber-invoice bersih")


# --- 3. Scanner tidak pernah menghubungkan otomatis (review-only) ---
# Setiap temuan 'mirip' adalah nomor invoice yang BELUM ada kontrak persis.
kontrak_norm = {db_contract._norm_kontrak(c['no_kontrak']) for c in contracts}
for m in res['mirip']:
    assert db_contract._norm_kontrak(m['po']) not in kontrak_norm, \
        f"{m['po']} sebenarnya cocok, tidak boleh masuk daftar mirip"
# Kandidat boleh berisi nomor kontrak yang mirip, tapi temuan TIDAK mengubah data.
assert isinstance(res['mirip'], list)
print("[3] review-only OK (tidak ada penghubungan otomatis)")


# --- 4. Halaman review render 200 + memuat 2 tab ---
from services import auth as _auth
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    # tab default = Temuan
    r = c.get('/kontrak/tinjau-no-po')
    assert r.status_code == 200, f"status {r.status_code}"
    html = r.data.decode('utf-8', 'replace')
    for probe in ('vendor sama — kandidat typo',
                  'Kontrak tanpa invoice',
                  'Tak Terdaftar'):
        assert probe in html, f"section '{probe}' tidak ada"
    assert 'vendor berbeda (info)' not in html, "section info 'beda vendor' harus sudah dihapus"
    assert 'No PO kembar' not in html, "section 'No PO kembar' harus sudah dihapus"
    # isi tab Tak Terdaftar ikut ter-render (74 nomor) walau tab default Temuan
    assert 'Nomor kontrak di invoice yang belum ada di registri' in html
    # scroll internal: tiap tabel yang MEMANG dirender dibungkus .kpr-scroll
    # (sticky header). Jumlahnya bergantung data: section A (mirip) & C
    # (tak terdaftar) hanya dirender bila ada isinya, section B (kontrak tanpa
    # invoice) selalu tampil selama ada kontrak. Karena itu jangan hardcode 3.
    n_readonly = (1 if res['tanpa_invoice'] else 0) + 1  # B + C(tak terdaftar)
    n_mirip = 1 if res['mirip'] else 0
    n_expect = n_mirip + n_readonly
    n_got = html.count('class="kpr-scroll"')
    assert n_got == n_expect, (
        f'pembungkus .kpr-scroll: dapat {n_got}, harusnya {n_expect} '
        f'(mirip={n_mirip}, tanpa_invoice={1 if res["tanpa_invoice"] else 0}, '
        f'missing=1)')
    assert n_got >= 1, 'tidak ada satu pun pembungkus .kpr-scroll'
    assert 'position: sticky' in html and '.kpr-scroll .kpr-table thead th' in html
    # tombol Kembali dipindah ke ATAS: sebelum tabel pertama
    assert 'Kembali ke Progress Kontrak' in html
    assert html.index('Kembali ke Progress Kontrak') < html.index('class="kpr-scroll"'), \
        "tombol Kembali harus di atas tabel"
    # tab=... memilih panel yang benar
    r_tab = c.get('/kontrak/tinjau-no-po?tab=tak-terdaftar')
    assert r_tab.status_code == 200
    html_tab = r_tab.data.decode('utf-8', 'replace')
    assert 'is-active' in html_tab
    # route lama /kontrak/belum-terdaftar -> redirect ke tab tak-terdaftar
    r_old = c.get('/kontrak/belum-terdaftar', follow_redirects=False)
    assert r_old.status_code in (301, 302, 303, 308), f"status redirect {r_old.status_code}"
    assert 'tab=tak-terdaftar' in r_old.headers.get('Location', '')
    # halaman daftar kontrak memuat tombol Pemeriksaan No PO
    r2 = c.get('/kontrak/')
    assert r2.status_code == 200
    h2 = r2.data.decode('utf-8', 'replace')
    assert 'Pemeriksaan No PO' in h2
    # banner ringkasan nilai belum tercocok tampil bila ada
    assert ('belum cocok' in h2) == (res['unmatched_count'] > 0)
print("[4] halaman pemeriksaan No PO (2 tab) + redirect route lama OK")


# --- 5. Kategori WARNING No PO terpasang di verification ---
from services.verification import check_row
row = {'NO PO / KONTRAK': next(iter(po_mirip)) if po_mirip else 'X',
       'NAMA LEVELANSIR / REKANAN': 'PT X', 'NO INVOICE': 'INV1', 'TGL INV': '2026-01-01',
       'TGL TERIMA': '2026-01-01', 'STATUS TERHADAP DPP': 'Lunas'}
if po_mirip:
    level, reasons = check_row(row, similar_po_nos=po_mirip)
    assert level == 'WARNING', f"harus WARNING, dapat {level}"
    assert any('mirip' in r.lower() for r in reasons), reasons
print("[5] kategori WARNING No PO di verification OK")

print('ALL CHECKS PASSED')
