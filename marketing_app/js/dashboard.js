/* ============================================================
   MARKETING EL GADGET — Dashboard
   ============================================================ */

async function loadDashboard() {
  const data = _cache;
  if (!data.ordenes) return;

  const ordenes = enrichOrdenes(data.ordenes, data.referidos, data.descuentos);
  const mesActual = calcCurrentMonth(ordenes);
  const mesAnterior = calcPreviousMonth(ordenes);

  const revActual = calcRevenue(mesActual);
  const revAnterior = calcRevenue(mesAnterior);
  const aovActual = calcAOV(mesActual);
  const aovAnterior = calcAOV(mesAnterior);
  const spark = calcSparkline(ordenes, 6);

  // Stat cards
  renderTrendCard(document.getElementById('stat-revenue'), {
    label: 'Ventas del mes',
    value: formatPrice(revActual),
    delta: formatDelta(revActual, revAnterior),
    sparkData: spark,
  });

  renderTrendCard(document.getElementById('stat-orders'), {
    label: 'Pedidos del mes',
    value: formatNumber(mesActual.length),
    delta: formatDelta(mesActual.length, mesAnterior.length),
    sub: `${calcCurrentMonth(ordenes.filter(o => { const d = o._fecha; return d && d.toDateString() === new Date().toDateString(); })).length} hoy`,
  });

  const activeRefs = calcActiveReferidos(data.referidos);
  const refRevenue = calcReferidoRevenue(ordenes);
  renderTrendCard(document.getElementById('stat-referidos'), {
    label: 'Referidos activos',
    value: formatNumber(activeRefs),
    sub: `Generaron ${formatPrice(refRevenue)}`,
  });

  renderTrendCard(document.getElementById('stat-aov'), {
    label: 'Ticket promedio',
    value: formatPrice(aovActual),
    delta: formatDelta(aovActual, aovAnterior),
  });

  // Ventas por mes (barras apiladas)
  const byMonth = calcRevenueByMonth(ordenes, 12);
  renderBarChart(document.getElementById('chart-monthly'), byMonth, { stacked: true });

  // Donut fuente de ventas
  const bySource = calcRevenueBySource(ordenes);
  renderDonut(document.getElementById('chart-sources'), [
    { label: 'Referido', value: bySource.referido, color: CHART_COLORS.referido },
    { label: 'Orgánico', value: bySource.organico, color: CHART_COLORS.organico },
    { label: 'Promo', value: bySource.promo, color: CHART_COLORS.promo },
    { label: 'Mayorista', value: bySource.mayorista, color: CHART_COLORS.mayorista },
  ]);

  // Top referidos
  const topRefs = calcTopReferidos(data.referidos, 5);
  const topRefsEl = document.getElementById('top-referidos');
  if (topRefs.length) {
    topRefsEl.innerHTML = topRefs.map((r, i) => `
      <div class="rank-row">
        <span class="rank-pos">${i + 1}</span>
        <div class="rank-info">
          <strong>${escapeHtml(r.nombre)}</strong>
          <span class="rank-sub">${escapeHtml(r.codigo)} · ${r.cantidad_ventas || 0} ventas</span>
        </div>
        <span class="rank-value">${formatPrice(r.comision_total || 0)}</span>
      </div>
    `).join('');
  } else {
    topRefsEl.innerHTML = '<div class="chart-empty">Sin referidos todavía</div>';
  }

  // Top productos
  const topProds = calcTopProductos(data.estadisticas, 5);
  const topProdsEl = document.getElementById('top-productos');
  if (topProds.length) {
    topProdsEl.innerHTML = topProds.map((p, i) => `
      <div class="rank-row">
        <span class="rank-pos">${i + 1}</span>
        <div class="rank-info">
          <strong>${escapeHtml(p.nombre)}</strong>
          <span class="rank-sub">${p.cantidad_vendida || 0} vendidos</span>
        </div>
        <span class="rank-value">${formatPrice(p.total_vendido || 0)}</span>
      </div>
    `).join('');
  } else {
    topProdsEl.innerHTML = '<div class="chart-empty">Sin ventas todavía</div>';
  }
}
