#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALERTAS DROPPERS - Productos nuevos, cambios de precio y de stock

Lee los 3 reportes de "/alerts/customer/index/" de Droppers (logueado),
que el sitio expone vía los endpoints JSON usados por los botones
"Cargar más productos":

- POST /alerts/product/news  -> productos nuevos en el catálogo de Droppers
- POST /alerts/product/price -> cambios de costo (precio de Droppers)
- POST /alerts/product/stock -> cambios de stock (agotado/reingresado)

Cada feed está paginado (page_number / next_page) y se recorre sólo hasta
llegar a lo ya procesado en una corrida anterior, según el checkpoint
guardado en data/droppers_alertas_estado.json. Así cada corrida diaria sólo
mira las novedades desde la última vez.

PRODUCTOS NUEVOS: para cada SKU detectado en /alerts/product/news que NO
tenga ya data/productos/<sku>/metadata.json, se scrapea el detalle completo
vía catalog/product/view/id/{entity_id}/ (mismo extractor que usa
scraper_maestro_v2_sin_categorias.py) y se guarda con categorias_pendientes
= True, igual que el scraper normal. El paso "Asignación de categoría
OFERTAS" del pipeline los categoriza automáticamente.

CAMBIOS DE PRECIO: si el SKU ya está en el catálogo local, se actualiza
metadata['precio'] con el nuevo costo. El paso "Cálculo de precios"
recalcula precio_venta para todos los productos en cada corrida.

CAMBIOS DE STOCK: en esta versión sólo se registran en un reporte JSON
(informativo); la detección de agotados/reingresados sigue a cargo de
17_deteccion_agotados_robusto.py.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config
from scraper_maestro_v2_sin_categorias import ScraperMaestroV2

logger = get_logger('alertas_droppers')

ESTADO_FILE = Config.DATA_DIR / 'droppers_alertas_estado.json'

ESTADO_DEFAULT = {
    'news_ultimo_entity_id': 0,
    'price_ultimo_timestamp': '1970-01-01 00:00:00',
    'stock_ultimo_timestamp': '1970-01-01 00:00:00',
}


def cargar_estado() -> dict:
    if ESTADO_FILE.exists():
        with open(ESTADO_FILE, 'r', encoding='utf-8') as f:
            estado = json.load(f)
        return {**ESTADO_DEFAULT, **estado}
    return dict(ESTADO_DEFAULT)


def guardar_estado(estado: dict):
    with open(ESTADO_FILE, 'w', encoding='utf-8') as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def obtener_paginas(session, endpoint: str, paginas_historicas: int):
    """
    Generador que va pidiendo POST /alerts/product/{endpoint} con
    page_number=1,2,3... y entrega los items de cada página junto con el
    número de página, hasta que next_page sea None o se llegue al límite
    de páginas (sólo aplica cuando es la primera ejecución, sin checkpoint).
    """
    pagina = 1
    while True:
        resp = session.post(
            f"https://droppers.com.ar/alerts/product/{endpoint}",
            data={'page_number': pagina},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        productos = data.get('products') or []

        yield pagina, productos

        if not data.get('next_page'):
            break
        if paginas_historicas and pagina >= paginas_historicas:
            break

        pagina += 1


def procesar_nuevos(session, estado: dict, paginas_historicas: int) -> list:
    """Detecta y scrapea productos nuevos vía /alerts/product/news"""
    ultimo_entity_id = estado['news_ultimo_entity_id']
    primera_ejecucion = ultimo_entity_id == 0

    candidatos = []
    max_entity_id = ultimo_entity_id

    for pagina, productos in obtener_paginas(session, 'news', 1 if primera_ejecucion else 0):
        for item in productos:
            entity_id = int(item.get('entity_id', 0))
            max_entity_id = max(max_entity_id, entity_id)

            if not primera_ejecucion and entity_id <= ultimo_entity_id:
                continue

            candidatos.append(item)

        if not primera_ejecucion:
            # En corridas normales, si ya llegamos a entity_id conocidos
            # en esta página, las siguientes serán todavía más viejas.
            ids_pagina = [int(p.get('entity_id', 0)) for p in productos]
            if ids_pagina and min(ids_pagina) <= ultimo_entity_id:
                break

        if primera_ejecucion and pagina >= max(paginas_historicas, 1):
            break

    estado['news_ultimo_entity_id'] = max_entity_id

    nuevos_agregados = []
    if not candidatos:
        return nuevos_agregados

    scraper = ScraperMaestroV2()
    scraper.session = session  # reutilizar la sesión ya logueada

    for item in candidatos:
        sku = item.get('sku')
        entity_id = item.get('entity_id')
        nombre = item.get('name', '')

        if not sku or not entity_id:
            continue

        if Config.get_ruta_metadata(sku).exists():
            logger.info(f"Alerta de producto nuevo {sku} ya existe en el catálogo local, se omite")
            continue

        url = f"https://droppers.com.ar/catalog/product/view/id/{entity_id}/"
        logger.info(f"Producto nuevo detectado por alertas: {sku} ({nombre}) -> {url}")

        producto = scraper.extraer_producto_sin_categorias(url)
        if not producto:
            logger.warning(f"No se pudo scrapear el producto nuevo {sku} ({url})")
            continue

        Config.guardar_metadata(producto['sku'], producto)
        nuevos_agregados.append({'sku': producto['sku'], 'nombre': producto.get('titulo', nombre)})

    return nuevos_agregados


def procesar_precios(session, estado: dict, paginas_historicas: int) -> list:
    """Detecta cambios de costo vía /alerts/product/price y actualiza metadata['precio']"""
    ultimo_timestamp = estado['price_ultimo_timestamp']
    primera_ejecucion = ultimo_timestamp == ESTADO_DEFAULT['price_ultimo_timestamp']

    actualizados = []
    max_timestamp = ultimo_timestamp

    for pagina, productos in obtener_paginas(session, 'price', 1 if primera_ejecucion else 0):
        timestamps_pagina = []

        for item in productos:
            timestamp = item.get('timestamp') or ''
            timestamps_pagina.append(timestamp)

            if timestamp > max_timestamp:
                max_timestamp = timestamp

            if not primera_ejecucion and timestamp <= ultimo_timestamp:
                continue

            sku = item.get('sku')
            if not sku or not Config.get_ruta_metadata(sku).exists():
                continue

            try:
                precio_nuevo = float(item.get('price', 0))
            except (TypeError, ValueError):
                continue

            metadata = Config.cargar_metadata(sku)
            precio_anterior = metadata.get('precio', 0)
            if precio_nuevo == precio_anterior:
                continue

            metadata['precio'] = precio_nuevo
            metadata['fecha_actualizacion_precio_alerta'] = datetime.now().isoformat()
            Config.guardar_metadata(sku, metadata)

            actualizados.append({
                'sku': sku,
                'nombre': item.get('name', metadata.get('titulo', '')),
                'precio_anterior': precio_anterior,
                'precio_nuevo': precio_nuevo,
            })

        if not primera_ejecucion and timestamps_pagina and min(timestamps_pagina) <= ultimo_timestamp:
            break

    estado['price_ultimo_timestamp'] = max_timestamp
    return actualizados


def procesar_stock(session, estado: dict, paginas_historicas: int) -> list:
    """Detecta cambios de stock vía /alerts/product/stock (informativo)"""
    ultimo_timestamp = estado['stock_ultimo_timestamp']
    primera_ejecucion = ultimo_timestamp == ESTADO_DEFAULT['stock_ultimo_timestamp']

    cambios = []
    max_timestamp = ultimo_timestamp

    for pagina, productos in obtener_paginas(session, 'stock', 1 if primera_ejecucion else 0):
        timestamps_pagina = []

        for item in productos:
            timestamp = item.get('timestamp') or ''
            timestamps_pagina.append(timestamp)

            if timestamp > max_timestamp:
                max_timestamp = timestamp

            if not primera_ejecucion and timestamp <= ultimo_timestamp:
                continue

            cambios.append({
                'sku': item.get('sku'),
                'nombre': item.get('name', ''),
                'estado': 'reingresado' if str(item.get('status')) == '1' else 'agotado',
                'timestamp': timestamp,
            })

        if not primera_ejecucion and timestamps_pagina and min(timestamps_pagina) <= ultimo_timestamp:
            break

    estado['stock_ultimo_timestamp'] = max_timestamp
    return cambios


def ejecutar(paginas_historicas: int = 1) -> bool:
    print("\n" + "=" * 70)
    print("🔔 ALERTAS DROPPERS - productos nuevos / precios / stock")
    print("=" * 70)

    scraper = ScraperMaestroV2()
    if not scraper.login():
        logger.error("No se pudo iniciar sesión en Droppers para leer alertas")
        return False

    session = scraper.session
    # Asegura que la sección de alertas quede inicializada en la sesión
    session.get("https://droppers.com.ar/alerts/customer/index/", timeout=30)

    estado = cargar_estado()

    print("\n📦 Revisando productos nuevos...")
    nuevos = procesar_nuevos(session, estado, paginas_historicas)
    print(f"   {len(nuevos)} producto(s) nuevo(s) agregado(s) al catálogo")
    for p in nuevos:
        print(f"   ➕ {p['sku']} - {p['nombre']}")

    print("\n💲 Revisando cambios de precio...")
    precios = procesar_precios(session, estado, paginas_historicas)
    print(f"   {len(precios)} producto(s) con cambio de costo")
    for p in precios:
        print(f"   💲 {p['sku']}: ${p['precio_anterior']:,.0f} -> ${p['precio_nuevo']:,.0f}")

    print("\n📊 Revisando cambios de stock...")
    stock = procesar_stock(session, estado, paginas_historicas)
    print(f"   {len(stock)} cambio(s) de stock detectado(s)")
    for c in stock:
        print(f"   📦 {c['sku']} ({c['nombre']}) -> {c['estado']}")

    if stock:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        reporte_file = Config.DATA_DIR / f'reporte_alertas_stock_{timestamp}.json'
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump({
                'fecha_ejecucion': datetime.now().isoformat(),
                'cambios': stock,
            }, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Reporte de stock guardado en: {reporte_file}")

    guardar_estado(estado)

    print("\n" + "=" * 70)
    print("✅ Alertas Droppers procesadas")
    print("=" * 70 + "\n")

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Alertas Droppers (productos nuevos, precios y stock)')
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Ejecutar sin confirmación interactiva (para automatización)'
    )
    parser.add_argument(
        '--paginas-historicas',
        type=int,
        default=1,
        help='Cantidad de páginas a procesar en la primera ejecución (sin checkpoint previo). Default: 1'
    )

    args = parser.parse_args()

    try:
        exitoso = ejecutar(paginas_historicas=args.paginas_historicas)
        sys.exit(0 if exitoso else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error en alertas Droppers: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
