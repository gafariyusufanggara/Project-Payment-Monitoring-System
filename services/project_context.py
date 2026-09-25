"""
Session-scoped "active project" context.

The app stores the user's currently selected project in the Flask session
so that every page (dashboard, laporan, verifikasi, cicilan) can filter
hutang rows by that project without each controller re-implementing it.

Sentinel value 'all'  → show every project (consolidated view).
Otherwise the value is a project id (stored as string).

This module is the single source of truth — controllers call
get_active_project_id() and pass the result to db.read_data().
"""
from flask import session

ALL_PROJECTS = 'all'


def get_active_project_id():
    """Return the active project_id from session.

    Returns 'all' (consolidated) when nothing is selected yet, or an
    int project id. The value is validated against the projects table;
    if the stored id no longer exists, it silently falls back to 'all'.
    """
    raw = session.get('active_project_id', ALL_PROJECTS)
    if str(raw) == ALL_PROJECTS or str(raw) == '':
        return ALL_PROJECTS
    try:
        pid = int(raw)
    except (ValueError, TypeError):
        return ALL_PROJECTS
    # Validate existence (cheap single-row lookup)
    import db_project
    if db_project.get_project(pid) is None:
        session['active_project_id'] = ALL_PROJECTS
        return ALL_PROJECTS
    return pid


def set_active_project_id(pid):
    """Persist the active project id into the session.

    Accepts 'all', '', None, or an int/str project id.
    """
    if pid is None or str(pid) == '' or str(pid) == ALL_PROJECTS:
        session['active_project_id'] = ALL_PROJECTS
    else:
        try:
            session['active_project_id'] = int(pid)
        except (ValueError, TypeError):
            session['active_project_id'] = ALL_PROJECTS


def get_read_filter():
    """Return the value to pass straight into db.read_data(project_id=...).

    Returns None (meaning "all rows") when consolidated view is active,
    otherwise the int project id. db.read_data treats None/'all' identically.
    """
    pid = get_active_project_id()
    if pid == ALL_PROJECTS:
        return None
    return pid
