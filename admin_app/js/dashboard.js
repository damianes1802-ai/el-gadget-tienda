/* ============================================================
   PANEL EL GADGET — Dashboard
   ============================================================ */

async function loadDashboard() {
  const statsEl = document.getElementById('dashboard-stats');
  const chartEl = document.getElementById('dashboard-ventas-chart');
  const topEl = document.getElementById('dashboard-top-productos');

  statsEl.innerHTML = '<div class="stat-card"><h3>Cargando…</h3></div>';

  try {
    const data = await apiCall('get_estadisticas');
    renderStats(statsEl, data);
    renderVentasChart(chartEl, data.ventas_por_mes || []);
    renderTopProductos(topEl, data.top_productos || []);
    setStatus(true, 'Conectado');
  } catch (e) {
    statsEl.innerHTML = `<div class="stat-card"><h3>Error</h3><div class="numero" style="font-size:14px;color:var(--red)">${escapeHtml(e.message)}</div></div>`;
    setStatus(false, 'Sin conexión');
  }
}

function renderStats(el, data) {
  const productos = data.productos || {};
  const ordenes = data.ordenes || {};

  el.innerHTML = `
    <div class="stat-card">
      <h3>Ventas aprobadas</h3>
      <div class="numero">${formatPrice(data.ventas_totales)}</div>
    </div>
    <div class="stat-card">
      <h3>Pedidos</h3>
      <div class="numero">${ordenes.total ?? 0}</div>
      <div class="sub">${ordenes.pendientes ?? 0} pendientes de procesar</div>
    </div>
    <div class="stat-card">
      <h3>Productos</h3>
      <div class="numero">${productos.en_stock ?? 0}</div>
      <div class="sub">${productos.agotados ?? 0} agotados de ${productos.total ?? 0} totales</div>
    </div>
    <div class="stat-card">
      <h3>Facturación AFIP</h3>
      <div class="numero">${data.facturas_emitidas ?? 0}</div>
      <div class="sub">${data.pedidos_sin_facturar ?? 0} pedidos aprobados sin facturar</div>
    </div>
  `;
}

const MESES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

function renderVentasChart(el, ventasPorMes) {
  if (!ventasPorMes.length) {
    el.innerHTML = '<p style="font-size:13px;color:var(--gray-600)">Todavía no hay ventas aprobadas.</p>';
    return;
  }

  const max = Math.max(...ventasPorMes.map(v => v.total || 0), 1);

  el.innerHTML = ventasPorMes.map(v => {
    const [anio, mes] = (v.mes || '').split('-');
    const label = MESES_CORTOS[parseInt(mes, 10) - 1] || v.mes;
    const alturaPct = Math.max(((v.total || 0) / max) * 100, 2);
    return `
      <div class="bar-col">
        <div class="bar-value">${formatPrice(v.total)}</div>
        <div class="bar" style="height:${alturaPct}%"></div>
        <div class="bar-label">${label} '${(anio || '').slice(-2)}</div>
      </div>
    `;
  }).join('');
}

function renderTopProductos(el, topProductos) {
  if (!topProductos.length) {
    el.innerHTML = '<p style="font-size:13px;color:var(--gray-600)">Todavía no hay ventas registradas.</p>';
    return;
  }

  el.innerHTML = topProductos.map((p, i) => `
    <div class="top-row">
      <div class="top-rank">${i + 1}</div>
      <div class="top-info">
        <div class="top-name">${escapeHtml(p.nombre || p.sku)}</div>
        <div class="top-meta">SKU ${escapeHtml(p.sku)} · ${p.cantidad_vendida} unidades vendidas</div>
      </div>
      <div class="top-total">${formatPrice(p.total_vendido)}</div>
    </div>
  `).join('');
}
