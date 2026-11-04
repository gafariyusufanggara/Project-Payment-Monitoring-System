"""Cek font-size angka KPI ter-render seragam antar halaman.

Semua KPI memakai .ds-kpi--compact, jadi .ds-kpi__value seharusnya
memakai var(--ds-fs-2xl). Skrip ini membaca nilai computed lewat
Chrome headless (DevTools Protocol) di beberapa halaman.
"""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from base64 import b64encode
from hashlib import sha1

HOST = "127.0.0.1"
PORT = 5097
BASE = f"http://{HOST}:{PORT}"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PASSWORD = os.environ.get("APP_PASSWORD", "adminkso1234")

PAGES = [
    ("/invoice-cicilan", "Progress Invoice Cicilan"),
    ("/levelansir-retensi", "Retensi"),
    ("/status-dokumen", "Status Dokumen"),
    ("/inv-minggu-ini", "Inv. Minggu Ini"),
    ("/verifikasi", "Verifikasi Data"),
]

JS = """
(() => {
  const out = [];
  document.querySelectorAll('.ds-kpi').forEach(k => {
    const v = k.querySelector('.ds-kpi__value');
    if (!v) return;
    const cs = getComputedStyle(v);
    const label = k.querySelector('.ds-kpi__label');
    out.push({
      label: label ? label.textContent.trim() : '',
      fontSize: parseFloat(cs.fontSize),
      cls: v.className,
      kcls: k.className,
      zh: getComputedStyle(document.documentElement).zoom,
      f2xl: getComputedStyle(document.documentElement).getPropertyValue('--ds-fs-2xl'),
      rule: (() => { try { for (const sh of document.styleSheets) { try { for (const rl of sh.cssRules) { if (rl.selectorText && rl.selectorText.includes('.ds-kpi--compact') && rl.style.fontSize) return rl.selectorText+' => '+rl.style.fontSize; } } catch(e){} } return 'none'; } catch(e) { return 'err'; } })()
    });
  });
  return JSON.stringify(out);
})()
"""


class WS:
    def __init__(self, url):
        m = re.match(r"ws://([^:/]+):(\d+)(/.*)", url)
        self.sock = socket.create_connection((m.group(1), int(m.group(2))), timeout=20)
        key = b64encode(os.urandom(16)).decode()
        req = (
            f"GET {m.group(3)} HTTP/1.1\r\nHost: {m.group(1)}:{m.group(2)}\r\n"
            f"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
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
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

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


def wait_http(url, tries=60):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def main():
    env = dict(os.environ, APP_PASSWORD=PASSWORD)
    logs = tempfile.TemporaryFile()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import app; app.app.run(host='%s', port=%d, debug=False, use_reloader=False)" % (HOST, PORT)],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env, stdout=logs, stderr=subprocess.STDOUT,
    )
    profile = tempfile.mkdtemp(prefix="kpi-font-")
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=9334", f"--user-data-dir={profile}",
         "--window-size=1920,1080", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    fails = []
    try:
        if not wait_http(BASE + "/login"):
            print("FAIL server tidak hidup")
            return 1
        for _ in range(80):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9334/json/list", timeout=1).read())
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("FAIL chrome devtools tidak siap")
            return 1

        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            print("FAIL tidak ada tab page")
            return 1
        ws = WS(page_tabs[0]["webSocketDebuggerUrl"])
        midrc = [0]

        def jcall(m, p=None):
            midrc[0] += 1
            return ws.call(midrc[0], m, p)

        jcall("Page.enable")
        jcall("Runtime.enable")
        jcall("Emulation.setDeviceMetricsOverride", {"width": 1920, "height": 1080, "deviceScaleFactor": 1, "mobile": False})

        jcall("Page.navigate", {"url": BASE + "/login"})
        time.sleep(2)
        jcall("Runtime.evaluate", {"expression": f"""
          document.getElementById('password').value='{PASSWORD}';
          document.getElementById('loginForm').submit();
        """})
        time.sleep(2.5)

        results = {}
        for path, name in PAGES:
            jcall("Page.navigate", {"url": BASE + path})
            time.sleep(2.5)
            r = jcall("Runtime.evaluate", {"expression": JS, "returnByValue": True})
            val = r.get("result", {}).get("result", {}).get("value")
            if not val or val == "[]":
                dbg = jcall("Runtime.evaluate", {"expression": "document.title+' | '+location.pathname+' | dsKpi='+document.querySelectorAll('.ds-kpi').length+' | body='+document.body.className", "returnByValue": True})
                print("  DBG", name, dbg.get("result",{}).get("result",{}).get("value"))
            results[name] = json.loads(val) if val else []

        baseline = None
        for name, _ in [(n, p) for p, n in PAGES]:
            rows = results.get(name, [])
            if not rows:
                fails.append(f"{name}: tidak ada KPI terdeteksi")
                continue
            base_sizes = [r["fontSize"] for r in rows if "val-sm" not in r["cls"] and "val-xs" not in r["cls"]]
            if not base_sizes:
                fails.append(f"{name}: tidak ada KPI ukuran dasar")
                continue
            top = max(set(base_sizes), key=base_sizes.count)
            if baseline is None:
                baseline = top
            flag = "OK " if abs(top - baseline) < 0.5 else "BAD"
            if flag == "BAD":
                fails.append(f"{name}: KPI dasar {top}px != {baseline}px")
            print(f"{flag} {name:22s} dasar={top}px  semua={sorted(set(r['fontSize'] for r in rows))}")
            if flag == "BAD":
                for r in rows[:2]:
                    print(f"      kcls={r['kcls']!r} vcls={r['cls']!r} fs={r['fontSize']} zoom={r['zh']}")
                    print(f"      --ds-fs-2xl={r['f2xl']!r} rule={r['rule']!r}")

        print()
        if fails:
            print("GAGAL:")
            for f in fails:
                print("  - " + f)
            return 1
        print(f"SEMUA LOLOS - font-size KPI seragam ({baseline}px)")
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
