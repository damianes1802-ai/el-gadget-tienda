/* ============================================================
   PANEL EL GADGET — Productos
   ============================================================ */

let categoriasCargadas = false;

async function loadProductos() {
  const tbody = document.getElementById('productos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="7">Cargando…</td></tr>';

  if (!categoriasCargadas) {
    try {
      const categorias = await apiCall('get_categorias');
      const select = document.getElementById('productos-filtro-categoria');
      categorias.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.categoria;
        opt.textContent = `${c.categoria} (${c.total})`;
        select.appendChild(opt);
      });
      categoriasCargadas = true;
    } catch (e) { /* no bloquea la carga de productos */ }
  }

  try {
    const categoria = document.getElementById('productos-filtro-categoria').value;
    const search = document.getElementById('productos-buscar').value.trim();
    const incluirAgotados = document.getElementById('productos-incluir-agotados').checked;

    const productos = await apiCall('get_productos', categoria || null, search || null, incluirAgotados);
    renderProductosTabla(productos);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderProductosTabla(productos) {
  const tbody = document.getElementById('productos-tbody');
  if (!productos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="7">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = productos.map(p => {
    const costo = parseFloat(p.precio_costo) || 0;
    const venta = parseFloat(p.precio_venta) || 0;
    const margenPct = costo > 0 ? ((venta - costo) / costo * 100) : null;
    const margenTexto = margenPct !== null ? `${margenPct.toFixed(0)}%` : '-';
    const sinStock = (p.stock || 0) <= 0;

    return `
      <tr>
        <td class="cell-muted">${escapeHtml(p.sku)}</td>
        <td>${escapeHtml(p.nombre)}</td>
        <td class="cell-muted">${escapeHtml(p.categoria || '-')}</td>
        <td>${formatPrice(costo)}</td>
        <td class="cell-strong">${formatPrice(venta)}</td>
        <td>${margenTexto}</td>
        <td>${sinStock ? '<span class="badge badge-red">Agotado</span>' : `<span class="badge badge-green">${p.stock}</span>`}</td>
      </tr>
    `;
  }).join('');
}

let productosSearchTimeout;
document.getElementById('productos-filtro-categoria').addEventListener('change', loadProductos);
document.getElementById('productos-incluir-agotados').addEventListener('change', loadProductos);
document.getElementById('productos-buscar').addEventListener('input', () => {
  clearTimeout(productosSearchTimeout);
  productosSearchTimeout = setTimeout(loadProductos, 350);
});
