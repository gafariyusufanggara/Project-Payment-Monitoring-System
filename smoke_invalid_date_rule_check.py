import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.verification import _is_invalid_date

fail = []


def case(val, expected, label):
    got = _is_invalid_date(val)
    ok = got == expected
    print(f"{'OK ' if ok else 'FAIL'} {label}: {val!r} -> {got} (harap {expected})")
    if not ok:
        fail.append(label)


case('036/BNI/10/26', True, 'nomor bukti di kolom tanggal')
case('14/10/2026', True, 'format DD/MM/YYYY bukan ISO')
case('2026-02-31', True, 'tanggal mustahil (kalender)')
case('2026-13-01', True, 'bulan 13')
case('abc', True, 'teks bebas')
case('-', False, 'placeholder strip')
case('', False, 'kosong')
case(None, False, 'None')
case('   ', False, 'spasi saja')
case('2026-11-14', False, 'ISO sah')
case('2026-11-14 00:00:00', False, 'ISO + jam')
case('2026-11-14T00:00:00', False, 'ISO + T')

print()
if fail:
    print(f'GAGAL: {fail}')
    sys.exit(1)
print('SEMUA LOLOS - _is_invalid_date')
