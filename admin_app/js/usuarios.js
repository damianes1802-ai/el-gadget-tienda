/* ============================================================
   PANEL EL GADGET — Usuarios registrados
   ============================================================ */

let todosLosUsuarios = [];

async function loadUsuarios() {
  const tbody = document.getElementById('usuarios-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="6">Cargando…</td></tr>';

  try {
    todosLosUsuarios = await apiCall('get_usuarios');
    renderUsuariosTabla(filtrarUsuariosLocal());
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="6">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function filtrarUsuariosLocal() {
  const q = document.getElementById('usuarios-buscar').value.trim().toLowerCase();
  if (!q) return todosLosUsuarios;
  return todosLosUsuarios.filter(u =>
    (u.nombre || '').toLowerCase().includes(q) ||
    (u.email || '').toLowerCase().includes(q)
  );
}

function renderUsuariosTabla(usuarios) {
  const tbody = document.getElementById('usuarios-tbody');
  if (!usuarios.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = usuarios.map(u => `
    <tr>
      <td>${escapeHtml(u.nombre || '-')}</td>
      <td class="cell-muted">${escapeHtml(u.email || '-')}</td>
      <td class="cell-muted">${escapeHtml(u.telefono || '-')}</td>
      <td class="cell-strong">${escapeHtml(u.codigo_descuento || '-')}</td>
      <td>${u.descuento_usado ? '<span class="badge badge-gray">Usado</span>' : '<span class="badge badge-green">Disponible</span>'}</td>
      <td class="cell-muted">${formatDate(u.creado_at)}</td>
    </tr>
  `).join('');
}

document.getElementById('usuarios-buscar').addEventListener('input', () => renderUsuariosTabla(filtrarUsuariosLocal()));

document.getElementById('btn-descargar-usuarios').addEventListener('click', async () => {
  const btn = document.getElementById('btn-descargar-usuarios');
  btn.disabled = true;
  try {
    const resultado = await apiCall('descargar_usuarios_csv');
    if (resultado && resultado.cancelado) {
      // El usuario cerró el diálogo de guardado sin elegir archivo
    } else {
      toast('CSV descargado correctamente', 'success');
    }
  } catch (e) {
    toast('Error al descargar el CSV: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
  }
});
