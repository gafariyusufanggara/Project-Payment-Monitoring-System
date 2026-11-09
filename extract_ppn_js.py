p = r'D:\KERJAAN AYAH\Base Monitoring Hutang APP\templates\laporan_ppn.html'
s = open(p, encoding='utf-8').read()
i = s.find('<script>')
j = s.find('</script>', i)
js = s[i+8:j]
open(r'D:\KERJAAN AYAH\Base Monitoring Hutang APP\ppn_script.js', 'w', encoding='utf-8').write(js)
print('len', len(js))
