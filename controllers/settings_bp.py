"""
CONTROLLER — Exclude Invoice: exclusion rules (kategori / rekanan) dari perhitungan.

Rows yang cocok tetap tampil di tabel tapi diabaikan dashboard + semua laporan.
Daftar exclude disimpan di Flask session (per browser), bukan config global.
"""
from flask import Blueprint, render_template, request, jsonify

import db
from constants import CATEGORIES
from services.exclusion import (
    get_excluded_categories, get_excluded_rekanan, set_excluded as set_exclusion,
)

bp = Blueprint('settings', __name__)


@bp.route('/exclude-invoice')
def exclude_invoice():
    rekanan_db = sorted({(r.get('NAMA LEVELANSIR / REKANAN') or '').strip()
                         for r in db.read_data(None)
                         if (r.get('NAMA LEVELANSIR / REKANAN') or '').strip()})
    # Names on the exclude list but absent from the DB must still render (removable).
    rekanan_all = sorted(set(rekanan_db) | set(get_excluded_rekanan()))
    return render_template(
        'settings.html',
        rekanan_list=rekanan_all,
        excluded_categories=get_excluded_categories(),
        excluded_rekanan=get_excluded_rekanan(),
    )


@bp.route('/api/settings/excluded', methods=['POST'])
def set_excluded():
    """Toggle one exclusion entry.

    Body: {"type": "kategori"|"rekanan", "name": str, "excluded": bool}.
    Mutates the session list then persists via the session cookie.
    """
    data = request.get_json(silent=True) or {}
    typ = data.get('type')
    name = (data.get('name') or '').strip()
    excluded = bool(data.get('excluded'))
    if not name:
        return jsonify({'error': 'Nama kosong'}), 400
    if typ not in ('kategori', 'rekanan'):
        return jsonify({'error': 'Tipe tidak valid'}), 400
    set_exclusion(typ, name, excluded)
    return jsonify({
        'excluded_categories': get_excluded_categories(),
        'excluded_rekanan': get_excluded_rekanan(),
    })
