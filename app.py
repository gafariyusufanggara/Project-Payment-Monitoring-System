"""
Monitoring Hutang Reguler - Web App (MVC layout)
-------------------------------------------------
  app.py             → entry point (app factory + run)
  controllers/       → routes (Blueprints)
  services/          → business logic (model layer)
  db.py / constants  → data + config
  templates/         → view layer

Run: python app.py   Open: http://localhost:5000
"""
import os
from datetime import timedelta

from flask import Flask, redirect, request, url_for

import db
from db_audit import init_audit_db
from services.excel_import import migrate_from_excel

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'hutang-monitoring-2026')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

# ── Register controllers (Blueprints) ───────────────────
from controllers.main import bp as main_bp
from controllers.auth_bp import bp as auth_bp
from controllers.import_bp import bp as import_bp
from controllers.laporan_bp import bp as laporan_bp
from controllers.verification_bp import bp as verifikasi_bp
from controllers.cicilan_bp import bp as cicilan_bp
from controllers.project_bp import bp as project_bp
from controllers.contract_bp import bp as contract_bp
from controllers.settings_bp import bp as settings_bp

app.register_blueprint(main_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(import_bp)
app.register_blueprint(laporan_bp)
app.register_blueprint(verifikasi_bp)
app.register_blueprint(cicilan_bp)
app.register_blueprint(project_bp)
app.register_blueprint(contract_bp)
app.register_blueprint(settings_bp)


# ── Jinja filter: format money (Indonesian locale, no Rp prefix, no decimals) ──
@app.template_filter('money')
def _money_filter(val):
    """Format a number with dot separators (ID locale). E.g. 1000000 → 1.000.000"""
    try:
        v = int(float(val or 0))
        return '{:,}'.format(v).replace(',', '.')
    except (ValueError, TypeError):
        return '0'


# ── Jinja filter: money, but show - instead of 0 (data-invoice table) ──
@app.template_filter('money0')
def _money0_filter(val):
    """Same as money, but renders - when the value is zero/empty."""
    try:
        v = float(val or 0)
    except (ValueError, TypeError):
        v = 0
    if v == 0:
        return '-'
    return '{:,}'.format(int(v)).replace(',', '.')


# ── Jinja filter: format date YYYY-MM-DD → 10 Mar 2026 ──
@app.template_filter('tgl')
def _tgl_filter(val):
    """Format YYYY-MM-DD to Indonesian short date. Empty/invalid → '—'."""
    from constants import parse_date
    d = parse_date(val)
    if not d:
        return '—'
    bulan = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
             'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
    return f'{d.day} {bulan[d.month]} {d.year}'


# ── Context processor: inject notif badge count on every request ──
@app.context_processor
def inject_notif_counts():
    """Provide verification notif counts + edit-modal globals to all templates."""
    from services.verification import get_counts
    from constants import (
        FORM_FIELDS, DATE_FIELDS, NUMERIC_FIELDS, CATEGORIES, STATUS_DPP, STATUS_PPN,
        EXCLUDED_CATEGORIES, EXCLUDED_REKANAN,
    )
    from db_project import get_project_select
    counts = get_counts()
    import db_audit
    audit_total = db_audit.get_audit_count()
    # Active project scope (session) — 'all' = consolidated view across projects.
    from services.project_context import get_active_project_id, get_read_filter
    from constants import (
        load_last_import as _load_imp, format_update_label as _fmt_upd,
        format_update_detail as _fmt_upd_d,
    )
    _inv_map, _ktk_map = _load_imp()
    _rf = get_read_filter()
    if _rf is None:
        _inv_ts = max(_inv_map.values()) if _inv_map else ''
        _ktk_ts = max(_ktk_map.values()) if _ktk_map else ''
    else:
        _k = str(_rf)
        _inv_ts = _inv_map.get(_k, '')
        _ktk_ts = max([t for t in (_ktk_map.get(_k, ''), _ktk_map.get('', '')) if t], default='')
    _latest = max([t for t in (_inv_ts, _ktk_ts) if t], default='')
    _upd_tip = []
    if _inv_ts:
        _upd_tip.append('Invoice: ' + _fmt_upd_d(_inv_ts))
    if _ktk_ts:
        _upd_tip.append('Kontrak: ' + _fmt_upd_d(_ktk_ts))
    cat_n = len(EXCLUDED_CATEGORIES)
    rek_n = len(EXCLUDED_REKANAN)
    exc_rows = 0
    if cat_n + rek_n > 0:
        import db as _db
        from constants import is_excluded_row as _is_exc
        try:
            exc_rows = sum(1 for r in _db.read_data(get_read_filter()) if _is_exc(r))
        except Exception:
            exc_rows = 0
    def _short(names, limit=5):
        names = list(names)
        if len(names) <= limit:
            return ', '.join(names)
        return ', '.join(names[:limit]) + f' (+{len(names) - limit} lainnya)'
    _tip = []
    if cat_n:
        _tip.append('Kategori: ' + _short(EXCLUDED_CATEGORIES))
    if rek_n:
        _tip.append('Rekanan: ' + _short(EXCLUDED_REKANAN))
    return {
        'update_label': _fmt_upd(_latest),
        'update_inv_ts': _inv_ts,
        'update_ktk_ts': _ktk_ts,
        'update_detail_inv': _fmt_upd_d(_inv_ts),
        'update_detail_ktk': _fmt_upd_d(_ktk_ts),
        'update_tip': ' | '.join(_upd_tip),
        'exclude_cat_count': cat_n,
        'exclude_rek_count': rek_n,
        'exclude_row_count': exc_rows,
        'exclude_tip': ' | '.join(_tip),
        'verification_total': counts['total_issues'],
        'verification_critical': counts['critical_count'],
        'verification_completion': counts['completion_count'],
        'verification_warning': counts['warning_count'],
        'audit_total': audit_total,
        'form_fields': FORM_FIELDS,
        'date_fields': DATE_FIELDS,
        'numeric_fields': NUMERIC_FIELDS,
        'categories': CATEGORIES,
        'status_dpp': STATUS_DPP,
        'status_ppn': STATUS_PPN,
        'project_list': get_project_select(),
        'active_project_id': get_active_project_id(),
    }


# ── Auth guard: semua route butuh login kecuali /login + static ──
@app.before_request
def _require_login():
    from services.auth import is_authed
    if request.endpoint in (None, 'auth.login', 'static'):
        return None
    if request.path == '/login':
        return None
    if is_authed():
        return None
    if request.headers.get('HX-Request') == 'true':
        resp = redirect(url_for('auth.login', next=request.path))
        resp.headers['HX-Refresh'] = 'true'
        return resp
    return redirect(url_for('auth.login', next=request.path))


# ── HTMX: dorong URL ke history browser untuk navigasi sidebar ──
# htmx.ajax() di HTMX 2.0.4 mengabaikan opsi pushUrl, sehingga address bar
# tidak berubah dan highlight menu (yang membaca location.pathname) basi.
# Header HX-Push-Url adalah mekanisme bawaan HTMX yang didukung.
@app.after_request
def _hx_push_url(response):
    if request.headers.get('HX-Request') == 'true':
        response.headers['HX-Push-Url'] = request.path
    return response


def init_db_all():
    data_dir = os.environ.get('DATA_DIR')
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
    db.init_db()
    init_audit_db()
    from db_ignore import init_ignore_db
    init_ignore_db()
    from db_project import init_project_tables
    init_project_tables()
    from db_contract import init_contract_tables
    init_contract_tables()
    if os.environ.get('DISABLE_EXCEL_AUTOMIGRATE') != '1':
        migrate_from_excel()


if __name__ == '__main__':
    init_db_all()
    print(f'\n[APP] Project Financial Monitoring System')
    print(f'[APP] Database: {db.DB_FILE}')
    print(f'[APP] Buka browser: http://localhost:5000\n')
    app.run(debug=True, host='0.0.0.0', port=5000)
