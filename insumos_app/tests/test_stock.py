# -*- coding: utf-8 -*-
"""
Motor de stock: libro mayor, idempotencia, fecha de corte, pendientes y alertas.

Son las cuatro propiedades de las que depende que el stock no mienta, más las
conversiones de unidad que las sostienen.
"""

import sqlite3

import pytest

from insumos_app.tests.conftest import (
    assert_libro_mayor_cierra, crear_articulo, crear_mapeo, poner_receta,
)
from insumos_app import calculos, db, stock


# ════════════════════════════════════════════════════════════════════════════
# EL LIBRO MAYOR — la invariante central
# ════════════════════════════════════════════════════════════════════════════

def test_el_stock_se_reconstruye_sumando_los_movimientos(conn, taller):
    """El test que pide la especificación: `stock_unidades` == Σ movimientos.

    Se somete el sistema a una secuencia larga y mezclada (carga inicial,
    compras, ventas por tres canales, un ajuste, una merma, una devolución,
    una venta pendiente que después se reprocesa) y al final cada insumo tiene
    que poder explicarse sumando su columna del libro mayor.
    """
    # Carga inicial del inventario físico
    stock.fijar_stock(conn, taller["cairel"], 5.0)        # 5 kg → 2.000 caireles
    stock.fijar_stock(conn, taller["cadena"], 2.0)        # 2 kg → 1.111,1 eslabones
    stock.fijar_stock(conn, taller["argolla"], 800)
    stock.fijar_stock(conn, taller["cinta"], 60)

    # Compras
    stock.registrar_movimiento_manual(conn, taller["cairel"], 1.5, "ingreso")
    stock.registrar_movimiento_manual(conn, taller["argolla"], 500, "ingreso")

    # Ventas por los tres canales automáticos y una manual
    stock.procesar_venta(conn, "ml", "2000001", [{"id_externo_item": "MLA100000001", "cantidad": 2}])
    stock.procesar_venta(conn, "elgadget", "EG-5001", [{"id_externo_item": "AFD-20", "cantidad": 1}])
    stock.procesar_venta(conn, "ml", "2000002",
                         [{"id_externo_item": "MLA100000002", "variacion_externa": "VAR-DORADO",
                           "cantidad": 1}])
    stock.procesar_venta(conn, "manual", "manual-001",
                         [{"articulo_id": taller["borla"], "cantidad": 3}])

    # Una orden con dos artículos distintos, que comparten el cairel
    stock.procesar_venta(conn, "empretienda", "EMP-77", [
        {"articulo_id": taller["borla"], "cantidad": 1},
        {"articulo_id": taller["guirnalda"], "cantidad": 1},
    ])

    # Correcciones
    stock.registrar_movimiento_manual(conn, taller["cinta"], 2, "merma", nota="Se mancharon")
    stock.registrar_movimiento_manual(conn, taller["argolla"], -15, "ajuste", nota="Conteo")
    stock.registrar_movimiento_manual(conn, taller["cairel"], 0.1, "devolucion")
    stock.fijar_stock(conn, taller["cadena"], 1.5)        # recuento físico

    # Una venta de un artículo sin receta, que después se receta y se reprocesa
    sin_receta = crear_articulo(conn, "Servilletero de madera", sku_elgadget="AFD-99")
    stock.procesar_venta(conn, "elgadget", "EG-5002",
                         [{"articulo_id": sin_receta, "cantidad": 4}])
    poner_receta(conn, sin_receta, [(taller["argolla"], 1), (taller["cinta"], 2)])
    stock.reprocesar_venta(conn, "elgadget", "EG-5002")

    filas = assert_libro_mayor_cierra(conn)
    assert len(filas) == 4
    # Y no es un cierre trivial: hubo movimiento de verdad.
    total_movimientos = conn.execute("SELECT COUNT(*) FROM movimiento_stock").fetchone()[0]
    assert total_movimientos > 25


def test_el_stock_nunca_se_escribe_sin_movimiento(conn, taller):
    """Cada operación del motor deja el libro mayor cuadrado, una por una."""
    operaciones = [
        lambda: stock.fijar_stock(conn, taller["cairel"], 3.0),
        lambda: stock.registrar_movimiento_manual(conn, taller["cairel"], 0.5, "ingreso"),
        lambda: stock.procesar_venta(conn, "manual", "m-1",
                                     [{"articulo_id": taller["borla"], "cantidad": 1}]),
        lambda: stock.registrar_movimiento_manual(conn, taller["cairel"], 0.2, "merma"),
        lambda: stock.fijar_stock(conn, taller["cairel"], 2.0),
    ]
    for operar in operaciones:
        operar()
        assert_libro_mayor_cierra(conn)


def test_el_movimiento_guarda_de_que_venta_vino(conn, taller):
    """Sin la referencia, un número que no cierra no se puede investigar."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.procesar_venta(conn, "ml", "2000055", [{"id_externo_item": "MLA100000001", "cantidad": 1}])

    mov = conn.execute(
        """SELECT * FROM movimiento_stock
            WHERE insumo_id = ? AND tipo = 'venta'""", (taller["cairel"],)
    ).fetchone()
    assert mov["origen_canal"] == "ml"
    assert mov["referencia_externa"] == "2000055"
    assert mov["articulo_id"] == taller["borla"]


# ════════════════════════════════════════════════════════════════════════════
# EL STOCK SE GUARDA EN UNIDADES
# ════════════════════════════════════════════════════════════════════════════

def test_un_insumo_por_peso_guarda_unidades_no_gramos(conn, taller):
    """La pantalla pide kilos; la base guarda unidades."""
    stock.fijar_stock(conn, taller["cairel"], 2.5)   # 2,5 kg de caireles de 2,5 g
    fila = stock.insumo_por_id(conn, taller["cairel"])
    assert fila["stock_unidades"] == 1000.0
    assert calculos.stock_para_pantalla(dict(fila))["cantidad_pantalla"] == 2.5


def test_el_descuento_de_un_insumo_por_peso_es_una_resta_de_unidades(conn, taller):
    """No hay conversión en el camino del descuento: por eso no acumula error."""
    stock.fijar_stock(conn, taller["cairel"], 2.5)   # 1.000 unidades
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": taller["borla"], "cantidad": 10}])
    # 10 borlas × 6 caireles = 60
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 940.0


def test_cargar_en_unidades_tambien_es_posible(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 400, en_unidades=True)
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 400.0


# ════════════════════════════════════════════════════════════════════════════
# IDEMPOTENCIA
# ════════════════════════════════════════════════════════════════════════════

def test_la_misma_orden_dos_veces_descuenta_una_sola(conn, taller):
    """Mercado Libre va a devolver la misma orden más de una vez."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    antes = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    primera = stock.procesar_venta(conn, "ml", "2000001",
                                   [{"id_externo_item": "MLA100000001", "cantidad": 2}])
    intermedio = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    segunda = stock.procesar_venta(conn, "ml", "2000001",
                                   [{"id_externo_item": "MLA100000001", "cantidad": 2}])
    despues = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    assert primera["ya_estaba_procesada"] is False
    assert segunda["ya_estaba_procesada"] is True
    assert intermedio == antes - 12     # 2 borlas × 6 caireles
    assert despues == intermedio        # la segunda no tocó nada
    assert not segunda["movimientos"]


def test_la_segunda_llamada_no_asienta_movimientos(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    for _ in range(4):
        stock.procesar_venta(conn, "ml", "2000009",
                             [{"id_externo_item": "MLA100000001", "cantidad": 1}])
    ventas = conn.execute(
        """SELECT COUNT(*) FROM movimiento_stock
            WHERE referencia_externa = '2000009'""").fetchone()[0]
    assert ventas == 3   # un movimiento por insumo de la receta de la borla, una sola vez


def test_el_mismo_id_en_otro_canal_es_otra_venta(conn, taller):
    """La clave es (canal, id_externo): un EG-1 y un MLA-1 no se pisan."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.procesar_venta(conn, "manual", "1", [{"articulo_id": taller["borla"], "cantidad": 1}])
    r = stock.procesar_venta(conn, "elgadget", "1", [{"articulo_id": taller["borla"], "cantidad": 1}])
    assert r["ya_estaba_procesada"] is False
    assert r["estado"] == "procesada"


def test_una_venta_sin_id_externo_no_se_acepta(conn, taller):
    """Sin id externo no hay idempotencia posible, así que no se procesa."""
    with pytest.raises(ValueError, match="idempotente"):
        stock.procesar_venta(conn, "ml", "", [{"articulo_id": taller["borla"], "cantidad": 1}])


# ════════════════════════════════════════════════════════════════════════════
# FECHA DE CORTE
# ════════════════════════════════════════════════════════════════════════════

def test_la_primera_carga_de_stock_fija_la_fecha_de_corte(conn, taller):
    assert db.get_fecha_corte(conn) is None
    resultado = stock.fijar_stock(conn, taller["cairel"], 5.0)
    assert resultado["fecha_corte_fijada"] == db.hoy_iso()
    assert db.get_fecha_corte(conn).isoformat() == db.hoy_iso()


def test_la_segunda_carga_no_mueve_la_fecha_de_corte(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-01")
    resultado = stock.fijar_stock(conn, taller["cadena"], 1.0)
    assert resultado["fecha_corte_fijada"] is None
    assert db.get_config(conn, "fecha_corte") == "2026-10-01"


def test_una_venta_anterior_al_corte_se_ignora(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    antes = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    resultado = stock.procesar_venta(
        conn, "ml", "1900001", [{"id_externo_item": "MLA100000001", "cantidad": 5}],
        fecha_venta="2026-09-15",
    )
    assert resultado["estado"] == "ignorada_fecha_corte"
    assert not resultado["movimientos"]
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == antes


def test_la_venta_ignorada_queda_registrada_igual(conn, taller):
    """Descartarla sin registro dejaría la pregunta "¿y esta venta?" sin respuesta."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    stock.procesar_venta(conn, "ml", "1900001",
                         [{"id_externo_item": "MLA100000001", "cantidad": 5}],
                         fecha_venta="2026-09-15")

    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE canal = 'ml' AND id_externo = '1900001'"
    ).fetchone()
    assert fila["estado"] == "ignorada_fecha_corte"
    assert "fecha de corte" in fila["detalle"]


def test_una_venta_del_dia_del_corte_si_se_procesa(conn, taller):
    """El corte es "anterior a", no "anterior o igual a"."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    resultado = stock.procesar_venta(
        conn, "ml", "2000100", [{"id_externo_item": "MLA100000001", "cantidad": 1}],
        fecha_venta="2026-10-20",
    )
    assert resultado["estado"] == "procesada"


def test_la_fecha_de_mercado_libre_con_huso_se_entiende(conn, taller):
    """ML manda `2026-10-20T14:33:00.000-03:00`, no una fecha pelada."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    resultado = stock.procesar_venta(
        conn, "ml", "2000101", [{"id_externo_item": "MLA100000001", "cantidad": 1}],
        fecha_venta="2026-10-19T22:10:00.000-03:00",
    )
    assert resultado["estado"] == "ignorada_fecha_corte"


def test_sin_fecha_de_venta_se_procesa(conn, taller):
    """Una carga manual puede no traer fecha; no se la castiga por eso."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    db.set_config(conn, "fecha_corte", "2026-10-20")
    resultado = stock.procesar_venta(conn, "manual", "m-9",
                                     [{"articulo_id": taller["borla"], "cantidad": 1}])
    assert resultado["estado"] == "procesada"


# ════════════════════════════════════════════════════════════════════════════
# PENDIENTES: SIN RECETA Y SIN MAPEO
# ════════════════════════════════════════════════════════════════════════════

def test_una_venta_sin_receta_se_registra_y_se_avisa(conn, taller):
    """No se descarta en silencio: eso haría que el stock mienta."""
    articulo = crear_articulo(conn, "Pesa de mantel ágata", sku_elgadget="AFD-77")
    resultado = stock.procesar_venta(conn, "elgadget", "EG-1",
                                     [{"articulo_id": articulo, "cantidad": 2}])

    assert resultado["estado"] == "pendiente_receta"
    assert not resultado["movimientos"]
    assert resultado["avisos"]
    assert "Pesa de mantel ágata" in resultado["avisos"][0]

    fila = conn.execute(
        "SELECT * FROM venta_procesada WHERE canal = 'elgadget' AND id_externo = 'EG-1'"
    ).fetchone()
    assert fila["estado"] == "pendiente_receta"


def test_la_venta_pendiente_se_descuenta_al_cargar_la_receta(conn, taller):
    """La contracara de la idempotencia: el pendiente tiene que poder cerrarse."""
    articulo = crear_articulo(conn, "Pesa de mantel ágata")
    stock.fijar_stock(conn, taller["argolla"], 500)
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 2}])
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 500

    poner_receta(conn, articulo, [(taller["argolla"], 4)])
    resultado = stock.reprocesar_venta(conn, "manual", "m-1")

    assert resultado["estado"] == "procesada"
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 492  # 500 − 2×4
    assert_libro_mayor_cierra(conn)


def test_reprocesar_dos_veces_no_descuenta_dos_veces(conn, taller):
    """El reproceso no es una puerta trasera para duplicar el descuento."""
    articulo = crear_articulo(conn, "Pesa de mantel ágata")
    stock.fijar_stock(conn, taller["argolla"], 500)
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": articulo, "cantidad": 2}])
    poner_receta(conn, articulo, [(taller["argolla"], 4)])

    stock.reprocesar_venta(conn, "manual", "m-1")
    segunda = stock.reprocesar_venta(conn, "manual", "m-1")

    assert segunda["ya_estaba_procesada"] is True
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 492


def test_una_venta_sin_mapeo_queda_pendiente_de_mapeo(conn, taller):
    """Una publicación de ML que nadie asoció a un artículo."""
    resultado = stock.procesar_venta(conn, "ml", "2000500",
                                     [{"id_externo_item": "MLA999999999", "cantidad": 1}])
    assert resultado["estado"] == "pendiente_mapeo"
    assert not resultado["movimientos"]
    assert "MLA999999999" in resultado["avisos"][0]


def test_la_venta_sin_mapeo_se_cierra_al_cargar_el_mapeo(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.procesar_venta(conn, "ml", "2000500",
                         [{"id_externo_item": "MLA999999999", "cantidad": 1}])
    crear_mapeo(conn, taller["borla"], "ml", "MLA999999999")

    resultado = stock.reprocesar_venta(conn, "ml", "2000500")
    assert resultado["estado"] == "procesada"
    assert_libro_mayor_cierra(conn)


def test_una_orden_con_un_item_sin_receta_no_descuenta_ninguno(conn, taller):
    """Todo o nada por venta: descontar la mitad dejaría una venta a medio asentar."""
    sin_receta = crear_articulo(conn, "Servilletero de madera")
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    antes = stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"]

    resultado = stock.procesar_venta(conn, "empretienda", "EMP-1", [
        {"articulo_id": taller["borla"], "cantidad": 1},     # sí tiene receta
        {"articulo_id": sin_receta, "cantidad": 1},          # no tiene
    ])

    assert resultado["estado"] == "pendiente_receta"
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == antes


def test_reprocesar_pendientes_cierra_los_que_puede(conn, taller):
    sin_receta = crear_articulo(conn, "Servilletero de madera")
    otro = crear_articulo(conn, "Borla mini")
    stock.fijar_stock(conn, taller["argolla"], 300)

    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": sin_receta, "cantidad": 1}])
    stock.procesar_venta(conn, "manual", "m-2", [{"articulo_id": otro, "cantidad": 1}])

    poner_receta(conn, sin_receta, [(taller["argolla"], 2)])  # solo uno se recetó
    resultado = stock.reprocesar_pendientes(conn)

    assert resultado["total"] == 2
    assert resultado["resumen"]["procesada"] == 1
    assert resultado["resumen"]["pendiente_receta"] == 1
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 298


def test_una_venta_ya_procesada_no_se_reprocesa(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": taller["borla"], "cantidad": 1}])
    resultado = stock.reprocesar_venta(conn, "manual", "m-1")
    assert resultado["ya_estaba_procesada"] is True
    assert "no es un pendiente" in resultado["avisos"][0]


def test_reprocesar_una_venta_inexistente_es_error(conn):
    with pytest.raises(ValueError, match="No hay ninguna venta"):
        stock.reprocesar_venta(conn, "ml", "no-existe")


# ════════════════════════════════════════════════════════════════════════════
# RESOLUCIÓN DE ARTÍCULO
# ════════════════════════════════════════════════════════════════════════════

def test_resuelve_por_mapeo_con_variante(conn, taller):
    assert stock.resolver_articulo_id(conn, "ml", "MLA100000002", "VAR-DORADO") == taller["guirnalda"]


def test_un_mapeo_sin_variante_cubre_todas_las_variantes(conn, taller):
    """Cuando las variantes son colores del mismo artículo, mapear la
    publicación alcanza y no hay que cargar una fila por color."""
    assert stock.resolver_articulo_id(conn, "ml", "MLA100000001", "VAR-ROJO") == taller["borla"]


def test_resuelve_por_sku_de_el_gadget_sin_mapeo_explicito(conn, taller):
    """El SKU ya está en el artículo: pedir además un mapeo sería cargarlo dos veces."""
    assert stock.resolver_articulo_id(conn, "elgadget", "AFD-20") == taller["borla"]


def test_mercado_libre_no_tiene_respaldo_por_sku(conn, taller):
    """El item_id de ML no se parece a nada que el artículo guarde."""
    assert stock.resolver_articulo_id(conn, "ml", "AFD-20") is None


def test_sin_identificador_no_resuelve(conn, taller):
    assert stock.resolver_articulo_id(conn, "ml", None) is None
    assert stock.resolver_articulo_id(conn, "ml", "") is None


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ════════════════════════════════════════════════════════════════════════════

def test_la_venta_que_cruza_el_umbral_avisa(conn, taller):
    # alerta del cairel: 0,5 kg = 200 unidades
    stock.fijar_stock(conn, taller["cairel"], 0.52)   # 208 unidades
    resultado = stock.procesar_venta(conn, "manual", "m-1",
                                     [{"articulo_id": taller["borla"], "cantidad": 2}])  # −12

    alertas = {a["nombre"]: a for a in resultado["alertas"]}
    assert "Cairel de vidrio 10 mm" in alertas
    assert alertas["Cairel de vidrio 10 mm"]["recien_cruzado"] is True
    assert alertas["Cairel de vidrio 10 mm"]["unidad"] == "kg"


def test_la_venta_siguiente_no_vuelve_a_avisar_como_nueva(conn, taller):
    """Si cada venta avisara de lo mismo, el aviso se vuelve ruido."""
    stock.fijar_stock(conn, taller["cairel"], 0.52)
    stock.procesar_venta(conn, "manual", "m-1", [{"articulo_id": taller["borla"], "cantidad": 2}])
    segunda = stock.procesar_venta(conn, "manual", "m-2",
                                   [{"articulo_id": taller["borla"], "cantidad": 1}])

    alertas = {a["nombre"]: a for a in segunda["alertas"]}
    assert alertas["Cairel de vidrio 10 mm"]["recien_cruzado"] is False


def test_sin_cruzar_el_umbral_no_hay_alerta(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.fijar_stock(conn, taller["argolla"], 900)
    stock.fijar_stock(conn, taller["cinta"], 100)
    resultado = stock.procesar_venta(conn, "manual", "m-1",
                                     [{"articulo_id": taller["borla"], "cantidad": 1}])
    assert resultado["alertas"] == []


def test_el_movimiento_manual_tambien_evalua_alertas(conn, taller):
    stock.fijar_stock(conn, taller["cinta"], 12)
    resultado = stock.registrar_movimiento_manual(conn, taller["cinta"], 3, "merma")
    assert resultado["alertas"]
    assert resultado["alertas"][0]["recien_cruzado"] is True


def test_alertas_actuales_lista_todo_lo_que_esta_bajo(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 0.1)
    stock.fijar_stock(conn, taller["argolla"], 10)
    stock.fijar_stock(conn, taller["cinta"], 500)
    nombres = {a["nombre"] for a in stock.alertas_actuales(conn)}
    assert nombres == {"Cairel de vidrio 10 mm", "Cadena dorada eslabón fino", "Argolla 8 mm"}
    # la cadena entra porque sigue en 0, por debajo de su umbral de 0,2 kg


def test_los_insumos_inactivos_no_alertan(conn, taller):
    stock.fijar_stock(conn, taller["cairel"], 0.1)
    conn.execute("UPDATE insumo SET activo = 0 WHERE id != ?", (taller["cairel"],))
    nombres = {a["nombre"] for a in stock.alertas_actuales(conn)}
    assert nombres == {"Cairel de vidrio 10 mm"}


# ════════════════════════════════════════════════════════════════════════════
# STOCK NEGATIVO
# ════════════════════════════════════════════════════════════════════════════

def test_vender_sin_stock_cargado_deja_negativo_y_avisa(conn, taller):
    """Rechazar la venta sería perder el dato real de que se vendió."""
    resultado = stock.procesar_venta(conn, "manual", "m-1",
                                     [{"articulo_id": taller["borla"], "cantidad": 1}])
    assert resultado["estado"] == "procesada"
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == -6
    assert any("negativo" in a for a in resultado["avisos"])
    assert any(a["stock_negativo"] for a in resultado["alertas"])
    assert_libro_mayor_cierra(conn)


# ════════════════════════════════════════════════════════════════════════════
# MOVIMIENTOS MANUALES
# ════════════════════════════════════════════════════════════════════════════

def test_el_signo_lo_pone_el_tipo(conn, taller):
    """Una merma cargada en positivo no puede sumar stock."""
    stock.fijar_stock(conn, taller["argolla"], 100)
    stock.registrar_movimiento_manual(conn, taller["argolla"], 10, "merma")
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 90

    stock.registrar_movimiento_manual(conn, taller["argolla"], 25, "ingreso")
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 115


def test_el_ajuste_respeta_el_signo_porque_es_un_delta(conn, taller):
    stock.fijar_stock(conn, taller["argolla"], 100)
    stock.registrar_movimiento_manual(conn, taller["argolla"], -7, "ajuste")
    assert stock.insumo_por_id(conn, taller["argolla"])["stock_unidades"] == 93


def test_una_venta_no_entra_por_el_camino_manual(conn, taller):
    """Las ventas van por `procesar_venta`, que es el único camino idempotente."""
    with pytest.raises(ValueError, match="manual inválido"):
        stock.registrar_movimiento_manual(conn, taller["argolla"], 1, "venta")


def test_un_movimiento_de_cantidad_cero_no_se_acepta(conn, taller):
    with pytest.raises(ValueError, match="no puede ser cero"):
        stock.registrar_movimiento_manual(conn, taller["argolla"], 0, "ingreso")


def test_fijar_stock_asienta_la_diferencia_no_el_absoluto(conn, taller):
    stock.fijar_stock(conn, taller["argolla"], 100)
    resultado = stock.fijar_stock(conn, taller["argolla"], 85)

    assert resultado["tipo"] == "ajuste"
    assert resultado["delta_unidades"] == -15
    mov = conn.execute(
        "SELECT * FROM movimiento_stock WHERE insumo_id = ? ORDER BY id DESC LIMIT 1",
        (taller["argolla"],),
    ).fetchone()
    assert mov["cantidad_unidades"] == -15
    assert_libro_mayor_cierra(conn)


def test_fijar_el_mismo_stock_no_genera_movimiento(conn, taller):
    stock.fijar_stock(conn, taller["argolla"], 100)
    resultado = stock.fijar_stock(conn, taller["argolla"], 100)
    assert resultado["sin_cambios"] is True
    assert resultado["movimiento_id"] is None
    assert conn.execute(
        "SELECT COUNT(*) FROM movimiento_stock WHERE insumo_id = ?", (taller["argolla"],)
    ).fetchone()[0] == 1


def test_un_insumo_inexistente_es_error(conn):
    with pytest.raises(ValueError, match="No existe el insumo"):
        stock.registrar_movimiento_manual(conn, 999, 1, "ingreso")
    with pytest.raises(ValueError, match="No existe el insumo"):
        stock.fijar_stock(conn, 999, 1)


# ════════════════════════════════════════════════════════════════════════════
# LOTES Y VALIDACIONES
# ════════════════════════════════════════════════════════════════════════════

def test_el_lote_procesa_cada_venta_por_separado(conn, taller):
    """Lo que va a usar la sincronización de ML: una ventana con repetidas."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.procesar_venta(conn, "ml", "2000001", [{"id_externo_item": "MLA100000001", "cantidad": 1}])

    resultado = stock.procesar_lote(conn, [
        {"canal": "ml", "id_externo": "2000001",
         "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}]},   # repetida
        {"canal": "ml", "id_externo": "2000002",
         "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}]},   # nueva
        {"canal": "ml", "id_externo": "2000003",
         "items": [{"id_externo_item": "MLA404", "cantidad": 1}]},         # sin mapeo
        {"canal": "ml", "id_externo": "", "items": []},                    # inválida
    ])

    assert resultado["total"] == 4
    assert resultado["resumen"]["ya_procesada"] == 1
    assert resultado["resumen"]["procesada"] == 1
    assert resultado["resumen"]["pendiente_mapeo"] == 1
    assert resultado["resumen"]["error"] == 1
    assert_libro_mayor_cierra(conn)


def test_un_canal_invalido_es_error(conn, taller):
    with pytest.raises(ValueError, match="Canal inválido"):
        stock.procesar_venta(conn, "shopify", "1",
                             [{"articulo_id": taller["borla"], "cantidad": 1}])


def test_una_venta_sin_items_es_error(conn):
    with pytest.raises(ValueError, match="no tiene ítems"):
        stock.procesar_venta(conn, "ml", "1", [])


def test_una_cantidad_no_positiva_es_error(conn, taller):
    with pytest.raises(ValueError, match="mayor que cero"):
        stock.procesar_venta(conn, "ml", "1", [{"articulo_id": taller["borla"], "cantidad": 0}])


def test_un_item_sin_forma_de_resolver_el_articulo_es_error(conn):
    with pytest.raises(ValueError, match="articulo_id"):
        stock.procesar_venta(conn, "ml", "1", [{"cantidad": 1}])


# ════════════════════════════════════════════════════════════════════════════
# PESO DE ENVÍO DESDE LA BASE
# ════════════════════════════════════════════════════════════════════════════

def test_el_peso_de_envio_sale_de_la_receta(conn, taller):
    envio = stock.envio_de_articulo(conn, taller["borla"])
    # 6×2,5 + 2×0,4 + 1×12 = 27,8 g, × 1,05
    assert envio["peso_envio_g"] == pytest.approx(29.19)
    assert envio["receta_incompleta"] is False


def test_el_articulo_sin_receta_declara_que_no_puede_cotizar(conn, taller):
    articulo = crear_articulo(conn, "Servilletero de madera")
    envio = stock.envio_de_articulo(conn, articulo)
    assert envio["peso_envio_g"] == 0
    assert envio["receta_incompleta"] is True


def test_cambiar_un_peso_unitario_cambia_el_peso_de_envio(conn, taller):
    """Es la razón de derivar el peso: se corrige el insumo, no 403 productos."""
    antes = stock.envio_de_articulo(conn, taller["borla"])["peso_envio_g"]
    conn.execute("UPDATE insumo SET peso_unitario_g = 3.0 WHERE id = ?", (taller["cairel"],))
    despues = stock.envio_de_articulo(conn, taller["borla"])["peso_envio_g"]
    assert despues > antes
    assert despues == pytest.approx((6 * 3.0 + 2 * 0.4 + 12.0) * 1.05)


# ════════════════════════════════════════════════════════════════════════════
# VARIAS PUBLICACIONES PARA EL MISMO ARTÍCULO
#
# Caso real: el socio tiene el mismo producto publicado más de una vez en la
# misma cuenta de Mercado Libre, y las dos publicaciones tienen ventas.
#
# Funciona porque `articulo_id` quedó FUERA del UNIQUE de `mapeo_canal`, que
# es una decisión correcta pero implícita: meterlo ahí en un refactor rompería
# este caso sin que nada se queje. Estos tests la fijan.
# ════════════════════════════════════════════════════════════════════════════

def test_varias_publicaciones_pueden_apuntar_al_mismo_articulo(conn, taller):
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000001")
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000002")

    assert stock.resolver_articulo_id(conn, "ml", "MLA200000001") == taller["borla"]
    assert stock.resolver_articulo_id(conn, "ml", "MLA200000002") == taller["borla"]


def test_una_publicacion_no_puede_apuntar_a_dos_articulos(conn, taller):
    """La asimetría es a propósito: N publicaciones → 1 artículo sí,
    1 publicación → N artículos no, porque una venta no sabría cuál descontar."""
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000003")
    with pytest.raises(sqlite3.IntegrityError):
        crear_mapeo(conn, taller["guirnalda"], "ml", "MLA200000003")


def test_las_ventas_de_dos_publicaciones_del_mismo_articulo_descuentan_las_dos(conn, taller):
    """La idempotencia es por ORDEN, no por publicación ni por artículo: dos
    ventas distintas del mismo artículo no se colapsan en una."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)   # 2.000 unidades
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000001")
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000002")

    primera = stock.procesar_venta(conn, "ml", "3000001",
                                   [{"id_externo_item": "MLA200000001", "cantidad": 1}])
    segunda = stock.procesar_venta(conn, "ml", "3000002",
                                   [{"id_externo_item": "MLA200000002", "cantidad": 1}])

    assert primera["estado"] == "procesada" and primera["ya_estaba_procesada"] is False
    assert segunda["estado"] == "procesada" and segunda["ya_estaba_procesada"] is False
    assert primera["articulos"][0]["articulo_id"] == segunda["articulos"][0]["articulo_id"]
    # 2 ventas × 6 caireles, las dos descontadas
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 1988.0
    assert_libro_mayor_cierra(conn)


def test_repetir_la_orden_de_una_de_las_dos_publicaciones_sigue_siendo_idempotente(conn, taller):
    """Varias publicaciones no debilitan la idempotencia."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000001")
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000002")

    stock.procesar_venta(conn, "ml", "3000001",
                         [{"id_externo_item": "MLA200000001", "cantidad": 1}])
    stock.procesar_venta(conn, "ml", "3000002",
                         [{"id_externo_item": "MLA200000002", "cantidad": 1}])
    repetida = stock.procesar_venta(conn, "ml", "3000001",
                                    [{"id_externo_item": "MLA200000001", "cantidad": 1}])

    assert repetida["ya_estaba_procesada"] is True
    assert stock.insumo_por_id(conn, taller["cairel"])["stock_unidades"] == 1988.0


def test_el_libro_mayor_distingue_de_que_publicacion_vino_cada_venta(conn, taller):
    """Con dos publicaciones del mismo artículo, el rastro sigue siendo la
    orden: es lo que permite investigar un número que no cierra."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000001")
    crear_mapeo(conn, taller["borla"], "ml", "MLA200000002")
    stock.procesar_venta(conn, "ml", "3000001",
                         [{"id_externo_item": "MLA200000001", "cantidad": 1}])
    stock.procesar_venta(conn, "ml", "3000002",
                         [{"id_externo_item": "MLA200000002", "cantidad": 1}])

    refs = [f["referencia_externa"] for f in conn.execute(
        """SELECT referencia_externa FROM movimiento_stock
            WHERE insumo_id = ? AND tipo = 'venta' ORDER BY id""",
        (taller["cairel"],)).fetchall()]
    assert refs == ["3000001", "3000002"]


# ── Comodín de variante vs mapeo específico ─────────────────────────────────

def test_el_mapeo_de_una_variante_le_gana_al_comodin(conn, taller):
    """Semántica "el específico pisa al general". Importa ahora que un artículo
    puede tener varias publicaciones: es más fácil cargar las dos filas."""
    crear_mapeo(conn, taller["borla"], "ml", "MLA300000001", "")           # comodín
    crear_mapeo(conn, taller["guirnalda"], "ml", "MLA300000001", "BRONCE")  # específico

    assert stock.resolver_articulo_id(conn, "ml", "MLA300000001", "BRONCE") == taller["guirnalda"]


def test_una_variante_sin_fila_propia_cae_al_comodin(conn, taller):
    crear_mapeo(conn, taller["borla"], "ml", "MLA300000001", "")
    crear_mapeo(conn, taller["guirnalda"], "ml", "MLA300000001", "BRONCE")

    assert stock.resolver_articulo_id(conn, "ml", "MLA300000001", "DORADO") == taller["borla"]
    assert stock.resolver_articulo_id(conn, "ml", "MLA300000001") == taller["borla"]


def test_la_venta_de_la_variante_especifica_descuenta_el_articulo_especifico(conn, taller):
    """La preferencia no es solo de la función de resolución: llega al stock."""
    stock.fijar_stock(conn, taller["cairel"], 5.0)
    stock.fijar_stock(conn, taller["cadena"], 2.0)
    crear_mapeo(conn, taller["borla"], "ml", "MLA300000001", "")
    crear_mapeo(conn, taller["guirnalda"], "ml", "MLA300000001", "BRONCE")

    resultado = stock.procesar_venta(
        conn, "ml", "3000010",
        [{"id_externo_item": "MLA300000001", "variacion_externa": "BRONCE", "cantidad": 1}])

    assert resultado["articulos"][0]["articulo_id"] == taller["guirnalda"]
    # la guirnalda lleva cadena y la borla no: prueba que descontó la correcta
    assert stock.insumo_por_id(conn, taller["cadena"])["stock_unidades"] < 1111.0


def test_sin_comodin_una_venta_sin_variante_no_resuelve(conn, taller):
    """No se adivina la variante: queda pendiente de mapeo y se avisa."""
    crear_mapeo(conn, taller["borla"], "ml", "MLA300000002", "DORADO")

    assert stock.resolver_articulo_id(conn, "ml", "MLA300000002") is None
    resultado = stock.procesar_venta(conn, "ml", "3000020",
                                     [{"id_externo_item": "MLA300000002", "cantidad": 1}])
    assert resultado["estado"] == "pendiente_mapeo"
