#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERADOR DE FEED DE PRODUCTOS - GOOGLE MERCHANT CENTER
Genera pages/google_shopping.xml a partir de data/catalogo.db.

El archivo se publica vía GitHub Pages (pages/**) en:
    https://elgadget.com.ar/google_shopping.xml

Esa URL se carga en Merchant Center como fuente de datos primaria con
obtención programada diaria (Productos → Fuentes de datos → Agregar).

DIFERENCIAS DELIBERADAS CON generar_feed_facebook.py
----------------------------------------------------
El feed de Meta arrastra tres cosas que en Google causan desaprobación, así
que acá NO se replican:

1. `link` apunta a la ficha estática real (/producto/<slug>/), no a
   /producto_detalle.html?sku=X — esa URL está en Disallow del robots.txt, y
   Google necesita poder rastrear la landing de cada producto.
2. `availability` sale del stock real, no hardcodeada en "in stock". Un
   desajuste de disponibilidad entre feed y sitio es causa directa de
   desaprobación.
3. El precio usa la MISMA lógica de campañas que el sitio (utils/campanas.py),
   publicando precio de lista en g:price y el de oferta en g:sale_price. Si el
   feed dice un precio y la ficha muestra otro, Google desaprueba el producto y
   suma señal negativa a la revisión de la cuenta.

Además: los productos no tienen marca ni GTIN cargados (son genéricos de
dropshipping), así que se declara `g:identifier_exists = no`, que es el
mecanismo previsto por Google para eso. NO se pone "El Gadget" como marca: no
fabricamos estos productos y declararlo sería incorrecto.

Por la misma razón NO se publica `g:mpn` con el SKU (ver INCLUIR_MPN): la spec
oficial de mpn dice "Use the MPN assigned by the manufacturer. Unless you're the
manufacturer, don't use a value that you've created" y "When in doubt do not
provide an MPN", y los ejemplos de identifier_exists=no dejan mpn en blanco. El
SKU acá es el de Droppers (distribuidor), no un número de parte del fabricante:
publicarlo como MPN sería un valor inventado a ojos de Google y un motivo de
desaprobación, justo lo contrario de lo que se busca.

ATRIBUTOS DE CLASIFICACIÓN (2026-09-21)
---------------------------------------
- `g:google_product_category`: la categoría de la tienda es una bolsa mixta
  ("OFERTAS" tiene bodies de bebé, cinta para techos y un remolque de motos),
  así que el mapeo va en dos niveles: primero REGLAS POR NOMBRE (regex sobre el
  nombre normalizado, de más específica a más genérica) y, si ninguna matchea,
  un DEFAULT POR CATEGORÍA solo para las categorías homogéneas. Si tampoco hay
  default, el atributo se omite: Google prefiere que falte a que esté mal.
  Todas las rutas son de la taxonomía oficial (taxonomy-with-ids.en-US.txt);
  `verificar_mapeo_taxonomia(ruta)` las valida contra ese archivo.
- `g:color` / `g:size`: salen de las columnas `color` / `talle` cuando no están
  vacías. Al 2026-09-21 las 202 filas en stock las tienen vacías (los talles
  viven dentro de `variantes_internas`, un JSON por producto), así que hoy no
  se emiten; el código queda listo para cuando el sync las complete.
- `g:item_group_id`: idem, solo cuando la columna trae grupo (hoy ninguna).
- `g:product_type`: categoría (> subcategoría) de la tienda, texto libre.
- `g:condition`: siempre `new` (todo el catálogo es nuevo).

AUTOR: Sistema Ecommerce Automation
"""

import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger
from utils.campanas import campanas_programadas_vigentes, calcular_precio_oferta

logger = get_logger('generar_feed_google')

CANONICAL_DOMAIN = "https://elgadget.com.ar"   # igual que en 12_generar_paginas_producto.py
TIENDA = "El Gadget"
TITULO_MAX = 150        # límite de Google para title
DESCRIPCION_MAX = 5000
MAX_IMAGENES_EXTRA = 10  # additional_image_link admite hasta 10

# g:mpn con el SKU: APAGADO a propósito (ver docblock). Si algún día se cargan
# números de parte reales del fabricante, poner True y emitirlos desde esa
# columna, no desde el SKU de Droppers.
INCLUIR_MPN = False

# ---------------------------------------------------------------------------
# MAPEO A LA TAXONOMÍA DE GOOGLE (google_product_category)
# ---------------------------------------------------------------------------
# Reglas por nombre: (regex sobre el nombre en minúsculas y SIN acentos, ruta
# oficial). Se evalúan EN ORDEN y gana la primera que matchea, así que las
# específicas van antes que las genéricas (ej. "cartuchera ... mochila" tiene
# que caer en Pen & Pencil Cases, no en Backpacks; "botella ... con stickers"
# en Water Bottles, no en Decorative Stickers).
REGLAS_NOMBRE = [
    # --- bebés / infantil ---
    (r'\bbody\b', "Apparel & Accessories > Clothing > Baby & Toddler Clothing > Baby One-Pieces"),
    (r'\bmedias?\b', "Apparel & Accessories > Clothing > Underwear & Socks > Socks"),
    (r'protector(es)? (de )?perilla', "Baby & Toddler > Baby Safety > Baby Safety Locks & Guards"),
    (r'borde (de )?seguridad', "Baby & Toddler > Baby Safety > Baby Safety Locks & Guards"),
    (r'\borinal\b|\bpelela\b', "Baby & Toddler > Potty Training"),
    (r'bloques de construccion|juguete para armar', "Toys & Games > Toys > Building Toys > Construction Set Toys"),
    # cartuchera y mochila ANTES que peluche/bandolera: "cartuchera ... mochila
    # bandolera" es una cartuchera y "mochila ... peluche" es una mochila.
    (r'\bcartuchera\b|\bcanopla\b', "Office Supplies > Filing & Organization > Pen & Pencil Cases"),
    (r'\bmochila\b|\bmorral\b', "Luggage & Bags > Backpacks"),
    (r'\bpeluche\b', "Toys & Games > Toys > Dolls, Playsets & Toy Figures > Stuffed Animals"),
    # --- librería ---
    (r'\bresaltador', "Office Supplies > Office Instruments > Writing & Drawing Instruments > Markers & Highlighters > Highlighters"),
    (r'\bboligrafo|\blapicera', "Office Supplies > Office Instruments > Writing & Drawing Instruments > Pens & Pencils"),
    (r'\bsacapuntas\b', "Office Supplies > Office Instruments > Pencil Sharpeners"),
    (r'\banotador\b', "Office Supplies > General Office Supplies > Paper Products > Notebooks & Notepads"),
    # --- cocina / bebidas (antes que stickers: "botella ... con stickers") ---
    (r'vaso termico|\btumbler\b', "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Tumblers"),
    (r'botella.*termic|termic.*botella|\btermo\b', "Home & Garden > Kitchen & Dining > Food & Beverage Carriers > Thermoses"),
    (r'\bbotella\b', "Home & Garden > Kitchen & Dining > Food & Beverage Carriers > Water Bottles"),
    (r'escurr', "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils > Dish Racks & Drain Boards"),
    (r'plato giratorio', "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils > Kitchen Organizers"),
    (r'moldes? .*helado|helado.*moldes?', "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils"),
    (r'lava ?copas|cepillo.*(copas|vasos)', "Home & Garden > Household Supplies > Household Cleaning Supplies > Scrub Brushes"),
    (r'dispenser|dispensador', "Home & Garden > Bathroom Accessories > Soap & Lotion Dispensers"),
    # --- papelería decorativa / fiesta ---
    (r'\bstickers?\b', "Arts & Entertainment > Hobbies & Creative Arts > Arts & Crafts > Art & Crafting Materials > Embellishments & Trims > Decorative Stickers"),
    (r'\bglobos?\b', "Arts & Entertainment > Party & Celebration > Party Supplies > Balloons"),
    (r'vela.*cumplea|cumplea.*vela', "Arts & Entertainment > Party & Celebration > Party Supplies > Birthday Candles"),
    # --- baño / limpieza / hogar ---
    (r'\bescobilla\b', "Home & Garden > Bathroom Accessories > Toilet Brushes & Holders"),
    (r'\bjabonera\b', "Home & Garden > Bathroom Accessories > Soap Dishes & Holders"),
    (r'soporte (de )?ducha', "Home & Garden > Bathroom Accessories"),
    (r'sacapelusas?|quita ?pelusas?', "Home & Garden > Household Supplies > Laundry Supplies > Lint Rollers"),
    (r'atrapa ?pelos', "Home & Garden > Household Supplies > Laundry Supplies > Laundry Balls"),
    (r'organizador colgante', "Home & Garden > Household Supplies > Storage & Organization > Clothing & Closet Storage > Closet Organizers & Garment Racks"),
    (r'fundas?.*(ropa|traje|camper)', "Luggage & Bags > Garment Bags"),
    (r'repelente', "Home & Garden > Household Supplies > Pest Control > Repellents"),
    (r'\bmaceta', "Home & Garden > Lawn & Garden > Gardening > Pots & Planters"),
    (r'tira de luz|tira de luces', "Home & Garden > Lighting > Night Lights & Ambient Lighting"),
    (r'\blampara\b|\bvelador\b', "Home & Garden > Lighting > Lamps"),
    # --- ferretería / plomería ---
    (r'rejilla.*desag|desague', "Hardware > Plumbing > Plumbing Fixture Hardware & Parts > Drain Components > Drain Covers & Strainers"),
    (r'destapaca|pinza.*ca(n|ñ)er', "Hardware > Plumbing > Plumbing Fixture Hardware & Parts > Drain Components > Drain Rods"),
    (r'cinta membrana|membrana autoadhesiva', "Hardware > Building Consumables > Hardware Tape"),
    (r'espejos?.*(bici|monopat)', "Sporting Goods > Outdoor Recreation > Cycling > Bicycle Accessories > Bicycle Mirrors"),
    (r'\bremolque\b', "Vehicles & Parts > Vehicle Parts & Accessories > Vehicle Storage & Cargo > Motor Vehicle Trailers"),
    # --- mascotas ---
    (r'collar isabelino', "Animals & Pet Supplies > Pet Supplies > Pet Medical Collars"),
    (r'cepillo.*mascota', "Animals & Pet Supplies > Pet Supplies > Pet Grooming Supplies > Pet Combs & Brushes"),
    (r'mascotas?|\bperros?\b|\bgatos?\b', "Animals & Pet Supplies > Pet Supplies"),
    # --- salud / belleza ---
    (r'corrector (de )?postura|\bfaja\b', "Health & Beauty > Health Care > Supports & Braces"),
    (r'dilatador|ronquido', "Health & Beauty > Personal Care > Sleeping Aids > Snoring & Sleep Apnea Aids"),
    (r'depilaci', "Health & Beauty > Personal Care > Shaving & Grooming > Hair Removal > Waxing Kits & Supplies"),
    (r'tapones.*(ruido|oido)', "Health & Beauty > Personal Care > Ear Care > Earplugs"),
    # --- electrónica ---
    (r'\bmicrofono\b', "Electronics > Audio > Audio Components > Microphones"),
    (r'\breloj\b', "Apparel & Accessories > Jewelry > Watches"),
    # --- verano ---
    (r'flotador|inflable', "Home & Garden > Pool & Spa > Pool & Spa Accessories > Pool Floats & Loungers"),
    (r'bikini|\bmalla\b|traje de bano|vedetina|enteriza', "Apparel & Accessories > Clothing > Swimwear"),
    # --- indumentaria y accesorios (bolsos antes que bandolera/cartera) ---
    (r'\bcalzas?\b', "Apparel & Accessories > Clothing > Activewear"),
    (r'\bblusa\b|\bcamisa\b', "Apparel & Accessories > Clothing > Shirts & Tops"),
    (r'\bgorro\b|\bbeanie\b|\bpiluso\b', "Apparel & Accessories > Clothing Accessories > Hats"),
    (r'\bguantes?\b', "Apparel & Accessories > Clothing Accessories > Gloves & Mittens"),
    (r'\bmanton\b|\bponcho\b|\bbufanda\b', "Apparel & Accessories > Clothing Accessories > Scarves & Shawls"),
    (r'portacosmetico|\bneceser\b', "Luggage & Bags > Cosmetic & Toiletry Bags"),
    (r'rinonera', "Luggage & Bags > Fanny Packs"),
    (r'bandoler|\bcartera\b|\bbolso\b|mini bag|\bsobre mujer\b', "Apparel & Accessories > Handbags, Wallets & Cases > Handbags"),
]

# Default por categoría de la tienda, SOLO para las homogéneas. Las bolsas
# mixtas (OFERTAS, Verano, Home, Nuevos Ingresos, Artículos Infantiles) no
# tienen default a propósito: sin regla por nombre, se omite el atributo.
DEFAULT_POR_CATEGORIA = {
    'Accesorios para Mascotas': "Animals & Pet Supplies > Pet Supplies",
    'Accesorios de Moda': "Apparel & Accessories",
    'Bazar y Cocina': "Home & Garden > Kitchen & Dining",
    'Baño y Limpieza': "Home & Garden > Household Supplies",
    'Deco': "Home & Garden > Decor",
    'Electrónica': "Electronics",
    'Estética y Belleza': "Health & Beauty",
    'Fitness': "Sporting Goods > Exercise & Fitness",
}

_REGLAS_COMPILADAS = [(re.compile(rx), ruta) for rx, ruta in REGLAS_NOMBRE]


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos ni diacríticos, espacios colapsados."""
    if not texto:
        return ''
    sin_acentos = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', sin_acentos.lower()).strip()


def google_product_category(nombre: str, categoria: str) -> str:
    """Ruta oficial de Google para el producto, o '' si no hay mapeo seguro."""
    n = normalizar(nombre)
    for rx, ruta in _REGLAS_COMPILADAS:
        if rx.search(n):
            return ruta
    return DEFAULT_POR_CATEGORIA.get((categoria or '').strip(), '')


def verificar_mapeo_taxonomia(ruta_taxonomia) -> list:
    """Devuelve las rutas del mapeo que NO existen en el archivo oficial
    (taxonomy-with-ids.en-US.txt, formato 'ID - Ruta > Sub'). Lista vacía = OK."""
    texto = Path(ruta_taxonomia).read_text(encoding='utf-8')
    oficiales = {linea.split(' - ', 1)[1].strip() for linea in texto.splitlines()
                 if ' - ' in linea and not linea.startswith('#')}
    usadas = {ruta for _, ruta in REGLAS_NOMBRE} | set(DEFAULT_POR_CATEGORIA.values())
    return sorted(r for r in usadas if r not in oficiales)


def limpiar(texto: str, limite: int) -> str:
    """Aplana a una línea y recorta al límite de Google."""
    if not texto:
        return ''
    return re.sub(r'\s+', ' ', texto).strip()[:limite]


def imagenes_de(producto) -> tuple:
    """Devuelve (principal, [adicionales]) a partir de las columnas de la DB."""
    principal = (producto['imagen_principal'] or '').strip()
    crudas = (producto['imagenes_adicionales'] or '').strip()
    extra = [u.strip() for u in crudas.split(',') if u.strip() and u.strip() != principal]
    return principal, extra[:MAX_IMAGENES_EXTRA]


def item_xml(producto, descuentos) -> str:
    """Arma el <item> de un producto. Devuelve '' si le falta algo obligatorio."""
    sku = producto['sku']
    slug = (producto['url_amigable'] or '').strip()
    imagen, extra = imagenes_de(producto)

    # Sin slug no hay landing rastreable; sin imagen Google lo rechaza igual.
    if not slug or not imagen:
        return ''

    precio_lista = float(producto['precio_venta'])
    oferta = calcular_precio_oferta(dict(producto), descuentos)

    campos = [
        f"<g:id>{escape(sku)}</g:id>",
        f"<title>{escape(limpiar(producto['nombre'], TITULO_MAX))}</title>",
        f"<description>{escape(limpiar(producto['descripcion'], DESCRIPCION_MAX))}</description>",
        f"<link>{CANONICAL_DOMAIN}/producto/{escape(slug)}/</link>",
        f"<g:image_link>{escape(imagen)}</g:image_link>",
    ]
    campos += [f"<g:additional_image_link>{escape(u)}</g:additional_image_link>" for u in extra]
    campos += [
        f"<g:availability>{'in_stock' if (producto['stock'] or 0) > 0 else 'out_of_stock'}</g:availability>",
        "<g:condition>new</g:condition>",
        f"<g:price>{precio_lista:.2f} ARS</g:price>",
    ]
    if oferta is not None and oferta < precio_lista:
        campos.append(f"<g:sale_price>{float(oferta):.2f} ARS</g:sale_price>")

    # Genéricos de dropshipping: sin marca ni GTIN reales. Declararlo es lo que
    # Google espera; inventar una marca sería incorrecto.
    campos.append("<g:identifier_exists>no</g:identifier_exists>")
    if INCLUIR_MPN:
        campos.append(f"<g:mpn>{escape(sku)}</g:mpn>")

    # Clasificación: taxonomía oficial de Google (solo si hay mapeo seguro) +
    # categoría propia de la tienda como product_type.
    gpc = google_product_category(producto['nombre'], producto['categoria'])
    if gpc:
        campos.append(f"<g:google_product_category>{escape(gpc)}</g:google_product_category>")
    tipo = ' > '.join(x for x in [producto['categoria'], producto['subcategoria']] if x)
    if tipo:
        campos.append(f"<g:product_type>{escape(tipo)}</g:product_type>")

    # Variantes: grupo, color y talle solo cuando la base los trae (hoy vacíos).
    grupo = (str(producto['item_group_id'] or '')).strip()
    if grupo:
        campos.append(f"<g:item_group_id>{escape(grupo)}</g:item_group_id>")
    color = (producto['color'] or '').strip()
    if color:
        campos.append(f"<g:color>{escape(limpiar(color, 100))}</g:color>")
    talle = (producto['talle'] or '').strip()
    if talle:
        campos.append(f"<g:size>{escape(limpiar(talle, 100))}</g:size>")

    cuerpo = '\n      '.join(campos)
    return f"    <item>\n      {cuerpo}\n    </item>"


def generar_feed():
    print("\n" + "=" * 70)
    print("🛒 GENERADOR DE FEED GOOGLE MERCHANT CENTER")
    print("=" * 70 + "\n")

    db_path = Config.DATA_DIR / 'catalogo.db'
    if not db_path.exists():
        print(f"❌ No se encontró la base de datos: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    descuentos = campanas_programadas_vigentes(cursor)

    cursor.execute("""
        SELECT sku, nombre, descripcion, precio_venta, stock, categoria, subcategoria,
               imagen_principal, imagenes_adicionales, item_group_id, url_amigable,
               color, talle
        FROM productos
        WHERE precio_venta > 0 AND stock > 0
        ORDER BY sku
    """)
    productos = cursor.fetchall()
    conn.close()

    if not productos:
        print("⚠️  No hay productos disponibles en catalogo.db")
        return 1

    items, omitidos = [], []
    for p in productos:
        xml = item_xml(p, descuentos)
        (items.append(xml) if xml else omitidos.append(p['sku']))

    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
        '  <channel>\n'
        f'    <title>{escape(TIENDA)}</title>\n'
        f'    <link>{CANONICAL_DOMAIN}</link>\n'
        '    <description>Catálogo de productos de El Gadget para Google Merchant Center</description>\n'
        f'    <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S -0300")}</lastBuildDate>\n'
        + '\n'.join(items) + '\n'
        '  </channel>\n'
        '</rss>\n'
    )

    output_file = Config.BASE_DIR / 'pages' / 'google_shopping.xml'
    output_file.write_text(feed, encoding='utf-8')

    con_oferta = feed.count('<g:sale_price>')
    print(f"✅ Feed generado: {output_file}")
    print(f"📦 Productos incluidos: {len(items)} ({con_oferta} con precio de oferta)")
    print(f"   google_product_category: {feed.count('<g:google_product_category>')} · "
          f"item_group_id: {feed.count('<g:item_group_id>')} · "
          f"color: {feed.count('<g:color>')} · size: {feed.count('<g:size>')}")
    if omitidos:
        print(f"⚠️  Omitidos por falta de slug o imagen ({len(omitidos)}): {', '.join(omitidos[:10])}")
    print(f"🔗 URL pública (tras el push): {CANONICAL_DOMAIN}/google_shopping.xml")
    print("\n" + "=" * 70 + "\n")

    logger.info(f"Feed Google generado: {len(items)} productos, {len(omitidos)} omitidos -> {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(generar_feed())
