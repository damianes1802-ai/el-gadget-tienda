/* ============================================================
   MARKETING EL GADGET — Campañas (placeholder ads futuro)
   ============================================================ */

async function loadCampanias() {
  const data = _cache;
  const descuentos = data.descuentos || [];
  const activos = descuentos.filter(d => d.activo);

  renderTrendCard(document.getElementById('camp-stat-activas'), { label: 'Campañas activas', value: formatNumber(activos.length) });

  const ordenes = enrichOrdenes(data.ordenes, data.referidos, data.descuentos);
  const promoRevenue = calcRevenue(ordenes.filter(o => o._source === 'promo'));
  renderTrendCard(document.getElementById('camp-stat-revenue'), { label: 'Revenue via promos', value: formatPrice(promoRevenue) });

  const tbody = document.getElementById('campanias-tbody');
  if (activos.length) {
    tbody.innerHTML = activos.map(d => {
      const ordsCamp = ordenes.filter(o => (o.descuento_codigo || '').toUpperCase() === (d.codigo || '').toUpperCase());
      const rev = calcRevenue(ordsCamp);
      return `<tr>
        <td>${escapeHtml(d.nombre)}</td>
        <td><code>${escapeHtml(d.codigo)}</code></td>
        <td class="text-center">${d.tipo === 'porcentaje' ? d.valor + '%' : formatPrice(d.valor)}</td>
        <td class="text-center">${d.usos_actuales || 0}${d.uso_maximo ? '/' + d.uso_maximo : ''}</td>
        <td class="text-right">${formatPrice(rev)}</td>
        <td class="text-center"><span class="badge badge-green">Activa</span></td>
      </tr>`;
    }).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Sin campañas activas</td></tr>';
  }
}
