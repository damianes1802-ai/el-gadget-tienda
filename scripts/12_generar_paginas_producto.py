#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERADOR DE PÁGINAS ESTÁTICAS DE PRODUCTO (SEO)

Genera pages/producto/<slug>/index.html para cada producto disponible en
data/catalogo.db: una página con meta tags (title, description, canonical,
Open Graph) y datos estructurados (JSON-LD Product), con el contenido del
producto ya escrito en el HTML, para que los buscadores indexen el título,
la descripción, el precio y las imágenes reales sin depender de JavaScript.

También:
- Guarda el slug calculado en productos.url_amigable (data/catalogo.db).
- Genera pages/sitemap.xml con todas las páginas de producto y las páginas
  principales del sitio.
- Elimina carpetas pages/producto/<slug>/ de productos que ya no están
  disponibles en el catálogo, para no dejar páginas huérfanas indexadas.

USO:
    python 12_generar_paginas_producto.py

AUTOR: Sistema Ecommerce Automation
"""

import html
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('generar_paginas_producto')

PAGES_DIR = Config.BASE_DIR / 'pages'
PRODUCTO_DIR = PAGES_DIR / 'producto'
SITEMAP_FILE = PAGES_DIR / 'sitemap.xml'

BRAND = "El Gadget"
WHATSAPP_NUM = "5491126228481"
RELACIONADOS_LIMIT = 4

LOGO_SVG = '<img src="../../assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42">'

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<rect width='100' height='100' rx='22' fill='%2314151A'/>"
           "<rect x='14' y='34' width='72' height='34' rx='17' fill='none' stroke='white' stroke-width='7'/>"
           "<circle cx='34' cy='51' r='6' fill='white'/>"
           "<rect x='58' y='42' width='6' height='18' rx='2' fill='%23FFC700'/>"
           "<rect x='68' y='36' width='6' height='30' rx='2' fill='%23FFC700'/>"
           "<rect x='78' y='45' width='6' height='12' rx='2' fill='%23FFC700'/></svg>")

WHATSAPP_ICON = ('<svg viewBox="0 0 32 32" width="28" height="28" fill="#fff" xmlns="http://www.w3.org/2000/svg">'
                 '<path d="M16.04 2.67C8.7 2.67 2.74 8.62 2.74 15.96c0 2.62.73 5.14 2.1 7.33L2 29.33l6.2-1.79a13.2 13.2 0 0 0 7.84 2.42h.01c7.34 0 13.3-5.95 13.3-13.29 0-3.55-1.39-6.89-3.9-9.4a13.2 13.2 0 0 0-9.4-3.9zm0 24.34h-.01a11 11 0 0 1-5.6-1.53l-.4-.24-4.16 1.2 1.21-4.05-.26-.42a10.96 10.96 0 0 1-1.68-5.86c0-6.07 4.94-11.01 11.02-11.01a10.96 10.96 0 0 1 7.79 3.23 10.96 10.96 0 0 1 3.22 7.8c0 6.08-4.95 11.02-11.13 11.02zm6.04-8.25c-.33-.17-1.96-.97-2.27-1.08-.3-.11-.52-.17-.74.17-.22.33-.85 1.07-1.04 1.29-.19.22-.38.24-.7.08-1.9-.95-3.15-1.7-4.4-3.84-.33-.58.33-.54.95-1.79.1-.22.05-.4-.05-.57-.1-.17-.66-1.6-.91-2.18-.24-.58-.49-.5-.68-.5-.17 0-.37 0-.57.01-.2 0-.51.07-.78.37-.27.3-1.04 1.02-1.04 2.47s1.07 2.87 1.22 3.08c.15.2 2.05 3.18 5.07 4.4 2.51 1.01 3.02.83 3.57.77.55-.06 1.79-.73 2.04-1.45.25-.71.25-1.32.17-1.45-.07-.13-.27-.2-.54-.34z"/></svg>')


def slugify(texto: str) -> str:
    """Convierte un texto a slug ascii en minúsculas separado por guiones"""
    texto = unicodedata.normalize('NFKD', texto or '')
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = texto.lower()
    texto = re.sub(r'[^a-z0-9]+', '-', texto)
    texto = texto.strip('-')
    texto = re.sub(r'-{2,}', '-', texto)
    return texto


def construir_slug(nombre: str, sku: str) -> str:
    """Slug SEO-friendly: nombre del producto + SKU como sufijo único/estable"""
    base = slugify(nombre)[:70].strip('-')
    sufijo = slugify(sku) or 'producto'
    if not base:
        return sufijo
    return f"{base}-{sufijo}"


def formatear_precio(valor) -> str:
    """Formato de precio estilo es-AR: $12.345"""
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0
    return '$' + f"{n:,.0f}".replace(',', '.')


def parsear_imagenes(producto: dict) -> list:
    imagenes = []
    if producto.get('imagen_principal'):
        imagenes.append(producto['imagen_principal'])
    adicionales = producto.get('imagenes_adicionales') or ''
    for img in adicionales.replace('\n', ',').split(','):
        img = img.strip()
        if img:
            imagenes.append(img)
    return imagenes


def render_thumbnails(imagenes: list, nombre: str) -> str:
    items = []
    for i, img in enumerate(imagenes):
        activa = ' active' if i == 0 else ''
        items.append(
            f'<img src="{html.escape(img)}" class="thumbnail{activa}" '
            f'alt="{html.escape(nombre)}" onclick="cambiarImagen(\'{img}\', {i})">'
        )
    return '<div class="thumbnails-wrap"><div class="thumbnails" id="thumbnails">' + ''.join(items) + '</div></div>'


def etiqueta_variante(p: dict) -> str:
    return ' - '.join(filter(None, [p.get('color'), p.get('talle')])) or p.get('nombre') or p.get('sku')


def render_variantes(producto: dict, variantes: list) -> str:
    if variantes:
        opciones = [f'<option value="{html.escape(producto["sku"])}" selected>{html.escape(etiqueta_variante(producto))}</option>']
        for var in variantes:
            opciones.append(
                f'<option value="{html.escape(var["sku"])}">{html.escape(etiqueta_variante(var))}</option>'
            )

        return f'''
      <div class="variants-section" id="variantsSection">
        <label class="variant-label">Variantes disponibles</label>
        <select class="variant-select" id="variantSelect" onchange="cambiarVariante(this.value)">{''.join(opciones)}</select>
      </div>'''

    variantes_internas = json.loads(producto.get('variantes_internas') or '[]')
    if variantes_internas:
        etiqueta = variantes_internas[0].get('etiqueta_atributo') or 'Variantes disponibles'
        opciones = ''.join(
            f'<option value="{html.escape(v["valor"])}">{html.escape(v["valor"])}</option>'
            for v in variantes_internas
        )
        disabled = ' disabled' if len(variantes_internas) < 2 else ''

        return f'''
      <div class="variants-section" id="internalVariantsSection">
        <label class="variant-label">{html.escape(etiqueta)}</label>
        <select class="variant-select" id="internalVariantSelect" onchange="cambiarVarianteInterna(this.value)"{disabled}>{opciones}</select>
      </div>'''

    return ''


def render_relacionados(relacionados: list, categoria: str, slug_map: dict) -> str:
    if not relacionados:
        return ''

    cards = []
    for p in relacionados:
        slug = slug_map.get(p['sku'])
        href = f"../{slug}/" if slug else f"../../producto_detalle?sku={p['sku']}"
        imagen = p.get('imagen_principal') or ''
        if imagen:
            img_html = (f'<img class="card-img" src="{html.escape(imagen)}" '
                        f'alt="{html.escape(p["nombre"])}" loading="lazy">')
        else:
            img_html = '<div class="card-img-placeholder">📦</div>'

        cards.append(f'''
          <a class="card" href="{html.escape(href)}">
            <div class="card-img-wrap">{img_html}</div>
            <div class="card-body">
              <div class="card-cat">{html.escape(p.get('categoria') or categoria or '')}</div>
              <div class="card-name">{html.escape(p['nombre'])}</div>
              <div class="card-price">{formatear_precio(p['precio_venta'])}</div>
            </div>
          </a>''')

    return f'''
  <div class="related-section" id="relatedSection">
    <div class="grid-heading">
      <h2>Productos relacionados</h2>
    </div>
    <div class="grid" id="relatedGrid">{''.join(cards)}</div>
  </div>'''


def render_pagina(producto: dict, slug: str, site_url: str, variantes: list, relacionados: list, slug_map: dict) -> str:
    nombre = producto['nombre']
    sku = producto['sku']
    categoria = producto.get('categoria') or 'General'
    descripcion = (producto.get('descripcion') or '').strip()
    descripcion_meta = re.sub(r'\s+', ' ', descripcion).strip()[:160] or nombre
    precio = producto['precio_venta']
    imagenes = parsear_imagenes(producto)
    imagen_principal = imagenes[0] if imagenes else ''

    canonical = f"{site_url}/producto/{slug}/"
    titulo_pagina = f"{nombre} | {BRAND}"

    breadcrumb_producto = nombre if len(nombre) <= 40 else nombre[:40] + '…'

    en_stock = (producto.get('stock') or 0) > 0
    stock_badge = (
        '<span class="stock-badge in-stock" id="stockBadge">✓ En stock</span>'
        if en_stock else
        '<span class="stock-badge out-of-stock" id="stockBadge">✗ Agotado</span>'
    )

    jsonld = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": nombre,
        "image": imagenes,
        "description": descripcion_meta,
        "sku": sku,
        "brand": {"@type": "Brand", "name": BRAND},
        "offers": {
            "@type": "Offer",
            "url": canonical,
            "priceCurrency": "ARS",
            "price": f"{float(precio or 0):.2f}",
            "availability": "https://schema.org/InStock" if en_stock else "https://schema.org/OutOfStock",
        },
    }

    main_image_html = (
        f'<img id="mainImage" class="main-image" src="{html.escape(imagen_principal)}" '
        f'alt="{html.escape(nombre)}" onclick="zoomImage()">'
        if imagen_principal else
        '<img id="mainImage" class="main-image" src="" alt="">'
    ) + (
        '<button class="gallery-arrow gallery-arrow-prev" onclick="galeriaAnterior()" '
        'aria-label="Imagen anterior" type="button">‹</button>'
        '<button class="gallery-arrow gallery-arrow-next" onclick="galeriaSiguiente()" '
        'aria-label="Imagen siguiente" type="button">›</button>'
    )

    gallery_class = 'gallery' if len(imagenes) > 1 else 'gallery single-image'

    producto_js = {
        "sku": sku,
        "nombre": nombre,
        "precio_venta": precio,
        "stock": producto.get('stock') or 0,
        "color": producto.get('color') or '',
        "talle": producto.get('talle') or '',
        "descripcion": descripcion,
        "imagenes": imagenes,
        "variantes_internas": json.loads(producto.get('variantes_internas') or '[]'),
        "variantes": [
            {
                "sku": v['sku'],
                "nombre": v['nombre'],
                "precio_venta": v['precio_venta'],
                "stock": v.get('stock') or 0,
                "color": v.get('color') or '',
                "talle": v.get('talle') or '',
                "descripcion": (v.get('descripcion') or '').strip(),
                "imagenes": parsear_imagenes(v),
                "url": f"../{slug_map[v['sku']]}/",
            }
            for v in variantes
        ],
    }

    html_doc = TEMPLATE
    reemplazos = {
        '__TITLE__': html.escape(titulo_pagina),
        '__META_DESC__': html.escape(descripcion_meta),
        '__CANONICAL__': html.escape(canonical),
        '__OG_IMAGE__': html.escape(imagen_principal),
        '__FAVICON__': FAVICON,
        '__LOGO_SVG__': LOGO_SVG,
        '__WHATSAPP_ICON__': WHATSAPP_ICON,
        '__WHATSAPP_NUM__': WHATSAPP_NUM,
        '__JSONLD__': json.dumps(jsonld, ensure_ascii=False),
        '__BREADCRUMB_CATEGORIA__': html.escape(categoria),
        '__BREADCRUMB_PRODUCTO__': html.escape(breadcrumb_producto),
        '__GALLERY_CLASS__': gallery_class,
        '__CATEGORY_BADGE__': html.escape(categoria),
        '__PRODUCT_TITLE__': html.escape(nombre),
        '__PRODUCT_PRICE__': formatear_precio(precio),
        '__PRODUCT_SKU__': html.escape(sku),
        '__STOCK_BADGE__': stock_badge,
        '__MAIN_IMAGE__': main_image_html,
        '__THUMBNAILS__': render_thumbnails(imagenes, nombre),
        '__DESCRIPTION__': html.escape(descripcion or 'Sin descripción disponible.'),
        '__VARIANTS__': render_variantes(producto, variantes),
        '__RELATED__': render_relacionados(relacionados, categoria, slug_map),
        '__PRODUCTO_JSON__': json.dumps(producto_js, ensure_ascii=False),
    }

    for token, valor in reemplazos.items():
        html_doc = html_doc.replace(token, str(valor))

    return html_doc


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<meta name="description" content="__META_DESC__">
<link rel="canonical" href="__CANONICAL__">
<meta property="og:type" content="product">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__META_DESC__">
<meta property="og:url" content="__CANONICAL__">
<meta property="og:image" content="__OG_IMAGE__">
<meta name="theme-color" content="#14151A">
<link rel="icon" type="image/svg+xml" href="__FAVICON__">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../../assets/css/style.css">
<script type="application/ld+json">__JSONLD__</script>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="header-inner">
    <a href="../../" class="logo">
      <div class="logo-badge">
        __LOGO_SVG__
      </div>
      <div class="logo-text">
        <div class="logo-name">El<span> Gadget</span></div>
        <div class="logo-tagline">Tienda online</div>
      </div>
    </a>
    <div class="search-desktop">
      <div class="search-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" placeholder="Buscar productos..." onkeydown="if(event.key==='Enter'){window.location.href='../../?buscar='+encodeURIComponent(this.value)}">
      </div>
    </div>
    <a href="../../carrito" class="cart-pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
      </svg>
      <span class="label">Mi pedido</span>
      <span class="cart-badge" id="cartBadge">0</span>
    </a>
  </div>
</header>

<!-- BREADCRUMB -->
<div class="breadcrumb">
  <a href="../../">Inicio</a>
  <span class="sep">/</span>
  <span class="current">__BREADCRUMB_CATEGORIA__</span>
  <span class="sep">/</span>
  <span class="current">__BREADCRUMB_PRODUCTO__</span>
</div>

<!-- CONTENIDO -->
<div class="product-wrap" id="productWrap">
  <div class="product-grid">
    <!-- Galería -->
    <div class="__GALLERY_CLASS__" id="gallery">
      <div class="main-image-wrap">
        __MAIN_IMAGE__
      </div>
      __THUMBNAILS__
    </div>

    <!-- Información -->
    <div class="product-info">
      <span class="product-cat-badge">__CATEGORY_BADGE__</span>
      <h1 class="product-title" id="productTitle">__PRODUCT_TITLE__</h1>
      <div>
        <div class="product-price" id="productPrice">__PRODUCT_PRICE__</div>
        <div class="product-sku" id="productSku">SKU: __PRODUCT_SKU__</div>
      </div>
      __STOCK_BADGE__
      __VARIANTS__

      <!-- Descripción -->
      <div class="product-description">
        <h3>Descripción</h3>
        <div class="description" id="productDescription">__DESCRIPTION__</div>
      </div>

      <!-- Acciones -->
      <div class="actions">
        <button class="btn btn-accent" onclick="agregarAlCarrito()">Agregar al pedido</button>
        <button class="btn btn-dark" onclick="comprarAhora()">Comprar ahora</button>
      </div>
    </div>
  </div>
__RELATED__
</div>

<!-- FOOTER -->
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="logo">
        <div class="logo-badge">
          __LOGO_SVG__
        </div>
        <div class="logo-text">
          <div class="logo-name">El<span> Gadget</span></div>
          <div class="logo-tagline">Tienda online</div>
        </div>
      </div>
      <p>Productos para el hogar, moda, tecnología y mucho más. Elegí tus productos, pagá online de forma segura y te lo enviamos a tu casa.</p>
    </div>
    <div class="footer-col">
      <h4>Ayuda</h4>
      <a href="../../carrito">Mi pedido</a>
      <a href="../../seguimiento">Seguimiento de pedido</a>
      <a href="../../faq">Preguntas frecuentes</a>
      <a href="https://wa.me/__WHATSAPP_NUM__?text=Hola!%20Tengo%20una%20consulta" target="_blank" rel="noopener">Hablar por WhatsApp</a>
    </div>
    <div class="footer-col">
      <h4>Información</h4>
      <a href="../../sobre_nosotros">Sobre nosotros</a>
      <a href="#" onclick="return false;">Envíos a todo el país</a>
      <a href="#" onclick="return false;">Pagos seguros</a>
      <a href="../../arrepentimiento">Botón de arrepentimiento</a>
    </div>
  </div>
  <div class="footer-bottom">© <span id="year"></span> El Gadget · Todos los derechos reservados</div>
</footer>

<!-- WHATSAPP FLOTANTE -->
<a href="https://wa.me/__WHATSAPP_NUM__?text=Hola!%20Tengo%20una%20consulta" class="whatsapp-float" target="_blank" rel="noopener" aria-label="Contactar por WhatsApp" title="Contactanos por WhatsApp">
  __WHATSAPP_ICON__
</a>

<!-- CARRITO BAR -->
<div class="cart-bar" id="cartBar">
  <div class="cart-bar-info">
    <div class="cart-bar-count" id="cartBarCount">0</div>
    <div class="cart-bar-text">Tu pedido<strong id="cartBarTotal">$0</strong></div>
  </div>
  <a class="cart-bar-btn" href="../../carrito">Ver pedido</a>
</div>

<!-- TOAST -->
<div class="toast" id="toast"></div>

<script src="../../assets/js/cart.js"></script>
<script>
document.getElementById('year').textContent = new Date().getFullYear();

const PRODUCTO = __PRODUCTO_JSON__;
let varianteActiva = PRODUCTO;
const opcionesVariantes = [PRODUCTO, ...(PRODUCTO.variantes || [])];

let imagenesActuales = PRODUCTO.imagenes || [];
let imagenIndexActual = 0;

function cambiarImagen(src, index) {
  document.getElementById('mainImage').src = src;
  imagenIndexActual = index;
  document.querySelectorAll('.thumbnail').forEach((thumb, i) => {
    thumb.classList.toggle('active', i === index);
    if (i === index) {
      const cont = thumb.parentElement;
      cont.scrollTo({ left: thumb.offsetLeft - (cont.clientWidth - thumb.clientWidth) / 2, behavior: 'smooth' });
    }
  });
}

function galeriaAnterior() {
  if (imagenesActuales.length < 2) return;
  const nuevo = (imagenIndexActual - 1 + imagenesActuales.length) % imagenesActuales.length;
  cambiarImagen(imagenesActuales[nuevo], nuevo);
}

function galeriaSiguiente() {
  if (imagenesActuales.length < 2) return;
  const nuevo = (imagenIndexActual + 1) % imagenesActuales.length;
  cambiarImagen(imagenesActuales[nuevo], nuevo);
}

// Swipe táctil en la imagen principal
(function initSwipeGaleria() {
  const wrap = document.querySelector('.main-image-wrap');
  if (!wrap) return;
  let touchStartX = 0;
  wrap.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
  wrap.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 40) {
      if (dx < 0) galeriaSiguiente(); else galeriaAnterior();
    }
  }, { passive: true });
})();

function zoomImage() {
  const img = document.getElementById('mainImage');
  if (img.src) window.open(img.src, '_blank');
}

// Renderiza la imagen principal y las miniaturas para la variante seleccionada
function renderImagenes(imagenes, nombre) {
  const main = document.getElementById('mainImage');
  if (!imagenes || !imagenes.length) return;

  imagenesActuales = imagenes;
  imagenIndexActual = 0;
  main.src = imagenes[0];
  main.alt = nombre;

  document.getElementById('gallery').classList.toggle('single-image', imagenes.length <= 1);

  const thumbsHtml = imagenes.map((img, i) =>
    `<img src="${img}" class="thumbnail${i === 0 ? ' active' : ''}" alt="${nombre}" onclick="cambiarImagen('${img}', ${i})">`
  ).join('');

  const thumbsContainer = document.getElementById('thumbnails');
  if (thumbsContainer) thumbsContainer.innerHTML = thumbsHtml;
}

// Cambiar la variante seleccionada (color/talle): actualiza precio, stock, SKU e imágenes
function cambiarVariante(sku) {
  const variante = opcionesVariantes.find(v => v.sku === sku);
  if (!variante) return;

  varianteActiva = variante;

  document.getElementById('productPrice').textContent = formatPrice(variante.precio_venta);
  document.getElementById('productSku').textContent = `SKU: ${variante.sku}`;

  const stockBadge = document.getElementById('stockBadge');
  if (variante.stock > 0) {
    stockBadge.className = 'stock-badge in-stock';
    stockBadge.textContent = '✓ En stock';
  } else {
    stockBadge.className = 'stock-badge out-of-stock';
    stockBadge.textContent = '✗ Agotado';
  }

  if (variante.imagenes && variante.imagenes.length > 0) {
    renderImagenes(variante.imagenes, variante.nombre);
  }

  if (variante.descripcion) {
    document.getElementById('productDescription').textContent = variante.descripcion;
  }

  if (variante.url) {
    history.replaceState(null, '', variante.url);
  }
}

// Cambiar variante interna seleccionada: solo cambia la galería de imágenes
function cambiarVarianteInterna(valor) {
  const variante = (PRODUCTO.variantes_internas || []).find(v => v.valor === valor);
  if (!variante) return;

  if (variante.imagenes && variante.imagenes.length > 0) {
    renderImagenes(variante.imagenes, PRODUCTO.nombre);
  }
}

function agregarAlCarrito() {
  if (varianteActiva.stock <= 0) {
    showToast('❌ Producto agotado');
    return;
  }

  addCartItem({
    sku: varianteActiva.sku,
    nombre: varianteActiva.nombre,
    precio: varianteActiva.precio_venta,
    imagen: (varianteActiva.imagenes && varianteActiva.imagenes[0]) || '',
    color: varianteActiva.color || '',
    talle: varianteActiva.talle || '',
    cantidad: 1
  });
  showToast(`✅ ${varianteActiva.nombre} agregado a tu pedido`);
}

function comprarAhora() {
  agregarAlCarrito();
  window.location.href = '../../carrito';
}
</script>
</body>
</html>
"""


def cargar_productos(conn) -> list:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM productos
        WHERE stock > 0 AND precio_venta > 0
        ORDER BY sku
    """)
    return [dict(row) for row in cursor.fetchall()]


def generar():
    print("\n" + "=" * 70)
    print("🌐 GENERADOR DE PÁGINAS ESTÁTICAS DE PRODUCTO (SEO)")
    print("=" * 70 + "\n")

    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'http://localhost:5500').rstrip('/')

    db_path = Config.DATA_DIR / 'catalogo.db'
    if not db_path.exists():
        print(f"❌ No se encontró la base de datos: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    productos = cargar_productos(conn)
    if not productos:
        print("⚠️  No hay productos disponibles para generar páginas")
        conn.close()
        return 1

    # 1. Calcular slugs y guardarlos en productos.url_amigable
    slug_map = {}
    slugs_usados = set()
    for p in productos:
        slug = construir_slug(p['nombre'], p['sku'])
        if slug in slugs_usados:
            slug = f"{slug}-{slugify(p['sku'])}-2"
        slugs_usados.add(slug)
        slug_map[p['sku']] = slug

    cursor = conn.cursor()
    cursor.executemany(
        "UPDATE productos SET url_amigable = ? WHERE sku = ?",
        [(slug, sku) for sku, slug in slug_map.items()]
    )
    conn.commit()

    # 2. Agrupar por categoría e item_group_id para relacionados/variantes
    por_categoria = {}
    por_grupo = {}
    for p in productos:
        por_categoria.setdefault(p.get('categoria') or '', []).append(p)
        grupo = p.get('item_group_id') or ''
        if grupo:
            por_grupo.setdefault(grupo, []).append(p)

    # 3. Generar página por producto
    PRODUCTO_DIR.mkdir(parents=True, exist_ok=True)
    slugs_generados = set()

    for p in productos:
        sku = p['sku']
        slug = slug_map[sku]
        slugs_generados.add(slug)

        grupo = p.get('item_group_id') or ''
        variantes = [v for v in por_grupo.get(grupo, []) if v['sku'] != sku] if grupo else []

        categoria = p.get('categoria') or ''
        relacionados = [
            r for r in por_categoria.get(categoria, [])
            if r['sku'] != sku
        ][:RELACIONADOS_LIMIT]

        contenido = render_pagina(p, slug, site_url, variantes, relacionados, slug_map)

        destino_dir = PRODUCTO_DIR / slug
        destino_dir.mkdir(parents=True, exist_ok=True)
        (destino_dir / 'index.html').write_text(contenido, encoding='utf-8')

    print(f"✅ {len(slugs_generados)} páginas de producto generadas en {PRODUCTO_DIR}")

    # 4. Eliminar carpetas de productos que ya no están disponibles
    eliminadas = 0
    if PRODUCTO_DIR.exists():
        for carpeta in PRODUCTO_DIR.iterdir():
            if carpeta.is_dir() and carpeta.name not in slugs_generados:
                shutil.rmtree(carpeta)
                eliminadas += 1

    if eliminadas:
        print(f"🗑️  {eliminadas} páginas de producto descontinuadas eliminadas")

    # 5. Generar sitemap.xml
    hoy = date.today().isoformat()
    urls = [
        f"{site_url}/",
        f"{site_url}/carrito",
        f"{site_url}/faq",
        f"{site_url}/sobre_nosotros",
        f"{site_url}/arrepentimiento",
        f"{site_url}/seguimiento",
    ]
    urls += [f"{site_url}/producto/{slug}/" for slug in sorted(slugs_generados)]

    sitemap_items = '\n'.join(
        f"  <url><loc>{html.escape(u)}</loc><lastmod>{hoy}</lastmod></url>"
        for u in urls
    )
    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{sitemap_items}\n"
        '</urlset>\n'
    )
    SITEMAP_FILE.write_text(sitemap_xml, encoding='utf-8')
    print(f"✅ Sitemap generado: {SITEMAP_FILE} ({len(urls)} URLs)")

    conn.close()
    print("\n" + "=" * 70 + "\n")
    logger.info(f"Páginas de producto generadas: {len(slugs_generados)}, eliminadas: {eliminadas}")
    return 0


if __name__ == "__main__":
    sys.exit(generar())
