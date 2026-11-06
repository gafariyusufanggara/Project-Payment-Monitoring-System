# Stack

- Framework: Flask 3.1.3 (Jinja templates, `app.py` + `controllers/` + `services/`)
- Language: py
- Package manager: pip (`requirements.txt`: Flask, openpyxl, XlsxWriter, Werkzeug, gunicorn)
- Styling: vanilla CSS (`static/css/`: app.css, laporan.css, dll; tokens via CSS vars `--lp-*`)
- Component library: none (Bootstrap classes + custom CSS; Bootstrap JS via CDN/bundled in base.html)
- Design tokens: css-vars (`--lp-primary`, `--lp-teal`, `--lp-badge-h-*`, `--lp-badge-p-*` di laporan.css)
- Dark mode: none
- State/data: server-rendered Jinja; SQLite (`monitoring_hutang*.db`); HTMX partial swaps
- Test: smoke_*.py scripts root (Playwright-driven, e.g. smoke_content_width_check.py) + pytest cache; no pytest suite / no lint config
- Lint/format: none configured
- Typecheck: null
- Build: none (no bundler)
- Dev server: `python app.py` (Flask dev) / `wsgi.py` + gunicorn prod
