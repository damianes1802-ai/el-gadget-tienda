/* ============================================================
   PANEL EL GADGET — utilidades compartidas
   ============================================================ */

// ── Conexión con el bridge de pywebview ──
let pywebviewReady = false;
const pywebviewReadyPromise = new Promise((resolve) => {
  if (window.pywebview) { pywebviewReady = true; resolve(); return; }
  window.addEventListener('pywebviewready', () => { pywebviewReady = true; resolve(); });
});

/**
 * Llama a un método de la clase Api (scripts/admin_desktop.py) y devuelve su resultado.
 * Si el método devuelve { error: "..." }, lanza una excepción con ese mensaje.
 */
async function apiCall(method, ...args) {
  await pywebviewReadyPromise;
  const fn = window.pywebview.api[method];
  if (!fn) throw new Error(`Método de API no encontrado: ${method}`);
  const result = await fn(...args);
  if (result && typeof result === 'object' && result.error) {
    throw new Error(result.error);
  }
  return result;
}

// ── Formato de moneda / fecha ──
function formatPrice(val) {
  const n = parseFloat(val) || 0;
  return '$' + n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
}

function formatPriceDecimal(val) {
  const n = parseFloat(val) || 0;
  return '$' + n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(fecha) {
  if (!fecha) return '-';
  const d = new Date(fecha.includes('T') || fecha.includes('Z') ? fecha : fecha.replace(' ', 'T'));
  if (isNaN(d.getTime())) return fecha;
  return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

// ── Badges ──
function badgeEstado(estado) {
  const map = {
    pendiente_procesar: ['badge-yellow', 'Pendiente'],
    procesando: ['badge-blue', 'Procesando'],
    enviado: ['badge-purple', 'Enviado'],
    entregado: ['badge-green', 'Entregado'],
    cancelado: ['badge-red', 'Cancelado'],
  };
  const [cls, label] = map[estado] || ['badge-gray', estado || '-'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function badgePago(estado) {
  const map = {
    approved: ['badge-green', 'Aprobado'],
    pending: ['badge-yellow', 'Pendiente'],
    rejected: ['badge-red', 'Rechazado'],
  };
  const [cls, label] = map[estado] || ['badge-gray', estado || '-'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function badgeFactura(orden) {
  if (orden.factura_cae) {
    return `<span class="badge badge-green">CAE ${orden.factura_cae}</span>`;
  }
  if (orden.factura_error) {
    return `<span class="badge badge-red">Error</span>`;
  }
  return `<span class="badge badge-gray">Sin facturar</span>`;
}

function badgeArrepentimiento(estado) {
  const map = {
    pendiente: ['badge-yellow', 'Pendiente'],
    aprobado: ['badge-green', 'Aprobado'],
    rechazado: ['badge-red', 'Rechazado'],
  };
  const [cls, label] = map[estado] || ['badge-gray', estado || '-'];
  return `<span class="badge ${cls}">${label}</span>`;
}

// ── Toast ──
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ── Modales ──
function openModal(id) {
  document.getElementById(id).classList.add('show');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('show');
}

// Cierra modales con los botones [data-close] o clic fuera del contenido
document.addEventListener('click', (e) => {
  const closeId = e.target.getAttribute && e.target.getAttribute('data-close');
  if (closeId) { closeModal(closeId); return; }
  if (e.target.classList && e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('show');
  }
});

// ── Modal de confirmación de eliminación (genérico) ──
// Cualquier sección puede llamar a confirmarEliminar(mensaje, onConfirm) para
// reutilizar el modal #modal-confirmar-overlay sin pisar el callback de otra.
let _confirmarEliminarCallback = null;

function confirmarEliminar(mensaje, onConfirm) {
  document.getElementById('modal-confirmar-texto').textContent = mensaje;
  _confirmarEliminarCallback = onConfirm;
  openModal('modal-confirmar-overlay');
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btn-confirmar-eliminar');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const callback = _confirmarEliminarCallback;
    _confirmarEliminarCallback = null;
    closeModal('modal-confirmar-overlay');
    if (callback) await callback();
  });
});

// ── Loader inicial ──
function hideLoader() {
  const el = document.getElementById('loader-overlay');
  if (el) el.classList.add('hide');
}

function setStatus(ok, text) {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-text');
  dot.className = 'status-dot ' + (ok ? 'ok' : 'error');
  label.textContent = text;
}

// ── Escapado simple para texto insertado en HTML ──
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
