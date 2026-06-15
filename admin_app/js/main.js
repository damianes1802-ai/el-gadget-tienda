/* ============================================================
   PANEL EL GADGET — navegación principal
   ============================================================ */

const SECTION_TITLES = {
  dashboard: 'Dashboard',
  pedidos: 'Pedidos',
  productos: 'Productos',
  precios: 'Precios',
  clientes: 'Clientes',
  arrepentimientos: 'Arrepentimientos',
  usuarios: 'Usuarios',
  descuentos: 'Descuentos',
};

const SECTION_LOADERS = {
  dashboard: loadDashboard,
  pedidos: loadPedidos,
  productos: loadProductos,
  precios: loadPrecios,
  clientes: loadClientes,
  arrepentimientos: loadArrepentimientos,
  usuarios: loadUsuarios,
  descuentos: loadDescuentos,
};

const loadedSections = new Set();
let currentSection = 'dashboard';

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
    SECTION_LOADERS[name]();
  }
}

function refreshCurrentSection() {
  SECTION_LOADERS[currentSection]();
}

document.querySelectorAll('.nav-item').forEach(el => {
  el.addEventListener('click', () => showSection(el.dataset.section));
});

document.getElementById('btn-refresh').addEventListener('click', refreshCurrentSection);

// ── Init ──
(async function init() {
  try {
    await apiCall('get_estadisticas');
    setStatus(true, 'Conectado');
  } catch (e) {
    setStatus(false, 'Sin conexión');
    toast('No se pudo conectar con la API de El Gadget: ' + e.message, 'error');
  } finally {
    hideLoader();
    showSection('dashboard');
  }
})();
