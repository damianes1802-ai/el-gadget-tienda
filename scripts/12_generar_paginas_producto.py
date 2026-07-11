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
from utils.seo_categorias import CATEGORIAS_SEO, COLECCIONES_SEO, slug_categoria
from utils.blog_posts import BLOG_POSTS

logger = get_logger('generar_paginas_producto')

PAGES_DIR = Config.BASE_DIR / 'pages'
PRODUCTO_DIR = PAGES_DIR / 'producto'
SITEMAP_FILE = PAGES_DIR / 'sitemap.xml'

BRAND = "El Gadget"
WHATSAPP_NUM = "5491126228481"
RELACIONADOS_LIMIT = 4
CANONICAL_DOMAIN = "https://elgadget.com.ar"  # dominio canónico fijo, no depende de SITE_URL del .env

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


def cloudinary_thumb(url: str, size: int = 150) -> str:
    """Inserta transformaciones de Cloudinary para servir una miniatura liviana
    (w×h, recorte, formato y calidad automáticos). Si no es una URL de
    Cloudinary sin transformar, la devuelve igual."""
    marcador = '/image/upload/'
    if 'res.cloudinary.com' in url and marcador in url and '/upload/w_' not in url and '/upload/c_' not in url:
        t = f'w_{size},h_{size},c_fill,f_auto,q_auto'
        return url.replace(marcador, f'{marcador}{t}/', 1)
    return url


def render_thumbnails(imagenes: list, nombre: str) -> str:
    items = []
    for i, img in enumerate(imagenes):
        activa = ' active' if i == 0 else ''
        thumb = cloudinary_thumb(img, 150)
        items.append(
            f'<img src="{html.escape(thumb)}" class="thumbnail{activa}" width="72" height="72" '
            f'loading="lazy" alt="{html.escape(nombre)}" onclick="cambiarImagen(\'{img}\', {i})">'
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
      <a href="../../categoria/{slug_categoria(categoria)}/" style="font-size:13.5px;font-weight:700;color:var(--ink);text-decoration:underline;text-underline-offset:3px;white-space:nowrap">Ver todo en {html.escape(categoria)} →</a>
    </div>
    <div class="grid" id="relatedGrid">{''.join(cards)}</div>
  </div>'''


def render_pagina(producto: dict, slug: str, site_url: str, variantes: list, relacionados: list, slug_map: dict) -> str:
    nombre = producto['nombre']
    sku = producto['sku']
    categoria = producto.get('categoria') or 'General'
    descripcion = (producto.get('descripcion') or '').strip()
    descripcion_meta = re.sub(r'\s+', ' ', descripcion).strip() or nombre
    if len(descripcion_meta) > 157:
        # cortar en límite de palabra para que la meta no termine a mitad de término
        descripcion_meta = descripcion_meta[:157].rsplit(' ', 1)[0].rstrip(',;:') + '…'
    precio = producto['precio_venta']
    imagenes = parsear_imagenes(producto)
    imagen_principal = imagenes[0] if imagenes else ''

    canonical = f"{CANONICAL_DOMAIN}/producto/{slug}/"
    titulo_pagina = f"{nombre} | {BRAND}"

    breadcrumb_producto = nombre if len(nombre) <= 40 else nombre[:40] + '…'

    stock_val = producto.get('stock') or 0
    en_stock = stock_val > 0
    if not en_stock:
        stock_badge = '<span class="stock-badge out-of-stock" id="stockBadge">✗ Agotado</span>'
    elif stock_val == 1:
        stock_badge = '<span class="stock-badge in-stock" id="stockBadge">✓ En stock</span><div class="urgency-badge" style="display:flex">⚡ ¡Última unidad disponible!</div>'
    elif stock_val <= 5:
        stock_badge = f'<span class="stock-badge in-stock" id="stockBadge">✓ En stock</span><div class="urgency-badge" style="display:flex">⚡ ¡Últimas {stock_val} unidades!</div>'
    else:
        stock_badge = '<span class="stock-badge in-stock" id="stockBadge">✓ En stock</span>'

    cat_slug = slug_categoria(categoria)
    jsonld = [{
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
    }, {
        "@context": "https://schema.org/",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{CANONICAL_DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": categoria,
             "item": f"{CANONICAL_DOMAIN}/categoria/{cat_slug}/"},
            {"@type": "ListItem", "position": 3, "name": nombre},
        ],
    }]

    main_image_html = (
        f'<img id="mainImage" class="main-image" src="{html.escape(imagen_principal)}" '
        f'alt="{html.escape(nombre)}" onclick="zoomImage()">'
        if imagen_principal else
        f'<img id="mainImage" class="main-image" src="" alt="{html.escape(nombre)}">'
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
        '__CAT_SLUG__': cat_slug,
        '__BREADCRUMB_PRODUCTO__': html.escape(breadcrumb_producto),
        '__GALLERY_CLASS__': gallery_class,
        '__CATEGORY_BADGE__': html.escape(categoria),
        '__PRODUCT_TITLE__': html.escape(nombre),
        '__PRODUCT_NAME_SHORT__': html.escape((nombre[:42] + '…') if len(nombre) > 43 else nombre),
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
  <a href="../../categoria/__CAT_SLUG__/">__BREADCRUMB_CATEGORIA__</a>
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

      <!-- Acciones -->
      <div class="actions" id="mainActions">
        <button class="btn btn-accent" onclick="agregarAlCarrito()">Agregar al pedido</button>
        <button class="btn btn-dark" onclick="comprarAhora()">Comprar ahora</button>
      </div>

      <!-- Descripción -->
      <div class="product-description">
        <h3>Descripción</h3>
        <div class="description" id="productDescription">__DESCRIPTION__</div>
      </div>

      <!-- Reseñas de compradores reales (cart.js lo puebla solo si hay aprobadas) -->
      <div class="product-resenas" id="resenasProducto" style="display:none"></div>
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

<!-- BARRA STICKY DE COMPRA (mobile): aparece al scrollear más allá del CTA
     principal, para tener siempre el precio y "Agregar" a mano (Fogg: prompt
     disponible en el pico de motivación) -->
<div class="pdp-sticky-buy" id="pdpStickyBuy" aria-hidden="true">
  <div class="pdp-sticky-info">
    <span class="pdp-sticky-name">__PRODUCT_NAME_SHORT__</span>
    <span class="pdp-sticky-price" id="pdpStickyPrice">__PRODUCT_PRICE__</span>
  </div>
  <button class="btn btn-accent" onclick="agregarAlCarrito()">Agregar</button>
</div>

<!-- TOAST -->
<div class="toast" id="toast"></div>

<script src="../../assets/js/cart.js"></script>
<script>
document.getElementById('year').textContent = new Date().getFullYear();

// Mostrar la barra sticky de compra cuando el CTA principal sale de la vista
(function () {
  var main = document.getElementById('mainActions');
  var bar = document.getElementById('pdpStickyBuy');
  if (!main || !bar || !('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (entries) {
    bar.classList.toggle('show', !entries[0].isIntersecting);
  }, { rootMargin: '0px 0px -40px 0px' });
  io.observe(main);
})();

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
    precio: (varianteActiva.precio_oferta != null && varianteActiva.precio_oferta < varianteActiva.precio_venta)
      ? varianteActiva.precio_oferta : varianteActiva.precio_venta,
    precio_lista: varianteActiva.precio_venta,
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


def _card_listado(p: dict, slug_map: dict) -> str:
    slug = slug_map.get(p['sku'])
    href = f"/producto/{slug}/" if slug else f"/producto_detalle?sku={p['sku']}"
    imagen = p.get('imagen_principal') or ''
    if imagen:
        img_html = (f'<img class="card-img" src="{html.escape(imagen)}" '
                    f'alt="{html.escape(p["nombre"])}" loading="lazy">')
    else:
        img_html = '<div class="card-img-placeholder">📦</div>'
    return f'''
      <a class="card" href="{href}" data-sku="{html.escape(p['sku'])}" data-precio="{p['precio_venta'] or 0}">
        <div class="card-img-wrap">{img_html}</div>
        <div class="card-body">
          <div class="card-cat">{html.escape(p.get('categoria') or '')}</div>
          <div class="card-name">{html.escape(p['nombre'])}</div>
          <div class="card-rating" style="display:none"></div>
          <div class="card-price">{formatear_precio(p['precio_venta'])}</div>
          <button class="card-btn" onclick="event.preventDefault();event.stopPropagation();agregarAlCarrito('{html.escape(p['sku'])}')">Agregar al pedido</button>
        </div>
      </a>'''


def render_pagina_listado(tipo: str, slug: str, cfg: dict, items: list, slug_map: dict,
                          chips: list) -> str:
    """Página estática de categoría o colección: grid de productos con <a href>
    reales (descubrimiento + autoridad interna), copy con la keyword primaria
    del research (SEO-KEYWORDS/MAPA-KEYWORDS.md) y FAQ con schema."""
    canonical = f"{CANONICAL_DOMAIN}/{tipo}/{slug}/"
    h1 = cfg['h1']
    # Posición serial: la primera fila de la grilla es el inventario de
    # atención más valioso -> ofertas activas primero (orden estable).
    items = sorted(items, key=lambda p: 0 if (p.get('precio_oferta') is not None
                   and p['precio_oferta'] < p['precio_venta']) else 1)
    cards = ''.join(_card_listado(p, slug_map) for p in items)

    chips_html = ''.join(
        f'<a href="/{t}/{s}/" class="chip{" chip-activa" if (t, s) == (tipo, slug) else ""}">{html.escape(n)}</a>'
        for t, s, n in chips
    )

    # Secciones H2 con las keywords secundarias del grupo (pueden traer links
    # internos en el texto: no se escapan, el contenido es propio y controlado)
    secciones_html = ''
    if cfg.get('secciones'):
        bloques = ''.join(
            f'<section class="listado-seccion"><h2>{html.escape(t)}</h2><p>{cuerpo}</p></section>'
            for t, cuerpo in cfg['secciones']
        )
        secciones_html = f'<div class="listado-secciones">{bloques}</div>'

    faqs_html = ''
    jsonld = [{
        "@context": "https://schema.org/",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{CANONICAL_DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": h1},
        ],
    }, {
        "@context": "https://schema.org/",
        "@type": "ItemList",
        "name": h1,
        "numberOfItems": len(items),
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": p['nombre'],
             "url": f"{CANONICAL_DOMAIN}/producto/{slug_map.get(p['sku'], '')}/"}
            for i, p in enumerate(items[:24]) if slug_map.get(p['sku'])
        ],
    }]
    if cfg.get('faqs'):
        faqs_items = ''.join(
            f'<div class="listado-faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
            for q, a in cfg['faqs']
        )
        faqs_html = f'''
  <section class="listado-faqs">
    <h2>Preguntas frecuentes</h2>
    {faqs_items}
  </section>'''
        jsonld.append({
            "@context": "https://schema.org/",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in cfg['faqs']
            ],
        })

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(cfg['title'])}</title>
<meta name="description" content="{html.escape(cfg['meta'])}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(cfg['title'])}">
<meta property="og:description" content="{html.escape(cfg['meta'])}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta name="theme-color" content="#14151A">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/style.css">
<style>
/* Hero oscuro con acento: misma identidad que la home y las landings */
.listado-hero {{ background: var(--ink); color: #fff; text-align: center; padding: 0 1.25rem 34px;
  background-image: radial-gradient(circle at 15% 20%, rgba(255,199,0,0.08), transparent 40%), radial-gradient(circle at 85% 80%, rgba(255,199,0,0.06), transparent 45%); }}
.breadcrumb-oscuro {{ max-width: 1240px; margin: 0 auto; padding: 14px 0 22px; font-size: 12.5px; color: rgba(255,255,255,0.55); display: flex; gap: 8px; justify-content: center; }}
.breadcrumb-oscuro a {{ color: rgba(255,255,255,0.8); font-weight: 600; text-decoration: none; }}
.breadcrumb-oscuro a:hover {{ color: var(--accent); }}
.breadcrumb-oscuro .sep {{ color: rgba(255,255,255,0.3); }}
.listado-badge {{ display: inline-block; background: var(--accent); color: var(--ink); font-size: 11.5px; font-weight: 800;
  text-transform: uppercase; letter-spacing: 1.5px; padding: 6px 16px; border-radius: 20px; margin-bottom: 16px; }}
.listado-hero h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: clamp(26px, 4.5vw, 40px); margin: 0 0 12px; color: #fff; }}
.listado-hero p {{ max-width: 680px; font-size: 14.5px; line-height: 1.75; color: rgba(255,255,255,0.72); margin: 0 auto; }}
.hero-trust {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 20px; font-size: 12px; font-weight: 600;
  color: rgba(255,255,255,0.65); margin-top: 20px; }}
.chips-nav {{ max-width: 1240px; margin: 18px auto 0; padding: 0 1.25rem; display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; }}
.chips-nav::-webkit-scrollbar {{ display: none; }}
@media (min-width: 1100px) {{ .chips-nav {{ flex-wrap: wrap; justify-content: center; }} }}
.chip {{ flex-shrink: 0; font-size: 12.5px; font-weight: 600; color: var(--ink); background: #fff; border: 1.5px solid var(--gray-200); border-radius: 20px; padding: 7px 14px; text-decoration: none; }}
.chip:hover {{ border-color: var(--accent); }}
.chip-activa {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
.listado-grid {{ max-width: 1240px; margin: 0 auto; padding: 20px 1.25rem 10px; }}
.orden-bar {{ max-width: 1240px; margin: 14px auto 0; padding: 0 1.25rem; display: flex; justify-content: center; align-items: center; gap: 8px; font-size: 13px; color: var(--gray-600); }}
.orden-bar select {{ padding: 8px 12px; border: 1.5px solid var(--gray-200); border-radius: 20px; font-size: 13px; font-weight: 600; color: var(--ink); background: #fff; }}
.card-rating {{ font-size: 12.5px; color: var(--accent-deep); letter-spacing: 1px; margin-bottom: 2px; }}
.card-rating small {{ color: var(--gray-400); letter-spacing: 0; }}
.terminal-cta {{ text-align: center; padding: 26px 1.25rem 6px; }}
.terminal-cta p {{ font-size: 14.5px; font-weight: 600; color: var(--gray-600); margin: 0 0 12px; }}
.terminal-cta-btns {{ display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }}
.terminal-cta .btn-outline {{ border: 1.5px solid var(--gray-200); color: var(--ink); }}
.listado-secciones {{ max-width: 820px; margin: 26px auto 0; padding: 0 1.25rem; display: grid; gap: 14px; }}
.listado-seccion {{ background: #fff; border: 1.5px solid var(--gray-200); border-radius: var(--radius); padding: 22px 24px; text-align: center; box-shadow: var(--shadow); }}
.listado-seccion h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 19px; color: var(--ink); margin: 0 0 8px; }}
.listado-seccion h2::after {{ content: ''; display: block; width: 44px; height: 4px; border-radius: 2px; background: var(--accent); margin: 10px auto 0; }}
.listado-seccion p {{ font-size: 14px; line-height: 1.75; color: var(--gray-600); margin: 0; }}
.listado-seccion a {{ color: var(--ink); font-weight: 600; }}
.listado-faqs {{ max-width: 820px; margin: 0 auto; padding: 30px 1.25rem 44px; }}
.listado-faqs h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 21px; color: var(--ink); margin: 0 0 16px; text-align: center; }}
.listado-faq-item {{ background: #fff; border: 1.5px solid var(--gray-200); border-left: 5px solid var(--accent); border-radius: var(--radius-sm); padding: 14px 18px; margin-bottom: 10px; }}
.listado-faq-item h3 {{ font-size: 14.5px; margin: 0 0 6px; color: var(--ink); }}
.listado-faq-item p {{ font-size: 13.5px; line-height: 1.7; color: var(--gray-600); margin: 0; }}
</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <a href="/" class="logo">
      <div class="logo-badge"><img src="/assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42"></div>
      <div class="logo-text">
        <div class="logo-name">El<span> Gadget</span></div>
        <div class="logo-tagline">Tienda online</div>
      </div>
    </a>
    <div class="search-desktop">
      <div class="search-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" placeholder="Buscar productos..." onkeydown="if(event.key==='Enter'){{window.location.href='/?buscar='+encodeURIComponent(this.value)}}">
      </div>
    </div>
    <a href="/carrito" class="cart-pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
      <span class="label">Mi pedido</span>
      <span class="cart-badge" id="cartBadge">0</span>
    </a>
  </div>
</header>

<div class="listado-hero">
  <div class="breadcrumb breadcrumb-oscuro">
    <a href="/">Inicio</a>
    <span class="sep">/</span>
    <span class="current">{html.escape(h1)}</span>
  </div>
  <span class="listado-badge">{'Colección' if tipo == 'coleccion' else 'Categoría'} · {len(items)} productos</span>
  <h1>{html.escape(h1)}</h1>
  <p>{html.escape(cfg['intro'])}</p>
  <div class="hero-trust">
    <span>🚚 Envíos a todo el país</span><span>🔒 Pago seguro</span><span>🔄 Cambios hasta 10 días</span><span>💬 Atención real</span>
  </div>
</div>

<nav class="chips-nav" aria-label="Categorías">{chips_html}</nav>

<div class="orden-bar">
  <label for="ordenSel">Ordenar por:</label>
  <select id="ordenSel" onchange="ordenarGrid(this.value)">
    <option value="rel">Relevancia</option>
    <option value="asc">Menor precio</option>
    <option value="desc">Mayor precio</option>
  </select>
</div>

<div class="listado-grid">
  <div class="grid" id="listadoGrid">{cards}</div>
</div>

<!-- Área terminal (Gutenberg): quien llegó al final sin decidir necesita un siguiente paso -->
<div class="terminal-cta">
  <p>¿No encontraste lo que buscabas?</p>
  <div class="terminal-cta-btns">
    <a class="btn btn-accent" href="{'/' if tipo == 'categoria' and slug == 'ofertas' else '/categoria/ofertas/'}">{'Ver todo el catálogo' if tipo == 'categoria' and slug == 'ofertas' else 'Ver las ofertas de la semana'}</a>
    <a class="btn btn-outline" href="https://wa.me/{WHATSAPP_NUM}?text=Hola!%20Busco%20un%20producto" target="_blank" rel="noopener">Preguntanos por WhatsApp</a>
  </div>
</div>
{secciones_html}
{faqs_html}

<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="logo">
        <div class="logo-badge"><img src="/assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42"></div>
        <div class="logo-text">
          <div class="logo-name">El<span> Gadget</span></div>
          <div class="logo-tagline">Tienda online</div>
        </div>
      </div>
      <p>Productos para el hogar, moda, tecnología y mucho más. Elegí tus productos, pagá online de forma segura y te lo enviamos a tu casa.</p>
    </div>
    <div class="footer-col">
      <h4>Ayuda</h4>
      <a href="/carrito">Mi pedido</a>
      <a href="/seguimiento">Seguimiento de pedido</a>
      <a href="/faq">Preguntas frecuentes</a>
      <a href="/devoluciones">Devoluciones y garantías</a>
    </div>
    <div class="footer-col">
      <h4>Información</h4>
      <a href="/sobre_nosotros">Sobre nosotros</a>
      <a href="/mayoristas">Comprar al por mayor</a>
      <a href="/referidos">Programa de referidos</a>
      <a href="/privacidad">Política de privacidad</a>
      <a href="/arrepentimiento">Botón de arrepentimiento</a>
      <a href="/terminos">Términos y condiciones</a>
    </div>
  </div>
  <div class="footer-bottom">© <span id="year"></span> El Gadget · Todos los derechos reservados</div>
</footer>

<div class="toast" id="toast"></div>
<script src="/assets/js/cart.js"></script>
<script>
document.getElementById('year').textContent = new Date().getFullYear();

// Orden por precio (client-side, el HTML estático queda intacto para SEO)
var _ordenOriginal = null;
function ordenarGrid(modo) {{
  var grid = document.getElementById('listadoGrid');
  if (!_ordenOriginal) _ordenOriginal = [].slice.call(grid.children);
  var cards = [].slice.call(grid.children);
  if (modo === 'rel') cards = _ordenOriginal.slice();
  else cards.sort(function(a, b) {{
    var d = parseFloat(a.dataset.precio) - parseFloat(b.dataset.precio);
    return modo === 'asc' ? d : -d;
  }});
  cards.forEach(function(c) {{ grid.appendChild(c); }});
}}

// Catálogo estático (CDN): pinta ofertas/stock y alimenta el botón Agregar
var _mapProds = {{}};
var _catalogoListo = fetch('/productos.json?v=' + new Date().toISOString().slice(0, 10).replace(/-/g, ''))
  .then(function(r) {{ return r.ok ? r.json() : null; }})
  .then(function(d) {{
    if (!d) return;
    var map = _mapProds;
    (d.productos || d).forEach(function(p) {{ map[p.sku] = p; }});
    document.querySelectorAll('#listadoGrid a.card[data-sku]').forEach(function(c) {{
      var p = map[c.dataset.sku];
      if (!p) return;
      if (p.precio_oferta != null && p.precio_oferta < p.precio_venta) {{
        var pct = Math.round((1 - p.precio_oferta / p.precio_venta) * 100);
        c.querySelector('.card-price').innerHTML =
          '<span style="text-decoration:line-through;color:var(--gray-400);font-size:12.5px;margin-right:6px">' +
          formatPrice(p.precio_venta) + '</span>' + formatPrice(p.precio_oferta) +
          ' <span style="color:var(--red);font-size:12px;font-weight:700">-' + pct + '%</span>';
        c.dataset.precio = p.precio_oferta;
      }}
      if (p.stock != null && p.stock > 0 && p.stock <= 5) {{
        var b = document.createElement('div');
        b.style.cssText = 'font-size:11.5px;font-weight:700;color:var(--red);margin-top:2px';
        b.textContent = p.stock === 1 ? '⚡ ¡Última unidad!' : '⚡ ¡Últimas ' + p.stock + ' unidades!';
        c.querySelector('.card-price').insertAdjacentElement('afterend', b);
      }}
    }});
  }}).catch(function() {{}});

// Agregar al pedido desde la card (usa el catálogo ya cargado; espera si hace falta)
function agregarAlCarrito(sku) {{
  _catalogoListo.then(function() {{
    var p = _mapProds[sku];
    if (!p) return;
    var oferta = p.precio_oferta != null && p.precio_oferta < p.precio_venta;
    addCartItem({{
      sku: p.sku, nombre: p.nombre,
      precio: oferta ? p.precio_oferta : p.precio_venta,
      precio_lista: p.precio_venta,
      imagen: p.imagen_principal || '', cantidad: 1
    }});
    showToast('✅ ' + p.nombre + ' agregado a tu pedido');
  }});
}}

// Ratings REALES de reseñas aprobadas (se activan solos cuando existan)
fetch(EG_API_URL + '/api/resenas/promedios')
  .then(function(r) {{ return r.ok ? r.json() : null; }})
  .then(function(d) {{
    if (!d) return;
    document.querySelectorAll('#listadoGrid a.card[data-sku]').forEach(function(c) {{
      var x = d[c.dataset.sku];
      if (!x || !x.total) return;
      var el = c.querySelector('.card-rating');
      el.innerHTML = '★'.repeat(Math.round(x.promedio)) + ' <small>' + x.promedio + ' (' + x.total + ')</small>';
      el.style.display = 'block';
    }});
  }}).catch(function() {{}});
</script>
</body>
</html>'''


def _shell_blog(titulo: str, meta: str, canonical: str, jsonld: list, hero: str, cuerpo: str) -> str:
    """Shell compartido de las páginas del blog (misma identidad que los listados)."""
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(titulo)}</title>
<meta name="description" content="{html.escape(meta)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(titulo)}">
<meta property="og:description" content="{html.escape(meta)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta name="theme-color" content="#14151A">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/style.css">
<style>
.blog-hero {{ background: var(--ink); color: #fff; text-align: center; padding: 0 1.25rem 34px;
  background-image: radial-gradient(circle at 15% 20%, rgba(255,199,0,0.08), transparent 40%), radial-gradient(circle at 85% 80%, rgba(255,199,0,0.06), transparent 45%); }}
.blog-hero .bc {{ max-width: 1240px; margin: 0 auto; padding: 14px 0 22px; font-size: 12.5px; color: rgba(255,255,255,0.55); display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }}
.blog-hero .bc a {{ color: rgba(255,255,255,0.8); font-weight: 600; text-decoration: none; }}
.blog-hero .badge {{ display: inline-block; background: var(--accent); color: var(--ink); font-size: 11.5px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; padding: 6px 16px; border-radius: 20px; margin-bottom: 16px; }}
.blog-hero h1 {{ font-family: 'Space Grotesk', sans-serif; font-size: clamp(25px, 4.2vw, 38px); margin: 0 0 12px; color: #fff; }}
.blog-hero p {{ max-width: 680px; font-size: 14.5px; line-height: 1.75; color: rgba(255,255,255,0.72); margin: 0 auto; }}
.blog-hero p strong {{ color: var(--accent); }}
.blog-fecha {{ font-size: 12px; color: rgba(255,255,255,0.45); margin-top: 14px; }}
.blog-body {{ max-width: 760px; margin: 26px auto 0; padding: 0 1.25rem; display: grid; gap: 14px; }}
.blog-body section {{ background: #fff; border: 1.5px solid var(--gray-200); border-radius: var(--radius); padding: 22px 24px; box-shadow: var(--shadow); }}
.blog-body h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 19px; color: var(--ink); margin: 0 0 10px; text-align: center; }}
.blog-body h2::after {{ content: ''; display: block; width: 44px; height: 4px; border-radius: 2px; background: var(--accent); margin: 10px auto 0; }}
.blog-body p {{ font-size: 14px; line-height: 1.8; color: var(--gray-600); margin: 0; text-align: center; }}
.blog-body a {{ color: var(--ink); font-weight: 600; }}
.blog-grid {{ max-width: 900px; margin: 26px auto 0; padding: 0 1.25rem; display: grid; gap: 14px; grid-template-columns: 1fr; }}
@media (min-width: 720px) {{ .blog-grid {{ grid-template-columns: 1fr 1fr; }} }}
.blog-card {{ background: #fff; border: 1.5px solid var(--gray-200); border-radius: var(--radius); padding: 20px 22px; text-decoration: none; box-shadow: var(--shadow); transition: border-color .15s; text-align: center; }}
.blog-card:hover {{ border-color: var(--accent); }}
.blog-card h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 16.5px; color: var(--ink); margin: 0 0 8px; }}
.blog-card p {{ font-size: 13px; line-height: 1.65; color: var(--gray-600); margin: 0; }}
.listado-faqs {{ max-width: 820px; margin: 0 auto; padding: 30px 1.25rem 44px; }}
.listado-faqs h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 21px; color: var(--ink); margin: 0 0 16px; text-align: center; }}
.listado-faq-item {{ background: #fff; border: 1.5px solid var(--gray-200); border-left: 5px solid var(--accent); border-radius: var(--radius-sm); padding: 14px 18px; margin-bottom: 10px; }}
.listado-faq-item h3 {{ font-size: 14.5px; margin: 0 0 6px; color: var(--ink); }}
.listado-faq-item p {{ font-size: 13.5px; line-height: 1.7; color: var(--gray-600); margin: 0; }}
.blog-cierre {{ max-width: 760px; margin: 10px auto 0; padding: 0 1.25rem 40px; text-align: center; }}
</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
<body>
<header class="header">
  <div class="header-inner">
    <a href="/" class="logo">
      <div class="logo-badge"><img src="/assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42"></div>
      <div class="logo-text"><div class="logo-name">El<span> Gadget</span></div><div class="logo-tagline">Tienda online</div></div>
    </a>
    <a href="/carrito" class="cart-pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/></svg>
      <span class="label">Mi pedido</span><span class="cart-badge" id="cartBadge">0</span>
    </a>
  </div>
</header>
{hero}
{cuerpo}
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="logo"><div class="logo-badge"><img src="/assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42"></div>
        <div class="logo-text"><div class="logo-name">El<span> Gadget</span></div><div class="logo-tagline">Tienda online</div></div></div>
      <p>Productos para el hogar, moda y más. Comprá online seguro y te lo enviamos a tu casa.</p>
    </div>
    <div class="footer-col"><h4>Tienda</h4><a href="/">Catálogo</a><a href="/categoria/ofertas/">Ofertas</a><a href="/blog/">Blog</a><a href="/seguimiento">Seguimiento</a></div>
    <div class="footer-col"><h4>Ayuda</h4><a href="/faq">Preguntas frecuentes</a><a href="/devoluciones">Devoluciones</a><a href="/sobre_nosotros">Sobre nosotros</a></div>
  </div>
  <div class="footer-bottom">© <span id="year"></span> El Gadget · Todos los derechos reservados</div>
</footer>
<div class="toast" id="toast"></div>
<script src="/assets/js/cart.js"></script>
<script>document.getElementById('year').textContent = new Date().getFullYear();</script>
</body>
</html>'''


def generar_blog() -> list:
    """Genera /blog/ (hub) y /blog/<slug>/ desde utils.blog_posts. Devuelve slugs."""
    blog_dir = PAGES_DIR / 'blog'
    slugs = []
    for slug, cfg in BLOG_POSTS.items():
        canonical = f"{CANONICAL_DOMAIN}/blog/{slug}/"
        jsonld = [{
            "@context": "https://schema.org/",
            "@type": "Article",
            "headline": cfg['h1'],
            "description": cfg['meta'],
            "datePublished": cfg['fecha'],
            "author": {"@type": "Organization", "name": BRAND},
            "publisher": {"@type": "Organization", "name": BRAND},
            "mainEntityOfPage": canonical,
        }, {
            "@context": "https://schema.org/",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{CANONICAL_DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{CANONICAL_DOMAIN}/blog/"},
                {"@type": "ListItem", "position": 3, "name": cfg['h1']},
            ],
        }]
        if cfg.get('faqs'):
            jsonld.append({
                "@context": "https://schema.org/", "@type": "FAQPage",
                "mainEntity": [{"@type": "Question", "name": q,
                                "acceptedAnswer": {"@type": "Answer", "text": a}}
                               for q, a in cfg['faqs']],
            })
        hero = f'''<div class="blog-hero">
  <div class="bc"><a href="/">Inicio</a><span>/</span><a href="/blog/">Blog</a><span>/</span><span>{html.escape(cfg['h1'][:42])}…</span></div>
  <span class="badge">Blog · El Gadget</span>
  <h1>{html.escape(cfg['h1'])}</h1>
  <p>{cfg['intro']}</p>
  <div class="blog-fecha">Actualizado: {cfg['fecha']}</div>
</div>'''
        secciones = ''.join(f'<section><h2>{html.escape(t)}</h2><p>{c}</p></section>'
                            for t, c in cfg['secciones'])
        faqs = ''
        if cfg.get('faqs'):
            items = ''.join(f'<div class="listado-faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
                            for q, a in cfg['faqs'])
            faqs = f'<div class="listado-faqs"><h2>Preguntas frecuentes</h2>{items}</div>'
        cierre = ('<div class="blog-cierre"><a class="btn btn-accent" href="/" '
                  'style="display:inline-block">Ver el catálogo completo →</a></div>')
        cuerpo = f'<div class="blog-body">{secciones}</div>{faqs}{cierre}'
        destino = blog_dir / slug
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'index.html').write_text(
            _shell_blog(cfg['title'], cfg['meta'], canonical, jsonld, hero, cuerpo), encoding='utf-8')
        slugs.append(slug)

    # Hub /blog/
    canonical = f"{CANONICAL_DOMAIN}/blog/"
    jsonld = [{"@context": "https://schema.org/", "@type": "Blog", "name": f"Blog de {BRAND}",
               "url": canonical}]
    hero = '''<div class="blog-hero">
  <div class="bc"><a href="/">Inicio</a><span>/</span><span>Blog</span></div>
  <span class="badge">Blog · El Gadget</span>
  <h1>Ideas, guías y trucos para tu casa</h1>
  <p>Organización, deco, regalos y vida diaria: contenido útil, sin humo, escrito para resolver.</p>
</div>'''
    cards = ''.join(
        f'''<a class="blog-card" href="/blog/{s}/"><h2>{html.escape(c['h1'])}</h2><p>{html.escape(re.sub("<[^>]+>", "", c['intro'])[:130])}…</p></a>'''
        for s, c in BLOG_POSTS.items())
    cuerpo = f'<div class="blog-grid">{cards}</div><div class="blog-cierre" style="padding-top:30px"><a class="btn btn-accent" href="/" style="display:inline-block">Ir a la tienda →</a></div>'
    blog_dir.mkdir(parents=True, exist_ok=True)
    (blog_dir / 'index.html').write_text(
        _shell_blog(f'Blog de {BRAND} — Ideas y guías para tu casa',
                    'Guías de organización, deco, regalos y hogar: contenido práctico del equipo de El Gadget, con envío a todo el país.',
                    canonical, jsonld, hero, cuerpo), encoding='utf-8')
    return slugs


def generar_listados(productos: list, slug_map: dict) -> tuple:
    """Genera /categoria/<slug>/ y /coleccion/<slug>/. Devuelve (slugs_cat, slugs_col)."""
    por_slug_cat = {}
    for p in productos:
        por_slug_cat.setdefault(slug_categoria(p.get('categoria') or ''), []).append(p)

    chips = [('categoria', s, CATEGORIAS_SEO[s]['h1']) for s in CATEGORIAS_SEO if s in por_slug_cat]
    chips += [('coleccion', s, c['h1']) for s, c in COLECCIONES_SEO.items()]

    cat_dir = PAGES_DIR / 'categoria'
    slugs_cat = []
    for s, cfg in CATEGORIAS_SEO.items():
        items = por_slug_cat.get(s) or []
        if not items:
            continue
        destino = cat_dir / s
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'index.html').write_text(
            render_pagina_listado('categoria', s, cfg, items, slug_map, chips), encoding='utf-8')
        slugs_cat.append(s)

    col_dir = PAGES_DIR / 'coleccion'
    slugs_col = []
    for s, cfg in COLECCIONES_SEO.items():
        rx = re.compile(cfg['match'], re.I)
        items = [p for p in productos if rx.search(p['nombre'])]
        if len(items) < 3:
            continue
        destino = col_dir / s
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'index.html').write_text(
            render_pagina_listado('coleccion', s, cfg, items, slug_map, chips), encoding='utf-8')
        slugs_col.append(s)

    return slugs_cat, slugs_col


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
        # Rotación por posición: cada producto linkea a sus 4 vecinos SIGUIENTES
        # en la categoría (con vuelta). Así todos reciben ~4 in-links, en vez de
        # concentrar todos los links en los primeros 4 de la categoría (SEO).
        cat_lista = por_categoria.get(categoria, [])
        vecinos = [r for r in cat_lista if r['sku'] != sku]
        if vecinos:
            idx = next((i for i, r in enumerate(cat_lista) if r['sku'] == sku), 0)
            relacionados = [vecinos[(idx + k) % len(vecinos)]
                            for k in range(min(RELACIONADOS_LIMIT, len(vecinos)))]
        else:
            relacionados = []

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

    # 4b. Páginas de categoría y colección (arquitectura SEO: home -> listado -> producto)
    slugs_cat, slugs_col = generar_listados(productos, slug_map)
    print(f"✅ {len(slugs_cat)} páginas de categoría y {len(slugs_col)} de colección generadas")

    # 4c. Blog (contenido informacional que alimenta a las categorías)
    slugs_blog = generar_blog()
    print(f"✅ Blog: hub + {len(slugs_blog)} posts generados")

    # 5. Generar sitemap.xml
    hoy = date.today().isoformat()
    canonical_url = CANONICAL_DOMAIN
    static_pages = [
        (f"{canonical_url}/", "weekly"),
        (f"{canonical_url}/faq", "monthly"),
        (f"{canonical_url}/sobre_nosotros", "monthly"),
        (f"{canonical_url}/arrepentimiento", "monthly"),
        (f"{canonical_url}/seguimiento", "monthly"),
        (f"{canonical_url}/privacidad", "monthly"),
        (f"{canonical_url}/devoluciones", "monthly"),
        (f"{canonical_url}/terminos", "monthly"),
        (f"{canonical_url}/referidos", "weekly"),
        (f"{canonical_url}/mayoristas", "monthly"),
    ]
    # Landings /ganar/ desde el filesystem (la lista hardcodeada dejaba afuera
    # a las landings nuevas). panel-preview es una página soporte: no se indexa.
    ganar_dir = PAGES_DIR / 'ganar'
    if ganar_dir.exists():
        static_pages.append((f"{canonical_url}/ganar/", "monthly"))
        for d in sorted(ganar_dir.iterdir()):
            if d.is_dir() and d.name != 'panel-preview' and (d / 'index.html').exists():
                static_pages.append((f"{canonical_url}/ganar/{d.name}/", "monthly"))
    static_pages += [(f"{canonical_url}/categoria/{s}/", "weekly") for s in slugs_cat]
    static_pages += [(f"{canonical_url}/coleccion/{s}/", "weekly") for s in slugs_col]
    static_pages.append((f"{canonical_url}/blog/", "weekly"))
    static_pages += [(f"{canonical_url}/blog/{s}/", "monthly") for s in slugs_blog]
    urls = [(f"{canonical_url}/producto/{slug}/", "weekly") for slug in sorted(slugs_generados)]
    all_urls = static_pages + urls

    sitemap_items = '\n'.join(
        f"  <url><loc>{html.escape(u)}</loc><lastmod>{hoy}</lastmod><changefreq>{freq}</changefreq></url>"
        for u, freq in all_urls
    )
    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{sitemap_items}\n"
        '</urlset>\n'
    )
    SITEMAP_FILE.write_text(sitemap_xml, encoding='utf-8')
    print(f"✅ Sitemap generado: {SITEMAP_FILE} ({len(all_urls)} URLs, dominio: {canonical_url})")

    # 6. Catálogo estático (pages/productos.json): mismo shape que GET
    # /api/productos, servido gratis por el CDN de GitHub Pages. El frontend lo
    # usa como primera fuente y solo cae a la API si falla. Como este script
    # corre en la sync diaria (03-04 AM) y también al redeploy manual de
    # precios, los precios de oferta del día ya vienen calculados acá con la
    # MISMA lógica compartida que usa la API (utils/campanas.py).
    from utils.campanas import campanas_programadas_vigentes, calcular_precio_oferta
    cur_json = conn.cursor()
    cur_json.execute("SELECT * FROM productos WHERE stock > 0 ORDER BY nombre")
    filas_catalogo = [dict(r) for r in cur_json.fetchall()]
    campanas = campanas_programadas_vigentes(cur_json)
    for p in filas_catalogo:
        p["precio_oferta"] = calcular_precio_oferta(p, campanas)
    catalogo_file = PAGES_DIR / 'productos.json'
    catalogo_file.write_text(
        json.dumps(filas_catalogo, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8'
    )
    print(f"✅ Catálogo estático: {catalogo_file} ({len(filas_catalogo)} productos)")

    conn.close()
    print("\n" + "=" * 70 + "\n")
    logger.info(f"Páginas de producto generadas: {len(slugs_generados)}, eliminadas: {eliminadas}")
    return 0


if __name__ == "__main__":
    sys.exit(generar())
