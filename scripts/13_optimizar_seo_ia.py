#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPTIMIZADOR SEO CON IA (Gemini API)

Reescribe nombre/descripcion de un lote de productos usando la API gratuita
de Gemini, para mejorar el copy de las paginas estaticas de producto.

Prioriza productos nunca optimizados (seo_optimizado_at IS NULL); una vez que
todos tienen fecha, recicla por los mas viejos primero.

Uso:
    python scripts/13_optimizar_seo_ia.py --limit 50
    python scripts/13_optimizar_seo_ia.py --limit 3 --dry-run
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('optimizador_seo_ia')

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "descripcion": {"type": "string"},
    },
    "required": ["titulo", "descripcion"],
}

PROMPT_TEMPLATE = """Sos un redactor de e-commerce especializado en SEO para Argentina.
Tu tarea es reescribir el titulo y la descripcion de un producto para la tienda online "El Gadget".

Datos actuales del producto:
- Nombre actual: {nombre}
- Descripcion actual: {descripcion}
- Categoria: {categoria}
- Subcategoria: {subcategoria}
- Marca: {marca}
- Color: {color}
- Talle: {talle}
- Precio de venta: ${precio_venta} ARS

Instrucciones:
- Tono argentino, natural, cercano, sin keyword-stuffing.
- "titulo": entre 50 y 70 caracteres, atractivo y SEO-friendly, manteniendo la identidad del producto
  (no inventes una marca o modelo distinto al original).
- "descripcion": entre 120 y 200 palabras, en parrafos cortos o bullets separados por saltos de
  linea (\\n), basada en los hechos del texto original (no inventes especificaciones nuevas),
  incluyendo palabras clave relevantes para busquedas en Argentina.
- Nunca menciones al proveedor ("Droppers" ni ningun otro nombre de proveedor). La marca de la
  tienda es siempre "El Gadget".
- Responde unicamente con el JSON solicitado, sin texto adicional.
"""


def conectar_db() -> sqlite3.Connection:
    db_path = Config.DATA_DIR / 'catalogo.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def asegurar_columna(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(productos)")
    columnas = {row[1] for row in cursor.fetchall()}
    if 'seo_optimizado_at' not in columnas:
        cursor.execute("ALTER TABLE productos ADD COLUMN seo_optimizado_at TIMESTAMP")
        conn.commit()


def obtener_lote(conn: sqlite3.Connection, limit: int) -> list:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sku, nombre, descripcion, categoria, subcategoria, marca, color, talle, precio_venta
        FROM productos
        WHERE stock > 0
        ORDER BY (seo_optimizado_at IS NULL) DESC, seo_optimizado_at ASC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cursor.fetchall()]


def obtener_por_skus(conn: sqlite3.Connection, skus: list) -> list:
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(skus))
    cursor.execute(f"""
        SELECT sku, nombre, descripcion, categoria, subcategoria, marca, color, talle, precio_venta
        FROM productos
        WHERE stock > 0 AND sku IN ({placeholders})
    """, skus)
    return [dict(row) for row in cursor.fetchall()]


def generar_copy(producto: dict, api_key: str, intentos: int = 4) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        nombre=producto['nombre'],
        descripcion=producto['descripcion'] or '',
        categoria=producto['categoria'] or '',
        subcategoria=producto['subcategoria'] or '',
        marca=producto['marca'] or '',
        color=producto['color'] or '',
        talle=producto['talle'] or '',
        precio_venta=producto['precio_venta'],
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }

    for intento in range(1, intentos + 1):
        response = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=60,
        )
        # Reintentar errores transitorios de permisos/cuota (la API key recien
        # creada puede tardar unos minutos en propagarse en todos los backends)
        if response.status_code in (403, 429, 500, 503) and intento < intentos:
            time.sleep(5 * intento)
            continue
        response.raise_for_status()
        data = response.json()
        break

    texto = data["candidates"][0]["content"]["parts"][0]["text"]
    resultado = json.loads(texto)

    titulo = resultado.get("titulo", "").strip()
    descripcion = resultado.get("descripcion", "").strip()

    if not titulo or not descripcion:
        raise ValueError(f"Respuesta vacia de Gemini: {resultado}")

    return {"titulo": titulo, "descripcion": descripcion}


def main():
    parser = argparse.ArgumentParser(description="Optimiza SEO de productos con Gemini API")
    parser.add_argument("--limit", type=int, default=50, help="Cantidad de productos a optimizar")
    parser.add_argument("--skus", help="Lista de SKUs separados por coma a optimizar (ignora --limit)")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en la base de datos")
    args = parser.parse_args()

    env = Config.cargar_env()
    api_key = env.get('GEMINI_API_KEY', '')
    if not api_key:
        raise SystemExit("Falta GEMINI_API_KEY en config/.env")

    conn = conectar_db()
    asegurar_columna(conn)

    if args.skus:
        skus = [s.strip() for s in args.skus.split(',') if s.strip()]
        productos = obtener_por_skus(conn, skus) if skus else []
    else:
        productos = obtener_lote(conn, args.limit)
    print(f"\n🔍 {len(productos)} productos seleccionados para optimizar\n")

    actualizados = 0
    errores = []

    for i, producto in enumerate(productos, 1):
        sku = producto['sku']
        print(f"[{i}/{len(productos)}] {sku} - {producto['nombre'][:60]}")

        try:
            copy = generar_copy(producto, api_key)
            print(f"  Nuevo titulo: {copy['titulo']}")
            print(f"  Nueva descripcion: {copy['descripcion'][:120]}...")

            if not args.dry_run:
                conn.execute(
                    "UPDATE productos SET nombre = ?, descripcion = ?, "
                    "seo_optimizado_at = datetime('now') WHERE sku = ?",
                    (copy['titulo'], copy['descripcion'], sku)
                )
                conn.commit()
            actualizados += 1

        except Exception as e:
            logger.error(f"Error optimizando {sku}: {e}")
            errores.append((sku, str(e)))
            print(f"  ⚠️  Error: {e}")

        if i < len(productos):
            time.sleep(4)

    conn.close()

    print("\n" + "=" * 50)
    print(f"✅ Productos optimizados: {actualizados}")
    print(f"⚠️  Errores: {len(errores)}")
    for sku, err in errores:
        print(f"   - {sku}: {err}")
    if args.dry_run:
        print("\n(dry-run: no se escribio nada en la base de datos)")


if __name__ == "__main__":
    main()
