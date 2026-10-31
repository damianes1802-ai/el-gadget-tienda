# -*- coding: utf-8 -*-
"""
Configuración común de los tests del sistema de insumos.

DOS REGLAS QUE ESTOS TESTS RESPETAN

1. Cada test corre sobre su propia base en un temporal. Nunca se toca
   `data/insumos.db` (los datos del socio) ni `data/catalogo.db` (el catálogo
   de El Gadget, que está versionado y es público).

2. Todos los datos de ejemplo son INVENTADOS. El repositorio es público y los
   costos y el stock del socio son datos comerciales suyos: no entran a git ni
   siquiera como fixture.

La autenticación se apaga reasignando el símbolo del módulo, no por variable
de entorno: la API lee `config/.env` si existe, así que una env var no
alcanzaría en la máquina de Damián.
"""

import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

from insumos_app import api as api_mod  # noqa: E402
from insumos_app import db  # noqa: E402

api_mod.INSUMOS_PASSWORD = ""  # tests sin credencial


# ════════════════════════════════════════════════════════════════════════════
# FIXTURES DE BASE
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Conexión a una base temporal, con el esquema ya creado."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "insumos_test.db")
    db.migrar()
    conexion = db.conectar()
    yield conexion
    conexion.close()


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """TestClient de FastAPI contra una base temporal."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "insumos_api.db")
    db.migrar()
    with TestClient(api_mod.app) as c:
        yield c


# ════════════════════════════════════════════════════════════════════════════
# LA INVARIANTE CENTRAL
# ════════════════════════════════════════════════════════════════════════════

def assert_libro_mayor_cierra(conexion):
    """`insumo.stock_unidades` tiene que ser la suma de sus movimientos.

    Se exige igualdad EXACTA, no aproximada: `db.recalcular_stock` escribe
    literalmente el resultado de la misma suma que hace la auditoría, así que
    cualquier diferencia significa que algún camino de escritura tocó el stock
    sin pasar por el libro mayor. Eso es el bug que esta invariante existe
    para atrapar, y una tolerancia lo esconderia.
    """
    filas = db.auditar_libro_mayor(conexion)
    for f in filas:
        assert f["stock_unidades"] == f["suma_movimientos"], (
            f"El insumo {f['insumo_id']} ({f['nombre']}) tiene stock "
            f"{f['stock_unidades']} pero sus movimientos suman "
            f"{f['suma_movimientos']}: alguien escribió stock sin asentar movimiento"
        )
        assert f["ok"]
    return filas


# ════════════════════════════════════════════════════════════════════════════
# DATOS DE EJEMPLO (INVENTADOS)
# ════════════════════════════════════════════════════════════════════════════

def crear_insumo(
    conexion,
    nombre,
    modo_stock="unidad",
    peso_unitario_g=1.0,
    alerta=0,
    costo=None,
    unidad_compra=None,
):
    cur = conexion.execute(
        """INSERT INTO insumo (nombre, modo_stock, peso_unitario_g,
                               alerta_cuando_queden, costo_compra, unidad_compra, creado_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nombre, modo_stock, peso_unitario_g, alerta, costo, unidad_compra, db.ahora_iso()),
    )
    return int(cur.lastrowid)


def crear_articulo(
    conexion,
    nombre,
    largo=100.0,
    ancho=80.0,
    alto=40.0,
    doblado=False,
    emb=None,
    margen=1.05,
    sku_elgadget=None,
    sku_afd=None,
):
    emb = emb or (None, None, None)
    cur = conexion.execute(
        """INSERT INTO articulo (nombre, sku_afd, sku_elgadget,
                                 largo_real_mm, ancho_real_mm, alto_real_mm,
                                 se_embala_doblado, largo_emb_mm, ancho_emb_mm, alto_emb_mm,
                                 margen_embalaje, creado_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nombre, sku_afd, sku_elgadget, largo, ancho, alto,
         1 if doblado else 0, emb[0], emb[1], emb[2], margen, db.ahora_iso()),
    )
    return int(cur.lastrowid)


def poner_receta(conexion, articulo_id, lineas):
    """`lineas` es [(insumo_id, cantidad), ...] en UNIDADES del insumo."""
    for insumo_id, cantidad in lineas:
        conexion.execute(
            """INSERT INTO receta (articulo_id, insumo_id, cantidad) VALUES (?, ?, ?)
               ON CONFLICT(articulo_id, insumo_id) DO UPDATE SET cantidad = excluded.cantidad""",
            (articulo_id, insumo_id, cantidad),
        )


def crear_mapeo(conexion, articulo_id, canal, id_externo, variacion=""):
    cur = conexion.execute(
        """INSERT INTO mapeo_canal (articulo_id, canal, id_externo, variacion_externa, creado_at)
           VALUES (?, ?, ?, ?, ?)""",
        (articulo_id, canal, id_externo, variacion, db.ahora_iso()),
    )
    return int(cur.lastrowid)


@pytest.fixture
def taller(conn):
    """Un taller chico y completo, con todo inventado.

    Dos insumos por peso (caireles y cadena), dos por unidad (argollas y
    cinta), y dos artículos: una borla normal y una guirnalda que se embala
    doblada.
    """
    ids = {
        "cairel": crear_insumo(conn, "Cairel de vidrio 10 mm", "peso", 2.5,
                               alerta=0.5, costo=18000, unidad_compra="kg"),
        "cadena": crear_insumo(conn, "Cadena dorada eslabón fino", "peso", 1.8,
                               alerta=0.2, costo=24000, unidad_compra="kg"),
        "argolla": crear_insumo(conn, "Argolla 8 mm", "unidad", 0.4,
                                alerta=50, costo=35, unidad_compra="unidad"),
        "cinta": crear_insumo(conn, "Cinta de yute 15 mm", "unidad", 12.0,
                              alerta=10, costo=900, unidad_compra="unidad"),
    }
    ids["borla"] = crear_articulo(
        conn, "Sujeta cortina borla trenzada",
        largo=180.0, ancho=60.0, alto=50.0, sku_elgadget="AFD-20", sku_afd="BORLA-01",
    )
    ids["guirnalda"] = crear_articulo(
        conn, "Guirnalda de caireles 2 m",
        largo=2000.0, ancho=60.0, alto=20.0,
        doblado=True, emb=(250.0, 250.0, 60.0), sku_elgadget="AFD-21",
    )

    poner_receta(conn, ids["borla"], [(ids["cairel"], 6), (ids["argolla"], 2), (ids["cinta"], 1)])
    poner_receta(conn, ids["guirnalda"], [(ids["cairel"], 40), (ids["cadena"], 25)])

    crear_mapeo(conn, ids["borla"], "ml", "MLA100000001")
    crear_mapeo(conn, ids["guirnalda"], "ml", "MLA100000002", "VAR-DORADO")

    return ids
