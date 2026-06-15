/* ============================================================
   PANEL EL GADGET — Clientes
   ============================================================ */

let todosLosClientes = [];

async function loadClientes() {
  const tbody = document.getElementById('clientes-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7">Cargando…</td></tr>';

  try {
    todosLosClientes = await apiCall('get_clientes');
    renderClientesTabla(filtrarClientesLocal());
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
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
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = clientes.map(c => {
    const ubicacion = [c.ciudad, c.provincia].filter(Boolean).join(', ') || '-';
    const nombreCompleto = `${c.nombre || ''} ${c.apellido || ''}`.trim() || 'este cliente';
    const tieneOrdenes = (c.cantidad_ordenes ?? 0) > 0;
    const btnEliminar = tieneOrdenes
      ? `<button class="btn btn-danger btn-sm" disabled title="No se puede eliminar: tiene pedidos asociados">Eliminar</button>`
      : `<button class="btn btn-danger btn-sm" onclick="pedirEliminarCliente(${c.id}, '${escapeHtml(nombreCompleto.replace(/'/g, "\\'"))}')">Eliminar</button>`;
    return `
      <tr>
        <td>${escapeHtml(c.nombre || '-')} ${escapeHtml(c.apellido || '')}</td>
        <td class="cell-muted">${escapeHtml(c.email || '-')}</td>
        <td class="cell-muted">${escapeHtml(c.telefono || '-')}</td>
        <td class="cell-muted">${escapeHtml(ubicacion)}</td>
        <td>${c.cantidad_ordenes ?? 0}</td>
        <td class="cell-strong">${formatPriceDecimal(c.total_comprado)}</td>
        <td>${btnEliminar}</td>
      </tr>
    `;
  }).join('');
}

function pedirEliminarCliente(id, nombre) {
  confirmarEliminar(
    `Se eliminará el cliente "${nombre}". Esta acción no se puede deshacer.`,
    async () => {
      try {
        await apiCall('eliminar_cliente', id);
        toast(`Cliente eliminado`, 'success');
        loadClientes();
      } catch (e) {
        toast('Error al eliminar el cliente: ' + e.message, 'error');
      }
    }
  );
}

document.getElementById('clientes-buscar').addEventListener('input', () => renderClientesTabla(filtrarClientesLocal()));
