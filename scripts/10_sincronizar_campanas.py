#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SINCRONIZAR CAMPAÑAS DE DESCUENTO (API de Render → catalogo.db del repo)

Por qué existe
--------------
La tabla `descuentos` vive SOLO en el disco persistente de Render: el panel de
gestión escribe ahí y el checkout cobra desde ahí. El repo, en cambio, es lo
que leen el generador de páginas estáticas y los feeds de Google y Facebook.
`sincronizar_catalogo_desde_repo()` copia en el otro sentido (repo → Render) y
solo las tablas de catálogo, así que nadie traía las campañas de vuelta.

Resultado hasta el 2026-09-27: una campaña cargada en el panel la cobraba el
checkout, pero el sitio y los feeds seguían mostrando el precio de lista. Este
paso cierra ese agujero: baja las campañas vigentes y las escribe en el repo
ANTES de generar, así el precio publicado y el precio cobrado son el mismo.

Qué copia
---------
Solo las campañas PROGRAMADAS (las que no tienen código y mueven el precio del
catálogo). Los códigos —referidos, bienvenida, los asociados a un email— no se
tocan nunca: son privados y no viven en el repo.

Falla en blando a propósito
---------------------------
Si la API no responde (Render free se duerme, corte de red), NO borra nada: deja
el repo como estaba y sale con 0 para no frenar el pipeline. Borrar por un
timeout publicaría precio de lista en medio de una campaña, que es peor que
quedarse con la copia de ayer. Solo reemplaza cuando la respuesta fue 200.

Uso:
    python scripts/10_sincronizar_campanas.py
    API_URL=http://localhost:8000 python scripts/10_sincronizar_campanas.py
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / 'data' / 'catalogo.db'
API_URL = os.environ.get('API_URL', 'https://el-gadget-tienda.onrender.com').rstrip('/')
TIMEOUT = int(os.environ.get('CAMPANAS_TIMEOUT', '90'))   # Render free tarda en despertar

CAMPOS = ('id', 'nombre', 'tipo', 'valor', 'alcance', 'categoria', 'skus',
          'fecha_inicio', 'fecha_fin', 'recurrente_anual', 'activo',
          'mostrar_banner', 'banner_titulo', 'banner_texto')


def traer_campanas() -> list:
    """Campañas vigentes según la API. Lanza si no se pudo consultar."""
    url = f'{API_URL}/api/descuentos/campanas'
    req = urllib.request.Request(url, headers={'User-Agent': 'el-gadget-pipeline'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise RuntimeError(f'HTTP {r.status}')
        return json.loads(r.read().decode('utf-8')).get('campanas') or []


def escribir(campanas: list) -> int:
    """Reemplaza las campañas programadas del repo por las de la API.

    Borra solo las filas sin código: si alguna vez hubiera un código en el
    catalogo.db versionado, no es asunto de este script.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM descuentos WHERE codigo IS NULL')
        for c in campanas:
            cur.execute(
                f"INSERT INTO descuentos ({', '.join(CAMPOS)}) "
                f"VALUES ({', '.join('?' * len(CAMPOS))})",
                tuple(c.get(k) for k in CAMPOS))
        conn.commit()
        return len(campanas)
    finally:
        conn.close()


def main() -> int:
    print('=' * 70)
    print('  SINCRONIZACIÓN DE CAMPAÑAS DE DESCUENTO')
    print('=' * 70)
    if not DB_PATH.exists():
        print(f'⛔ No existe {DB_PATH}')
        return 1

    print(f'🌐 Consultando {API_URL}/api/descuentos/campanas …')
    try:
        campanas = traer_campanas()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, RuntimeError, ValueError) as e:
        print(f'⚠️  No se pudo consultar la API ({e}). Se deja el repo como está: '
              'borrar campañas por un timeout publicaría precio de lista en medio '
              'de una promoción.')
        return 0

    n = escribir(campanas)
    if not n:
        print('✅ Sin campañas vigentes hoy (el catálogo va a precio de lista).')
        return 0

    print(f'✅ {n} campaña(s) vigente(s) copiada(s) al repo:')
    for c in campanas:
        signo = '%' if c.get('tipo') == 'porcentaje' else '$'
        alcance = c.get('alcance')
        if alcance == 'skus':
            try:
                detalle = f"{len(json.loads(c.get('skus') or '[]'))} SKU(s)"
            except ValueError:
                detalle = 'SKUs ilegibles'
        elif alcance == 'categoria':
            detalle = f"categoría {c.get('categoria')}"
        else:
            detalle = 'todo el catálogo'
        print(f"   · {c.get('nombre')}: -{c.get('valor')}{signo} sobre {detalle} "
              f"({c.get('fecha_inicio') or 'sin inicio'} → {c.get('fecha_fin') or 'sin fin'})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
