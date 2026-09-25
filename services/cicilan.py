"""
MODEL — Invoice Cicilan (installment) detection.

Aturan: nomor INVOICE sama (NO INVOICE) tapi VOLUME PROGRESS != 1 (<1)
=> cicilan. Dibedakan suffix .01/.02/-01 di NO INVOICE INTERNAL.
Grouping pakai NO INVOICE base (bukan effective_invoice bersuffix) agar
tidak terpecah jadi 1-row.
"""
import re
from collections import OrderedDict

import db
from constants import safe_float, effective_invoice


def _base_invoice(row):
    raw = (row.get('NO INVOICE') or '').strip()
    if raw:
        return raw
    inv = effective_invoice(row)
    m = re.match(r'^(.*)[.\-]\d+$', inv)
    return m.group(1) if m else inv


def get_cicilan_data(project_id=None):
    data = db.read_data(project_id=project_id)
    groups = OrderedDict()

    for row in data:
        rekan = (row.get('NAMA LEVELANSIR / REKANAN') or '').strip()
        base = _base_invoice(row)
        if not base:
            continue
        key = (rekan, base)

        if key not in groups:
            groups[key] = {
                'rekanan': rekan,
                'invoice': base,
                'invoice_internal': (row.get('NO INVOICE INTERNAL') or '').strip(),
                'row_count': 0,
                'harga_excl': safe_float(row.get('HARGA (EXLD)')),
                'harga_satuan': safe_float(row.get('HARGA SATUAN')),
                'dpp_total': 0,
                'total_bayar_dpp': 0,
                'payments': [],
                'volumes': [],
            }
        g = groups[key]
        g['row_count'] += 1
        bayar = safe_float(row.get('PEMBAYARAN DPP'))
        harga_row = safe_float(row.get('HARGA (EXLD)'))
        g['dpp_total'] += harga_row
        g['total_bayar_dpp'] += bayar
        vol_raw = (row.get('VOLUME PROGRESS') or '').strip()
        try:
            vol_f = float(vol_raw) if vol_raw else 1.0
        except (ValueError, TypeError):
            vol_f = 1.0
        g['volumes'].append(vol_f)
        g['payments'].append({
            'amount': bayar,
            'no_po': (row.get('NO PO / KONTRAK') or '').strip(),
            'deskripsi': (row.get('DESKRIPSI') or '').strip(),
            'volume': vol_raw,
            'harga_excl': harga_row,
            'sisa': max(0, harga_row - bayar),
        })

    cicilan = []
    for g in groups.values():
        if g['row_count'] <= 1:
            continue
        has_cicilan_vol = any(v < 1 - 1e-9 for v in g['volumes'])
        if not has_cicilan_vol:
            continue
        g['sisa_dpp'] = max(0, g['dpp_total'] - g['total_bayar_dpp'])
        del g['volumes']
        cicilan.append(g)

    cicilan.sort(key=lambda g: (g['rekanan'].lower(), g['invoice'].lower()))
    return cicilan
