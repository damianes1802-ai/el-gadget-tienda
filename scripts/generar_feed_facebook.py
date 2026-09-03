#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERADOR DE FEED DE PRODUCTOS - FACEBOOK / WHATSAPP CATALOG
Genera pages/facebook_catalog.csv a partir de data/catalogo.db.

El archivo se publica vía GitHub Pages (pages/**) en:
    {SITE_URL}/facebook_catalog.csv

Esa URL se configura en Meta Commerce Manager como "fuente de datos"
con actualización programada, y el catálogo resultante se puede
vincular a una cuenta de WhatsApp Business para mostrar el catálogo
dentro de la app.

AUTOR: Sistema Ecommerce Automation
"""

import csv
import re
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger
from utils.campanas import campanas_programadas_vigentes, calcular_precio_oferta

logger = get_logger('generar_feed_facebook')

BRAND = "El Gadget"
DESCRIPCION_MAX = 5000
# Dominio canonico FIJO, igual que en 12_generar_paginas_producto.py. NO leerlo
# de SITE_URL: el secret ENV_FILE del CI tiene un valor viejo
# (damianes1802-ai.github.io/el-gadget-tienda) y por eso el catalogo de WhatsApp
# quedo publicando URLs rotas durante meses.
CANONICAL_DOMAIN = "https://elgadget.com.ar"

# Columnas según especificación de Meta Commerce Manager
HEADERS = [
    'id', 'title', 'description', 'availability', 'condition',
    'price', 'sale_price', 'link', 'image_link', 'additional_image_link',
    'brand', 'product_type', 'item_group_id',
]


def limpiar_descripcion(texto: str) -> str:
    """Aplana la descripción a una sola línea y la recorta al límite de Meta"""
    if not texto:
        return ''
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto[:DESCRIPCION_MAX]


def generar_feed():
    print("\n" + "=" * 70)
    print("📡 GENERADOR DE FEED FACEBOOK / WHATSAPP CATALOG")
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
        SELECT sku, nombre, descripcion, precio_venta, stock, categoria,
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

    output_dir = Config.BASE_DIR / 'pages'
    output_file = output_dir / 'facebook_catalog.csv'

    filas_escritas = 0
    omitidos = []
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)

        for p in productos:
            sku = p['sku']
            imagenes_adicionales = p['imagenes_adicionales'] or ''

            slug = (p['url_amigable'] or '').strip()
            if not slug:
                omitidos.append(sku)   # sin ficha estatica no hay adonde mandar al cliente
                continue

            precio_lista = float(p['precio_venta'])
            oferta = calcular_precio_oferta(dict(p), descuentos)
            sale = f"{float(oferta):.2f} ARS" if (oferta is not None and oferta < precio_lista) else ''

            fila = [
                sku,
                p['nombre'] or '',
                limpiar_descripcion(p['descripcion']),
                'in stock' if (p['stock'] or 0) > 0 else 'out of stock',
                'new',
                f"{precio_lista:.2f} ARS",
                sale,
                f"{CANONICAL_DOMAIN}/producto/{slug}/",
                p['imagen_principal'] or '',
                imagenes_adicionales,
                BRAND,
                p['categoria'] or '',
                p['item_group_id'] or '',
            ]
            writer.writerow(fila)
            filas_escritas += 1

    feed_url = f"{CANONICAL_DOMAIN}/facebook_catalog.csv"

    print(f"✅ Feed generado: {output_file}")
    print(f"📦 Productos incluidos: {filas_escritas}")
    if omitidos:
        print(f"⚠️  Omitidos por falta de slug ({len(omitidos)}): {', '.join(omitidos[:10])}")
    print(f"🔗 URL pública (tras el push): {feed_url}")
    print("\n" + "=" * 70 + "\n")

    logger.info(f"Feed Facebook/WhatsApp generado: {filas_escritas} productos -> {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(generar_feed())
