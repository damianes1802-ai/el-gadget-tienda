# -*- coding: utf-8 -*-
"""
DATOS DE EJEMPLO — Así Fue Deco

Carga un catálogo inventado para poder recorrer la interfaz con pantallas
llenas: insumos de los dos modos de stock, uno en alerta y otro en negativo,
artículos con y sin receta, un artículo que se embala doblado, un artículo con
DOS publicaciones de Mercado Libre y una venta que quedó pendiente de receta.

**TODO ACÁ ES INVENTADO.** El repositorio `damianes1802-ai/el-gadget-tienda` es
PÚBLICO y el costo y el stock de los insumos son datos comerciales del socio:
no se commitean nunca. Los nombres, los pesos y los precios de este archivo no
son los suyos, son plausibles y nada más.

CORRER

    python -m insumos_app.datos_ejemplo

Escribe en la base que tenga configurada `insumos_app.db` (por defecto
`data/insumos.db`, gitignoreada). Si la base ya tiene insumos, NO hace nada:
sobrescribir el inventario real de alguien con datos de demostración sería un
desastre silencioso. Para forzarlo sobre una base propia:

    python -m insumos_app.datos_ejemplo --forzar
    python -m insumos_app.datos_ejemplo --db C:\\tmp\\demo.db
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from insumos_app import calculos, db, stock


# ════════════════════════════════════════════════════════════════════════════
# EL CATÁLOGO INVENTADO
# ════════════════════════════════════════════════════════════════════════════

CATEGORIAS = [
    ("Caireles", 1, ["De vidrio", "De acrílico"]),
    ("Cadenas", 2, ["De metal", "Plástica"]),
    ("Argollas", 3, []),
    ("Cintas", 4, ["De gros", "De yute"]),
    ("Herrajes", 5, []),
]

# (nombre, categoría, subcategoría, modo, peso_g, umbral, costo, unidad_compra,
#  medidas_mm, stock_inicial)
INSUMOS = [
    ("Cairel de vidrio gota 20 mm", "Caireles", "De vidrio",
     "peso", 2.5, 0.5, 18500, "kg", (20, 10, 10), 2.4),
    ("Cairel de acrílico facetado 14 mm", "Caireles", "De acrílico",
     "peso", 1.1, 0.3, 9200, "kg", (14, 8, 8), 0.26),
    ("Eslabón de cadena dorada", "Cadenas", "De metal",
     "peso", 1.8, 0.4, 14300, "kg", (12, 7, 2), 1.2),
    ("Argolla niquelada 8 mm", "Argollas", None,
     "unidad", 0.6, 200, 11, "unidad", (8, 8, 1), 850),
    ("Cinta de gros 15 mm (por metro)", "Cintas", "De gros",
     "unidad", 4.2, 30, 320, "unidad", (1000, 15, 1), 120),
    ("Borla de hilo 7 cm", "Cintas", None,
     "unidad", 9.5, 40, 540, "unidad", (70, 25, 25), 35),
    ("Sujetador con imán 18 mm", "Herrajes", None,
     "unidad", 12.0, 25, 890, "unidad", (18, 18, 6), 60),
    ("Pesa de mantel de cerámica", "Herrajes", None,
     "unidad", 46.0, 20, 1250, "unidad", (40, 40, 14), 48),
]

# (nombre, sku_elgadget, sku_afd, medidas_reales, doblado, medidas_embaladas,
#  receta [(insumo, cantidad)])
ARTICULOS = [
    ("Guirnalda de caireles 2 m", "AFD-21", "GUIR-2M",
     (2000, 60, 20), True, (250, 250, 60),
     [("Cairel de vidrio gota 20 mm", 40), ("Eslabón de cadena dorada", 25)]),

    ("Borla sujeta cortina", "AFD-20", "BORLA-01",
     (180, 70, 70), False, None,
     [("Borla de hilo 7 cm", 1), ("Argolla niquelada 8 mm", 2),
      ("Cinta de gros 15 mm (por metro)", 1)]),

    ("Servilleteros de caireles (juego de 4)", "AFD-22", "SERV-4",
     (120, 60, 60), False, None,
     [("Cairel de acrílico facetado 14 mm", 24), ("Argolla niquelada 8 mm", 4)]),

    ("Pesas de mantel (juego de 4)", "AFD-23", "PESA-4",
     (160, 80, 50), False, None,
     [("Pesa de mantel de cerámica", 4), ("Cinta de gros 15 mm (por metro)", 2)]),

    ("Sujeta cortina con imán (par)", "AFD-24", "IMAN-2",
     (200, 60, 40), False, None,
     [("Sujetador con imán 18 mm", 2), ("Cinta de gros 15 mm (por metro)", 2),
      ("Cairel de vidrio gota 20 mm", 6)]),

    # A propósito sin receta: así la interfaz muestra el aviso de que no hay
    # peso y la alerta de "artículos sin receta" tiene de qué hablar.
    ("Guirnalda de luces deco 3 m", "AFD-25", "LUZ-3M",
     (3000, 40, 30), True, (300, 300, 50), []),
]

# (articulo, canal, id_externo, variacion)
# Dos publicaciones de Mercado Libre hacia la MISMA guirnalda: es el caso real
# del socio —un producto publicado dos veces en la misma cuenta, con ventas en
# las dos— y la interfaz tiene que mostrarlo como lo que es, una lista.
MAPEOS = [
    ("Guirnalda de caireles 2 m", "ml", "MLA111111111", ""),
    ("Guirnalda de caireles 2 m", "ml", "MLA222222222", ""),
    ("Borla sujeta cortina", "ml", "MLA333333333", "VAR-BEIGE"),
    ("Borla sujeta cortina", "ml", "MLA333333333", "VAR-NEGRO"),
    ("Servilleteros de caireles (juego de 4)", "empretienda", "9001", ""),
    ("Guirnalda de luces deco 3 m", "ml", "MLA444444444", ""),
]


def cargar(conn) -> None:
    # La `fecha_corte` la fija la primera carga de inventario, que acá es hoy,
    # así que las ventas de ejemplo tienen que ser de hoy para que descuenten.
    # Una sí va con fecha vieja, a propósito: es el único modo de que la
    # pantalla muestre el estado `ignorada_fecha_corte`.
    hoy = date.today().isoformat()
    hace_un_mes = (date.today() - timedelta(days=30)).isoformat()

    # ── Taxonomía ───────────────────────────────────────────────────────
    ids_categoria, ids_subcategoria = {}, {}
    for nombre, orden, subs in CATEGORIAS:
        cur = conn.execute(
            "INSERT INTO categoria (nombre, orden) VALUES (?, ?)", (nombre, orden)
        )
        ids_categoria[nombre] = int(cur.lastrowid)
        for i, sub in enumerate(subs, start=1):
            cur = conn.execute(
                "INSERT INTO subcategoria (categoria_id, nombre, orden) VALUES (?, ?, ?)",
                (ids_categoria[nombre], sub, i),
            )
            ids_subcategoria[(nombre, sub)] = int(cur.lastrowid)
    print(f"  {len(CATEGORIAS)} categorías")

    # ── Insumos, con su stock por el libro mayor ────────────────────────
    ids_insumo = {}
    for (nombre, cat, sub, modo, peso, umbral, costo, unidad_compra,
         medidas, inicial) in INSUMOS:
        cur = conn.execute(
            """INSERT INTO insumo
                   (nombre, categoria_id, subcategoria_id, modo_stock, peso_unitario_g,
                    largo_mm, ancho_mm, alto_mm, alerta_cuando_queden,
                    costo_compra, unidad_compra, activo, creado_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (nombre, ids_categoria.get(cat), ids_subcategoria.get((cat, sub)),
             modo, peso, medidas[0], medidas[1], medidas[2], umbral,
             costo, unidad_compra, db.ahora_iso()),
        )
        insumo_id = int(cur.lastrowid)
        ids_insumo[nombre] = insumo_id

        # El stock entra como movimiento, nunca escrito en la columna: es la
        # misma regla que respeta la API, y es lo que hace que la auditoría
        # cuadre también con los datos de ejemplo.
        stock.asegurar_fecha_corte(conn)
        db.registrar_movimiento(
            conn, insumo_id,
            calculos.a_unidades(inicial, modo, peso),
            "inventario_inicial",
            usuario="carga de ejemplo",
            nota="Inventario inicial de ejemplo",
        )
    print(f"  {len(INSUMOS)} insumos con su inventario inicial")

    # ── Artículos y recetas ─────────────────────────────────────────────
    ids_articulo = {}
    for (nombre, sku_eg, sku_afd, reales, doblado, embaladas, receta) in ARTICULOS:
        cur = conn.execute(
            """INSERT INTO articulo
                   (nombre, sku_afd, sku_elgadget, id_empretienda,
                    largo_real_mm, ancho_real_mm, alto_real_mm,
                    se_embala_doblado, largo_emb_mm, ancho_emb_mm, alto_emb_mm,
                    margen_embalaje, activo, creado_at)
               VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (nombre, sku_afd, sku_eg,
             reales[0], reales[1], reales[2],
             1 if doblado else 0,
             embaladas[0] if embaladas else None,
             embaladas[1] if embaladas else None,
             embaladas[2] if embaladas else None,
             db.margen_embalaje_default(conn), db.ahora_iso()),
        )
        articulo_id = int(cur.lastrowid)
        ids_articulo[nombre] = articulo_id
        for insumo, cantidad in receta:
            conn.execute(
                "INSERT INTO receta (articulo_id, insumo_id, cantidad) VALUES (?, ?, ?)",
                (articulo_id, ids_insumo[insumo], cantidad),
            )
    print(f"  {len(ARTICULOS)} artículos ({sum(1 for a in ARTICULOS if not a[6])} sin receta a propósito)")

    # ── Publicaciones ───────────────────────────────────────────────────
    for articulo, canal, id_externo, variacion in MAPEOS:
        conn.execute(
            """INSERT INTO mapeo_canal
                   (articulo_id, canal, id_externo, variacion_externa, creado_at)
               VALUES (?, ?, ?, ?, ?)""",
            (ids_articulo[articulo], canal, id_externo, variacion, db.ahora_iso()),
        )
    conn.commit()
    print(f"  {len(MAPEOS)} publicaciones (dos de ML al mismo artículo)")

    # ── Ventas, por el motor de verdad ──────────────────────────────────
    # Nada de INSERT a mano acá: pasan por `procesar_venta` para que el libro
    # mayor quede consistente y los estados sean los reales.
    ventas = [
        ("manual", "manual-ejemplo-01",
         [{"articulo_id": ids_articulo["Borla sujeta cortina"], "cantidad": 3}]),
        ("ml", "3000001",
         [{"id_externo_item": "MLA111111111", "cantidad": 1}]),
        # La segunda publicación del mismo artículo también descuenta: la
        # idempotencia es por ORDEN, no por publicación.
        ("ml", "3000002",
         [{"id_externo_item": "MLA222222222", "cantidad": 2}]),
        # Esta queda pendiente de receta: el artículo existe y está mapeado,
        # pero no tiene receta cargada. No descuenta NADA.
        ("ml", "3000003",
         [{"id_externo_item": "MLA444444444", "cantidad": 1}]),
        # Una venta sin publicación mapeada: queda pendiente de mapeo.
        ("ml", "3000004",
         [{"id_externo_item": "MLA999999999", "cantidad": 1}]),
    ]
    estados = {}
    for canal, id_externo, items in ventas:
        r = stock.procesar_venta(conn, canal, id_externo, items, fecha_venta=hoy)
        estados[r["estado"]] = estados.get(r["estado"], 0) + 1

    # Anterior a la fecha de corte: queda registrada y NO descuenta. Es una
    # decisión del sistema, no un pendiente, así que tampoco se reprocesa.
    r = stock.procesar_venta(
        conn, "manual", "manual-ejemplo-04",
        [{"articulo_id": ids_articulo["Borla sujeta cortina"], "cantidad": 5}],
        fecha_venta=hace_un_mes,
    )
    estados[r["estado"]] = estados.get(r["estado"], 0) + 1
    print(f"  {len(ventas) + 1} ventas: " + ", ".join(f"{v} {k}" for k, v in sorted(estados.items())))

    # Una venta cancelada, para que la pantalla de cancelaciones tenga qué
    # mostrar y se vea la restitución en el historial del insumo.
    stock.procesar_venta(
        conn, "manual", "manual-ejemplo-02",
        [{"articulo_id": ids_articulo["Servilleteros de caireles (juego de 4)"], "cantidad": 1}],
        fecha_venta=hoy,
    )
    stock.cancelar_venta(conn, "manual", "manual-ejemplo-02",
                         motivo="Ejemplo: la clienta se arrepintió")
    print("  1 venta cancelada con su stock restituido")

    # Y un insumo en negativo: se vendió material que no estaba cargado. El
    # sistema lo permite a propósito (rechazarlo sería perder el dato real) y
    # lo reporta como alerta; la interfaz tiene que mostrarlo en rojo.
    db.registrar_movimiento(
        conn, ids_insumo["Cinta de gros 15 mm (por metro)"], -135.0, "venta",
        origen_canal="manual", referencia_externa="manual-ejemplo-03",
        nota="Ejemplo: consumo que dejó el stock en negativo",
    )
    conn.commit()
    print("  1 insumo en negativo y 2 por debajo del umbral")


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga datos de ejemplo inventados.")
    parser.add_argument("--db", help="Ruta de la base (por defecto, la del sistema)")
    parser.add_argument("--forzar", action="store_true",
                        help="Carga aunque la base ya tenga datos")
    args = parser.parse_args()

    if args.db:
        db.DB_PATH = Path(args.db)

    db.migrar()
    conn = db.conectar()
    try:
        existentes = conn.execute("SELECT COUNT(*) FROM insumo").fetchone()[0]
        if existentes and not args.forzar:
            print(f"La base {db.DB_PATH} ya tiene {existentes} insumos: no se toca nada.")
            print("Si es una base de prueba y querés agregar los ejemplos igual, usá --forzar.")
            return 1

        print(f"Cargando datos de ejemplo en {db.DB_PATH}")
        cargar(conn)
        print("\nListo. Levantá la API y abrí la interfaz:")
        print("  python -m insumos_app.api")
        print("  http://localhost:8010/app/")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
