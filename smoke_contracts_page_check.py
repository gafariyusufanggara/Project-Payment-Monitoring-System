# -*- coding: utf-8 -*-
"""Smoke check: halaman Progress Kontrak (templates/contracts.html).

Memverifikasi bahwa angka KPI = jumlah kolom tabel, kolom "Sisa Tagihan"
dibulatkan (floating point kecil dianggap 0), kolom "Bayar DPP (%)"
memakai basis fallback yang sama dengan kolom "DPP Kontrak", label
kolom tidak lagi bentrok dengan KPI, dan urutan kolom (blok DPP, blok
PPN, Sisa Tagihan di akhir).

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
        'sisa_tagihan': sisa, 'sisa_tagihan_ppn': sisa,
        'progres': 0.0, 'progres_ppn': 0.0, 'over': False, 'over_ppn': False,
        'status_invoice': 'Ada Invoice', 'jumlah_invoice': 2, 'total_dpp': 100.0,
        'project_id': '', 'ppn_rate': 11.0,
    }
    summ = {'total_kontrak': 1, 'total_dpp': 100.0, 'total_ppn': 11.0,
            'total_tertagih': 100 - sisa, 'total_tertagih_ppn': 11 - sisa,
            'total_sisa': sisa, 'total_dibayar': 0.0, 'total_dibayar_ppn': 0.0,
            'total_sisa_dpp': sisa, 'total_sisa_ppn': sisa, 'belum_lunas': 0,
            'total_belum_ditagih': sisa, 'total_belum_ditagih_ppn': sisa,
            'total_belum_dibayar': 0.0, 'total_belum_dibayar_ppn': 0.0,
            'jatuh_tempo': 0, 'belum_invoice': 0}
    with app.test_request_context('/'):
        html = render_template('contracts.html', contracts=[c], summary=summ,
                               project_labels={}, project_list=[])
    # Ambil hanya sel "Sisa Tagih" (satu-satunya cell-money yg membawa kelas warna
    # text-success/text-danger dan bukan kc-owe-only).
    td = re.search(r'<td class="cell-money kc-sisa(?: kc-owe)? (text-(?:success|danger))"[^>]*>([^<]*)</td>', html)
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
print('[3] pembulatan & warna Sisa Tagihan OK')


# --- 4. Label kolom tidak bentrok dg KPI ---
with app.test_request_context('/'):
    html = render_template('contracts.html', contracts=contracts, summary=summary,
                           project_labels={}, project_list=[])
assert 'Sisa Tagihan (DPP)' in html and 'Sisa Tagihan (PPN)' in html, \
    "label 'Sisa Tagihan' tidak ditemukan"
assert 'Belum Ditagih (DPP)' not in html, "label lama 'Belum Ditagih' masih ada"
assert 'Sisa Tagih (' not in html, "label lama 'Sisa Tagih' masih ada"
print('[4] label kolom OK (Sisa Tagihan, bukan Belum Ditagih)')

# --- 4b. Urutan kolom: blok DPP, blok PPN, sisa di akhir ---
_hdr = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', th)).strip() for th in
        re.findall(r'<th[^>]*>(.*?)</th>', html, re.S)]
_hdr = [_h for _h in _hdr if _h][:15]
_expected = ['No.', 'Vendor / Rekanan', 'Item Pekerjaan',
             'DPP Kontrak', 'Tagihan DPP', 'Bayar DPP (Rp)', 'Bayar DPP (%)',
             'PPN Kontrak', 'Tagihan PPN', 'Bayar PPN (Rp)', 'Bayar PPN (%)',
             'Metode Bayar',
             'Sisa Tagihan (DPP)', 'Sisa Tagihan (PPN)', 'Stat. Invoice']
assert _hdr == _expected, f'urutan kolom salah:\n{_hdr}\n!=\n{_expected}'
print('[4b] urutan kolom OK: DPP -> PPN, Sisa Tagihan di akhir')

# --- 4c. Filter Metode Bayar (setelah filter Status) ---
assert 'id="filterMetode"' in html, 'select filterMetode tidak ada'
assert html.index('id="filterStatus"') < html.index('id="filterMetode"'), \
    'filter Metode Bayar harus setelah filter Status'
_opts = re.findall(r'<option value="([^"]*)">([^<]*)</option>',
                   re.search(r'id="filterMetode".*?</select>', html, re.S).group(0))
assert ('', 'Semua Metode Bayar') in _opts, 'opsi default filter Metode Bayar tidak ada'
_metode_vals = {m['metode_pembayaran'] for m in contracts if m['metode_pembayaran']}
assert _metode_vals == {v for v, _ in _opts if v not in ('', '-')}, \
    f'opsi metode tidak sesuai data: {_opts}'
assert len(re.findall(r'data-metode="', html)) == len(contracts), \
    'setiap baris harus punya data-metode'
assert "getElementById('filterMetode')" in html, 'listener filter Metode Bayar tidak terpasang'
print('[4c] filter Metode Bayar OK:', [lbl for _, lbl in _opts])


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


# --- 7. Detail kontrak: No. Invoice & Deskripsi bisa diklik (cell-expand) ---
_client = app.test_client()
with _client.session_transaction() as _sess:
    _sess['authed'] = True
_cid, _invs = None, []
for _c in contracts:
    _rows_inv = db_contract.get_contract_invoices(_c['no_kontrak'])
    if _rows_inv:
        _cid, _invs = _c['id'], _rows_inv
        break
assert _cid, 'tidak ada kontrak dengan invoice untuk uji detail'
_det = _client.get(f'/kontrak/{_cid}')
assert _det.status_code == 200, f'detail kontrak HTTP {_det.status_code}'
_det_html = _det.get_data(as_text=True)
assert _det_html.count('class="cell-desc" data-full=') == len(_invs), \
    'setiap sel Deskripsi harus punya data-full'
assert 'class="cell-desc" title=' not in _det_html, \
    'title pada sel Deskripsi harus dihapus (satu mekanisme: klik)'
assert _det_html.count('class="cell-desc cell-invno" data-full=') == len(_invs), \
    'setiap sel No. Invoice harus terpotong + punya data-full (bisa diklik)'
assert '.kd-table [data-full].cx-on { cursor: pointer; }' in _det_html, \
    'CSS affordance klik (.cx-on) tak ada di halaman detail'
assert (_det_html.index('<th>Tgl Berkas Lengkap</th>')
        < _det_html.index('<th>Tgl Jatuh Tempo</th>')
        < _det_html.index('<th>Deskripsi</th>')), \
    'kolom Tgl Jatuh Tempo harus setelah Tgl Berkas Lengkap'
assert all((_i['jth_tempo'] or '-') in _det_html for _i in _invs), \
    'nilai Tgl Jatuh Tempo invoice tidak ter-render'
print(f'[7] detail kontrak: {len(_invs)} invoice, No. Invoice + Deskripsi clickable, '
      f'Tgl Jatuh Tempo OK')


# --- 8. Detail kontrak: KPI Sisa Tagihan = Nilai Kontrak - Terbayar ---
_det2 = _client.get(f'/kontrak/{_cid}').get_data(as_text=True)
assert 'Sisa Tagihan (DPP)' in _det2 and 'Sisa Tagihan (PPN)' in _det2, \
    'label Sisa Tagihan (DPP/PPN) tidak ditemukan di detail'
assert 'Sisa Hutang Kontrak' not in _det2, \
    'label lama Sisa Hutang Kontrak masih ada di detail'
_cd = db_contract.get_contract(_cid)
_money_f = appmod.app.jinja_env.filters['money']
_kpi = dict(re.findall(
    r'Sisa Tagihan \((DPP|PPN)\)</div><div class="ds-kpi__value">([^<]+)</div>',
    _det2))
assert _kpi, 'nilai KPI Sisa Tagihan tak terbaca dari HTML'
for _tax, _nilai, _bayar in (('DPP', _cd['nilai_dpp'], _cd['dibayar']),
                             ('PPN', _cd['nilai_ppn'], _cd['dibayar_ppn'])):
    _expect = _money_f((_nilai or 0) - (_bayar or 0))
    assert _kpi.get(_tax) == _expect, \
        f'Sisa Tagihan {_tax} = {_kpi.get(_tax)} != nilai-dibayar {_expect}'
print(f'[8] KPI Sisa Tagihan OK: DPP {_kpi["DPP"]}, PPN {_kpi["PPN"]}')

# --- 9. Daftar kontrak: KPI Sisa Tagihan = Σ kolom Sisa Tagihan ---
# Definisi: bagian kontrak yang belum dibayar (Nilai Kontrak - Terbayar),
# termasuk yang belum ditagih. KPI harus sama persis dengan jumlah kolom.
_sum_dpp = sum(c['nilai_dpp'] - c['dibayar'] for c in contracts)
_sum_ppn = sum(c['nilai_ppn'] - c['dibayar_ppn'] for c in contracts)
assert abs(summary['total_sisa_dpp'] - _sum_dpp) < 0.5, \
    f"KPI Sisa Tagihan DPP {summary['total_sisa_dpp']:,.0f} != Σ kolom {_sum_dpp:,.0f}"
assert abs(summary['total_sisa_ppn'] - _sum_ppn) < 0.5, \
    f"KPI Sisa Tagihan PPN {summary['total_sisa_ppn']:,.0f} != Σ kolom {_sum_ppn:,.0f}"
assert abs(summary['total_belum_ditagih'] + summary['total_belum_dibayar']
           - summary['total_sisa_dpp']) < 0.5, \
    'rincian hint DPP (belum ditagih + belum dibayar) != KPI Sisa Tagihan DPP'
assert abs(summary['total_belum_ditagih_ppn'] + summary['total_belum_dibayar_ppn']
           - summary['total_sisa_ppn']) < 0.5, \
    'rincian hint PPN (belum ditagih + belum dibayar) != KPI Sisa Tagihan PPN'
for c in contracts:
    assert abs((c['nilai_dpp'] - c['dibayar']) - c['sisa_tagihan']) < 0.5, \
        f"{c['no_kontrak']}: sisa_tagihan != nilai_dpp - dibayar"
    assert abs((c['nilai_ppn'] - c['dibayar_ppn']) - c['sisa_tagihan_ppn']) < 0.5, \
        f"{c['no_kontrak']}: sisa_tagihan_ppn != nilai_ppn - dibayar_ppn"
with app.test_request_context('/'):
    _html9 = render_template('contracts.html', contracts=contracts, summary=summary,
                             project_labels={}, project_list=[])
assert 'Sisa Tagihan (DPP)</div>' in _html9 and 'Sisa Tagihan (PPN)</div>' in _html9, \
    'label KPI Sisa Tagihan (DPP/PPN) tidak ditemukan'
assert 'Sisa Hutang DPP</div>' not in _html9, 'label lama Sisa Hutang DPP masih ada'
_money9 = appmod.app.jinja_env.filters['money']
for _lbl, _val in (('DPP', summary['total_sisa_dpp']),
                   ('PPN', summary['total_sisa_ppn'])):
    assert f'Sisa Tagihan ({_lbl})</div><div class="ds-kpi__value">{_money9(_val)}</div>' \
        in _html9, f'nilai KPI Sisa Tagihan {_lbl} tidak sesuai summary'
print(f'[9] KPI Sisa Tagihan = jumlah kolom OK: DPP {_sum_dpp:,.0f}, PPN {_sum_ppn:,.0f}')

# --- 10. Kolom Bayar DPP/PPN (Rp): merah hanya bila nominal > 0 ---
_paid_red = _html9.count('class="cell-money text-danger" style="font-weight:700"')
_paid_expected = (sum(1 for c in contracts if (c['dibayar'] or 0) > 1.0)
                  + sum(1 for c in contracts if (c['dibayar_ppn'] or 0) > 1.0))
assert _paid_red == _paid_expected, \
    f'highlight Bayar DPP/PPN salah: {_paid_red} != {_paid_expected} (hanya nominal > 0)'
_zero_rows = [c for c in contracts if not (c['dibayar'] or 0) > 1.0]
assert _zero_rows, 'data uji tidak punya baris bayar DPP = 0'
print(f'[10] Bayar DPP/PPN merah hanya bila > 0 OK: {_paid_red} sel '
      f'({len(_zero_rows)} baris bayar 0 tanpa highlight)')


print('ALL CHECKS PASSED')
