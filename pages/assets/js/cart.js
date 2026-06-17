/* ============================================================
   EL GADGET — Carrito compartido (localStorage)
   Item: { sku, nombre, precio, imagen, cantidad, color, talle }
   ============================================================ */

const CARRITO_KEY = 'carrito';
const EG_API_URL = 'https://el-gadget-tienda.onrender.com';

function getCarrito() {
  return JSON.parse(localStorage.getItem(CARRITO_KEY) || '[]');
}

function guardarCarrito(carrito) {
  localStorage.setItem(CARRITO_KEY, JSON.stringify(carrito));
}

function cartCount(carrito) {
  return carrito.reduce((s, i) => s + i.cantidad, 0);
}

function cartTotal(carrito) {
  return carrito.reduce((s, i) => s + i.precio * i.cantidad, 0);
}

function formatPrice(val) {
  const n = parseFloat(val) || 0;
  return '$' + n.toLocaleString('es-AR', { maximumFractionDigits: 0 });
}

/**
 * Refresca el badge del header y la barra inferior de carrito
 * en cualquier página que incluya esos elementos (#cartBadge, #cartBar,
 * #cartBarCount, #cartBarTotal). Devuelve el carrito actual.
 */
function actualizarCarritoUI() {
  const carrito = getCarrito();
  const count = cartCount(carrito);
  const total = cartTotal(carrito);

  const badge = document.getElementById('cartBadge');
  if (badge) badge.textContent = count;

  const bar = document.getElementById('cartBar');
  const barCount = document.getElementById('cartBarCount');
  const barTotal = document.getElementById('cartBarTotal');
  if (barCount) barCount.textContent = count;
  if (barTotal) barTotal.textContent = formatPrice(total);
  if (bar) bar.classList.toggle('show', count > 0);

  return carrito;
}

/**
 * Agrega un producto al carrito (o incrementa su cantidad si ya existe,
 * matcheando por SKU). item: { sku, nombre, precio, imagen, cantidad, color, talle }
 * Cada página define su propio "agregarAlCarrito(...)" (con la firma que
 * necesite) que internamente llama a esta función de bajo nivel.
 */
function addCartItem(item) {
  const carrito = getCarrito();
  const existente = carrito.find(i => i.sku === item.sku);
  if (existente) {
    existente.cantidad += item.cantidad || 1;
  } else {
    carrito.push({
      sku: item.sku,
      nombre: item.nombre,
      precio: item.precio,
      imagen: item.imagen || '',
      color: item.color || '',
      talle: item.talle || '',
      cantidad: item.cantidad || 1
    });
  }
  guardarCarrito(carrito);
  actualizarCarritoUI();
  return carrito;
}

function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), 2200);
}

function escapeHtmlBasico(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Prefijo relativo para enlazar a páginas de la raíz de pages/ (login,
 * mi_cuenta.html, etc.) tanto desde la raíz como desde las páginas de
 * producto, que viven dos niveles más abajo (pages/producto/<slug>/).
 */
function egRootPath() {
  return location.pathname.includes('/producto/') ? '../../' : '';
}

/**
 * Popup de bienvenida: ofrece 10% OFF a cambio de registrarse con
 * nombre + email. Se inyecta en cualquier página (excepto checkout)
 * si todavía no fue cerrado/usado.
 */
function initPopupRegistro() {
  if (localStorage.getItem('eg_popup_dismissed')) return;
  if (location.pathname.endsWith('checkout') || location.pathname.endsWith('checkout.html')) return;
  if (location.pathname.endsWith('login') || location.pathname.endsWith('mi_cuenta') || location.pathname.endsWith('mi_cuenta.html')) return;

  const overlay = document.createElement('div');
  overlay.className = 'eg-popup-overlay';
  overlay.id = 'egPopupOverlay';
  overlay.innerHTML = `
    <div class="eg-popup-card">
      <button class="eg-popup-close" id="egPopupClose" aria-label="Cerrar">&times;</button>
      <div id="egPopupContenido">
        <div class="eg-popup-emoji">🎁</div>
        <h2>10% OFF en tu primera compra</h2>
        <p>Creá tu cuenta y obtené un 10% de descuento automático en tu primera compra.</p>
        <div class="field">
          <label>Nombre</label>
          <input type="text" id="egPopupNombre" placeholder="Tu nombre">
        </div>
        <div class="field">
          <label>Email</label>
          <input type="email" id="egPopupEmail" placeholder="tu@email.com">
        </div>
        <div class="field">
          <label>Teléfono</label>
          <input type="tel" id="egPopupTelefono" placeholder="11 1234 5678">
        </div>
        <div class="field">
          <label>Contraseña</label>
          <input type="password" id="egPopupPassword" placeholder="Mínimo 6 caracteres">
        </div>
        <div class="field">
          <label>Confirmar contraseña</label>
          <input type="password" id="egPopupPassword2" placeholder="Repetí tu contraseña">
        </div>
        <div class="eg-popup-error" id="egPopupError"></div>
        <button class="btn btn-accent btn-block" id="egPopupSubmit">Quiero mi 10% OFF</button>
        <p style="margin-top:10px;font-size:12.5px">¿Ya tenés cuenta? <a href="${egRootPath()}login">Iniciá sesión</a></p>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      overlay.classList.remove('show');
      localStorage.setItem('eg_popup_dismissed', '1');
    }
  });

  document.getElementById('egPopupClose').addEventListener('click', () => {
    overlay.classList.remove('show');
    localStorage.setItem('eg_popup_dismissed', '1');
  });

  document.getElementById('egPopupSubmit').addEventListener('click', async () => {
    const nombre = document.getElementById('egPopupNombre').value.trim();
    const email = document.getElementById('egPopupEmail').value.trim();
    const telefono = document.getElementById('egPopupTelefono').value.trim();
    const password = document.getElementById('egPopupPassword').value;
    const password2 = document.getElementById('egPopupPassword2').value;
    const errorEl = document.getElementById('egPopupError');
    errorEl.innerHTML = '';
    errorEl.style.display = 'none';

    if (!nombre || !email || !email.includes('@') || !telefono) {
      errorEl.textContent = 'Completá tu nombre, email y teléfono.';
      errorEl.style.display = 'block';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = 'La contraseña debe tener al menos 6 caracteres.';
      errorEl.style.display = 'block';
      return;
    }
    if (password !== password2) {
      errorEl.textContent = 'Las contraseñas no coinciden.';
      errorEl.style.display = 'block';
      return;
    }

    const btn = document.getElementById('egPopupSubmit');
    btn.disabled = true;
    btn.textContent = 'Enviando...';

    try {
      const res = await fetch(`${EG_API_URL}/api/registro`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, email, telefono, password })
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 409) {
          errorEl.innerHTML = `Ya existe una cuenta con ese email. <a href="${egRootPath()}login">Iniciá sesión</a>`;
          errorEl.style.display = 'block';
          btn.disabled = false;
          btn.textContent = 'Quiero mi 10% OFF';
          return;
        }
        throw new Error(data.detail || 'No pudimos completar el registro');
      }

      localStorage.setItem('eg_popup_dismissed', '1');
      localStorage.setItem('eg_token', data.token);
      localStorage.setItem('eg_nombre', data.nombre || nombre);

      const yaUsado = data.descuento_usado === 1 || data.descuento_usado === true;
      if (data.codigo_descuento && !yaUsado) {
        localStorage.setItem('eg_descuento_codigo', data.codigo_descuento);
        localStorage.setItem('eg_descuento_pendiente', '1');
        localStorage.setItem('eg_email_registrado', email);
      }

      document.getElementById('egPopupContenido').innerHTML = `
        <div class="eg-popup-emoji">🎉</div>
        <h2>¡Listo, ${escapeHtmlBasico(nombre)}!</h2>
        <p>${yaUsado
          ? 'Ya usaste tu 10% OFF de bienvenida en una compra anterior. ¡Gracias por volver!'
          : 'Tu 10% OFF se va a aplicar automáticamente en tu primera compra. Te enviamos un email de confirmación.'}</p>
        <button class="btn btn-accent btn-block" id="egPopupCerrar">Entendido</button>
      `;
      document.getElementById('egPopupCerrar').addEventListener('click', () => {
        overlay.classList.remove('show');
      });
      if (!yaUsado) mostrarBannerBienvenida();
      initAccountLink();
    } catch (e) {
      errorEl.textContent = e.message;
      errorEl.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Quiero mi 10% OFF';
    }
  });

  setTimeout(() => overlay.classList.add('show'), 1500);
}

/**
 * En páginas de producto (definen `const PRODUCTO`), consulta el precio
 * y stock actuales en vivo y actualiza #productPrice / #stockBadge si
 * hay una oferta activa o el stock está bajo.
 */
function initOfertaYStockProducto() {
  if (typeof PRODUCTO === 'undefined') return;

  fetch(`${EG_API_URL}/api/producto/${PRODUCTO.sku}`)
    .then(res => res.ok ? res.json() : null)
    .then(data => {
      if (!data) return;

      if (data.precio_oferta != null && data.precio_oferta < data.precio_venta) {
        const priceEl = document.getElementById('productPrice');
        const pct = Math.round((1 - data.precio_oferta / data.precio_venta) * 100);
        if (priceEl) {
          priceEl.innerHTML = `
            <div class="product-price-row">
              <span class="product-price-old">${formatPrice(data.precio_venta)}</span>
              <span class="product-price-offer">${formatPrice(data.precio_oferta)}</span>
              <span class="discount-pill">-${pct}%</span>
            </div>`;
        }
      }

      const stockBadge = document.getElementById('stockBadge');
      if (stockBadge && data.stock > 0 && data.stock <= 5) {
        const txt = data.stock === 1 ? '⚡ ¡Última unidad disponible!' : `⚡ ¡Últimas ${data.stock} unidades!`;
        let urgencyEl = document.querySelector('.urgency-badge');
        if (!urgencyEl) {
          urgencyEl = document.createElement('div');
          urgencyEl.className = 'urgency-badge';
          stockBadge.insertAdjacentElement('afterend', urgencyEl);
        }
        urgencyEl.textContent = txt;
        urgencyEl.style.display = 'flex';
      }
    })
    .catch(() => {});
}

function initVentasBadge() {
  if (typeof PRODUCTO === 'undefined') return;

  fetch(`${EG_API_URL}/api/producto/${PRODUCTO.sku}/ventas`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || !data.ventas) return;
      const n = data.ventas;
      const badge = document.createElement('div');
      badge.className = 'ventas-badge';
      badge.textContent = `🛍️ ${n} ${n === 1 ? 'persona compró' : 'personas compraron'} este producto`;
      const stockEl = document.getElementById('stockBadge');
      if (!stockEl) return;
      let insertAfter = stockEl;
      const next = insertAfter.nextElementSibling;
      if (next && next.classList.contains('urgency-badge')) insertAfter = next;
      insertAfter.insertAdjacentElement('afterend', badge);
    })
    .catch(() => {});
}

/**
 * En páginas de producto, guarda el SKU en localStorage.eg_vistos para
 * mostrar "Vistos recientemente" en el catálogo (máx. 8, sin duplicados,
 * el más reciente primero).
 */
function registrarProductoVisto() {
  if (typeof PRODUCTO === 'undefined') return;
  let vistos = [];
  try {
    vistos = JSON.parse(localStorage.getItem('eg_vistos') || '[]');
  } catch (e) {}
  vistos = vistos.filter(sku => sku !== PRODUCTO.sku);
  vistos.unshift(PRODUCTO.sku);
  localStorage.setItem('eg_vistos', JSON.stringify(vistos.slice(0, 8)));
}

/**
 * Si el usuario se registró y todavía no usó su 10% OFF de bienvenida,
 * inserta un banner fino al principio de la página recordándolo. El
 * banner deja de aparecer solo cuando checkout.html limpia
 * localStorage.eg_descuento_pendiente tras concretar esa compra.
 */
function mostrarBannerBienvenida() {
  if (localStorage.getItem('eg_descuento_pendiente') !== '1') return;
  if (document.getElementById('egWelcomeBanner')) return;

  const banner = document.createElement('div');
  banner.className = 'eg-welcome-banner';
  banner.id = 'egWelcomeBanner';
  banner.textContent = '🎉 Tenés 10% OFF en tu primera compra: se aplica automáticamente al pagar';
  document.body.insertBefore(banner, document.body.firstChild);
}

/**
 * Inyecta en el header (.header-inner, antes del botón de carrito) un
 * enlace a "Mi cuenta" (si hay sesión activa) o "Ingresar" (si no la hay).
 * Se ejecuta en todas las páginas porque cart.js se carga en todas.
 */
function initAccountLink() {
  const headerInner = document.querySelector('.header-inner');
  if (!headerInner) return;

  const root = egRootPath();
  const logueado = !!localStorage.getItem('eg_token');

  let link = document.getElementById('egAccountLink');
  if (!link) {
    link = document.createElement('a');
    link.id = 'egAccountLink';
    link.className = 'account-pill';
    const cartPill = headerInner.querySelector('.cart-pill');
    if (cartPill) {
      headerInner.insertBefore(link, cartPill);
    } else {
      headerInner.appendChild(link);
    }
  }

  if (logueado) {
    link.href = `${root}mi_cuenta`;
    link.innerHTML = '👤 <span class="label">Mi cuenta</span>';
  } else {
    link.href = `${root}login`;
    link.innerHTML = '👤 <span class="label">Ingresar</span>';
  }
}

/**
 * Carga el tarifario de envíos (zonas, partidos de Buenos Aires, etc.)
 * desde la API. Devuelve los datos o null si falla.
 */
async function egCargarZonasEnvio() {
  try {
    const res = await fetch(`${EG_API_URL}/api/envio/zonas`);
    return await res.json();
  } catch (e) {
    return null;
  }
}

/**
 * Calcula la zona/costo de envío para una provincia (y partido de Buenos
 * Aires, si aplica) a partir de los datos de egCargarZonasEnvio().
 * Devuelve { zona, costo, nombre, plazo } o null si no se puede calcular.
 */
function egCalcularEnvio(zonasData, provincia, partido) {
  if (!zonasData || !provincia) return null;

  let zonaId;
  if (provincia === zonasData.provincia_caba) {
    zonaId = zonasData.zona_caba;
  } else if (provincia === zonasData.provincia_buenos_aires) {
    if (!partido) return null;
    zonaId = zonasData.partidos_buenos_aires[partido] || zonasData.zona_default_buenos_aires;
  } else {
    zonaId = zonasData.zona_default_resto_pais;
  }

  return { zona: zonaId, ...zonasData.zonas[zonaId] };
}

document.addEventListener('DOMContentLoaded', () => {
  actualizarCarritoUI();
  initPopupRegistro();
  initOfertaYStockProducto();
  initVentasBadge();
  registrarProductoVisto();
  mostrarBannerBienvenida();
  initAccountLink();
});
