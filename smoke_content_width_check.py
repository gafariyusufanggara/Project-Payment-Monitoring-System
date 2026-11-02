import base64, json, os, socket, struct, subprocess, sys, threading, time, urllib.request, urllib.parse

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP); os.chdir(APP)
os.environ.setdefault('APP_PASSWORD', 'adminkso1234')
from app import app

PORT = 5096; DBG = 9221
PROFILE = os.path.join(os.environ.get('TEMP'), 'chrome-width-probe2')
os.makedirs(PROFILE, exist_ok=True)
threading.Thread(target=lambda: app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False), daemon=True).start()
time.sleep(3.0)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={DBG}',
                         f'--user-data-dir={PROFILE}', '--no-first-run', '--disable-gpu',
                         '--hide-scrollbars', 'about:blank'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ws_url = None
for _ in range(60):
    try:
        tabs = json.loads(urllib.request.urlopen(f'http://127.0.0.1:{DBG}/json', timeout=2).read())
        pg = [t for t in tabs if t.get('type') == 'page']
        if pg: ws_url = pg[0]['webSocketDebuggerUrl']; break
    except Exception: pass
    time.sleep(0.3)

u = urllib.parse.urlparse(ws_url)
sock = socket.create_connection((u.hostname, u.port), timeout=25)
key = base64.b64encode(os.urandom(16)).decode()
sock.sendall((f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
              f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
b = b''
while b'\r\n\r\n' not in b: b += sock.recv(4096)
buf = [b.split(b'\r\n\r\n', 1)[1]]

def send(o):
    d = json.dumps(o).encode(); n = len(d); h = bytearray([0x81])
    if n < 126: h.append(0x80 | n)
    elif n < 65536: h.append(0x80 | 126); h += struct.pack('>H', n)
    else: h.append(0x80 | 127); h += struct.pack('>Q', n)
    m = os.urandom(4); h += m
    sock.sendall(bytes(h) + bytes(x ^ m[i % 4] for i, x in enumerate(d)))

def recvn(n):
    while len(buf[0]) < n: buf[0] += sock.recv(65536)
    o, r = buf[0][:n], buf[0][n:]; buf[0] = r; return o

def recv():
    b0, b1 = recvn(2); ln = b1 & 0x7f
    if ln == 126: ln = struct.unpack('>H', recvn(2))[0]
    elif ln == 127: ln = struct.unpack('>Q', recvn(8))[0]
    m = recvn(4) if b1 & 0x80 else None; pl = recvn(ln)
    if m: pl = bytes(x ^ m[i % 4] for i, x in enumerate(pl))
    return pl.decode('utf8', 'replace')

mid = [0]
def cmd(method, params=None):
    mid[0] += 1; send({'id': mid[0], 'method': method, 'params': params or {}})
    for _ in range(2000):
        r = json.loads(recv())
        if r.get('id') == mid[0]:
            if 'error' in r: raise RuntimeError(r['error'])
            return r.get('result', {})
    raise RuntimeError('timeout ' + method)

cmd('Page.enable'); cmd('Runtime.enable')
cmd('Emulation.setDeviceMetricsOverride', {'width': 1920, 'height': 1080, 'deviceScaleFactor': 1, 'mobile': False})
cmd('Page.navigate', {'url': f'http://127.0.0.1:{PORT}/login'}); time.sleep(1.5)
cmd('Runtime.evaluate', {'expression': "document.getElementById('password').value='adminkso1234';document.getElementById('loginForm').submit();"})
time.sleep(3.0)

EXPR = """(() => {
  const c = document.querySelector('.content-area');
  const w = document.querySelector('.dash-wrap,.rp-wrap,.cic-wrap,.ds-wrap,.kc-wrap,.kd-wrap,.vf-wrap,.prj-wrap,.prj-page');
  const t = document.querySelector('.rp-tbl,.cic-table,.ds-table,.kd-table');
  const cs = w ? getComputedStyle(w) : null;
  return JSON.stringify({
    contentW: c ? Math.round(c.getBoundingClientRect().width) : null,
    wrapW: w ? Math.round(w.getBoundingClientRect().width) : null,
    wrapClass: w ? w.className : null,
    maxW: cs ? cs.maxWidth : null,
    tableW: t ? Math.round(t.getBoundingClientRect().width) : null,
    docScrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth
  });
})()"""

PAGES = [('dashboard', ''), ('inv_minggu', '/inv-minggu-ini'), ('inv_bulan', '/inv-bulan-ini'),
         ('retensi', '/levelansir-retensi'), ('status_dokumen', '/status-dokumen'),
         ('kontrak', '/kontrak/'), ('kontrak_detail', '/kontrak/CONTRACT_ID'),
         ('progress_cicilan', '/invoice-cicilan'), ('verifikasi', '/verifikasi'),
         ('daftar_proyek', '/project/'), ('proyek_dashboard', '/project/PROJECT_ID/dashboard'),
         ('proyek_detail', '/project/PROJECT_ID/edit')]
VIEWPORTS = [(1920, 1080), (1440, 900), (1280, 800), (375, 667)]

fails = []
def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' -- ' + detail) if detail and not cond else ''))
    if not cond: fails.append(name)

# cari contract_id nyata
r0 = cmd('Runtime.evaluate', {'expression': "JSON.stringify(Array.from(document.querySelectorAll('a[href*=\"/kontrak/\"]')).map(a=>a.getAttribute('href')).filter(h=>/\\/kontrak\\/\\d+$/.test(h)).slice(0,1))", 'returnByValue': True})
try:
    cand = json.loads(r0['result']['value']) or []
except Exception:
    cand = []
CONTRACT_PATH = cand[0] if cand else '/kontrak/1'
print('contract path ->', CONTRACT_PATH)
PAGES = [(n, (CONTRACT_PATH if n == 'kontrak_detail' else pp)) for n, pp in PAGES]

# cari project_id nyata dari halaman daftar proyek
cmd('Page.navigate', {'url': f'http://127.0.0.1:{PORT}/project/'}); time.sleep(2.0)
r1 = cmd('Runtime.evaluate', {'expression': "JSON.stringify(Array.from(document.querySelectorAll('a[href*=\"dashboard\"]')).map(a=>a.getAttribute('href')).filter(h=>/\\d+\\/dashboard$/.test(h)).slice(0,1))", 'returnByValue': True})
try:
    pc = json.loads(r1['result']['value']) or []
except Exception:
    pc = []
PROJECT_ID = '1'
if pc:
    PROJECT_ID = pc[0].split('/')[2]
print('project id ->', PROJECT_ID)
PAGES = [(n, pp.replace('PROJECT_ID', PROJECT_ID)) for n, pp in PAGES]

baseline = {}
for vw, vh in VIEWPORTS:
    cmd('Emulation.setDeviceMetricsOverride', {'width': vw, 'height': vh, 'deviceScaleFactor': 1, 'mobile': vw <= 480})
    time.sleep(0.6)
    print(f'--- viewport {vw}x{vh} ---')
    for name, path in PAGES:
        cmd('Page.navigate', {'url': f'http://127.0.0.1:{PORT}/{path}'}); time.sleep(2.2)
        r = cmd('Runtime.evaluate', {'expression': EXPR, 'returnByValue': True})
        d = json.loads(r['result']['value'])
        print(f"  {name}: {json.dumps(d)}")
        if d['wrapW'] is None:
            check(f'{name} @{vw}: wrapper ditemukan', False, 'wrapper null'); continue
        if vw == 1920 and name == 'dashboard':
            baseline['w'] = d['wrapW']
        if vw == 1920:
            check(f'{name} @1920 lebar == dashboard', abs(d['wrapW'] - baseline.get('w', d['wrapW'])) <= 2,
                  f"wrap={d['wrapW']} dash={baseline.get('w')}")
        check(f'{name} @{vw}: tanpa max-width', d['maxW'] in ('none', ''), d['maxW'])
        check(f'{name} @{vw}: tidak ada scroll horizontal', d['docScrollW'] <= d['innerW'] + 1,
              f"scrollW={d['docScrollW']} innerW={d['innerW']}")

sock.close(); proc.kill()
print()
if fails:
    print('FAILED:', len(fails)); sys.exit(1)
print('ALL CHECKS PASSED')
