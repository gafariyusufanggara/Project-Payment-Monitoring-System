import json, os, re, socket, struct, subprocess, sys, tempfile, time, urllib.request
from base64 import b64encode

HOST = "127.0.0.1"
PORT = 5097
BASE = f"http://{HOST}:{PORT}"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PASSWORD = os.environ.get("APP_PASSWORD", "adminkso1234")

JS = """(() => {
  const a = document.querySelector('#navProgressKontrak');
  if (!a) return JSON.stringify({found: false});
  const badge = a.querySelector('#sidebarPoBadge');
  const label = a.querySelector('span:not(.nav-badge)');
  const ar = a.getBoundingClientRect();
  const lr = label ? label.getBoundingClientRect() : null;
  const br = badge && !badge.hidden ? badge.getBoundingClientRect() : null;
  const cs = badge ? getComputedStyle(badge) : null;
  return JSON.stringify({
    found: true,
    badgeVisible: !!(badge && !badge.hidden),
    badgeInline: badge ? badge.classList.contains('nav-badge-inline') : false,
    badgeMarginLeft: cs ? cs.marginLeft : null,
    badgeFlexShrink: cs ? cs.flexShrink : null,
    labelEllipsis: label ? getComputedStyle(label).textOverflow : null,
    badgeRight: br ? br.right : null,
    anchorRight: ar.right,
    overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    clipped: br ? br.right > ar.right + 1 : null,
  });
})()"""


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
            header += struct.pack("!B", n | 0x80)
        elif n < 65536:
            header += struct.pack("!B", 126 | 0x80) + struct.pack("!H", n)
        else:
            header += struct.pack("!B", 127 | 0x80) + struct.pack("!Q", n)
        header += mask
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + payload)

    def recv(self):
        while len(self.buf) < 2:
            self.buf += self.sock.recv(65536)
        b1 = self.buf[1] & 0x7F
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
            off = 2
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
    profile = tempfile.mkdtemp(prefix="nav-badge-")
    chrome = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
         "--remote-debugging-port=9335", f"--user-data-dir={profile}",
         "--window-size=1440,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_http(BASE + "/login"):
            print("FAIL server tidak hidup")
            return 1
        for _ in range(80):
            try:
                tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9335/json/list", timeout=1).read())
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("FAIL chrome devtools tidak siap")
            return 1
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        ws = WS(page_tabs[0]["webSocketDebuggerUrl"])
        mid = [0]

        def jcall(m, p=None):
            mid[0] += 1
            return ws.call(mid[0], m, p)

        jcall("Page.enable")
        jcall("Runtime.enable")
        jcall("Page.navigate", {"url": BASE + "/login"})
        time.sleep(2)
        jcall("Runtime.evaluate", {"expression": f"document.getElementById('password').value='{PASSWORD}'; document.getElementById('loginForm').submit();"})
        time.sleep(2.5)
        jcall("Page.navigate", {"url": BASE + "/kontrak/"})
        time.sleep(2.5)
        r = jcall("Runtime.evaluate", {"expression": JS, "returnByValue": True})
        val = json.loads(r.get("result", {}).get("result", {}).get("value"))
        print(json.dumps(val, indent=1))
        assert val["found"], "nav Progress Kontrak tak ada"
        assert val["badgeInline"], "badge belum inline"
        assert val["badgeMarginLeft"] == "2px", val
        assert val["badgeFlexShrink"] == "0", val
        assert val["labelEllipsis"] == "ellipsis", val
        assert val["overflowX"] is False, val
        if val["badgeVisible"]:
            assert val["clipped"] is False, val
        else:
            print("badge hidden (po_review_count=0), cek geometri tanpa badge")
        print("NAV BADGE OK")
        return 0
    finally:
        chrome.terminate()
        server.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
