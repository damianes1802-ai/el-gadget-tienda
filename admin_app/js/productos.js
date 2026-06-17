/* ============================================================
   PANEL EL GADGET — Productos
   ============================================================ */

let categoriasCargadas = false;
let todosLosProductos = [];

async function loadProductos() {
  const tbody = document.getElementById('productos-tbody');
  tbody.innerHTML = '<tr class="loading-row"><td colspan="9">Cargando…</td></tr>';

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
    renderProductosTabla(filtrarProductosSeo(productos));
  } catch (e) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="9">Error al cargar: ${escapeHtml(e.message)}</td></tr>`;
  }
}

function filtrarProductosSeo(productos) {
  const soloPendientes = document.getElementById('productos-solo-seo-pendientes').checked;
  const resumen = document.getElementById('productos-seo-resumen');

  const pendientes = productos.filter(p => (p.stock || 0) > 0 && !p.seo_optimizado_at).length;
  const optimizados = productos.filter(p => (p.stock || 0) > 0 && p.seo_optimizado_at).length;
  resumen.textContent = `SEO: ${optimizados} optimizados, ${pendientes} pendientes`;

  if (!soloPendientes) return productos;
  return productos.filter(p => (p.stock || 0) > 0 && !p.seo_optimizado_at);
}

function renderProductosTabla(productos) {
  const tbody = document.getElementById('productos-tbody');
  if (!productos.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="9">Sin resultados</td></tr>';
    return;
  }

  tbody.innerHTML = productos.map(p => {
    const costo = parseFloat(p.precio_costo) || 0;
    const venta = parseFloat(p.precio_venta) || 0;
    const margenPct = costo > 0 ? ((venta - costo) / costo * 100) : null;
    const margenTexto = margenPct !== null ? `${margenPct.toFixed(0)}%` : '-';
    const sinStock = (p.stock || 0) <= 0;
    const seoBadge = p.seo_optimizado_at
      ? `<span class="badge badge-green" title="${escapeHtml(formatDate(p.seo_optimizado_at))}">Optimizado</span>`
      : '<span class="badge badge-gray">Pendiente</span>';

    return `
      <tr>
        <td class="cell-muted">${escapeHtml(p.sku)}</td>
        <td>${escapeHtml(p.nombre)}</td>
        <td class="cell-muted">${escapeHtml(p.categoria || '-')}</td>
        <td>${formatPrice(costo)}</td>
        <td class="cell-strong">${formatPrice(venta)}</td>
        <td>${margenTexto}</td>
        <td>${sinStock ? '<span class="badge badge-red">Agotado</span>' : `<span class="badge badge-green">${p.stock}</span>`}</td>
        <td>${seoBadge}</td>
        <td><button class="btn btn-outline btn-sm" onclick="abrirEditarProducto('${escapeHtml(p.sku)}')">Editar</button></td>
      </tr>
    `;
  }).join('');
}

// ── Reordenar imágenes (la primera es la portada) ──
let imagenesOrdenActual = [];

function parsearImagenesProducto(p) {
  const principales = p.imagen_principal ? [p.imagen_principal] : [];
  let adicionales = [];
  if (p.imagenes_adicionales) {
    adicionales = p.imagenes_adicionales.replace(/\n/g, ',').split(',').map(s => s.trim()).filter(Boolean);
  }
  return [...principales, ...adicionales];
}

function renderImagenesProducto() {
  const cont = document.getElementById('modal-producto-imagenes');
  if (!imagenesOrdenActual.length) {
    cont.innerHTML = '<p class="cell-muted">Este producto no tiene imágenes cargadas.</p>';
    return;
  }
  cont.innerHTML = imagenesOrdenActual.map((url, i) => `
    <div class="imagen-reorder-item">
      <img src="${escapeHtml(url)}" alt="" loading="lazy">
      ${i === 0 ? '<span class="badge badge-green">Portada</span>' : ''}
      <span class="imagen-reorder-url" title="${escapeHtml(url)}">${escapeHtml(url)}</span>
      <div class="imagen-reorder-actions">
        <button type="button" class="btn btn-outline btn-sm" ${i === 0 ? 'disabled' : ''} onclick="moverImagenProducto(${i}, -1)">↑</button>
        <button type="button" class="btn btn-outline btn-sm" ${i === imagenesOrdenActual.length - 1 ? 'disabled' : ''} onclick="moverImagenProducto(${i}, 1)">↓</button>
      </div>
    </div>
  `).join('');
}

function moverImagenProducto(index, delta) {
  const nuevoIndex = index + delta;
  if (nuevoIndex < 0 || nuevoIndex >= imagenesOrdenActual.length) return;
  [imagenesOrdenActual[index], imagenesOrdenActual[nuevoIndex]] = [imagenesOrdenActual[nuevoIndex], imagenesOrdenActual[index]];
  renderImagenesProducto();
}

function abrirEditarProducto(sku) {
  const p = todosLosProductos.find(x => x.sku === sku);
  if (!p) return;

  document.getElementById('modal-producto-sku').textContent = `(${p.sku})`;
  document.getElementById('modal-producto-nombre').value = p.nombre || '';
  document.getElementById('modal-producto-descripcion').value = p.descripcion || '';
  document.getElementById('modal-producto-categoria').value = p.categoria || '';
  document.getElementById('modal-producto-stock').value = p.stock ?? 0;
  document.getElementById('modal-producto-stock-manual').checked = !!(p.stock_manual);
  document.getElementById('modal-producto-costo').value = formatPrice(p.precio_costo);
  document.getElementById('modal-producto-precio').value = p.precio_venta ?? 0;

  imagenesOrdenActual = parsearImagenesProducto(p);
  renderImagenesProducto();

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
  const stockManual = document.getElementById('modal-producto-stock-manual').checked;
  const precio = parseFloat(document.getElementById('modal-producto-precio').value);

  if (nombre !== (p.nombre || '')) cambios.nombre = nombre;
  if (descripcion !== (p.descripcion || '')) cambios.descripcion = descripcion;
  if (categoria !== (p.categoria || '')) cambios.categoria = categoria;
  if (!isNaN(stock) && stock !== (p.stock ?? 0)) {
    cambios.stock = stock;
    cambios.stock_manual = stockManual;
  } else if (stockManual !== !!(p.stock_manual)) {
    cambios.stock_manual = stockManual;
  }
  if (!isNaN(precio) && precio !== (p.precio_venta ?? 0)) cambios.precio_venta = precio;

  const imagenesOriginal = parsearImagenesProducto(p);
  if (JSON.stringify(imagenesOrdenActual) !== JSON.stringify(imagenesOriginal)) {
    cambios.imagen_principal = imagenesOrdenActual[0] || '';
    cambios.imagenes_adicionales = imagenesOrdenActual.slice(1).join(',');
  }

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
document.getElementById('productos-solo-seo-pendientes').addEventListener('change', () => {
  renderProductosTabla(filtrarProductosSeo(todosLosProductos));
});
document.getElementById('productos-buscar').addEventListener('input', () => {
  clearTimeout(productosSearchTimeout);
  productosSearchTimeout = setTimeout(loadProductos, 350);
});
