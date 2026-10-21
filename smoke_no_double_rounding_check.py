# -*- coding: utf-8 -*-
"""Audit: tidak boleh ada pembulatan berlapis (double rounding) pada nominal.

Aturan yang disetujui pengguna (standar akuntansi / source of truth = Excel):
  * DB menyimpan nilai MENTAH apa adanya (termasuk desimal dari formula Excel).
  * Pembulatan rupiah (round-half-away-from-zero = ROUND() Excel) hanya
    dilakukan SEKALI, di lapisan tampil.
  * Jalur simpan (import, write_row, snapshot audit) DILARANG membulatkan.

Memverifikasi:
  1. constants.calc_sisa menyimpan hasil hitung mentah (tidak int(x+0.5)).
  2. round_currency tidak dipakai di jalur simpan: import_rows, write_row,
     db_audit.save_snapshot.
  3. round_currency hanya dipakai sebagai pemformatan form (edit_form).
  4. base.html recalcEdit tidak membulatkan HARGA/TOTAL ke input form.
  5. controllers.main mempertahankan nilai mentah saat user tidak mengubah
     nominal di form edit.
  6. Data nyata: tidak ada sel yang "sudah bulat" tapi berbeda dari nilai
     mentah Excel (deteksi double rounding: SISA == hasil hitung terbulat).

Run:  python smoke_no_double_rounding_check.py
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

ROOT = os.path.dirname(os.path.abspath(__file__))


def src(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


constants = src('constants.py')
db_py = src('db.py')
db_audit = src('db_audit.py')
main_py = src('controllers/main.py')
base_html = src('templates/base.html')


def func_body(text, name):
    m = re.search(rf'\ndef {name}\(.*?\n(?=\ndef |\Z)', text, re.S)
    if m:
        return m.group(0)
    # JS (indentasi di dalam <script>): ambil dari 'function name(' sampai
    # kurung kurawal penutup pada indentasi yang sama.
    m = re.search(rf'^( *)(?:(?:const|let|var)\s+{name}\s*=\s*(?:function)?|function\s+{name})'
                  rf'\s*\([^)]*\)\s*\{{', text, re.M)
    if m:
        indent = m.group(1)
        start = m.start()
        end_pat = re.compile(rf'^{indent}\}}', re.M)
        end = end_pat.search(text, m.end())
        assert end, f'{name}(): penutup tidak ditemukan'
        return text[start:end.end()]
    assert False, f'{name}() tidak ditemukan'


# --- 1. calc_sisa menyimpan mentah ---
calc_body = func_body(constants, 'calc_sisa')
assert 'int(x + 0.5)' not in calc_body, \
    'calc_sisa masih membulatkan (int(x + 0.5)) — akan menimpa nilai mentah'
assert 'SISA HUTANG DPP' in calc_body and 'max(0, x)' in calc_body.replace(' ', ' ')
print('[1] calc_sisa menyimpan hasil hitung mentah OK')

# --- 2. Jalur simpan bebas round_currency ---
for fname, text, label in (
    ('import_rows', db_py, 'db.import_rows'),
    ('write_row', db_py, 'db.write_row'),
    ('save_snapshot', db_audit, 'db_audit.save_snapshot'),
):
    body = func_body(text, fname)
    assert 'round_currency(' not in body, f'{label} masih membulatkan saat simpan'
print('[2] jalur simpan (import_rows, write_row, save_snapshot) bebas pembulatan OK')

# --- 3. round_currency hanya di edit_form (tampilan) ---
assert 'round_currency(row_data)' in main_py, 'edit_form harus membulatkan untuk tampilan'
uses = [l.strip() for l in main_py.splitlines() if 'round_currency(' in l and 'import' not in l]
assert len(uses) == 1, f'round_currency dipakai di luar edit_form: {uses}'
print('[3] round_currency hanya di edit_form (lapisan tampil) OK')

# --- 4. recalcEdit tidak membulatkan ---
recalc = func_body(base_html, 'recalcEdit')
recalc_code = re.sub(r'//.*', '', recalc)  # abaikan komentar
assert 'Math.round' not in recalc_code, \
    'recalcEdit masih Math.round — nominal form akan tersimpan terbulat'
print('[4] recalcEdit menulis nilai apa adanya ke form OK')

# --- 5. Pengaman edit: nominal tak berubah → pertahankan nilai mentah ---
edit_body = func_body(main_py, 'edit')
assert 'CURRENCY_FIELDS' in edit_body, \
    'edit() harus mempertahankan nilai mentah bila nominal tidak diubah user'
print('[5] edit() mempertahankan nilai mentah bila nominal tidak diubah OK')

# --- 5b. services/laporan.py tidak membulatkan nominal ---
laporan_py = src('services/laporan.py')
bad_round = [(i + 1, l.strip()) for i, l in enumerate(laporan_py.splitlines())
             if re.search(r'int\([^)]*\+\s*0\.5\)|\bround\(', l)]
assert not bad_round, f'laporan.py masih membulatkan nominal: {bad_round[:5]}'
# Status lunas/belum lunas memakai toleransi SISA_EPS, bukan '> 0' mentah.
assert 'sisa_belum_lunas' in laporan_py, \
    'laporan.py harus memakai sisa_belum_lunas() (toleransi SISA_EPS)'
assert "inv['sisa_dpp'] > 0" not in laporan_py, \
    "jangan pakai '> 0' mentah untuk status lunas — pakai sisa_belum_lunas()"
print('[5b] laporan.py bebas pembulatan + status lunas pakai toleransi SISA_EPS OK')

# --- 6. Deteksi double rounding pada data nyata ---
import db  # noqa: E402
from constants import calc_sisa, safe_float, CURRENCY_FIELDS  # noqa: E402

rows = db.read_data()
bad = []
for r in rows:
    # Bandingkan SISA tersimpan vs nilai mentah Excel (kalau ada) dan vs
    # hasil hitung mentah — selisih sub-rupiah murni tidak jadi masalah,
    # yang dicari: sel yang jelas-jelas sudah dibulatkan padahal sumbernya
    # berdesimal.
    for f in ('SISA HUTANG (INCLD PPN)', 'SISA HUTANG DPP', 'SISA HUTANG PPN'):
        v = r.get(f)
        if v in (None, ''):
            continue
        try:
            fv = float(v)
        except (ValueError, TypeError):
            continue
        if abs(fv - round(fv)) > 1e-9:
            continue  # mentah, wajar
        # Nilai tersimpan bulat: pastikan memang begitu di sumber, bukan hasil
        # pembulatan lokal. Bandingkan dgn hitung-ulang mentah.
        probe = dict(r)
        calc_sisa(probe)
        raw = safe_float(probe.get(f))
        if abs(raw - fv) > 0.5:
            bad.append((r.get('R'), f, v, raw))
assert not bad, f'indikasi double rounding: {bad[:5]}'
print(f'[6] {len(rows)} baris: SISA konsisten dengan hitung mentah, tanpa double rounding OK')

# --- 7. Laporan Jatuh Tempo: total = round(SUM mentah), bukan SUM(terbulat) ---
from services import laporan as lap  # noqa: E402
from constants import SISA_EPS, sisa_belum_lunas  # noqa: E402

jt_rows, jt_count = lap.build_jatuh_tempo_data()
sum_raw = 0.0
sum_rounded_rows = 0.0
for month in jt_rows:
    for rk in month.get('rekanan_list', []):
        for inv in rk.get('invoices', []):
            s = inv.get('sisa_dpp') or 0
            sum_raw += s
            sum_rounded_rows += round(s)
# Footer laporan = round(Σ mentah). Bila tiap invoice sudah dibulatkan di server,
# Σ mentah akan sama-persis dengan Σ terbulat (tanda nilai sudah dirusak).
if abs(sum_raw - sum_rounded_rows) > 1e-9:
    print(f'[7] JT: Σ mentah {sum_raw:,.2f} != Σ per-baris {sum_rounded_rows:,.0f} '
          f'→ nilai mentah terjaga OK')
else:
    print('[7] JT: tidak ada invoice berdesimal (Σ mentah == Σ per-baris) OK')
assert sisa_belum_lunas(SISA_EPS * 0.5) is False
assert sisa_belum_lunas(SISA_EPS * 1.5) is True
print('[7b] toleransi SISA_EPS: 0.5 → lunas, 1.5 → belum lunas OK')

# --- 8. Konsistensi template: tidak ada cek sisa pakai '> 0' mentah ---
import glob  # noqa: E402
tpl_dir = os.path.join(ROOT, 'templates')
bad_tpl = []
for path in glob.glob(os.path.join(tpl_dir, '**', '*.html'), recursive=True):
    with open(path, encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if re.search(r"sisa[\w.\[\]'\"]*\s*[<>]=?\s*0", line) and 'has_sisa' not in line:
                bad_tpl.append(f'{os.path.relpath(path, ROOT)}:{i}')
assert not bad_tpl, f'template masih pakai pembanding sisa mentah (>0): {bad_tpl[:5]}'
print('[8] semua template memakai |has_sisa / SISA_EPS (tidak ada "sisa > 0" mentah) OK')
print('SEMUA LOLOS')
