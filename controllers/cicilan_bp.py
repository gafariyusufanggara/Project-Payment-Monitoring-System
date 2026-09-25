"""
CONTROLLER — Invoice Cicilan (installment) page.
"""
from flask import Blueprint, render_template

from services.cicilan import get_cicilan_data

bp = Blueprint('cicilan', __name__)


@bp.route('/invoice-cicilan')
def invoice_cicilan():
    from services.project_context import get_read_filter
    pid = get_read_filter()
    cicilan = get_cicilan_data(project_id=pid)
    total_rekanan = len({g['rekanan'] for g in cicilan})
    total_invoices = len(cicilan)
    total_rows = sum(g['row_count'] for g in cicilan)
    total_harga = sum(g['dpp_total'] for g in cicilan)
    total_bayar = sum(g['total_bayar_dpp'] for g in cicilan)
    total_sisa = sum(g['sisa_dpp'] for g in cicilan)
    return render_template('invoice_cicilan.html',
                           cicilan=cicilan,
                           total_rekanan=total_rekanan,
                           total_invoices=total_invoices,
                           total_rows=total_rows,
                           total_harga=total_harga,
                           total_bayar=total_bayar,
                           total_sisa=total_sisa)
