
(function () {
const REKANAN_DATA = {{ report_rows | tojson }};
function monthSel(){ return document.getElementById('monthSel'); }
function activeMonthKey(){ const s=monthSel(); return s?s.value:''; }
// Tahun-bulan periode aktif ('YYYY-MM'); #monthSel.value sudah 'YYYY-MM'.
function activeYearMonth(){ const s=monthSel(); return s&&s.value?s.value.slice(0,7):''; }
// Tanggal cut off 'YYYY-MM-DD' langsung dari native date picker.
// '' berarti Tanpa Cut Off.
function currentCutoffDate(){ const inp=document.getElementById('cutoffDate'); return inp&&inp.value?inp.value:''; }
// Batasi date picker hanya pada bulan periode aktif.
function setCutoffBounds(){
  const inp=document.getElementById('cutoffDate'); const ym=activeYearMonth();
  if(!inp||!ym) return;
  const p=ym.split('-'); const year=parseInt(p[0],10); const month=parseInt(p[1],10);
  if(!year||!month) return;
  const pad=n=>String(n).padStart(2,'0');
  inp.min=year+'-'+pad(month)+'-01';
  inp.max=year+'-'+pad(month)+'-'+pad(new Date(year,month,0).getDate());
  if(inp.value&&(inp.value<inp.min||inp.value>inp.max)) inp.value=inp.min;
}
  function fmtDate(iso){ const p=String(iso).split('-'); return p.length===3?(p[2]+'-'+p[1]+'-'+p[0]):iso; }
function updateCutoffLabel(monthKey){ const lbl=document.getElementById('cutoffMonthLabel'); if(!lbl) return; const base=monthLabel(monthKey||activeMonthKey()); const d=currentCutoffDate(); lbl.textContent=d?(base+' · s/d '+fmtDate(d)):base; }
function setSelValue(sel,key){ if(!sel||!key) return false; for(let i=0;i<sel.options.length;i++){ if(sel.options[i].value===key){ sel.value=key; return true; } } return false; }
function monthLabel(key){ const s=monthSel(); if(s){ for(const o of s.options){ if(o.value===key) return o.textContent.trim(); } } return key; }
function selectMonth(key,skipCutoff){ setSelValue(monthSel(), key); document.querySelectorAll('.month-section').forEach(el=>{ el.hidden=(el.id!=='section-'+key); }); const inp=document.getElementById('cutoffDate'); if(inp&&!skipCutoff) inp.value=''; setCutoffBounds(); updateCutoffLabel(key); if(window.TableEnhance) window.TableEnhance.refresh(); if(isVendorPrioritasOnly()){ const s=document.getElementById('section-'+key); if(s) recomputeSection(s, true); } if(!skipCutoff){ const d=document.getElementById('cutoffDate'); if(d&&d.value) applyCutoff(); } }
function bindMonthSel(){ const sel=monthSel(); if(!sel||sel.dataset.bound) return; sel.dataset.bound='1'; sel.addEventListener('change', function(){ selectMonth(this.value); }); if(sel.value) selectMonth(sel.value, true); }
function exportExcel(btn){ btn=btn||document.getElementById('exportBtn'); const orig=btn.innerHTML; btn.innerHTML='<span class="spinner-border spinner-border-sm me-1" role="status"></span> Mengunduh...'; btn.disabled=true; const key=activeMonthKey(); const params=new URLSearchParams(); if(key) params.set('month', key); const cutoff=currentCutoffDate(); if(cutoff) params.set('cutoff', cutoff); const qs=params.toString(); window.location.href='/laporan-ppn/export'+(qs?'?'+qs:''); setTimeout(()=>{ btn.innerHTML=orig; btn.disabled=false; },3000); }
function applyCutoff(){ const key=activeMonthKey(); const params=new URLSearchParams(); const cutoff=currentCutoffDate(); if(cutoff) params.set('cutoff', cutoff); if(key) params.set('month', key); const qs=params.toString(); window.location.href='/laporan-ppn'+(qs?'?'+qs:''); }
function clearCutoff(){ const inp=document.getElementById('cutoffDate'); if(inp) inp.value=''; applyCutoff(); }
let _activeRow=null;
function showDetail(monthKey,rekanan,rowEl){
  if(_activeRow) _activeRow.classList.remove('selected');
  if(rowEl){ rowEl.classList.add('selected'); _activeRow=rowEl; }
  const allInvoices=[];
  for(const m of REKANAN_DATA){ const rec=m.rekanan_list.find(s=>s.rekanan===rekanan); if(rec&&rec.invoices) for(const inv of rec.invoices) allInvoices.push({...inv, bulan:m.label, bulanKey:m.key}); }
  allInvoices.sort((a,b)=>(a.tgl_berkas<b.tgl_berkas?1:a.tgl_berkas>b.tgl_berkas?-1:0));
  const perLabel=monthLabel(monthKey)||monthKey;
  document.getElementById('modalLabel').innerHTML='<i class="bi bi-receipt"></i> '+esc(rekanan)+' <span class="mm mm-cnt" role="status" aria-live="polite">'+allInvoices.length+' invoice</span> <span class="mm">Periode '+esc(perLabel)+'</span>';
  const search=document.getElementById('invoiceSearch'); search.value='';
  const body=document.getElementById('modalInvoices'); const tfoot=document.getElementById('modalTfoot');
  let currentInvoiceTotal=0, currentPaymentTotal=0;
  if(allInvoices.length===0){ document.getElementById('currentInvoiceTotal').textContent='Rp 0'; document.getElementById('currentPaymentTotal').textContent='Rp 0'; body.innerHTML='<tr class="em"><td colspan="10"><i class="bi bi-inbox"></i>Tidak ada data untuk '+esc(rekanan)+'</td></tr>'; if(tfoot) tfoot.hidden=true; }
  else {
    let tDpp=0,tPpn=0,tB=0,tS=0;
    body.innerHTML=allInvoices.map(inv=>{
      const sisa=Math.max(0,(Number(inv.ppn)||0)-(Number(inv.bayar_ppn)||0)); tDpp+=Number(inv.harga_excl)||0; tPpn+=Number(inv.ppn)||0; tB+=Number(inv.bayar_ppn)||0; tS+=sisa;
      const cls = sisa > 1 ? 'sn' : 'sz';  // SISA_EPS (Rp 1)
      const invYM=String(inv.tgl_berkas||'').slice(0,7); const payYM=String(inv.tgl_bayar_ppn||'').slice(0,7);
      const invoiceIsCurrent=invYM===monthKey; const paymentIsCurrent=payYM===monthKey;
      if(invoiceIsCurrent) currentInvoiceTotal+=Number(inv.ppn??0)||0;
      if(paymentIsCurrent) currentPaymentTotal+=Number(inv.bayar_ppn??0)||0;
      return '<tr class="'+(invoiceIsCurrent?'hl-row-inv':(paymentIsCurrent?'hl-row-pay':''))+'" data-search="'+esc([inv.invoice,inv.po,inv.deskripsi].join(' ').toLowerCase())+'" data-prioritas="'+(inv.prioritas||'0')+'"><td class="l '+(invoiceIsCurrent?'hl-date-invoice':'')+'">'+esc(fmtDate(inv.tgl_berkas))+'</td>'+CellExpand.td(inv.invoice,'l iv',40)+CellExpand.td(inv.po,'l',25)+'<td class="l">'+esc(fmtDate(inv.jth_tempo))+'</td>'+CellExpand.td(inv.deskripsi,'l',40)+'<td class="m-h">'+fmt(inv.harga_excl)+'</td><td class="m-h">'+fmt(inv.ppn)+'</td><td class="l '+(paymentIsCurrent?'hl-date-payment':'')+'">'+esc(fmtDate(inv.tgl_bayar_ppn))+'</td><td class="m-p">'+fmt(inv.bayar_ppn)+'</td><td class="m-s '+cls+'">'+fmt(sisa)+'</td></tr>';
    }).join('');
    if(tfoot){ tfoot.hidden=false; document.getElementById('ftDpp').textContent=fmt(tDpp); document.getElementById('ftPpn').textContent=fmt(tPpn); document.getElementById('ftBayar').textContent=fmt(tB); const ftS=document.getElementById('ftSisa'); ftS.textContent=fmt(tS); ftS.className=tS>0?'t-s-pos':'t-s-zero'; }
  }
  document.getElementById('currentInvoiceTotal').textContent='Rp '+fmt(currentInvoiceTotal);
  document.getElementById('currentPaymentTotal').textContent='Rp '+fmt(currentPaymentTotal);
  _modalSearchEl = search;
  _modalBody = body;
  _modalAllInv = allInvoices;
  search.oninput = applyModalPrioritasFilter;
  applyModalPrioritasFilter();
  const modalEl=document.getElementById('ppnModal'); const modal=bootstrap.Modal.getOrCreateInstance(modalEl); modal.show();
  modalEl.addEventListener('hidden.bs.modal', function _onHide(){ modalEl.removeEventListener('hidden.bs.modal', _onHide); if(_activeRow){ _activeRow.classList.remove('selected'); _activeRow=null; } });

let _modalSearchEl = null;
let _modalBody = null;
let _modalAllInv = [];

// ─── filter prioritas (rekap halaman + modal) ───
function vendorPrioritasEl() { return document.getElementById('vendorPrioritasSel'); }
function isVendorPrioritasOnly() { const el = vendorPrioritasEl(); return el && el.checked; }

function recomputeSection(section, only) {
  let sdP = 0, sdB = 0, lP = 0, siP = 0, lB = 0, siB = 0, cnt = 0, pay = 0;
  const monthKey = section.dataset.nowKey || section.id.replace('section-', '');
  const month = REKANAN_DATA.find(m => m.key === monthKey);
  section.querySelectorAll('table.lp-tbl tbody tr[data-rekan]').forEach(tr => {
    const rekan = tr.dataset.rekan;
    const s = month && month.rekanan_list.find(x => x.rekanan === rekan);
    if (!s) { tr.hidden = true; return; }
    const show = !only || s.prioritas === '1';
    tr.hidden = !show;
    if (!show) return;
    sdP += Number(s.sd_ppn || 0); sdB += Number(s.sd_bayar_ppn || 0);
    lP += Number(s.lalu_ppn || 0); siP += Number(s.saat_ini_ppn || 0);
    lB += Number(s.lalu_bayar_ppn || 0); siB += Number(s.saat_ini_bayar_ppn || 0);
    cnt += Number(s.count || 0); pay += Number(s.ppn_pay_count || 0);
  });
  const sisa = Math.max(0, sdP - sdB);
  const set = (sel, v) => { const el = section.querySelector(sel); if (el) el.textContent = fmt(v); };
  set('[data-jt="hero-sisa"]', sisa);
  set('[data-jt="hero-hutang"]', sdP);
  set('[data-jt="hero-bayar"]', sdB);
  set('[data-jt="kpi-lalu-h"]', lP);
  set('[data-jt="kpi-si-h"]', siP);
  set('[data-jt="kpi-sd-h"]', sdP);
  set('[data-jt="kpi-lalu-b"]', lB);
  set('[data-jt="kpi-si-b"]', siB);
  set('[data-jt="kpi-sd-b"]', sdB);
  set('[data-jt="ft-lalu-h"]', lP);
  set('[data-jt="ft-si-h"]', siP);
  set('[data-jt="ft-sd-h"]', sdP);
  set('[data-jt="ft-lalu-b"]', lB);
  set('[data-jt="ft-si-b"]', siB);
  set('[data-jt="ft-sd-b"]', sdB);
  set('[data-jt="ft-sisa"]', sisa);
  const tc = section.querySelector('[data-jt="tag-cnt"]'); if (tc) tc.textContent = cnt + ' PPN';
  const tp = section.querySelector('[data-jt="tag-pay"]'); if (tp) tp.textContent = pay + ' Pembayaran';
}

function filterVendorPrioritas() {
  const only = isVendorPrioritasOnly();
  document.querySelectorAll('.month-section:not([hidden])').forEach(section => recomputeSection(section, only));
  if (window.TableEnhance) { window.TableEnhance.refresh(); window.TableEnhance.resetPage(); }
  applyModalPrioritasFilter();
}

function applyModalPrioritasFilter() {
  if (!_modalSearchEl || !_modalBody) return;
  const query = _modalSearchEl.value.trim().toLocaleLowerCase('id-ID');
  const only = isVendorPrioritasOnly();
  let visible = 0;
  _modalBody.querySelectorAll('tr[data-search]').forEach(row => {
    const prioOk = !only || row.dataset.prioritas === '1';
    row.hidden = !(prioOk && (!query || row.dataset.search.includes(query)));
    if (!row.hidden) visible++;
  });
  const mmEl = document.querySelector('#modalLabel .mm-cnt');
  if (mmEl) mmEl.textContent = (query || only)
    ? `${visible} dari ${_modalAllInv.length} invoice`
    : `${_modalAllInv.length} invoice`;
}

function esc(s){ return String(s||'-').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
function fmt(v){ return Math.round(Number(v||0)).toLocaleString('id-ID'); }
// Expose fungsi ke window (dipakai attribut inline onclick/onchange).
window.exportExcel = exportExcel;
window.showDetail = showDetail;
window.applyCutoff = applyCutoff;
window.clearCutoff = clearCutoff;
window.filterVendorPrioritas = filterVendorPrioritas;
// Re-init pada full load & setiap HTMX swap.
if (window.onPageReady) onPageReady(bindMonthSel);
else document.addEventListener('DOMContentLoaded', bindMonthSel);
  const cb = vendorPrioritasEl();
  if (cb && !cb.dataset.bound) { cb.dataset.bound = '1'; cb.addEventListener('change', filterVendorPrioritas); }
})();
