/* ============================================================
   PANEL EL GADGET — Historial de actualizaciones diarias
   ============================================================ */

let todoElHistorial = [];

async function loadHistorial() {
  const tbody = document.getElementById('historial-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7">Cargando…</td></tr>';

  try {
    todoElHistorial = await apiCall('get_historial');
    renderHistorialTabla(todoElHistorial);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderHistorialTabla(historial) {
  const tbody = document.getElementById('historial-tbody');
  if (!historial.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">Todavía no hay actualizaciones registradas</td></tr>';
    return;
  }

  tbody.innerHTML = historial.map(h => `
    <tr>
      <td class="cell-muted">${formatDate(h.fecha)}</td>
      <td class="cell-strong">${h.total_productos ?? '-'}</td>
      <td>${h.nuevos_count ? `<span class="badge badge-green">${h.nuevos_count}</span>` : '0'}</td>
      <td>${h.agotados_count ? `<span class="badge badge-red">${h.agotados_count}</span>` : '0'}</td>
      <td>${h.reingresados_count ? `<span class="badge badge-blue">${h.reingresados_count}</span>` : '0'}</td>
      <td>${h.exitoso ? '<span class="badge badge-green">OK</span>' : '<span class="badge badge-red">Error</span>'}</td>
      <td><button class="btn btn-outline btn-sm" onclick="verDetalleHistorial(${h.id})">Ver detalle</button></td>
    </tr>
  `).join('');
}

function renderListaHistorial(items, vacio) {
  if (!items || !items.length) return `<p class="cell-muted">${vacio}</p>`;
  return `<ul class="historial-lista">${items.map(it => {
    const sku = typeof it === 'string' ? it : (it.sku || '');
    const nombre = typeof it === 'string' ? '' : (it.nombre || '');
    return `<li><span class="cell-strong">${escapeHtml(sku)}</span>${nombre ? ` — ${escapeHtml(nombre)}` : ''}</li>`;
  }).join('')}</ul>`;
}

function verDetalleHistorial(id) {
  const h = todoElHistorial.find(x => x.id === id);
  if (!h) return;

  document.getElementById('modal-historial-titulo').textContent = `Actualización del ${formatDate(h.fecha)}`;

  document.getElementById('modal-historial-body').innerHTML = `
    <div class="detalle-grid">
      <div class="detalle-campo"><strong>Total de productos</strong>${h.total_productos ?? '-'}</div>
      <div class="detalle-campo"><strong>Estado</strong>${h.exitoso ? '<span class="badge badge-green">OK</span>' : '<span class="badge badge-red">Error</span>'}</div>
    </div>
    <div class="detalle-campo span-2" style="margin-bottom:18px">
      <strong>Productos nuevos (${h.nuevos_count ?? 0})</strong>
      ${renderListaHistorial(h.nuevos, 'Sin productos nuevos en esta actualización')}
    </div>
    <div class="detalle-campo span-2" style="margin-bottom:18px">
      <strong>Productos agotados (${h.agotados_count ?? 0})</strong>
      ${renderListaHistorial(h.agotados, 'Sin productos agotados en esta actualización')}
    </div>
    <div class="detalle-campo span-2">
      <strong>Productos reingresados (${h.reingresados_count ?? 0})</strong>
      ${renderListaHistorial(h.reingresados, 'Sin productos reingresados en esta actualización')}
    </div>
  `;

  openModal('modal-historial-overlay');
}
