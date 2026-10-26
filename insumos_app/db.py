# -*- coding: utf-8 -*-
"""
BASE DE DATOS DEL SISTEMA DE INSUMOS — Así Fue Deco

Esquema, conexión y migraciones. Ver `docs/ESPECIFICACION.md` para el diseño
funcional; acá está solo la traducción a SQLite y las invariantes que el
esquema defiende por sí mismo.

DÓNDE VIVE LA BASE
    `data/insumos.db`, que cae bajo el `data/*` del .gitignore del repo. El
    repositorio es PÚBLICO y el costo de los insumos y el stock son datos
    comerciales del socio: no se commitean nunca. La variable de entorno
    `INSUMOS_DB_PATH` permite apuntar a otro archivo (los tests la usan).

TRES INVARIANTES QUE ESTÁN EN EL ESQUEMA, NO EN LA APLICACIÓN
    1. `insumo.peso_unitario_g > 0` siempre, incluso si `modo_stock = 'peso'`.
       Es el divisor de la conversión kg → unidades: un 0 ahí es una división
       por cero y un NULL es un peso de envío silenciosamente incompleto.
    2. `movimiento_stock` es el libro mayor. `insumo.stock_unidades` no se
       modifica nunca "a mano": se recalcula como la suma de los movimientos
       del insumo (ver `recalcular_stock`). Así la invariante
       "stock == Σ movimientos" no se *mantiene*, se cumple por construcción.
    3. `venta_procesada` tiene clave primaria `(canal, id_externo)`. La
       idempotencia del descuento la garantiza el índice único, no un
       `if` que se puede olvidar.

HORARIOS
    Las fechas se guardan en hora local (ART), no en UTC como el resto del
    repo. Este sistema lo mira una persona y define la `fecha_corte` por día
    calendario: un `datetime('now')` de SQLite (UTC) correría el borde del día
    tres horas y las ventas de la noche del día de corte caerían del lado
    equivocado.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Canales que pueden originar una venta. `mapeo_canal` solo acepta los tres
# primeros: una venta 'manual' se carga eligiendo el artículo en pantalla, así
# que no necesita (ni puede tener) un identificador externo mapeado.
CANALES_VENTA = ("ml", "elgadget", "empretienda", "manual")
CANALES_MAPEABLES = ("ml", "elgadget", "empretienda")

MODOS_STOCK = ("peso", "unidad")
UNIDADES_COMPRA = ("kg", "unidad")

# Tipos de movimiento del libro mayor.
#   inventario_inicial  la carga física que fija la `fecha_corte`
#   ingreso             compra de insumo
#   venta               consumo derivado de una venta (siempre negativo)
#   ajuste              corrección de inventario (el delta, no el absoluto)
#   merma               rotura o descarte
#   devolucion          reversa de una venta
TIPOS_MOVIMIENTO = (
    "inventario_inicial",
    "ingreso",
    "venta",
    "ajuste",
    "merma",
    "devolucion",
)

ESTADOS_VENTA = (
    "procesada",
    "pendiente_receta",
    "pendiente_mapeo",
    "ignorada_fecha_corte",
)

MARGEN_EMBALAJE_DEFAULT = 1.05

SCHEMA_VERSION = 1


def _ruta_inicial() -> Path:
    override = os.environ.get("INSUMOS_DB_PATH", "").strip()
    if override:
        return Path(override)
    return DATA_DIR / "insumos.db"


# Global de módulo a propósito (mismo patrón que `api_local.DB_PATH`): los
# tests la reapuntan a un archivo temporal. Por eso el resto del paquete
# siempre llama a `db.conectar()` y nunca importa `DB_PATH` por valor.
DB_PATH = _ruta_inicial()


# ════════════════════════════════════════════════════════════════════════════
# CONEXIÓN
# ════════════════════════════════════════════════════════════════════════════

def conectar(ruta: Optional[Path] = None) -> sqlite3.Connection:
    """Abre una conexión lista para usar.

    `isolation_level=None` desactiva las transacciones implícitas de Python:
    cada sentencia suelta hace autocommit y las operaciones de varios pasos
    abren su transacción explícita con `transaccion()`. Sin esto, un
    `BEGIN IMMEDIATE` dentro del motor de stock choca con la transacción que
    Python ya había abierto solo.

    `foreign_keys` viene apagado por conexión en SQLite y el esquema se apoya
    en las FK (el `ON DELETE CASCADE` de `receta` y `mapeo_canal`), así que se
    enciende acá.
    """
    destino = Path(ruta) if ruta else DB_PATH
    destino.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(destino, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaccion(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transacción explícita para las operaciones de varios pasos.

    `IMMEDIATE` toma el lock de escritura al abrir, no en la primera
    escritura: dos procesos descontando la misma venta a la vez fallan al
    entrar en vez de a mitad de camino.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


# ════════════════════════════════════════════════════════════════════════════
# ESQUEMA
# ════════════════════════════════════════════════════════════════════════════

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS categoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT    NOT NULL UNIQUE,
    orden   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subcategoria (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL REFERENCES categoria(id) ON DELETE CASCADE,
    nombre       TEXT    NOT NULL,
    orden        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (categoria_id, nombre)
);

-- `modo_stock` es un campo propio y no una subcategoría: "de vidrio" dice qué
-- ES el insumo y "por peso" dice cómo se CUENTA. En la misma lista, un cairel
-- de vidrio comprado por peso tendría que elegir y se perdería un dato.
CREATE TABLE IF NOT EXISTS insumo (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre               TEXT    NOT NULL,
    categoria_id         INTEGER REFERENCES categoria(id),
    subcategoria_id      INTEGER REFERENCES subcategoria(id),
    modo_stock           TEXT    NOT NULL CHECK (modo_stock IN ('peso', 'unidad')),
    peso_unitario_g      REAL    NOT NULL CHECK (peso_unitario_g > 0),
    largo_mm             REAL,
    ancho_mm             REAL,
    alto_mm              REAL,
    stock_unidades       REAL    NOT NULL DEFAULT 0,
    alerta_cuando_queden REAL    NOT NULL DEFAULT 0,
    costo_compra         REAL,
    unidad_compra        TEXT    CHECK (unidad_compra IS NULL OR unidad_compra IN ('kg', 'unidad')),
    activo               INTEGER NOT NULL DEFAULT 1,
    creado_at            TEXT    NOT NULL,
    actualizado_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_insumo_categoria    ON insumo(categoria_id);
CREATE INDEX IF NOT EXISTS idx_insumo_subcategoria ON insumo(subcategoria_id);
CREATE INDEX IF NOT EXISTS idx_insumo_activo       ON insumo(activo);

-- Las medidas reales son obligatorias y las tres: Correo Argentino cotiza con
-- peso volumétrico y tiene topes de tamaño por servicio, así que con dos
-- dimensiones no se puede cotizar.
-- Si el artículo se embala doblado, las tres medidas embaladas pasan a ser
-- obligatorias: el CHECK evita el caso "se_embala_doblado = 1 y medidas
-- embaladas vacías", que haría cotizar una guirnalda de 2 m estirada.
CREATE TABLE IF NOT EXISTS articulo (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL,
    sku_afd           TEXT,
    sku_elgadget      TEXT,
    id_empretienda    TEXT,
    largo_real_mm     REAL    NOT NULL CHECK (largo_real_mm > 0),
    ancho_real_mm     REAL    NOT NULL CHECK (ancho_real_mm > 0),
    alto_real_mm      REAL    NOT NULL CHECK (alto_real_mm  > 0),
    se_embala_doblado INTEGER NOT NULL DEFAULT 0,
    largo_emb_mm      REAL,
    ancho_emb_mm      REAL,
    alto_emb_mm       REAL,
    margen_embalaje   REAL    NOT NULL DEFAULT {MARGEN_EMBALAJE_DEFAULT} CHECK (margen_embalaje >= 1),
    activo            INTEGER NOT NULL DEFAULT 1,
    creado_at         TEXT    NOT NULL,
    actualizado_at    TEXT,
    CHECK (
        se_embala_doblado = 0
        OR (largo_emb_mm IS NOT NULL AND largo_emb_mm > 0
            AND ancho_emb_mm IS NOT NULL AND ancho_emb_mm > 0
            AND alto_emb_mm  IS NOT NULL AND alto_emb_mm  > 0)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_articulo_sku_afd
    ON articulo(sku_afd) WHERE sku_afd IS NOT NULL AND sku_afd <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_articulo_sku_elgadget
    ON articulo(sku_elgadget) WHERE sku_elgadget IS NOT NULL AND sku_elgadget <> '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_articulo_id_empretienda
    ON articulo(id_empretienda) WHERE id_empretienda IS NOT NULL AND id_empretienda <> '';

CREATE TABLE IF NOT EXISTS receta (
    articulo_id INTEGER NOT NULL REFERENCES articulo(id) ON DELETE CASCADE,
    insumo_id   INTEGER NOT NULL REFERENCES insumo(id),
    cantidad    REAL    NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (articulo_id, insumo_id)
);

CREATE INDEX IF NOT EXISTS idx_receta_insumo ON receta(insumo_id);

-- Una publicación de Mercado Libre con variantes necesita una fila por
-- variante. `variacion_externa` es '' y no NULL porque SQLite considera
-- distintos dos NULL en un UNIQUE: con NULL se podrían cargar dos mapeos
-- idénticos sin variante.
CREATE TABLE IF NOT EXISTS mapeo_canal (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id       INTEGER NOT NULL REFERENCES articulo(id) ON DELETE CASCADE,
    canal             TEXT    NOT NULL CHECK (canal IN ('ml', 'elgadget', 'empretienda')),
    id_externo        TEXT    NOT NULL,
    variacion_externa TEXT    NOT NULL DEFAULT '',
    creado_at         TEXT    NOT NULL,
    UNIQUE (canal, id_externo, variacion_externa)
);

CREATE INDEX IF NOT EXISTS idx_mapeo_articulo ON mapeo_canal(articulo_id);

-- EL LIBRO MAYOR. `cantidad_unidades` positiva es ingreso y negativa egreso.
-- Siempre en unidades, también para los insumos de modo 'peso': la conversión
-- a kilos vive en la capa de presentación (ver `calculos.py`).
CREATE TABLE IF NOT EXISTS movimiento_stock (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_id          INTEGER NOT NULL REFERENCES insumo(id),
    cantidad_unidades  REAL    NOT NULL,
    tipo               TEXT    NOT NULL CHECK (tipo IN (
                           'inventario_inicial', 'ingreso', 'venta',
                           'ajuste', 'merma', 'devolucion')),
    origen_canal       TEXT,
    referencia_externa TEXT,
    articulo_id        INTEGER REFERENCES articulo(id),
    fecha              TEXT    NOT NULL,
    usuario            TEXT,
    nota               TEXT
);

-- El índice no es un lujo: `recalcular_stock` suma todos los movimientos del
-- insumo después de cada movimiento.
CREATE INDEX IF NOT EXISTS idx_movimiento_insumo ON movimiento_stock(insumo_id);
CREATE INDEX IF NOT EXISTS idx_movimiento_fecha  ON movimiento_stock(fecha);
CREATE INDEX IF NOT EXISTS idx_movimiento_ref    ON movimiento_stock(origen_canal, referencia_externa);

-- La idempotencia del descuento. Mercado Libre va a devolver la misma orden
-- más de una vez (reintentos, ventanas de consulta superpuestas) y sin esta
-- tabla el stock se descuenta dos veces.
-- `items_json` guarda los ítems tal como llegaron, para poder reprocesar una
-- venta que quedó pendiente de receta o de mapeo sin pedirle al canal que la
-- mande de nuevo.
CREATE TABLE IF NOT EXISTS venta_procesada (
    canal         TEXT NOT NULL CHECK (canal IN ('ml', 'elgadget', 'empretienda', 'manual')),
    id_externo    TEXT NOT NULL,
    estado        TEXT NOT NULL CHECK (estado IN (
                      'procesada', 'pendiente_receta',
                      'pendiente_mapeo', 'ignorada_fecha_corte')),
    fecha_venta   TEXT,
    fecha_proceso TEXT NOT NULL,
    items_json    TEXT,
    detalle       TEXT,
    PRIMARY KEY (canal, id_externo)
);

CREATE INDEX IF NOT EXISTS idx_venta_estado ON venta_procesada(estado);
CREATE INDEX IF NOT EXISTS idx_venta_fecha  ON venta_procesada(fecha_venta);

CREATE TABLE IF NOT EXISTS config (
    clave          TEXT PRIMARY KEY,
    valor          TEXT,
    actualizado_at TEXT
);
"""


def migrar(conn: Optional[sqlite3.Connection] = None) -> None:
    """Crea el esquema si falta y deja la base lista para usar.

    Idempotente: se puede llamar en cada arranque de la API.
    """
    propia = conn is None
    conn = conn or conectar()
    try:
        # WAL es persistente en el archivo: un lector no bloquea al escritor,
        # que es justo el caso de la pantalla de stock abierta mientras entra
        # una venta.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)

        if get_config(conn, "schema_version") is None:
            set_config(conn, "schema_version", str(SCHEMA_VERSION))
        if get_config(conn, "margen_embalaje_default") is None:
            set_config(conn, "margen_embalaje_default", str(MARGEN_EMBALAJE_DEFAULT))
    finally:
        if propia:
            conn.close()


# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

def get_config(conn: sqlite3.Connection, clave: str) -> Optional[str]:
    fila = conn.execute("SELECT valor FROM config WHERE clave = ?", (clave,)).fetchone()
    return fila["valor"] if fila else None


def set_config(conn: sqlite3.Connection, clave: str, valor: Optional[str]) -> None:
    conn.execute(
        """INSERT INTO config (clave, valor, actualizado_at) VALUES (?, ?, ?)
           ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor,
                                            actualizado_at = excluded.actualizado_at""",
        (clave, valor, ahora_iso()),
    )


def todas_las_config(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    filas = conn.execute("SELECT clave, valor FROM config ORDER BY clave").fetchall()
    return {f["clave"]: f["valor"] for f in filas}


def get_fecha_corte(conn: sqlite3.Connection) -> Optional[date]:
    """La fecha de la primera carga de stock. Las ventas anteriores se ignoran.

    Devuelve None mientras no haya ninguna carga: sin inventario cargado no
    hay nada que descontar contra qué, y el motor lo informa en vez de
    inventar un corte.
    """
    valor = get_config(conn, "fecha_corte")
    if not valor:
        return None
    return a_fecha(valor)


def margen_embalaje_default(conn: sqlite3.Connection) -> float:
    """Margen con el que nace un artículo que no declara el suyo.

    La especificación deja 1,05 por dimensión como lo pidió el socio, pero
    aplicar 1,05 a las tres infla el VOLUMEN un 15,8% (1,05³ = 1,158). Si
    algún día quiere 5% de volumen, el factor es 1,016 y se cambia acá, sin
    tocar código ni los artículos ya cargados.
    """
    valor = get_config(conn, "margen_embalaje_default")
    try:
        return float(valor) if valor else MARGEN_EMBALAJE_DEFAULT
    except (TypeError, ValueError):
        return MARGEN_EMBALAJE_DEFAULT


# ════════════════════════════════════════════════════════════════════════════
# FECHAS
# ════════════════════════════════════════════════════════════════════════════

def ahora_iso() -> str:
    """Timestamp local (ART) con precisión de segundos. Ver nota del módulo."""
    return datetime.now().isoformat(timespec="seconds")


def hoy_iso() -> str:
    return date.today().isoformat()


def a_fecha(valor: Any) -> Optional[date]:
    """Normaliza a `date` lo que venga: `date`, `datetime` o texto ISO.

    Mercado Libre devuelve `2026-10-20T14:33:00.000-03:00` y otros canales
    mandan solo `2026-10-20`. La comparación contra `fecha_corte` es por día
    calendario, así que todo se reduce a la parte de fecha.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    texto = str(valor).strip()
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


# ════════════════════════════════════════════════════════════════════════════
# LIBRO MAYOR
# ════════════════════════════════════════════════════════════════════════════

def registrar_movimiento(
    conn: sqlite3.Connection,
    insumo_id: int,
    cantidad_unidades: float,
    tipo: str,
    *,
    origen_canal: Optional[str] = None,
    referencia_externa: Optional[str] = None,
    articulo_id: Optional[int] = None,
    usuario: Optional[str] = None,
    nota: Optional[str] = None,
    fecha: Optional[str] = None,
) -> int:
    """Asienta un movimiento y recalcula el stock del insumo.

    ES EL ÚNICO CAMINO por el que `insumo.stock_unidades` cambia. Cualquier
    otro `UPDATE insumo SET stock_unidades = ...` rompe la invariante del
    libro mayor y deja un número que nadie puede explicar después.
    """
    if tipo not in TIPOS_MOVIMIENTO:
        raise ValueError(f"Tipo de movimiento desconocido: {tipo}")

    cur = conn.execute(
        """INSERT INTO movimiento_stock
               (insumo_id, cantidad_unidades, tipo, origen_canal,
                referencia_externa, articulo_id, fecha, usuario, nota)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            insumo_id,
            float(cantidad_unidades),
            tipo,
            origen_canal,
            referencia_externa,
            articulo_id,
            fecha or ahora_iso(),
            usuario,
            nota,
        ),
    )
    recalcular_stock(conn, insumo_id)
    return int(cur.lastrowid)


def recalcular_stock(conn: sqlite3.Connection, insumo_id: int) -> float:
    """Reescribe `insumo.stock_unidades` como la suma de sus movimientos.

    Sumar de nuevo en vez de hacer `stock = stock + delta` es deliberado: así
    el valor almacenado ES la suma del libro mayor, con la misma aritmética y
    el mismo orden que usa la auditoría, y la invariante no depende de que
    todos los caminos de escritura acierten el delta. A esta escala (miles de
    movimientos, con índice por insumo) el costo es irrelevante.
    """
    total = conn.execute(
        "SELECT COALESCE(SUM(cantidad_unidades), 0) FROM movimiento_stock WHERE insumo_id = ?",
        (insumo_id,),
    ).fetchone()[0]
    conn.execute(
        "UPDATE insumo SET stock_unidades = ?, actualizado_at = ? WHERE id = ?",
        (total, ahora_iso(), insumo_id),
    )
    return float(total)


def auditar_libro_mayor(conn: sqlite3.Connection) -> list:
    """Compara, insumo por insumo, el stock almacenado contra el libro mayor.

    La tolerancia existe porque la columna es REAL: `recalcular_stock` hace
    que los dos números salgan de la misma suma, pero un insumo cargado por
    una versión futura con otro camino de escritura aparecería acá.
    """
    filas = conn.execute(
        """SELECT i.id, i.nombre, i.stock_unidades,
                  COALESCE((SELECT SUM(m.cantidad_unidades)
                              FROM movimiento_stock m
                             WHERE m.insumo_id = i.id), 0) AS suma_movimientos
             FROM insumo i
            ORDER BY i.id"""
    ).fetchall()

    resultado = []
    for f in filas:
        diferencia = float(f["stock_unidades"]) - float(f["suma_movimientos"])
        resultado.append(
            {
                "insumo_id": f["id"],
                "nombre": f["nombre"],
                "stock_unidades": float(f["stock_unidades"]),
                "suma_movimientos": float(f["suma_movimientos"]),
                "diferencia": diferencia,
                "ok": abs(diferencia) < 1e-6,
            }
        )
    return resultado
