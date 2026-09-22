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
- Conserva la ficha de los productos AGOTADOS (badge, sin compra, JSON-LD
  OutOfStock, alternativas en stock) en vez de borrarla: la URL no da 404 y
  al reingresar recupera la misma posición. Pasados AGOTADO_DIAS_MAX días, la
  ficha pasa a un stub noindex + refresh a su categoría y sale del sitemap.
  Estado por SKU (slug congelado, nombre, agotado_desde): data/fichas_producto.json.

USO:
    python 12_generar_paginas_producto.py

AUTOR: Sistema Ecommerce Automation
"""

import hashlib
import html
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger
from utils.seo_categorias import CATEGORIAS_SEO, COLECCIONES_SEO, slug_categoria, resolver_categoria
from utils.blog_posts import BLOG_POSTS

logger = get_logger('generar_paginas_producto')

PAGES_DIR = Config.BASE_DIR / 'pages'
PRODUCTO_DIR = PAGES_DIR / 'producto'
SITEMAP_FILE = PAGES_DIR / 'sitemap.xml'
# Estado URL -> (hash de contenido, lastmod) para que el sitemap solo declare
# "cambió" cuando la página cambió DE VERDAD (señal lastmod confiable para Google).
LASTMOD_STATE_FILE = Config.BASE_DIR / 'data' / 'sitemap_lastmod.json'
# Slugs viejos de producto -> SKU, para redirigirlos a la URL actual (versionado)
REDIRECTS_FILE = Config.BASE_DIR / 'data' / 'redirects_producto.json'
# Estado de fichas por SKU (versionado): slug congelado + último nombre + desde
# cuándo está agotado. Es la memoria que sobrevive al borrado de la fila en
# catalogo.db (11_ borra los agotados en cada sync): con esto la ficha de un
# agotado sigue publicada (badge + alternativas, OutOfStock) en vez de dar 404,
# y al reingresar recupera la MISMA URL (posición ganada, sin volver a cero).
FICHAS_STATE_FILE = Config.BASE_DIR / 'data' / 'fichas_producto.json'
# Fuente de datos de un agotado (ya no está en la base): data/productos/<SKU>/metadata.json
METADATA_DIR = Config.PRODUCTOS_DIR
# Más de N días agotado -> la ficha pasa a stub noindex + refresh a su categoría
# y sale del sitemap. Mientras tanto sigue indexable (Google: mantener la URL
# viva con OutOfStock conserva la posición cuando el producto vuelve).
AGOTADO_DIAS_MAX = 90

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


def _archivo_de_url(url: str) -> Path:
    """Resuelve una URL del sitemap al archivo HTML que sirve GitHub Pages."""
    path = url.replace(CANONICAL_DOMAIN, '', 1).strip('/')
    if not path:
        return PAGES_DIR / 'index.html'
    if url.endswith('/'):
        return PAGES_DIR / path / 'index.html'
    return PAGES_DIR / f"{path}.html"


def _calcular_lastmods(all_urls) -> dict:
    """lastmod honesto por URL: conserva la fecha guardada mientras el contenido
    (hash SHA-256, con CRLF normalizado) no cambie; si cambió o es nueva, hoy.
    Así el sitemap solo declara "modificado" ante cambios reales y Google puede
    confiar en la señal. El estado vive en data/sitemap_lastmod.json (versionado)."""
    hoy = date.today().isoformat()
    try:
        estado = json.loads(LASTMOD_STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        estado = {}
    nuevo = {}
    for u, _freq in all_urls:
        try:
            contenido = _archivo_de_url(u).read_bytes().replace(b'\r', b'')
            h = hashlib.sha256(contenido).hexdigest()[:16]
        except OSError:
            h = ''
        prev = estado.get(u)
        if h and prev and prev.get('hash') == h:
            nuevo[u] = {'hash': h, 'lastmod': prev['lastmod']}
        else:
            nuevo[u] = {'hash': h, 'lastmod': hoy}
    LASTMOD_STATE_FILE.write_text(
        json.dumps(nuevo, ensure_ascii=False, indent=0, sort_keys=True) + '\n',
        encoding='utf-8')
    return {u: v['lastmod'] for u, v in nuevo.items()}


# ── Fichas agotadas: estado por SKU, datos desde metadata.json ─────────────

def cargar_fichas_state() -> dict:
    """{sku: {'slug', 'nombre', 'precio', 'agotado_desde'?}} — ver FICHAS_STATE_FILE."""
    try:
        estado = json.loads(FICHAS_STATE_FILE.read_text(encoding='utf-8'))
        return estado if isinstance(estado, dict) else {}
    except (OSError, ValueError):
        return {}


def guardar_fichas_state(estado: dict) -> None:
    FICHAS_STATE_FILE.write_text(
        json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def leer_metadata(sku: str) -> dict:
    """metadata.json del producto (fuente de un agotado que ya no está en la base). {} si no hay."""
    f = METADATA_DIR / sku / 'metadata.json'
    try:
        m = json.loads(f.read_text(encoding='utf-8'))
        return m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        return {}


def listar_skus_con_metadata() -> list:
    if not METADATA_DIR.exists():
        return []
    return sorted(d.name for d in METADATA_DIR.iterdir() if d.is_dir() and (d / 'metadata.json').exists())


def producto_desde_metadata(sku: str, meta: dict, nombre_previo: str = '') -> dict:
    """Arma un dict con la misma forma que una fila de `productos` a partir de
    data/productos/<SKU>/metadata.json (mismo mapeo que 11_sincronizar_sqlite).
    `nombre_previo` es el último nombre publicado (puede venir reescrito por el
    SEO mensual): se prefiere sobre el título crudo del proveedor para que la
    ficha agotada no cambie de título respecto de lo que Google ya indexó."""
    imagenes = meta.get('imagenes_cloudinary') or meta.get('imagenes') or []
    precio = meta.get('precio_venta') or 0
    if not precio and isinstance(meta.get('calculo_precio'), dict):
        precio = meta['calculo_precio'].get('precio_final') or 0
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        precio = 0.0
    return {
        'sku': sku,
        'nombre': (nombre_previo or meta.get('titulo') or sku).strip(),
        'descripcion': meta.get('descripcion') or '',
        'precio_venta': precio,
        'stock': 0,
        'categoria': meta.get('categoria_principal') or meta.get('categoria') or 'General',
        'imagen_principal': imagenes[0] if imagenes else '',
        'imagenes_adicionales': ','.join(imagenes[1:]),
        'item_group_id': meta.get('item_group_id') or '',
        'variantes_internas': json.dumps(meta.get('variantes_internas') or [], ensure_ascii=False),
        'color': '', 'talle': '',
    }


def sku_de_ficha_existente(carpeta: Path) -> str:
    """SKU que sirve una carpeta pages/producto/<slug>/ ya publicada (leyendo el
    HTML), o '' si no es una ficha (stub de redirección, carpeta vacía). Es el
    último recurso para no perder la URL de un producto que quedó fuera de la
    base antes de que existiera el registro de fichas."""
    try:
        contenido = (carpeta / 'index.html').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    if 'http-equiv="refresh"' in contenido:
        return ''
    m = re.search(r'id="productSku">SKU: ([^<]+)<', contenido)
    return html.unescape(m.group(1)).strip() if m else ''


def nombre_de_ficha_existente(carpeta: Path) -> str:
    try:
        contenido = (carpeta / 'index.html').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''
    m = re.search(r'<h1 class="product-title" id="productTitle">([^<]*)</h1>', contenido)
    return html.unescape(m.group(1)).strip() if m else ''


def fecha_agotado_de_metadata(meta: dict) -> str:
    """'YYYY-MM-DD' de metadata.fecha_agotado (la escribe 17_deteccion_agotados_robusto), o ''."""
    f = (meta.get('fecha_agotado') or '')[:10]
    try:
        date.fromisoformat(f)
        return f
    except ValueError:
        return ''


def elegir_alternativas(sku: str, grupo: str, categoria: str, por_grupo: dict, por_categoria: dict,
                        productos: list) -> list:
    """Hasta RELACIONADOS_LIMIT productos EN STOCK para la ficha de un agotado:
    primero el mismo item_group_id (otro color/talle del mismo producto),
    después la misma categoría, y si no alcanza, el catálogo general. La
    elección es determinística (hash del SKU) para que la página no cambie de
    contenido en cada corrida sin motivo."""
    elegidos, vistos = [], {sku}

    def _sumar(lista):
        if not lista:
            return
        n = len(lista)
        base = int(hashlib.md5(sku.encode()).hexdigest(), 16) % n
        for k in range(n):
            if len(elegidos) >= RELACIONADOS_LIMIT:
                return
            p = lista[(base + k) % n]
            if p['sku'] not in vistos:
                vistos.add(p['sku'])
                elegidos.append(p)

    if grupo:
        _sumar(por_grupo.get(grupo, []))
    _sumar(por_categoria.get(categoria, []))
    _sumar(productos)
    return elegidos


def render_stub_agotado(slug: str, categoria: str) -> str:
    """Ficha de un producto agotado hace más de AGOTADO_DIAS_MAX días: noindex +
    canonical y meta refresh a su categoría (mismo patrón que los stubs de
    redirección de slugs viejos; GitHub Pages no tiene redirecciones de
    servidor). Sale del sitemap, pero la URL no da 404 y la carpeta se conserva:
    si el producto reingresa, vuelve a ser la ficha completa en la misma URL."""
    url = f"{CANONICAL_DOMAIN}/categoria/{slug_categoria(categoria)}/"
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        f'<title>Producto no disponible | {BRAND}</title>'
        f'<link rel="canonical" href="{html.escape(url)}">'
        f'<meta http-equiv="refresh" content="0;url={html.escape(url)}">'
        '<meta name="robots" content="noindex">'
        f'<script>location.replace({json.dumps(url)});</script>'
        f'</head><body><p>Este producto ya no está disponible. Te llevamos a '
        f'<a href="{html.escape(url)}">{html.escape(categoria)}</a>.</p></body></html>\n'
    )


def cloudinary_thumb(url: str, size: int = 150) -> str:
    """Inserta transformaciones de Cloudinary para servir una miniatura liviana
    (w×h, recorte, formato y calidad automáticos). Si no es una URL de
    Cloudinary sin transformar, la devuelve igual."""
    marcador = '/image/upload/'
    if 'res.cloudinary.com' in url and marcador in url and '/upload/w_' not in url and '/upload/c_' not in url:
        t = f'w_{size},h_{size},c_fill,f_auto,q_auto'
        return url.replace(marcador, f'{marcador}{t}/', 1)
    return url


def cloudinary_social(url: str) -> str:
    """Imagen para previews de WhatsApp / Facebook / X (og:image). Las
    originales son PNG de ~1 MB y 800x1200: WhatsApp no muestra miniatura si
    la imagen pesa más de ~300 KB. JPG cuadrado 1080x1080 con el producto
    entero sobre fondo blanco (c_pad), ~60-100 KB."""
    marcador = '/image/upload/'
    if 'res.cloudinary.com' in url and marcador in url and '/upload/w_' not in url and '/upload/c_' not in url:
        t = 'w_1080,h_1080,c_pad,b_white,f_jpg,q_auto:good'
        return url.replace(marcador, f'{marcador}{t}/', 1)
    return url


def cloudinary_main(url: str, w: int = 800) -> str:
    """Imagen principal del PDP: limita el ancho (preserva aspecto) + WebP/calidad
    auto. Mucho más liviana que la original full-res; la original queda disponible
    en data-full para el zoom."""
    marcador = '/image/upload/'
    if 'res.cloudinary.com' in url and marcador in url and '/upload/w_' not in url and '/upload/c_' not in url:
        return url.replace(marcador, f'{marcador}w_{w},c_limit,f_auto,q_auto/', 1)
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


def _normalizar_desc(s: str) -> str:
    """Purga artefactos de formateo de las descripciones (por si el optimizador IA
    reintroduce literales): \\n / \\r / \\t escapados -> reales, quita markdown **,
    y normaliza espacios. El contenedor .description usa white-space:pre-wrap, así
    que los newlines reales se renderizan como saltos de línea."""
    s = (s or '').strip()
    if not s:
        return s
    s = s.replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\r', '\n').replace('\\t', ' ')
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s).replace('**', '')
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'[ \t]{2,}', ' ', s)
    return s.strip()


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


def render_relacionados(relacionados: list, categoria: str, slug_map: dict,
                        titulo: str = 'Productos relacionados', intro: str = '') -> str:
    if not relacionados:
        return ''

    cards = []
    for p in relacionados:
        slug = slug_map.get(p['sku'])
        href = f"../{slug}/" if slug else f"../../producto_detalle?sku={p['sku']}"
        imagen = p.get('imagen_principal') or ''
        if imagen:
            img_html = (f'<img class="card-img" src="{html.escape(cloudinary_thumb(imagen, 400))}" '
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

    intro_html = f'\n    <p class="related-intro">{html.escape(intro)}</p>' if intro else ''
    return f'''
  <div class="related-section" id="relatedSection">
    <div class="grid-heading">
      <h2>{html.escape(titulo)}</h2>
      <a href="../../categoria/{slug_categoria(categoria)}/" style="font-size:13.5px;font-weight:700;color:var(--ink);text-decoration:underline;text-underline-offset:3px;white-space:nowrap">Ver todo en {html.escape(categoria)} →</a>
    </div>{intro_html}
    <div class="grid" id="relatedGrid">{''.join(cards)}</div>
  </div>'''


def render_pagina(producto: dict, slug: str, site_url: str, variantes: list, relacionados: list, slug_map: dict,
                  agotado: bool = False) -> str:
    """Ficha completa. Con `agotado=True` (producto fuera de la base o con
    stock 0): misma URL/título/galería, badge "Agotado", sin botones de compra
    (CTA "Avisame cuando vuelva" por WhatsApp), JSON-LD OutOfStock y
    `relacionados` se muestra como "Alternativas disponibles"."""
    nombre = producto['nombre']
    sku = producto['sku']
    categoria = producto.get('categoria') or 'General'
    descripcion = _normalizar_desc(producto.get('descripcion'))
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

    stock_val = 0 if agotado else (producto.get('stock') or 0)
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
    if not en_stock and float(precio or 0) <= 0:
        # agotado sin precio conocido: no declarar "$0.00" (señal falsa); OutOfStock alcanza
        jsonld[0]['offers'].pop('price', None)

    main_image_html = (
        f'<img id="mainImage" class="main-image" src="{html.escape(cloudinary_main(imagen_principal))}" '
        f'data-full="{html.escape(imagen_principal)}" fetchpriority="high" '
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

    # CTA principal + barra sticky (mobile). Agotado: sin compra; el botón pasa
    # a "Avisame cuando vuelva" (WhatsApp con mensaje prearmado; cart.js lo
    # registra solo como generate_lead con el SKU) + atajo a las alternativas.
    if not en_stock:
        aviso_txt = f"Hola! Quiero que me avisen cuando vuelva a estar disponible: {nombre} (SKU {sku})"
        wa_aviso = f"https://wa.me/{WHATSAPP_NUM}?text={quote(aviso_txt)}"
        precio_visible = formatear_precio(precio) if float(precio or 0) > 0 else 'Precio no disponible'
        acciones_html = (
            f'<div class="agotado-notice" role="status"><strong>Este producto está agotado por el momento.</strong> '
            f'Pedí que te avisemos cuando vuelva o elegí una alternativa disponible más abajo.</div>\n'
            f'      <div class="actions actions-agotado" id="mainActions">\n'
            f'        <a class="btn btn-accent" href="{html.escape(wa_aviso)}" target="_blank" rel="noopener">Avisame cuando vuelva</a>\n'
            f'        <a class="btn btn-dark" href="#relatedSection">Ver alternativas</a>\n'
            f'      </div>')
        sticky_cta = f'<a class="btn btn-accent" href="{html.escape(wa_aviso)}" target="_blank" rel="noopener">Avisame</a>'
        sticky_precio = '<span style="color:var(--red)">Agotado</span>'
        related_html = render_relacionados(
            relacionados, categoria, slug_map, titulo='Alternativas disponibles',
            intro='Estos productos sí están disponibles ahora, con envío a todo el país.')
    else:
        precio_visible = formatear_precio(precio)
        acciones_html = (
            '<div class="actions" id="mainActions">\n'
            '        <button class="btn btn-accent" onclick="agregarAlCarrito()">Agregar al pedido</button>\n'
            '        <button class="btn btn-dark" onclick="comprarAhora()">Comprar ahora</button>\n'
            '    <button class="ref-share-cta" id="refShareCta" type="button" onclick="compartirComoReferido()"></button>\n'
            '      </div>')
        sticky_cta = '<button class="btn btn-accent" onclick="agregarAlCarrito()">Agregar</button>'
        sticky_precio = formatear_precio(precio)
        related_html = render_relacionados(relacionados, categoria, slug_map)

    producto_js = {
        "sku": sku,
        "nombre": nombre,
        "precio_venta": precio,
        "stock": stock_val,
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
        '__OG_IMAGE__': html.escape(cloudinary_social(imagen_principal)),
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
        '__PRODUCT_PRICE__': precio_visible,
        '__PRODUCT_SKU__': html.escape(sku),
        '__STOCK_BADGE__': stock_badge,
        '__MAIN_IMAGE__': main_image_html,
        '__THUMBNAILS__': render_thumbnails(imagenes, nombre),
        '__DESCRIPTION__': html.escape(descripcion or 'Sin descripción disponible.'),
        '__VARIANTS__': render_variantes(producto, variantes),
        '__ACTIONS__': acciones_html,
        '__STICKY_PRICE__': sticky_precio,
        '__STICKY_CTA__': sticky_cta,
        '__RELATED__': related_html,
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
<meta property="og:image:secure_url" content="__OG_IMAGE__">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1080">
<meta property="og:image:height" content="1080">
<meta property="og:site_name" content="El Gadget">
<meta property="og:locale" content="es_AR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="__META_DESC__">
<meta name="twitter:image" content="__OG_IMAGE__">
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
      __ACTIONS__

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
  <div class="footer-legal">
    <strong>El Gadget</strong> &middot; Dami&aacute;n Ezequiel S&aacute;nchez &middot; CUIT 20-42396477-5 &middot; Responsable Monotributo<br>
    Esteban Echeverr&iacute;a 964, Wilde (B1875ATT), Provincia de Buenos Aires, Argentina<br>
    <a href="mailto:tienda@elgadget.com.ar">tienda@elgadget.com.ar</a> &middot; <a href="https://wa.me/5491126228481" target="_blank" rel="noopener">WhatsApp +54 9 11 2622-8481</a> &middot; <a href="/contacto">Contacto</a>
  </div>
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
    <span class="pdp-sticky-price" id="pdpStickyPrice">__STICKY_PRICE__</span>
  </div>
  __STICKY_CTA__
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

function cldMain(u){ return (u && u.includes('res.cloudinary.com') && u.includes('/image/upload/') && !u.includes('/upload/w_') && !u.includes('/upload/c_')) ? u.replace('/image/upload/','/image/upload/w_800,c_limit,f_auto,q_auto/') : u; }
function cambiarImagen(src, index) {
  const mi = document.getElementById('mainImage');
  mi.src = cldMain(src); mi.dataset.full = src;
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


// ── Referidos: "Comparti y gana $X" con la comision real de este producto ──
let _refCta = null;
async function cargarCtaReferido() {
  const token = localStorage.getItem('eg_token');
  const btn = document.getElementById('refShareCta');
  if (!token || !btn) return;
  try {
    const res = await fetch(EG_API_URL + '/api/referidos/comision/' + encodeURIComponent(varianteActiva.sku), { headers: { 'Authorization': 'Bearer ' + token } });
    if (!res.ok) return;           // no es referido, o sesion vencida: no se muestra nada
    _refCta = await res.json();
    btn.innerHTML = 'Compartí y ganá <span style="font-size:17px">' + formatPrice(_refCta.comision_ars) + '</span>'
      + '<small>Tu referido paga ' + formatPrice(_refCta.precio_con_descuento) + ' (−' + _refCta.descuento_pct + '%) · vos cobrás el ' + _refCta.tier_pct + '%</small>';
    btn.classList.add('visible');
  } catch (e) { /* silencioso: la ficha funciona igual sin esto */ }
}
function compartirComoReferido() {
  if (!_refCta) return;
  if (typeof ga4Event === 'function') ga4Event('share', { method: navigator.share ? 'nativo' : 'whatsapp', content_type: 'producto_ficha', item_id: _refCta.sku });
  const link = _refCta.url + '?ref=' + encodeURIComponent(_refCta.codigo) + '&utm_source=whatsapp&utm_medium=referral&utm_campaign=ficha_share';
  // Corto a propósito: la vista previa del link ya muestra nombre y foto.
  const texto = _refCta.descuento_pct + '% OFF en este producto de El Gadget: ' + formatPrice(_refCta.precio_venta) + ' → *' + formatPrice(_refCta.precio_con_descuento) + '*'
    + '\\n\\nComprá con el descuento desde este link (se aplica solo):\\n' + link;
  if (navigator.share) { navigator.share({ title: 'El Gadget', text: texto }).catch(function () {}); return; }
  window.open('https://wa.me/?text=' + encodeURIComponent(texto), '_blank', 'noopener');
}

function zoomImage() {
  // Antes abria la URL de Cloudinary en otra pestana: el usuario se iba del
  // sitio por error al tocar la imagen. Ahora agranda ACA, con navegacion.
  let lb = document.getElementById('lightbox');
  if (!lb) {
    lb = document.createElement('div');
    lb.id = 'lightbox'; lb.className = 'lightbox'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-label', 'Imagen ampliada');
    lb.innerHTML = '<button class="lightbox-close" aria-label="Cerrar" type="button">×</button>'
      + '<button class="gallery-arrow gallery-arrow-prev" aria-label="Imagen anterior" type="button">‹</button>'
      + '<img alt="">'
      + '<button class="gallery-arrow gallery-arrow-next" aria-label="Imagen siguiente" type="button">›</button>'
      + '<div class="lightbox-count"></div>';
    document.body.appendChild(lb);
    lb.querySelector('.lightbox-close').onclick = cerrarLightbox;
    lb.querySelector('.gallery-arrow-prev').onclick = function (e) { e.stopPropagation(); galeriaAnterior(); actualizarLightbox(); };
    lb.querySelector('.gallery-arrow-next').onclick = function (e) { e.stopPropagation(); galeriaSiguiente(); actualizarLightbox(); };
    lb.addEventListener('click', function (e) { if (e.target === lb) cerrarLightbox(); });
    document.addEventListener('keydown', function (e) {
      if (!lb.classList.contains('open')) return;
      if (e.key === 'Escape') cerrarLightbox();
      if (e.key === 'ArrowLeft') { galeriaAnterior(); actualizarLightbox(); }
      if (e.key === 'ArrowRight') { galeriaSiguiente(); actualizarLightbox(); }
    });
    activarSwipe(lb, function () { galeriaSiguiente(); actualizarLightbox(); }, function () { galeriaAnterior(); actualizarLightbox(); });
  }
  actualizarLightbox();
  lb.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function actualizarLightbox() {
  const lb = document.getElementById('lightbox');
  const main = document.getElementById('mainImage');
  if (!lb || !main) return;
  lb.querySelector('img').src = main.dataset.full || main.src;
  lb.querySelector('img').alt = main.alt || '';
  const n = (imagenesActuales || []).length;
  lb.querySelector('.lightbox-count').textContent = n > 1 ? (imagenIndexActual + 1) + ' / ' + n : '';
  lb.querySelectorAll('.gallery-arrow').forEach(function (b) { b.style.display = n > 1 ? '' : 'none'; });
}
function cerrarLightbox() {
  const lb = document.getElementById('lightbox');
  if (lb) lb.classList.remove('open');
  document.body.style.overflow = '';
}
// Swipe horizontal (mobile): deslizar cambia de imagen, como en cualquier app
function activarSwipe(el, onLeft, onRight) {
  let x0 = null, y0 = null;
  el.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
  el.addEventListener('touchend', function (e) {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
    x0 = y0 = null;
    if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy) * 1.5) { if (dx < 0) onLeft(); else onRight(); }
  }, { passive: true });
}

// Renderiza la imagen principal y las miniaturas para la variante seleccionada
function renderImagenes(imagenes, nombre) {
  const main = document.getElementById('mainImage');
  if (!imagenes || !imagenes.length) return;

  imagenesActuales = imagenes;
  imagenIndexActual = 0;
  main.src = cldMain(imagenes[0]); main.dataset.full = imagenes[0];
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
  cargarCtaReferido();
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

// IMG6: si el visitante es un referido logueado, mostrar cuanto gana con ESTE producto
cargarCtaReferido();
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


def cargar_agotados_db(conn) -> list:
    """Filas que siguen en la base pero no se venden (stock 0 —p. ej. apagado a
    mano desde el panel— o sin precio): su ficha se publica como agotada."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM productos
        WHERE NOT (stock > 0 AND precio_venta > 0)
        ORDER BY sku
    """)
    return [dict(row) for row in cursor.fetchall()]


def _card_listado(p: dict, slug_map: dict) -> str:
    slug = slug_map.get(p['sku'])
    href = f"/producto/{slug}/" if slug else f"/producto_detalle?sku={p['sku']}"
    imagen = p.get('imagen_principal') or ''
    if imagen:
        img_html = (f'<img class="card-img" src="{html.escape(cloudinary_thumb(imagen, 400))}" '
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

    if cfg.get('grupos'):
        # Colección agrupada por keyword: H2 por grupo (SEO) + accesos directos
        # tipo chips (como las categorías de la home). Sin "Ordenar por": el
        # orden categórico ES el orden de la página.
        restantes = list(items)
        grupos_render = []
        for gid, titulo, patron in cfg['grupos']:
            rg = re.compile(patron, re.I)
            del_grupo = [p for p in restantes if rg.search(p['nombre'])]
            restantes = [p for p in restantes if not rg.search(p['nombre'])]
            if del_grupo:
                grupos_render.append((gid, titulo, del_grupo))
        atajos = ''.join(f'<a href="#g-{gid}" class="chip">{html.escape(t)} ({len(g)})</a>'
                         for gid, t, g in grupos_render)
        bloques = ''.join(
            f'''<div class="grupo-sep" id="g-{gid}"><h2>{html.escape(t)} <span class="gcount">{len(g)}</span></h2></div>
  <div class="grid">{''.join(_card_listado(p, slug_map) for p in g)}</div>'''
            for gid, t, g in grupos_render)
        cuerpo_grid = f'''<nav class="chips-nav subcats-nav" aria-label="Secciones de la colección">{atajos}</nav>

<div class="listado-grid" id="listadoGrid">
  {bloques}
</div>'''
    else:
        cards = ''.join(_card_listado(p, slug_map) for p in items)
        cuerpo_grid = f'''<div class="orden-bar">
  <label for="ordenSel">Ordenar por:</label>
  <select id="ordenSel" onchange="ordenarGrid(this.value)">
    <option value="rel">Relevancia</option>
    <option value="asc">Menor precio</option>
    <option value="desc">Mayor precio</option>
  </select>
</div>

<div class="listado-grid">
  <div class="grid" id="listadoGrid">{cards}</div>
</div>'''

    # Dos desplegables (Categorías / Colecciones) en lugar de la fila de 18
    # chips: misma data, sin ruido visual. Los links quedan en el HTML (SEO).
    def _panel(t_filtro):
        return ''.join(f'<a href="/{t}/{s}/">{html.escape(n)}</a>'
                       for t, s, n in chips if t == t_filtro)
    chips_html = f'''<details class="mn-item"><summary>Categorías</summary><div class="mn-panel">{_panel('categoria')}</div></details>
  <details class="mn-item"><summary>Colecciones</summary><div class="mn-panel">{_panel('coleccion')}</div></details>'''

    # Secciones H2 con las keywords secundarias del grupo (pueden traer links
    # internos en el texto: no se escapan, el contenido es propio y controlado)
    secciones_html = ''
    if cfg.get('secciones'):
        bloques = ''.join(
            f'<section class="listado-seccion"><h2>{html.escape(t)}</h2><p>{cuerpo}</p></section>'
            for t, cuerpo in cfg['secciones']
        )
        secciones_html = f'<div class="listado-secciones">{bloques}</div>'

    guias = GUIAS_LISTADO.get(slug, [])
    guias_html = ''
    if guias:
        links_g = ''.join(f'<a href="/blog/{g}/">{html.escape(t)} →</a>' for g, t in guias)
        guias_html = (f'<div class="listado-guias"><h2>Guías relacionadas</h2>{links_g}</div>')

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
.subcats-nav {{ margin-top: 12px; }}
.subcats-nav .chip {{ border-color: var(--accent); font-weight: 700; }}
.listado-nav {{ padding-top: 16px; }}
.listado-nav .mn-item:last-child {{ grid-column: auto; }}
/* Separador de grupo: línea + píldora oscura = fin de una sección e inicio
   de la siguiente, legible de un vistazo sin invadir. */
.grupo-sep {{ display: flex; align-items: center; gap: 14px; margin: 36px 0 14px; scroll-margin-top: 96px; }}
.grupo-sep::before, .grupo-sep::after {{ content: ''; flex: 1; height: 2px; border-radius: 1px;
  background: linear-gradient(90deg, transparent, var(--gray-200)); }}
.grupo-sep::after {{ background: linear-gradient(90deg, var(--gray-200), transparent); }}
.grupo-sep h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 16.5px; font-weight: 700; color: #fff;
  background: var(--ink); border-radius: 24px; padding: 11px 22px; margin: 0; display: flex;
  align-items: center; gap: 9px; box-shadow: var(--shadow); white-space: nowrap; }}
.grupo-sep .gcount {{ background: var(--accent); color: var(--ink); font-size: 12px; font-weight: 800;
  border-radius: 12px; padding: 2px 9px; }}
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
.listado-guias {{ max-width: 760px; margin: 0 auto; padding: 4px 1.25rem 40px; text-align: center; }}
.listado-guias h2 {{ font-family: 'Space Grotesk', sans-serif; font-size: 17px; color: var(--ink); margin: 0 0 10px; }}
.listado-guias a {{ display: inline-block; margin: 4px 8px; font-size: 13.5px; font-weight: 600; color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }}
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

<div class="listado-hero" style="background-image:linear-gradient(rgba(20,21,26,0.72),rgba(20,21,26,0.9)),url(/assets/img/hero-{tipo}-{slug}.jpg);background-size:cover;background-position:center">
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

<nav class="mega-nav listado-nav" aria-label="Navegación del catálogo">
  {chips_html}
</nav>

{cuerpo_grid}
<script>
document.querySelectorAll('.listado-nav details').forEach(function(d) {{
  d.addEventListener('toggle', function() {{
    if (d.open) document.querySelectorAll('.listado-nav details[open]').forEach(function(o) {{ if (o !== d) o.open = false; }});
  }});
}});
document.addEventListener('click', function(e) {{
  if (!e.target.closest('.listado-nav')) document.querySelectorAll('.listado-nav details[open]').forEach(function(o) {{ o.open = false; }});
}});
</script>

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
{guias_html}

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
  <div class="footer-legal">
    <strong>El Gadget</strong> &middot; Dami&aacute;n Ezequiel S&aacute;nchez &middot; CUIT 20-42396477-5 &middot; Responsable Monotributo<br>
    Esteban Echeverr&iacute;a 964, Wilde (B1875ATT), Provincia de Buenos Aires, Argentina<br>
    <a href="mailto:tienda@elgadget.com.ar">tienda@elgadget.com.ar</a> &middot; <a href="https://wa.me/5491126228481" target="_blank" rel="noopener">WhatsApp +54 9 11 2622-8481</a> &middot; <a href="/contacto">Contacto</a>
  </div>
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


def _shell_blog(titulo: str, meta: str, canonical: str, jsonld: list, hero: str, cuerpo: str,
                og_img: str = '') -> str:
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
{f'<meta property="og:image" content="{og_img}">' if og_img else ''}
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
.blog-prod {{ max-width: 270px; margin: 18px auto 0; text-align: left; }}
.blog-cierre {{ max-width: 760px; margin: 10px auto 0; padding: 0 1.25rem 40px; text-align: center; }}
.blog-img-hero {{ max-width: 860px; margin: -18px auto 0; padding: 0 1.25rem; position: relative; z-index: 2; }}
.blog-img-hero img {{ width: 100%; height: auto; border-radius: var(--radius); box-shadow: 0 14px 34px rgba(20,21,26,0.18); display: block; }}
.blog-toc nav {{ display: flex; flex-direction: column; gap: 6px; }}
.blog-toc nav a {{ font-size: 13.5px; font-weight: 600; color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }}
.blog-body section {{ scroll-margin-top: 96px; }}
.blog-body section img {{ width: 100%; height: auto; border-radius: var(--radius-sm); margin-bottom: 16px; display: block; }}
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
  <div class="footer-legal">
    <strong>El Gadget</strong> &middot; Dami&aacute;n Ezequiel S&aacute;nchez &middot; CUIT 20-42396477-5 &middot; Responsable Monotributo<br>
    Esteban Echeverr&iacute;a 964, Wilde (B1875ATT), Provincia de Buenos Aires, Argentina<br>
    <a href="mailto:tienda@elgadget.com.ar">tienda@elgadget.com.ar</a> &middot; <a href="https://wa.me/5491126228481" target="_blank" rel="noopener">WhatsApp +54 9 11 2622-8481</a> &middot; <a href="/contacto">Contacto</a>
  </div>
</footer>
<div class="toast" id="toast"></div>
<script src="/assets/js/cart.js"></script>
<script>document.getElementById('year').textContent = new Date().getFullYear();</script>
</body>
</html>'''


# Interlinking editorial: posts relacionados entre si y guias por listado
# (auditoria de grafo jul-2026: los posts tenian 1 solo in-link, el hub).
BLOG_RELACIONADOS = {
    'mewing': ['como-reducir-la-papada', 'como-mejorar-la-postura'],
    'como-reducir-la-papada': ['como-mejorar-la-postura', 'mewing'],
    'como-mejorar-la-postura': ['como-reducir-la-papada', 'como-dejar-de-roncar'],
    'como-dejar-de-roncar': ['como-mejorar-la-postura', 'mewing'],
    'regalos-de-navidad': ['dia-del-amigo', 'regalos-originales-para-mujeres'],
    'hot-sale-cyber-monday-black-friday': ['dia-del-amigo', 'regalos-originales-para-mujeres'],
    'como-curar-el-mate': ['como-limpiar-termo-acero-inoxidable', 'regalos-originales-para-hombres'],
    'dia-del-amigo': ['regalos-originales-para-hombres', 'regalos-originales-para-mujeres'],
    'regalos-dia-de-la-madre': ['regalos-originales-para-mujeres', 'dia-del-amigo'],
    'regalos-originales-para-mujeres': ['regalos-dia-de-la-madre', 'regalos-originales-para-hombres'],
    'regalos-originales-para-hombres': ['regalos-originales-para-mujeres', 'regalos-dia-de-la-madre'],
    'como-organizar-el-placard': ['como-organizar-una-cocina-pequena', 'ideas-para-decorar-una-habitacion'],
    'como-organizar-una-cocina-pequena': ['como-organizar-el-placard', 'como-limpiar-termo-acero-inoxidable'],
    'ideas-para-decorar-una-habitacion': ['como-organizar-el-placard', 'regalos-originales-para-mujeres'],
    'como-sacar-pelos-de-mascota-de-la-ropa': ['como-limpiar-termo-acero-inoxidable', 'como-organizar-una-cocina-pequena'],
    'como-limpiar-termo-acero-inoxidable': ['como-curar-el-mate', 'como-organizar-una-cocina-pequena'],
}
GUIAS_LISTADO = {
    'fitness': [('mewing', 'Mewing: qué es y si realmente funciona'), ('como-reducir-la-papada', 'Cómo reducir la papada: qué funciona de verdad'), ('como-mejorar-la-postura', 'Cómo mejorar la postura: qué funciona de verdad')],
    'estetica-y-belleza': [('como-dejar-de-roncar', 'Cómo dejar de roncar y dormir mejor'), ('como-mejorar-la-postura', 'Cómo mejorar la postura: qué funciona de verdad')],
    'articulos-infantiles': [('regalos-de-navidad', 'Regalos de Navidad y Reyes: ideas por edad y presupuesto')],
    'ofertas': [('regalos-de-navidad', 'Regalos de Navidad: ideas y cuándo comprar'), ('hot-sale-cyber-monday-black-friday', 'Hot Sale, Cyber Monday y Black Friday: cuándo son'), ('dia-del-amigo', 'Día del Amigo: cuándo es y qué regalar')],
    'organizadores': [('como-organizar-el-placard', 'Cómo organizar el placard'), ('como-organizar-una-cocina-pequena', 'Cómo organizar una cocina pequeña')],
    'bazar-y-cocina': [('como-organizar-una-cocina-pequena', 'Cómo organizar una cocina pequeña'), ('como-limpiar-termo-acero-inoxidable', 'Cómo limpiar un termo de acero')],
    'vasos-y-botellas-termicas': [('como-curar-el-mate', 'Cómo curar el mate paso a paso'), ('como-limpiar-termo-acero-inoxidable', 'Cómo limpiar tu termo por dentro')],
    'accesorios-para-mascotas': [('como-sacar-pelos-de-mascota-de-la-ropa', 'Cómo sacar los pelos de tu mascota de la ropa')],
    'lamparas-y-luces-led': [('ideas-para-decorar-una-habitacion', 'Ideas para decorar una habitación'), ('regalos-originales-para-mujeres', 'Regalos originales para mujeres')],
    'deco': [('ideas-para-decorar-una-habitacion', 'Ideas para decorar una habitación')],
    'accesorios-de-moda': [('regalos-originales-para-mujeres', 'Regalos originales para mujeres')],
    'home': [('como-organizar-el-placard', 'Cómo organizar el placard'), ('ideas-para-decorar-una-habitacion', 'Ideas para decorar una habitación')],
}




def generar_blog(productos: list = None, slug_map: dict = None) -> list:
    """Genera /blog/ (hub) y /blog/<slug>/ desde utils.blog_posts. Devuelve slugs."""
    blog_dir = PAGES_DIR / 'blog'
    slugs = []
    for slug, cfg in BLOG_POSTS.items():
        canonical = f"{CANONICAL_DOMAIN}/blog/{slug}/"
        og_img = f"{CANONICAL_DOMAIN}{cfg['imagen'][0]}" if cfg.get('imagen') else ''
        jsonld = [{
            "@context": "https://schema.org/",
            "@type": "Article",
            "headline": cfg['h1'],
            "description": cfg['meta'],
            **({"image": [og_img]} if og_img else {}),
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
        img_hero = ''
        if cfg.get('imagen'):
            src, alt = cfg['imagen']
            img_hero = (f'<div class="blog-img-hero"><img src="{src}" alt="{html.escape(alt)}" '
                        f'width="1200" height="670"></div>')
        partes_sec = []
        for sec in cfg['secciones']:
            t, c = sec[0], sec[1]
            img_s, prod_s = '', ''
            if len(sec) > 2 and sec[2]:
                if sec[2][0] == 'prod' and productos:
                    rxp = re.compile(sec[2][1], re.I)
                    p_hit = next((p for p in productos if rxp.search(p['nombre'])), None)
                    if p_hit and slug_map:
                        prod_s = f'<div class="blog-prod">{_card_listado(p_hit, slug_map)}</div>'
                else:
                    s_src, s_alt = sec[2]
                    img_s = (f'<img src="{s_src}" alt="{html.escape(s_alt)}" width="1200" '
                             f'height="670" loading="lazy">')
            sec_id = f'sec-{len(partes_sec) + 1}'
            partes_sec.append(f'<section id="{sec_id}">{img_s}<h2>{html.escape(t)}</h2><p>{c}</p>{prod_s}</section>')
        toc = ''
        if len(cfg['secciones']) >= 6:
            items_toc = ''.join(f'<a href="#sec-{i + 1}">{html.escape(t[0])}</a>'
                                for i, t in enumerate(cfg['secciones']))
            toc = (f'<section class="blog-toc"><h2>En esta guía</h2><nav>{items_toc}</nav></section>')
        secciones = toc + ''.join(partes_sec)
        faqs = ''
        if cfg.get('faqs'):
            items = ''.join(f'<div class="listado-faq-item"><h3>{html.escape(q)}</h3><p>{html.escape(a)}</p></div>'
                            for q, a in cfg['faqs'])
            faqs = f'<div class="listado-faqs"><h2>Preguntas frecuentes</h2>{items}</div>'
        rel = ''
        rel_slugs = BLOG_RELACIONADOS.get(slug, [])
        if rel_slugs:
            def _thumb_rel(c):
                if not c.get('imagen'):
                    return ''
                t_src, t_alt = c['imagen']
                return (f'<img src="{t_src}" alt="{html.escape(t_alt)}" loading="lazy" width="1200" height="670" '
                        f'style="width:100%;height:120px;object-fit:cover;border-radius:10px;margin-bottom:10px;display:block">')
            cards_rel = ''.join(
                f'<a class="blog-card" href="/blog/{r}/">{_thumb_rel(BLOG_POSTS[r])}<h2>{html.escape(BLOG_POSTS[r]["h1"])}</h2></a>'
                for r in rel_slugs if r in BLOG_POSTS)
            rel = (f'<div class="listado-faqs" style="padding-top:6px"><h2>Seguí leyendo</h2>'
                   f'<div class="blog-grid" style="margin-top:0;padding:0">{cards_rel}</div></div>')
        cierre = ('<div class="blog-cierre"><a class="btn btn-accent" href="/" '
                  'style="display:inline-block">Ver el catálogo completo →</a></div>')
        cuerpo = f'{img_hero}<div class="blog-body">{secciones}</div>{faqs}{rel}{cierre}'
        destino = blog_dir / slug
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'index.html').write_text(
            _shell_blog(cfg['title'], cfg['meta'], canonical, jsonld, hero, cuerpo, og_img), encoding='utf-8')
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
    def _thumb(c):
        if not c.get('imagen'):
            return ''
        t_src, t_alt = c['imagen']
        return (f'<img src="{t_src}" alt="{html.escape(t_alt)}" loading="lazy" width="1200" height="670" '
                f'style="width:100%;height:150px;object-fit:cover;border-radius:12px;margin-bottom:12px;display:block">')
    cards = ''.join(
        f'''<a class="blog-card" href="/blog/{s}/">{_thumb(c)}<h2>{html.escape(c['h1'])}</h2><p>{html.escape(re.sub("<[^>]+>", "", c['intro'])[:130])}…</p></a>'''
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
        # title/H1/intro salen del stock real de hoy (ver FAMILIAS en seo_categorias.py)
        cfg = resolver_categoria(s, cfg, items)
        destino = cat_dir / s
        destino.mkdir(parents=True, exist_ok=True)
        (destino / 'index.html').write_text(
            render_pagina_listado('categoria', s, cfg, items, slug_map, chips), encoding='utf-8')
        slugs_cat.append(s)

    col_dir = PAGES_DIR / 'coleccion'
    slugs_col = []
    for s, cfg in COLECCIONES_SEO.items():
        rx = re.compile(cfg['match'], re.I)
        rx_ex = re.compile(cfg['excluir'], re.I) if cfg.get('excluir') else None
        items = [p for p in productos if rx.search(p['nombre'])
                 and not (rx_ex and rx_ex.search(p['nombre']))]
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

    # 1. Slugs: se CONGELAN una vez asignados. La URL de una ficha es un
    #    activo SEO (edad, enlaces, posicion); si se recalculara del nombre
    #    en cada corrida, cada reescritura de titulo (el job mensual de
    #    Gemini, un override manual) moveria la pagina a otra URL sin
    #    redireccion y Google encontraria un 404 donde habia una ficha
    #    rankeando. Entre junio y septiembre de 2026 eso paso con 35+
    #    productos. Solo se calcula slug para productos que no tienen uno.
    #    El sufijo con SKU garantiza unicidad, asi que congelar es seguro.
    #    Un producto que REINGRESA llega sin url_amigable (11_ inserta la fila
    #    de cero porque la anterior se borro al agotarse): su slug se recupera
    #    del registro de fichas (data/fichas_producto.json), asi vuelve a la
    #    misma URL que Google ya conocia en vez de estrenar una nueva.
    fichas = cargar_fichas_state()
    slug_map = {}
    slugs_usados = set()
    restaurados = 0
    # primero los que ya tienen slug (para que ningun nuevo choque con ellos)
    for p in productos:
        existente = (p.get('url_amigable') or '').strip()
        if existente:
            slug_map[p['sku']] = existente
            slugs_usados.add(existente)
    for p in productos:
        if p['sku'] in slug_map:
            continue
        previo = (fichas.get(p['sku']) or {}).get('slug') or ''
        if previo and previo not in slugs_usados:
            slug_map[p['sku']] = previo
            slugs_usados.add(previo)
            restaurados += 1
            continue
        slug = construir_slug(p['nombre'], p['sku'])
        if slug in slugs_usados:
            slug = f"{slug}-{slugify(p['sku'])}-2"
        slugs_usados.add(slug)
        slug_map[p['sku']] = slug
    if restaurados:
        print(f"♻️  {restaurados} productos reingresados recuperaron su URL anterior")

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
        # memoria de la ficha (sobrevive a que 11_ borre la fila al agotarse)
        fichas[sku] = {'slug': slug, 'nombre': p['nombre'], 'precio': p['precio_venta']}

    print(f"✅ {len(slugs_generados)} páginas de producto generadas en {PRODUCTO_DIR}")

    # 3a. Fichas de productos AGOTADOS. Antes se borraba la carpeta y la URL
    #     daba 404: se perdia la posicion ganada (ej. la pinza destapacanerias
    #     DL1254-1X1 rankeaba en el puesto 9 y desaparecio) y al reingresar
    #     (el stock de Droppers rota seguido) habia que empezar de cero. Ahora
    #     la ficha queda publicada con badge "Agotado", sin compra, JSON-LD
    #     OutOfStock y 4 alternativas en stock. Fuente de datos: la fila de la
    #     base si sigue ahi (stock 0), si no data/productos/<SKU>/metadata.json.
    #     La URL sale de la base, del registro de fichas o de la carpeta ya
    #     publicada: NUNCA se inventa una URL nueva para un agotado.
    #     Pasados AGOTADO_DIAS_MAX dias, la ficha se reemplaza por un stub
    #     noindex + refresh a su categoria y sale del sitemap.
    hoy = date.today()
    agotados_db = {p['sku']: dict(p) for p in cargar_agotados_db(conn)}
    carpetas_por_sku = {}
    for carpeta in PRODUCTO_DIR.iterdir():
        if carpeta.is_dir() and carpeta.name not in slugs_generados:
            s = sku_de_ficha_existente(carpeta)
            if s and s not in slug_map:
                carpetas_por_sku.setdefault(s, carpeta.name)
    candidatos = (set(agotados_db) | set(listar_skus_con_metadata()) | set(fichas) | set(carpetas_por_sku)) - set(slug_map)
    fichas_agotadas = {}     # slug -> 'ficha' | 'stub'
    slug_map_agotados = {}   # sku -> slug (para redirecciones de slugs viejos)
    for sku in sorted(candidatos):
        fila = agotados_db.get(sku)
        meta = leer_metadata(sku)
        reg = fichas.get(sku) or {}
        if not fila and not meta:
            continue  # sin datos para renderizar (no se inventa nada)
        slug = ((fila.get('url_amigable') or '').strip() if fila else '') or reg.get('slug') or carpetas_por_sku.get(sku, '')
        if not slug or slug in slugs_generados or slug in fichas_agotadas:
            continue  # nunca tuvo ficha publicada (o colision imposible por el sufijo SKU)
        nombre_previo = reg.get('nombre') or (nombre_de_ficha_existente(PRODUCTO_DIR / slug) if sku in carpetas_por_sku else '')
        if fila:
            producto = fila
            producto['nombre'] = (producto.get('nombre') or nombre_previo or sku).strip()
        else:
            producto = producto_desde_metadata(sku, meta, nombre_previo)
        if float(producto.get('precio_venta') or 0) <= 0 and reg.get('precio'):
            producto['precio_venta'] = reg['precio']  # ultimo precio publicado
        # Desde cuando esta agotado: lo mas antiguo entre el registro y
        # metadata.fecha_agotado (17_); si no hay nada, hoy. Nunca avanza
        # mientras siga agotado; se limpia al reingresar.
        fechas = [f for f in (reg.get('agotado_desde'), fecha_agotado_de_metadata(meta)) if f]
        desde = min(fechas) if fechas else hoy.isoformat()
        dias = (hoy - date.fromisoformat(desde)).days
        categoria = producto.get('categoria') or 'General'
        destino_dir = PRODUCTO_DIR / slug
        destino_dir.mkdir(parents=True, exist_ok=True)
        if dias > AGOTADO_DIAS_MAX:
            (destino_dir / 'index.html').write_text(render_stub_agotado(slug, categoria), encoding='utf-8')
            fichas_agotadas[slug] = 'stub'
        else:
            alternativas = elegir_alternativas(sku, producto.get('item_group_id') or '', categoria,
                                               por_grupo, por_categoria, productos)
            contenido = render_pagina(producto, slug, site_url, [], alternativas, slug_map, agotado=True)
            (destino_dir / 'index.html').write_text(contenido, encoding='utf-8')
            fichas_agotadas[slug] = 'ficha'
        slug_map_agotados[sku] = slug
        fichas[sku] = {'slug': slug, 'nombre': producto['nombre'], 'precio': producto.get('precio_venta') or 0,
                       'agotado_desde': desde}
    n_fichas_ag = sum(1 for v in fichas_agotadas.values() if v == 'ficha')
    n_stubs_ag = len(fichas_agotadas) - n_fichas_ag
    print(f"⛔ {n_fichas_ag} fichas de agotados conservadas (indexables, con alternativas) "
          f"+ {n_stubs_ag} agotados hace más de {AGOTADO_DIAS_MAX} días como stub noindex → categoría")

    # 3b. Redirecciones de slugs viejos. Si alguna vez un producto cambio de
    #     URL (antes de congelar los slugs, o por un cambio deliberado), la URL
    #     vieja sigue respondiendo con un stub que redirige a la actual, en vez
    #     de un 404 que tira la posicion ganada. GitHub Pages no tiene
    #     redirecciones de servidor: meta refresh 0 + canonical es lo que Google
    #     trata como redireccion permanente.
    redirects = {}
    if REDIRECTS_FILE.exists():
        try:
            redirects = json.loads(REDIRECTS_FILE.read_text(encoding='utf-8'))
        except Exception:
            redirects = {}
    # slugs que cambiaron en esta corrida (url_amigable previa distinta al slug actual)
    for p in productos:
        previo = (p.get('url_amigable') or '').strip()
        if previo and previo != slug_map.get(p['sku']) and previo not in slugs_generados:
            redirects[previo] = p['sku']
    # los agotados con ficha conservada tambien son destino valido: sus slugs
    # viejos siguen redirigiendo (y la entrada no se pierde mientras esten agotados)
    sku_a_slug = {**slug_map_agotados, **slug_map}
    stubs = 0
    vigentes = {}
    for viejo_slug, sku in redirects.items():
        destino = sku_a_slug.get(sku)
        if not destino or viejo_slug == destino or viejo_slug in slugs_generados or viejo_slug in fichas_agotadas:
            continue  # el producto ya no esta (404 legitimo) o el slug volvio a ser el actual
        vigentes[viejo_slug] = sku
        url = f"{CANONICAL_DOMAIN}/producto/{destino}/"
        stub = (
            '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
            f'<title>Redirigiendo… | {BRAND}</title>'
            f'<link rel="canonical" href="{html.escape(url)}">'
            f'<meta http-equiv="refresh" content="0;url={html.escape(url)}">'
            '<meta name="robots" content="noindex">'
            f'<script>location.replace({json.dumps(url)});</script>'
            f'</head><body><p>Esta página se movió a <a href="{html.escape(url)}">{html.escape(url)}</a>.</p></body></html>\n'
        )
        d = PRODUCTO_DIR / viejo_slug
        d.mkdir(parents=True, exist_ok=True)
        (d / 'index.html').write_text(stub, encoding='utf-8')
        stubs += 1
    REDIRECTS_FILE.write_text(json.dumps(vigentes, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    if stubs:
        print(f"↪️  {stubs} redirecciones de slugs viejos escritas")

    # 4. Eliminar SOLO las carpetas que no corresponden a nada: ni ficha en
    #    stock, ni agotado (ficha o stub, ver 3a), ni redireccion. Un agotado
    #    ya no se borra; aca solo cae una carpeta sin metadata ni fila en la
    #    base (no hay con que renderizarla) — 404 legitimo.
    eliminadas = 0
    if PRODUCTO_DIR.exists():
        for carpeta in PRODUCTO_DIR.iterdir():
            if (carpeta.is_dir() and carpeta.name not in slugs_generados and carpeta.name not in vigentes
                    and carpeta.name not in fichas_agotadas):
                logger.warning(f"Carpeta sin producto ni metadata, se elimina: {carpeta.name}")
                shutil.rmtree(carpeta)
                eliminadas += 1

    if eliminadas:
        print(f"🗑️  {eliminadas} carpetas de producto sin datos eliminadas")

    guardar_fichas_state(fichas)

    # 4b. Páginas de categoría y colección (arquitectura SEO: home -> listado -> producto)
    slugs_cat, slugs_col = generar_listados(productos, slug_map)
    print(f"✅ {len(slugs_cat)} páginas de categoría y {len(slugs_col)} de colección generadas")

    # 4c. Blog (contenido informacional que alimenta a las categorías)
    slugs_blog = generar_blog(productos, slug_map)
    print(f"✅ Blog: hub + {len(slugs_blog)} posts generados")

    # 5. Generar sitemap.xml
    canonical_url = CANONICAL_DOMAIN
    static_pages = [
        (f"{canonical_url}/", "weekly"),
        (f"{canonical_url}/faq", "monthly"),
        (f"{canonical_url}/sobre_nosotros", "monthly"),
        (f"{canonical_url}/contacto", "monthly"),
        (f"{canonical_url}/arrepentimiento", "monthly"),
        (f"{canonical_url}/seguimiento", "monthly"),
        (f"{canonical_url}/privacidad", "monthly"),
        (f"{canonical_url}/devoluciones", "monthly"),
        (f"{canonical_url}/terminos", "monthly"),
        (f"{canonical_url}/referidos", "weekly"),
        (f"{canonical_url}/mayoristas", "monthly"),
        (f"{canonical_url}/amigo-invisible/", "monthly"),
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
    # Agotados con ficha conservada: siguen en el sitemap (indexables, weekly).
    # Los stubs noindex (agotados hace mas de AGOTADO_DIAS_MAX dias) NO van.
    urls += [(f"{canonical_url}/producto/{slug}/", "weekly")
             for slug in sorted(s for s, tipo in fichas_agotadas.items() if tipo == 'ficha')]
    all_urls = static_pages + urls

    lastmods = _calcular_lastmods(all_urls)
    sitemap_items = '\n'.join(
        f"  <url><loc>{html.escape(u)}</loc><lastmod>{lastmods[u]}</lastmod><changefreq>{freq}</changefreq></url>"
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
    logger.info(f"Páginas de producto generadas: {len(slugs_generados)}, agotados: {n_fichas_ag} fichas + "
                f"{n_stubs_ag} stubs, eliminadas: {eliminadas}")
    return 0


if __name__ == "__main__":
    sys.exit(generar())
