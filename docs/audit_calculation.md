# Audit Perhitungan — Base Monitoring Hutang APP

## Ringkasan

| # | Issue | Severity | File | Line |
|---|-------|----------|------|------|
| 1 | `total_sisa_dpp` pakai raw data (bukan deduped) | **HIGH** | `services/dashboard.py` | 51-54 |
| 2 | `_rekanan_breakdown` sisa_dpp pakai `max(0, harga-bayar)` per-row pada deduped data | **MEDIUM** | `services/dashboard.py` | 116 |
| 3 | `_monthly_data` sisa_dpp pakai `max(0, harga-bayar)` per-row pada deduped data | **MEDIUM** | `services/dashboard.py` | 190 |
| 4 | `_daily_data` sisa_dpp pakai `max(0, harga-bayar)` per-row pada deduped data | **LOW** | `services/dashboard.py` | 210 |
| 5 | JT Excel detail row sisa_dpp pakai `max(0, 0 - bayar)` untuk baris duplikat | **LOW** | `services/jt_excel.py` | 194 |

---

## Issue 1: [HIGH] `total_sisa_dpp` di dashboard pakai raw data

### Lokasi
[`services/dashboard.py`](services/dashboard.py:51)

### Kode bermasalah
```python
total_sisa_dpp = sum(
    max(0, safe_float(r.get('HARGA (EXLD)')) - safe_float(r.get('PEMBAYARAN DPP')))
    for r in data        # ← PAKAI RAW data, BUKAN deduped
)
```

### Penyebab
Variable `data` adalah raw data dari DB, bukan `deduped`. Untuk invoice yang duplikat (installment), `HARGA (EXLD)` tetap utuh di semua baris raw, sehingga terjadi **double-counting**.

### Contoh
INV-001 dengan HARGA(EXLD)=1.000.000, dua kali bayar @200.000:
- Row 1: HARGA=1.000.000, BAYAR=200.000 → sisa = 800.000
- Row 2: HARGA=1.000.000, BAYAR=200.000 → sisa = 800.000
- **total_sisa_dpp = 1.600.000 (SALAH)** → harusnya 600.000 (1.000.000 - 400.000)

### Dampak
- Ringkasan dashboard: **Sisa Hutang** dan **Sisa Hutang DPP** over-counted
- Persentase `status_dpp_pct` tidak terpengaruh karena pakai `total_harga_excl` (deduped) sebagai denominator
- `sisa_hutang` (total_sisa_dpp + total_sisa_ppn) ikut salah

### Fix
```python
total_sisa_dpp = max(0, total_harga_excl_raw - total_dpp_paid)
```
Di mana sudah tersedia:
- `total_harga_excl_raw = sum(HARGA(EXLD) dari deduped)` ← sudah ada line 60
- `total_dpp_paid = sum(PEMBAYARAN DPP dari raw)` ← sudah ada line 49

---

## Issue 2: [MEDIUM] `_rekanan_breakdown` sisa_dpp per-row dengan `max(0, ...)`

### Lokasi
[`services/dashboard.py`](services/dashboard.py:116)

### Kode bermasalah
```python
rekanan_detail[rek]['sisa_dpp'] += max(
    0, safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
)
```

### Penyebab
Di `deduped` data, baris duplikat memiliki `HARGA (EXLD)=0` tapi `PEMBAYARAN DPP` tetap utuh. Rumus `max(0, 0 - bayar)` menghasilkan 0, bukan nilai negatif yang seharusnya meng-offset sisa dari baris pertama.

### Contoh
INV-001, HARGA=1.000.000, dua baris bayar @200.000 (deduped):
- Row 1: HARGA=1.000.000, BAYAR=200.000 → sisa = max(0, 1.000.000-200.000) = 800.000
- Row 2: HARGA=0, BAYAR=200.000 → sisa = max(0, 0-200.000) = 0
- **Akumulasi = 800.000 (SALAH)** → harusnya 600.000

### Dampak
- Breakdown per rekanan di dashboard: kolom **Sisa DPP** over-counted
- Kolom `total_dpp` dan `total_bayar_dpp` benar (dipakai via sum, bukan max)

### Fix
```python
# Ganti per-row max(0,...) dengan akumulasi biasa, lalu max(0) di akhir loop
rekanan_detail[rek]['sisa_dpp'] += (
    safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
)
```

Kemudian setelah loop, untuk tiap rekan:
```python
rekanan_detail[rek]['sisa_dpp'] = max(0, rekanan_detail[rek]['sisa_dpp'])
```

Atau lebih sederhana — hitung dari total yang sudah benar:
```python
rekanan_detail[rek]['sisa_dpp'] = max(
    0, rekanan_detail[rek]['total_dpp'] - rekanan_detail[rek]['total_bayar_dpp']
)
```
(inisialisasi 0 dulu, hitung setelah semua row diproses)

---

## Issue 3: [MEDIUM] `_monthly_data` sisa_dpp per-row dengan `max(0, ...)`

### Lokasi
[`services/dashboard.py`](services/dashboard.py:190)

### Kode bermasalah
```python
monthly_data[key]['sisa_dpp'] += max(
    0, safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
)
```

### Penyebab & Dampak
Sama dengan Issue 2. Data sudah `deduped` tapi `max(0, ...)` mencegah baris duplikat meng-offset sisa.

### Fix
```python
monthly_data[key]['sisa_dpp'] += (
    safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
)
```
Lalu setelah loop:
```python
for k in monthly_data:
    monthly_data[k]['sisa_dpp'] = max(0, monthly_data[k]['sisa_dpp'])
```

---

## Issue 4: [LOW] `_daily_data` sisa_dpp per-row dengan `max(0, ...)`

### Lokasi
[`services/dashboard.py`](services/dashboard.py:210)

### Penyebab & Dampak
Sama persis dengan Issue 3, bedanya di grouping per hari. Dampak lebih rendah karena daily view jarang menampilkan invoice yang sama di hari berbeda.

### Fix
```python
daily_data[key]['sisa_dpp'] += (
    safe_float(row.get('HARGA (EXLD)')) - safe_float(row.get('PEMBAYARAN DPP'))
)
```
Lalu setelah loop:
```python
for k in daily_data:
    daily_data[k]['sisa_dpp'] = max(0, daily_data[k]['sisa_dpp'])
```

---

## Issue 5: [LOW] JT Excel detail row sisa pakai per-row `max(0, ...)`

### Lokasi
[`services/jt_excel.py`](services/jt_excel.py:194)

### Kode bermasalah
```python
inv_sisa_dpp = max(0, inv['harga_excl'] - inv['bayar_dpp'])
```

### Penyebab
`inv['harga_excl']` sudah 0 untuk baris duplikat (dari `build_jatuh_tempo_data`), jadi:
- Row duplikat: `max(0, 0 - 200.000) = 0`

Tapi nilai sisa sebenarnya positif karena `bayar_dpp` masih terhitung sebagai cicilan.

### Dampak
- Detail row di Excel JT menampilkan **Sisa = 0** untuk baris cicilan
- **Vendor summary row (banded) tetap benar** karena menghitung ulang sisa dari `rekan_total_dpp - rekan_bayar_dpp`
- Hanya kosmetik di detail rows

### Fix
Gunakan nilai `sisa` dari data dict (`inv['sisa']`) yang sudah dihitung di `build_jatuh_tempo_data`:
```python
# di jt_excel.py line 194, ganti:
inv_sisa_dpp = max(0, inv['sisa'] or 0)
```
Atau gunakan `inv.get('sisa', max(0, inv['harga_excl'] - inv['bayar_dpp']))`.

---

## Verifikasi: Path yang sudah benar ✅

| Path | Formula | Status |
|------|---------|--------|
| **Dashboard total_tagihan** | `sum(TOTAL(INCLD) dari deduped)` | ✅ |
| **Dashboard total_dpp_paid** | `sum(PEMBAYARAN DPP dari raw)` | ✅ |
| **Dashboard total_ppn_paid** | `sum(PEMBAYARAN PPN dari raw)` | ✅ |
| **Dashboard total_harga_excl** | `sum(HARGA(EXLD) dari deduped)` | ✅ |
| **Dashboard status_dpp_pct** | `total_dpp_paid / total_harga_excl * 100` | ✅ |
| **Dashboard status_ppn_pct** | `total_ppn_paid / total_ppn_val * 100` | ✅ |
| **Laporan Bulanan _build_cum** | Sisa = max(0, cum HARGA - cum BAYAR) — both from correct sources | ✅ |
| **Laporan Mingguan** | Inherits `_build_cum` | ✅ |
| **Laporan PPN** | Inherits `_build_cum` | ✅ |
| **JT Report vendor summary** | Sisa = sum(total_dpp) - sum(bayar_dpp) | ✅ |
| **LBP Excel _render_lbp** | Detail pakai deduped data, vendor summary banded | ✅ |
| **Investor/aging count** | Hanya count, tidak dijumlah | ✅ |
| **Kategori breakdown** | Pakai `TOTAL(INCLD)` dari deduped | ✅ |

---

## Catatan Tambahan

1. **SISA HUTANG DPP per-row di DB table** (tampilan data invoice) tetap menampilkan nilai per-row seperti saat di-import. Untuk invoice duplikat, dua baris bisa tampil SISA=800.000 dan SISA=800.000. Ini bukan bug perhitungan — itu nilai yang disimpan per baris. Tapi perlu dipahami bahwa total sisa sesungguhnya adalah `HARGA(EXLD) - total PEMBAYARAN DPP` untuk invoice tersebut.

2. **`calc_sisa()` di constants.py** — fungsi yang jalan saat import/form — menghitung SISA HUTANG DPP = `max(0, HARGA(EXLD) - PEMBAYARAN DPP)` per baris. `POT. RETENSI` dan `POT. PPH` tidak memengaruhi SISA HUTANG DPP. Ini sesuai praktik akuntansi kontraktor di Indonesia (retensi = dana ditahan, PPH = potongan pajak).

3. **`PEMBAYARAN POT. PPH`** dan **`NILAI YG DITERIMA VENDOR`** tidak digunakan di perhitungan agregasi manapun — hanya disimpan untuk dokumentasi.

4. **Invoice-rekanan conflict detection** (di verifikasi) masih menggunakan `NO INVOICE` asli, bukan `effective_invoice()`. Ini benar karena conflict detection harus menandai duplikasi NO INVOICE asli, bukan workaround-nya.
