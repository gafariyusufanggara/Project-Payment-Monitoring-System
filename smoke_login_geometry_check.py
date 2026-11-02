import base64, json, os, socket, struct, subprocess, sys, threading, time, urllib.request, urllib.parse

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 5098
DBG = 9223
PROFILE = os.path.join(os.environ.get('TEMP', r'C:\Users\ADMINI~1\AppData\Local\Temp'), 'chrome-login-probe')
os.makedirs(PROFILE, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('APP_PASSWORD', 'adminkso1234')
from app import app
threading.Thread(target=lambda: app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False), daemon=True).start()
time.sleep(3.0)

proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={DBG}',
                         f'--user-data-dir={PROFILE}', '--no-first-run', '--no-default-browser-check',
                         '--disable-gpu', '--hide-scrollbars', 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws_url = None
for _ in range(60):
    try:
        tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{DBG}/json', timeout=2).read())
        page = [t for t in tabs if t.get('type') == 'page']
        if page:
            ws_url = page[0]['webSocketDebuggerUrl']; break
    except Exception:
        pass
    time.sleep(0.3)

fails = []
def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' -- ' + detail) if detail else ''))
    if not cond: fails.append(name)

if not ws_url:
    check('chrome devtools tersambung', False, 'tidak ada tab')
    proc.kill(); sys.exit(1)

u = urllib.parse.urlparse(ws_url)
sock = socket.create_connection((u.hostname, u.port), timeout=25)
key = base64.b64encode(os.urandom(16)).decode()
sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
              f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
buf = b''
while b'\r\n\r\n' not in buf:
    buf += sock.recv(4096)
head, buf = buf.split(b'\r\n\r\n', 1)
check('websocket handshake', b'101' in head, head.decode('latin1').split('\r\n')[0] if head else '')

def ws_send(obj):
    data = json.dumps(obj).encode()
    n = len(data)
    hdr = bytearray([0x81])
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126); hdr += struct.pack('>H', n)
    else:
        hdr.append(0x80 | 127); hdr += struct.pack('>Q', n)
    mask = os.urandom(4)
    hdr += mask
    sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

def recvn(n):
    global buf
    while len(buf) < n:
        chunk = sock.recv(65536)
        if not chunk: raise ConnectionError('closed')
        buf += chunk
    out, buf = buf[:n], buf[n:]
    return out

def ws_recv():
    b0, b1 = recvn(2)
    ln = b1 & 0x7F
    if ln == 126: ln = struct.unpack('>H', recvn(2))[0]
    elif ln == 127: ln = struct.unpack('>Q', recvn(8))[0]
    mask = recvn(4) if b1 & 0x80 else None
    payload = recvn(ln)
    if mask: payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return payload.decode('utf8', 'replace')

mid = [0]
def send(method, params=None):
    mid[0] += 1
    ws_send({'id': mid[0], 'method': method, 'params': params or {}})
    for _ in range(500):
        msg = json.loads(ws_recv())
        if msg.get('id') == mid[0]:
            if 'error' in msg: raise RuntimeError(msg['error'])
            return msg.get('result', {})
    raise RuntimeError('no reply ' + method)

send('Page.enable'); send('Runtime.enable')
send('Emulation.setDeviceMetricsOverride', {'width': 1920, 'height': 1080, 'deviceScaleFactor': 1, 'mobile': False})
send('Page.navigate', {'url': f'http://127.0.0.1:{PORT}/login'})
time.sleep(3.0)

EXPR = """(() => {
  const el = document.querySelector('.auth-split');
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el); const bs = getComputedStyle(document.body);
  return JSON.stringify({
    vh: window.innerHeight, vw: window.innerWidth,
    bottom: Math.round(r.bottom), top: Math.round(r.top), h: Math.round(r.height), w: Math.round(r.width),
    zoom: bs.zoom, bodyOverflow: bs.overflow,
    htmlOverflow: getComputedStyle(document.documentElement).overflow,
    scrollH: document.documentElement.scrollHeight,
    minH: cs.minHeight, height: cs.height
  });
})()"""
def measure():
    res = send('Runtime.evaluate', {'expression': EXPR, 'returnByValue': True})
    return json.loads(res['result']['value'])

m = measure(); print('1920x1080 ->', json.dumps(m))
check('desktop: body ter-zoom 0.9', abs(float(m['zoom']) - 0.9) < 0.001, m['zoom'])
check('desktop: .auth-split menyentuh dasar layar', abs(m['bottom'] - m['vh']) <= 1, f"bottom={m['bottom']} vh={m['vh']}")
check('desktop: tinggi = viewport (tanpa scroll)', abs(m['h'] - m['vh']) <= 1, f"h={m['h']} vh={m['vh']}")
check('desktop: scrollHeight <= viewport', m['scrollH'] <= m['vh'] + 1, f"scrollH={m['scrollH']}")
check('desktop: lebar penuh', abs(m['w'] - m['vw']) <= 1, f"w={m['w']} vw={m['vw']}")

send('Emulation.setDeviceMetricsOverride', {'width': 1280, 'height': 720, 'deviceScaleFactor': 1, 'mobile': False})
time.sleep(1.2); m2 = measure(); print('1280x720  ->', json.dumps(m2))
check('1280x720: menyentuh dasar', abs(m2['bottom'] - m2['vh']) <= 1, f"bottom={m2['bottom']} vh={m2['vh']}")

send('Emulation.setDeviceMetricsOverride', {'width': 1024, 'height': 768, 'deviceScaleFactor': 1, 'mobile': False})
time.sleep(1.2); m2b = measure(); print('1024x768  ->', json.dumps(m2b))
check('1024 (tumpuk): overflow dilonggarkan', 'auto' in (m2b['htmlOverflow'] + m2b['bodyOverflow']), f"html={m2b['htmlOverflow']} body={m2b['bodyOverflow']}")

send('Emulation.setDeviceMetricsOverride', {'width': 375, 'height': 667, 'deviceScaleFactor': 2, 'mobile': True})
time.sleep(1.5); m3 = measure(); print('375x667   ->', json.dumps(m3))
# Meta viewport sengaja dikunci width=1280 agar browser mobile memakai tata
# letak desktop. Jadi lebar CSS harus 1280, bukan 375.
check('mobile: viewport CSS terkunci 1280 (mode desktop)', m3['vw'] >= 1280, f"vw={m3['vw']}")
send('Emulation.setDeviceMetricsOverride', {'width': 375, 'height': 420, 'deviceScaleFactor': 2, 'mobile': True})
time.sleep(1.5); m4 = measure(); print('375x420   ->', json.dumps(m4))
# Mode desktop terkunci: tinggi layout ikut 1280 CSS px, jadi tidak lagi
# wajib overflow. Yang penting tidak ada konten terpotong (dicek di bawah).
check('mobile pendek: viewport CSS tetap 1280', m4['vw'] >= 1280, f"vw={m4['vw']}")
check('mobile pendek: form tidak terpotong (scrollH >= h)', m4['scrollH'] >= m4['h'] - 1, f"scrollH={m4['scrollH']} h={m4['h']}")
form = send('Runtime.evaluate', {'expression': "JSON.stringify((()=>{const b=document.querySelector('.auth-btn').getBoundingClientRect();return {top:Math.round(b.top),bottom:Math.round(b.bottom)}})())", 'returnByValue': True})
fb = json.loads(form['result']['value'])
check('mobile pendek: tombol Masuk berada di dalam area scroll', fb['bottom'] <= m4['scrollH'] + 1, f"btnBottom={fb['bottom']} scrollH={m4['scrollH']}")

sock.close(); proc.kill()
print()
if fails:
    print('FAILED:', len(fails)); sys.exit(1)
print('ALL CHECKS PASSED')
