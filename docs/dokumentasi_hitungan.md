# Dokumentasi Perhitungan — Realisasi Hutang & Pembayaran

## Ringkasan

Sistem menghitung **Realisasi Hutang** dan **Realisasi Pembayaran** secara akumulatif (s.d saat ini) per rekanan per periode. Setiap periode (bulan/minggu) menampilkan:

- **Lalu** — akumulasi sebelum periode ini
- **Saat Ini** — transaksi yang terjadi dalam periode ini
- **S.D Saat Ini** — total kumulatif sejak awal

---

## 1. Sumber Data

Data diambil dari tabel `hutang` di database (via [`db.read_data()`](db.py:42)). Setiap baris mewakili satu invoice, berisi:

| Kolom              | Keterangan                   | Contoh           |
|--------------------|------------------------------|------------------|
| `TOTAL (INCLD)`    | Total hutang termasuk PPN    | 2.000.000        |
| `HARGA (EXCL)`     | Harga sebelum PPN            | 1.818.182        |
| `PPN`              | PPN 11%                      | 181.818          |
| `POT. PPH`         | Potongan PPh                 | 0                |
| `PEMBAYARAN DPP`   | Pembayaran DPP               | 150.000          |
| `PEMBAYARAN PPN`   | Pembayaran PPN               | 0                |
| `TGL BAYAR DPP`    | Tanggal bayar DPP            | 2026-05-21       |
| `TGL BAYAR PPN`    | Tanggal bayar PPN            | (kosong)         |
| `SISA HUTANG (INCLD PPN)` | Sisa total dari DB    | 1.850.000        |

---

## 2. Alur Perhitungan ([`_build_cum()`](services/laporan.py:13))

### Pass 1 — Grouping

Hutang dikelompokkan berdasarkan tanggal `TGL TERIMA BERKAS LENGKAP` (bukan tanggal invoice atau tanggal bayar). Pembayaran dikelompokkan berdasarkan tanggal bayar masing-masing.

- **`hutang_rm[rekan][periode]`** — mengumpulkan:
  - `hutang` = jumlah `TOTAL (INCLD)`
  - `harga_excl` = jumlah `HARGA (EXCL)`
  - `pot_pph` = jumlah `POT. PPH`
  - `ppn` = jumlah `PPN`
  - `invoices[]` — detail per invoice

- **`bayar_rm[rekan][periode]`** — mengumpulkan:
  - `bayar` = jumlah `PEMBAYARAN DPP` (berdasarkan `TGL BAYAR DPP`)
  - `bayar_ppn` = jumlah `PEMBAYARAN PPN` (berdasarkan `TGL BAYAR PPN`)

### Pass 2 — Kumulatif

Untuk setiap rekanan, iterasi semua periode secara kronologis sambil menjalankan akumulator:

#### Rumus Realisasi Hutang

| Variabel    | Akumulator          | Sumber                  |
|-------------|---------------------|-------------------------|
| `ch`        | `TOTAL (INCLD)`     | hutang per periode      |
| `chx`       | `HARGA (EXCL)`      | hutang per periode      |
| `cpph`      | `POT. PPH`          | hutang per periode      |
| `cppn`      | `PPN`               | hutang per periode      |

#### Rumus Realisasi Pembayaran

| Variabel    | Akumulator          | Sumber                  |
|-------------|---------------------|-------------------------|
| `cb`        | `PEMBAYARAN DPP`    | bayar per periode       |
| `cbp`       | `PEMBAYARAN DPP`    | bayar per periode       |
| `cbpn`      | `PEMBAYARAN PPN`    | bayar per periode       |

**Catatan:** `cb` dan `cbp` saat ini identik. Dipisahkan untuk antisipasi jika ke depan ada jenis bayar lain.

#### Rumus Sisa per Periode

```
sisa_dpp = max(0, chx - cbp)
sisa_ppn = max(0, cppn - cbpn)
Sisa Total (INCLD) = sd_hutang - sd_bayar
```

> **Catatan (dikoreksi):** `POT. PPH` **tidak** mengurangi sisa DPP. PPh adalah
> potongan pajak, bukan pengurang kewajiban hutang DPP. Rumus ini konsisten
> dengan [`calc_sisa()`](constants.py:181) dan [`dashboard.py`](services/dashboard.py:55).
> `cpph` tetap dikumpulkan dan ditampilkan sebagai kolom PPH, tetapi tidak masuk
> ke rumus sisa.

Dimana:
- `chx` — kumulatif `HARGA (EXCL)` s.d periode ini
- `cpph` — kumulatif `POT. PPH` s.d periode ini
- `cbp` — kumulatif `PEMBAYARAN DPP` s.d periode ini
- `cppn` — kumulatif `PPN` s.d periode ini
- `cbpn` — kumulatif `PEMBAYARAN PPN` s.d periode ini

### Contoh Langkah

```
REKANAN: PT ABC

Periode     | chx      | cpph | cbp      | sisa_dpp
------------|----------|------|----------|-----------
2026-01     | 1.818.182| 0    | 0        | 1.818.182
2026-02     | 1.818.182| 0    | 0        | 1.818.182
2026-03     | 1.818.182| 0    | 0        | 1.818.182
2026-04     | 1.818.182| 0    | 0        | 1.818.182
2026-05     | 1.818.182| 0    | 150.000  | 1.668.182 ← mulai dibayar
2026-06     | 1.818.182| 0    | 150.000  | 1.668.182
…
```

---

## 3. Perbedaan dengan Database Lama

Di database, kolom `SISA HUTANG DPP` dihitung statis oleh fungsi [`calc_sisa()`](constants.py:158) ketika data di-import/diedit:

```python
sisa_hutang_dpp = max(0, HARGA(EXCL) - PEMBAYARAN DPP)
```

**Masalah:** Nilai ini disimpan sekali dan tidak pernah diubah. Jika ada pembayaran yang terjadi di masa depan (misal TGL BAYAR DPP = 2026-05-21), maka sejak data di-import, sisa DPP sudah dipotong pembayaran tersebut — padahal secara kumulatif per bulan, pembayaran itu belum terjadi di bulan-bulan sebelumnya.

**Solusi:** Sistem baru menghitung ulang sisa DPP/PPN secara **dinamis per periode** dengan menjumlahkan `HARGA(EXCL)` dan `PEMBAYARAN DPP` secara kumulatif berdasarkan tanggal masing-masing. Dengan ini:

- Sisa di bulan **Januari 2026** = `HARGA(EXCL)` — karena belum ada pembayaran
- Sisa di bulan **Mei 2026** = `HARGA(EXCL) - PEMBAYARAN DPP` — karena pembayaran sudah terjadi
- Sisa di modal detail invoice per-invoice = `max(0, HARGA(EXCL) - PEMBAYARAN DPP)` — karena untuk invoice individual, semua pembayaran sudah final.

---

## 4. Detail Invoice di Modal

Untuk modal detail invoice (per-invoice), rumus tetap sama:

```javascript
sisaDpp = max(0, harga_excl - bayar_dpp)
sisaPpn = max(0, ppn - bayar_ppn)
```

Ini karena invoice level tidak perlu akumulasi antar periode — setiap invoice berdiri sendiri dengan harga, potongan, dan pembayarannya.

---

## 5. Export Excel

Di export Excel ([`_render_lbp()`](services/laporan.py:399)), detail per invoice dihitung dengan mengklasifikasikan hutang/pembayaran ke "Lalu" vs "Saat Ini" berdasarkan perbandingan periode:

- Jika **TGL BERKAS** < periode terpilih → hutang masuk kolom "Lalu"
- Jika **TGL BERKAS** == periode terpilih → hutang masuk kolom "Saat Ini"
- Jika **TGL BAYAR DPP** < periode terpilih → bayar masuk kolom "Lalu"
- Jika **TGL BAYAR DPP** == periode terpilih → bayar masuk kolom "Saat Ini"

Sisa DPP per invoice di baris detail:
```
dpp_sisa = max(0, harga_excl - (p_lalu + p_si))
```

---

## 6. Diagram Alir

```
db.read_data()
    │
    ▼
Pass 1: Group by periode (TGL BERKAS untuk hutang, TGL BAYAR untuk bayar)
    │
    ▼
Pass 2: Iterasi periode, akumulasi chx/cpph/cbp/cbpn
    │
    ▼
Hitung sisa_dpp = max(0, chx - cbp)     # POT. PPH tidak mengurangi sisa DPP
Hitung sisa_ppn = max(0, cppn - cbpn)
    │
    ▼
Pass 3: Bentuk report_rows per bulan/minggu
    │
    ▼
Render HTML / Export Excel
```

---

## 7. Penempatan Periode Pembayaran

Pembayaran dikelompokkan ke periode dengan aturan yang menjamin **tidak ada
pembayaran yang hilang** dan **tidak ada pembayaran yang mendahului hutangnya**
(lihat [`_resolve_pay_period()`](services/laporan.py:13)):

| Kondisi `TGL BAYAR DPP`                    | Periode yang dipakai     |
|--------------------------------------------|--------------------------|
| Tanggal valid dan >= `TGL TERIMA`          | periode tanggal bayar    |
| Tanggal lebih awal dari `TGL TERIMA`       | di-clamp ke `TGL TERIMA` |
| Kosong / bukan tanggal (mis. `RC Divisi-12`)| jatuh ke `TGL TERIMA`    |

**Alasan:** bila pembayaran dibiarkan masuk ke periode sebelum hutangnya
tercatat, maka `sd_bayar > sd_hutang` → sisa menjadi negatif → dipotong
`max(0, …)` → nilai pembayaran itu hilang permanen dari neraca mingguan.

---

## 8. Catatan Penting

- `POT. PPH` **tidak** mengurangi sisa DPP. PPh adalah potongan pajak yang
  disetor, bukan pengurang kewajiban hutang — nilainya hanya ditampilkan sebagai
  kolom PPH terpisah. (`calc_sisa()` di `constants.py` juga tidak mengurangkannya.)
- Pembayaran DPP dan PPN dilacak terpisah karena tanggal bayarnya bisa berbeda.
- Sisa DPP dan sisa PPN tidak bisa langsung dijumlah karena PPN dihitung dari DPP.
- Kolom `SISA HUTANG DPP` dan `SISA HUTANG PPN` di database sudah **tidak dipakai lagi** untuk laporan. Hanya kolom `SISA HUTANG (INCLD PPN)` yang masih digunakan untuk field `sisa` (total sisa include PPN) sebagai fallback.
