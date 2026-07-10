/* ============================================================
   PANEL EL GADGET — Moderación de reseñas de productos
   ============================================================ */

async function loadResenas() {
  const tbody = document.getElementById('resenas-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="9">Cargando…</td></tr>';
  try {
    const resenas = await apiCall('get_resenas');
    renderResenasTabla(resenas);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="9">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderResenasTabla(resenas) {
  const tbody = document.getElementById('resenas-tbody');
  if (!resenas || !resenas.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="9">Todavía no hay reseñas. Llegan solas: el email post-entrega invita a cada comprador a dejar la suya.</td></tr>';
    return;
  }
  tbody.innerHTML = resenas.map(r => `
    <tr>
      <td class="cell-strong">#${r.id}</td>
      <td class="cell-muted">${formatDate(r.fecha)}</td>
      <td class="cell-muted">${escapeHtml(r.producto_sku || '-')}</td>
      <td class="cell-muted">#${r.orden_id ?? '-'}</td>
      <td style="color:var(--accent-deep,#c79a00);letter-spacing:1px;white-space:nowrap">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</td>
      <td style="max-width:260px">${r.comentario ? escapeHtml(r.comentario) : '<span class="cell-muted">-</span>'}</td>
      <td><input type="text" id="resena-nombre-${r.id}" value="${escapeHtml(r.nombre || '')}" placeholder="Ej: María G." maxlength="40" style="width:110px"></td>
      <td>${badgeResena(r.estado)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-outline btn-sm" onclick="moderarResena(${r.id}, 'aprobada')">Aprobar</button>
          <button class="btn btn-danger btn-sm" onclick="moderarResena(${r.id}, 'rechazada')">Rechazar</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function badgeResena(estado) {
  const map = {
    pendiente: '<span class="badge badge-gray">Pendiente</span>',
    aprobada: '<span class="badge badge-green">Aprobada</span>',
    rechazada: '<span class="badge badge-red">Rechazada</span>',
  };
  return map[estado] || `<span class="badge badge-gray">${escapeHtml(estado || '-')}</span>`;
}

async function moderarResena(id, estado) {
  const input = document.getElementById(`resena-nombre-${id}`);
  const nombre = input ? input.value.trim() : null;
  try {
    await apiCall('moderar_resena', id, estado, nombre);
    toast(estado === 'aprobada' ? 'Reseña aprobada: ya se ve en la ficha del producto' : `Reseña ${estado}`, 'success');
    loadResenas();
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
}
