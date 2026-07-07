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
  if (alcance === 'categoria') cargarCategoriasDescuento();
}

/* ── Categorías: select poblado desde el API (evita errores de tipeo) ── */
let _categoriasDescCargadas = false;
async function cargarCategoriasDescuento(valorActual) {
  const sel = document.getElementById('modal-descuento-categoria');
  if (!_categoriasDescCargadas) {
    try {
      const cats = await apiCall('get_categorias');
      (cats || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.categoria;
        opt.textContent = `${c.categoria} (${c.total})`;
        sel.appendChild(opt);
      });
      _categoriasDescCargadas = true;
    } catch (e) { /* si falla, el select queda con la opción vacía */ }
  }
  if (valorActual) {
    // Si la categoría guardada no está en la lista (vieja/renombrada), agregarla
    if (![...sel.options].some(o => o.value === valorActual)) {
      const opt = document.createElement('option');
      opt.value = valorActual;
      opt.textContent = `${valorActual} (no encontrada en el catálogo actual)`;
      sel.appendChild(opt);
    }
    sel.value = valorActual;
  }
}

/* ── SKUs: buscador con resultados clickeables + chips ──
   El textarea oculto modal-descuento-skus sigue siendo la fuente de datos
   (separados por coma), así guardar/editar no cambian. */
const _skuNombres = {};  // sku -> nombre (para mostrar chips lindos)

function _skusActuales() {
  return document.getElementById('modal-descuento-skus').value
    .split(',').map(s => s.trim()).filter(Boolean);
}

function _setSkus(lista) {
  document.getElementById('modal-descuento-skus').value = lista.join(', ');
  renderSkuChips();
}

function renderSkuChips() {
  const wrap = document.getElementById('modal-descuento-sku-chips');
  const skus = _skusActuales();
  if (!skus.length) { wrap.innerHTML = '<span class="cell-muted" style="font-size:12px">Ningún producto seleccionado</span>'; return; }
  wrap.innerHTML = skus.map(sku => `
    <span style="display:inline-flex;align-items:center;gap:6px;background:var(--cream,#F7F6F3);border:1px solid var(--gray-200,#e5e7eb);border-radius:16px;padding:3px 10px;font-size:12px">
      <strong>${escapeHtml(sku)}</strong>${_skuNombres[sku] ? ` <span class="cell-muted">${escapeHtml(String(_skuNombres[sku]).slice(0, 34))}</span>` : ''}
      <button type="button" onclick="quitarSkuDescuento('${escapeHtml(sku)}')" style="border:none;background:none;cursor:pointer;font-weight:700;color:var(--gray-600,#6b7280);padding:0">✕</button>
    </span>`).join('');
}

function agregarSkuDescuento(sku, nombre) {
  _skuNombres[sku] = nombre || _skuNombres[sku] || '';
  const skus = _skusActuales();
  if (!skus.includes(sku)) skus.push(sku);
  _setSkus(skus);
  document.getElementById('modal-descuento-sku-buscar').value = '';
  document.getElementById('modal-descuento-sku-resultados').style.display = 'none';
}

function quitarSkuDescuento(sku) {
  _setSkus(_skusActuales().filter(s => s !== sku));
}

let _skuBuscarTimer = null;
document.getElementById('modal-descuento-sku-buscar').addEventListener('input', (e) => {
  const term = e.target.value.trim();
  clearTimeout(_skuBuscarTimer);
  const resDiv = document.getElementById('modal-descuento-sku-resultados');
  if (term.length < 2) { resDiv.style.display = 'none'; return; }
  _skuBuscarTimer = setTimeout(async () => {
    try {
      const productos = await apiCall('get_productos', null, term, true);
      const lista = (productos || []).slice(0, 8);
      if (!lista.length) {
        resDiv.innerHTML = '<div style="padding:10px 12px;font-size:12.5px" class="cell-muted">Sin resultados</div>';
      } else {
        resDiv.innerHTML = lista.map(p => `
          <div onclick="agregarSkuDescuento('${escapeHtml(p.sku)}', '${escapeHtml((p.nombre || '').replace(/'/g, ''))}')"
               style="padding:8px 12px;font-size:12.5px;cursor:pointer;border-bottom:1px solid var(--gray-100,#f3f4f6)"
               onmouseover="this.style.background='var(--cream,#F7F6F3)'" onmouseout="this.style.background=''">
            <strong>${escapeHtml(p.sku)}</strong> — ${escapeHtml(p.nombre || '')}
            <span class="cell-muted">(${formatPrice(p.precio_venta)}${(p.stock || 0) <= 0 ? ' · sin stock' : ''})</span>
          </div>`).join('');
      }
      resDiv.style.display = '';
    } catch (err) { resDiv.style.display = 'none'; }
  }, 300);
});

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
  document.getElementById('modal-descuento-sku-buscar').value = '';
  document.getElementById('modal-descuento-sku-resultados').style.display = 'none';
  renderSkuChips();
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
  cargarCategoriasDescuento(d.categoria || '');
  document.getElementById('modal-descuento-skus').value = (d.skus || []).join(', ');
  renderSkuChips();
  document.getElementById('modal-descuento-codigo').value = d.codigo || '';
  // Los inputs type="date" solo aceptan exactamente 'YYYY-MM-DD': recortar
  // cualquier resto (hora, espacios) para que la fecha guardada siempre aparezca.
  document.getElementById('modal-descuento-fecha-inicio').value = (d.fecha_inicio || '').slice(0, 10);
  document.getElementById('modal-descuento-fecha-fin').value = (d.fecha_fin || '').slice(0, 10);
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

  // Una campaña recurrente sin fechas completas quedaría activa TODO el año.
  // El input type="date" devuelve '' si la fecha está incompleta (ej: sin año),
  // así que exigimos ambas fechas completas — con cualquier año, se ignora.
  const recurrenteChk = document.getElementById('modal-descuento-recurrente').checked;
  const fIni = document.getElementById('modal-descuento-fecha-inicio').value;
  const fFin = document.getElementById('modal-descuento-fecha-fin').value;
  if (recurrenteChk && (!fIni || !fFin)) {
    toast('Las campañas recurrentes necesitan fecha de inicio y fin COMPLETAS (poné cualquier año: se ignora, solo cuentan día y mes)', 'error');
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
