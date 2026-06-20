/* ============================================================
   MARKETING EL GADGET — utilidades compartidas
   ============================================================ */

// ── Conexión con el bridge de pywebview ──
let pywebviewReady = false;
const pywebviewReadyPromise = new Promise((resolve) => {
  if (window.pywebview) { pywebviewReady = true; resolve(); return; }
  window.addEventListener('pywebviewready', () => { pywebviewReady = true; resolve(); });
});

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

// ── Formato ──
function formatPrice(val) {
  const n = parseFloat(val) || 0;
  return '$' + n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
}

function formatNumber(val) {
  const n = parseFloat(val) || 0;
  return n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
}

function formatPercent(val) {
  const n = parseFloat(val) || 0;
  return n.toFixed(1) + '%';
}

function formatDate(fecha) {
  if (!fecha) return '-';
  const d = new Date(fecha.includes('T') || fecha.includes('Z') ? fecha : fecha.replace(' ', 'T'));
  if (isNaN(d.getTime())) return fecha;
  return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function formatDateShort(fecha) {
  if (!fecha) return '-';
  const d = new Date(fecha.includes('T') || fecha.includes('Z') ? fecha : fecha.replace(' ', 'T'));
  if (isNaN(d.getTime())) return fecha;
  return d.toLocaleDateString('es-AR');
}

function formatDelta(current, previous) {
  if (!previous || previous === 0) return { text: '-', cls: 'neutral' };
  const pct = ((current - previous) / previous) * 100;
  const sign = pct >= 0 ? '+' : '';
  return { text: `${sign}${pct.toFixed(1)}%`, cls: pct >= 0 ? 'positive' : 'negative' };
}

// ── Badges ──
function badgeSource(source) {
  const map = {
    referido: ['badge-accent', 'Referido'],
    organico: ['badge-ink', 'Orgánico'],
    promo: ['badge-purple', 'Promo'],
    mayorista: ['badge-green', 'Mayorista'],
  };
  const [cls, label] = map[source] || ['badge-gray', source || '-'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function badgeTier(tier) {
  const map = {
    base: ['badge-gray', 'Base 7%'],
    activo: ['badge-blue', 'Activo 11%'],
    top: ['badge-accent', 'Top 15%'],
  };
  const [cls, label] = map[tier] || ['badge-gray', tier || '-'];
  return `<span class="badge ${cls}">${label}</span>`;
}

// ── Toast ──
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ── Loader ──
function hideLoader() {
  const el = document.getElementById('loader-overlay');
  if (el) el.classList.add('hide');
}

function setStatus(ok, text) {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-text');
  if (dot) dot.className = 'status-dot ' + (ok ? 'ok' : 'error');
  if (label) label.textContent = text;
}

// ── Escapado HTML ──
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
