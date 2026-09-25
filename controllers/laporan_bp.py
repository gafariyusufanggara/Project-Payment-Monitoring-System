"""
CONTROLLER — Laporan routes (Blueprint).

View layer: renders laporan.html and serves the Excel export download.
"""

from datetime import datetime, date

from flask import Blueprint, render_template, send_file, request, jsonify

from services.laporan import build_laporan_data, build_mingguan_data, build_excel_export, build_weekly_excel_export, build_jatuh_tempo_data
from services.jt_excel import build_jt_excel
from services.laporan_ppn import build_ppn_data, build_ppn_mingguan_data

bp = Blueprint('laporan', __name__)


@bp.route('/laporan-bulanan')
def laporan():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    cutoff_str = request.args.get('cutoff', '').strip()
    cutoff_date = None
    if cutoff_str:
        try:
            cutoff_date = datetime.strptime(cutoff_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    report_rows, data_count = build_laporan_data(project_id=pid, cutoff_date=cutoff_date)
    months = [r['key'] for r in report_rows]
    active_month = request.args.get('month', '').strip()
    if not active_month or active_month not in months:
        active_month = months[-1] if months else ''
    # Partial mode: return only body HTML for fetch-based cutoff refresh
    # (rail Periode + Cut Off tinggal di parent, tak ikut di-replace)
    if request.args.get('partial') == '1':
        return render_template('partials/_laporan_bulanan_body.html',
                               report_rows=report_rows,
                               data_count=data_count,
                               months=months,
                               cutoff=cutoff_str,
                               active_month=active_month), {'X-LP-Period': active_month}
    return render_template('laporan_bulanan.html',
                           report_rows=report_rows,
                           data_count=data_count,
                           months=months,
                           cutoff=cutoff_str,
                           active_month=active_month)


@bp.route('/laporan-bulanan/data')
def laporan_data():
    """JSON API for client-side cutoff filter without page refresh."""
    from services.project_context import get_read_filter
    pid = get_read_filter()
    cutoff_str = request.args.get('cutoff', '').strip()
    cutoff_date = None
    if cutoff_str:
        try:
            cutoff_date = datetime.strptime(cutoff_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass
    report_rows, data_count = build_laporan_data(project_id=pid, cutoff_date=cutoff_date)
    months = [r['key'] for r in report_rows]
    return jsonify({
        'report_rows': report_rows,
        'data_count': data_count,
        'months': months,
    })


@bp.route('/laporan-mingguan')
def laporan_mingguan():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    report_rows, data_count = build_mingguan_data(project_id=pid)
    return render_template('laporan_mingguan.html',
                           report_rows=report_rows,
                           data_count=data_count)


@bp.route('/laporan-bulanan/export')
def laporan_export():
    from services.project_context import get_read_filter
    month_key = request.args.get('month') or None
    buf = build_excel_export(month_key=month_key, project_id=get_read_filter())
    month_label = month_key or datetime.now().strftime('%Y-%m')
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'LBP_Monitoring_Hutang_{month_label}.xlsx',
    )


@bp.route('/laporan-mingguan/export')
def laporan_mingguan_export():
    from services.project_context import get_read_filter
    week_key = request.args.get('week') or None
    buf = build_weekly_excel_export(week_key=week_key, project_id=get_read_filter())
    label = week_key or datetime.now().strftime('%Y-W%V')
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'LBP_Mingguan_Hutang_{label}.xlsx',
    )


@bp.route('/laporan-jatuh-tempo/export')
def laporan_jatuh_tempo_export():
    from services.project_context import get_read_filter
    month_key = request.args.get('month') or None
    buf = build_jt_excel(month_key=month_key, project_id=get_read_filter())
    label = month_key or date.today().strftime('%Y-%m')
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'Jatuh_Tempo_Monitoring_Hutang_{label}.xlsx',
    )


@bp.route('/laporan-jatuh-tempo')
def laporan_jatuh_tempo():
    from services.project_context import get_read_filter
    report_rows, data_count = build_jatuh_tempo_data(project_id=get_read_filter())
    now_key = date.today().strftime('%Y-%m')
    months = [r['key'] for r in report_rows]
    current_month = now_key if now_key in months else (months[-1] if months else '')
    return render_template('laporan_jatuh_tempo.html',
                           report_rows=report_rows,
                           data_count=data_count,
                           current_month=current_month)


@bp.route('/laporan-ppn')
def laporan_ppn():
    from services.project_context import get_read_filter
    report_rows, data_count = build_ppn_data(project_id=get_read_filter())
    now_key = date.today().strftime('%Y-%m')
    months = [r['key'] for r in report_rows]
    current_month = now_key if now_key in months else (months[-1] if months else '')
    return render_template('laporan_ppn.html',
                           report_rows=report_rows,
                           data_count=data_count,
                           current_month=current_month)


@bp.route('/laporan-ppn/export')
def laporan_ppn_export():
    from services.laporan_ppn import build_ppn_excel_export
    from services.project_context import get_read_filter
    month_key = request.args.get('month') or None
    buf = build_ppn_excel_export(month_key=month_key, project_id=get_read_filter())
    month_label = month_key or date.today().strftime('%Y-%m')
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'LPPN_Monitoring_Hutang_{month_label}.xlsx',
    )


@bp.route('/laporan-ppn-mingguan')
def laporan_ppn_mingguan():
    from services.project_context import get_read_filter
    report_rows, data_count = build_ppn_mingguan_data(project_id=get_read_filter())
    weeks = [r['key'] for r in report_rows]
    # Deep link: ?week=YYYY-Www preselects that week.
    week_key = request.args.get('week', '').strip()
    if not week_key or week_key not in weeks:
        week_key = weeks[-1] if weeks else ''
    return render_template('laporan_ppn_mingguan.html',
                           report_rows=report_rows,
                           data_count=data_count,
                           current_week=week_key)


@bp.route('/laporan-ppn-mingguan/export')
def laporan_ppn_mingguan_export():
    from services.laporan_ppn import build_ppn_mingguan_excel_export
    from services.project_context import get_read_filter
    week_key = request.args.get('week') or None
    buf = build_ppn_mingguan_excel_export(week_key=week_key, project_id=get_read_filter())
    label = week_key or 'mingguan'
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'LPPM_Monitoring_Hutang_{label}.xlsx',
    )
