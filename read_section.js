const fs = require('fs');
const c = fs.readFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', 'utf8');
const lines = c.split('\n');
// Print lines 425-510 (0-indexed: 424-509)
for (let i = 424; i < 510 && i < lines.length; i++) {
  process.stdout.write((i+1) + ': ' + lines[i] + '\n');
}
