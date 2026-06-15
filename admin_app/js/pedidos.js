/* ============================================================
   PANEL EL GADGET — Pedidos
   ============================================================ */

let todosLosPedidos = [];
let pedidoActual = null;

async function loadPedidos() {
  const tbody = document.getElementById('pedidos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="8">Cargando…</td></tr>';

  try {
    const estado = document.getElementById('pedidos-filtro-estado').value;
    todosLosPedidos = await apiCall('get_ordenes', estado || null);
    renderPedidosTabla(filtrarPedidosLocal());
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="8">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function filtrarPedidosLocal() {
  const q = document.getElementById('pedidos-buscar').value.trim().toLowerCase();
  if (!q) return todosLosPedidos;
  return todosLosPedidos.filter(o =>
    (o.cliente_nombre || '').toLowerCase().includes(q) ||
    (o.cliente_email || '').toLowerCase().includes(q) ||
    String(o.id).includes(q)
  );
}

function renderPedidosTabla(pedidos) {
  const tbody = document.getElementById('pedidos-tbody');
  if (!pedidos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="8">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = pedidos.map(o => `
    <tr>
      <td class="cell-strong">#${o.id}</td>
      <td class="cell-muted">${formatDate(o.fecha)}</td>
      <td>
        <div>${escapeHtml(o.cliente_nombre || '-')}</div>
        <div class="cell-muted">${escapeHtml(o.cliente_email || '')}</div>
      </td>
      <td class="cell-strong">${formatPriceDecimal(o.total)}</td>
      <td>${selectEstadoEnvio(o)}</td>
      <td>${badgePago(o.estado_pago)}</td>
      <td>${badgeFactura(o)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-outline btn-sm" onclick="verPedido(${o.id})">Ver</button>
        </div>
      </td>
    </tr>
  `).join('');
}

// ── Estado de envío (desplegable directo en la tabla) ──
const ESTADOS_ENVIO = [
  ['pendiente_procesar', 'Pendiente'],
  ['procesando', 'Procesando'],
  ['enviado', 'Despachado'],
  ['entregado', 'Recibido'],
  ['cancelado', 'Cancelado'],
];

function selectEstadoEnvio(o) {
  const opciones = ESTADOS_ENVIO.map(([valor, texto]) =>
    `<option value="${valor}" ${o.estado === valor ? 'selected' : ''}>${texto}</option>`
  ).join('');
  return `<select class="select-estado-envio estado-${escapeHtml(o.estado || '')}" data-id="${o.id}" onchange="cambiarEstadoEnvio(${o.id}, this)">${opciones}</select>`;
}

async function cambiarEstadoEnvio(id, select) {
  const nuevoEstado = select.value;
  const anterior = select.dataset.anterior || select.className.match(/estado-(\S+)/)?.[1];
  try {
    await apiCall('cambiar_estado_orden', id, nuevoEstado);
    const pedido = todosLosPedidos.find(o => o.id === id);
    if (pedido) pedido.estado = nuevoEstado;
    select.className = `select-estado-envio estado-${nuevoEstado}`;
    select.dataset.anterior = nuevoEstado;
    toast('Estado de envío actualizado', 'success');
  } catch (e) {
    select.value = anterior || '';
    toast('Error al actualizar el estado: ' + e.message, 'error');
  }
}

document.getElementById('pedidos-filtro-estado').addEventListener('change', loadPedidos);
document.getElementById('pedidos-buscar').addEventListener('input', () => renderPedidosTabla(filtrarPedidosLocal()));

// ── Detalle de pedido ──
async function verPedido(id) {
  try {
    const o = await apiCall('get_orden', id);
    pedidoActual = o;

    document.getElementById('modal-pedido-titulo').textContent = `Pedido #${o.id}`;

    const direccion = [o.calle, o.altura, o.piso ? `Piso ${o.piso}` : '', o.departamento]
      .filter(Boolean).join(' ') || o.direccion || '-';

    const itemsHtml = (o.items || []).map(i => `
      <tr>
        <td>${escapeHtml(i.producto_nombre || i.producto_sku)}</td>
        <td style="text-align:center">${i.cantidad}</td>
        <td style="text-align:right">${formatPriceDecimal(i.precio_unitario)}</td>
        <td style="text-align:right;font-weight:700">${formatPriceDecimal(i.subtotal)}</td>
      </tr>
    `).join('');

    const costoEnvio = Number(o.costo_envio || 0);
    const subtotalProductos = (o.items || []).reduce((acc, i) => acc + Number(i.subtotal || 0), 0);
    const footerHtml = costoEnvio > 0
      ? `<tr><td colspan="3" style="padding:6px 16px;text-align:right">Subtotal</td><td style="padding:6px 16px;text-align:right">${formatPriceDecimal(subtotalProductos)}</td></tr>
         <tr><td colspan="3" style="padding:6px 16px;text-align:right">Envío</td><td style="padding:6px 16px;text-align:right">${formatPriceDecimal(costoEnvio)}</td></tr>
         <tr style="background:var(--gray-100)"><td colspan="3" style="padding:10px 16px;text-align:right;font-weight:700">TOTAL</td><td style="padding:10px 16px;text-align:right;font-weight:700;font-size:15px">${formatPriceDecimal(o.total)}</td></tr>`
      : `<tr style="background:var(--gray-100)"><td colspan="3" style="padding:10px 16px;text-align:right;font-weight:700">TOTAL</td><td style="padding:10px 16px;text-align:right;font-weight:700;font-size:15px">${formatPriceDecimal(o.total)}</td></tr>`;

    let facturaHtml;
    if (o.factura_cae) {
      facturaHtml = `<span class="badge badge-green">Factura C ${String(o.factura_punto_venta).padStart(4,'0')}-${String(o.factura_numero).padStart(8,'0')} · CAE ${o.factura_cae}</span>`;
    } else if (o.factura_error) {
      facturaHtml = `<span class="badge badge-red">Error: ${escapeHtml(o.factura_error)}</span>`;
    } else {
      facturaHtml = `<span class="badge badge-gray">Sin facturar</span>`;
    }

    const emailHtml = o.email_confirmacion_enviado
      ? `<span class="badge badge-green">Enviado</span>`
      : `<span class="badge badge-gray">No enviado</span>`;

    document.getElementById('modal-pedido-body').innerHTML = `
      <div class="detalle-grid">
        <div class="detalle-campo"><strong>Cliente</strong>${escapeHtml(o.nombre || '-')} ${escapeHtml(o.apellido || '')}</div>
        <div class="detalle-campo"><strong>Email</strong>${escapeHtml(o.email || '-')}</div>
        <div class="detalle-campo"><strong>Teléfono</strong>${escapeHtml(o.telefono || '-')}</div>
        <div class="detalle-campo"><strong>CUIT / DNI</strong>${escapeHtml(o.cuit_dni || '-')}</div>
        <div class="detalle-campo"><strong>Dirección</strong>${escapeHtml(direccion)}</div>
        <div class="detalle-campo"><strong>Provincia / Ciudad</strong>${escapeHtml(o.provincia || '-')}${o.partido ? ` (${escapeHtml(o.partido)})` : ''} / ${escapeHtml(o.ciudad || '-')}</div>
        <div class="detalle-campo"><strong>Código postal</strong>${escapeHtml(o.codigo_postal || '-')}</div>
        <div class="detalle-campo"><strong>Envío</strong>${o.zona_envio ? `${escapeHtml(o.zona_envio)} · ${formatPriceDecimal(o.costo_envio)}` : '-'}</div>
        <div class="detalle-campo"><strong>Fecha</strong>${formatDate(o.fecha)}</div>
        <div class="detalle-campo"><strong>Estado pedido</strong>${badgeEstado(o.estado)}</div>
        <div class="detalle-campo"><strong>Estado pago</strong>${badgePago(o.estado_pago)}</div>
        <div class="detalle-campo"><strong>Factura AFIP</strong>${facturaHtml}</div>
        <div class="detalle-campo"><strong>Email de confirmación</strong>${emailHtml}</div>
        <div class="detalle-campo span-2">
          <strong>Tracking Droppers</strong>
          <div style="display:flex;gap:8px;align-items:center;margin-top:2px">
            <input type="text" id="pedido-tracking-input" value="${escapeHtml(o.tracking_url || '')}" placeholder="https://...">
            <button class="btn btn-dark btn-sm" onclick="guardarTracking()">Guardar</button>
          </div>
          ${o.tracking_url ? `<a href="${escapeHtml(o.tracking_url)}" target="_blank" style="font-size:12px;color:var(--accent-deep);display:inline-block;margin-top:6px">Abrir link de seguimiento ↗</a>` : ''}
        </div>
        ${o.notas ? `<div class="detalle-campo span-2"><strong>Notas</strong>${escapeHtml(o.notas)}</div>` : ''}
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>Producto</th><th style="text-align:center">Cant.</th><th style="text-align:right">Precio</th><th style="text-align:right">Subtotal</th></tr>
          </thead>
          <tbody>${itemsHtml}</tbody>
          <tfoot>${footerHtml}</tfoot>
        </table>
      </div>
    `;

    document.getElementById('modal-pedido-footer').innerHTML = `
      <button class="btn btn-outline" onclick="copiarParaDroppers()">Copiar para Droppers</button>
      <button class="btn btn-outline" onclick="reprocesarPago(${o.id})">Reprocesar factura / email</button>
      <button class="btn btn-dark" onclick="abrirCambiarEstado()">Cambiar estado</button>
      <button class="btn btn-danger" onclick="pedirEliminarPedido(${o.id}, '${escapeHtml((o.cliente_nombre||o.nombre||'').replace(/'/g, "\\'"))}')">Eliminar pedido</button>
    `;

    openModal('modal-pedido-overlay');
  } catch (e) {
    toast('Error al cargar el pedido: ' + e.message, 'error');
  }
}

// ── Tracking ──
async function guardarTracking() {
  if (!pedidoActual) return;
  const trackingUrl = document.getElementById('pedido-tracking-input').value.trim();

  try {
    await apiCall('actualizar_tracking', pedidoActual.id, trackingUrl);
    toast('Tracking guardado', 'success');
    await verPedido(pedidoActual.id);
    loadPedidos();
  } catch (e) {
    toast('Error al guardar el tracking: ' + e.message, 'error');
  }
}

// ── Copiar para Droppers ──
const PROVINCIAS_DROPPERS = {
  'Buenos Aires': 'Buenos Aires', 'CABA': 'Ciudad Autónoma de Buenos Aires',
  'Capital Federal': 'Ciudad Autónoma de Buenos Aires', 'Catamarca': 'Catamarca',
  'Chaco': 'Chaco', 'Chubut': 'Chubut', 'Córdoba': 'Córdoba',
  'Corrientes': 'Corrientes', 'Entre Ríos': 'Entre Ríos', 'Formosa': 'Formosa',
  'Jujuy': 'Jujuy', 'La Pampa': 'La Pampa', 'La Rioja': 'La Rioja',
  'Mendoza': 'Mendoza', 'Misiones': 'Misiones', 'Neuquén': 'Neuquén',
  'Río Negro': 'Río Negro', 'Salta': 'Salta', 'San Juan': 'San Juan',
  'San Luis': 'San Luis', 'Santa Cruz': 'Santa Cruz', 'Santa Fe': 'Santa Fe',
  'Santiago del Estero': 'Santiago del Estero', 'Tierra del Fuego': 'Tierra del Fuego',
  'Tucumán': 'Tucumán',
};

function copiarParaDroppers() {
  if (!pedidoActual) return;
  const o = pedidoActual;

  const provincia = PROVINCIAS_DROPPERS[o.provincia] || o.provincia || '';
  const productosTexto = (o.items || []).map(i =>
    `  - ${i.producto_nombre || i.producto_sku} x${i.cantidad} (SKU: ${i.producto_sku || '-'})`
  ).join('\n');

  const texto = `=== PEDIDO DROPPERS - Orden #${o.id} ===

DATOS DEL DESTINATARIO:
Nombre: ${(o.nombre || '').trim()}
Apellido: ${(o.apellido || '').trim()}
Razón social: ${o.razon_social || ''}
CUIT / DNI: ${o.cuit_dni || ''}
Email: ${o.email || ''}
Teléfono / Celular: ${o.telefono || ''}

DIRECCIÓN DE ENVÍO:
Calle: ${o.calle || ''}
Altura: ${o.altura || ''}
Piso: ${o.piso || ''}
Departamento: ${o.departamento || ''}
Localidad: ${o.ciudad || ''}
Partido: ${o.partido || ''}
Provincia: ${provincia}
Código postal: ${o.codigo_postal || ''}

PRODUCTOS:
${productosTexto || '  (sin detalle)'}

TOTAL: ${formatPriceDecimal(o.total)}
COSTO DE ENVÍO INCLUIDO: ${formatPriceDecimal(o.costo_envio || 0)}
=====================================`;

  navigator.clipboard.writeText(texto).then(() => {
    toast('Copiado al portapapeles', 'success');
  }).catch(() => {
    toast('No se pudo copiar al portapapeles', 'error');
  });
}

// ── Reprocesar factura / email ──
async function reprocesarPago(id) {
  try {
    const resultado = await apiCall('procesar_pago', id);
    toast('Reprocesado correctamente', 'success');
    if (pedidoActual && pedidoActual.id === id) {
      Object.assign(pedidoActual, resultado);
      await verPedido(id);
    }
    loadPedidos();
  } catch (e) {
    toast('Error al reprocesar: ' + e.message, 'error');
  }
}

// ── Cambiar estado ──
function abrirCambiarEstado() {
  if (!pedidoActual) return;
  document.getElementById('modal-estado-id').textContent = pedidoActual.id;
  document.getElementById('modal-estado-select').value = pedidoActual.estado || 'pendiente_procesar';
  openModal('modal-estado-overlay');
}

document.getElementById('btn-guardar-estado').addEventListener('click', async () => {
  if (!pedidoActual) return;
  const estado = document.getElementById('modal-estado-select').value;
  try {
    await apiCall('cambiar_estado_orden', pedidoActual.id, estado);
    closeModal('modal-estado-overlay');
    toast('Estado actualizado', 'success');
    await verPedido(pedidoActual.id);
    loadPedidos();
  } catch (e) {
    toast('Error al actualizar el estado: ' + e.message, 'error');
  }
});

// ── Eliminar ──
function pedirEliminarPedido(id, nombre) {
  confirmarEliminar(
    `Se eliminará el pedido #${id} de ${nombre || 'este cliente'}. Esta acción no se puede deshacer.`,
    async () => {
      try {
        await apiCall('eliminar_orden', id);
        closeModal('modal-pedido-overlay');
        toast(`Pedido #${id} eliminado`, 'success');
        loadPedidos();
      } catch (e) {
        toast('Error al eliminar el pedido: ' + e.message, 'error');
      }
    }
  );
}
