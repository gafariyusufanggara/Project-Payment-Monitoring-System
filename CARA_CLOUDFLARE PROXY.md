# Proxy mondebt.pages.dev → PythonAnywhere

Isi folder ini (`_worker.js`) meneruskan semua request ke `gafarybyh3.pythonanywhere.com`.

## Deploy (tanpa install apa pun)

1. Buka dash.cloudflare.com → Workers & Pages → Create → Pages → Upload assets.
2. Project name: `mondebt`.
3. Buat folder baru berisi HANYA `_worker.js` (jangan sertakan `CARA_DEPLOY.md` — ikut jadi publik), drag folder itu, Deploy.
4. Buka `https://mondebt.pages.dev/login`.

## Catatan

- Import/upload Excel besar lewat link PythonAnywhere langsung, bukan via `pages.dev`.
- Ganti username PA: edit `ORIGIN` di `_worker.js`, upload ulang.

## Update

Edit `_worker.js` → upload ulang file yang sama di Pages → Deployments → Create deployment.
