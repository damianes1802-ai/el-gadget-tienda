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

AUTOR: Sistema Ecommerce Automation
"""

import re
import sqlite3
import sys
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

    tipo = ' > '.join(x for x in [producto['categoria'], producto['subcategoria']] if x)
    if tipo:
        campos.append(f"<g:product_type>{escape(tipo)}</g:product_type>")
    if producto['item_group_id']:
        campos.append(f"<g:item_group_id>{escape(str(producto['item_group_id']))}</g:item_group_id>")

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
               imagen_principal, imagenes_adicionales, item_group_id, url_amigable
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
    if omitidos:
        print(f"⚠️  Omitidos por falta de slug o imagen ({len(omitidos)}): {', '.join(omitidos[:10])}")
    print(f"🔗 URL pública (tras el push): {CANONICAL_DOMAIN}/google_shopping.xml")
    print("\n" + "=" * 70 + "\n")

    logger.info(f"Feed Google generado: {len(items)} productos, {len(omitidos)} omitidos -> {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(generar_feed())
