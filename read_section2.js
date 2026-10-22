const fs = require('fs');
const c = fs.readFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', 'utf8');
const lines = c.split('\n');
for (let i = 370; i < 430 && i < lines.length; i++) {
  process.stdout.write((i+1) + ': ' + lines[i] + '\n');
}
