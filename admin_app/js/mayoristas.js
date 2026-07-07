/* ============================================================
   PANEL EL GADGET — Solicitudes de mayorista
   ============================================================ */

async function loadMayoristas() {
  const tbody = document.getElementById('mayoristas-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8">Cargando…</td></tr>';
  try {
    const solicitudes = await apiCall('get_solicitudes_mayorista');
    renderMayoristasTabla(solicitudes);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderMayoristasTabla(solicitudes) {
  const tbody = document.getElementById('mayoristas-tbody');
  if (!solicitudes || !solicitudes.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="8">Sin solicitudes</td></tr>';
    return;
  }
  tbody.innerHTML = solicitudes.map(s => `
    <tr>
      <td class="cell-strong">#${s.id}</td>
      <td class="cell-muted">${formatDate(s.fecha)}</td>
      <td>${escapeHtml(s.nombre || '-')}</td>
      <td>
        <div class="cell-muted">${escapeHtml(s.email || '')}</div>
        <div class="cell-muted">${escapeHtml(s.telefono || '')}</div>
      </td>
      <td>${s.tipo_negocio ? escapeHtml(s.tipo_negocio) : '<span class="cell-muted">-</span>'}</td>
      <td style="max-width:220px">${s.mensaje ? escapeHtml(s.mensaje) : '<span class="cell-muted">-</span>'}</td>
      <td>${badgeMayorista(s.estado)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-outline btn-sm" onclick="cambiarEstadoMayorista(${s.id}, 'aprobado')">Aprobar</button>
          <button class="btn btn-danger btn-sm" onclick="cambiarEstadoMayorista(${s.id}, 'rechazado')">Rechazar</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function badgeMayorista(estado) {
  const map = {
    pendiente: '<span class="badge badge-gray">Pendiente</span>',
    aprobado: '<span class="badge badge-green">Aprobado</span>',
    rechazado: '<span class="badge badge-red">Rechazado</span>',
  };
  return map[estado] || `<span class="badge badge-gray">${escapeHtml(estado || '-')}</span>`;
}

async function cambiarEstadoMayorista(id, estado) {
  try {
    await apiCall('cambiar_estado_solicitud_mayorista', id, estado);
    toast(`Solicitud ${estado}`, 'success');
    loadMayoristas();
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
}
