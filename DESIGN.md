---
version: "1.0"
name: "Buku Besar Tenang — Project Payment Monitoring System"
description: "Antarmuka keuangan profesional dengan chrome navy, aksen teal, dan permukaan slate terang."
colors:
  primary: "#0F766E"
  deep: "#16324F"
  deep-light: "#244866"
  deep-deep: "#102A43"
  deep-tint: "#EAF0F6"
  ink: "#243447"
  muted: "#526579"
  muted-strong: "#40566D"
  border: "#DCE3EB"
  neutral-soft: "#EDF2F7"
  bg: "#F5F7FA"
  surface: "#FFFFFF"
  hover: "#EDF2F7"
  warning: "#B45309"
  warning-ink: "#854D0E"
  warning-fill: "#F59E0B"
  orange: "#B45309"
  purple: "#6F5AA8"
  success: "#0F766E"
  success-soft: "#E6F4F1"
  success-ink: "#115E59"
  danger: "#B42318"
  danger-soft: "#FEF0EE"
  danger-hover: "#FBD8D3"
  danger-ink: "#912018"
  focus-ring: "rgba(15, 118, 110, 0.18)"
typography:
  display:
    fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.1
  title:
    fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "1rem"
    fontWeight: 700
  body:
    fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
  label:
    fontFamily: "Inter, -apple-system, 'Segoe UI', sans-serif"
    fontSize: "0.7rem"
    fontWeight: 700
    letterSpacing: "0.6px"
  data:
    fontFamily: "'JetBrains Mono', 'SF Mono', monospace"
    fontSize: "0.76rem"
    fontWeight: 600
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  5: "24px"
  6: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "7px 14px"
  button-primary-hover:
    backgroundColor: "{colors.success}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "7px 14px"
  kpi-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
---

# Design System: Project Payment Monitoring System

## Overview

**Creative North Star: "Buku Besar Tenang" — the calm ledger.**

Flat design keuangan yang menenangkan: kebisingan visual dihapus agar angka bicara. Chrome aplikasi memakai Azul Profundo (#005691) — kesan perbankan yang aman — sementara konten bernapas di atas permukaan terang netral. Verde Esmeralda (#2ECC40) adalah satu-satunya aksen tindakan: tombol primer, indikator item aktif, dan baris status "lunas". Semua angka uang dan metrik KPI memakai JetBrains Mono / tabular-nums agar kolom mengunci rapi seperti buku besar.

Mode: **Operate** — staf finance mengerjakan tugas; keakraban komponen mengalahkan ekspresi. Ekspresi brand hidup di detail: chip angka hijau pada toolbar, garis aksen 3px di atas kartu KPI, indikator hijau pada nav aktif.

**Key Characteristics:**
- Satu aksen (hijau) untuk aksi; biru profundo hanya untuk chrome & navigasi.
- Semua angka uang monospace tabular.
- Flat: shadow halus 1 tingkat, tanpa gradient dekoratif (hanya tint 2-stop pada chrome).
- Label uppercase 0.7rem letter-spacing 0.6px sebagai bahasa struktur.

## Colors

Palet flat finance: chrome biru, aksen hijau tunggal, netral abu netral.

### Primary
- **Verde Esmeralda** (#2ECC40): aksi primer (tombol Simpan/Import/Catat Audit), indikator item nav aktif, chip hitung toolbar, garis aksen KPI. Selalu dipasangkan teks gelap #333333 (bukan putih — putih di hijau gagal kontras).

### Secondary
- **Azul Profundo** (#005691, #0a6aa8, #004a7c): chrome — sidebar, header tabel, header modal, angka chip nomor seksi, warna tautan & focus. Biru berarti "struktur/navigasi", bukan aksi.

### Tertiary
- **Amarelo Ouro** (#FFD700): badge peringatan di sidebar (teks #333333); varian gelap #E5B800 untuk ikon kecil & fill chart agar terbaca di atas putih; tint #fdf6d8 untuk latar status peringatan.
- **Laranja Vibrante** (#FF8C00): CTA sekunder / level tengah ramp severity chart (blm-jatuh-tempo → >90 hari).
- **Roxo Suave** (#9370DB): badge info/audit & penekanan data; tint #ece4f7.

### Neutral
- **Cinza Escuro** (#333333): semua teks utama & permukaan gelap non-chrome.
- **Abu Teks** (#667080 / #4d5766): teks sekunder, label, meta (AA di atas putih).
- **Cinza Claro** (#F0F0F0, #f2f3f5, #f7f8f9): latar halaman, badge kategori, zebra halus.
- **Batas** (#e3e5e8, #eef0f2): border 1px, garis pemisah sel.
- **Permukaan** (#ffffff): kartu, tabel, modal.

### Status (semantik)
- **Success** #2ECC40 + tint #e4f9e7 + ink #1d7a2b (LUNAS, bayar lunas).
- **Danger** #e74c3c + tint #fdecea + ink #a12a1d (BELUM, jatuh tempo, kritis).

### Named Rules
**The Green Acts Rule.** Hijau hanya untuk aksi & status positif; biru tidak pernah jadi tombol primer; teks di atas hijau selalu #333333.

**The Chrome Rule.** Azul Profundo hanya menyentuh navigasi, header tabel/modal, dan fokus — tidak pernah jadi warna isi kartu.

**The Money Is Mono Rule.** Setiap sel uang memakai JetBrains Mono + tabular-nums; tidak ada angka keuangan dalam Inter.

## Typography

**Display Font:** Inter (fallback system sans)
**Body Font:** Inter
**Label/Mono Font:** JetBrains Mono — angka uang, nomor invoice, baris, kode

**Character:** Inter satu keluarga membawa seluruh UI (Operate mode); JetBrains Mono hanya untuk data agar kolom angka lurus.

### Hierarchy
- **Display** (700, 2rem, 1.1): angka hero dashboard (Total Sisa Hutang).
- **Title** (700, 1rem–1.25rem): judul halaman (`.ds-page-head__title`), judul kartu.
- **Body** (400, 0.85rem, 1.5): konten tabel & form.
- **Label** (700, 0.7rem, uppercase, 0.6px): label form, header kolom, section title.
- **Data** (600, 0.76rem, JetBrains Mono): sel uang, nomor, tanggal teknis.

## Layout

App shell flex: sidebar fixed 240px (collapse 72px, simpan di localStorage, terapkan sebelum paint via `sb-collapsed`), konten margin-left mengikuti. Topbar sticky 56px blur; content-area padding 24px 28px scroll sendiri. Breakpoint struktural: 992px sidebar menjadi 64px ikon-saja; 768px filter full-width; 576px konten 16px. Density: tabel ledger padat (padding-y 4px, font 0.85rem) — data finansial dibaca melintang 18+ kolom.

## Elevation & Depth

Flat-first: permukaan datar dengan border 1px; shadow hanya 3 tingkat halus (0.05–0.12 alpha) sebagai respons state — kartu KPI naik `translateY(-2px)` + shadow-md saat hover, modal pakai shadow-lg. Depth tidak pernah dari gradient; gradient 2-stop hanya pada chrome biru (sidebar/header) sebagai tekstur-brand yang disengaja.

## Shapes

Sudut membulat konsisten: 6px kontrol kecil, 8px tombol/input, 12px section, 16px kartu/modal/pill besar. Bahasa aksen: garis 3px (atas kartu KPI, kiri nav aktif, kiri toast) sebagai satu-satunya dekorasi berwarna. Border 1px #e3e5e8 di semua container terang.

## Components

### Buttons
- **Shape:** membulat 8px; kecil 6px.
- **Primary:** hijau #2ECC40, teks #333333, padding 7px 14px; hover #27b537 + teks putih (hanya di hover gelap); shadow hijau halus.
- **Ghost:** putih, border 1px, teks #333333; hover latar #f7f8f9.
- **Focus:** border + ring biru profundo rgba(0,86,145,.18) — satu suara fokus.

### Chips / Badges
- **Status:** tint + ink (lunas #e4f9e7/#1d7a2b, belum #fdecea/#a12a1d), radius 6px, 0.68rem bold.
- **Kategori:** abu #F0F0F0 + #4d5766.
- **Nav badge:** solid — kritis #e74c3c (pulse), peringatan #FFD700 teks #333, info #9370DB.

### Cards / Containers
- Radius 16px, putih, border 1px, shadow-sm; KPI memakai bar aksen 3px atas (hijau/emas/merah sesuai status).
- **Internal padding:** 16–24px.

### Inputs / Fields
- Putih, border 1px, radius 10px, teks 0.85rem.
- **Focus:** border #005691 + ring rgba(0,86,145,.12–.15).
- Label uppercase 0.7rem di atas input; error merah #a12a1d.

### Navigation
- Sidebar biru profundo gradient 180deg (#004a7c→#0a6aa8); item 0.82rem 500; hover putih 8%.
- **Aktif:** latar putih 14% + inset bar hijau 3px kiri + ikon hijau muda ("accent color indicator").
- Topbar putih blur; project-scope select radius 10px border ikon biru.

### Signature: Ledger Hero
Hero dashboard gradient biru profundo dengan angka raksasa Inter 700 putih + bar progres DPP/PPN tipis; satu-satunya blok "drenched" di sistem dan harus tetap biru.

## Do's and Don'ts

### Do:
- **Do** pakai `--ds-*` / `:root` token untuk semua warna baru; hex literal hanya untuk tint status yang sudah terdaftar.
- **Do** pasangkan teks di atas hijau dengan #333333.
- **Do** pakai JetBrains Mono untuk seluruh angka uang.
- **Do** pakai tint + ink untuk badge (bukan warna solid).
- **Do** gunakan focus ring biru profundo yang konsisten.

### Don't:
- **Don't** pakai putih sebagai teks di atas hijau (2.1:1).
- **Don't** perkenalkan aksen kedua selain hijau untuk aksi primer.
- **Don't** gradient dekoratif pada konten; gradient hanya chrome biru 2-stop.
- **Don't** pakai DM Sans / DM Serif Display — sudah diganti Inter.
- **Don't** buat permukaan gelap baru di luar chrome biru & hero.
