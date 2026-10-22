const fs = require('fs');
const c = fs.readFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', 'utf8');
const lines = c.split('\n');
let out = [];
for (let i = 476; i < 510 && i < lines.length; i++) {
  out.push((i+1) + ': ' + lines[i]);
}
fs.writeFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\chk.txt', out.join('\n'), 'utf8');
