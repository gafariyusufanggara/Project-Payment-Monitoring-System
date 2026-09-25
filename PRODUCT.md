# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: finance / accounting staff tracking vendor hutang day-to-day — input berkas/invoice, monitor JTH TEMPO aging, record DPP/PPN payments, reconcile per project. Secondary (implied by code): project admin/division submitting berkas, management viewing consolidated dashboards and laporan.

## Product Purpose

Replace fragile manual Excel tracking of vendor debts with a local Flask app that consolidates hutang across projects, auto-calculates sisa hutang + aging buckets, and produces verification, laporan mingguan/bulanan, and PPN reports. Success = accurate per-invoice sisa, no missed jatuh tempo, auditable edits.

## Positioning

Single local system that merges multi-project hutang (session-scoped `active_project_id`, `'all'` = consolidated) with Excel-compatible import/export plus an immutable-edit audit trail — neighboring Excel trackers cannot truthfully copy the consolidation + auto-aging + audit combination.

## Operating Context

Workflows: Excel import (`services/excel_import.py`, 1-based `IMPORT_COL_MAP`, dates `YYYY-MM-DD`) → dashboard/verifikasi → cicilan payments → laporan PPN/mingguan → JT Excel export. Rituals: `migrate_from_excel()` on startup (no-op unless `hutang` empty); per-project re-import deletes only that project's rows. Environment: localhost:5000, single-user desktop use, 50MB upload limit. Materials: existing `*.xlsx` files in root, invoice/PO/faktur pajak documents, bukti bayar DPP/PPN.

## Capabilities and Constraints

Confirmed: multi-project scoping via `services/project_context.py` only; all `hutang` columns TEXT with float/date casts in code; every write path runs `round_currency()` then `calc_sisa()`; `AUTO_FIELDS` never user-editable; `POST /edit/<row>` never touches main DB (snapshots to `monitoring_hutang_audit.db`); dedup identity `effective_invoice()` with report zero-out of duplicate amounts but accumulated payments; categories in runtime-created `config.json`. Constraints: Flask + SQLite local (`monitoring_hutang.db`, audit + ignore DBs), deps Flask/openpyxl/xlsxwriter, Python 3.13, startup order `init_db → init_audit_db → init_ignore_db → init_project_tables → migrate_from_excel`. Undecided: none material — multi-user/auth explicitly out of scope.

## Brand Commitments

Name: Monitoring Hutang / Project Financial Monitoring System. Voice: Indonesian finance terminology (LEVELANSIR, JTH TEMPO, SISA HUTANG, DPP/PPN). No logo, palette, or identity assets confirmed.

## Evidence on Hand

Real: runnable Flask MVC codebase (`app.py`, `controllers/`, `services/`, `templates/` extending `base.html`), `constants.py` column model, live SQLite DBs. Absent: no testimonials, customers, benchmarks, pricing, or deployment claims — future work must not fabricate them.

## Product Principles

1. Accuracy over convenience — rounding, sisa, and audit diffs follow Excel-compatible whole-Rupiah rules.
2. Project scope is explicit — every read declares `all` vs one `project_id`.
3. Main ledger is immutable on edit — corrections live in audit snapshots.
4. Excel round-trips losslessly — import/export preserves columns, dates, and amounts.
5. Local-first simplicity — no login, no hosted infra, runs with `python app.py`.
