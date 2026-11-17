# Smoke Tests

Kumpulan skrip pemeriksaan manual (`smoke_*.py`) untuk aplikasi Monitoring Hutang.
Setiap file adalah skrip mandiri (bukan pytest) yang mencetak `ALL CHECKS PASSED`
atau `SEMUA LOLOS` bila berhasil.

## Cara menjalankan

Jalankan dari root proyek (agar `import app`, `db`, dll. tetap ketemu):

```powershell
python tests/smoke_po_similarity_check.py
```

atau dari dalam folder `tests`:

```powershell
cd tests
python smoke_po_similarity_check.py
```

Setiap skrip menambahkan root proyek ke `sys.path` sendiri, jadi keduanya bekerja.

## Catatan lingkungan

Sebagian skrip membutuhkan kondisi tertentu:

- **Chrome headless** (mis. `smoke_kpi_font_check`, `smoke_nav_badge_check`,
  `smoke_viewport_check`, `smoke_content_width_check`, `smoke_login_geometry_check`)
  butuh Google Chrome terpasang di `C:\Program Files\Google\Chrome\Application\chrome.exe`.
  Bila Chrome tidak ada → `FileNotFoundError`.
- **Request context / data live**: sebagian skrip membaca data & session lewat
  helper yang membutuhkan request context Flask, sehingga bila dijalankan di luar
  konteks tsb akan muncul `Working outside of request context`. Ini kondisi
  lingkungan, bukan kegagalan logika.
- Skrip data-driven (mis. `smoke_invalid_date_rule_data_check`,
  `smoke_ppn_kpi_rounding_check`) bergantung pada isi database saat ini.

Jalankan skrip yang relevan dengan perubahan Anda; tidak semua harus hijau
sekaligus di setiap mesin.
