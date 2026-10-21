# -*- coding: utf-8 -*-
"""Smoke check: halaman Retensi (levelansir).

Memverifikasi:
- status retensi turunan dari sisa DPP (Lunas/Ditahan/Cair Sebagian/Belum Dibayar);
- KPI = jumlah kolom (retensi cair + belum cair = total retensi);
- Nilai PPN = 11% x (Nilai DPP - Pot. Retensi);
- kolom Kode Biaya sudah tidak tampil;
- nama rekanan, no invoice, no PO & deskripsi membawa data-full agar bisa diklik;
- kolom Tgl Berkas Lengkap tidak ditambahkan di halaman levelansir.

Run:  python smoke_retensi_page_check.py
Read-only terhadap data nyata.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod
import db
from constants import status_retensi
from flask import render_template

app = appmod.app


def render_levelansir():
    groups = db.get_levelansir_retensi(None)
    total = sum(g['total_retensi'] for g in groups)
    cair = sum(g['total_cair'] for g in groups)
    with app.test_request_context('/levelansir-retensi'):
        return render_template(
            'levelansir_retensi.html',
            levelansir_list=groups,
            total_retensi=total,
            total_cair=cair,
            total_belum_cair=total - cair,
            total_setelah_retensi=sum(i['total'] for g in groups for i in g['invoices']),
            total_levelansir=len(groups),
            total_invoices=sum(g['jumlah_invoice'] for g in groups),
            active_project_id=None,
        ), groups


# --- 1. Rumus status retensi (unit, termasuk toleransi Rp 1) ---
cases = [
    ((100.0, 5.0, 100.0), ('Lunas', 0.0, 5.0)),
    ((100.0, 5.0, 95.0), ('Ditahan', 5.0, 0.0)),
    ((100.0, 5.0, 97.0), ('Cair Sebagian', 3.0, 2.0)),
    ((100.0, 5.0, 90.0), ('Belum Dibayar', 5.0, 0.0)),
    ((100.0, 5.0, 95.5), ('Ditahan', 4.5, 0.5)),
    ((0.0, 5.0, 0.0), ('Belum Dibayar', 5.0, 0.0)),
]
for args, expected in cases:
    got = status_retensi(*args)
    assert got[0] == expected[0], f'status {args}: {got[0]} != {expected[0]}'
    assert abs(got[1] - expected[1]) < 0.01, f'sisa retensi {args}: {got[1]} != {expected[1]}'
    assert abs(got[2] - expected[2]) < 0.01, f'cair {args}: {got[2]} != {expected[2]}'
print(f'[1] rumus status retensi OK: {len(cases)} kasus')

# --- 2. Data nyata: sisa retensi + cair tidak melebihi nilai retensi ---
html, groups = render_levelansir()
assert groups, 'tidak ada data retensi'
invoices = [i for g in groups for i in g['invoices']]
for inv in invoices:
    assert 0 <= inv['sisa_retensi'] <= inv['nilai_retensi'] + 0.01, inv['no_invoice']
    assert abs(inv['retensi_cair'] + inv['sisa_retensi'] - inv['nilai_retensi']) < 0.01, \
        inv['no_invoice']
    expected_ppn = max(0, inv['harga_exld'] - inv['nilai_retensi']) * 0.11
    assert abs(inv['nilai_ppn'] - expected_ppn) < 0.01, inv['no_invoice']
print(f'[2] data retensi & PPN OK: {len(groups)} rekanan, {len(invoices)} invoice')

# --- 3. KPI = jumlah kolom ---
total = sum(g['total_retensi'] for g in groups)
cair = sum(g['total_cair'] for g in groups)
belum = sum(g['total_sisa_retensi'] for g in groups)
assert abs(cair + belum - total) < 0.01, f'KPI {cair:,.0f} + {belum:,.0f} != {total:,.0f}'
print(f'[3] KPI retensi OK: total {total:,.0f}, cair {cair:,.0f}, belum {belum:,.0f}')

# --- 4. Label & kolom halaman levelansir ---
for label in ('Status Retensi', 'Nilai DPP', 'Nilai PPN', 'DPP Setelah Retensi',
              'Sisa Retensi', 'Retensi Cair', 'Retensi Belum Cair'):
    assert label in html, f'label hilang: {label}'
assert 'Harga (Exld)' not in html, 'label Harga (Exld) masih tampil'
assert 'Retensi (%)' not in html, 'kolom Retensi (%) masih tampil'
assert 'Kode Biaya' not in html, 'kolom Kode Biaya masih tampil'
assert 'Tgl Berkas Lengkap' not in html, 'kolom Tgl Berkas Lengkap tidak diminta'
print('[4] label & kolom levelansir OK')

# --- 5. data-full pada nama rekanan, no invoice, no PO + deskripsi ---
for g in groups:
    assert f'data-full="{g["nama"]}"' in html, f'data-full rekanan hilang: {g["nama"]}'
for inv in invoices:
    for field in ('no_invoice', 'no_po', 'deskripsi'):
        if inv[field]:
            assert f'data-full="{inv[field]}"' in html, \
                f'data-full {field} hilang: {inv["no_invoice"]}'
print('[5] data-full rekanan, invoice, PO & deskripsi OK')

# --- 6. Search mencakup invoice/PO, bukan hanya rekanan ---
for g in groups:
    assert f'data-search="{g["search_text"].lower()}"' in html, \
        f'data-search hilang: {g["nama"]}'
print('[6] data-search invoice/PO/deskripsi OK')

print('ALL CHECKS PASSED')
