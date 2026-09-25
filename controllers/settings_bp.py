"""
CONTROLLER — Pengaturan: exclusion rules (kategori / rekanan) dari perhitungan.

Rows yang cocok tetap tampil di tabel tapi diabaikan dashboard + semua laporan.
"""
from flask import Blueprint, render_template, request, jsonify

import db
from constants import (
    CATEGORIES, EXCLUDED_CATEGORIES, EXCLUDED_REKANAN, save_excluded,
)

bp = Blueprint('settings', __name__)


@bp.route('/pengaturan')
def pengaturan():
    rekanan_db = sorted({(r.get('NAMA LEVELANSIR / REKANAN') or '').strip()
                         for r in db.read_data(None)
                         if (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()})
    # Names on the exclude list but absent from the DB must still render (removable).
    rekanan_all = sorted(set(rekanan_db) | set(EXCLUDED_REKANAN))
    return render_template(
        'settings.html',
        rekanan_list=rekanan_all,
        excluded_categories=EXCLUDED_CATEGORIES,
        excluded_rekanan=EXCLUDED_REKANAN,
    )


@bp.route('/api/settings/excluded', methods=['POST'])
def set_excluded():
    """Toggle one exclusion entry.

    Body: {"type": "kategori"|"rekanan", "name": str, "excluded": bool}.
    Mutates the live lists (same pattern as CATEGORIES) then persists config.json.
    """
    data = request.get_json(silent=True) or {}
    typ = data.get('type')
    name = (data.get('name') or '').strip()
    excluded = bool(data.get('excluded'))
    if not name:
        return jsonify({'error': 'Nama kosong'}), 400
    if typ not in ('kategori', 'rekanan'):
        return jsonify({'error': 'Tipe tidak valid'}), 400
    target = EXCLUDED_CATEGORIES if typ == 'kategori' else EXCLUDED_REKANAN
    if excluded and name not in target:
        target.append(name)
    elif not excluded and name in target:
        target.remove(name)
    save_excluded(EXCLUDED_CATEGORIES, EXCLUDED_REKANAN)
    return jsonify({
        'excluded_categories': EXCLUDED_CATEGORIES,
        'excluded_rekanan': EXCLUDED_REKANAN,
    })
