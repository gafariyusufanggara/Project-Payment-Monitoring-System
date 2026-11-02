import os, re, threading, time, urllib.request, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('APP_PASSWORD', 'adminkso1234')
from app import app

PORT = 5099
srv = threading.Thread(target=lambda: app.run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False), daemon=True)
srv.start()
time.sleep(3.0)

html = urllib.request.urlopen(f'http://127.0.0.1:{PORT}/login', timeout=15).read().decode('utf8', 'replace')

fails = []

def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' -- ' + detail) if detail and not cond else ''))
    if not cond:
        fails.append(name)

check('.auth-split punya min-height 100dvh', 'min-height: 100dvh' in html)
check('kompensasi calc(100dvh / var(--ui-zoom))', 'calc(100dvh / var(--ui-zoom))' in html)
check('desktop lock di >=1025', '@media (min-width: 1025px)' in html)
check('unlock overflow di <=1024', 'overflow: auto' in html)
check('tidak ada sisa min-height: 100vh tanpa fallback dvh',
      re.search(r'\.auth-split\s*\{[^}]*min-height:\s*100vh;\s*min-height:\s*100dvh;', html) is not None)

print()
if fails:
    print('FAILED:', len(fails))
    sys.exit(1)
print('ALL CHECKS PASSED')
