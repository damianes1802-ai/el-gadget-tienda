/* ============================================================
   MARKETING EL GADGET — Referidos analytics
   ============================================================ */

let _refPeriod = 'all';
let _refSort = 'revenue';

function exportReferidosCSV() {
  const data = _cache;
  if (!data.referidos || !data.referidos.length) { toast('No hay datos para exportar', 'error'); return; }

  const referidos = data.referidos || [];
  const headers = ['nombre', 'email', 'codigo', 'estado', 'ventas', 'revenue', 'comision_total', 'comision_pendiente', 'tier', 'fecha_registro'];
  const rows = referidos.map(r => {
    const tier = calcReferidoTier(r);
    return [
      r.nombre || '',
      r.email || '',
      r.codigo || '',
      r.activo ? 'activo' : 'inactivo',
      r.cantidad_ventas || 0,
      r.total_ventas || 0,
      r.comision_total || 0,
      r.comision_pendiente || 0,
      tier,
      csvFormatDate(r.creado_at || r.created_at || ''),
    ];
  });

  downloadCSV(`elgadget_referidos_${csvDateNow()}.csv`, headers, rows);
}

async function loadReferidos() {
  const data = _cache;
  if (!data.referidos) return;

  const ordenes = enrichOrdenes(data.ordenes, data.referidos, data.descuentos);
  const referidos = data.referidos || [];
  const activos = referidos.filter(r => r.activo);
  const inactivos = referidos.filter(r => !r.activo);

  const refRevenue = calcReferidoRevenue(ordenes);
  const comPagadas = referidos.reduce((s, r) => s + ((r.comision_total || 0) - (r.comision_pendiente || 0)), 0);
  const comPendientes = referidos.reduce((s, r) => s + (r.comision_pendiente || 0), 0);

  renderTrendCard(document.getElementById('ref-stat-activos'), { label: 'Referidos activos', value: formatNumber(activos.length), sub: `${inactivos.length} inactivos` });
  renderTrendCard(document.getElementById('ref-stat-revenue'), { label: 'Ventas via referidos', value: formatPrice(refRevenue) });
  renderTrendCard(document.getElementById('ref-stat-pagadas'), { label: 'Comisiones pagadas', value: formatPrice(comPagadas) });
  renderTrendCard(document.getElementById('ref-stat-pendientes'), { label: 'Comisiones pendientes', value: formatPrice(comPendientes) });

  renderReferidosTabla(referidos);
}

function renderReferidosTabla(referidos) {
  const tbody = document.getElementById('referidos-tbody');
  if (!referidos.length) { tbody.innerHTML = '<tr><td colspan="8" class="table-empty">Sin referidos</td></tr>'; return; }

  const sorted = [...referidos].sort((a, b) => {
    if (_refSort === 'revenue') return (b.total_ventas || 0) - (a.total_ventas || 0);
    if (_refSort === 'comision') return (b.comision_total || 0) - (a.comision_total || 0);
    return (b.creado_at || '').localeCompare(a.creado_at || '');
  });

  tbody.innerHTML = sorted.map(r => {
    const tier = calcReferidoTier(r);
    const lastSale = (r.periodos && r.periodos.length) ? r.periodos[r.periodos.length - 1].periodo : '-';
    return `<tr>
      <td>${escapeHtml(r.nombre)}</td>
      <td><code>${escapeHtml(r.codigo)}</code></td>
      <td class="text-center">${r.cantidad_ventas || 0}</td>
      <td class="text-right">${formatPrice(r.total_ventas || 0)}</td>
      <td class="text-right">${formatPrice(r.comision_total || 0)}</td>
      <td class="text-center">${badgeTier(tier)}</td>
      <td class="text-center">${escapeHtml(lastSale)}</td>
      <td class="text-center">${r.activo ? '<span class="badge badge-green">Activo</span>' : '<span class="badge badge-red">Inactivo</span>'}</td>
    </tr>`;
  }).join('');
}

document.getElementById('ref-sort')?.addEventListener('change', (e) => {
  _refSort = e.target.value;
  renderReferidosTabla(_cache.referidos || []);
});
