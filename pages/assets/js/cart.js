/* ============================================================
   EL GADGET — Carrito compartido (localStorage)
   Item: { sku, nombre, precio, imagen, cantidad, color, talle }
   ============================================================ */

const CARRITO_KEY = 'carrito';
const EG_API_URL = 'https://el-gadget-tienda.onrender.com';
const GA4_ID = 'G-D8GWDT1CBS';

function initGA4() {
  window.dataLayer = window.dataLayer || [];
  window.gtag = function() { dataLayer.push(arguments); };
  gtag('js', new Date());
  gtag('config', GA4_ID);
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA4_ID}`;
  document.head.appendChild(s);
}

function ga4Event(name, params) {
  if (typeof window.gtag === 'function') window.gtag('event', name, params);
}

const META_PIXEL_ID = '1749660892357733';

function initMetaPixel() {
  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
  n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}
  (window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', META_PIXEL_ID);
  fbq('track', 'PageView');
}

function fbqEvent(name, params) {
  if (typeof window.fbq === 'function') window.fbq('track', name, params);
}

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

/* Subtotal a precio de LISTA (sin ofertas de temporada). Los códigos de
   descuento se calculan sobre este valor y no se combinan con ofertas. */
function cartTotalLista(carrito) {
  return carrito.reduce((s, i) => s + (i.precio_lista || i.precio) * i.cantidad, 0);
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
  const MAX_POR_PRODUCTO = 15;
  const existente = carrito.find(i => i.sku === item.sku);
  if (existente) {
    const nuevaCantidad = existente.cantidad + (item.cantidad || 1);
    if (nuevaCantidad > MAX_POR_PRODUCTO) {
      existente.cantidad = MAX_POR_PRODUCTO;
      guardarCarrito(carrito);
      actualizarCarritoUI();
      if (typeof showToast === 'function') showToast('Máximo 15 unidades por producto. ¿Necesitás más? Escribinos por WhatsApp.');
      return;
    }
    existente.cantidad = nuevaCantidad;
  } else {
    carrito.push({
      sku: item.sku,
      nombre: item.nombre,
      precio: item.precio,
      precio_lista: item.precio_lista || item.precio,
      imagen: item.imagen || '',
      color: item.color || '',
      talle: item.talle || '',
      cantidad: Math.min(item.cantidad || 1, MAX_POR_PRODUCTO)
    });
  }
  guardarCarrito(carrito);
  actualizarCarritoUI();
  ga4Event('add_to_cart', {
    currency: 'ARS',
    value: item.precio * (item.cantidad || 1),
    items: [{ item_id: item.sku, item_name: item.nombre, price: item.precio, quantity: item.cantidad || 1 }]
  });
  fbqEvent('AddToCart', { content_ids: [item.sku], content_name: item.nombre, currency: 'ARS', value: item.precio * (item.cantidad || 1) });
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
        <p>Dejanos tu email y el descuento se aplica solo en tu primera compra. Sin vueltas.</p>
        <div class="field">
          <label>Email</label>
          <input type="email" id="egPopupEmail" placeholder="tu@email.com" autocomplete="email" inputmode="email">
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

  const egPopupEmailInput = document.getElementById('egPopupEmail');
  egPopupEmailInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') document.getElementById('egPopupSubmit').click();
  });

  document.getElementById('egPopupSubmit').addEventListener('click', async () => {
    const email = document.getElementById('egPopupEmail').value.trim();
    const errorEl = document.getElementById('egPopupError');
    errorEl.innerHTML = '';
    errorEl.style.display = 'none';

    if (!email || !email.includes('@') || !email.includes('.')) {
      errorEl.textContent = 'Ingresá un email válido.';
      errorEl.style.display = 'block';
      return;
    }

    const nombre = '';
    const btn = document.getElementById('egPopupSubmit');
    btn.disabled = true;
    btn.textContent = 'Enviando...';

    try {
      const res = await fetch(`${EG_API_URL}/api/registro`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
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
        <h2>¡Listo! Tu 10% OFF te espera</h2>
        <p>${yaUsado
          ? 'Ya usaste tu 10% OFF de bienvenida en una compra anterior. ¡Gracias por volver!'
          : 'Se aplica automáticamente en tu primera compra. Ya podés seguir eligiendo tus productos.'}</p>
        <button class="btn btn-accent btn-block" id="egPopupCerrar">Ver productos</button>
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

  // Disparo diferido (Fogg: mostrar el prompt cuando ya hay algo de motivación,
  // no en el primer paint). Se muestra al primero que ocurra: 30s, scroll >45%,
  // o intención de salida. Una sola vez por sesión.
  let mostrado = false;
  const mostrar = () => {
    if (mostrado || localStorage.getItem('eg_popup_dismissed')) return;
    mostrado = true;
    overlay.classList.add('show');
    limpiarTriggers();
  };
  const onScroll = () => {
    const h = document.documentElement;
    const pct = (h.scrollTop + window.innerHeight) / h.scrollHeight;
    if (pct > 0.45) mostrar();
  };
  const onExit = (e) => { if (e.clientY <= 0) mostrar(); };
  const timer = setTimeout(mostrar, 30000);
  function limpiarTriggers() {
    clearTimeout(timer);
    window.removeEventListener('scroll', onScroll, { passive: true });
    document.removeEventListener('mouseout', onExit);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  document.addEventListener('mouseout', onExit);
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
        // Reflejar la oferta en la barra sticky de compra (mobile)
        const stickyPrice = document.getElementById('pdpStickyPrice');
        if (stickyPrice) stickyPrice.textContent = formatPrice(data.precio_oferta);
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
  if (localStorage.getItem('eg_ref_code')) return;
  if (document.getElementById('egWelcomeBanner')) return;

  const banner = document.createElement('div');
  banner.className = 'eg-welcome-banner';
  banner.id = 'egWelcomeBanner';
  banner.textContent = '🎉 Tenés 10% OFF en tu primera compra: se aplica automáticamente al pagar';
  document.body.insertBefore(banner, document.body.firstChild);
}

/**
 * Captura el parámetro ?ref= de la URL y lo guarda en localStorage
 * para aplicar automáticamente el código de referido en checkout.
 * Muestra un banner verde en todas las páginas mientras el código esté activo.
 */
function capturaRefCode() {
  const params = new URLSearchParams(window.location.search);
  const ref = params.get('ref');
  if (ref && ref.trim()) {
    localStorage.setItem('eg_ref_code', ref.trim().toUpperCase());
  }
  const code = localStorage.getItem('eg_ref_code');
  if (!code) return;
  if (document.getElementById('egRefBanner') || document.getElementById('egComboBanner')) return;

  const tieneBienvenida = localStorage.getItem('eg_descuento_pendiente') === '1';
  const banner = document.createElement('div');

  if (tieneBienvenida) {
    banner.className = 'eg-combo-banner';
    banner.id = 'egComboBanner';
    banner.innerHTML = '<div class="eg-combo-big">Hasta 30% OFF</div>'
      + '<div class="eg-combo-detail">🎉 10% por tu primera compra + hasta 20% con el código <strong>' + code + '</strong> — se aplican automáticamente al pagar</div>';
  } else {
    banner.className = 'eg-ref-banner';
    banner.id = 'egRefBanner';
    banner.innerHTML = '🏷️ Código de descuento <strong>' + code + '</strong> activo — hasta 20% OFF se aplica automáticamente al pagar';
  }
  document.body.insertBefore(banner, document.body.firstChild);
}

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

function hasConsentCookies() {
  return localStorage.getItem('eg_cookies_accepted') === '1';
}

function showCookieBanner() {
  if (localStorage.getItem('eg_cookies_decided')) return;
  const banner = document.createElement('div');
  banner.id = 'eg-cookie-banner';
  // Compacto (una línea): recupera viewport en el funnel y no colisiona con
  // los CTAs de compra. Consentimiento válido igual (LIFT: menos distracción).
  banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#14151A;color:#fff;padding:9px 14px;z-index:9999;display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:nowrap;font-size:12px;line-height:1.35;box-shadow:0 -2px 12px rgba(0,0,0,0.3)';
  banner.innerHTML = `
    <span style="flex:1;min-width:0">🍪 Usamos cookies para mejorar tu experiencia. <a href="/privacidad#cookies" style="color:#FFC700;text-decoration:underline">Más info</a></span>
    <button onclick="acceptCookies()" style="background:#FFC700;color:#14151A;border:none;padding:6px 14px;border-radius:8px;font-weight:700;font-size:12px;cursor:pointer;white-space:nowrap">Aceptar</button>
    <button onclick="rejectOptionalCookies()" aria-label="Solo cookies necesarias" style="background:transparent;color:rgba(255,255,255,0.7);border:none;padding:6px 6px;font-size:12px;cursor:pointer;white-space:nowrap;text-decoration:underline">Solo necesarias</button>
  `;
  document.body.appendChild(banner);
}

function acceptCookies() {
  localStorage.setItem('eg_cookies_accepted', '1');
  localStorage.setItem('eg_cookies_decided', '1');
  document.getElementById('eg-cookie-banner')?.remove();
  initGA4();
  initMetaPixel();
}

function rejectOptionalCookies() {
  localStorage.setItem('eg_cookies_accepted', '0');
  localStorage.setItem('eg_cookies_decided', '1');
  document.getElementById('eg-cookie-banner')?.remove();
}

document.addEventListener('DOMContentLoaded', () => {
  if (hasConsentCookies()) {
    initGA4();
    initMetaPixel();
  } else {
    showCookieBanner();
  }
  actualizarCarritoUI();
  initPopupRegistro();
  initOfertaYStockProducto();
  initVentasBadge();
  registrarProductoVisto();
  mostrarBannerBienvenida();
  capturaRefCode();
  initAccountLink();

  if (typeof PRODUCTO !== 'undefined') {
    ga4Event('view_item', {
      currency: 'ARS',
      value: PRODUCTO.precio_venta,
      items: [{ item_id: PRODUCTO.sku, item_name: PRODUCTO.nombre, price: PRODUCTO.precio_venta, quantity: 1 }]
    });
    fbqEvent('ViewContent', { content_ids: [PRODUCTO.sku], content_name: PRODUCTO.nombre, currency: 'ARS', value: PRODUCTO.precio_venta });
  }

  const enCheckout = location.pathname.endsWith('checkout') || location.pathname.endsWith('checkout.html');
  if (enCheckout) {
    const c = getCarrito();
    if (c.length) {
      ga4Event('begin_checkout', {
        currency: 'ARS',
        value: cartTotal(c),
        items: c.map(i => ({ item_id: i.sku, item_name: i.nombre, price: i.precio, quantity: i.cantidad }))
      });
      fbqEvent('InitiateCheckout', { num_items: cartCount(c), currency: 'ARS', value: cartTotal(c) });
    }
  }
});
