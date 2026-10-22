const fs = require('fs');
const c = fs.readFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', 'utf8');

// Replace the jtDataLabels plugin section with fixed version
const oldPlugin = `    plugins: [{
      id: 'jtDataLabels',
      afterDatasetsDraw(chart) {
        const { ctx: cx } = chart;
        const yScale = chart.scales.y;
        const xScale = chart.scales.x;
        // Draw total (hutang) label above each stacked bar
        const metaStack = chart.getDatasetMeta(1); // bayar dataset (top of stack)
        if (!metaStack || !metaStack.data) return;
        metaStack.data.forEach((pt, i) => {
          const h = hutang[i] || 0;
          if (!h) return;
          const txt = fmtMoney(h);
          cx.save();
          cx.font = '700 10px Inter, system-ui, sans-serif';
          cx.fillStyle = '#16324f';
          cx.textAlign = 'center';
          cx.textBaseline = 'bottom';
          cx.fillText(txt, pt.x, pt.y - 6);
          cx.restore();
        });
      }
    }]`;

const newPlugin = `    plugins: [{
      id: 'jtDataLabels',
      afterDatasetsDraw(chart) {
        const { ctx: cx } = chart;
        const yScale = chart.scales.y;
        // Draw hutang total label above stacked bar — only when bar is tall enough
        const metaStack = chart.getDatasetMeta(1); // bayar = top of stack
        if (!metaStack || !metaStack.data) return;
        const maxHutang = Math.max(...hutang, 1);
        metaStack.data.forEach((pt, i) => {
          const h = hutang[i] || 0;
          // Skip: no debt, or bar too short to fit label without overlap
          if (!h || h < maxHutang * 0.05) return;
          // Skip if point is at/above chart top (value == yMax)
          if (pt.y <= yScale.top + 14) return;
          const txt = fmtMoney(h);
          cx.save();
          cx.font = '700 10px Inter, system-ui, sans-serif';
          cx.fillStyle = '#16324f';
          cx.textAlign = 'center';
          cx.textBaseline = 'bottom';
          cx.fillText(txt, pt.x, pt.y - 6);
          cx.restore();
        });
      }
    }]`;

if (!c.includes(oldPlugin)) {
  console.log('ERROR: old plugin block not found');
  process.exit(1);
}
const updated = c.replace(oldPlugin, newPlugin);
fs.writeFileSync('D:\\KERJAAN AYAH\\Base Monitoring Hutang APP\\templates\\laporan_jatuh_tempo.html', updated, 'utf8');
console.log('OK — plugin replaced, lines:', updated.split('\n').length);
