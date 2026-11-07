# -*- coding: utf-8 -*-
"""
Cancelación de ventas y restitución de stock.

El test que da sentido a todo el archivo es
`test_la_reversa_devuelve_lo_descontado_aunque_la_receta_haya_cambiado`: es la
diferencia entre revertir los movimientos reales y recalcular la receta, y es
un error que no falla, solo deja el stock mal.
"""

import sqlite3

import pytest

from insumos_app.tests.conftest import (
    assert_libro_mayor_cierra, crear_articulo, crear_mapeo, poner_receta,
)
from insumos_app import db, stock


def _vender_una_borla(conn, taller, orden="3000001", cantidad=1):
    return stock.procesar_venta(
        conn, "manual", orden, [{"articulo_id": taller["borla"], "cantidad": cantidad}]
    )


# ════════════════════════════════════════════════════════════════════════════
# LO QUE SE REVIERTE ES EL MOVIMIENTO, NO LA RECETA
# ════════════════════════════════════════════════════════════════════════════

def test_la_reversa_devuelve_lo_descontado_aunque_la_receta_haya_cambiado(conn, taller):
    """EL test de este archivo.

    Entre la venta y la cancelación alguien edita la receta. Recalcular el
    consumo desde la receta nueva restituiría 10 caireles cuando se habían
    descontado 6: el stock quedaría mal sin que nada falle. La reversa tiene
    que devolver exactamente lo que el libro mayor dice que salió.
    """
    stock.fijar_stock(conn, taller["cairel"], 5.0)        # 2.000 unidades
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    _vender_una_borla(conn, taller, cantidad=2)           # 2 × 6 caireles = −12
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial - 12

    # La receta cambia DESPUÉS de la venta
    poner_receta(conn, taller["borla"], [(taller["cairel"], 10)])

    stock.cancelar_venta(conn, "manual", "3000001")

    final = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]
    assert final == inicial, (
        "La cancelación tiene que devolver los 12 caireles que salieron, no los 20 "
        "que pediría la receta nueva"
    )
    assert_libro_mayor_cierra(conn)


def test_la_reversa_sobrevive_a_que_la_receta_pierda_un_insumo(conn, taller):
    """Si el insumo ya no está en la receta, igual hay que devolverlo."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.fijar_stock(conn, taller["argolla"], 500)
    stock.fijar_stock(conn, taller["cinta"], 50)
    previos = {
        k: stock.insumo_por_id(conn, taller[k])["stock_unidades"]
        for k in ("cairel", "argolla", "cinta")
    }

    _vender_una_borla(conn, taller)
    # la receta se reduce a un solo insumo
    conn.execute("DELETE FROM receta WHERE articulo_id = ?", (taller["borla"],))
    poner_receta(conn, taller["borla"], [(taller["cairel"], 6)])

    stock.cancelar_venta(conn, "manual", "3000001")

    for clave, antes in previos.items():
        assert stock.insumo_por_id(conn, taller[clave])["stock_unidades"] == antes
    assert_libro_mayor_cierra(conn)


def test_la_devolucion_apunta_al_movimiento_que_revierte(conn, taller):
    """Sin ese rastro, un stock que no cierra no se puede reconstruir."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    venta = _vender_una_borla(conn, taller)
    originales = {m["movimiento_id"] for m in venta["movimientos"]}

    resultado = stock.cancelar_venta(conn, "manual", "3000001")

    assert {m["revierte_movimiento_id"] for m in resultado["movimientos"]} == originales
    devoluciones = conn.execute(
        """SELECT * FROM movimiento_stock
            WHERE tipo = 'devolucion' AND referencia_externa = '3000001'"""
    ).fetchall()
    assert len(devoluciones) == 3            # un insumo por línea de receta
    assert all(d["origen_canal"] == "manual" for d in devoluciones)
    assert all(d["articulo_id"] == taller["borla"] for d in devoluciones)


def test_una_venta_de_varios_articulos_se_revierte_completa(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.fijar_stock(conn, taller["cadena"], 2.0)
    stock.fijar_stock(conn, taller["argolla"], 500)
    stock.fijar_stock(conn, taller["cinta"], 50)
    previos = {
        k: stock.insumo_por_id(conn, taller[k])["stock_unidades"]
        for k in ("cairel", "cadena", "argolla", "cinta")
    }

    stock.procesar_venta(conn, "empretienda", "EMP-1", [
        {"articulo_id": taller["borla"], "cantidad": 2},
        {"articulo_id": taller["guirnalda"], "cantidad": 1},
    ])
    resultado = stock.cancelar_venta(conn, "empretienda", "EMP-1")

    assert resultado["restituyo_stock"] is True
    for clave, antes in previos.items():
        assert stock.insumo_por_id(conn, taller[clave])["stock_unidades"] == antes
    assert_libro_mayor_cierra(conn)


# ════════════════════════════════════════════════════════════════════════════
# IDEMPOTENCIA
# ════════════════════════════════════════════════════════════════════════════

def test_cancelar_dos_veces_no_restituye_dos_veces(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]
    _vender_una_borla(conn, taller)

    primera = stock.cancelar_venta(conn, "manual", "3000001")
    intermedio = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]
    segunda = stock.cancelar_venta(conn, "manual", "3000001")

    assert primera["ya_estaba_cancelada"] is False
    assert segunda["ya_estaba_cancelada"] is True
    assert not segunda["movimientos"]
    assert intermedio == inicial
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial


def test_cancelar_cuatro_veces_tampoco(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]
    _vender_una_borla(conn, taller)
    for _ in range(4):
        stock.cancelar_venta(conn, "manual", "3000001")

    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial
    devoluciones = conn.execute(
        "SELECT COUNT(*) FROM movimiento_stock WHERE tipo = 'devolucion'"
    ).fetchone()[0]
    assert devoluciones == 3     # una sola tanda


def test_el_estado_queda_cancelada_con_su_fecha(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    _vender_una_borla(conn, taller)
    stock.cancelar_venta(conn, "manual", "3000001", motivo="Comprador se arrepintió")

    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE canal = 'manual' AND id_externo = '3000001'"
    ).fetchone()
    assert fila["estado"] == "cancelada"
    assert fila["estado_previo"] == "procesada"
    assert fila["fecha_cancelacion"]
    assert "Comprador se arrepintió" in fila["detalle"]


# ════════════════════════════════════════════════════════════════════════════
# VENTAS QUE NUNCA DESCONTARON
# ════════════════════════════════════════════════════════════════════════════

def test_cancelar_una_pendiente_de_receta_no_genera_movimientos(conn, taller):
    articulo = crear_articulo(conn, "Servilletero de madera")
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 1}])

    resultado = stock.cancelar_venta(conn, "manual", "m-1")

    assert resultado["estado"] == "cancelada"
    assert resultado["estado_previo"] == "pendiente_receta"
    assert resultado["restituyo_stock"] is False
    assert not resultado["movimientos"]
    assert conn.execute("SELECT COUNT(*) FROM movimiento_stock").fetchone()[0] == 0


def test_cancelar_una_pendiente_de_mapeo_no_genera_movimientos(conn, taller):
    stock.procesar_venta(conn, "ml", "2000500",
                         [{"id_externo_item": "MLA999999999", "cantidad": 1}])
    resultado = stock.cancelar_venta(conn, "ml", "2000500")

    assert resultado["estado_previo"] == "pendiente_mapeo"
    assert resultado["restituyo_stock"] is False


def test_cancelar_una_ignorada_por_fecha_de_corte_no_genera_movimientos(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    stock.procesar_venta(conn, "manual", "m-1",
                         [{"articulo_id": taller["borla"], "cantidad": 1}],
                         fecha_venta="2026-09-01")
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    resultado = stock.cancelar_venta(conn, "manual", "m-1")

    assert resultado["estado_previo"] == "ignorada_fecha_corte"
    assert resultado["restituyo_stock"] is False
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial


def test_la_cancelacion_sin_restitucion_se_explica_sola(conn, taller):
    """`estado_previo` existe para que no haya que adivinar por qué una venta
    cancelada no devolvió nada."""
    articulo = crear_articulo(conn, "Servilletero de madera")
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 1}])
    stock.cancelar_venta(conn, "manual", "m-1")

    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE id_externo = 'm-1'").fetchone()
    assert fila["estado_previo"] == "pendiente_receta"
    assert "no había descontado stock" in fila["detalle"]


# ════════════════════════════════════════════════════════════════════════════
# EL CRUCE: UNA VENTA CANCELADA NO VUELVE A DESCONTAR POR NINGÚN CAMINO
# ════════════════════════════════════════════════════════════════════════════

def test_una_cancelada_no_entra_por_reprocesar_pendientes(conn, taller):
    """El riesgo concreto: la venta quedó pendiente, se canceló, y después
    alguien carga la receta y corre el reproceso."""
    articulo = crear_articulo(conn, "Servilletero de madera")
    stock.fijar_stock(conn, taller["argolla"], 500)
    inicial = stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"]

    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 1}])
    stock.cancelar_venta(conn, "manual", "m-1")
    poner_receta(conn, articulo, [(taller["argolla"], 4)])

    resultado = stock.reprocesar_pendientes(conn)

    assert resultado["total"] == 0
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == inicial


def test_una_cancelada_no_entra_por_reprocesar_una(conn, taller):
    articulo = crear_articulo(conn, "Servilletero de madera")
    stock.fijar_stock(conn, taller["argolla"], 500)
    inicial = stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"]

    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 1}])
    stock.cancelar_venta(conn, "manual", "m-1")
    poner_receta(conn, articulo, [(taller["argolla"], 4)])

    resultado = stock.reprocesar_venta(conn, "manual", "m-1")

    assert resultado["estado"] == "cancelada"
    assert resultado["ya_estaba_procesada"] is True
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == inicial


def test_forzar_no_puede_descontar_una_cancelada(conn, taller):
    """La garantía vive en el motor, no en la disciplina de quien lo llama."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    _vender_una_borla(conn, taller)
    stock.cancelar_venta(conn, "manual", "3000001")
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    resultado = stock.procesar_venta(
        conn, "manual", "3000001",
        [{"articulo_id": taller["borla"], "cantidad": 1}], forzar=True)

    assert resultado["ya_estaba_procesada"] is True
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial


def test_reenviar_la_venta_cancelada_no_la_resucita(conn, taller):
    """Una sincronización atrasada puede volver a postear la orden."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    _vender_una_borla(conn, taller)
    stock.cancelar_venta(conn, "manual", "3000001")
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    resultado = _vender_una_borla(conn, taller)

    assert resultado["ya_estaba_procesada"] is True
    assert resultado["estado"] == "cancelada"
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial


# ════════════════════════════════════════════════════════════════════════════
# ÓRDENES QUE NUNCA LLEGAMOS A VER
# ════════════════════════════════════════════════════════════════════════════

def test_cancelar_una_venta_inexistente_es_error_por_defecto(conn):
    """Protege del id mal tipeado en la pantalla de carga manual."""
    with pytest.raises(ValueError, match="No hay ninguna venta registrada"):
        stock.cancelar_venta(conn, "ml", "no-existe")
    assert conn.execute("SELECT COUNT(*) FROM venta_procesada").fetchone()[0] == 0


def test_un_sincronizador_puede_dejar_constancia_de_una_orden_desconocida(conn):
    resultado = stock.cancelar_venta(conn, "ml", "2000777", registrar_si_no_existe=True)

    assert resultado["estado"] == "cancelada"
    assert resultado["estado_previo"] is None
    assert resultado["restituyo_stock"] is False
    assert conn.execute(
        "SELECT estado FROM venta_procesada WHERE id_externo = '2000777'"
    ).fetchone()["estado"] == "cancelada"


def test_registrar_la_cancelacion_desconocida_PROTEGE_el_stock(conn, taller):
    """Es la razón de ser de `registrar_si_no_existe`.

    Secuencia real: la orden se cancela en el canal antes de que la veamos, el
    sincronizador de cancelaciones la registra, y después una consulta de
    "órdenes nuevas" atrasada la postea como venta. Sin la fila, se descuenta
    stock de una orden que ya estaba cancelada.
    """
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    crear_mapeo(conn, taller["borla"], "ml", "MLA100000050")
    inicial = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    stock.cancelar_venta(conn, "ml", "2000777", registrar_si_no_existe=True)
    tardia = stock.procesar_venta(conn, "ml", "2000777",
                                  [{"id_externo_item": "MLA100000050", "cantidad": 1}])

    assert tardia["ya_estaba_procesada"] is True
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == inicial


# ════════════════════════════════════════════════════════════════════════════
# CRUCE CON VARIAS PUBLICACIONES DEL MISMO ARTÍCULO
# ════════════════════════════════════════════════════════════════════════════

def test_cancelar_una_de_dos_ventas_del_mismo_articulo_no_toca_la_otra(conn, taller):
    """El cruce de los dos requerimientos: la reversa es por ORDEN, así que dos
    publicaciones del mismo artículo se cancelan independientemente."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)       # 2.000
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000001")
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000002")

    stock.procesar_venta(conn, "ml", "3000001",
                         [{"id_externo_item": "MLA200000001", "cantidad": 1}])
    stock.procesar_venta(conn, "ml", "3000002",
                         [{"id_externo_item": "MLA200000002", "cantidad": 1}])
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 1988.0

    stock.cancelar_venta(conn, "ml", "3000001")

    # se devolvieron 6 (una venta), no 12 (las dos)
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 1994.0
    assert conn.execute(
        "SELECT estado FROM venta_procesada WHERE id_externo = '3000002'"
    ).fetchone()["estado"] == "procesada"
    assert_libro_mayor_cierra(conn)


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS Y LOTES
# ════════════════════════════════════════════════════════════════════════════

def test_la_cancelacion_saca_al_insumo_de_la_alerta(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 0.52)      # 208, umbral 200
    _vender_una_borla(conn, taller, cantidad=2)          # −12 → 196, en alerta
    assert any(a["nombre"].startswith("Cairel") for a in stock.alertas_actuales(conn))

    stock.cancelar_venta(conn, "manual", "3000001")

    assert not any(a["nombre"].startswith("Cairel") for a in stock.alertas_actuales(conn))


def test_la_cancelacion_corrige_un_stock_negativo(conn, taller):
    _vender_una_borla(conn, taller)                      # sin stock cargado → negativo
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == -6
    stock.cancelar_venta(conn, "manual", "3000001")
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 0
    assert_libro_mayor_cierra(conn)


def test_el_lote_de_cancelaciones_resume_cada_caso(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    sin_receta = crear_articulo(conn, "Servilletero de madera")
    _vender_una_borla(conn, taller, orden="3000001")
    stock.procesar_venta(conn, "manual", "3000002",
                         [{"articulo_id": sin_receta, "cantidad": 1}])

    resultado = stock.cancelar_lote(conn, [
        {"canal": "manual", "id_externo": "3000001"},   # descontó: restituye
        {"canal": "manual", "id_externo": "3000002"},   # pendiente: nada que devolver
        {"canal": "manual", "id_externo": "3000001"},   # repetida
        {"canal": "ml", "id_externo": "2000999"},       # desconocida: se registra
        {"canal": "shopify", "id_externo": "x"},        # canal inválido
    ])

    assert resultado["total"] == 5
    assert resultado["resumen"]["cancelada_con_restitucion"] == 1
    assert resultado["resumen"]["cancelada_sin_stock_que_devolver"] == 2
    assert resultado["resumen"]["ya_cancelada"] == 1
    assert resultado["resumen"]["error"] == 1
    assert_libro_mayor_cierra(conn)


def test_volver_a_pasar_el_mismo_lote_no_cambia_nada(conn, taller):
    """Un sincronizador que relee órdenes va a repetir la lista."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    _vender_una_borla(conn, taller)
    lote = [{"canal": "manual", "id_externo": "3000001"}]

    stock.cancelar_lote(conn, lote)
    stock_tras_primera = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]
    segunda = stock.cancelar_lote(conn, lote)

    assert segunda["resumen"]["ya_cancelada"] == 1
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == stock_tras_primera


def test_un_canal_invalido_es_error(conn):
    with pytest.raises(ValueError, match="Canal inválido"):
        stock.cancelar_venta(conn, "shopify", "1")


def test_sin_id_externo_es_error(conn):
    with pytest.raises(ValueError, match="id_externo"):
        stock.cancelar_venta(conn, "ml", "")


# ════════════════════════════════════════════════════════════════════════════
# MIGRACIÓN DEL ESQUEMA v1 → v2
#
# El estado 'cancelada' entró en un CHECK, y SQLite no permite alterarlos: la
# tabla se reconstruye. Si esa reconstrucción pierde filas, se pierde el
# registro de qué ventas ya se procesaron, y eso significa descontar todo de
# nuevo en la próxima sincronización.
# ════════════════════════════════════════════════════════════════════════════

DDL_V1 = """
CREATE TABLE venta_procesada (
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
CREATE TABLE config (clave TEXT PRIMARY KEY, valor TEXT, actualizado_at TEXT);
"""


@pytest.fixture
def base_v1(tmp_path, monkeypatch):
    """Una base con el esquema viejo y datos adentro."""
    ruta = tmp_path / "v1.db"
    monkeypatch.setattr(db, "DB_PATH", ruta)

    crudo = sqlite3.connect(ruta, isolation_level=None)
    crudo.executescript(DDL_V1)
    crudo.execute(
        """INSERT INTO venta_procesada
               (canal, id_externo, estado, fecha_venta, fecha_proceso, items_json, detalle)
           VALUES ('ml', '2000001', 'procesada', '2026-10-20', '2026-10-20T10:00:00',
                   '[{"cantidad": 1}]', NULL)"""
    )
    crudo.execute(
        """INSERT INTO venta_procesada
               (canal, id_externo, estado, fecha_venta, fecha_proceso, items_json, detalle)
           VALUES ('manual', 'm-1', 'pendiente_receta', '2026-10-21',
                   '2026-10-21T10:00:00', '[]', 'Falta receta')"""
    )
    crudo.execute(
        "INSERT INTO config (clave, valor) VALUES ('schema_version', '1')"
    )
    crudo.close()
    return ruta


def test_la_migracion_conserva_las_ventas_ya_procesadas(base_v1):
    """Perderlas haría que la próxima sincronización descuente todo de nuevo."""
    db.migrar()

    conexion = db.conectar()
    filas = {f["id_externo"]: dict(f) for f in
             conexion.execute("SELECT * FROM venta_procesada").fetchall()}
    assert set(filas) == {"2000001", "m-1"}
    assert filas["2000001"]["estado"] == "procesada"
    assert filas["2000001"]["fecha_venta"] == "2026-10-20"
    assert filas["2000001"]["items_json"] == '[{"cantidad": 1}]'
    assert filas["m-1"]["detalle"] == "Falta receta"
    conexion.close()


def test_la_migracion_habilita_el_estado_cancelada(base_v1):
    db.migrar()
    conexion = db.conectar()
    conexion.execute(
        """UPDATE venta_procesada SET estado = 'cancelada', estado_previo = 'procesada',
               fecha_cancelacion = '2026-10-26T20:00:00' WHERE id_externo = '2000001'"""
    )
    fila = conexion.execute(
        "SELECT * FROM venta_procesada WHERE id_externo = '2000001'").fetchone()
    assert fila["estado"] == "cancelada"
    assert fila["estado_previo"] == "procesada"
    conexion.close()


def test_la_migracion_deja_la_version_al_dia_y_no_se_repite(base_v1):
    db.migrar()
    conexion = db.conectar()
    assert db.get_config(conexion, "schema_version") == str(db.SCHEMA_VERSION)
    conexion.close()

    # Correrla de nuevo es inocuo (la API la llama en cada arranque)
    db.migrar()
    db.migrar()
    conexion = db.conectar()
    assert conexion.execute("SELECT COUNT(*) FROM venta_procesada").fetchone()[0] == 2
    conexion.close()


def test_una_base_v1_queda_operativa_despues_de_migrar(base_v1, monkeypatch):
    """La prueba de fuego: cancelar una venta que venía del esquema viejo."""
    db.migrar()
    conexion = db.conectar()

    insumo = conexion.execute(
        """INSERT INTO insumo (nombre, modo_stock, peso_unitario_g, creado_at)
           VALUES ('Cairel', 'unidad', 2.5, ?)""", (db.ahora_iso(),)).lastrowid
    articulo = conexion.execute(
        """INSERT INTO articulo (nombre, largo_real_mm, ancho_real_mm, alto_real_mm, creado_at)
           VALUES ('Borla', 10, 10, 10, ?)""", (db.ahora_iso(),)).lastrowid
    poner_receta(conexion, articulo, [(insumo, 3)])
    stock.fijar_stock(conexion, insumo, 100)

    stock.procesar_venta(conexion, "manual", "nueva-1",
                         [{"articulo_id": articulo, "cantidad": 2}])
    assert stock.insumo_por_id(conexion, insumo)["stock_unidades"] == 94

    stock.cancelar_venta(conexion, "manual", "nueva-1")
    assert stock.insumo_por_id(conexion, insumo)["stock_unidades"] == 100
    assert_libro_mayor_cierra(conexion)
    conexion.close()
