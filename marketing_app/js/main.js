/* ============================================================
   MARKETING EL GADGET — navegación principal
   ============================================================ */

const SECTION_TITLES = {
  dashboard: 'Dashboard',
  referidos: 'Referidos',
  productos: 'Productos',
  ventas: 'Ventas',
  campanias: 'Campañas',
  contenidos: 'Contenido',
  configuracion: 'Configuración',
};

const loadedSections = new Set();
let currentSection = 'dashboard';

// ── Cache global de datos ──
let _cache = {
  estadisticas: null,
  ordenes: null,
  referidos: null,
  clientes: null,
  usuarios: null,
  descuentos: null,
  productos: null,
  lastFetch: null,
};

async function fetchAllData(force = false) {
  if (_cache.lastFetch && !force) return _cache;
  setStatus(false, 'Despertando servidor...');
  const loaderText = document.querySelector('.loader-text');
  try {
    if (loaderText) loaderText.textContent = 'Despertando servidor (puede tardar ~30s)...';
    const estadisticas = await apiCall('get_estadisticas');

    setStatus(false, 'Cargando datos...');
    if (loaderText) loaderText.textContent = 'Cargando datos...';
    const safe = (p) => p.catch(e => { console.error(e); return []; });
    const [ordenes, referidos, clientes, usuarios, descuentos, productos] = await Promise.all([
      safe(apiCall('get_all_ordenes')),
      safe(apiCall('get_referidos')),
      safe(apiCall('get_clientes')),
      safe(apiCall('get_usuarios')),
      safe(apiCall('get_descuentos')),
      safe(apiCall('get_productos')),
    ]);
    _cache = { estadisticas, ordenes, referidos, clientes, usuarios, descuentos, productos, lastFetch: Date.now() };
    setStatus(true, 'Conectado');
    return _cache;
  } catch (e) {
    setStatus(false, 'Error: ' + e.message);
    throw e;
  }
}

function callSectionLoader(name) {
  const loaders = {
    dashboard: typeof loadDashboard !== 'undefined' ? loadDashboard : null,
    referidos: typeof loadReferidos !== 'undefined' ? loadReferidos : null,
    productos: typeof loadProductos !== 'undefined' ? loadProductos : null,
    ventas: typeof loadVentas !== 'undefined' ? loadVentas : null,
    campanias: typeof loadCampanias !== 'undefined' ? loadCampanias : null,
    contenidos: typeof loadContenidos !== 'undefined' ? loadContenidos : null,
    configuracion: typeof loadConfiguracion !== 'undefined' ? loadConfiguracion : null,
  };
  const fn = loaders[name];
  if (fn) fn();
}

function showSection(name) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.section === name);
  });
  document.querySelectorAll('.section').forEach(el => {
    el.classList.toggle('active', el.id === `section-${name}`);
  });
  document.getElementById('section-title').textContent = SECTION_TITLES[name] || name;
  currentSection = name;

  if (!loadedSections.has(name)) {
    loadedSections.add(name);
    callSectionLoader(name);
  }
}

async function refreshAll() {
  loadedSections.clear();
  await fetchAllData(true);
  showSection(currentSection);
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => showSection(el.dataset.section));
  });

  document.getElementById('btn-refresh').addEventListener('click', refreshAll);

  // ── Init ──
  (async function init() {
    try {
      await pywebviewReadyPromise;
      await fetchAllData(true);
    } catch (e) {
      console.error('[MKT] init error:', e);
      toast('No se pudo conectar con la API: ' + e.message, 'error');
    } finally {
      hideLoader();
      showSection('dashboard');
    }
  })();
});
