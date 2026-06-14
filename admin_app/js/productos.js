/* ============================================================
   PANEL EL GADGET — Productos
   ============================================================ */

let categoriasCargadas = false;
let todosLosProductos = [];

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
    todosLosProductos = productos;
    renderProductosTabla(productos);
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function renderProductosTabla(productos) {
  const tbody = document.getElementById('productos-tbody');
  if (!productos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="8">Sin resultados</td></tr>';
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
        <td><button class="btn btn-outline btn-sm" onclick="abrirEditarProducto('${escapeHtml(p.sku)}')">Editar</button></td>
      </tr>
    `;
  }).join('');
}

function abrirEditarProducto(sku) {
  const p = todosLosProductos.find(x => x.sku === sku);
  if (!p) return;

  document.getElementById('modal-producto-sku').textContent = `(${p.sku})`;
  document.getElementById('modal-producto-nombre').value = p.nombre || '';
  document.getElementById('modal-producto-descripcion').value = p.descripcion || '';
  document.getElementById('modal-producto-categoria').value = p.categoria || '';
  document.getElementById('modal-producto-stock').value = p.stock ?? 0;
  document.getElementById('modal-producto-costo').value = formatPrice(p.precio_costo);
  document.getElementById('modal-producto-precio').value = p.precio_venta ?? 0;

  document.getElementById('btn-guardar-producto').dataset.sku = sku;
  openModal('modal-producto-overlay');
}

document.getElementById('btn-guardar-producto').addEventListener('click', async (e) => {
  const sku = e.target.dataset.sku;
  const p = todosLosProductos.find(x => x.sku === sku);
  if (!p) return;

  const cambios = {};
  const nombre = document.getElementById('modal-producto-nombre').value.trim();
  const descripcion = document.getElementById('modal-producto-descripcion').value.trim();
  const categoria = document.getElementById('modal-producto-categoria').value.trim();
  const stock = parseInt(document.getElementById('modal-producto-stock').value, 10);
  const precio = parseFloat(document.getElementById('modal-producto-precio').value);

  if (nombre !== (p.nombre || '')) cambios.nombre = nombre;
  if (descripcion !== (p.descripcion || '')) cambios.descripcion = descripcion;
  if (categoria !== (p.categoria || '')) cambios.categoria = categoria;
  if (!isNaN(stock) && stock !== (p.stock ?? 0)) cambios.stock = stock;
  if (!isNaN(precio) && precio !== (p.precio_venta ?? 0)) cambios.precio_venta = precio;

  if (!Object.keys(cambios).length) {
    closeModal('modal-producto-overlay');
    return;
  }

  try {
    const actualizado = await apiCall('actualizar_producto', sku, cambios);
    if (actualizado._remoto && actualizado._remoto.error) {
      throw new Error('Guardado local OK, pero falló en la tienda online: ' + actualizado._remoto.error);
    }
    closeModal('modal-producto-overlay');
    toast('Producto actualizado', 'success');
    loadProductos();
  } catch (e) {
    toast('Error al guardar el producto: ' + e.message, 'error');
  }
});

let productosSearchTimeout;
document.getElementById('productos-filtro-categoria').addEventListener('change', loadProductos);
document.getElementById('productos-incluir-agotados').addEventListener('change', loadProductos);
document.getElementById('productos-buscar').addEventListener('input', () => {
  clearTimeout(productosSearchTimeout);
  productosSearchTimeout = setTimeout(loadProductos, 350);
});
