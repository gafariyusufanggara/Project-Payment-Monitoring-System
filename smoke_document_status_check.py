# -*- coding: utf-8 -*-
"""Smoke check: halaman Status Dokumen (/status-dokumen).

Halaman ini mendaftar dokumen yang masih REVISI — yaitu baris yang
"Tanggal Berkas Lengkap" (field 'TGL TERIMA') masih kosong. Kriteria ini
sama dengan penanda "Kelengkapan" di halaman Verifikasi Data.

Verifikasi:
  1. /status-dokumen render 200 (setelah login) & memuat penanda halaman.
  2. get_document_status() mengembalikan baris yang SEMUA-nya 'TGL TERIMA'
     kosong, dan tidak ada baris terisi yang ikut.
  3. Hitungan = jumlah baris 'TGL TERIMA' kosong pada db.read_data()
     (mengecualikan baris yang di-ignore), konsisten dengan count_document_revisi().
  4. Nominal DPP/PPN/PPh/Retensi/Total terhitung: summary = jumlah per baris.
  5. HTML memuat KPI + tabel + kolom nominal (data-val).
  6. Sidebar: tombol /status-dokumen ada tepat setelah Dashboard di grup Ringkasan.

Run:  python smoke_document_status_check.py
Read-only terhadap data nyata.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

import db
import app as appmod
from services import auth as _auth
from services.document_status import (
    get_document_status, count_document_revisi, _COL_TGL_TERIMA, _is_blank,
)

app = appmod.app
ROOT = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(ROOT, 'templates', 'document_status.html')
BASE = os.path.join(ROOT, 'templates', 'base.html')


def _blank(v):
    return v is None or str(v).strip() == ''


# --- 1. Halaman render 200 & memuat penanda ---
with app.test_client() as c:
    with c.session_transaction() as s:
        s[_auth.SESSION_KEY] = True
    r = c.get('/status-dokumen')
    assert r.status_code == 200, f"/status-dokumen -> {r.status_code}"
    html = r.get_data(as_text=True) if hasattr(r, 'get_data') else r.data.decode('utf-8', 'replace')
assert 'Status Dokumen' in html, "halaman tak memuat judul 'Status Dokumen'"
assert 'id="dsTable"' in html or 'Tidak Ada Dokumen Revisi' in html, \
    "halaman tak memuat tabel revisi / empty-state"
assert 'id="navStatusDokumen"' in html, "tombol sidebar Status Dokumen tidak ada"
print("[1] /status-dokumen 200 + penanda halaman OK")


# --- 2 & 3. Data service: hanya baris TGL TERIMA kosong, jumlah konsisten ---
rows, summary = get_document_status()
data = db.read_data()
ignored = set()
try:
    from db_ignore import get_ignored_set
    ignored = get_ignored_set(None)
except Exception:
    pass
expected = [
    row for row in data
    if row.get('_row') not in ignored and _is_blank(row.get(_COL_TGL_TERIMA))
]
assert summary['revisi_count'] == len(rows) == len(expected) == count_document_revisi(), \
    (f"hitungan tidak konsisten: summary={summary['revisi_count']} rows={len(rows)} "
     f"expected={len(expected)} count_fn={count_document_revisi()}")
# Setiap baris yang dikembalikan memang TGL TERIMA kosong.
by_idx = {row.get('_row'): row for row in data}
for item in rows:
    src = by_idx.get(item['row_idx'])
    assert src is not None, f"row_idx {item['row_idx']} tak ada di db.read_data()"
    assert _is_blank(src.get(_COL_TGL_TERIMA)), \
        f"baris {item['r']} ikut padahal TGL TERIMA terisi"
print(f"[2] {len(rows)} baris revisi, semua TGL TERIMA kosong OK")


# --- 3b. Baris yang TGL TERIMA terisi TIDAK ikut ---
returned_idx = {item['row_idx'] for item in rows}
terisi = [
    row for row in data
    if not _is_blank(row.get(_COL_TGL_TERIMA))
]
for row in terisi:
    assert row.get('_row') not in returned_idx, \
        f"baris terisi R-{row.get('R')} bocor ke daftar revisi"
print(f"[3] {len(terisi)} baris terisi tidak bocor ke revisi OK")


# --- 4. Nominal terhitung & konsisten dengan jumlah per baris ---
sum_dpp = sum(r['dpp'] for r in rows)
sum_ppn = sum(r['ppn'] for r in rows)
sum_pph = sum(r['pph'] for r in rows)
sum_ret = sum(r['retensi'] for r in rows)
sum_tot = sum(r['total'] for r in rows)
assert abs(summary['dpp'] - sum_dpp) < 0.5, "summary DPP != jumlah per baris"
assert abs(summary['ppn'] - sum_ppn) < 0.5, "summary PPN != jumlah per baris"
assert abs(summary['pph'] - sum_pph) < 0.5, "summary PPh != jumlah per baris"
assert abs(summary['retensi'] - sum_ret) < 0.5, "summary Retensi != jumlah per baris"
assert abs(summary['total'] - sum_tot) < 0.5, "summary Total != jumlah per baris"
print(f"[4] nominal OK — DPP {summary['dpp']:.0f}, PPN {summary['ppn']:.0f}, "
      f"PPh {summary['pph']:.0f}, Retensi {summary['retensi']:.0f}, Total {summary['total']:.0f}")


# --- 5. Template memuat KPI + tabel + kolom nominal ---
with open(TPL, encoding='utf-8') as f:
    tpl = f.read()
for token in ('Nilai DPP', 'Nilai PPN', 'Pot. PPh', 'Nilai Retensi', 'Total (Incl. PPN)'):
    assert token in tpl, f"template tak memuat kolom/KPI '{token}'"
assert 'data-val="{{ row.dpp }}"' in tpl or 'ds-money' in tpl, \
    "template tak menampilkan nominal (data-val)"
assert 'data-val="{{ summary.dpp }}"' in tpl, "KPI ringkas tak menampilkan nominal DPP"
# Nominal tanpa prefix "Rp" — konsisten dengan KPI uang di halaman lain.
assert "'Rp '" not in tpl, "JS masih memakai prefix 'Rp' pada nominal"
assert '|money }}' in tpl, "nominal harus memakai filter |money (id-ID, tanpa Rp)"
# KPI Dokumen Revisi harus menyertakan sub-label jumlah Levelansir.
assert 'ds-kpi__hint' in tpl and 'Levelansir' in tpl, \
    "KPI Dokumen Revisi tak menampilkan keterangan jumlah Levelansir"
assert re.search(r'Dokumen Revisi</div>.*?ds-kpi__hint">\{\{ summary\.rekanan_count \}\}', tpl, re.S), \
    "sub-label Levelansir harus memakai summary.rekanan_count"
assert re.search(r'Dokumen Revisi</div><div class="ds-kpi__value">\d+</div><div class="ds-kpi__hint">\d+ Levelansir</div>', html), \
    "HTML tak memuat keterangan Levelansir di bawah Dokumen Revisi"
# Deskripsi harus punya data-full agar tooltip click-expand menampilkan teks penuh.
assert re.search(r'class="ds-desc"[^>]*data-full=', tpl), \
    "Deskripsi (ds-desc) tak punya data-full — tooltip tidak akan muncul"
# Font tabel harus konsisten dengan tabel Data Invoice (.dt-table):
# body 0.78rem, header 0.7rem uppercase navy, zebra even.
# Catatan: sebelumnya halaman ini memakai .74rem sementara tabel Data Invoice
# memakai 0.78rem, sehingga keduanya TIDAK konsisten. Nilai diseragamkan ke
# 0.78rem (lihat static/css/app.css & normalisasi skala font).
assert re.search(
    r'\.ds-table \{ width: 100%; min-width: \d+px; border-collapse: separate; border-spacing: 0; font-size: 0\.78rem; \}',
    tpl), \
    "font-size/layout tabel Status Dokumen tak sesuai tabel lain (0.78rem, tanpa table-layout:fixed)"
assert re.search(r'\.ds-table thead th \{[^}]*font-size: 0\.7rem', tpl, re.S), \
    "font-size header tabel Status Dokumen tak sesuai tabel lain (0.7rem)"
assert 'color: #eaf2f8' in tpl, "warna teks header tak sama dengan tabel lain (#eaf2f8)"
assert 'nth-child(even)' in tpl, "tabel Status Dokumen tak punya zebra seperti tabel lain"
# Kolom Rekanan harus lebar agar tidak wrap sempit (colgroup + min-width).
assert '<colgroup>' in tpl and 'ds-col-rekanan' in tpl, "tabel harus pakai colgroup utk lebar kolom rapi"
assert re.search(r'\.ds-col-rekanan \{ width: [^;]+; min-width: 2\d\dpx', tpl), \
    "kolom Rekanan harus lebar (min-width >= 200px)"
# Kolom nominal juga dirender di HTML saat ada data.
if rows:
    assert html.count('data-val=') >= len(rows) * 5, \
        "HTML tak memuat nominal per baris (5 kolom uang)"
    assert html.count('class="ds-desc" data-full=') >= len(rows), \
        "HTML tak memuat data-full pada Deskripsi tiap baris"
# Kolom "Tgl Berkas" (TGL TERIMA BERKAS) diletakkan TEPAT SEBELUM "Tgl Berkas Lengkap".
assert '>Tgl Berkas</th>' in tpl, "template tak memuat kolom 'Tgl Berkas'"
assert re.search(r'>Tgl Berkas</th>\s*<th[^>]*>Tgl Berkas Lengkap</th>', tpl), \
    "kolom 'Tgl Berkas' harus tepat SEBELUM kolom 'Tgl Berkas Lengkap'"
assert re.search(r'\{\{ row\.tgl_berkas or \'-\' \}\}', tpl), \
    "sel 'Tgl Berkas' harus merender row.tgl_berkas dgn fallback '-'"
print("[5] template memuat KPI + kolom nominal (DPP/PPN/PPh/Retensi/Total) OK")

# --- 5b. Judul header halaman jelas & besar ---
assert 'ds-head-title' in tpl and 'Daftar Revisi Dokumen' in tpl, \
    "header halaman tak punya judul deskriptif 'Daftar Revisi Dokumen'"
assert re.search(r'\.ds-head-title \{[^}]*font-size: 1\.\d+rem', tpl), \
    "judul header harus berukuran besar (>=1.1rem), bukan teks kecil"
assert 'Daftar Revisi Dokumen' in html, "HTML tak memuat judul keterangan halaman"
print("[5b] keterangan header halaman (judul saja, font besar) OK")


# --- 6. Sidebar: tombol tepat setelah Dashboard di grup Ringkasan ---
with open(BASE, encoding='utf-8') as f:
    base = f.read()
dash_pos = base.find("navigateTo('/dashboard')")
status_pos = base.find("navigateTo('/status-dokumen')")
assert dash_pos != -1 and status_pos != -1, "tombol Dashboard / Status Dokumen tak ada"
assert status_pos > dash_pos, "Status Dokumen harus SETELAH Dashboard"
# Harus berada dalam grup Ringkasan (sebelum section berikutnya).
ringkasan_pos = base.find('sidebar-section">Ringkasan')
next_section = base.find('sidebar-section">', ringkasan_pos + 10)
assert ringkasan_pos < status_pos < next_section, \
    "Status Dokumen harus di dalam grup Ringkasan (setelah Dashboard)"
# Label menu sidebar tetap 'Status Dokumen'.
assert '>Status Dokumen</span>' in base, "label menu sidebar harus tetap 'Status Dokumen'"
assert "activeText = 'Status Dokumen'" in base, "updateActiveNav tak memetakan /status-dokumen"
assert '>Status Dokumen</span>' in html, "HTML tak memuat label menu 'Status Dokumen'"
print("[6] sidebar: tombol 'Status Dokumen' di grup Ringkasan setelah Dashboard OK")

print("\nALL CHECKS PASSED")
