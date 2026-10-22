const fs = require('fs');
const c = fs.readFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', 'utf8');
// Find the jtDataLabels plugin section
const start = c.indexOf("id: 'jtDataLabels'");
const end = c.indexOf('   });\n}\nensureChartJs', start);
console.log(c.substring(start - 5, end + 20));
