# -*- coding: utf-8 -*-
"""Smoke check: halaman Progress Kontrak (templates/contracts.html).

Memverifikasi bahwa angka KPI = jumlah kolom tabel, kolom "Sisa Tagih"
dibulatkan (floating point kecil dianggap 0), kolom "Terbayar DPP (%)"
memakai basis fallback yang sama dengan kolom "DPP Kontrak", dan label
kolom tidak lagi bentrok dengan KPI.

Run:  python smoke_contracts_page_check.py
Read-only terhadap data nyata.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
import db_contract
from constants import safe_float
from flask import render_template

app = appmod.app

EPS = 1.0  # toleransi pembulatan Rp 1 (harus sama dengan {% set eps %} di template)

contracts = db_contract.get_contracts('all')
summary = db_contract.get_summary('all')


# --- 1. KPI = jumlah kolom (basis fallback yang sama) ---
sum_dpp = sum(safe_float(c['nilai_dpp']) for c in contracts)
sum_ppn = sum(safe_float(c['nilai_ppn']) for c in contracts)
assert abs(sum_dpp - summary['total_dpp']) < 0.5, \
    f"KPI DPP {summary['total_dpp']:,.0f} != Σ kolom {sum_dpp:,.0f}"
assert abs(sum_ppn - summary['total_ppn']) < 0.5, \
    f"KPI PPN {summary['total_ppn']:,.0f} != Σ kolom {sum_ppn:,.0f}"
print(f'[1] KPI vs kolom OK: DPP {sum_dpp:,.0f}, PPN {sum_ppn:,.0f}, '
      f'{len(contracts)} kontrak')


# --- 2. Kontrak dg Total DPP kosong tetap punya bar progres (basis fallback) ---
fallback = [c for c in contracts
            if safe_float(c.get('total_dpp')) == 0 and safe_float(c.get('nilai_dpp')) > 0]
for c in fallback:
    with app.test_request_context('/'):
        html = render_template('contracts.html', contracts=[c],
                               summary=db_contract.get_summary('all'),
                               project_labels={}, project_list=[])
    assert 'DPP Kontrak belum diisi.' not in html, \
        f"{c['no_kontrak']}: DPP kosong tapi nilai_dpp ada -> bar harus muncul"
print(f'[2] fallback DPP OK: {len(fallback)} kontrak dg Total DPP kosong')


# --- 3. Pembulatan "Sisa Tagih": FP noise & over-tagih ---
def render_sisa(sisa):
    """Return (class_table, text) untuk sel sisa DPP/PPN dg nilai tertentu."""
    c = {
        'id': 1, 'no_kontrak': 'T/1', 'vendor': 'PT X', 'item_pekerjaan': 'Y',
        'nilai_dpp': 100.0, 'nilai_ppn': 11.0,
        'tertagih': 100.0 - sisa, 'tertagih_ppn': 11.0 - sisa,
        'sisa_kontrak': sisa, 'sisa_ppn': sisa, 'dibayar': 0.0, 'dibayar_ppn': 0.0,
        'progres': 0.0, 'progres_ppn': 0.0, 'over': False, 'over_ppn': False,
        'status_invoice': 'Ada Invoice', 'jumlah_invoice': 2, 'total_dpp': 100.0,
        'project_id': '', 'ppn_rate': 11.0,
    }
    summ = {'total_kontrak': 1, 'total_dpp': 100.0, 'total_ppn': 11.0,
            'total_tertagih': 100 - sisa, 'total_tertagih_ppn': 11 - sisa,
            'total_sisa': sisa, 'total_dibayar': 0.0, 'total_dibayar_ppn': 0.0,
            'total_sisa_dpp': 0.0, 'total_sisa_ppn': 0.0, 'belum_lunas': 0,
            'jatuh_tempo': 0, 'belum_invoice': 0}
    with app.test_request_context('/'):
        html = render_template('contracts.html', contracts=[c], summary=summ,
                               project_labels={}, project_list=[])
    # Ambil hanya sel "Sisa Tagih" (satu-satunya cell-money yg membawa kelas warna
    # text-success/text-danger dan bukan kc-owe-only).
    td = re.search(r'<td class="cell-money (?:kc-owe )?(text-(?:success|danger))"[^>]*>([^<]*)</td>', html)
    return td.group(1), td.group(2)

cls, txt = render_sisa(-1e-9)
assert txt == '0', f"FP noise -1e-9 harus dibulatkan jadi 0, dapat '{txt}'"
assert 'text-danger' not in cls, "FP noise tidak boleh merah"
assert 'text-success' in cls, "FP noise (dianggap 0) harus hijau"

cls, txt = render_sisa(-0.4)
assert txt == '0' and 'text-success' in cls, "sub-Rp1 harus dibulatkan jadi 0 (hijau)"

cls, txt = render_sisa(0)
assert txt == '0' and 'text-success' in cls, "sisa 0 harus hijau"

cls, txt = render_sisa(-50)
assert txt == '-50' and 'text-danger' in cls, "over-tagih nyata harus merah & negatif"

cls, txt = render_sisa(50)
assert txt == '50' and 'text-danger' in cls, "ada sisa harus merah"
print('[3] pembulatan & warna Sisa Tagih OK')


# --- 4. Label kolom tidak bentrok dg KPI ---
with app.test_request_context('/'):
    html = render_template('contracts.html', contracts=contracts, summary=summary,
                           project_labels={}, project_list=[])
assert 'Sisa Tagih (DPP)' in html and 'Sisa Tagih (PPN)' in html, \
    "label 'Sisa Tagih' tidak ditemukan"
assert 'Belum Ditagih (DPP)' not in html, "label lama 'Belum Ditagih' masih ada"
print('[4] label kolom OK (Sisa Tagih, bukan Belum Ditagih)')


# --- 5. Badge ikon (tanda seru) di menu sidebar "Progress Kontrak" ---
# Harus muncul di halaman mana pun (sidebar global), TANPA angka.
from services import auth as authmod  # noqa: E402

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'templates', 'base.html'), encoding='utf-8') as f:
    base_src = f.read()
assert 'id="navProgressKontrak"' in base_src, "menu Progress Kontrak tak punya id"
assert 'nav-badge-icon' in base_src, "badge ikon Progress Kontrak tak ada di base.html"
assert 'bi-exclamation' in base_src, \
    "ikon tanda seru (bi-exclamation) tak ada di menu Progress Kontrak"
# Badge ikon tak boleh menampilkan angka sebagai TEKS tampil: hanya ikon di
# dalam span badge. (po_review_count boleh muncul di atribut title tooltip.)
import re as _re  # noqa: E402
_badge = _re.search(r'<span class="nav-badge[^"]*nav-badge-icon"[^>]*>(.*?)</span>',
                    base_src, _re.S)
assert _badge, "span badge ikon Progress Kontrak tak ditemukan di base.html"
_inner = _badge.group(1)
assert 'bi-exclamation' in _inner, "badge harus berisi ikon tanda seru"
assert '{{ po_review_count }}' not in _inner, \
    "isi badge Progress Kontrak harus IKON saja (tanpa angka tampil)"
# CSS .nav-badge-icon tersedia.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'static', 'css', 'base.css'), encoding='utf-8') as f:
    base_css = f.read()
assert '.nav-badge-icon' in base_css, "CSS .nav-badge-icon tak ada di base.css"

# Render nyata: badge harus ikut muncul di halaman non-kontrak (sidebar global).
client = app.test_client()
with client.session_transaction() as s:
    s[authmod.SESSION_KEY] = True
page = client.get('/dashboard').get_data(as_text=True)
assert 'id="navProgressKontrak"' in page, "menu Progress Kontrak tak render di /dashboard"
from services.contract_match import count_cached  # noqa: E402
_count = count_cached(None)
if _count > 0:
    assert 'nav-badge-icon' in page, \
        f"po_review_count={_count}>0 tapi badge ikon tak muncul di sidebar"
    _rb = re.search(r'<span class="nav-badge[^"]*nav-badge-icon"[^>]*>(.*?)</span>', page, re.S)
    assert _rb and 'bi-exclamation' in _rb.group(1), \
        "badge ikon harus berisi ikon tanda seru (bukan angka)"
    print(f'[5] badge ikon Progress Kontrak OK (po_review_count={_count}, tanpa angka)')
else:
    print(f'[5] badge ikon Progress Kontrak OK (po_review_count=0 -> badge tersembunyi)')


# --- 6. Keterangan "kandidat typo" di halaman Progress Kontrak ---
# Banner harus muncul saat ada temuan (po_review_count>0) dan menjelaskan
# "Mirip & vendor sama — kandidat typo", serupa halaman Pemeriksaan No PO.
_kc_page = client.get('/kontrak/').get_data(as_text=True)
assert '.kc-typo-banner' in base_src or '.kc-typo-banner' in _kc_page, \
    "CSS .kc-typo-banner tak ada (keterangan kandidat typo)"
if _count > 0:
    _banner = re.search(r'<div class="kc-typo-banner">.*?</div>', _kc_page, re.S)
    assert _banner, "banner keterangan kandidat typo tak render saat ada temuan"
    _btext = _banner.group(0)
    assert 'kandidat typo' in _btext, "banner harus memuat frasa 'kandidat typo'"
    assert 'mirip' in _btext and 'vendor sama' in _btext, \
        "banner harus menjelaskan 'Mirip & vendor sama'"
    assert 'Pemeriksaan No PO' in _btext, \
        "banner sebaiknya memuat tautan ke Pemeriksaan No PO"
    print(f'[6] keterangan kandidat typo OK ({_count} invoice, banner tampil)')
else:
    # Tanpa temuan: banner boleh tidak tampil, tapi CSS tetap harus tersedia.
    assert '.kc-typo-banner' in _kc_page, "CSS .kc-typo-banner tak tersedia di halaman"
    print('[6] keterangan kandidat typo OK (po_review_count=0 -> banner tersembunyi)')

print('ALL CHECKS PASSED')
