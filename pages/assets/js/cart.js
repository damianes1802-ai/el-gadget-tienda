/* ============================================================
   EL GADGET — Carrito compartido (localStorage)
   Item: { sku, nombre, precio, imagen, cantidad, color, talle }
   ============================================================ */

const CARRITO_KEY = 'carrito';
const EG_API_URL = 'https://el-gadget-tienda.onrender.com';
const GA4_ID = 'G-D8GWDT1CBS';

// GA4 se carga SIEMPRE con Consent Mode v2. La analítica (analytics_storage)
// está activa por defecto: en Argentina no rige un opt-in tipo GDPR para
// medición agregada, y sin esto el 60-70% del tráfico que ignora el banner
// desaparecía de los informes (sign_up, referral_visit, purchase). Lo que sí
// queda atado al "Aceptar" del banner es la publicidad: ad_storage /
// ad_user_data / ad_personalization y el Meta Pixel. Quien elige "Solo
// necesarias" no recibe cookies publicitarias. Decisión de Damián, 2026-09-18.
function initGA4() {
  if (window.__egGA4) return;
  window.__egGA4 = true;
  window.dataLayer = window.dataLayer || [];
  window.gtag = function() { dataLayer.push(arguments); };
  const ok = hasConsentCookies();
  gtag('consent', 'default', {
    analytics_storage: 'granted',
    ad_storage: ok ? 'granted' : 'denied',
    ad_user_data: ok ? 'granted' : 'denied',
    ad_personalization: ok ? 'granted' : 'denied'
  });
  gtag('js', new Date());
  // Propiedades de usuario: quién lo refirió y si es referidor. Van ANTES de
  // config para que viajen desde el primer evento de la sesión.
  const props = {};
  const refCode = localStorage.getItem('eg_ref_code');
  if (refCode) props.referido_por = refCode;
  if (localStorage.getItem('eg_es_referido') === '1') props.cliente_referidor = 'si';
  const tier = localStorage.getItem('eg_tier_referido');
  if (tier) props.tier_referido = tier;
  if (Object.keys(props).length) gtag('set', 'user_properties', props);
  const cfg = {};
  // Tráfico interno (Damián probando): abrir una vez elgadget.com.ar/?interno=1
  // en cada navegador propio deja la marca; GA4 lo excluye con el data filter
  // "Internal Traffic" (activo). ?interno=0 la saca.
  const qInterno = new URLSearchParams(location.search).get('interno');
  if (qInterno === '1') localStorage.setItem('eg_trafico_interno', '1');
  if (qInterno === '0') localStorage.removeItem('eg_trafico_interno');
  if (localStorage.getItem('eg_trafico_interno') === '1') cfg.traffic_type = 'internal';
  gtag('config', GA4_ID, cfg);
  const s = document.createElement('script');
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA4_ID}`;
  document.head.appendChild(s);
}

function ga4Consentir() {
  if (typeof window.gtag !== 'function') return;
  gtag('consent', 'update', {
    analytics_storage: 'granted', ad_storage: 'granted',
    ad_user_data: 'granted', ad_personalization: 'granted'
  });
}

function ga4Event(name, params) {
  if (typeof window.gtag === 'function') window.gtag('event', name, params);
}

function ga4SetUserProps(props) {
  if (typeof window.gtag === 'function') window.gtag('set', 'user_properties', props);
}

// ── Listas de productos (view_item_list / select_item) ──────────────────────
// Lee las cards del DOM (a.card[data-sku]) para no depender de cada página.
function egItemsDeCards(cards, listName) {
  return Array.from(cards).slice(0, 30).map((a, i) => ({
    item_id: a.dataset.sku,
    item_name: (a.querySelector('.card-name')?.textContent || a.dataset.nombre || a.dataset.sku).trim(),
    price: Number(a.dataset.precio || 0),
    index: i,
    item_list_name: listName
  }));
}

let _egUltimaLista = '';
function trackItemList(listName, cards) {
  const items = egItemsDeCards(cards, listName);
  if (!items.length) return;
  // La misma lista no se reporta dos veces seguidas (re-render por filtros).
  const firma = listName + '|' + items.length + '|' + items[0].item_id;
  if (firma === _egUltimaLista) return;
  _egUltimaLista = firma;
  ga4Event('view_item_list', { item_list_name: listName, items });
}

function egNombreListaPagina() {
  const h1 = document.querySelector('h1');
  return (h1 ? h1.textContent : document.title.replace(' | El Gadget', '')).trim().slice(0, 100);
}

function initItemListTracking() {
  // select_item: click en cualquier card con SKU (índice, categorías, colecciones)
  document.addEventListener('click', e => {
    const a = e.target.closest('a.card[data-sku]');
    if (!a || e.target.closest('.card-btn')) return;
    const listName = a.closest('[data-list-name]')?.dataset.listName || egNombreListaPagina();
    const grilla = a.closest('#productGrid, #listadoGrid, .grid') || document;
    const item = egItemsDeCards([a], listName)[0];
    item.index = Array.from(grilla.querySelectorAll('a.card[data-sku]')).indexOf(a);
    ga4Event('select_item', { item_list_name: listName, items: [item] });
  });
  // view_item_list en páginas estáticas (categorías/colecciones) — el índice
  // lo dispara desde renderGrid porque su grilla se arma por JS.
  const estaticas = document.querySelectorAll('#listadoGrid a.card[data-sku]');
  if (estaticas.length) trackItemList(egNombreListaPagina(), estaticas);
  // Bloques estáticos con nombre propio (Destacados de la home, regalos por
  // presupuesto en el blog): los escribe el generador, se miden por su data-list-name.
  document.querySelectorAll('[data-list-name]').forEach(c => {
    if (c.id === 'productGrid' || c.id === 'listadoGrid') return;
    const cards = c.querySelectorAll('a.card[data-sku]');
    if (cards.length) trackItemList(c.dataset.listName, cards);
  });
}

// ── Leads por WhatsApp (generate_lead) ───────────────────────────────────────
// Solo links de CONTACTO (con número). Los wa.me/?text=... sin número son
// "compartir" y ya se miden como share.
function initLeadTracking() {
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href]');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    const esWa = /wa\.me\/\d{6,}|api\.whatsapp\.com\/send\?[^#]*phone=|whatsapp:\/\/send\?[^#]*phone=/i.test(href);
    if (!esWa) return;
    ga4Event('generate_lead', {
      method: 'whatsapp',
      page_type: egTipoDePagina(),
      item_id: (typeof PRODUCTO !== 'undefined' && PRODUCTO.sku) || undefined,
      currency: 'ARS',
      value: (typeof PRODUCTO !== 'undefined' && Number(PRODUCTO.precio_venta)) || undefined
    });
    fbqEvent('Contact', { content_category: egTipoDePagina() });
  });
}

function egTipoDePagina() {
  const p = location.pathname;
  if (typeof PRODUCTO !== 'undefined') return 'producto';
  if (p.startsWith('/categoria/')) return 'categoria';
  if (p.startsWith('/coleccion/')) return 'coleccion';
  if (p.startsWith('/ganar/')) return 'ganar';
  if (p.startsWith('/blog/')) return 'blog';
  if (/checkout|carrito|confirmacion/.test(p)) return 'checkout';
  if (/contacto|sobre_nosotros/.test(p)) return 'contacto';
  if (/mi_cuenta|login|referidos/.test(p)) return 'cuenta';
  if (p === '/' || /index/.test(p)) return 'home';
  return 'otra';
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
  // Landings de referidos: la visita viene a GANAR plata, no a comprar.
  // La oferta de comprador acá es ruido justo en el momento de conversión.
  if (location.pathname.startsWith('/ganar')) return;

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
  // Landings de Ads (body[data-eg-landing]): tráfico pago de alta intención de compra.
  // No interrumpir con timer ni scroll; ofrecer el 10% solo en exit-intent (recupera a
  // quien se va, sin molestar al comprador enganchado). En mobile no hay exit-intent -> sin popup.
  const esLanding = document.body && document.body.getAttribute('data-eg-landing') === '1';
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
  const timer = esLanding ? null : setTimeout(mostrar, 30000);
  function limpiarTriggers() {
    if (timer) clearTimeout(timer);
    window.removeEventListener('scroll', onScroll, { passive: true });
    document.removeEventListener('mouseout', onExit);
  }
  if (!esLanding) window.addEventListener('scroll', onScroll, { passive: true });
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
 * Reseñas de compradores reales en la ficha de producto (prueba social,
 * Cialdini). La sección solo aparece si el producto tiene reseñas APROBADAS
 * por moderación: nunca se muestra contenido inventado ni la sección vacía.
 */
function initResenasProducto() {
  if (typeof PRODUCTO === 'undefined') return;
  const cont = document.getElementById('resenasProducto');
  if (!cont) return;

  fetch(`${EG_API_URL}/api/producto/${PRODUCTO.sku}/resenas`)
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || !data.total) return;
      const estrellas = v => '★'.repeat(v) + '☆'.repeat(5 - v);
      const esc = s => { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; };
      const items = data.resenas.slice(0, 6).map(r => `
        <div class="resena-item">
          <div class="resena-head">
            <span class="resena-stars">${estrellas(r.rating)}</span>
            ${r.nombre ? `<span class="resena-nombre">${esc(r.nombre)}</span>` : ''}
            <span class="resena-fecha">${(r.fecha || '').slice(0, 10).split('-').reverse().join('/')}</span>
          </div>
          ${r.comentario ? `<p class="resena-texto">${esc(r.comentario)}</p>` : ''}
        </div>`).join('');
      cont.innerHTML = `
        <h3>Opiniones de compradores</h3>
        <div class="resenas-promedio">
          <span class="resena-stars">${estrellas(Math.round(data.promedio))}</span>
          <strong>${data.promedio}</strong> · ${data.total} ${data.total === 1 ? 'opinión verificada' : 'opiniones verificadas'}
        </div>
        ${items}`;
      cont.style.display = 'block';
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
  banner.className = 'eg-bar';
  banner.id = 'egWelcomeBanner';
  banner.setAttribute('role', 'status');
  banner.innerHTML = '🎁 <b>10% OFF</b> en tu primera compra <span class="eg-bar-sep">·</span> se aplica solo al pagar';
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
    const codigo = ref.trim().toUpperCase();
    localStorage.setItem('eg_ref_code', codigo);
    // La visita referida es el primer paso medible del embudo de referidos:
    // registro → compartido → visita con código → compra.
    ga4SetUserProps({ referido_por: codigo });
    ga4Event('referral_visit', { ref_code: codigo, page_type: egTipoDePagina() });
  }
  const code = localStorage.getItem('eg_ref_code');
  if (!code) return;
  if (document.getElementById('egRefBanner') || document.getElementById('egComboBanner')) return;

  const tieneBienvenida = localStorage.getItem('eg_descuento_pendiente') === '1';
  const banner = document.createElement('div');
  banner.setAttribute('role', 'status');

  if (tieneBienvenida) {
    // Dos líneas explícitas: el titular con la cifra y el código, y debajo
    // el desglose. Antes era una sola frase larga en flex-wrap y en celulares
    // se cortaba en cualquier lado.
    banner.className = 'eg-bar eg-bar-combo';
    banner.id = 'egComboBanner';
    banner.innerHTML = '<div class="eg-bar-l1">Hasta <b>30% OFF</b> con tu código <span class="eg-bar-code">' + code + '</span></div>'
      + '<div class="eg-bar-l2">10% de bienvenida + hasta 20% del código · se aplican solos al pagar</div>';
  } else {
    banner.className = 'eg-bar';
    banner.id = 'egRefBanner';
    banner.innerHTML = '<div class="eg-bar-l1">Código <span class="eg-bar-code">' + code + '</span> activo: <b>hasta 20% OFF</b></div>'
      + '<div class="eg-bar-l2">Se aplica solo al pagar</div>';
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
    <span style="flex:1;min-width:0">🍪 Usamos cookies para medir el uso del sitio y, si aceptás, para publicidad. <a href="/privacidad#cookies" style="color:#FFC700;text-decoration:underline">Más info</a></span>
    <button onclick="acceptCookies()" style="background:#FFC700;color:#14151A;border:none;padding:6px 14px;border-radius:8px;font-weight:700;font-size:12px;cursor:pointer;white-space:nowrap">Aceptar</button>
    <button onclick="rejectOptionalCookies()" aria-label="Solo cookies necesarias" style="background:transparent;color:rgba(255,255,255,0.7);border:none;padding:6px 6px;font-size:12px;cursor:pointer;white-space:nowrap;text-decoration:underline">Solo necesarias</button>
  `;
  document.body.appendChild(banner);
}

function acceptCookies() {
  localStorage.setItem('eg_cookies_accepted', '1');
  localStorage.setItem('eg_cookies_decided', '1');
  document.getElementById('eg-cookie-banner')?.remove();
  ga4Consentir();
  initMetaPixel();
}

// Reabre el banner para cambiar la preferencia (link en /privacidad#cookies).
function egConfigurarCookies() {
  localStorage.removeItem('eg_cookies_decided');
  showCookieBanner();
  return false;
}

function rejectOptionalCookies() {
  localStorage.setItem('eg_cookies_accepted', '0');
  localStorage.setItem('eg_cookies_decided', '1');
  document.getElementById('eg-cookie-banner')?.remove();
  if (typeof window.gtag === 'function') {
    gtag('consent', 'update', { ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied' });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initGA4();
  if (hasConsentCookies()) {
    initMetaPixel();
  } else {
    showCookieBanner();
  }
  initItemListTracking();
  initLeadTracking();
  actualizarCarritoUI();
  initPopupRegistro();
  initOfertaYStockProducto();
  initVentasBadge();
  initResenasProducto();
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
