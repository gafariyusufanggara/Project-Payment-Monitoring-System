# -*- coding: utf-8 -*-
"""Smoke check: Exclude Invoice diterapkan konsisten di semua perhitungan.

Aturan: baris yang KATEGORI/rekanannya di daftar Exclude Invoice tidak boleh
masuk perhitungan (subtotal, KPI, total) di halaman mana pun, walau barisnya
tetap tampil di tabel.

Yang diperiksa:
  1. is_excluded_values / is_excluded_row konsisten (case-insensitive, trim).
  2. Tabel Data Invoice menandai baris ter-exclude; footer JS melewatinya.
  3. get_cicilan_data, get_document_status, db.get_levelansir_retensi,
     dashboard total_retensi & export laporan memakai aturan exclude.
  4. Uji fungsional: saat satu rekanan dimasukkan ke EXCLUDED_REKANAN,
     perhitungan di atas berubah dan baris itu hilang dari hasil.
  5. KPI Progress Kontrak (daftar + detail) ikut exclude; baris invoice
     ter-exclude tetap tampil dengan penanda.

Run:  python smoke_exclude_consistency_check.py
Read-only terhadap data nyata (mutasi daftar exclude dikembalikan di akhir).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import constants  # noqa: E402
import db  # noqa: E402
from constants import is_excluded_row, is_excluded_values, safe_float  # noqa: E402
from services.cicilan import get_cicilan_data  # noqa: E402
from services.document_status import get_document_status  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as f:
        return f.read()


# --- 1. Semantik dasar ---
_cat = (constants.CATEGORIES or ['Bahan'])[0]
constants.EXCLUDED_CATEGORIES.append(_cat)
try:
    assert is_excluded_row({'KATEGORI': f' {_cat.upper()} ', 'NAMA LEVELANSIR / REKANAN': ''})
    assert is_excluded_values(_cat.lower(), 'PT APA SAJA')
finally:
    constants.EXCLUDED_CATEGORIES.remove(_cat)
print('[1] is_excluded_values case-insensitive + trim OK')

# --- 2. Wiring tabel & footer ---
assert 'data-excluded=' in _read('templates', 'partials', '_data_table.html')
assert "tr.dataset.excluded === '1'" in _read('templates', 'index.html')
print('[2] _data_table menandai baris + updateFootTotals melewati baris exclude OK')

# --- 3. Penanda filter ada di setiap jalur perhitungan ---
paths = [
    ('services', 'cicilan.py'),
    ('services', 'document_status.py'),
    ('services', 'dashboard.py'),
    ('services', 'laporan.py'),
    ('services', 'laporan_ppn.py'),
    ('services', 'contract_match.py'),
    ('db.py',),
    ('db_project.py',),
    ('db_contract.py',),
]
for p in paths:
    assert 'is_excluded' in _read(*p), f'{p}: tidak memakai aturan exclude'
print('[3] semua modul perhitungan memakai aturan exclude OK')

# --- 4. Uji fungsional pada data nyata ---
rows = db.read_data()
cic_before = get_cicilan_data()
assert cic_before, 'tidak ada data cicilan — tidak bisa uji fungsional'
_rek = cic_before[0]['rekanan']
_retrek = next(((r.get('NAMA LEVELANSIR / REKANAN') or '').strip() for r in rows
                if safe_float(r.get('POT. RETENSI')) > 0
                and (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()), None)
doc_before = get_document_status()[1]
ret_before = sum(g['total_retensi'] for g in db.get_levelansir_retensi())

constants.EXCLUDED_REKANAN.append(_rek)
if _retrek and _retrek.lower() != _rek.lower():
    constants.EXCLUDED_REKANAN.append(_retrek)
try:
    assert is_excluded_row({'KATEGORI': '', 'NAMA LEVELANSIR / REKANAN': _rek})
    cic_after = get_cicilan_data()
    doc_after = get_document_status()[1]
    ret_after = sum(g['total_retensi'] for g in db.get_levelansir_retensi())

    assert all(g['rekanan'].strip().lower() != _rek.lower() for g in cic_after), \
        f'cicilan masih memuat rekanan ter-exclude: {_rek}'
    assert len(cic_after) < len(cic_before), 'grup cicilan ter-exclude tidak hilang'
    assert doc_after['revisi_count'] <= doc_before['revisi_count']
    if _retrek:
        assert ret_after < ret_before, 'retensi rekanan ter-exclude masih terhitung'
    print(f'[4] exclude "{_rek}": cicilan {len(cic_before)}->{len(cic_after)} grup, '
          f'retensi {ret_before:,.0f}->{ret_after:,.0f} OK')
finally:
    if _retrek and _retrek.lower() != _rek.lower():
        constants.EXCLUDED_REKANAN.remove(_retrek)
    constants.EXCLUDED_REKANAN.remove(_rek)

# --- 5. KPI Progress Kontrak (daftar + detail) ikut aturan exclude ---
import db_contract  # noqa: E402

_contracts = db_contract.get_contracts('all')
_c = next((c for c in _contracts
           if (c.get('jumlah_invoice') or 0) > 0 and (c.get('tertagih') or 0) > 0), None)
assert _c, 'tidak ada kontrak dengan invoice �?" tidak bisa uji fungsional'
_crek = next((i['rekanan'] for i in db_contract.get_contract_invoices(_c['no_kontrak'])
              if not i['excluded'] and i['rekanan']), None)
assert _crek, f"{_c['no_kontrak']}: invoice aktif tanpa rekanan"
_sum_before = db_contract.get_summary()
_detail_before = db_contract.get_contract(_c['id'])

constants.EXCLUDED_REKANAN.append(_crek)
try:
    _detail_after = db_contract.get_contract(_c['id'])
    _inv_after = db_contract.get_contract_invoices(_c['no_kontrak'])
    _sum_after = db_contract.get_summary()

    assert _inv_after, 'semua invoice hilang dari tabel (harus tetap tampil)'
    assert any(i['excluded'] for i in _inv_after if i['rekanan'].lower() == _crek.lower()), \
        f'baris {_crek} harus tetap tampil dengan flag excluded'
    assert (_detail_after['tertagih'] < _detail_before['tertagih']
            or _detail_after['dibayar'] < _detail_before['dibayar']), \
        'KPI kontrak detail tidak berubah saat invoicenya di-exclude'
    assert _detail_after['jumlah_invoice'] < _detail_before['jumlah_invoice']
    assert _sum_after['total_tertagih'] < _sum_before['total_tertagih'], \
        'KPI daftar kontrak masih menghitung invoice ter-exclude'
    assert _detail_after['status_invoice'] in ('Ada Invoice', 'Semua Invoice Ter-exclude')

    # Subtitle KPI detail memakai pola yang sama dengan daftar kontrak:
    # "Belum ditagih: ... · <komponen kedua>", tanpa frasa lama.
    _list_src = _read('templates', 'contracts.html')
    assert 'Belum ditagih: ' in _list_src and 'Sisa hutang: ' in _list_src, \
        'contracts.html: pola hint KPI berubah'
    _detail_src = _read('templates', 'contract_detail.html')
    assert 'Belum ditagih: ' in _detail_src and 'Sisa tagihan: ' in _detail_src, \
        'contract_detail.html: hint KPI belum seragam dengan daftar kontrak'
    assert 'Sudah ditagih, belum dibayar &middot; Belum ditagih' not in _detail_src, \
        'contract_detail.html: hint lama masih ada'
    assert 'Semua Invoice Ter-exclude' in _detail_src, 'badge status exclude hilang'
    assert 'kd-excl-flag' in _detail_src, 'penanda baris invoice ter-exclude hilang'

    print(f'[5] kontrak {_c["no_kontrak"]}: invoice {_detail_before["jumlah_invoice"]}'
          f'->{_detail_after["jumlah_invoice"]}, '
          f'tertagih {_detail_before["tertagih"]:,.0f}->{_detail_after["tertagih"]:,.0f}, '
          f'summary {_sum_before["total_tertagih"]:,.0f}->{_sum_after["total_tertagih"]:,.0f} OK')
finally:
    constants.EXCLUDED_REKANAN.remove(_crek)

# Verifikasi sengaja memeriksa SEMUA baris (data quality), bukan perhitungan uang.
assert 'is_excluded' not in _read('services', 'verification.py'), \
    'services/verification.py: keputusan "tetap hitung semua baris" berubah'
print('[6] Verifikasi tetap memeriksa semua baris (pengecualian disengaja) OK')

print('SEMUA LOLOS')
