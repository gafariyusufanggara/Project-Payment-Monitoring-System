import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db
from services.verification import (check_row, _is_invalid_date, DATE_FIELDS)

data = db.read_data()
bad = []
for row in data:
    for col in DATE_FIELDS:
        if _is_invalid_date(row.get(col)):
            bad.append((row.get('R'), (row.get('NAMA LEVELANSIR / REKANAN') or '')[:32], col, row.get(col)))

print(f'[1] baris dengan tanggal tidak sah: {len(bad)}')
for r in bad:
    print('   ', r)

# R-195 harus CRITICAL
target = next((row for row in data if '036/BNI/10/26' in str(row.get('TGL BAYAR DPP') or '')), None)
assert target, 'baris contoh (036/BNI/10/26) tidak ditemukan'
level, reasons = check_row(target)
print(f"[2] R-{target.get('R')} level={level}")
print('    reasons:', reasons)
assert level == 'CRITICAL', f'R-{target.get("R")} harus CRITICAL, dapat {level}'
assert any('bukan tanggal valid' in x for x in reasons), 'reason tanggal tidak valid tidak muncul'
assert any('Tgl Bayar DPP' in x for x in reasons), 'label Tgl Bayar DPP tidak muncul di reason'
print('[2] OK - R-195 CRITICAL dengan pill tanggal tidak valid')

# baris yang hanya berisi '-' di TGL FAKTUR PAJAK tidak boleh ter-flag karena aturan ini
dash_rows = [r for r in data if (r.get('TGL FAKTUR PAJAK') or '').strip() == '-']
false_pos = []
for r in dash_rows:
    _lv, _rs = check_row(r)
    if any('bukan tanggal valid' in x for x in _rs):
        false_pos.append(r.get('R'))
print(f"[3] baris '-' di TGL FAKTUR PAJAK: {len(dash_rows)}, false positive: {len(false_pos)}")
assert not false_pos, f"baris '-' ikut ter-flag: {false_pos[:10]}"
print('[3] OK - placeholder strip tidak dianggap error')

print()
print('ALL CHECKS PASSED')
