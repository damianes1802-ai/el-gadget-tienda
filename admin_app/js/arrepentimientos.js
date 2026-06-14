/* ============================================================
   PANEL EL GADGET — Solicitudes de arrepentimiento
   ============================================================ */

async function loadArrepentimientos() {
  const tbody = document.getElementById('arrepentimientos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7">Cargando…</td></tr>';

  try {
    const solicitudes = await apiCall('get_arrepentimientos');
    renderArrepentimientosTabla(solicitudes);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderArrepentimientosTabla(solicitudes) {
  const tbody = document.getElementById('arrepentimientos-tbody');
  if (!solicitudes.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">Sin solicitudes</td></tr>';
    return;
  }

  tbody.innerHTML = solicitudes.map(s => `
    <tr>
      <td class="cell-strong">#${s.id}</td>
      <td class="cell-muted">${formatDate(s.fecha)}</td>
      <td>#${s.orden_id}</td>
      <td>
        <div>${escapeHtml(s.cliente_nombre || '-')}</div>
        <div class="cell-muted">${escapeHtml(s.email || '')}</div>
      </td>
      <td style="max-width:240px">${s.motivo ? escapeHtml(s.motivo) : '<span class="cell-muted">(sin motivo)</span>'}</td>
      <td>${badgeArrepentimiento(s.estado)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-outline btn-sm" onclick="cambiarEstadoArrepentimiento(${s.id}, 'aprobado')">Aprobar</button>
          <button class="btn btn-danger btn-sm" onclick="cambiarEstadoArrepentimiento(${s.id}, 'rechazado')">Rechazar</button>
        </div>
      </td>
    </tr>
  `).join('');
}

async function cambiarEstadoArrepentimiento(id, estado) {
  try {
    await apiCall('actualizar_estado_arrepentimiento', id, estado);
    toast('Solicitud actualizada', 'success');
    loadArrepentimientos();
  } catch (e) {
    toast('Error al actualizar la solicitud: ' + e.message, 'error');
  }
}
