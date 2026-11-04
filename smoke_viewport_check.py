"""Verifikasi halaman tampil dalam tata letak desktop di browser mobile.

Menyetel meta viewport ke `width=1280` seharusnya membuat browser mobile
memakai lebar tata letak 1280 CSS px, sehingga semua breakpoint
`max-width: 1024px` tidak aktif.

Skrip ini menjalankan Chrome headless dengan emulasi perangkat mobile
(devtools `Emulation.setDeviceMetricsOverride` mobile=True + touch), lalu
membaca `window.innerWidth` dan properti layout yang hanya muncul pada
mode desktop:
  - sidebar tampil (bukan `translateX` keluar layar)
  - header halaman versi desktop terlihat
  - rasio zoom efektif = lebar fisik / 1280
"""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from base64 import b64encode

HOST = "127.0.0.1"
PORT = 5099
BASE = f"http://{HOST}:{PORT}"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PASSWORD = os.environ.get("APP_PASSWORD", "adminkso1234")
PHYS_W = 390
PHYS_H = 844

PAGES = [
    ("/login", "Login", True),
    ("/", "Dashboard", False),
    ("/invoice-cicilan", "Progress Invoice Cicilan", False),
    ("/levelansir-retensi", "Retensi", False),
    ("/status-dokumen", "Status Dokumen", False),
    ("/verifikasi", "Verifikasi Data", False),
    ("/project/", "Daftar Proyek", False),
]

PROBE = """(() => {
  const metaEl = document.querySelector('meta[name=viewport]');
  const sidebar = document.querySelector('.sidebar, #sidebar, aside.sidebar');
  const sb = sidebar ? sidebar.getBoundingClientRect() : null;
  const main = document.querySelector('.content-area, .main-content');
  return JSON.stringify({
    meta: metaEl ? metaEl.getAttribute('content') : null,
    innerW: window.innerWidth,
    outerW: window.outerWidth,
    vvW: window.visualViewport ? Math.round(window.visualViewport.width) : null,
    vvScale: window.visualViewport ? Number(window.visualViewport.scale.toFixed(4)) : null,
    docScrollW: document.documentElement.scrollWidth,
    sidebarLeft: sb ? Math.round(sb.left) : null,
    sidebarW: sb ? Math.round(sb.width) : null,
    sidebarHidden: sidebar ? (sb.width === 0 || sb.left + sb.width <= 0) : null,
    contentW: main ? Math.round(main.getBoundingClientRect().width) : null,
    mqMobile: window.matchMedia('(max-width: 1024px)').matches,
    bodyScrollW: document.body.scrollWidth
  });
})()"""


class WS:
    def __init__(self, url):
        m = re.match(r"ws://([^:/]+):(\d+)(/.*)", url)
        self.sock = socket.create_connection((m.group(1), int(m.group(2))), timeout=20)
        key = b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {m.group(3)} HTTP/1.1\r\nHost: {m.group(1)}:{m.group(2)}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, data):
        payload = data.encode()
        header = bytearray([0x81])
        n = len(payload)
        mask = os.urandom(4)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        while True:
            while len(self.buf) < 2:
                self.buf += self.sock.recv(65536)
            b1 = self.buf[1] & 0x7F
            off = 2
            if b1 == 126:
                while len(self.buf) < 4:
                    self.buf += self.sock.recv(65536)
                n = struct.unpack(">H", self.buf[2:4])[0]
                off = 4
            elif b1 == 127:
                while len(self.buf) < 10:
                    self.buf += self.sock.recv(65536)
                n = struct.unpack(">Q", self.buf[2:10])[0]
                off = 10
            else:
                n = b1
            while len(self.buf) < off + n:
                self.buf += self.sock.recv(65536)
            msg = self.buf[off:off + n]
            self.buf = self.buf[off + n:]
            return json.loads(msg.decode())

    def call(self, mid, method, params=None):
        self.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            r = self.recv()
            if r.get("id") == mid:
                return r


def main():
    logs = tempfile.TemporaryFile()
    server = subprocess.Popen(
        [sys.executable, "-c",
         f"import app; app.app.run(host='{HOST}', port={PORT}, debug=False, use_reloader=False)"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=dict(os.environ, APP_PASSWORD=PASSWORD),
        stdout=logs, stderr=subprocess.STDOUT,
    )
    profile = tempfile.mkdtemp(prefix="vw-check-")
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
         "--no-default-browser-check", "--remote-debugging-port=9336",
         f"--user-data-dir={profile}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    fails = []
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(BASE + "/login", timeout=1)
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("FAIL server tidak hidup")
            return 1

        tabs = []
        for _ in range(80):
            try:
                tabs = json.loads(urllib.request.urlopen(
                    "http://127.0.0.1:9336/json/list", timeout=1).read())
                if any(t.get("type") == "page" for t in tabs):
                    break
            except Exception:
                pass
            time.sleep(0.25)

        ws = WS([t for t in tabs if t.get("type") == "page"][0]["webSocketDebuggerUrl"])
        mid = [0]

        def jc(m, p=None):
            mid[0] += 1
            return ws.call(mid[0], m, p)

        def probe():
            r = jc("Runtime.evaluate", {"expression": PROBE, "returnByValue": True})
            v = r.get("result", {}).get("result", {}).get("value")
            return json.loads(v) if v else {}

        jc("Page.enable")
        jc("Runtime.enable")
        jc("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
        jc("Emulation.setDeviceMetricsOverride", {
            "width": PHYS_W, "height": PHYS_H, "deviceScaleFactor": 3, "mobile": True,
            "screenWidth": PHYS_W, "screenHeight": PHYS_H,
        })

        jc("Page.navigate", {"url": BASE + "/login"})
        time.sleep(2.5)
        jc("Runtime.evaluate", {"expression":
            f"document.getElementById('password').value='{PASSWORD}';"
            "document.getElementById('loginForm').submit();"})
        time.sleep(2.5)

        print(f"Emulasi mobile {PHYS_W}x{PHYS_H} @3x\n")
        for path, name, is_login in PAGES:
            jc("Page.navigate", {"url": BASE + path})
            time.sleep(2.2)
            d = probe()
            if not d:
                fails.append(f"{name}: gagal membaca layout")
                continue

            ok = True
            why = []
            if d["innerW"] < 1280:
                ok = False
                why.append(f"innerW={d['innerW']} < 1280")
            if d.get("mqMobile"):
                ok = False
                why.append("media query mobile (<=1024px) masih aktif")
            if d.get("meta") is None or "width=1280" not in d.get("meta", ""):
                ok = False
                why.append(f"meta viewport={d.get('meta')!r}")
            if not is_login and d.get("sidebarHidden"):
                ok = False
                why.append("sidebar tersembunyi (mode mobile)")

            zoom = (PHYS_W / d["innerW"]) if d["innerW"] else 0
            flag = "OK " if ok else "BAD"
            print(f"{flag} {name:18s} innerW={d['innerW']:5d} scale={d.get('vvScale')} "
                  f"zoomEfektif={zoom:.3f} sidebarW={d.get('sidebarW')} "
                  f"contentW={d.get('contentW')} scrollW={d.get('docScrollW')}")
            if why:
                fails.append(f"{name}: " + "; ".join(why))

        print()
        if fails:
            print("GAGAL:")
            for f in fails:
                print("  - " + f)
            return 1
        print("SEMUA LOLOS - semua halaman memakai tata letak desktop di emulasi mobile")
        return 0
    finally:
        chrome.terminate()
        server.terminate()
        try:
            chrome.wait(timeout=10)
        except Exception:
            chrome.kill()
        try:
            server.wait(timeout=10)
        except Exception:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
