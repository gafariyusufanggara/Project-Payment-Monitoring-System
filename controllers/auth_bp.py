from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import auth as auth_svc

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if auth_svc.is_authed():
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        if auth_svc.check_password(request.form.get('password', '')):
            auth_svc.login()
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        flash('Password salah.', 'danger')
    return render_template('login.html')


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    auth_svc.logout()
    return redirect(url_for('auth.login'))
