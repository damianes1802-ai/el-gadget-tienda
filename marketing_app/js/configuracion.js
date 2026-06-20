/* ============================================================
   MARKETING EL GADGET — Configuración
   ============================================================ */

async function loadConfiguracion() {
  const statusEl = document.getElementById('config-api-status');
  const latencyEl = document.getElementById('config-api-latency');

  statusEl.innerHTML = '<span class="badge badge-yellow">Probando...</span>';
  latencyEl.textContent = '';

  try {
    const result = await apiCall('check_connection');
    if (result.ok) {
      statusEl.innerHTML = '<span class="badge badge-green">Conectado</span>';
      latencyEl.textContent = `${result.latency_ms}ms`;
    } else {
      statusEl.innerHTML = '<span class="badge badge-red">Error</span>';
      latencyEl.textContent = result.error || '';
    }
  } catch (e) {
    statusEl.innerHTML = '<span class="badge badge-red">Sin conexión</span>';
    latencyEl.textContent = e.message;
  }

  // Cargar data counts
  const data = _cache;
  document.getElementById('config-count-ordenes').textContent = Array.isArray(data.ordenes) ? data.ordenes.length : '-';
  document.getElementById('config-count-productos').textContent = Array.isArray(data.productos) ? data.productos.length : '-';
  document.getElementById('config-count-referidos').textContent = Array.isArray(data.referidos) ? data.referidos.length : '-';
  document.getElementById('config-count-clientes').textContent = Array.isArray(data.clientes) ? data.clientes.length : '-';
}

document.getElementById('btn-test-connection')?.addEventListener('click', loadConfiguracion);
