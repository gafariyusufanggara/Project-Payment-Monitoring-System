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
import html as htmlmod
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
    """Return (class_sel, text) untuk sel "Sisa Hutang (DPP)" dg nilai tertentu.

    `sisa` = nilai utang (tagihan - bayar). Belum ditagih diset 0 supaya sel
    yang diuji hanya kolom Sisa Hutang.
    """
    c = {
        'id': 1, 'no_kontrak': 'T/1', 'vendor': 'PT X', 'item_pekerjaan': 'Y',
        'nilai_dpp': 100.0, 'nilai_ppn': 11.0,
        'tertagih': sisa, 'tertagih_ppn': sisa,
        'sisa_kontrak': 0.0, 'sisa_ppn': 0.0, 'dibayar': 0.0, 'dibayar_ppn': 0.0,
        'sisa_hutang': sisa, 'sisa_hutang_ppn': sisa,
        'sisa_tagihan': sisa, 'sisa_tagihan_ppn': sisa,
        'progres': 0.0, 'progres_ppn': 0.0, 'over': False, 'over_ppn': False,
        'status_invoice': 'Ada Invoice', 'jumlah_invoice': 2, 'total_dpp': 100.0,
        'project_id': '', 'ppn_rate': 11.0,
        # Pencocokan termin — pill dirender dari dict ini (bukan query ulang).
        'termin_cocok': db_contract.termin_progress(
            [{'nilai': 100.0, 'label': 'Termin 1', 'urutan_no': 1}], sisa),
    }
    summ = {'total_kontrak': 1, 'total_dpp': 100.0, 'total_ppn': 11.0,
            'total_tertagih': sisa, 'total_tertagih_ppn': sisa,
            'total_sisa': sisa, 'total_dibayar': 0.0, 'total_dibayar_ppn': 0.0,
            'total_sisa_dpp': sisa, 'total_sisa_ppn': sisa, 'belum_lunas': 0,
            'total_sisa_hutang': sisa, 'total_sisa_hutang_ppn': sisa,
            'total_belum_ditagih': 0.0, 'total_belum_ditagih_ppn': 0.0,
            'total_belum_dibayar': sisa, 'total_belum_dibayar_ppn': sisa,
            'jatuh_tempo': 0, 'belum_invoice': 0}
    with app.test_request_context('/'):
        html = render_template('contracts.html', contracts=[c], summary=summ,
                               project_labels={}, project_list=[])
    # Sel "Sisa Hutang (DPP)" = satu-satunya cell-money kc-sisa yang membawa
    # kelas warna text-success/text-danger.
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
assert txt == '-50' and 'text-danger' in cls, "sisa negatif nyata harus merah & negatif"

cls, txt = render_sisa(50)
assert txt == '50' and 'text-danger' in cls, "ada sisa hutang harus merah"
print('[3] pembulatan & warna Sisa Hutang OK')


# --- 3b. "Belum Ditagih" TIDAK boleh diberi warna peringatan ---
# Pekerjaan yang belum ditagih bukan utang; menandainya merah akan membuat
# angka besar (mis. 176 jt pada kontrak yang baru ditagih 20%) terbaca
# seolah tagihan menumpuk.
_c_belum = {
    'id': 2, 'no_kontrak': 'T/2', 'vendor': 'PT Y', 'item_pekerjaan': 'Z',
    'nilai_dpp': 220.0, 'nilai_ppn': 24.2, 'tertagih': 44.0, 'tertagih_ppn': 4.84,
    'dibayar': 0.0, 'dibayar_ppn': 0.0, 'sisa_hutang': 44.0, 'sisa_hutang_ppn': 4.84,
    'sisa_kontrak': 176.0, 'sisa_ppn': 19.36,
    'sisa_tagihan': 220.0, 'sisa_tagihan_ppn': 24.2,
    'progres': 0.0, 'progres_ppn': 0.0, 'over': False, 'over_ppn': False,
    'status_invoice': 'Ada Invoice', 'jumlah_invoice': 1, 'total_dpp': 220.0,
    'project_id': '', 'ppn_rate': 11.0,
    'termin_cocok': db_contract.termin_progress(
        [{'nilai': 44.0, 'label': 'Termin 1', 'urutan_no': 1},
         {'nilai': 176.0, 'label': 'Termin 2', 'urutan_no': 2}], 44.0),
}
_summ_belum = {'total_kontrak': 1, 'total_dpp': 220.0, 'total_ppn': 24.2,
               'total_tertagih': 44.0, 'total_tertagih_ppn': 4.84,
               'total_sisa': 44.0, 'total_dibayar': 0.0, 'total_dibayar_ppn': 0.0,
               'total_sisa_dpp': 220.0, 'total_sisa_ppn': 24.2, 'belum_lunas': 1,
               'total_sisa_hutang': 44.0, 'total_sisa_hutang_ppn': 4.84,
               'total_belum_ditagih': 176.0, 'total_belum_ditagih_ppn': 19.36,
               'total_belum_dibayar': 44.0, 'total_belum_dibayar_ppn': 4.84,
               'jatuh_tempo': 0, 'belum_invoice': 0}
with app.test_request_context('/'):
    _h_belum = render_template('contracts.html', contracts=[_c_belum],
                               summary=_summ_belum,
                               project_labels={}, project_list=[])
_belum_tds = re.findall(r'<td class="cell-money kc-belum[^"]*"[^>]*>([^<]*)</td>',
                        _h_belum)
assert _belum_tds, 'sel "Belum Ditagih" (kelas kc-belum) tidak ditemukan'
assert 'text-danger' not in _h_belum.split('kc-belum')[1][:120], \
    'sel Belum Ditagih tidak boleh merah (bukan utang)'
assert '.kc-page #kcTable tbody td.kc-belum { color: #667080; }' in _h_belum, \
    'CSS netral utk kc-belum (belum ditagih) tidak ada'
print(f'[3b] Belum Ditagih netral (bukan utang) OK: {_belum_tds[:2]}')


# --- 4. Label kolom: total tetap "Sisa Tagihan", pecahannya dua kolom ---
with app.test_request_context('/'):
    html = render_template('contracts.html', contracts=contracts, summary=summary,
                           project_labels={}, project_list=[])
assert 'Sisa Tagihan (DPP)' in html and 'Sisa Tagihan (PPN)' in html, \
    "label KPI 'Sisa Tagihan' tidak ditemukan"
# "Belum Ditagih" dan "Sisa Hutang" kini kolom tersendiri (dipisah dari total).
assert 'Belum Ditagih (DPP)' in html and 'Sisa Hutang (DPP)' in html, \
    "kolom 'Belum Ditagih (DPP)' / 'Sisa Hutang (DPP)' tidak ditemukan"
assert 'Sisa Tagih (' not in html, "label lama 'Sisa Tagih' masih ada"
print('[4] label kolom OK: Sisa Tagihan (total) + Belum Ditagih/Sisa Hutang (rincian)')

# --- 4b. Urutan kolom: blok DPP, blok PPN, sisa di akhir ---
# Header kini 2 baris (baris grup + baris label). Yang menentukan urutan
# kolom data adalah baris TERAKHIR; baris grup hanya penanda visual.
_thead = re.search(r'<thead>(.*?)</thead>', html, re.S).group(1)
_trows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', _thead, re.S)
_leaf_row = _trows[-1]
_hdr = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', th)).strip() for th in
        re.findall(r'<th[^>]*>(.*?)</th>', _leaf_row, re.S)]
_hdr = [_h for _h in _hdr if _h][:18]
_expected = ['No.', 'Vendor / Rekanan', 'Item Pekerjaan',
             'DPP Kontrak', 'Tagihan DPP', 'Bayar DPP (Rp)', 'Bayar DPP (%)',
             'PPN Kontrak', 'Tagihan PPN', 'Bayar PPN (Rp)', 'Bayar PPN (%)',
             'Metode Bayar',
             'Belum Ditagih (DPP)', 'Sisa Hutang (DPP)',
             'Belum Ditagih (PPN)', 'Sisa Hutang (PPN)',
             'Termin Ditagih', 'Invoice']
assert _hdr == _expected, f'urutan kolom salah:\n{_hdr}\n!=\n{_expected}'
print('[4b] urutan kolom OK: DPP -> PPN, Belum Ditagih + Sisa Hutang per pajak')

# --- 4b1. Baris grup kolom: label + rentang span harus menutup 18 kolom ---
_grow = _trows[0]
_gtxt = [htmlmod.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', th)).strip())
         for th in re.findall(r'<th[^>]*>(.*?)</th>', _grow, re.S)]
_gspans = [(int(a), int(b)) for a, b in
           re.findall(r'data-gstart="(\d+)"\s+data-gspan="(\d+)"', _grow)]
assert _gtxt == ['', 'Identitas', '', 'DPP', 'PPN', 'Sisa & Hutang', 'Status', ''], \
    f'label grup kolom salah: {_gtxt}'
assert [a for a, _ in _gspans] == [0, 1, 2, 3, 7, 12, 16, 17], \
    f'data-gstart grup salah: {_gspans}'
assert sum(b for _, b in _gspans) == 18, \
    f'total span grup {sum(b for _, b in _gspans)} != 18 kolom'
assert all(re.search(r'class="[^"]*kc-grp-(id|dpp|ppn|sisa|stat)', th)
           for th in re.findall(r'<th[^>]*data-gspan[^>]*>', _grow)), \
    'setiap sel grup harus punya kelas warna kc-grp-*'
print('[4b1] grup kolom OK: Identitas | DPP | PPN | Sisa & Hutang | Status (18 kolom)')

# --- 4b2. Urut ALAMIAH menurut No. PO/Kontrak ---
# Regresi: ORDER BY teks membuat "PB.10" < "PB.9" dan "PB.100" < "PB.2",
# sehingga nomor 01 tidak dijamin di atas. Kini diurutkan numerik.
_key = db_contract._no_kontrak_sort_key

# (a) unit: nomor dipecah jadi (prefix, angka) - pad nol tidak berpengaruh.
_cases = ['PB.1/PO', 'PB.10/PO', 'PB.2/PO', 'PB.01/PO', 'PB.9/PO', 'PB.100/PO']
_nums = [k[2] for k in map(_key, sorted(_cases, key=_key))]
assert _nums == [1, 1, 2, 9, 10, 100], \
    f'natural sort salah: {sorted(_cases, key=_key)} -> {_nums}'
assert _key('PB.001/KONTRAK/NK-WIKA/03/08/2025')[2] == 1, \
    'nomor diambil dari segmen pertama (sebelum "/") - PB.001 harus 1'

# (b) tanpa angka -> SELALU di bawah nomor berangka (elemen pertama 1).
assert _key('TANPA-NOMOR')[0] == 1 and _key('')[0] == 1, \
    'kontrak tanpa angka harus dapat penanda urutan 1 (paling bawah)'
assert _key('PB.001/PO')[0] == 0, 'kontrak berangka harus dapat penanda urutan 0'

# (c) data nyata: get_contracts() sudah terurut menaik & elemen pertama
#     adalah nomor terkecil.
_keys = [_key(c['no_kontrak']) for c in contracts]
assert _keys == sorted(_keys), 'get_contracts() tidak urut menurut No. PO'
if contracts:
    _min = min(_key(c['no_kontrak'])[2] for c in contracts)
    assert _key(contracts[0]['no_kontrak'])[2] == _min, \
        (f'kontrak pertama {contracts[0]["no_kontrak"]!r} bukan nomor terkecil '
         f'({_min})')

# (d) urutan baris di HTML == urutan get_contracts().
_html_nos = re.findall(r'data-no-kontrak="([^"]*)"', html)
if _html_nos:
    assert _html_nos == [c['no_kontrak'] for c in contracts], \
        'urutan baris <tbody> tidak sama dengan get_contracts()'
print(f'[4b2] urut No. PO alami OK ({len(contracts)} kontrak, '
      f'pertama: {contracts[0]["no_kontrak"] if contracts else "-"})')

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
def _dmy(_v):
    _p = str(_v or '').split('-')
    return f'{_p[2]}-{_p[1]}-{_p[0]}' if len(_p) == 3 and all(_p) else '-'
assert all(_dmy(_i['jth_tempo']) in _det_html for _i in _invs), \
    'nilai Tgl Jatuh Tempo invoice tidak ter-render dalam format DD-MM-YYYY'
print(f'[7] detail kontrak: {len(_invs)} invoice, No. Invoice + Deskripsi clickable, '
      f'Tgl Jatuh Tempo OK')


# --- 7b. Kolom Retensi pada tabel invoice (tepat setelah Pot. PPH) ---
# Sumber: kolom asli "POT. RETENSI" pada tabel hutang, diteruskan sebagai
# inv['pot_retensi'] oleh get_contract_invoices().
_seg = _det_html[_det_html.index('Invoice dengan No. Kontrak Ini'):]
_seg = _seg[:_seg.index('</section>')]
_th = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', t)).strip()
       for t in re.findall(r'<th[^>]*>(.*?)</th>',
                           re.search(r'<thead>(.*?)</thead>', _seg, re.S).group(1),
                           re.S)]
assert 'Retensi' in _th, f'kolom Retensi tidak ada pada tabel invoice: {_th}'
assert _th[_th.index('Pot. PPH') + 1] == 'Retensi', \
    f'Retensi harus TEPAT setelah Pot. PPH, urutan: {_th}'
assert len(_th) == 14, f'jumlah kolom tabel invoice: {len(_th)}, harusnya 14'
assert _th[_th.index('Bayar DPP') + 1] == 'Tgl Bayar DPP', \
    f'Tgl Bayar DPP harus TEPAT setelah Bayar DPP, urutan: {_th}'
assert _th[_th.index('Bayar PPN') + 1] == 'Tgl Bayar PPN', \
    f'Tgl Bayar PPN harus TEPAT setelah Bayar PPN, urutan: {_th}'

# Setiap baris punya jumlah <td> = jumlah kolom (tidak ada sel bergeser).
_body = re.search(r'<tbody>(.*?)</tbody>', _seg, re.S).group(1)
_trs = re.findall(r'<tr>(.*?)</tr>', _body, re.S)
assert _trs, 'tabel invoice kosong'
assert {len(re.findall(r'<td', _r)) for _r in _trs} == {14}, \
    'jumlah <td> per baris tidak sama dengan 14 kolom'

# Nilai retensi benar-benar ter-render (bukan hanya header).
_money = app.jinja_env.filters['money']
_bln = [  # kontrak ber-retensi: cari yang punya nilai retensi
    _c for _c in contracts
    if any(_i['pot_retensi'] for _i in db_contract.get_contract_invoices(_c['no_kontrak']))]
assert _bln, 'tidak ada data retensi di DB untuk diuji'
_cr = _bln[0]
_inv_r = db_contract.get_contract_invoices(_cr['no_kontrak'])
_hr = _client.get(f'/kontrak/{_cr["id"]}').get_data(as_text=True)
_sr = _hr[_hr.index('Invoice dengan No. Kontrak Ini'):]
_sr = _sr[:_sr.index('</section>')]
_trr = re.findall(r'<tr>(.*?)</tr>',
                  re.search(r'<tbody>(.*?)</tbody>', _sr, re.S).group(1), re.S)
_ada = 0
for _i in _inv_r:
    if _i['pot_retensi']:
        assert any(_money(_i['pot_retensi']) in _r for _r in _trr), \
            f'retensi {_money(_i["pot_retensi"])} tidak tampil di baris'
        _ada += 1
assert _ada, 'nilai retensi tidak ter-render satupun'
print(f'[7b] kolom Retensi OK (setelah Pot. PPH, 14 kolom, '
      f'{_ada} nilai tampil di {_cr["no_kontrak"]})')


# --- 7c. Jadwal Termin: kolom "Status DPP" + "Status PPN" (4 status) ---
def _termin_seg(html):
    seg = html[html.index('Jadwal Termin'):]
    return seg[:seg.index('</table>')]


def _pills(html):
    return re.findall(
        r'<span class="kd-term-pill kd-term-pill--(\w+)"[^>]*>([^<]+)</span>',
        _termin_seg(html))


_valid = {'Lunas', 'Bayar Sebagian', 'Ditagih Sebagian', 'Belum Ditagih',
          'Belum Dibayar', 'Ditagih & Bayar Sebagian'}
_tseg = _termin_seg(_det_html)
for _hdr in ('Status DPP', 'Status PPN'):
    assert _hdr in _tseg, f'header "{_hdr}" tidak ada di Jadwal Termin'
assert 'Status Invoice' not in _tseg, \
    'header "Status Invoice" harus diganti Status DPP/PPN'
assert re.search(r'<th[^>]*>Status</th>', _tseg) is None, \
    'header "Status" lama masih ada di Jadwal Termin'
assert 'PPN per Termin (Rp)' in _tseg, 'header PPN per Termin (Rp) tidak ada'
assert re.search(r'PPN per Termin \(Rp\)[^<]*<span', _tseg) is None, \
    'header PPN per Termin (Rp) masih menyertakan persen'

_pl = _pills(_det_html)
assert _pl, 'pill status termin tidak ter-render'
_labs = {re.sub(r'&amp;', '&', t) for _, t in _pl}
assert _labs <= _valid, f'label status tak dikenal: {_labs}'
_ncells = len(re.findall(r'<td class="text-center">\s*<span class="kd-term-pill',
                         _tseg))
assert len(_pl) == _ncells, \
    f'jumlah pill {len(_pl)} != jumlah sel status {_ncells} (2 sel per termin)'

# Rekonsiliasi: label diturunkan ulang dari data DB, DPP dan PPN terpisah.
_mismatch = []
_totals = {'DPP': dict.fromkeys(_valid, 0), 'PPN': dict.fromkeys(_valid, 0)}
for _c in contracts:
    _ts = db_contract.enrich_termins(db_contract.get_termins(_c['id']), _c)
    if not _ts:
        continue
    for _t in _ts:
        for _kind in ('dpp', 'ppn'):
            _lab = _t['status_' + _kind]
            _ton = _t['status_tone_' + _kind]
            _totals[_kind.upper()][_lab] += 1
            assert _ton in ('ok', 'jalan', 'belum', 'warn'), \
                f"{_c['no_kontrak']}: tone {_ton}"
            _cocok = _t['cocok_status' if _kind == 'dpp' else 'cocok_status_ppn']
            _byr = float(_t['dibayar_termin' if _kind == 'dpp'
                              else 'dibayar_ppn_termin'])
            _pagu_k = float(_t['nilai' if _kind == 'dpp' else 'ppn'] or 0)
            _nol = _byr <= 1.0
            _lunas = abs(_pagu_k - _byr) <= 1.0
            if _cocok == 'belum':
                _want = 'Belum Ditagih'
            elif _cocok == 'sebagian':
                _want = 'Ditagih Sebagian' if _nol else 'Ditagih & Bayar Sebagian'
            elif _nol:
                _want = 'Belum Dibayar'
            elif _lunas:
                _want = 'Lunas'
            else:
                _want = 'Bayar Sebagian'
            if _lab != _want:
                _mismatch.append(
                    f"{_c['no_kontrak']}#{_t['urutan_no']} {_kind}: "
                    f"{_lab} != {_want}")
        _pagu = float(_t['nilai'] or 0)
        assert 0 <= _t['dibayar_termin'] <= _pagu + 1.0, \
            f"{_c['no_kontrak']}: alokasi bayar DPP termin melebihi pagu"
        _pagu_ppn = float(_t['ppn'] or 0)
        assert 0 <= _t['dibayar_ppn_termin'] <= _pagu_ppn + 1.0, \
            f"{_c['no_kontrak']}: alokasi bayar PPN termin melebihi pagu"
assert not _mismatch, f'label status tidak konsisten: {_mismatch[:5]}'
print(f'[7c] Status DPP/PPN OK: DPP {_totals["DPP"]} | PPN {_totals["PPN"]} '
      f'(PPN per Termin tanpa persen)')


# --- 8. Detail kontrak: KPI + rincian memakai istilah yang sama dgn daftar ---
_det2 = _client.get(f'/kontrak/{_cid}').get_data(as_text=True)
assert 'Sisa Hutang (DPP)' in _det2 and 'Sisa Hutang (PPN)' in _det2, \
    'label Sisa Hutang (DPP/PPN) tidak ditemukan di detail'
assert 'Belum Ditagih (DPP)' in _det2, \
    'label Belum Ditagih (DPP) tidak ditemukan di detail'
assert 'Sisa Hutang Kontrak' not in _det2, \
    'label lama Sisa Hutang Kontrak masih ada di detail'
_cd = db_contract.get_contract(_cid)
assert 'Daftar Kontrak</a>' in _det2, \
    'tombol kembali harus berlabel Daftar Kontrak'
assert f'>{_cd["no_kontrak"]}</span>' in _det2, \
    'nomor kontrak/PO tidak tampil di sebelah tombol Daftar Kontrak'
assert re.search(r'id="pageTitle".{0,400}?' + re.escape(_cd['vendor']), _det2, re.S), \
    'nama vendor/rekanan tidak tampil di topbar'
_money_f = appmod.app.jinja_env.filters['money']
_kpi = dict(re.findall(
    r'Sisa Hutang \((DPP|PPN)\)</div><div class="ds-kpi__value">([^<]+)</div>',
    _det2))
assert _kpi, 'nilai KPI Sisa Hutang tak terbaca dari HTML'
# Sisa Hutang = yang SUDAH DITAGIH tapi belum dibayar (bukan nilai - bayar).
for _tax, _tagih, _bayar in (('DPP', _cd['tertagih'], _cd['dibayar']),
                             ('PPN', _cd['tertagih_ppn'], _cd['dibayar_ppn'])):
    _expect = _money_f(max(0.0, (_tagih or 0) - (_bayar or 0)))
    assert _kpi.get(_tax) == _expect, \
        f'Sisa Hutang {_tax} = {_kpi.get(_tax)} != tagih-bayar {_expect}'
print(f'[8] KPI Sisa Hutang OK: DPP {_kpi["DPP"]}, PPN {_kpi["PPN"]}')

# --- 9. Daftar kontrak: tiga angka sisa konsisten dgn kolom ---
# Sisa Tagihan (total) = Belum Ditagih + Sisa Hutang. Identitas ini yang
# membuat pemecahan dua kolom tidak mengubah angka total.
_sum_dpp = sum(c['nilai_dpp'] - c['dibayar'] for c in contracts)
_sum_ppn = sum(c['nilai_ppn'] - c['dibayar_ppn'] for c in contracts)
assert abs(summary['total_sisa_dpp'] - _sum_dpp) < 0.5, \
    f"KPI Sisa Tagihan DPP {summary['total_sisa_dpp']:,.0f} != Σ kolom {_sum_dpp:,.0f}"
assert abs(summary['total_sisa_ppn'] - _sum_ppn) < 0.5, \
    f"KPI Sisa Tagihan PPN {summary['total_sisa_ppn']:,.0f} != Σ kolom {_sum_ppn:,.0f}"
assert abs(summary['total_belum_ditagih'] + summary['total_sisa_hutang']
           - summary['total_sisa_dpp']) < 0.5, \
    'Belum Ditagih DPP + Sisa Hutang DPP != Sisa Tagihan DPP'
assert abs(summary['total_belum_ditagih_ppn'] + summary['total_sisa_hutang_ppn']
           - summary['total_sisa_ppn']) < 0.5, \
    'Belum Ditagih PPN + Sisa Hutang PPN != Sisa Tagihan PPN'
for c in contracts:
    assert abs((c['nilai_dpp'] - c['dibayar']) - c['sisa_tagihan']) < 0.5, \
        f"{c['no_kontrak']}: sisa_tagihan != nilai_dpp - dibayar"
    assert abs((c['nilai_ppn'] - c['dibayar_ppn']) - c['sisa_tagihan_ppn']) < 0.5, \
        f"{c['no_kontrak']}: sisa_tagihan_ppn != nilai_ppn - dibayar_ppn"
    # Inti perbaikan: Sisa Hutang HANYA dari yang sudah ditagih.
    assert abs(max(0.0, c['tertagih'] - c['dibayar']) - c['sisa_hutang']) < 0.5, \
        f"{c['no_kontrak']}: sisa_hutang != max(0, tertagih - dibayar)"
    assert abs(max(0.0, c['tertagih_ppn'] - c['dibayar_ppn'])
               - c['sisa_hutang_ppn']) < 0.5, \
        f"{c['no_kontrak']}: sisa_hutang_ppn != max(0, tertagih_ppn - dibayar_ppn)"
    assert abs(c['sisa_kontrak'] + c['sisa_hutang'] - c['sisa_tagihan']) < 0.5, \
        f"{c['no_kontrak']}: belum_ditagih + sisa_hutang != sisa_tagihan"
with app.test_request_context('/'):
    _html9 = render_template('contracts.html', contracts=contracts, summary=summary,
                             project_labels={}, project_list=[])
assert 'Sisa Tagihan (DPP)</div>' in _html9 and 'Sisa Tagihan (PPN)</div>' in _html9, \
    'label KPI Sisa Tagihan (DPP/PPN) tidak ditemukan'
for _lbl in ('DPP', 'PPN'):
    for _nm in ('Belum Ditagih', 'Sisa Hutang'):
        assert f'{_nm} ({_lbl})</th>' in _html9, \
            f'kolom "{_nm} ({_lbl})" tidak ditemukan'
assert 'Sisa Hutang DPP</div>' not in _html9, 'label lama Sisa Hutang DPP masih ada'
_money9 = appmod.app.jinja_env.filters['money']
for _lbl, _val in (('DPP', summary['total_sisa_dpp']),
                   ('PPN', summary['total_sisa_ppn'])):
    assert f'Sisa Tagihan ({_lbl})</div><div class="ds-kpi__value">{_money9(_val)}</div>' \
        in _html9, f'nilai KPI Sisa Tagihan {_lbl} tidak sesuai summary'
# Hint KPI menyebut "Sisa hutang", bukan lagi "Sudah ditagih belum dibayar".
assert 'Sisa hutang: ' in _html9, 'hint KPI harus menyebut "Sisa hutang"'
print(f'[9] Sisa Tagihan = Belum Ditagih + Sisa Hutang OK: '
      f'hutang DPP {summary["total_sisa_hutang"]:,.0f}, '
      f'PPN {summary["total_sisa_hutang_ppn"]:,.0f}')

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


# --- 11. Pencocokan invoice ke jadwal termin (kolom "Termin Ditagih") ---
# Inti halaman Progress Kontrak: invoice yang masuk harus bisa dicocokkan ke
# termin kontrak. Diuji dengan termin nyata Sulzer (10/27/54/9 dari 20,1 M).
_term = [{'nilai': 2010000000.0, 'label': 'Uang Muka', 'urutan_no': 1},
         {'nilai': 5427000000.0, 'label': 'FAT', 'urutan_no': 2},
         {'nilai': 10854000000.0, 'label': 'Material on Site/BASTB', 'urutan_no': 3},
         {'nilai': 1809000000.0, 'label': 'Commisioning', 'urutan_no': 4}]
_cases = [
    (0,                     0, 'belum'),
    (1005000000,            0, 'berjalan'),   # separuh Uang Muka
    (2010000000,            1, 'pas'),        # Uang Muka lunas
    (4723500000,            1, 'berjalan'),   # Uang Muka + separuh FAT
    (7437000000,            2, 'pas'),        # Uang Muka + FAT
    (20100000000,           4, 'pas'),        # semua termin
    (20210000000,           4, 'lebih'),      # melebihi total termin
]
for _x, _n, _st in _cases:
    _r = db_contract.termin_progress(_term, _x)
    assert _r['status'] == _st, f'tertagih {_x:,.0f}: status {_r["status"]} != {_st}'
    assert _r['ditagih'] == _n, f'tertagih {_x:,.0f}: ditagih {_r["ditagih"]} != {_n}'
    assert _r['pesan'], 'setiap status harus punya pesan penjelasan'
# Menagih sebagian termin adalah NORMAL, bukan temuan: status 'berjalan'.
assert db_contract.termin_progress(_term, 4723500000)['selisih'] == 0, \
    'tagihan sebagian termin tidak boleh dihitung sebagai selisih/temuan'
# Tanpa jadwal termin -> tidak bisa dicocokkan (bukan 0/0).
_none = db_contract.termin_progress([], 5000000)
assert _none['status'] == 'tanpa_jadwal' and not _none['ada_jadwal'], \
    'kontrak tanpa termin harus berstatus tanpa_jadwal'
print(f'[11] termin_progress OK: {len(_cases)} kasus + tanpa_jadwal')

# --- 11b. Tampilan: semua kontrak nyata ter-render dengan pill yang benar ---
for _c in contracts:
    _tc = _c.get('termin_cocok')
    assert _tc is not None, f"{_c['no_kontrak']}: termin_cocok tidak terpasang"
    assert _tc['status'] in ('tanpa_jadwal', 'belum', 'pas', 'berjalan', 'lebih'), \
        f"{_c['no_kontrak']}: status tak dikenal {_tc['status']}"
    assert _tc['status'] != 'tanpa_jadwal' or not _tc['ada_jadwal'], \
        f"{_c['no_kontrak']}: status tanpa_jadwal tapi ada_jadwal True"
_pills = re.findall(r'kc-term-pill kc-term-pill--(\w+)"[^>]*>\s*([\d/—]+)', _html9)
_pill_contracts = [c for c in contracts if c['id'] in
                   {c2['id'] for c2 in contracts}]
assert len(_pills) == len(contracts), \
    f'pill termin harus satu per kontrak: {len(_pills)} != {len(contracts)}'
for _c, (_, _txt) in zip(contracts, _pills):
    _tc = _c['termin_cocok']
    _want = '—' if not _tc['ada_jadwal'] else f"{_tc['ditagih']}/{_tc['jumlah']}"
    assert _txt == _want, f"{_c['no_kontrak']}: pill '{_txt}' != '{_want}'"
print(f'[11b] pill Termin Ditagih ter-render benar untuk {len(contracts)} kontrak')

# --- 11c. Istilah "Belum Ditagih" vs "Sisa Hutang" tidak tertukar ---
# Ini inti perbaikan: pekerjaan yang belum ditagih BUKAN utang. Tooltip dan
# label harus memakai istilah yang sama di daftar maupun detail, dan frasa
# lama yang menggabungkan keduanya tidak boleh muncul lagi.
for _cls in ('contracts.html', 'contract_detail.html'):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'templates', _cls), encoding='utf-8') as _f:
        _src = _f.read()
    assert 'Sisa Hutang (' in _src, f'{_cls}: label "Sisa Hutang" tidak ada'
    assert 'Belum Ditagih (' in _src, f'{_cls}: label "Belum Ditagih" tidak ada'
    # Tooltip Sisa Hutang harus menyebut "sudah ditagih".
    assert 'sudah ditagih' in _src.lower(), \
        f'{_cls}: tooltip Sisa Hutang harus menegaskan "sudah ditagih"'
    assert 'termasuk yang belum ditagih' not in _src, \
        f'{_cls}: frasa lama "termasuk yang belum ditagih" masih ada'
    assert 'Terdiri dari' not in _src, \
        f'{_cls}: penjelasan lama "Terdiri dari ..." sudah digantikan kolom terpisah'
assert 'Sisa hutang: ' in _html9, \
    'hint KPI harus memakai label "Sisa hutang"'
print('[11c] istilah Belum Ditagih vs Sisa Hutang konsisten OK')

# --- 11d. Detail kontrak: grup identitas, proyek, dan metode penetapan ---
_detail_id = contracts[0]['id']
_detail = client.get(f'/kontrak/{_detail_id}').get_data(as_text=True)
_read = re.search(r'<dl class="kd-def" id="kdRead">(.*?)</dl>', _detail, re.S)
assert _read, 'blok baca Identitas Kontrak tidak ditemukan'
_read_groups = re.findall(r'<div class="kd-def__sec">(.*?)</div>', _read.group(1))
assert _read_groups == ['Identitas Kontrak', 'Nilai &amp; Pajak',
                        'Pekerjaan &amp; Jadwal', 'Status Penagihan'], \
    f'urutan grup Identitas Kontrak salah: {_read_groups}'
assert 'Metode Penetapan' not in _read.group(1), \
    'metode penetapan tidak perlu tampil di blok baca'
_form = re.search(r'<form[^>]*id="kdForm".*?</form>', _detail, re.S)
assert _form, 'form Identitas Kontrak tidak ditemukan'
_form_groups = re.findall(r'<h2 class="kd-group__title">(.*?)</h2>', _form.group(0))
assert _form_groups == ['Identitas Kontrak', 'Nilai &amp; Pajak', 'Pekerjaan &amp; Jadwal'], \
    f'grup form Identitas Kontrak salah: {_form_groups}'
for _field in ('project_id', 'nilai_kontrak', 'ppn_rate',
               'metode_pembayaran', 'tipe_pekerjaan', 'item_pekerjaan',
               'tgl_kontrak', 'tgl_selesai', 'durasi_termin'):
    assert f'name="{_field}"' in _form.group(0), f'field {_field} tidak ada di form'
assert 'name="metode_penetapan"' not in _form.group(0), \
    'metode penetapan tidak perlu tampil di form'
assert '— Tanpa proyek —' in _form.group(0), 'opsi tanpa proyek tidak ada'
assert '<div class="kd-s4"><dt>Proyek</dt>' in _read.group(1)
assert '<div class="kd-s8"><dt>Tipe Kontrak</dt>' in _read.group(1), \
    'Tipe Kontrak harus mulai sejajar dengan Nilai DPP di bawahnya'
assert re.search(r'<div class="kd-s4">\s*<label class="kd-label" for="project_id">',
                 _form.group(0))
assert re.search(r'<div class="kd-s8">\s*<label class="kd-label" for="tipe_kontrak">',
                 _form.group(0)), 'Tipe Kontrak di form harus mulai sejajar dengan PPN di bawahnya'
print(f'[11d] detail kontrak OK: 4 grup baca, 3 grup form, proyek editable tanpa metode penetapan')


print('ALL CHECKS PASSED')
