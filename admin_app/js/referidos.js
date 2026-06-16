/* ============================================================
   PANEL EL GADGET — Referidos
   ============================================================ */

let todosLosReferidos = [];
let _desactivarRefId = null;
let _eliminarRefId = null;
let _detalleReferidoData = null;

async function loadReferidos() {
  const tbody = document.getElementById('referidos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="10">Cargando…</td></tr>';

  try {
    todosLosReferidos = await apiCall('get_referidos');
    renderReferidosTabla(todosLosReferidos);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="10">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderReferidosTabla(referidos) {
  const tbody = document.getElementById('referidos-tbody');
  if (!referidos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="10">No hay usuarios registrados como referidos</td></tr>';
    return;
  }

  tbody.innerHTML = referidos.map(r => {
    const activo = r.activo
      ? '<span class="badge badge-green">Activo</span>'
      : '<span class="badge badge-red">Inactivo</span>';
    const fecha = r.creado_at ? formatDate(r.creado_at) : '-';
    const acciones = r.activo
      ? `<button class="btn btn-sm btn-outline" onclick="verDetalleReferido(${r.id})">Ver detalle</button>
         <button class="btn btn-sm btn-danger" onclick="confirmarDesactivarRef(${r.id}, '${escapeHtml(r.nombre)}')">Desactivar</button>`
      : `<button class="btn btn-sm btn-outline" onclick="verDetalleReferido(${r.id})">Ver detalle</button>
         <button class="btn btn-sm btn-danger" onclick="confirmarEliminarRef(${r.id}, '${escapeHtml(r.nombre)}')">Eliminar</button>`;

    return `<tr>
      <td>${escapeHtml(r.nombre)}</td>
      <td>${escapeHtml(r.email)}</td>
      <td>${escapeHtml(r.dni)}</td>
      <td><code style="background:#F5F3EE;padding:2px 8px;border-radius:6px;font-size:12px;font-weight:700;letter-spacing:1px">${escapeHtml(r.codigo)}</code></td>
      <td>${fecha}</td>
      <td>${activo}</td>
      <td>${r.cantidad_ventas || 0}</td>
      <td>${formatPrice(r.comision_total || 0)}</td>
      <td>${formatPrice(r.comision_pendiente || 0)}</td>
      <td style="white-space:nowrap">${acciones}</td>
    </tr>`;
  }).join('');
}

async function verDetalleReferido(id) {
  const ref = todosLosReferidos.find(r => r.id === id);
  if (!ref) return;

  document.getElementById('modal-referido-nombre').textContent = ref.nombre;
  _detalleReferidoData = ref;

  const periodos = ref.periodos || [];
  const periodosTbody = document.getElementById('modal-referido-periodos');

  if (!periodos.length) {
    periodosTbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sin comisiones registradas</td></tr>';
  } else {
    periodosTbody.innerHTML = periodos.map(p => {
      const [anio, mes] = (p.periodo || '').split('-');
      const nombreMes = anio && mes
        ? new Date(+anio, +mes - 1).toLocaleDateString('es-AR', { month: 'long', year: 'numeric' })
        : p.periodo;

      const estadoBadge = p.pagado
        ? '<span class="badge badge-green">Pagado</span>'
        : '<span class="badge badge-yellow">Pendiente</span>';

      const accionBtn = (!p.pagado && ref.activo)
        ? `<button class="btn btn-sm btn-accent" onclick="marcarPagadoRef(${id}, '${escapeHtml(p.periodo)}', this)">Marcar pagado</button>`
        : '-';

      return `<tr>
        <td style="text-transform:capitalize">${nombreMes}</td>
        <td>${p.cantidad_ventas || 0}</td>
        <td>${formatPrice(p.monto_total || 0)}</td>
        <td>${formatPrice(p.comision_total || 0)}</td>
        <td>${estadoBadge}</td>
        <td>${accionBtn}</td>
      </tr>`;
    }).join('');
  }

  openModal('modal-referido-overlay');
}

async function marcarPagadoRef(refId, periodo, btn) {
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Guardando…';

  try {
    await apiCall('marcar_referido_pagado', refId, periodo);
    toast(`Período ${periodo} marcado como pagado`);

    const ref = todosLosReferidos.find(r => r.id === refId);
    if (ref && ref.periodos) {
      const p = ref.periodos.find(x => x.periodo === periodo);
      if (p) p.pagado = 1;
    }

    btn.closest('tr').querySelector('.badge').className = 'badge badge-green';
    btn.closest('tr').querySelector('.badge').textContent = 'Pagado';
    btn.closest('td').textContent = '-';

    await loadReferidos();
  } catch (e) {
    toast(e.message || 'Error al marcar como pagado', 'error');
    btn.disabled = false;
    btn.textContent = original;
  }
}

function confirmarDesactivarRef(id, nombre) {
  document.getElementById('modal-desactivar-ref-nombre').textContent = nombre;
  _desactivarRefId = id;
  openModal('modal-desactivar-ref-overlay');
}

function confirmarEliminarRef(id, nombre) {
  document.getElementById('modal-eliminar-ref-nombre').textContent = nombre;
  _eliminarRefId = id;
  openModal('modal-eliminar-ref-overlay');
}

document.addEventListener('DOMContentLoaded', () => {
  const btnDesactivar = document.getElementById('btn-confirmar-desactivar-ref');
  if (btnDesactivar) {
    btnDesactivar.addEventListener('click', async () => {
      const id = _desactivarRefId;
      _desactivarRefId = null;
      closeModal('modal-desactivar-ref-overlay');

      try {
        await apiCall('desactivar_referido', id);
        toast('Referido desactivado correctamente');
        await loadReferidos();
      } catch (e) {
        toast(e.message || 'Error al desactivar referido', 'error');
      }
    });
  }

  const btnEliminar = document.getElementById('btn-confirmar-eliminar-ref');
  if (btnEliminar) {
    btnEliminar.addEventListener('click', async () => {
      const id = _eliminarRefId;
      _eliminarRefId = null;
      closeModal('modal-eliminar-ref-overlay');

      try {
        await apiCall('eliminar_referido', id);
        toast('Referido eliminado correctamente');
        await loadReferidos();
      } catch (e) {
        toast(e.message || 'Error al eliminar referido', 'error');
      }
    });
  }
});
