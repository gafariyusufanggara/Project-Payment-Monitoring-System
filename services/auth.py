import hmac
import os

from flask import session

SESSION_KEY = 'authed'


def get_app_password():
    return os.environ.get('APP_PASSWORD', 'admin123')


def is_authed():
    return bool(session.get(SESSION_KEY))


def check_password(candidate):
    return hmac.compare_digest(str(candidate or ''), str(get_app_password()))


def login():
    session[SESSION_KEY] = True
    session.permanent = True


def logout():
    session.pop(SESSION_KEY, None)
