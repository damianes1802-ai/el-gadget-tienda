# -*- coding: utf-8 -*-
"""
MOTOR DE STOCK — Así Fue Deco

Todo lo que mueve stock pasa por acá. La API es una cáscara sobre este módulo
y la futura integración con Mercado Libre va a llamar a `procesar_venta` sin
enterarse de nada más.

UNA VENTA SE RESUELVE SIEMPRE IGUAL, VENGA DEL CANAL QUE VENGA

    venta → artículo (vía mapeo_canal) → receta → un movimiento por insumo

CUATRO DECISIONES QUE CONVIENE CONOCER ANTES DE TOCAR ESTE ARCHIVO

1. IDEMPOTENCIA. Antes de mover nada se consulta `venta_procesada` por
   `(canal, id_externo)`. Mercado Libre va a devolver la misma orden más de
   una vez —por reintentos o por ventanas de consulta superpuestas— y sin esto
   el stock se descuenta dos veces y nadie se entera hasta que falta
   material. `id_externo` es el id de la ORDEN; el id de la publicación va en
   los ítems y es otra cosa.

2. TODO O NADA POR VENTA. Si una orden trae dos ítems y uno no tiene receta,
   no se descuenta ninguno: la venta queda registrada en estado
   `pendiente_receta` con sus ítems guardados. Descontar la mitad obligaría a
   recordar qué parte ya se descontó para no duplicar al reprocesar, y el
   libro mayor quedaría con una venta a medio asentar. Así, cuando el socio
   carga la receta que falta, `reprocesar_venta` la asienta completa y exactamente
   una vez.

3. NADA SE DESCARTA EN SILENCIO. Una venta sin receta, sin mapeo o anterior a
   la `fecha_corte` igual deja su fila en `venta_procesada`, con el estado que
   explica qué pasó. Si se descartara sin registro, el stock mentiría y no
   habría forma de saber por qué.

4. EL STOCK PUEDE QUEDAR NEGATIVO Y SE AVISA. Si se vende un artículo cuyo
   insumo no estaba cargado, la venta se asienta igual y el insumo queda en
   negativo. Rechazar la venta sería perder el dato real; el negativo es
   visible, se reporta como alerta y se corrige con un movimiento de ajuste.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import calculos, db


# ════════════════════════════════════════════════════════════════════════════
# LECTURAS AUXILIARES
# ════════════════════════════════════════════════════════════════════════════

def insumo_por_id(conn: sqlite3.Connection, insumo_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM insumo WHERE id = ?", (insumo_id,)).fetchone()


def articulo_por_id(conn: sqlite3.Connection, articulo_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM articulo WHERE id = ?", (articulo_id,)).fetchone()


def receta_de(conn: sqlite3.Connection, articulo_id: int) -> List[Dict[str, Any]]:
    """La receta de un artículo con los datos del insumo ya pegados.

    Trae `peso_unitario_g` porque el cálculo del peso de envío lo necesita, y
    `modo_stock` porque las alertas se expresan en la unidad del insumo.
    """
    filas = conn.execute(
        """SELECT r.insumo_id, r.cantidad,
                  i.nombre, i.peso_unitario_g, i.modo_stock,
                  i.stock_unidades, i.alerta_cuando_queden, i.activo
             FROM receta r
             JOIN insumo i ON i.id = r.insumo_id
            WHERE r.articulo_id = ?
            ORDER BY i.nombre""",
        (articulo_id,),
    ).fetchall()
    return [dict(f) for f in filas]


def envio_de_articulo(conn: sqlite3.Connection, articulo_id: int) -> Optional[Dict[str, Any]]:
    """Peso y medidas de envío de un artículo. Lo que consume el cotizador."""
    art = articulo_por_id(conn, articulo_id)
    if art is None:
        return None
    return calculos.calcular_envio(dict(art), receta_de(conn, articulo_id))


# ════════════════════════════════════════════════════════════════════════════
# RESOLUCIÓN DE ARTÍCULO POR CANAL
# ════════════════════════════════════════════════════════════════════════════

# Columna de `articulo` que sirve de respaldo cuando no hay fila en
# `mapeo_canal`. Los SKU ya están en el artículo "para cruzar con los otros
# sistemas", así que exigir además un mapeo explícito sería pedirle al socio
# que cargue el mismo dato dos veces. Mercado Libre no tiene respaldo: su
# item_id no se parece a nada que el artículo guarde, y el mapeo es
# obligatorio.
_COLUMNA_RESPALDO = {
    "elgadget": "sku_elgadget",
    "empretienda": "id_empretienda",
}


def resolver_articulo_id(
    conn: sqlite3.Connection,
    canal: str,
    id_externo_item: Optional[str],
    variacion_externa: str = "",
) -> Optional[int]:
    """Del identificador que manda el canal al artículo del sistema.

    Orden de resolución:
      1. `mapeo_canal` exacto, con variante.
      2. `mapeo_canal` de la publicación sin variante: un mapeo cargado sin
         variante cubre todas las variantes de esa publicación, que es lo
         razonable cuando las variantes son colores del mismo artículo.
      3. El SKU propio del artículo, si el canal tiene columna de respaldo.
    """
    if not id_externo_item:
        return None

    id_externo_item = str(id_externo_item).strip()
    variacion = (variacion_externa or "").strip()

    if variacion:
        fila = conn.execute(
            """SELECT articulo_id FROM mapeo_canal
                WHERE canal = ? AND id_externo = ? AND variacion_externa = ?""",
            (canal, id_externo_item, variacion),
        ).fetchone()
        if fila:
            return int(fila["articulo_id"])

    fila = conn.execute(
        """SELECT articulo_id FROM mapeo_canal
            WHERE canal = ? AND id_externo = ? AND variacion_externa = ''""",
        (canal, id_externo_item),
    ).fetchone()
    if fila:
        return int(fila["articulo_id"])

    columna = _COLUMNA_RESPALDO.get(canal)
    if columna:
        fila = conn.execute(
            f"SELECT id FROM articulo WHERE {columna} = ?", (id_externo_item,)
        ).fetchone()
        if fila:
            return int(fila["id"])

    return None


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ════════════════════════════════════════════════════════════════════════════

def alertas_actuales(conn: sqlite3.Connection, incluir_inactivos: bool = False) -> List[Dict[str, Any]]:
    """Todos los insumos que hoy están en o por debajo de su umbral."""
    sql = "SELECT * FROM insumo"
    if not incluir_inactivos:
        sql += " WHERE activo = 1"
    sql += " ORDER BY nombre"

    alertas = []
    for fila in conn.execute(sql).fetchall():
        insumo = dict(fila)
        if calculos.en_alerta(insumo):
            alertas.append(calculos.describir_alerta(insumo))
    return alertas


def _evaluar_alertas(
    conn: sqlite3.Connection,
    insumo_ids: Iterable[int],
    stock_previo: Dict[int, float],
) -> List[Dict[str, Any]]:
    """Alertas de los insumos que acaba de tocar un movimiento.

    `recien_cruzado` distingue el insumo que cruzó el umbral CON este
    movimiento del que ya venía abajo. Sin esa distinción, cada venta volvería
    a avisar por los mismos insumos y el aviso se vuelve ruido que el socio
    aprende a ignorar.
    """
    alertas = []
    for insumo_id in dict.fromkeys(insumo_ids):  # únicos, conservando el orden
        fila = insumo_por_id(conn, insumo_id)
        if fila is None:
            continue
        insumo = dict(fila)
        if not calculos.en_alerta(insumo):
            continue

        alerta = calculos.describir_alerta(insumo)
        previo = stock_previo.get(insumo_id)
        alerta["recien_cruzado"] = (
            previo is not None and not calculos.en_alerta(insumo, stock_unidades=previo)
        )
        alertas.append(alerta)
    return alertas


# ════════════════════════════════════════════════════════════════════════════
# MOVIMIENTOS MANUALES
# ════════════════════════════════════════════════════════════════════════════

# El signo del movimiento lo determina el tipo, no quien llama: así una carga
# de 3 kg de merma no puede sumar stock por un signo olvidado. El 'ajuste' es
# la excepción deliberada, porque es justamente el delta con signo.
_SIGNO_POR_TIPO = {
    "ingreso": 1,
    "devolucion": 1,
    "inventario_inicial": 1,
    "merma": -1,
    "venta": -1,
    "ajuste": 0,  # se respeta el signo que venga
}


def asegurar_fecha_corte(conn: sqlite3.Connection) -> Optional[str]:
    """La `fecha_corte` es la fecha de la primera carga de stock.

    Se fija sola con el primer `inventario_inicial` para que no quede sin
    definir, que es el estado peligroso: sin corte, una sincronización de
    Mercado Libre traería el historial completo de ventas y lo descontaría de
    un inventario que recién se está cargando. Se puede sobrescribir a mano
    por el endpoint de config.
    """
    if db.get_config(conn, "fecha_corte"):
        return None
    hoy = db.hoy_iso()
    db.set_config(conn, "fecha_corte", hoy)
    return hoy


def registrar_movimiento_manual(
    conn: sqlite3.Connection,
    insumo_id: int,
    cantidad: float,
    tipo: str,
    *,
    en_unidades: bool = False,
    usuario: Optional[str] = None,
    nota: Optional[str] = None,
) -> Dict[str, Any]:
    """Ingreso, merma, ajuste o devolución cargados a mano.

    `cantidad` viene en la unidad de pantalla del insumo (kilos si el modo es
    'peso'), salvo que `en_unidades` diga lo contrario. El signo lo pone el
    tipo; ver `_SIGNO_POR_TIPO`.
    """
    fila = insumo_por_id(conn, insumo_id)
    if fila is None:
        raise ValueError(f"No existe el insumo {insumo_id}")
    if tipo not in _SIGNO_POR_TIPO or tipo == "venta":
        raise ValueError(
            "Tipo de movimiento manual inválido: usar ingreso, merma, ajuste, "
            "devolucion o inventario_inicial (las ventas entran por procesar_venta)"
        )

    insumo = dict(fila)
    cantidad = float(cantidad)
    if cantidad == 0:
        raise ValueError("La cantidad de un movimiento no puede ser cero")

    unidades = cantidad if en_unidades else calculos.a_unidades(
        cantidad, insumo["modo_stock"], float(insumo["peso_unitario_g"])
    )

    signo = _SIGNO_POR_TIPO[tipo]
    if signo != 0:
        unidades = abs(unidades) * signo

    stock_previo = {insumo_id: float(insumo["stock_unidades"] or 0.0)}

    with db.transaccion(conn):
        fecha_corte_fijada = (
            asegurar_fecha_corte(conn) if tipo == "inventario_inicial" else None
        )
        movimiento_id = db.registrar_movimiento(
            conn, insumo_id, unidades, tipo, usuario=usuario, nota=nota
        )

    return {
        "movimiento_id": movimiento_id,
        "insumo_id": insumo_id,
        "tipo": tipo,
        "cantidad_unidades": round(unidades, 4),
        "stock": calculos.stock_para_pantalla(dict(insumo_por_id(conn, insumo_id))),
        "fecha_corte_fijada": fecha_corte_fijada,
        "alertas": _evaluar_alertas(conn, [insumo_id], stock_previo),
    }


def fijar_stock(
    conn: sqlite3.Connection,
    insumo_id: int,
    cantidad: float,
    *,
    en_unidades: bool = False,
    usuario: Optional[str] = None,
    nota: Optional[str] = None,
) -> Dict[str, Any]:
    """Deja el stock de un insumo en un valor absoluto, contando el inventario.

    No escribe `stock_unidades`: calcula el delta contra lo que hay y asienta
    un movimiento por esa diferencia. Es la única forma de que "el inventario
    físico dice 1.240" no rompa el libro mayor.

    El primer conteo de un insumo se asienta como `inventario_inicial` (y fija
    la `fecha_corte` si todavía no estaba); los siguientes son `ajuste`.
    """
    fila = insumo_por_id(conn, insumo_id)
    if fila is None:
        raise ValueError(f"No existe el insumo {insumo_id}")

    insumo = dict(fila)
    objetivo = float(cantidad) if en_unidades else calculos.a_unidades(
        float(cantidad), insumo["modo_stock"], float(insumo["peso_unitario_g"])
    )
    actual = float(insumo["stock_unidades"] or 0.0)
    delta = objetivo - actual

    tiene_movimientos = conn.execute(
        "SELECT 1 FROM movimiento_stock WHERE insumo_id = ? LIMIT 1", (insumo_id,)
    ).fetchone()
    tipo = "ajuste" if tiene_movimientos else "inventario_inicial"

    if abs(delta) < 1e-9:
        return {
            "insumo_id": insumo_id,
            "sin_cambios": True,
            "movimiento_id": None,
            "stock": calculos.stock_para_pantalla(insumo),
            "alertas": [],
            "fecha_corte_fijada": None,
        }

    stock_previo = {insumo_id: actual}
    with db.transaccion(conn):
        fecha_corte_fijada = (
            asegurar_fecha_corte(conn) if tipo == "inventario_inicial" else None
        )
        movimiento_id = db.registrar_movimiento(
            conn,
            insumo_id,
            delta,
            tipo,
            usuario=usuario,
            nota=nota or ("Conteo de inventario" if tipo == "inventario_inicial" else "Ajuste por conteo"),
        )

    return {
        "insumo_id": insumo_id,
        "sin_cambios": False,
        "movimiento_id": movimiento_id,
        "tipo": tipo,
        "delta_unidades": round(delta, 4),
        "stock": calculos.stock_para_pantalla(dict(insumo_por_id(conn, insumo_id))),
        "fecha_corte_fijada": fecha_corte_fijada,
        "alertas": _evaluar_alertas(conn, [insumo_id], stock_previo),
    }


# ════════════════════════════════════════════════════════════════════════════
# MOTOR DE DESCUENTO POR VENTA
# ════════════════════════════════════════════════════════════════════════════

def _normalizar_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Valida y uniforma los ítems de una venta.

    Un ítem identifica el artículo de una de dos formas: `articulo_id` directo
    (venta manual, o un canal que ya resolvió el artículo) o
    `id_externo_item` + `variacion_externa` para que lo resuelva el mapeo.
    """
    if not items:
        raise ValueError("La venta no tiene ítems")

    normalizados = []
    for crudo in items:
        cantidad = float(crudo.get("cantidad") or 0)
        if cantidad <= 0:
            raise ValueError("La cantidad vendida de cada ítem debe ser mayor que cero")

        articulo_id = crudo.get("articulo_id")
        id_externo_item = crudo.get("id_externo_item")
        if not articulo_id and not id_externo_item:
            raise ValueError(
                "Cada ítem necesita `articulo_id` o `id_externo_item` para resolver el artículo"
            )

        normalizados.append(
            {
                "articulo_id": int(articulo_id) if articulo_id else None,
                "id_externo_item": str(id_externo_item) if id_externo_item else None,
                "variacion_externa": str(crudo.get("variacion_externa") or ""),
                "cantidad": cantidad,
            }
        )
    return normalizados


def _registrar_venta(
    conn: sqlite3.Connection,
    canal: str,
    id_externo: str,
    estado: str,
    fecha_venta: Optional[str],
    items: List[Dict[str, Any]],
    detalle: Optional[str],
) -> None:
    conn.execute(
        """INSERT INTO venta_procesada
               (canal, id_externo, estado, fecha_venta, fecha_proceso, items_json, detalle)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(canal, id_externo) DO UPDATE SET
               estado        = excluded.estado,
               fecha_venta   = excluded.fecha_venta,
               fecha_proceso = excluded.fecha_proceso,
               items_json    = excluded.items_json,
               detalle       = excluded.detalle""",
        (
            canal,
            id_externo,
            estado,
            fecha_venta,
            db.ahora_iso(),
            json.dumps(items, ensure_ascii=False),
            detalle,
        ),
    )


def procesar_venta(
    conn: sqlite3.Connection,
    canal: str,
    id_externo: str,
    items: Sequence[Dict[str, Any]],
    *,
    fecha_venta: Optional[str] = None,
    usuario: Optional[str] = None,
    nota: Optional[str] = None,
    forzar: bool = False,
) -> Dict[str, Any]:
    """Procesa una venta y descuenta los insumos de su receta.

    Es el punto de entrada único: Mercado Libre, El Gadget, Empretienda y las
    ventas manuales llegan todas acá.

    `id_externo` identifica la ORDEN y es la clave de idempotencia. `forzar`
    es solo para `reprocesar_venta`: nunca puede pisar una venta que ya está
    en estado `procesada`, así que no hay forma de descontar dos veces.
    """
    if canal not in db.CANALES_VENTA:
        raise ValueError(f"Canal inválido: {canal}. Válidos: {', '.join(db.CANALES_VENTA)}")
    id_externo = str(id_externo or "").strip()
    if not id_externo:
        raise ValueError("La venta necesita un id_externo para poder ser idempotente")

    items_norm = _normalizar_items(items)

    with db.transaccion(conn):
        # ── 1. Idempotencia ───────────────────────────────────────────────
        existente = conn.execute(
            "SELECT * FROM venta_procesada WHERE canal = ? AND id_externo = ?",
            (canal, id_externo),
        ).fetchone()
        if existente is not None and (not forzar or existente["estado"] == "procesada"):
            return {
                "canal": canal,
                "id_externo": id_externo,
                "estado": existente["estado"],
                "ya_estaba_procesada": True,
                "articulos": [],
                "movimientos": [],
                "alertas": [],
                "avisos": [
                    f"La venta {canal}/{id_externo} ya estaba registrada "
                    f"(estado: {existente['estado']}). No se descontó nada de nuevo."
                ],
            }

        # ── 2. Fecha de corte ─────────────────────────────────────────────
        fecha_corte = db.get_fecha_corte(conn)
        fecha = db.a_fecha(fecha_venta)
        if fecha_corte and fecha and fecha < fecha_corte:
            detalle = (
                f"Venta del {fecha.isoformat()}, anterior a la fecha de corte "
                f"{fecha_corte.isoformat()}: no se descuenta."
            )
            _registrar_venta(conn, canal, id_externo, "ignorada_fecha_corte",
                             fecha_venta, items_norm, detalle)
            return {
                "canal": canal,
                "id_externo": id_externo,
                "estado": "ignorada_fecha_corte",
                "ya_estaba_procesada": False,
                "articulos": [],
                "movimientos": [],
                "alertas": [],
                "avisos": [detalle],
            }

        # ── 3. Resolver los artículos ─────────────────────────────────────
        avisos: List[str] = []
        sin_mapeo: List[str] = []
        resueltos: List[Dict[str, Any]] = []

        for item in items_norm:
            articulo_id = item["articulo_id"]
            if articulo_id is None:
                articulo_id = resolver_articulo_id(
                    conn, canal, item["id_externo_item"], item["variacion_externa"]
                )

            art = articulo_por_id(conn, articulo_id) if articulo_id else None
            if art is None:
                etiqueta = item["id_externo_item"] or f"articulo_id={item['articulo_id']}"
                if item["variacion_externa"]:
                    etiqueta += f" (variante {item['variacion_externa']})"
                sin_mapeo.append(etiqueta)
                continue

            resueltos.append(
                {
                    "articulo_id": int(art["id"]),
                    "nombre": art["nombre"],
                    "cantidad": item["cantidad"],
                    "receta": receta_de(conn, int(art["id"])),
                }
            )

        if sin_mapeo:
            detalle = (
                "No se pudo resolver a qué artículo corresponde: "
                + "; ".join(sin_mapeo)
                + ". La venta queda registrada; cargá el mapeo de canal y reprocesala."
            )
            _registrar_venta(conn, canal, id_externo, "pendiente_mapeo",
                             fecha_venta, items_norm, detalle)
            return {
                "canal": canal,
                "id_externo": id_externo,
                "estado": "pendiente_mapeo",
                "ya_estaba_procesada": False,
                "articulos": [
                    {k: v for k, v in r.items() if k != "receta"} for r in resueltos
                ],
                "movimientos": [],
                "alertas": [],
                "avisos": [detalle],
            }

        # ── 4. ¿Están todas las recetas? ──────────────────────────────────
        sin_receta = [r["nombre"] for r in resueltos if not r["receta"]]
        if sin_receta:
            detalle = (
                "Sin receta cargada: "
                + "; ".join(sin_receta)
                + ". La venta queda registrada y pendiente de recetar; "
                "no se descontó stock de ningún ítem de esta venta."
            )
            _registrar_venta(conn, canal, id_externo, "pendiente_receta",
                             fecha_venta, items_norm, detalle)
            return {
                "canal": canal,
                "id_externo": id_externo,
                "estado": "pendiente_receta",
                "ya_estaba_procesada": False,
                "articulos": [
                    {k: v for k, v in r.items() if k != "receta"} for r in resueltos
                ],
                "movimientos": [],
                "alertas": [],
                "avisos": [detalle],
            }

        # ── 5. Descontar ──────────────────────────────────────────────────
        stock_previo: Dict[int, float] = {}
        movimientos: List[Dict[str, Any]] = []
        tocados: List[int] = []

        for resuelto in resueltos:
            for consumo in calculos.consumo_de_receta(resuelto["receta"], resuelto["cantidad"]):
                insumo_id = int(consumo["insumo_id"])
                if insumo_id not in stock_previo:
                    actual = insumo_por_id(conn, insumo_id)
                    stock_previo[insumo_id] = float(actual["stock_unidades"] or 0.0)

                movimiento_id = db.registrar_movimiento(
                    conn,
                    insumo_id,
                    consumo["cantidad_unidades"],
                    "venta",
                    origen_canal=canal,
                    referencia_externa=id_externo,
                    articulo_id=resuelto["articulo_id"],
                    usuario=usuario,
                    nota=nota,
                )
                tocados.append(insumo_id)

                insumo = dict(insumo_por_id(conn, insumo_id))
                movimientos.append(
                    {
                        "movimiento_id": movimiento_id,
                        "insumo_id": insumo_id,
                        "insumo": insumo["nombre"],
                        "articulo_id": resuelto["articulo_id"],
                        "cantidad_unidades": round(consumo["cantidad_unidades"], 4),
                        "stock_resultante": calculos.stock_para_pantalla(insumo),
                    }
                )

        _registrar_venta(conn, canal, id_externo, "procesada", fecha_venta, items_norm, None)

        alertas = _evaluar_alertas(conn, tocados, stock_previo)
        negativos = [a["nombre"] for a in alertas if a.get("stock_negativo")]
        if negativos:
            avisos.append(
                "Quedaron en negativo (se vendió material que no estaba cargado): "
                + ", ".join(negativos)
            )

    return {
        "canal": canal,
        "id_externo": id_externo,
        "estado": "procesada",
        "ya_estaba_procesada": False,
        "articulos": [{k: v for k, v in r.items() if k != "receta"} for r in resueltos],
        "movimientos": movimientos,
        "alertas": alertas,
        "avisos": avisos,
    }


def procesar_lote(
    conn: sqlite3.Connection, ventas: Sequence[Dict[str, Any]], usuario: Optional[str] = None
) -> Dict[str, Any]:
    """Procesa varias ventas, una por una.

    Cada venta es independiente: la que falla no arrastra a las demás. Es lo
    que va a usar la sincronización de Mercado Libre, que trae una ventana de
    órdenes donde algunas ya estaban procesadas.
    """
    resultados = []
    for venta in ventas:
        try:
            resultados.append(
                procesar_venta(
                    conn,
                    venta.get("canal"),
                    venta.get("id_externo"),
                    venta.get("items") or [],
                    fecha_venta=venta.get("fecha_venta"),
                    usuario=venta.get("usuario") or usuario,
                    nota=venta.get("nota"),
                )
            )
        except (ValueError, sqlite3.Error) as e:
            resultados.append(
                {
                    "canal": venta.get("canal"),
                    "id_externo": venta.get("id_externo"),
                    "estado": "error",
                    "error": str(e),
                }
            )

    resumen: Dict[str, int] = {}
    for r in resultados:
        clave = r["estado"] if not r.get("ya_estaba_procesada") else "ya_procesada"
        resumen[clave] = resumen.get(clave, 0) + 1

    return {"total": len(resultados), "resumen": resumen, "resultados": resultados}


def reprocesar_venta(conn: sqlite3.Connection, canal: str, id_externo: str) -> Dict[str, Any]:
    """Reintenta una venta que quedó pendiente de receta o de mapeo.

    Es la contracara necesaria de la idempotencia: sin esto, la fila en
    `venta_procesada` bloquearía para siempre el descuento de una venta que
    quedó pendiente, y el stock nunca se pondría al día.

    Una venta ya `procesada` no se reprocesa (devolvería a descontar), y una
    `ignorada_fecha_corte` tampoco: esa fue una decisión, no un pendiente.
    """
    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE canal = ? AND id_externo = ?",
        (canal, id_externo),
    ).fetchone()
    if fila is None:
        raise ValueError(f"No hay ninguna venta registrada como {canal}/{id_externo}")

    if fila["estado"] not in ("pendiente_receta", "pendiente_mapeo"):
        return {
            "canal": canal,
            "id_externo": id_externo,
            "estado": fila["estado"],
            "ya_estaba_procesada": True,
            "articulos": [],
            "movimientos": [],
            "alertas": [],
            "avisos": [
                f"La venta está en estado {fila['estado']}: no es un pendiente y no se reprocesa."
            ],
        }

    items = json.loads(fila["items_json"] or "[]")
    return procesar_venta(
        conn,
        canal,
        id_externo,
        items,
        fecha_venta=fila["fecha_venta"],
        nota="Reproceso de venta pendiente",
        forzar=True,
    )


def reprocesar_pendientes(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Reintenta todas las ventas pendientes. Para correr tras cargar recetas."""
    filas = conn.execute(
        """SELECT canal, id_externo FROM venta_procesada
            WHERE estado IN ('pendiente_receta', 'pendiente_mapeo')
            ORDER BY fecha_venta, id_externo"""
    ).fetchall()

    resultados = [reprocesar_venta(conn, f["canal"], f["id_externo"]) for f in filas]

    resumen: Dict[str, int] = {}
    for r in resultados:
        resumen[r["estado"]] = resumen.get(r["estado"], 0) + 1

    return {"total": len(resultados), "resumen": resumen, "resultados": resultados}
