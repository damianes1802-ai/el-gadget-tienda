/* ============================================================
   PANEL EL GADGET — Descuentos y campañas promocionales
   ============================================================ */

let todosLosDescuentos = [];

async function loadDescuentos() {
  const tbody = document.getElementById('descuentos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8">Cargando…</td></tr>';

  try {
    todosLosDescuentos = await apiCall('get_descuentos');
    renderDescuentosTabla(todosLosDescuentos);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function formatFechaSimple(f) {
  if (!f) return null;
  const partes = f.split('-');
  if (partes.length !== 3) return f;
  return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

function formatMesDia(f) {
  if (!f) return null;
  const partes = f.split('-');
  if (partes.length !== 3) return f;
  return `${partes[2]}/${partes[1]}`;
}

function describirVigencia(d) {
  if (d.recurrente_anual) {
    const desde = formatMesDia(d.fecha_inicio);
    const hasta = formatMesDia(d.fecha_fin);
    const rango = (desde && hasta) ? `${desde} - ${hasta}` : (desde ? `Desde ${desde}` : (hasta ? `Hasta ${hasta}` : 'Todo el año'));
    return `🔁 ${rango} <span class="cell-muted" style="font-size:11px">(todos los años)</span>`;
  }
  const desde = formatFechaSimple(d.fecha_inicio);
  const hasta = formatFechaSimple(d.fecha_fin);
  if (desde && hasta) return `${desde} - ${hasta}`;
  if (desde) return `Desde ${desde}`;
  if (hasta) return `Hasta ${hasta}`;
  return 'Sin límite';
}

function describirAlcance(d) {
  if (d.alcance === 'categoria') return `Categoría: ${escapeHtml(d.categoria || '-')}`;
  if (d.alcance === 'skus') return `SKUs (${(d.skus || []).length})`;
  return 'Todos los productos';
}

function renderDescuentosTabla(descuentos) {
  const tbody = document.getElementById('descuentos-tbody');
  if (!descuentos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="8">Sin descuentos creados</td></tr>';
    return;
  }

  tbody.innerHTML = descuentos.map(d => {
    const valor = d.tipo === 'fijo' ? formatPrice(d.valor) : `${d.valor}%`;
    return `
      <tr>
        <td>${escapeHtml(d.nombre)}</td>
        <td class="cell-strong">${escapeHtml(d.codigo || '-')}</td>
        <td>${valor}</td>
        <td class="cell-muted">${describirAlcance(d)}</td>
        <td class="cell-muted">${describirVigencia(d)}</td>
        <td>${d.activo ? '<span class="badge badge-green">Activo</span>' : '<span class="badge badge-gray">Inactivo</span>'}</td>
        <td>${d.mostrar_banner ? '<span class="badge badge-green">Sí</span>' : '<span class="badge badge-gray">No</span>'}</td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="abrirEditarDescuento(${d.id})">Editar</button>
          <button class="btn btn-danger btn-sm" onclick="pedirEliminarDescuento(${d.id}, '${escapeHtml(d.nombre).replace(/'/g, "\\'")}')">Eliminar</button>
        </td>
      </tr>
    `;
  }).join('');
}

// ── Alta / edición ──
function toggleAlcanceFields() {
  const alcance = document.getElementById('modal-descuento-alcance').value;
  document.getElementById('modal-descuento-categoria-wrap').style.display = alcance === 'categoria' ? '' : 'none';
  document.getElementById('modal-descuento-skus-wrap').style.display = alcance === 'skus' ? '' : 'none';
}

function toggleBannerFields() {
  const activo = document.getElementById('modal-descuento-banner').checked;
  document.getElementById('modal-descuento-banner-wrap').style.display = activo ? '' : 'none';
}

document.getElementById('modal-descuento-alcance').addEventListener('change', toggleAlcanceFields);
document.getElementById('modal-descuento-banner').addEventListener('change', toggleBannerFields);

function resetModalDescuento() {
  document.getElementById('modal-descuento-titulo').textContent = 'Nuevo descuento';
  document.getElementById('btn-guardar-descuento').dataset.id = '';
  document.getElementById('modal-descuento-nombre').value = '';
  document.getElementById('modal-descuento-tipo').value = 'porcentaje';
  document.getElementById('modal-descuento-valor').value = '';
  document.getElementById('modal-descuento-alcance').value = 'todos';
  document.getElementById('modal-descuento-categoria').value = '';
  document.getElementById('modal-descuento-skus').value = '';
  document.getElementById('modal-descuento-codigo').value = '';
  document.getElementById('modal-descuento-fecha-inicio').value = '';
  document.getElementById('modal-descuento-fecha-fin').value = '';
  document.getElementById('modal-descuento-uso-maximo').value = '';
  document.getElementById('modal-descuento-activo').checked = true;
  document.getElementById('modal-descuento-banner').checked = false;
  document.getElementById('modal-descuento-banner-titulo').value = '';
  document.getElementById('modal-descuento-banner-texto').value = '';
  document.getElementById('modal-descuento-recurrente').checked = false;
  toggleAlcanceFields();
  toggleBannerFields();
}

document.getElementById('btn-nuevo-descuento').addEventListener('click', () => {
  resetModalDescuento();
  openModal('modal-descuento-overlay');
});

function abrirEditarDescuento(id) {
  const d = todosLosDescuentos.find(x => x.id === id);
  if (!d) return;

  resetModalDescuento();
  document.getElementById('modal-descuento-titulo').textContent = 'Editar descuento';
  document.getElementById('btn-guardar-descuento').dataset.id = d.id;
  document.getElementById('modal-descuento-nombre').value = d.nombre || '';
  document.getElementById('modal-descuento-tipo').value = d.tipo || 'porcentaje';
  document.getElementById('modal-descuento-valor').value = d.valor ?? '';
  document.getElementById('modal-descuento-alcance').value = d.alcance || 'todos';
  document.getElementById('modal-descuento-categoria').value = d.categoria || '';
  document.getElementById('modal-descuento-skus').value = (d.skus || []).join(', ');
  document.getElementById('modal-descuento-codigo').value = d.codigo || '';
  document.getElementById('modal-descuento-fecha-inicio').value = d.fecha_inicio || '';
  document.getElementById('modal-descuento-fecha-fin').value = d.fecha_fin || '';
  document.getElementById('modal-descuento-uso-maximo').value = d.uso_maximo ?? '';
  document.getElementById('modal-descuento-activo').checked = !!d.activo;
  document.getElementById('modal-descuento-banner').checked = !!d.mostrar_banner;
  document.getElementById('modal-descuento-banner-titulo').value = d.banner_titulo || '';
  document.getElementById('modal-descuento-banner-texto').value = d.banner_texto || '';
  document.getElementById('modal-descuento-recurrente').checked = !!d.recurrente_anual;
  toggleAlcanceFields();
  toggleBannerFields();

  openModal('modal-descuento-overlay');
}

document.getElementById('btn-guardar-descuento').addEventListener('click', async (e) => {
  const nombre = document.getElementById('modal-descuento-nombre').value.trim();
  const valor = parseFloat(document.getElementById('modal-descuento-valor').value);

  if (!nombre) {
    toast('Ingresá un nombre para el descuento', 'error');
    return;
  }
  if (isNaN(valor) || valor <= 0) {
    toast('Ingresá un valor de descuento válido', 'error');
    return;
  }

  const skus = document.getElementById('modal-descuento-skus').value
    .split(',').map(s => s.trim()).filter(Boolean);

  const datos = {
    nombre,
    tipo: document.getElementById('modal-descuento-tipo').value,
    valor,
    alcance: document.getElementById('modal-descuento-alcance').value,
    categoria: document.getElementById('modal-descuento-categoria').value.trim(),
    skus,
    codigo: document.getElementById('modal-descuento-codigo').value.trim().toUpperCase() || null,
    fecha_inicio: document.getElementById('modal-descuento-fecha-inicio').value || null,
    fecha_fin: document.getElementById('modal-descuento-fecha-fin').value || null,
    uso_maximo: parseInt(document.getElementById('modal-descuento-uso-maximo').value, 10) || null,
    activo: document.getElementById('modal-descuento-activo').checked,
    mostrar_banner: document.getElementById('modal-descuento-banner').checked,
    banner_titulo: document.getElementById('modal-descuento-banner-titulo').value.trim(),
    banner_texto: document.getElementById('modal-descuento-banner-texto').value.trim(),
    recurrente_anual: document.getElementById('modal-descuento-recurrente').checked,
  };

  const id = e.target.dataset.id;
  if (id) datos.id = parseInt(id, 10);

  try {
    await apiCall('guardar_descuento', datos);
    closeModal('modal-descuento-overlay');
    toast(id ? 'Descuento actualizado' : 'Descuento creado', 'success');
    loadDescuentos();
  } catch (err) {
    toast('Error al guardar el descuento: ' + err.message, 'error');
  }
});

// ── Eliminar ──
let descuentoParaEliminar = null;

function pedirEliminarDescuento(id, nombre) {
  descuentoParaEliminar = id;
  document.getElementById('modal-confirmar-texto').textContent =
    `Se eliminará el descuento "${nombre}". Esta acción no se puede deshacer.`;
  openModal('modal-confirmar-overlay');
}

document.getElementById('btn-confirmar-eliminar').addEventListener('click', async () => {
  if (!descuentoParaEliminar) return;
  const id = descuentoParaEliminar;
  descuentoParaEliminar = null;
  try {
    await apiCall('eliminar_descuento', id);
    closeModal('modal-confirmar-overlay');
    toast('Descuento eliminado', 'success');
    loadDescuentos();
  } catch (e) {
    toast('Error al eliminar el descuento: ' + e.message, 'error');
    closeModal('modal-confirmar-overlay');
  }
});
