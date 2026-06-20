/* ============================================================
   MARKETING EL GADGET — Ventas analytics
   ============================================================ */

let _ventasPeriod = 'all';

async function loadVentas() {
  const data = _cache;
  if (!data.ordenes) return;
  renderVentas();
}

function renderVentas() {
  const data = _cache;
  const ordenes = enrichOrdenes(data.ordenes, data.referidos, data.descuentos);
  const filtered = filterPeriod(ordenes, _ventasPeriod);

  const revenue = calcRevenue(filtered);
  const aov = calcAOV(filtered);
  const repeatRate = calcRepeatRate(data.clientes);

  renderTrendCard(document.getElementById('ventas-stat-revenue'), { label: 'Revenue', value: formatPrice(revenue) });
  renderTrendCard(document.getElementById('ventas-stat-aov'), { label: 'Ticket promedio', value: formatPrice(aov) });
  renderTrendCard(document.getElementById('ventas-stat-orders'), { label: 'Pedidos', value: formatNumber(filtered.length) });
  renderTrendCard(document.getElementById('ventas-stat-repeat'), { label: 'Clientes recurrentes', value: formatPercent(repeatRate) });

  // Revenue por mes
  const byMonth = calcRevenueByMonth(filtered, 12);
  renderBarChart(document.getElementById('chart-ventas-monthly'), byMonth, { stacked: true });

  // Donut por fuente
  const bySource = calcRevenueBySource(filtered);
  renderDonut(document.getElementById('chart-ventas-source'), [
    { label: 'Referido', value: bySource.referido, color: CHART_COLORS.referido },
    { label: 'Orgánico', value: bySource.organico, color: CHART_COLORS.organico },
    { label: 'Promo', value: bySource.promo, color: CHART_COLORS.promo },
    { label: 'Mayorista', value: bySource.mayorista, color: CHART_COLORS.mayorista },
  ]);

  // Por zona
  const byZona = calcRevenueByZona(filtered);
  const zonaItems = Object.entries(byZona).map(([k, v]) => ({ label: k, value: v })).sort((a, b) => b.value - a.value);
  renderHBarChart(document.getElementById('chart-ventas-zona'), zonaItems, { maxItems: 8 });

  // Por día de semana
  const byDay = calcRevenueByDayOfWeek(filtered);
  renderBarChart(document.getElementById('chart-ventas-day'), byDay.map(d => ({ mes: d.day, total: d.total })));
}

document.querySelectorAll('#ventas-period-bar button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#ventas-period-bar button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    _ventasPeriod = btn.dataset.period;
    renderVentas();
  });
});
