"""
Session-scoped Exclude Invoice lists.

Exclusion lists live in the Flask session cookie, so each browser
gets its own set: one user excluding a rekanan does not affect the
others. Login is a single shared password; identity is the browser.
"""
from flask import session

SESSION_KEY = 'excluded'


def _bucket():
    data = session.get(SESSION_KEY)
    if not isinstance(data, dict):
        data = {}
        session[SESSION_KEY] = data
    return data


def get_excluded_categories():
    return list(_bucket().get('categories') or [])


def get_excluded_rekanan():
    return list(_bucket().get('rekanan') or [])


def set_excluded(typ, name, excluded):
    data = _bucket()
    key = 'categories' if typ == 'kategori' else 'rekanan'
    names = list(data.get(key) or [])
    if excluded and name not in names:
        names.append(name)
    elif not excluded and name in names:
        names.remove(name)
    data[key] = names
    session[SESSION_KEY] = data
    session.modified = True
    return names


def is_excluded_values(kategori, rekanan):
    cats = {c.lower() for c in get_excluded_categories() if (c or '').strip()}
    reks = {r.lower() for r in get_excluded_rekanan() if (r or '').strip()}
    kat = (kategori or '').strip()
    if kat and kat.lower() in cats:
        return True
    rek = (rekanan or '').strip()
    if rek and rek.lower() in reks:
        return True
    return False


def is_excluded_row(row):
    return is_excluded_values(row.get('KATEGORI'),
                              row.get('NAMA LEVELANSIR / REKANAN'))
