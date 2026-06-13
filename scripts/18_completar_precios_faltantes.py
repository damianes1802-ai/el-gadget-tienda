#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPLETAR PRECIOS FALTANTES
Recorre los productos en stock con precio=0 (no se pudo extraer el precio
en el scraping original) y revisita su página en Droppers para obtenerlo,
usando el mismo método de extracción robusto del scraper v2 corregido.
"""

import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import sys
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('completar_precios')
load_dotenv(Config.CONFIG_DIR / '.env')


def login(session: requests.Session) -> bool:
    print("🔐 Login en Droppers...")
    resp = session.get("https://droppers.com.ar/customer/account/login/", timeout=30)
    soup = BeautifulSoup(resp.content, 'html.parser')
    form_key_input = soup.find('input', {'name': 'form_key'})
    if not form_key_input:
        return False

    form_key = form_key_input.get('value')
    resp = session.post("https://droppers.com.ar/customer/account/loginPost/", data={
        'form_key': form_key,
        'login[username]': os.getenv('DROPPERS_USER'),
        'login[password]': os.getenv('DROPPERS_PASS')
    }, timeout=30, allow_redirects=True)

    if any(x in resp.text for x in ['Mi cuenta', 'customer/account']):
        print("✅ Login exitoso\n")
        return True
    return False


def extraer_precio(session: requests.Session, url: str) -> int:
    """Extrae el precio de costo de una página de producto"""
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text

    precio_match = re.search(r'"price":\s*(\d+)', html)
    if precio_match:
        return int(precio_match.group(1))

    precio_match = re.search(r'data-price-amount="([\d.]+)"', html)
    if precio_match:
        return int(float(precio_match.group(1)))

    return 0


def main():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    if not login(session):
        print("❌ No se pudo iniciar sesión en Droppers")
        return

    skus = Config.listar_productos()

    pendientes = []
    for sku in skus:
        metadata = Config.cargar_metadata(sku)
        if metadata.get('disponibilidad') == 'in stock' and metadata.get('precio', 0) == 0:
            url = metadata.get('url_original')
            if url:
                pendientes.append((sku, url))

    print(f"📋 {len(pendientes)} productos con precio faltante\n")

    actualizados = 0
    sin_precio = 0

    for i, (sku, url) in enumerate(pendientes, 1):
        print(f"[{i}/{len(pendientes)}] {sku}...", end=' ')
        try:
            precio = extraer_precio(session, url)
            if precio > 0:
                metadata = Config.cargar_metadata(sku)
                metadata['precio'] = precio
                Config.guardar_metadata(sku, metadata)
                print(f"✅ ${precio:,}")
                actualizados += 1
            else:
                print("⚠️  sin precio en la página")
                sin_precio += 1
        except Exception as e:
            print(f"❌ error: {e}")
            logger.error(f"Error procesando {sku}: {e}")

        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"✅ Actualizados: {actualizados}")
    print(f"⚠️  Sin precio: {sin_precio}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
