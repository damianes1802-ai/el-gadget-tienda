/* ============================================================
   MARKETING EL GADGET — Productos analytics
   ============================================================ */

async function loadProductos() {
  const data = _cache;
  if (!data.estadisticas) return;

  const productos = (data.productos || {}).productos || [];
  const enStock = productos.filter(p => p.stock > 0).length;
  const agotados = productos.length - enStock;
  const topProds = calcTopProductos(data.estadisticas, 10);

  renderTrendCard(document.getElementById('prod-stat-stock'), { label: 'En stock', value: formatNumber(enStock), sub: `${agotados} agotados` });
  renderTrendCard(document.getElementById('prod-stat-top'), { label: 'Más vendido', value: topProds.length ? escapeHtml(topProds[0].nombre.substring(0, 30)) : '-' });
  renderTrendCard(document.getElementById('prod-stat-revenue'), { label: 'Revenue top 10', value: formatPrice(topProds.reduce((s, p) => s + (p.total_vendido || 0), 0)) });
  renderTrendCard(document.getElementById('prod-stat-units'), { label: 'Unidades vendidas (top 10)', value: formatNumber(topProds.reduce((s, p) => s + (p.cantidad_vendida || 0), 0)) });

  renderHBarChart(document.getElementById('chart-top-productos'), topProds.map(p => ({
    label: p.nombre.length > 40 ? p.nombre.substring(0, 40) + '…' : p.nombre,
    value: p.total_vendido || 0,
  })));

  const tbody = document.getElementById('productos-tbody');
  if (topProds.length) {
    tbody.innerHTML = topProds.map((p, i) => `<tr>
      <td class="text-center">${i + 1}</td>
      <td>${escapeHtml(p.nombre)}</td>
      <td><code>${escapeHtml(p.sku)}</code></td>
      <td class="text-center">${p.cantidad_vendida || 0}</td>
      <td class="text-right">${formatPrice(p.total_vendido || 0)}</td>
    </tr>`).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="5" class="table-empty">Sin ventas todavía</td></tr>';
  }
}
