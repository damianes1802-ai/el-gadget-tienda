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

logger = get_logger('generar_feed_facebook')

BRAND = "El Gadget"
DESCRIPCION_MAX = 5000

# Columnas según especificación de Meta Commerce Manager
HEADERS = [
    'id', 'title', 'description', 'availability', 'condition',
    'price', 'link', 'image_link', 'additional_image_link',
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

    env = Config.cargar_env()
    site_url = env.get('SITE_URL', 'http://localhost:5500').rstrip('/')

    db_path = Config.DATA_DIR / 'catalogo.db'
    if not db_path.exists():
        print(f"❌ No se encontró la base de datos: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sku, nombre, descripcion, precio_venta, categoria,
               imagen_principal, imagenes_adicionales, item_group_id
        FROM productos
        WHERE precio_venta > 0
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
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)

        for p in productos:
            sku = p['sku']
            imagenes_adicionales = p['imagenes_adicionales'] or ''

            fila = [
                sku,
                p['nombre'] or '',
                limpiar_descripcion(p['descripcion']),
                'in stock',
                'new',
                f"{p['precio_venta']:.2f} ARS",
                f"{site_url}/producto_detalle.html?sku={sku}",
                p['imagen_principal'] or '',
                imagenes_adicionales,
                BRAND,
                p['categoria'] or '',
                p['item_group_id'] or '',
            ]
            writer.writerow(fila)
            filas_escritas += 1

    feed_url = f"{site_url}/facebook_catalog.csv"

    print(f"✅ Feed generado: {output_file}")
    print(f"📦 Productos incluidos: {filas_escritas}")
    print(f"🔗 URL pública (tras el push): {feed_url}")
    print("\n" + "=" * 70 + "\n")

    logger.info(f"Feed Facebook/WhatsApp generado: {filas_escritas} productos -> {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(generar_feed())
