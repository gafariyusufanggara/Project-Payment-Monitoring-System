# -*- coding: utf-8 -*-
"""Smoke check: halaman form proyek (project_detail.html — tambah/ubah).

Memverifikasi tata letak & komponen UI baru:
- memakai stylesheet bersama static/css/project.css;
- toolbar: tombol kembali + badge status berdot + tautan Dashboard;
- form terbagi 3 grup: Identitas, Kontrak & Jadwal, Catatan;
- field wajib (kode_proyek, nama_proyek) tetap `required`;
- chip nilai kontrak diberi catatan "akumulasi kontrak vendor" agar tidak
  disalahbandingkan dengan realisasi;
- sidebar ringkasan memuat Realisasi & Sisa Hutang yang sama dgn daftar proyek;
- zona hapus dipisah, mengirim ke form tersembunyi (bukan <form> bersarang);
- TIDAK ada <form> bersarang (HTML tidak valid) di seluruh dokumen;
- alur POST action=delete benar-benar menghapus — diuji pada SALINAN DB.

PENTING: seluruh uji mutasi memakai DATA_DIR ke salinan sementara. Database
nyata tidak pernah disentuh.

Run:  python smoke_project_detail_page_check.py
"""
import os
import re
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

LIVE_DB = os.path.join(ROOT, 'monitoring_hutang.db')
assert os.path.exists(LIVE_DB), f'DB tidak ditemukan: {LIVE_DB}'

# ── Siapkan salinan DB terpisah SEBELUM mengimpor modul aplikasi ──
# Aplikasi memakai beberapa berkas DB (monitoring_hutang, _audit, _ignore, ...).
# Semua disalin agar salinan berperilaku sama persis dgn aslinya.
TMP_DIR = tempfile.mkdtemp(prefix='prj_detail_check_')
TMP_DB = os.path.join(TMP_DIR, 'monitoring_hutang.db')
_db_files = [f for f in os.listdir(ROOT) if f.endswith('.db')]
assert 'monitoring_hutang.db' in _db_files, 'monitoring_hutang.db tidak ditemukan'
for _f in _db_files:
    shutil.copy2(os.path.join(ROOT, _f), os.path.join(TMP_DIR, _f))
os.environ['DATA_DIR'] = TMP_DIR

import app as appmod  # noqa: E402  (harus setelah DATA_DIR di-set)
import db_project  # noqa: E402
from services.auth import SESSION_KEY  # noqa: E402

app = appmod.app
app.config['TESTING'] = True

# Pastikan modul DB benar-benar menunjuk salinan, bukan DB nyata.
assert os.path.abspath(db_project.DB_FILE) == os.path.abspath(TMP_DB), (
    f'db_project.DB_FILE = {db_project.DB_FILE}, bukan salinan {TMP_DB}')

PROJECTS = db_project.get_projects()
assert PROJECTS, 'salinan DB tidak berisi proyek — smoke check tidak bermakna'
P = PROJECTS[0]
money_f = app.jinja_env.filters['money']


def client():
    c = app.test_client()
    with c.session_transaction() as s:
        s[SESSION_KEY] = True
    return c


def body_of(html):
    s = re.sub(r'<style>.*?</style>', '', html, flags=re.S)
    return re.sub(r'<!--.*?-->', '', s, flags=re.S)


with client() as c:
    r_edit = c.get(f"/project/{P['id']}/edit")
    r_new = c.get('/project/create')
assert r_edit.status_code == 200, f"GET edit -> {r_edit.status_code}"
assert r_new.status_code == 200, f"GET create -> {r_new.status_code}"
edit_html = r_edit.get_data(as_text=True)
new_html = r_new.get_data(as_text=True)
edit_body, new_body = body_of(edit_html), body_of(new_html)

# ── 1. Stylesheet bersama dipakai ──
for name, html in (('edit', edit_html), ('create', new_html)):
    assert 'css/project.css' in html, f'{name}: static/css/project.css tidak dimuat'
    assert 'prj-page' in html, f'{name}: kerangka .prj-page tidak dipakai'
print('[1] css/project.css dimuat & kerangka .prj-page dipakai (edit + create)')

# ── 2. Toolbar: kembali, badge status berdot, tautan Dashboard ──
assert '/project/' in edit_body, 'tombol kembali ke daftar proyek hilang'
assert 'prj-badge' in edit_body, 'badge status berdot hilang'
assert P['status'] in edit_body, 'teks status tidak tampil'
assert '/dashboard' in edit_body, 'tautan Dashboard hilang di toolbar'
# halaman "create" belum punya proyek -> tidak boleh ada TAUTAN Dashboard.
# Dicek pada elemen <a href> di area konten (bukan seluruh dokumen: sidebar &
# inline JS base.html memang menyebut '/dashboard').
_main = new_body[new_body.find('aria-label="Informasi proyek"'):]
_hrefs = re.findall(r'<a\b[^>]*href="([^"]*)"', _main)
assert not any('/dashboard' in h for h in _hrefs), \
    f'halaman Proyek Baru tidak boleh punya tautan Dashboard: {_hrefs}'
print('[2] toolbar: kembali + badge status + Dashboard (create tanpa Dashboard)')

# ── 3. Tiga grup form berurutan ──
groups = re.findall(r'class="prj-group-label"[^>]*>\s*([^<]+?)\s*</h2>', edit_body)
assert groups == ['Identitas', 'Kontrak &amp; Jadwal', 'Catatan'] or \
       groups == ['Identitas', 'Kontrak & Jadwal', 'Catatan'], f'grup form: {groups}'
print(f'[3] 3 grup form berurutan: {" -> ".join(groups)}')

# ── 4. Field wajib tetap required ──
for fid in ('kode_proyek', 'nama_proyek'):
    m = re.search(r'<input[^>]*id="%s"[^>]*>' % fid, edit_body)
    assert m, f'input #{fid} tidak ditemukan'
    assert 'required' in m.group(0), f'#{fid} kehilangan atribut required'
print('[4] kode_proyek & nama_proyek tetap required')

# ── 5. Nilai kontrak: input + catatan basis ──
assert 'nilai_kontrak' in edit_body, 'input nilai_kontrak hilang'
assert 'akumulasi kontrak vendor' in edit_body, \
    'catatan "akumulasi kontrak vendor" hilang (mencegah salah banding dgn realisasi)'
print('[5] input nilai kontrak + catatan basis tersedia')

# ── 6. Sidebar ringkasan: angka sama dgn daftar proyek ──
for lbl, val in (('Realisasi', P['total_realisasi']), ('Sisa Hutang', P['total_sisa'])):
    assert lbl in edit_body, f'ringkasan "{lbl}" hilang di sidebar'
    assert money_f(val) in edit_body, \
        f'ringkasan "{lbl}" tidak menampilkan {money_f(val)}'
assert money_f(P['nilai_kontrak']) in edit_body, 'nilai kontrak tidak tampil di ringkasan'
print('[6] sidebar ringkasan konsisten dgn angka daftar proyek')

# ── 7. Zona hapus dipisah + pakai form tersembunyi ──
assert 'pdt-danger' in edit_body, 'zona hapus (pdt-danger) hilang'
assert 'pdtDeleteForm' in edit_html, 'form tersembunyi utk hapus tidak ada'
assert 'name="action" value="delete"' in edit_html.replace("'", '"'), \
    'input action=delete tidak ditemukan pada form tersembunyi'
assert 'submitDelete' in edit_html, 'handler submitDelete tidak ada'
print('[7] zona hapus terpisah & memakai form tersembunyi')

# ── 8. Tidak ada <form> bersarang (HTML tidak valid) ──
# Komentar HTML & isi <script> dibuang dulu: keduanya boleh menyebut "<form>"
# sebagai teks (mis. komentar penjelas) dan bukan markup nyata.
def markup_only(html):
    s = re.sub(r'<script\b.*?</script>', '', html, flags=re.S | re.I)
    return re.sub(r'<!--.*?-->', '', s, flags=re.S)


for name, html in (('edit', edit_html), ('create', new_html)):
    m = markup_only(html)
    opens = len(re.findall(r'<form\b', m, flags=re.I))
    closes = len(re.findall(r'</form>', m, flags=re.I))
    assert opens == closes, f'{name}: <form> {opens} vs </form> {closes}'
    depth = 0
    for tok in re.finditer(r'<form\b|</form>', m, flags=re.I):
        depth += 1 if tok.group(0).lower().startswith('<form') else -1
        assert depth <= 1, f'{name}: terdeteksi <form> bersarang'
        assert depth >= 0, f'{name}: ada </form> berlebih'
print('[8] tidak ada <form> bersarang (HTML valid)')

# ── 9. POST action=delete benar-benar menghapus (pada SALINAN DB) ──
pid = P['id']
with client() as c:
    r = c.post(f'/project/{pid}/edit', data={'action': 'delete'})
assert r.status_code == 302, f'POST delete -> {r.status_code}, harusnya 302'
assert db_project.get_project(pid) is None, 'proyek belum terhapus di salinan DB'
con = sqlite3.connect(TMP_DB)
n_left = con.execute('SELECT COUNT(*) FROM hutang WHERE project_id = ?',
                     (str(pid),)).fetchone()[0]
con.close()
assert n_left == 0, f'masih ada {n_left} baris hutang ber-project_id {pid}'
print('[9] POST action=delete menghapus proyek & melepas tautan hutang (salinan DB)')

# ── 10. DB nyata tidak tersentuh ──
con_live = sqlite3.connect(LIVE_DB)
n_live = con_live.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
linked = con_live.execute("SELECT COUNT(*) FROM hutang WHERE project_id != ''").fetchone()[0]
con_live.close()
assert n_live >= 1, 'DB NYATA kehilangan proyek — seharusnya tidak tersentuh!'
assert linked >= 1, 'DB NYATA kehilangan relasi hutang — seharusnya tidak tersentuh!'
print(f'[10] DB nyata utuh ({n_live} proyek, {linked} hutang ter-relasi)')

shutil.rmtree(TMP_DIR, ignore_errors=True)
print('\nALL CHECKS PASSED')
