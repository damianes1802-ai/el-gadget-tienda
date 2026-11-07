# -*- coding: utf-8 -*-
"""
API DEL SISTEMA DE INSUMOS — Así Fue Deco

FastAPI. Es una cáscara delgada sobre `stock.py` y `calculos.py`: las reglas
de negocio no viven acá, para que la carga manual, la sincronización de
Mercado Libre y la interfaz web no puedan discrepar entre sí.

CORRER EN LOCAL
    python -m insumos_app.api          (desde la raíz del repo)
    http://localhost:8010/docs

AUTENTICACIÓN — PROVISORIA Y A PROPÓSITO
    La especificación deja usuarios y permisos sin definir, así que no se
    inventa un modelo de usuarios acá. Mientras tanto hay un secreto
    compartido en el header `X-Insumos-Password`, igual que el
    `X-Admin-Password` de El Gadget, que se lee de `INSUMOS_PASSWORD` en
    `config/.env` o del entorno.

    Si `INSUMOS_PASSWORD` no está configurado, la API arranca ABIERTA y lo
    avisa por consola. Eso sirve para desarrollo y para los tests; antes de
    exponerla a internet hay que configurar el secreto (y, cuando se definan,
    los usuarios de verdad).
"""

from __future__ import annotations

import hmac
import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

if __package__ in (None, ""):  # permite `python insumos_app/api.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from insumos_app import calculos, db, modelos, stock
from insumos_app.modelos import campos_enviados

VERSION = "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN Y AUTENTICACIÓN
# ════════════════════════════════════════════════════════════════════════════

def _leer_env() -> Dict[str, str]:
    """Lee `config/.env` si existe, con el entorno del sistema como base.

    No usa `scripts/utils/config.Config` para no acoplar esta app al módulo de
    El Gadget, y porque ese lector descarta el entorno del sistema cuando el
    archivo existe: en Render no hay `config/.env` y las variables vienen del
    panel.
    """
    valores: Dict[str, str] = dict(os.environ)
    archivo = db.BASE_DIR / "config" / ".env"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            valores[clave.strip()] = valor.strip()
    return valores


INSUMOS_PASSWORD = _leer_env().get("INSUMOS_PASSWORD", "").strip()


def requerir_auth(x_insumos_password: Optional[str] = Header(None)) -> None:
    """Comparación en tiempo constante, para no filtrar el secreto por timing."""
    if not INSUMOS_PASSWORD:
        return  # modo abierto de desarrollo; avisado en el arranque
    if not x_insumos_password or not hmac.compare_digest(
        x_insumos_password, INSUMOS_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="Credencial inválida")


def conexion() -> Iterator[sqlite3.Connection]:
    """Una conexión por request. `db.conectar()` lee `db.DB_PATH` en el momento,
    que es lo que les permite a los tests apuntar a una base temporal."""
    conn = db.conectar()
    try:
        yield conn
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════════════════
# APP
# ════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def _ciclo_de_vida(app: FastAPI):
    """Crea el esquema si falta, en cada arranque. `migrar()` es idempotente."""
    db.migrar()
    print(f"[insumos] base: {db.DB_PATH}")
    if not INSUMOS_PASSWORD:
        print(
            "[insumos] ATENCIÓN: INSUMOS_PASSWORD no está configurado, "
            "la API responde SIN autenticación. Configuralo antes de exponerla."
        )
    yield


app = FastAPI(
    title="Insumos y Producción — Así Fue Deco",
    description=(
        "Stock de insumos, recetas de artículos y peso/medidas de envío "
        "derivados de la receta."
    ),
    version=VERSION,
    lifespan=_ciclo_de_vida,
)

# La interfaz web se sirve desde otro origen y la autenticación va por header,
# no por cookies, así que no se piden credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def _valor_invalido(request: Request, exc: ValueError) -> JSONResponse:
    """Las reglas de negocio del motor se comunican con ValueError."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(sqlite3.IntegrityError)
async def _integridad(request: Request, exc: sqlite3.IntegrityError) -> JSONResponse:
    """Un CHECK o un UNIQUE del esquema es un pedido inválido, no un bug.

    El mensaje crudo de SQLite se devuelve porque nombra la restricción, y en
    este sistema eso es justo lo que el operador necesita saber.
    """
    return JSONResponse(
        status_code=409,
        content={"detail": f"El dato no cumple una restricción de la base: {exc}"},
    )


@app.get("/", tags=["salud"])
def raiz() -> Dict[str, Any]:
    return {
        "sistema": "Insumos y Producción — Así Fue Deco",
        "version": VERSION,
        "docs": "/docs",
        "autenticacion": "X-Insumos-Password" if INSUMOS_PASSWORD else "abierta (sin configurar)",
    }


@app.get("/salud", tags=["salud"])
def salud(conn: sqlite3.Connection = Depends(conexion)) -> Dict[str, Any]:
    insumos = conn.execute("SELECT COUNT(*) FROM insumo").fetchone()[0]
    articulos = conn.execute("SELECT COUNT(*) FROM articulo").fetchone()[0]
    pendientes = conn.execute(
        "SELECT COUNT(*) FROM venta_procesada WHERE estado LIKE 'pendiente%'"
    ).fetchone()[0]
    return {
        "ok": True,
        "version": VERSION,
        "insumos": insumos,
        "articulos": articulos,
        "ventas_pendientes": pendientes,
        "fecha_corte": db.get_config(conn, "fecha_corte"),
    }


api = APIRouter(prefix="/api", dependencies=[Depends(requerir_auth)])


# ════════════════════════════════════════════════════════════════════════════
# SERIALIZACIÓN
# ════════════════════════════════════════════════════════════════════════════

def _insumo_salida(conn: sqlite3.Connection, fila: sqlite3.Row) -> Dict[str, Any]:
    insumo = dict(fila)
    insumo["activo"] = bool(insumo["activo"])
    insumo["stock"] = calculos.stock_para_pantalla(insumo)
    insumo["costos"] = calculos.costos_derivados(insumo)
    insumo["en_alerta"] = calculos.en_alerta(insumo)
    insumo["unidad_pantalla"] = calculos.unidad_de_pantalla(insumo["modo_stock"])

    if insumo.get("categoria_id"):
        f = conn.execute(
            "SELECT nombre FROM categoria WHERE id = ?", (insumo["categoria_id"],)
        ).fetchone()
        insumo["categoria"] = f["nombre"] if f else None
    else:
        insumo["categoria"] = None

    if insumo.get("subcategoria_id"):
        f = conn.execute(
            "SELECT nombre FROM subcategoria WHERE id = ?", (insumo["subcategoria_id"],)
        ).fetchone()
        insumo["subcategoria"] = f["nombre"] if f else None
    else:
        insumo["subcategoria"] = None

    return insumo


def _articulo_salida(
    conn: sqlite3.Connection, fila: sqlite3.Row, completo: bool = True
) -> Dict[str, Any]:
    articulo = dict(fila)
    articulo["activo"] = bool(articulo["activo"])
    articulo["se_embala_doblado"] = bool(articulo["se_embala_doblado"])

    receta = stock.receta_de(conn, int(articulo["id"]))
    articulo["envio"] = calculos.calcular_envio(articulo, receta)

    if completo:
        articulo["receta"] = [
            {
                "insumo_id": r["insumo_id"],
                "nombre": r["nombre"],
                "cantidad": r["cantidad"],
                "peso_unitario_g": r["peso_unitario_g"],
                "peso_total_g": round(float(r["cantidad"]) * float(r["peso_unitario_g"]), 3),
                "modo_stock": r["modo_stock"],
                "insumo_activo": bool(r["activo"]),
            }
            for r in receta
        ]
        articulo["mapeos"] = [
            dict(m)
            for m in conn.execute(
                """SELECT id, canal, id_externo, variacion_externa
                     FROM mapeo_canal WHERE articulo_id = ?
                    ORDER BY canal, id_externo""",
                (articulo["id"],),
            ).fetchall()
        ]
    return articulo


def _obtener(conn: sqlite3.Connection, tabla: str, id_: int) -> sqlite3.Row:
    fila = conn.execute(f"SELECT * FROM {tabla} WHERE id = ?", (id_,)).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"No existe {tabla} con id {id_}")
    return fila


def _aplicar_update(
    conn: sqlite3.Connection, tabla: str, id_: int, cambios: Dict[str, Any]
) -> None:
    if not cambios:
        return
    if "activo" in cambios and cambios["activo"] is not None:
        cambios["activo"] = 1 if cambios["activo"] else 0
    if "se_embala_doblado" in cambios and cambios["se_embala_doblado"] is not None:
        cambios["se_embala_doblado"] = 1 if cambios["se_embala_doblado"] else 0

    columnas = ", ".join(f"{c} = ?" for c in cambios)
    valores = list(cambios.values())
    sufijo = ""
    if tabla in ("insumo", "articulo"):
        sufijo = ", actualizado_at = ?"
        valores.append(db.ahora_iso())
    conn.execute(f"UPDATE {tabla} SET {columnas}{sufijo} WHERE id = ?", valores + [id_])


# ════════════════════════════════════════════════════════════════════════════
# CATEGORÍAS Y SUBCATEGORÍAS
# ════════════════════════════════════════════════════════════════════════════

@api.get("/categorias", tags=["categorias"])
def listar_categorias(conn: sqlite3.Connection = Depends(conexion)) -> List[Dict[str, Any]]:
    """Categorías con sus subcategorías anidadas y la cuenta de insumos."""
    salida = []
    for cat in conn.execute("SELECT * FROM categoria ORDER BY orden, nombre").fetchall():
        subs = conn.execute(
            "SELECT * FROM subcategoria WHERE categoria_id = ? ORDER BY orden, nombre",
            (cat["id"],),
        ).fetchall()
        salida.append(
            {
                **dict(cat),
                "insumos": conn.execute(
                    "SELECT COUNT(*) FROM insumo WHERE categoria_id = ?", (cat["id"],)
                ).fetchone()[0],
                "subcategorias": [
                    {
                        **dict(s),
                        "insumos": conn.execute(
                            "SELECT COUNT(*) FROM insumo WHERE subcategoria_id = ?", (s["id"],)
                        ).fetchone()[0],
                    }
                    for s in subs
                ],
            }
        )
    return salida


@api.post("/categorias", status_code=201, tags=["categorias"])
def crear_categoria(
    datos: modelos.CategoriaIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    cur = conn.execute(
        "INSERT INTO categoria (nombre, orden) VALUES (?, ?)",
        (datos.nombre.strip(), datos.orden),
    )
    return dict(_obtener(conn, "categoria", int(cur.lastrowid)))


@api.put("/categorias/{categoria_id}", tags=["categorias"])
def editar_categoria(
    categoria_id: int,
    datos: modelos.CategoriaUpdate,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    _obtener(conn, "categoria", categoria_id)
    _aplicar_update(conn, "categoria", categoria_id, campos_enviados(datos))
    return dict(_obtener(conn, "categoria", categoria_id))


@api.delete("/categorias/{categoria_id}", tags=["categorias"])
def borrar_categoria(
    categoria_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Se niega si quedan insumos adentro, en la categoría o en sus subcategorías.

    Borrarla en cascada dejaría insumos sin clasificar sin que nadie lo pida.
    """
    _obtener(conn, "categoria", categoria_id)
    en_uso = conn.execute(
        """SELECT COUNT(*) FROM insumo
            WHERE categoria_id = ?
               OR subcategoria_id IN (SELECT id FROM subcategoria WHERE categoria_id = ?)""",
        (categoria_id, categoria_id),
    ).fetchone()[0]
    if en_uso:
        raise HTTPException(
            status_code=409,
            detail=f"La categoría tiene {en_uso} insumo(s). Reasignalos antes de borrarla.",
        )
    conn.execute("DELETE FROM categoria WHERE id = ?", (categoria_id,))
    return {"borrada": categoria_id}


@api.get("/categorias/{categoria_id}/subcategorias", tags=["categorias"])
def listar_subcategorias(
    categoria_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> List[Dict[str, Any]]:
    _obtener(conn, "categoria", categoria_id)
    return [
        dict(f)
        for f in conn.execute(
            "SELECT * FROM subcategoria WHERE categoria_id = ? ORDER BY orden, nombre",
            (categoria_id,),
        ).fetchall()
    ]


@api.post("/subcategorias", status_code=201, tags=["categorias"])
def crear_subcategoria(
    datos: modelos.SubcategoriaIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    _obtener(conn, "categoria", datos.categoria_id)
    cur = conn.execute(
        "INSERT INTO subcategoria (categoria_id, nombre, orden) VALUES (?, ?, ?)",
        (datos.categoria_id, datos.nombre.strip(), datos.orden),
    )
    return dict(_obtener(conn, "subcategoria", int(cur.lastrowid)))


@api.put("/subcategorias/{subcategoria_id}", tags=["categorias"])
def editar_subcategoria(
    subcategoria_id: int,
    datos: modelos.SubcategoriaUpdate,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    _obtener(conn, "subcategoria", subcategoria_id)
    _aplicar_update(conn, "subcategoria", subcategoria_id, campos_enviados(datos))
    return dict(_obtener(conn, "subcategoria", subcategoria_id))


@api.delete("/subcategorias/{subcategoria_id}", tags=["categorias"])
def borrar_subcategoria(
    subcategoria_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    _obtener(conn, "subcategoria", subcategoria_id)
    en_uso = conn.execute(
        "SELECT COUNT(*) FROM insumo WHERE subcategoria_id = ?", (subcategoria_id,)
    ).fetchone()[0]
    if en_uso:
        raise HTTPException(
            status_code=409,
            detail=f"La subcategoría tiene {en_uso} insumo(s). Reasignalos antes de borrarla.",
        )
    conn.execute("DELETE FROM subcategoria WHERE id = ?", (subcategoria_id,))
    return {"borrada": subcategoria_id}


# ════════════════════════════════════════════════════════════════════════════
# INSUMOS
# ════════════════════════════════════════════════════════════════════════════

@api.get("/insumos", tags=["insumos"])
def listar_insumos(
    activo: Optional[bool] = None,
    categoria_id: Optional[int] = None,
    subcategoria_id: Optional[int] = None,
    q: Optional[str] = None,
    solo_alerta: bool = False,
    conn: sqlite3.Connection = Depends(conexion),
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM insumo WHERE 1 = 1"
    params: List[Any] = []
    if activo is not None:
        sql += " AND activo = ?"
        params.append(1 if activo else 0)
    if categoria_id is not None:
        sql += " AND categoria_id = ?"
        params.append(categoria_id)
    if subcategoria_id is not None:
        sql += " AND subcategoria_id = ?"
        params.append(subcategoria_id)
    if q:
        sql += " AND nombre LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY nombre"

    salida = [_insumo_salida(conn, f) for f in conn.execute(sql, params).fetchall()]
    if solo_alerta:
        salida = [i for i in salida if i["en_alerta"]]
    return salida


@api.get("/insumos/{insumo_id}", tags=["insumos"])
def ver_insumo(
    insumo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    insumo = _insumo_salida(conn, _obtener(conn, "insumo", insumo_id))
    insumo["usado_en"] = [
        dict(f)
        for f in conn.execute(
            """SELECT a.id AS articulo_id, a.nombre, r.cantidad
                 FROM receta r JOIN articulo a ON a.id = r.articulo_id
                WHERE r.insumo_id = ? ORDER BY a.nombre""",
            (insumo_id,),
        ).fetchall()
    ]
    return insumo


@api.post("/insumos", status_code=201, tags=["insumos"])
def crear_insumo(
    datos: modelos.InsumoIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Crea un insumo y, si se manda `stock_inicial`, lo asienta como inventario.

    El stock inicial no se escribe en la columna: entra como movimiento
    `inventario_inicial`, en la misma transacción que el alta. Así el libro
    mayor explica también el primer número, y esa carga fija la `fecha_corte`
    si todavía no estaba definida.
    """
    if datos.modo_stock not in db.MODOS_STOCK:
        raise HTTPException(
            status_code=400,
            detail=f"modo_stock debe ser uno de: {', '.join(db.MODOS_STOCK)}",
        )
    if datos.unidad_compra and datos.unidad_compra not in db.UNIDADES_COMPRA:
        raise HTTPException(
            status_code=400,
            detail=f"unidad_compra debe ser uno de: {', '.join(db.UNIDADES_COMPRA)}",
        )
    if datos.peso_unitario_g is None or datos.peso_unitario_g <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "peso_unitario_g es obligatorio y mayor que cero, también en modo "
                "'peso': es el puente entre los kilos que se compran y las unidades "
                "que pide la receta."
            ),
        )
    if datos.subcategoria_id:
        sub = _obtener(conn, "subcategoria", datos.subcategoria_id)
        if datos.categoria_id and int(sub["categoria_id"]) != datos.categoria_id:
            raise HTTPException(
                status_code=400,
                detail="La subcategoría no pertenece a la categoría indicada",
            )

    with db.transaccion(conn):
        cur = conn.execute(
            """INSERT INTO insumo
                   (nombre, categoria_id, subcategoria_id, modo_stock, peso_unitario_g,
                    largo_mm, ancho_mm, alto_mm, alerta_cuando_queden,
                    costo_compra, unidad_compra, activo, creado_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datos.nombre.strip(),
                datos.categoria_id,
                datos.subcategoria_id,
                datos.modo_stock,
                datos.peso_unitario_g,
                datos.largo_mm,
                datos.ancho_mm,
                datos.alto_mm,
                datos.alerta_cuando_queden,
                datos.costo_compra,
                datos.unidad_compra,
                1 if datos.activo else 0,
                db.ahora_iso(),
            ),
        )
        insumo_id = int(cur.lastrowid)

        if datos.stock_inicial:
            unidades = calculos.a_unidades(
                datos.stock_inicial, datos.modo_stock, datos.peso_unitario_g
            )
            stock.asegurar_fecha_corte(conn)
            db.registrar_movimiento(
                conn,
                insumo_id,
                unidades,
                "inventario_inicial",
                usuario=datos.usuario,
                nota="Carga inicial al crear el insumo",
            )

    return _insumo_salida(conn, _obtener(conn, "insumo", insumo_id))


@api.put("/insumos/{insumo_id}", tags=["insumos"])
def editar_insumo(
    insumo_id: int,
    datos: modelos.InsumoUpdate,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """Edición parcial. No toca el stock: para eso están los movimientos.

    Cambiar `modo_stock` es seguro para el stock —se guarda en unidades, así
    que el número no se mueve, solo cambia la unidad en que se muestra— pero
    NO para el umbral de alerta, que está expresado en la unidad del modo
    viejo. Se avisa en la respuesta en vez de reinterpretarlo en silencio.
    """
    anterior = _obtener(conn, "insumo", insumo_id)
    cambios = campos_enviados(datos)

    avisos = []
    nuevo_modo = cambios.get("modo_stock")
    umbral = float(anterior["alerta_cuando_queden"] or 0)
    if nuevo_modo and nuevo_modo != anterior["modo_stock"] and umbral:
        avisos.append(
            f"El modo de stock pasó de '{anterior['modo_stock']}' a '{nuevo_modo}': "
            f"el umbral de alerta ({umbral}) ahora se lee en "
            f"{calculos.unidad_de_pantalla(nuevo_modo)}. Revisalo."
        )

    if cambios.get("modo_stock") and cambios["modo_stock"] not in db.MODOS_STOCK:
        raise HTTPException(status_code=400, detail="modo_stock inválido")
    if cambios.get("unidad_compra") and cambios["unidad_compra"] not in db.UNIDADES_COMPRA:
        raise HTTPException(status_code=400, detail="unidad_compra inválida")
    if "peso_unitario_g" in cambios and (
        cambios["peso_unitario_g"] is None or cambios["peso_unitario_g"] <= 0
    ):
        raise HTTPException(
            status_code=400, detail="peso_unitario_g tiene que ser mayor que cero"
        )

    _aplicar_update(conn, "insumo", insumo_id, cambios)
    salida = _insumo_salida(conn, _obtener(conn, "insumo", insumo_id))
    if avisos:
        salida["avisos"] = avisos
    return salida


@api.delete("/insumos/{insumo_id}", tags=["insumos"])
def borrar_insumo(
    insumo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Borra el insumo solo si no tiene historia. Si la tiene, se desactiva.

    Un insumo con movimientos no se puede borrar sin romper el libro mayor
    (sus movimientos explican el stock de un insumo que ya no existiría), y
    uno que está en una receta dejaría artículos con el peso de envío
    silenciosamente incompleto.
    """
    _obtener(conn, "insumo", insumo_id)
    movimientos = conn.execute(
        "SELECT COUNT(*) FROM movimiento_stock WHERE insumo_id = ?", (insumo_id,)
    ).fetchone()[0]
    recetas = conn.execute(
        "SELECT COUNT(*) FROM receta WHERE insumo_id = ?", (insumo_id,)
    ).fetchone()[0]

    if movimientos or recetas:
        _aplicar_update(conn, "insumo", insumo_id, {"activo": 0})
        return {
            "desactivado": insumo_id,
            "borrado": False,
            "movimientos": movimientos,
            "recetas": recetas,
            "detalle": (
                "El insumo tiene historia (movimientos o recetas), así que se "
                "desactivó en vez de borrarse: borrarlo rompería el libro mayor."
            ),
        }

    conn.execute("DELETE FROM insumo WHERE id = ?", (insumo_id,))
    return {"borrado": insumo_id, "desactivado": False}


@api.post("/insumos/{insumo_id}/stock", tags=["insumos"])
def fijar_stock_insumo(
    insumo_id: int, datos: modelos.StockIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Conteo de inventario: deja el stock en el valor absoluto que se manda.

    Internamente asienta la DIFERENCIA como movimiento. El primer conteo de un
    insumo es `inventario_inicial` y fija la `fecha_corte`; los siguientes son
    `ajuste`.
    """
    _obtener(conn, "insumo", insumo_id)
    return stock.fijar_stock(
        conn,
        insumo_id,
        datos.cantidad,
        en_unidades=datos.en_unidades,
        usuario=datos.usuario,
        nota=datos.nota,
    )


@api.get("/insumos/{insumo_id}/movimientos", tags=["insumos"])
def movimientos_de_insumo(
    insumo_id: int,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """El libro mayor de un insumo, con el saldo que dejó cada movimiento.

    El saldo lo calcula la base con una subconsulta por fila (la suma de todo
    lo anterior y la fila misma) en vez de acumularlo en Python: así la última
    fila coincide con `stock_unidades` sin importar en qué página se esté.
    """
    fila = _obtener(conn, "insumo", insumo_id)
    insumo = dict(fila)

    total = conn.execute(
        "SELECT COUNT(*) FROM movimiento_stock WHERE insumo_id = ?", (insumo_id,)
    ).fetchone()[0]
    filas = conn.execute(
        """SELECT m.*, a.nombre AS articulo,
                  (SELECT SUM(m2.cantidad_unidades)
                     FROM movimiento_stock m2
                    WHERE m2.insumo_id = m.insumo_id AND m2.id <= m.id) AS saldo_unidades
             FROM movimiento_stock m
             LEFT JOIN articulo a ON a.id = m.articulo_id
            WHERE m.insumo_id = ?
            ORDER BY m.id DESC LIMIT ? OFFSET ?""",
        (insumo_id, limit, offset),
    ).fetchall()

    movimientos = []
    for f in filas:
        mov = dict(f)
        for clave, origen in (("cantidad_pantalla", "cantidad_unidades"),
                              ("saldo_pantalla", "saldo_unidades")):
            mov[clave] = round(
                calculos.desde_unidades(
                    float(mov[origen] or 0.0),
                    insumo["modo_stock"],
                    float(insumo["peso_unitario_g"]),
                ),
                4,
            )
        movimientos.append(mov)

    return {
        "insumo_id": insumo_id,
        "nombre": insumo["nombre"],
        "unidad_pantalla": calculos.unidad_de_pantalla(insumo["modo_stock"]),
        "stock": calculos.stock_para_pantalla(insumo),
        "total": total,
        "limit": limit,
        "offset": offset,
        "movimientos": movimientos,
    }


# ════════════════════════════════════════════════════════════════════════════
# ARTÍCULOS
# ════════════════════════════════════════════════════════════════════════════

@api.get("/articulos", tags=["articulos"])
def listar_articulos(
    activo: Optional[bool] = None,
    q: Optional[str] = None,
    sin_receta: bool = False,
    conn: sqlite3.Connection = Depends(conexion),
) -> List[Dict[str, Any]]:
    """Listado de artículos. `sin_receta=true` filtra los que no pueden cotizar."""
    sql = "SELECT * FROM articulo WHERE 1 = 1"
    params: List[Any] = []
    if activo is not None:
        sql += " AND activo = ?"
        params.append(1 if activo else 0)
    if q:
        sql += " AND (nombre LIKE ? OR sku_afd LIKE ? OR sku_elgadget LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY nombre"

    salida = [
        _articulo_salida(conn, f, completo=False)
        for f in conn.execute(sql, params).fetchall()
    ]
    if sin_receta:
        salida = [a for a in salida if a["envio"]["receta_incompleta"]]
    return salida


@api.get("/articulos/{articulo_id}", tags=["articulos"])
def ver_articulo(
    articulo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    return _articulo_salida(conn, _obtener(conn, "articulo", articulo_id))


@api.post("/articulos", status_code=201, tags=["articulos"])
def crear_articulo(
    datos: modelos.ArticuloIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Crea un artículo. Nace sin receta, así que todavía no puede cotizar envío."""
    if datos.se_embala_doblado and not all(
        [datos.largo_emb_mm, datos.ancho_emb_mm, datos.alto_emb_mm]
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Si el artículo se embala doblado hacen falta las tres medidas "
                "embaladas: son las que se usan para cotizar el envío."
            ),
        )
    margen = datos.margen_embalaje
    if margen is None:
        margen = db.margen_embalaje_default(conn)

    cur = conn.execute(
        """INSERT INTO articulo
               (nombre, sku_afd, sku_elgadget, id_empretienda,
                largo_real_mm, ancho_real_mm, alto_real_mm,
                se_embala_doblado, largo_emb_mm, ancho_emb_mm, alto_emb_mm,
                margen_embalaje, activo, creado_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datos.nombre.strip(),
            datos.sku_afd,
            datos.sku_elgadget,
            datos.id_empretienda,
            datos.largo_real_mm,
            datos.ancho_real_mm,
            datos.alto_real_mm,
            1 if datos.se_embala_doblado else 0,
            datos.largo_emb_mm,
            datos.ancho_emb_mm,
            datos.alto_emb_mm,
            margen,
            1 if datos.activo else 0,
            db.ahora_iso(),
        ),
    )
    return _articulo_salida(conn, _obtener(conn, "articulo", int(cur.lastrowid)))


@api.put("/articulos/{articulo_id}", tags=["articulos"])
def editar_articulo(
    articulo_id: int,
    datos: modelos.ArticuloUpdate,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    _obtener(conn, "articulo", articulo_id)
    _aplicar_update(conn, "articulo", articulo_id, campos_enviados(datos))
    return _articulo_salida(conn, _obtener(conn, "articulo", articulo_id))


@api.delete("/articulos/{articulo_id}", tags=["articulos"])
def borrar_articulo(
    articulo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Borra el artículo si nunca se vendió; si se vendió, lo desactiva.

    Los movimientos de una venta apuntan al artículo: borrarlo dejaría el
    libro mayor sin poder explicar de qué fue ese consumo.
    """
    _obtener(conn, "articulo", articulo_id)
    movimientos = conn.execute(
        "SELECT COUNT(*) FROM movimiento_stock WHERE articulo_id = ?", (articulo_id,)
    ).fetchone()[0]

    if movimientos:
        _aplicar_update(conn, "articulo", articulo_id, {"activo": 0})
        return {
            "desactivado": articulo_id,
            "borrado": False,
            "movimientos": movimientos,
            "detalle": (
                "El artículo tiene movimientos de venta asociados, así que se "
                "desactivó en vez de borrarse."
            ),
        }

    conn.execute("DELETE FROM articulo WHERE id = ?", (articulo_id,))
    return {"borrado": articulo_id, "desactivado": False}


@api.get("/articulos/{articulo_id}/envio", tags=["articulos", "envio"])
def envio_articulo(
    articulo_id: int,
    margen: Optional[float] = Query(
        None, description="Margen de embalaje alternativo, para simular sin guardar"
    ),
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """Peso y medidas del paquete embalado. Es el dato que el sistema existe para dar.

    `margen` permite simular otro factor sin tocar el artículo: sirve para ver
    cuánto cambia la cotización entre 1,05 por dimensión (que infla el volumen
    15,8%) y 1,016 (que lo infla 5%).
    """
    fila = _obtener(conn, "articulo", articulo_id)
    envio = calculos.calcular_envio(
        dict(fila), stock.receta_de(conn, articulo_id), margen=margen
    )
    return {
        "articulo_id": articulo_id,
        "nombre": fila["nombre"],
        "sku_afd": fila["sku_afd"],
        "sku_elgadget": fila["sku_elgadget"],
        "medidas_reales_mm": {
            "largo": fila["largo_real_mm"],
            "ancho": fila["ancho_real_mm"],
            "alto": fila["alto_real_mm"],
        },
        **envio,
    }


@api.get("/envio", tags=["envio"])
def envio_por_sku(
    sku_elgadget: Optional[str] = None,
    sku_afd: Optional[str] = None,
    id_empretienda: Optional[str] = None,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """Peso y medidas de envío buscando por SKU, sin conocer el id interno.

    Es la puerta para el cotizador de Correo Argentino del checkout de El
    Gadget, que conoce el SKU del producto y nada más.
    """
    criterios = [
        ("sku_elgadget", sku_elgadget),
        ("sku_afd", sku_afd),
        ("id_empretienda", id_empretienda),
    ]
    activos = [(col, val) for col, val in criterios if val]
    if not activos:
        raise HTTPException(
            status_code=400,
            detail="Hace falta uno de: sku_elgadget, sku_afd o id_empretienda",
        )

    columna, valor = activos[0]
    fila = conn.execute(f"SELECT * FROM articulo WHERE {columna} = ?", (valor,)).fetchone()
    if fila is None:
        raise HTTPException(
            status_code=404, detail=f"No hay ningún artículo con {columna} = {valor}"
        )
    return envio_articulo(int(fila["id"]), None, conn)


# ════════════════════════════════════════════════════════════════════════════
# RECETAS
# ════════════════════════════════════════════════════════════════════════════

@api.get("/articulos/{articulo_id}/receta", tags=["recetas"])
def ver_receta(
    articulo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    fila = _obtener(conn, "articulo", articulo_id)
    receta = stock.receta_de(conn, articulo_id)
    return {
        "articulo_id": articulo_id,
        "nombre": fila["nombre"],
        "items": receta,
        "envio": calculos.calcular_envio(dict(fila), receta),
    }


@api.put("/articulos/{articulo_id}/receta", tags=["recetas"])
def reemplazar_receta(
    articulo_id: int, datos: modelos.RecetaIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Reemplaza la receta completa. Es lo que manda el editor de la pantalla.

    No rehace movimientos de stock ya asentados: cambiar una receta afecta las
    ventas que vengan, no las que ya se descontaron. Las ventas pendientes de
    receta sí se pueden reprocesar después con
    `POST /api/ventas/pendientes/reprocesar`.
    """
    _obtener(conn, "articulo", articulo_id)

    vistos = set()
    for item in datos.items:
        if item.insumo_id in vistos:
            raise HTTPException(
                status_code=400,
                detail=f"El insumo {item.insumo_id} aparece dos veces en la receta",
            )
        vistos.add(item.insumo_id)
        if item.cantidad <= 0:
            raise HTTPException(
                status_code=400, detail="Las cantidades de la receta tienen que ser mayores que cero"
            )
        _obtener(conn, "insumo", item.insumo_id)

    with db.transaccion(conn):
        conn.execute("DELETE FROM receta WHERE articulo_id = ?", (articulo_id,))
        for item in datos.items:
            conn.execute(
                "INSERT INTO receta (articulo_id, insumo_id, cantidad) VALUES (?, ?, ?)",
                (articulo_id, item.insumo_id, item.cantidad),
            )

    return ver_receta(articulo_id, conn)


@api.post("/articulos/{articulo_id}/receta", tags=["recetas"])
def poner_linea_receta(
    articulo_id: int,
    datos: modelos.RecetaItemIn,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """Agrega o actualiza una sola línea de la receta."""
    _obtener(conn, "articulo", articulo_id)
    _obtener(conn, "insumo", datos.insumo_id)
    if datos.cantidad <= 0:
        raise HTTPException(status_code=400, detail="La cantidad tiene que ser mayor que cero")

    conn.execute(
        """INSERT INTO receta (articulo_id, insumo_id, cantidad) VALUES (?, ?, ?)
           ON CONFLICT(articulo_id, insumo_id) DO UPDATE SET cantidad = excluded.cantidad""",
        (articulo_id, datos.insumo_id, datos.cantidad),
    )
    return ver_receta(articulo_id, conn)


@api.delete("/articulos/{articulo_id}/receta/{insumo_id}", tags=["recetas"])
def borrar_linea_receta(
    articulo_id: int, insumo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    _obtener(conn, "articulo", articulo_id)
    cur = conn.execute(
        "DELETE FROM receta WHERE articulo_id = ? AND insumo_id = ?",
        (articulo_id, insumo_id),
    )
    if cur.rowcount == 0:
        raise HTTPException(
            status_code=404, detail=f"El insumo {insumo_id} no está en la receta"
        )
    return ver_receta(articulo_id, conn)


# ════════════════════════════════════════════════════════════════════════════
# MAPEO DE CANAL
# ════════════════════════════════════════════════════════════════════════════

@api.get("/mapeos", tags=["mapeos"])
def listar_mapeos(
    canal: Optional[str] = None,
    articulo_id: Optional[int] = None,
    conn: sqlite3.Connection = Depends(conexion),
) -> List[Dict[str, Any]]:
    sql = """SELECT m.*, a.nombre AS articulo
               FROM mapeo_canal m JOIN articulo a ON a.id = m.articulo_id
              WHERE 1 = 1"""
    params: List[Any] = []
    if canal:
        sql += " AND m.canal = ?"
        params.append(canal)
    if articulo_id:
        sql += " AND m.articulo_id = ?"
        params.append(articulo_id)
    sql += " ORDER BY m.canal, a.nombre"
    return [dict(f) for f in conn.execute(sql, params).fetchall()]


def _avisos_de_precedencia(
    conn: sqlite3.Connection, canal: str, id_externo: str, variacion: str, articulo_id: int
) -> List[str]:
    """Avisa cuando el mapeo que se está cargando convive con otro que lo pisa.

    No bloquea nada: la combinación es legítima y la precedencia está definida
    (gana el específico). Lo que evita es que alguien cargue un comodín a un
    artículo y una variante a otro sin darse cuenta de cuál va a ganar — ahora
    más probable, porque un artículo puede tener varias publicaciones.
    """
    avisos: List[str] = []

    def nombre_de(articulo: int) -> str:
        fila = conn.execute("SELECT nombre FROM articulo WHERE id = ?", (articulo,)).fetchone()
        return fila["nombre"] if fila else f"artículo {articulo}"

    if variacion:
        comodin = conn.execute(
            """SELECT articulo_id FROM mapeo_canal
                WHERE canal = ? AND id_externo = ? AND variacion_externa = ''""",
            (canal, id_externo),
        ).fetchone()
        if comodin and int(comodin["articulo_id"]) != articulo_id:
            avisos.append(
                f"La publicación {id_externo} ya tenía un mapeo sin variante hacia "
                f"«{nombre_de(int(comodin['articulo_id']))}». Este mapeo específico le gana "
                f"para la variante «{variacion}»; las demás variantes siguen cayendo al otro."
            )
    else:
        especificos = conn.execute(
            """SELECT variacion_externa, articulo_id FROM mapeo_canal
                WHERE canal = ? AND id_externo = ? AND variacion_externa <> ''
                ORDER BY variacion_externa""",
            (canal, id_externo),
        ).fetchall()
        otros = [f for f in especificos if int(f["articulo_id"]) != articulo_id]
        if otros:
            detalle = ", ".join(
                f"«{f['variacion_externa']}» → «{nombre_de(int(f['articulo_id']))}»" for f in otros
            )
            avisos.append(
                f"La publicación {id_externo} ya tenía mapeos por variante que le ganan a este "
                f"comodín: {detalle}. El comodín cubre solo las variantes restantes."
            )
    return avisos


@api.post("/mapeos", status_code=201, tags=["mapeos"])
def crear_mapeo(
    datos: modelos.MapeoIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Asocia una publicación de un canal con un artículo.

    Sin esto, una venta de Mercado Libre no sabe a qué artículo corresponde y
    queda en `pendiente_mapeo`.

    VARIAS PUBLICACIONES PUEDEN APUNTAR AL MISMO ARTÍCULO, y es un caso real:
    el socio tiene productos publicados más de una vez en la misma cuenta de
    Mercado Libre. Lo permite el UNIQUE `(canal, id_externo, variacion_externa)`,
    que deja `articulo_id` afuera a propósito. La asimetría también es
    deliberada: una publicación NO puede apuntar a dos artículos, porque una
    venta no sabría cuál descontar.

    PRECEDENCIA: un mapeo con variante le gana al comodín (el de
    `variacion_externa` vacío) para esa variante; las demás variantes caen al
    comodín. Cargar los dos es legítimo, pero confunde, así que se avisa en la
    respuesta en vez de dejarlo pasar callado.
    """
    if datos.canal not in db.CANALES_MAPEABLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"canal debe ser uno de: {', '.join(db.CANALES_MAPEABLES)}. "
                "Las ventas manuales eligen el artículo en pantalla y no se mapean."
            ),
        )
    _obtener(conn, "articulo", datos.articulo_id)
    id_externo = datos.id_externo.strip()
    variacion = (datos.variacion_externa or "").strip()

    avisos = _avisos_de_precedencia(conn, datos.canal, id_externo, variacion,
                                    datos.articulo_id)

    cur = conn.execute(
        """INSERT INTO mapeo_canal
               (articulo_id, canal, id_externo, variacion_externa, creado_at)
           VALUES (?, ?, ?, ?, ?)""",
        (datos.articulo_id, datos.canal, id_externo, variacion, db.ahora_iso()),
    )
    salida = dict(_obtener(conn, "mapeo_canal", int(cur.lastrowid)))
    if avisos:
        salida["avisos"] = avisos
    return salida


@api.delete("/mapeos/{mapeo_id}", tags=["mapeos"])
def borrar_mapeo(
    mapeo_id: int, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    _obtener(conn, "mapeo_canal", mapeo_id)
    conn.execute("DELETE FROM mapeo_canal WHERE id = ?", (mapeo_id,))
    return {"borrado": mapeo_id}


# ════════════════════════════════════════════════════════════════════════════
# VENTAS — EL MOTOR
# ════════════════════════════════════════════════════════════════════════════

def _item_de_venta(item: modelos.VentaItemIn) -> Dict[str, Any]:
    """Del modelo de entrada al diccionario que espera el motor."""
    return {
        "cantidad": item.cantidad,
        "articulo_id": item.articulo_id,
        "id_externo_item": item.id_externo_item,
        "variacion_externa": item.variacion_externa,
    }


@api.get("/ventas/pendientes", tags=["ventas"])
def ventas_pendientes(conn: sqlite3.Connection = Depends(conexion)) -> List[Dict[str, Any]]:
    """Ventas registradas que todavía no descontaron stock.

    Son las que les falta receta o mapeo. Mientras estén acá, el stock está
    sobrestimado y el sistema lo dice en voz alta en vez de disimularlo.
    """
    return [
        dict(f)
        for f in conn.execute(
            """SELECT * FROM venta_procesada
                WHERE estado IN ('pendiente_receta', 'pendiente_mapeo')
                ORDER BY fecha_venta, id_externo"""
        ).fetchall()
    ]


@api.post("/ventas/pendientes/reprocesar", tags=["ventas"])
def reprocesar_todas(conn: sqlite3.Connection = Depends(conexion)) -> Dict[str, Any]:
    """Reintenta todas las ventas pendientes. Correr después de cargar recetas."""
    return stock.reprocesar_pendientes(conn)


@api.post("/ventas", tags=["ventas"])
def procesar_venta_endpoint(
    datos: modelos.VentaIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Procesa una venta y descuenta los insumos de la receta.

    Punto de entrada único de todos los canales. Es idempotente por
    `(canal, id_externo)`: repetir la llamada no vuelve a descontar.
    """
    return stock.procesar_venta(
        conn,
        datos.canal,
        datos.id_externo,
        [_item_de_venta(i) for i in datos.items],
        fecha_venta=datos.fecha_venta,
        usuario=datos.usuario,
        nota=datos.nota,
    )


@api.post("/ventas/lote", tags=["ventas"])
def procesar_lote_endpoint(
    datos: modelos.LoteVentasIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Procesa varias ventas. Lo que va a usar la sincronización de Mercado Libre.

    Cada venta es independiente: una que falla no arrastra a las demás, y las
    que ya estaban procesadas se informan sin volver a descontar.
    """
    ventas = []
    for v in datos.ventas:
        ventas.append(
            {
                "canal": v.canal,
                "id_externo": v.id_externo,
                "fecha_venta": v.fecha_venta,
                "usuario": v.usuario,
                "nota": v.nota,
                "items": [_item_de_venta(i) for i in v.items],
            }
        )
    return stock.procesar_lote(conn, ventas, usuario=datos.usuario)


@api.post("/ventas/cancelaciones", tags=["ventas"])
def cancelar_lote_endpoint(
    datos: modelos.LoteCancelacionesIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Cancela varias ventas de una. Para la sincronización de canales.

    PARA QUIEN HAGA EL SINCRONIZADOR DE MERCADO LIBRE: las cancelaciones no
    llegan consultando "órdenes nuevas". Una orden cambia de estado en el canal
    DESPUÉS de que la vimos, así que una sincronización que solo mira lo nuevo
    nunca se va a enterar de una cancelación.

    El patrón que este endpoint espera es releer el estado de las órdenes que
    ya se conocen:

        1. `GET /api/ventas?canal=ml&estado=procesada&desde=<fecha>` da los
           `id_externo` que este sistema ya procesó.
        2. Se consulta el estado actual de esas órdenes en el canal.
        3. Las que volvieron canceladas se postean acá, todas juntas.

    Se puede repetir con la misma lista sin consecuencias: cada cancelación es
    idempotente.
    """
    cancelaciones = [
        {
            "canal": c.canal,
            "id_externo": c.id_externo,
            "motivo": c.motivo,
            "usuario": c.usuario,
        }
        for c in datos.cancelaciones
    ]
    return stock.cancelar_lote(
        conn,
        cancelaciones,
        usuario=datos.usuario,
        registrar_si_no_existe=datos.registrar_si_no_existe,
    )


@api.get("/ventas", tags=["ventas"])
def listar_ventas(
    canal: Optional[str] = None,
    estado: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    sql = "SELECT * FROM venta_procesada WHERE 1 = 1"
    params: List[Any] = []
    if canal:
        sql += " AND canal = ?"
        params.append(canal)
    if estado:
        sql += " AND estado = ?"
        params.append(estado)
    if desde:
        sql += " AND fecha_venta >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha_venta <= ?"
        params.append(hasta)

    total = conn.execute(
        sql.replace("SELECT *", "SELECT COUNT(*)", 1), params
    ).fetchone()[0]
    sql += " ORDER BY fecha_proceso DESC LIMIT ? OFFSET ?"
    filas = conn.execute(sql, params + [limit, offset]).fetchall()
    return {"total": total, "limit": limit, "offset": offset,
            "ventas": [dict(f) for f in filas]}


@api.get("/ventas/{canal}/{id_externo}", tags=["ventas"])
def ver_venta(
    canal: str, id_externo: str, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Una venta y los movimientos que generó."""
    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE canal = ? AND id_externo = ?",
        (canal, id_externo),
    ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail=f"No hay venta {canal}/{id_externo}")

    movimientos = conn.execute(
        """SELECT m.*, i.nombre AS insumo, a.nombre AS articulo
             FROM movimiento_stock m
             JOIN insumo i ON i.id = m.insumo_id
             LEFT JOIN articulo a ON a.id = m.articulo_id
            WHERE m.origen_canal = ? AND m.referencia_externa = ?
            ORDER BY m.id""",
        (canal, id_externo),
    ).fetchall()
    return {**dict(fila), "movimientos": [dict(m) for m in movimientos]}


@api.post("/ventas/{canal}/{id_externo}/cancelar", tags=["ventas"])
def cancelar_una(
    canal: str,
    id_externo: str,
    datos: Optional[modelos.CancelacionIn] = None,
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """Cancela una venta y restituye el stock que había descontado.

    **Restituye los movimientos que realmente se hicieron, no recalcula la
    receta.** Si entre la venta y la cancelación alguien editó la receta del
    artículo, recalcular devolvería cantidades distintas de las descontadas y
    el stock quedaría mal sin que nada falle.

    Idempotente: cancelar dos veces no restituye dos veces. Una venta que
    nunca descontó (pendiente de receta o de mapeo, o anterior a la
    `fecha_corte`) se marca cancelada sin generar movimientos, y queda fuera
    de la cola de pendientes para que no pueda descontar más tarde.

    Es también el enganche para El Gadget cuando Mercado Pago reporta un pago
    reintegrado o anulado.
    """
    datos = datos or modelos.CancelacionIn()
    return stock.cancelar_venta(
        conn,
        canal,
        id_externo,
        motivo=datos.motivo,
        usuario=datos.usuario,
        registrar_si_no_existe=datos.registrar_si_no_existe,
    )


@api.post("/ventas/{canal}/{id_externo}/reprocesar", tags=["ventas"])
def reprocesar_una(
    canal: str, id_externo: str, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Reintenta una venta pendiente, ya cargada la receta o el mapeo que faltaba.

    Una venta ya procesada no se reprocesa: esa es la garantía de que no se
    descuenta dos veces.
    """
    return stock.reprocesar_venta(conn, canal, id_externo)


# ════════════════════════════════════════════════════════════════════════════
# MOVIMIENTOS
# ════════════════════════════════════════════════════════════════════════════

@api.get("/movimientos", tags=["movimientos"])
def listar_movimientos(
    insumo_id: Optional[int] = None,
    articulo_id: Optional[int] = None,
    tipo: Optional[str] = None,
    canal: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(conexion),
) -> Dict[str, Any]:
    """El libro mayor completo, filtrable."""
    where = " WHERE 1 = 1"
    params: List[Any] = []
    if insumo_id:
        where += " AND m.insumo_id = ?"
        params.append(insumo_id)
    if articulo_id:
        where += " AND m.articulo_id = ?"
        params.append(articulo_id)
    if tipo:
        where += " AND m.tipo = ?"
        params.append(tipo)
    if canal:
        where += " AND m.origen_canal = ?"
        params.append(canal)
    if desde:
        where += " AND m.fecha >= ?"
        params.append(desde)
    if hasta:
        where += " AND m.fecha <= ?"
        params.append(hasta)

    total = conn.execute(
        f"SELECT COUNT(*) FROM movimiento_stock m{where}", params
    ).fetchone()[0]
    filas = conn.execute(
        f"""SELECT m.*, i.nombre AS insumo, i.modo_stock, i.peso_unitario_g,
                   a.nombre AS articulo
              FROM movimiento_stock m
              JOIN insumo i ON i.id = m.insumo_id
              LEFT JOIN articulo a ON a.id = m.articulo_id
              {where}
             ORDER BY m.id DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    movimientos = []
    for f in filas:
        mov = dict(f)
        mov["cantidad_pantalla"] = round(
            calculos.desde_unidades(
                float(mov["cantidad_unidades"]), mov["modo_stock"],
                float(mov["peso_unitario_g"]),
            ),
            4,
        )
        mov["unidad_pantalla"] = calculos.unidad_de_pantalla(mov["modo_stock"])
        movimientos.append(mov)

    return {"total": total, "limit": limit, "offset": offset, "movimientos": movimientos}


@api.post("/movimientos", status_code=201, tags=["movimientos"])
def crear_movimiento(
    datos: modelos.MovimientoIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Ingreso, merma, ajuste o devolución cargados a mano.

    El signo lo pone el tipo (un ingreso suma, una merma resta); el 'ajuste'
    es el único que acepta un delta con signo. Las ventas NO entran por acá:
    van a `POST /api/ventas`, que es el único camino idempotente.
    """
    return stock.registrar_movimiento_manual(
        conn,
        datos.insumo_id,
        datos.cantidad,
        datos.tipo,
        en_unidades=datos.en_unidades,
        usuario=datos.usuario,
        nota=datos.nota,
    )


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS, CONFIG Y AUDITORÍA
# ════════════════════════════════════════════════════════════════════════════

@api.get("/alertas", tags=["alertas"])
def listar_alertas(
    incluir_inactivos: bool = False, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Insumos en o por debajo de su umbral, más los que quedaron en negativo.

    El canal de aviso (pantalla, mail o WhatsApp) está sin definir en la
    especificación: por ahora las alertas se consultan y se devuelven también
    en la respuesta de cada movimiento y de cada venta.
    """
    alertas = stock.alertas_actuales(conn, incluir_inactivos=incluir_inactivos)
    return {
        "total": len(alertas),
        "negativos": sum(1 for a in alertas if a["stock_negativo"]),
        "alertas": alertas,
    }


@api.get("/config", tags=["config"])
def ver_config(conn: sqlite3.Connection = Depends(conexion)) -> Dict[str, Any]:
    return db.todas_las_config(conn)


# Solo estas dos claves se editan por API: `schema_version` la maneja la
# migración y tocarla a mano haría que una migración futura no corra.
CLAVES_EDITABLES = ("fecha_corte", "margen_embalaje_default")


@api.put("/config/{clave}", tags=["config"])
def editar_config(
    clave: str, datos: modelos.ConfigIn, conn: sqlite3.Connection = Depends(conexion)
) -> Dict[str, Any]:
    """Cambia una clave de configuración.

    `fecha_corte`: las ventas anteriores a esta fecha se ignoran. Se fija sola
    con la primera carga de stock; acá se corrige si hace falta.

    `margen_embalaje_default`: el factor con el que nacen los artículos
    nuevos. Ojo: 1,05 por dimensión infla el volumen 15,8%; para 5% de
    volumen el factor es 1,016.
    """
    if clave not in CLAVES_EDITABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden editar: {', '.join(CLAVES_EDITABLES)}",
        )
    if clave == "fecha_corte" and datos.valor:
        if db.a_fecha(datos.valor) is None:
            raise HTTPException(
                status_code=400, detail="fecha_corte tiene que ser una fecha ISO (AAAA-MM-DD)"
            )
    if clave == "margen_embalaje_default" and datos.valor:
        try:
            if float(datos.valor) < 1:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="margen_embalaje_default tiene que ser un número mayor o igual a 1",
            )

    db.set_config(conn, clave, datos.valor)
    return {"clave": clave, "valor": db.get_config(conn, clave)}


@api.get("/auditoria/stock", tags=["auditoria"])
def auditar_stock(conn: sqlite3.Connection = Depends(conexion)) -> Dict[str, Any]:
    """Compara el stock de cada insumo contra la suma de sus movimientos.

    La invariante del sistema es que `insumo.stock_unidades` siempre se puede
    reconstruir sumando el libro mayor. Este endpoint es la forma de
    comprobarlo sin abrir la base: si alguna fila viene con `ok: false`, hay
    un camino de escritura que se saltó el libro mayor y hay que encontrarlo.
    """
    filas = db.auditar_libro_mayor(conn)
    descuadres = [f for f in filas if not f["ok"]]
    return {
        "total_insumos": len(filas),
        "cuadra": not descuadres,
        "descuadres": descuadres,
        "insumos": filas,
    }


app.include_router(api)

# La interfaz web (insumos_app/web/) la sirve esta misma app, en /app/. Un solo
# origen: el front pega a rutas relativas y no hay ninguna URL de API que
# configurar. El montaje vive en `servir_web.py` para no mezclarlo con los
# endpoints.
from insumos_app.servir_web import montar_interfaz  # noqa: E402

montar_interfaz(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8010)
