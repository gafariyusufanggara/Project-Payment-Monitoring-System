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
import re
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
    # Pecahan per status — harus sama persis dengan controllers/main.py.
    ditahan = sum(inv['sisa_retensi'] for g in groups for inv in g['invoices']
                  if inv['status_retensi'] in ('Ditahan', 'Cair Sebagian'))
    belum_ditahan = sum(inv['sisa_retensi'] for g in groups for inv in g['invoices']
                       if inv['status_retensi'] == 'Belum Dibayar')
    with app.test_request_context('/levelansir-retensi'):
        return render_template(
            'levelansir_retensi.html',
            levelansir_list=groups,
            total_retensi=total,
            total_cair=cair,
            total_belum_cair=total - cair,
            retensi_ditahan=ditahan,
            retensi_belum_ditahan=belum_ditahan,
            retensi_dibayar_sebagian=sum(inv['retensi_cair'] for g in groups for inv in g['invoices']
                                         if inv['status_retensi'] == 'Cair Sebagian'),
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

# --- 3b. KPI Retensi Ditahan + Belum Ditahan harus menutup seluruh utang retensi ---
# Regresi yang dikunci: dulu KPI memakai (total - sudah dibayar) sehingga
# "Cair" selalu Rp 0 dan "Belum Cair" selalu == Total -> dua kartu tidak
# menambah informasi. Retensi = utang ke vendor, jadi bahasanya hutang.
ditahan = sum(inv['sisa_retensi'] for g in groups for inv in g['invoices']
              if inv['status_retensi'] in ('Ditahan', 'Cair Sebagian'))
belum_ditahan = sum(inv['sisa_retensi'] for g in groups for inv in g['invoices']
                    if inv['status_retensi'] == 'Belum Dibayar')
sebagian_dibayar = sum(inv['retensi_cair'] for g in groups for inv in g['invoices']
                       if inv['status_retensi'] == 'Cair Sebagian')
assert abs(ditahan + belum_ditahan + sebagian_dibayar + (cair - sebagian_dibayar) - total) < 0.01, \
    f'identitas KPI gagal: {ditahan:,.0f}+{belum_ditahan:,.0f}+{sebagian_dibayar:,.0f} != {total:,.0f}'
assert abs(belum - (ditahan + belum_ditahan)) < 0.01, \
    f'ditahan({ditahan:,.0f}) + belum ditahan({belum_ditahan:,.0f}) harus == sisa utang({belum:,.0f})'
# Kartu tidak boleh dua-duanya nol / saling meniadakan.
assert ditahan > 0 or belum_ditahan > 0, 'KPI Retensi Ditahan & Belum Ditahan tidak boleh dua-duanya nol'
print(f'[3b] KPI Retensi Ditahan {ditahan:,.0f} + Belum Ditahan {belum_ditahan:,.0f} = {belum:,.0f} OK')

# --- 4. Label & kolom halaman levelansir ---
for label in ('Status Retensi', 'Nilai DPP', 'Nilai PPN', 'DPP Setelah Retensi',
              'Bayar DPP',
              'Sisa Retensi', 'Total Retensi',
              'Retensi Ditahan', 'Belum Ditahan'):
    assert label in html, f'label hilang: {label}'
# Label lama yang ambigu tidak boleh kembali.
assert 'Retensi Belum Cair' not in html, 'KPI "Retensi Belum Cair" (ambigu) masih tampil'
assert 'DPP Setelah Potongan' not in html, 'label lama "DPP Setelah Potongan" masih tampil'
# Kerangkanya utang, bukan "pencairan dana".
assert 'Siap Cair' not in html, 'istilah "Siap Cair" masih tampil (salah kerangka)'
assert 'Terkunci' not in html, 'istilah "Terkunci" masih tampil (salah kerangka)'
assert 'dicairkan' not in html, 'istilah "dicairkan" masih tampil (retensi = utang, bukan dana cair)'
assert 'Jatuh Waktu' not in html, 'istilah "Jatuh Waktu" masih tampil (retensi = ditahan)'
assert 'Menunggu DPP' not in html, 'istilah "Menunggu DPP" masih tampil'
assert 'Harga (Exld)' not in html, 'label Harga (Exld) masih tampil'
assert 'Retensi (%)' not in html, 'kolom Retensi (%) masih tampil'
assert 'Kode Biaya' not in html, 'kolom Kode Biaya masih tampil'
assert 'Tgl Berkas Lengkap' not in html, 'kolom Tgl Berkas Lengkap tidak diminta'
# Keterangan panjang di bawah KPI sudah dihapus (mengganggu tampilan).
# Penjelasan istilah kini ada di tooltip tiap kartu, jadi tidak hilang.
assert 'cic-sub' not in html, 'paragraf keterangan panjang di bawah KPI masih tampil'
print('[4] label & kolom levelansir OK')

# --- 4c. Kolom Bayar DPP: urutan tepat setelah DPP Setelah Retensi ---
_head = html[html.index('cic-table'):html.index('</thead>')]
_labs = [re.sub(r'<[^>]+>', '', x).strip()
         for x in re.findall(r'<th\b[^>]*>([\s\S]*?)</th>', _head)]
assert 'Bayar DPP' in _labs, f'kolom Bayar DPP hilang: {_labs}'
_i = _labs.index('Bayar DPP')
assert _labs[_i - 1] == 'DPP Setelah Retensi', \
    f'Bayar DPP harus tepat setelah DPP Setelah Retensi, dapat: {_labs[_i - 1]}'
assert _labs[_i + 1] == 'Sisa Retensi', \
    f'Bayar DPP harus tepat sebelum Sisa Retensi, dapat: {_labs[_i + 1]}'
# Nilai Bayar DPP benar-benar tampil (bukan kolom kosong).
assert any(i['bayar_dpp'] > 0 for i in invoices), 'tidak ada invoice dengan bayar_dpp > 0'
assert re.search(r'<td class="cell-money">\d[\d.]*</td>\s*<td class="cell-money">', html), \
    'sel Bayar DPP tidak berisi angka'
print(f'[4c] kolom Bayar DPP di posisi {_i}, urutan {_labs[_i-1]} -> Bayar DPP -> {_labs[_i+1]} OK')

# --- 4b. Route asli: KPI benar-benar terisi (bukan jatuh ke 0 default) ---
# render_levelansir() di atas memanggil render_template() manual, jadi keyword
# yang lupa dikirim dari controller TIDAK ketahuan. Di sini kita render lewat
# route /levelansir-retensi yang sesungguhnya supaya nama variabel controller
# ikut teruji (bug nyata: KPI tampil Rp 0 karena keyword tak cocok).
from services import auth as _auth

with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    resp = c.get('/levelansir-retensi')
assert resp.status_code == 200, f'/levelansir-retensi -> {resp.status_code}'
page = resp.data.decode('utf-8')

_kpi = dict(re.findall(
    r'ds-kpi__label">([^<]+)</div><div class="ds-kpi__value">([^<]*)<', page))
assert 'Retensi Ditahan' in _kpi, f'KPI Retensi Ditahan hilang: {list(_kpi)}'
assert 'Belum Ditahan' in _kpi, f'KPI Belum Ditahan hilang: {list(_kpi)}'


def _rp(label):
    return float(_kpi[label].replace('.', '').replace(',', '.') or 0)


# Angka KPI di halaman harus sama dengan hasil hitung langsung dari data.
assert abs(_rp('Retensi Ditahan') - ditahan) < 1.0, \
    f"KPI Retensi Ditahan {_kpi['Retensi Ditahan']} != {ditahan:,.0f}"
assert abs(_rp('Belum Ditahan') - belum_ditahan) < 1.0, \
    f"KPI Belum Ditahan {_kpi['Belum Ditahan']} != {belum_ditahan:,.0f}"
assert _rp('Total Retensi') > 0, 'KPI Total Retensi bernilai 0 — data tidak terkirim'
# Kedua kartu tidak boleh dua-duanya 0 saat data punya retensi.
assert _rp('Retensi Ditahan') + _rp('Belum Ditahan') > 0, \
    'KPI Retensi Ditahan & Belum Ditahan dua-duanya 0 — variabel controller tidak terkirim'
print(f"[4b] route asli: Ditahan {_kpi['Retensi Ditahan']} + "
      f"Belum Ditahan {_kpi['Belum Ditahan']} OK")

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
