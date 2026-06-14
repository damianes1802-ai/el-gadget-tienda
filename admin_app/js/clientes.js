/* ============================================================
   PANEL EL GADGET — Clientes
   ============================================================ */

let todosLosClientes = [];

async function loadClientes() {
  const tbody = document.getElementById('clientes-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="6">Cargando…</td></tr>';

  try {
    todosLosClientes = await apiCall('get_clientes');
    renderClientesTabla(filtrarClientesLocal());
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="6">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function filtrarClientesLocal() {
  const q = document.getElementById('clientes-buscar').value.trim().toLowerCase();
  if (!q) return todosLosClientes;
  return todosLosClientes.filter(c =>
    (c.nombre || '').toLowerCase().includes(q) ||
    (c.apellido || '').toLowerCase().includes(q) ||
    (c.email || '').toLowerCase().includes(q)
  );
}

function renderClientesTabla(clientes) {
  const tbody = document.getElementById('clientes-tbody');
  if (!clientes.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = clientes.map(c => {
    const ubicacion = [c.ciudad, c.provincia].filter(Boolean).join(', ') || '-';
    return `
      <tr>
        <td>${escapeHtml(c.nombre || '-')} ${escapeHtml(c.apellido || '')}</td>
        <td class="cell-muted">${escapeHtml(c.email || '-')}</td>
        <td class="cell-muted">${escapeHtml(c.telefono || '-')}</td>
        <td class="cell-muted">${escapeHtml(ubicacion)}</td>
        <td>${c.cantidad_ordenes ?? 0}</td>
        <td class="cell-strong">${formatPriceDecimal(c.total_comprado)}</td>
      </tr>
    `;
  }).join('');
}

document.getElementById('clientes-buscar').addEventListener('input', () => renderClientesTabla(filtrarClientesLocal()));
