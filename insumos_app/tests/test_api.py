# -*- coding: utf-8 -*-
"""
Endpoints de la API. Datos de ejemplo inventados.

Cubre el camino que va a recorrer la interfaz web: cargar taxonomía, insumos,
artículos y recetas; contar inventario; procesar una venta; y leer el peso de
envío, que es el dato por el que existe el sistema.
"""

import pytest


# ════════════════════════════════════════════════════════════════════════════
# AYUDANTES
# ════════════════════════════════════════════════════════════════════════════

def nuevo_insumo(cliente, nombre="Cairel de vidrio 10 mm", **extra):
    cuerpo = {
        "nombre": nombre,
        "modo_stock": "peso",
        "peso_unitario_g": 2.5,
        "alerta_cuando_queden": 0.5,
        "costo_compra": 18000,
        "unidad_compra": "kg",
    }
    cuerpo.update(extra)
    r = cliente.post("/api/insumos", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


def nuevo_articulo(cliente, nombre="Sujeta cortina borla trenzada", **extra):
    cuerpo = {
        "nombre": nombre,
        "largo_real_mm": 180,
        "ancho_real_mm": 60,
        "alto_real_mm": 50,
        "sku_elgadget": "AFD-20",
    }
    cuerpo.update(extra)
    r = cliente.post("/api/articulos", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


# ════════════════════════════════════════════════════════════════════════════
# SALUD Y AUTENTICACIÓN
# ════════════════════════════════════════════════════════════════════════════

def test_salud_responde(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_raiz_describe_el_sistema(cliente):
    assert "Así Fue Deco" in cliente.get("/").json()["sistema"]


def test_con_password_configurada_pide_el_header(cliente, monkeypatch):
    from insumos_app import api as api_mod

    monkeypatch.setattr(api_mod, "INSUMOS_PASSWORD", "secreto-de-prueba")
    assert cliente.get("/api/insumos").status_code == 401
    assert cliente.get("/api/insumos", headers={"X-Insumos-Password": "otro"}).status_code == 401
    r = cliente.get("/api/insumos", headers={"X-Insumos-Password": "secreto-de-prueba"})
    assert r.status_code == 200


def test_la_salud_no_pide_credencial(cliente, monkeypatch):
    """Para que un monitoreo externo pueda chequear sin el secreto."""
    from insumos_app import api as api_mod

    monkeypatch.setattr(api_mod, "INSUMOS_PASSWORD", "secreto-de-prueba")
    assert cliente.get("/salud").status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# CATEGORÍAS Y SUBCATEGORÍAS
# ════════════════════════════════════════════════════════════════════════════

def test_crud_de_categorias(cliente):
    cat = cliente.post("/api/categorias", json={"nombre": "Caireles", "orden": 1}).json()
    assert cat["nombre"] == "Caireles"

    sub = cliente.post(
        "/api/subcategorias", json={"categoria_id": cat["id"], "nombre": "De vidrio"}
    ).json()
    assert sub["categoria_id"] == cat["id"]

    listado = cliente.get("/api/categorias").json()
    assert listado[0]["subcategorias"][0]["nombre"] == "De vidrio"

    r = cliente.put(f"/api/categorias/{cat['id']}", json={"nombre": "Caireles y cuentas"})
    assert r.json()["nombre"] == "Caireles y cuentas"

    assert cliente.delete(f"/api/subcategorias/{sub['id']}").status_code == 200
    assert cliente.delete(f"/api/categorias/{cat['id']}").status_code == 200
    assert cliente.get("/api/categorias").json() == []


def test_no_se_borra_una_categoria_con_insumos(cliente):
    """Borrarla en cascada dejaría insumos sin clasificar sin que nadie lo pida."""
    cat = cliente.post("/api/categorias", json={"nombre": "Caireles"}).json()
    nuevo_insumo(cliente, categoria_id=cat["id"])

    r = cliente.delete(f"/api/categorias/{cat['id']}")
    assert r.status_code == 409
    assert "insumo" in r.json()["detail"]


def test_una_categoria_repetida_es_conflicto(cliente):
    cliente.post("/api/categorias", json={"nombre": "Caireles"})
    assert cliente.post("/api/categorias", json={"nombre": "Caireles"}).status_code == 409


def test_la_subcategoria_tiene_que_pertenecer_a_la_categoria(cliente):
    a = cliente.post("/api/categorias", json={"nombre": "Caireles"}).json()
    b = cliente.post("/api/categorias", json={"nombre": "Cintas"}).json()
    sub = cliente.post(
        "/api/subcategorias", json={"categoria_id": a["id"], "nombre": "De vidrio"}
    ).json()

    r = cliente.post("/api/insumos", json={
        "nombre": "Cairel", "modo_stock": "peso", "peso_unitario_g": 2.5,
        "categoria_id": b["id"], "subcategoria_id": sub["id"],
    })
    assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════
# INSUMOS
# ════════════════════════════════════════════════════════════════════════════

def test_el_insumo_muestra_stock_en_las_dos_unidades_y_costos(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=2.5)
    assert insumo["stock"]["unidades"] == 1000.0
    assert insumo["stock"]["cantidad_pantalla"] == 2.5
    assert insumo["unidad_pantalla"] == "kg"
    assert insumo["costos"]["costo_por_unidad"] == pytest.approx(45.0)


def test_el_stock_inicial_entra_como_movimiento_y_fija_el_corte(cliente):
    """El libro mayor tiene que explicar también el primer número."""
    insumo = nuevo_insumo(cliente, stock_inicial=2.5)

    movimientos = cliente.get(f"/api/insumos/{insumo['id']}/movimientos").json()
    assert movimientos["total"] == 1
    assert movimientos["movimientos"][0]["tipo"] == "inventario_inicial"
    assert movimientos["movimientos"][0]["cantidad_unidades"] == 1000.0

    assert cliente.get("/api/config").json()["fecha_corte"] is not None


def test_el_peso_unitario_es_obligatorio_aunque_el_modo_sea_peso(cliente):
    r = cliente.post("/api/insumos", json={
        "nombre": "Cairel", "modo_stock": "peso", "peso_unitario_g": 0,
    })
    assert r.status_code == 400
    assert "peso_unitario_g" in r.json()["detail"]


def test_un_modo_de_stock_invalido_se_rechaza(cliente):
    r = cliente.post("/api/insumos", json={
        "nombre": "Cairel", "modo_stock": "docena", "peso_unitario_g": 2.5,
    })
    assert r.status_code == 400


def test_editar_un_insumo_no_cambia_su_stock(cliente):
    """El stock solo se mueve por el libro mayor: no hay campo para pisarlo."""
    insumo = nuevo_insumo(cliente, stock_inicial=2.5)
    r = cliente.put(f"/api/insumos/{insumo['id']}",
                    json={"nombre": "Cairel de vidrio 12 mm", "stock_unidades": 999999})
    assert r.status_code == 200
    assert r.json()["nombre"] == "Cairel de vidrio 12 mm"
    assert r.json()["stock"]["unidades"] == 1000.0


def test_contar_inventario_asienta_la_diferencia(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=2.5)
    r = cliente.post(f"/api/insumos/{insumo['id']}/stock", json={"cantidad": 2.0})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["tipo"] == "ajuste"
    assert cuerpo["delta_unidades"] == -200.0   # 2,0 kg − 2,5 kg = −200 unidades
    assert cuerpo["stock"]["cantidad_pantalla"] == 2.0


def test_el_movimiento_manual_entra_por_su_endpoint(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=2.5)
    r = cliente.post("/api/movimientos", json={
        "insumo_id": insumo["id"], "cantidad": 0.5, "tipo": "ingreso", "nota": "Compra",
    })
    assert r.status_code == 201
    assert r.json()["stock"]["cantidad_pantalla"] == 3.0


def test_una_venta_no_entra_por_el_endpoint_de_movimientos(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=1.0)
    r = cliente.post("/api/movimientos", json={
        "insumo_id": insumo["id"], "cantidad": 1, "tipo": "venta",
    })
    assert r.status_code == 400


def test_el_listado_filtra_por_alerta(cliente):
    nuevo_insumo(cliente, nombre="Cairel con stock", stock_inicial=5.0)
    nuevo_insumo(cliente, nombre="Cairel sin stock", stock_inicial=0.1)

    todos = cliente.get("/api/insumos").json()
    en_alerta = cliente.get("/api/insumos", params={"solo_alerta": True}).json()
    assert len(todos) == 2
    assert [i["nombre"] for i in en_alerta] == ["Cairel sin stock"]


def test_el_insumo_dice_en_que_articulos_se_usa(cliente):
    insumo = nuevo_insumo(cliente)
    articulo = nuevo_articulo(cliente)
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": insumo["id"], "cantidad": 6}]})

    detalle = cliente.get(f"/api/insumos/{insumo['id']}").json()
    assert detalle["usado_en"][0]["nombre"] == "Sujeta cortina borla trenzada"
    assert detalle["usado_en"][0]["cantidad"] == 6


def test_un_insumo_con_historia_se_desactiva_en_vez_de_borrarse(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=1.0)
    r = cliente.delete(f"/api/insumos/{insumo['id']}")
    assert r.json()["borrado"] is False
    assert r.json()["desactivado"] == insumo["id"]
    assert cliente.get(f"/api/insumos/{insumo['id']}").json()["activo"] is False


def test_un_insumo_sin_historia_se_borra(cliente):
    insumo = nuevo_insumo(cliente)
    assert cliente.delete(f"/api/insumos/{insumo['id']}").json()["borrado"] == insumo["id"]
    assert cliente.get(f"/api/insumos/{insumo['id']}").status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# ARTÍCULOS, RECETAS Y ENVÍO
# ════════════════════════════════════════════════════════════════════════════

def test_el_articulo_nace_con_el_margen_por_defecto(cliente):
    assert nuevo_articulo(cliente)["margen_embalaje"] == 1.05


def test_el_margen_por_defecto_es_configurable(cliente):
    """Para pasar a 1,016 (5% de volumen) sin tocar código."""
    cliente.put("/api/config/margen_embalaje_default", json={"valor": "1.016"})
    assert nuevo_articulo(cliente)["margen_embalaje"] == 1.016


def test_el_articulo_doblado_necesita_las_tres_medidas_embaladas(cliente):
    r = cliente.post("/api/articulos", json={
        "nombre": "Guirnalda de caireles 2 m",
        "largo_real_mm": 2000, "ancho_real_mm": 60, "alto_real_mm": 20,
        "se_embala_doblado": True, "largo_emb_mm": 250,
    })
    assert r.status_code == 400
    assert "embaladas" in r.json()["detail"]


def test_el_peso_de_envio_sale_de_la_receta(cliente):
    cairel = nuevo_insumo(cliente, nombre="Cairel de vidrio 10 mm")
    cinta = nuevo_insumo(cliente, nombre="Cinta de yute", modo_stock="unidad",
                         peso_unitario_g=12.0, unidad_compra="unidad", costo_compra=900)
    articulo = nuevo_articulo(cliente)

    cliente.put(f"/api/articulos/{articulo['id']}/receta", json={"items": [
        {"insumo_id": cairel["id"], "cantidad": 6},
        {"insumo_id": cinta["id"], "cantidad": 1},
    ]})

    envio = cliente.get(f"/api/articulos/{articulo['id']}/envio").json()
    assert envio["peso_insumos_g"] == pytest.approx(27.0)   # 6×2,5 + 12
    assert envio["peso_envio_g"] == pytest.approx(28.35)    # × 1,05
    assert envio["largo_envio_mm"] == pytest.approx(189.0)
    assert envio["receta_incompleta"] is False


def test_el_envio_se_puede_simular_con_otro_margen(cliente):
    cairel = nuevo_insumo(cliente)
    articulo = nuevo_articulo(cliente)
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": cairel["id"], "cantidad": 6}]})

    con_105 = cliente.get(f"/api/articulos/{articulo['id']}/envio").json()
    con_1016 = cliente.get(f"/api/articulos/{articulo['id']}/envio",
                           params={"margen": 1.016}).json()
    assert con_1016["volumen_cm3"] < con_105["volumen_cm3"]
    # El artículo no cambió: la simulación no guarda nada.
    assert cliente.get(f"/api/articulos/{articulo['id']}").json()["margen_embalaje"] == 1.05


def test_la_guirnalda_se_cotiza_doblada(cliente):
    articulo = cliente.post("/api/articulos", json={
        "nombre": "Guirnalda de caireles 2 m",
        "largo_real_mm": 2000, "ancho_real_mm": 60, "alto_real_mm": 20,
        "se_embala_doblado": True,
        "largo_emb_mm": 250, "ancho_emb_mm": 250, "alto_emb_mm": 60,
    }).json()

    envio = cliente.get(f"/api/articulos/{articulo['id']}/envio").json()
    assert envio["medidas_reales_mm"]["largo"] == 2000      # el dato real se conserva
    assert envio["largo_envio_mm"] == pytest.approx(262.5)  # pero se cotiza doblada


def test_el_envio_se_consulta_por_sku(cliente):
    """La puerta para el cotizador del checkout, que solo conoce el SKU."""
    cairel = nuevo_insumo(cliente)
    articulo = nuevo_articulo(cliente, sku_elgadget="AFD-20")
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": cairel["id"], "cantidad": 6}]})

    envio = cliente.get("/api/envio", params={"sku_elgadget": "AFD-20"}).json()
    assert envio["articulo_id"] == articulo["id"]
    assert envio["peso_envio_g"] == pytest.approx(15.75)


def test_el_envio_por_sku_inexistente_es_404(cliente):
    assert cliente.get("/api/envio", params={"sku_elgadget": "NO-EXISTE"}).status_code == 404


def test_el_envio_sin_criterio_es_400(cliente):
    assert cliente.get("/api/envio").status_code == 400


def test_un_sku_repetido_es_conflicto(cliente):
    """Dos artículos con el mismo SKU harían ambigua la cotización."""
    nuevo_articulo(cliente, sku_elgadget="AFD-20")
    r = cliente.post("/api/articulos", json={
        "nombre": "Otro", "largo_real_mm": 10, "ancho_real_mm": 10,
        "alto_real_mm": 10, "sku_elgadget": "AFD-20",
    })
    assert r.status_code == 409


def test_el_articulo_sin_receta_avisa_que_no_puede_cotizar(cliente):
    articulo = nuevo_articulo(cliente)
    envio = cliente.get(f"/api/articulos/{articulo['id']}/envio").json()
    assert envio["receta_incompleta"] is True
    assert envio["peso_envio_g"] == 0

    sin_receta = cliente.get("/api/articulos", params={"sin_receta": True}).json()
    assert [a["id"] for a in sin_receta] == [articulo["id"]]


def test_la_receta_se_edita_por_linea_y_completa(cliente):
    a = nuevo_insumo(cliente, nombre="Cairel")
    b = nuevo_insumo(cliente, nombre="Argolla", modo_stock="unidad", peso_unitario_g=0.4)
    articulo = nuevo_articulo(cliente)

    cliente.post(f"/api/articulos/{articulo['id']}/receta",
                 json={"insumo_id": a["id"], "cantidad": 6})
    r = cliente.post(f"/api/articulos/{articulo['id']}/receta",
                     json={"insumo_id": b["id"], "cantidad": 2})
    assert len(r.json()["items"]) == 2

    # Repetir la misma línea actualiza la cantidad, no duplica
    r = cliente.post(f"/api/articulos/{articulo['id']}/receta",
                     json={"insumo_id": a["id"], "cantidad": 8})
    items = {i["insumo_id"]: i["cantidad"] for i in r.json()["items"]}
    assert items[a["id"]] == 8

    r = cliente.delete(f"/api/articulos/{articulo['id']}/receta/{b['id']}")
    assert len(r.json()["items"]) == 1

    # El PUT reemplaza la receta completa
    r = cliente.put(f"/api/articulos/{articulo['id']}/receta",
                    json={"items": [{"insumo_id": b["id"], "cantidad": 4}]})
    assert [i["insumo_id"] for i in r.json()["items"]] == [b["id"]]


def test_una_receta_con_el_mismo_insumo_dos_veces_se_rechaza(cliente):
    insumo = nuevo_insumo(cliente)
    articulo = nuevo_articulo(cliente)
    r = cliente.put(f"/api/articulos/{articulo['id']}/receta", json={"items": [
        {"insumo_id": insumo["id"], "cantidad": 6},
        {"insumo_id": insumo["id"], "cantidad": 2},
    ]})
    assert r.status_code == 400


def test_una_receta_con_cantidad_cero_se_rechaza(cliente):
    insumo = nuevo_insumo(cliente)
    articulo = nuevo_articulo(cliente)
    r = cliente.put(f"/api/articulos/{articulo['id']}/receta",
                    json={"items": [{"insumo_id": insumo["id"], "cantidad": 0}]})
    assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════
# MAPEO DE CANAL
# ════════════════════════════════════════════════════════════════════════════

def test_crud_de_mapeos(cliente):
    articulo = nuevo_articulo(cliente)
    r = cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA100000001",
    })
    assert r.status_code == 201
    mapeo = r.json()

    assert cliente.get("/api/mapeos", params={"canal": "ml"}).json()[0]["articulo"] == articulo["nombre"]
    assert cliente.delete(f"/api/mapeos/{mapeo['id']}").status_code == 200


def test_el_canal_manual_no_se_mapea(cliente):
    """Una venta manual elige el artículo en pantalla, no tiene id externo."""
    articulo = nuevo_articulo(cliente)
    r = cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "manual", "id_externo": "x",
    })
    assert r.status_code == 400


def test_un_mapeo_repetido_es_conflicto(cliente):
    articulo = nuevo_articulo(cliente)
    cuerpo = {"articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA1"}
    cliente.post("/api/mapeos", json=cuerpo)
    assert cliente.post("/api/mapeos", json=cuerpo).status_code == 409


# ════════════════════════════════════════════════════════════════════════════
# VENTAS
# ════════════════════════════════════════════════════════════════════════════

def _taller_por_api(cliente):
    """Monta por API el taller mínimo: un insumo, un artículo, receta y mapeo."""
    insumo = nuevo_insumo(cliente, stock_inicial=5.0)       # 2.000 unidades
    articulo = nuevo_articulo(cliente)
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": insumo["id"], "cantidad": 6}]})
    cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA100000001",
    })
    return insumo, articulo


def test_procesar_una_venta_descuenta_y_devuelve_los_movimientos(cliente):
    insumo, articulo = _taller_por_api(cliente)

    r = cliente.post("/api/ventas", json={
        "canal": "ml", "id_externo": "2000001", "fecha_venta": "2026-10-26",
        "items": [{"id_externo_item": "MLA100000001", "cantidad": 2}],
    })
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "procesada"
    assert cuerpo["movimientos"][0]["cantidad_unidades"] == -12
    assert cliente.get(f"/api/insumos/{insumo['id']}").json()["stock"]["unidades"] == 1988.0


def test_la_venta_repetida_no_descuenta_de_nuevo(cliente):
    insumo, _ = _taller_por_api(cliente)
    venta = {"canal": "ml", "id_externo": "2000001",
             "items": [{"id_externo_item": "MLA100000001", "cantidad": 2}]}

    cliente.post("/api/ventas", json=venta)
    segunda = cliente.post("/api/ventas", json=venta).json()

    assert segunda["ya_estaba_procesada"] is True
    assert cliente.get(f"/api/insumos/{insumo['id']}").json()["stock"]["unidades"] == 1988.0


def test_el_lote_informa_el_resumen(cliente):
    _taller_por_api(cliente)
    r = cliente.post("/api/ventas/lote", json={"ventas": [
        {"canal": "ml", "id_externo": "2000001",
         "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}]},
        {"canal": "ml", "id_externo": "2000001",
         "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}]},
        {"canal": "ml", "id_externo": "2000002",
         "items": [{"id_externo_item": "MLA404", "cantidad": 1}]},
    ]})
    resumen = r.json()["resumen"]
    assert resumen["procesada"] == 1
    assert resumen["ya_procesada"] == 1
    assert resumen["pendiente_mapeo"] == 1


def test_la_venta_pendiente_se_lista_y_se_reprocesa(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=5.0)
    articulo = nuevo_articulo(cliente)

    r = cliente.post("/api/ventas", json={
        "canal": "manual", "id_externo": "manual-001",
        "items": [{"articulo_id": articulo["id"], "cantidad": 2}],
    })
    assert r.json()["estado"] == "pendiente_receta"

    pendientes = cliente.get("/api/ventas/pendientes").json()
    assert len(pendientes) == 1
    assert pendientes[0]["id_externo"] == "manual-001"
    assert cliente.get("/salud").json()["ventas_pendientes"] == 1

    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": insumo["id"], "cantidad": 6}]})
    r = cliente.post("/api/ventas/manual/manual-001/reprocesar")
    assert r.json()["estado"] == "procesada"
    assert cliente.get(f"/api/insumos/{insumo['id']}").json()["stock"]["unidades"] == 1988.0
    assert cliente.get("/api/ventas/pendientes").json() == []


def test_reprocesar_todas_las_pendientes(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=5.0)
    articulo = nuevo_articulo(cliente)
    cliente.post("/api/ventas", json={
        "canal": "manual", "id_externo": "m-1",
        "items": [{"articulo_id": articulo["id"], "cantidad": 1}],
    })
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": insumo["id"], "cantidad": 6}]})

    r = cliente.post("/api/ventas/pendientes/reprocesar")
    assert r.json()["resumen"]["procesada"] == 1


def test_la_venta_muestra_sus_movimientos(cliente):
    _taller_por_api(cliente)
    cliente.post("/api/ventas", json={
        "canal": "ml", "id_externo": "2000001",
        "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}],
    })
    detalle = cliente.get("/api/ventas/ml/2000001").json()
    assert detalle["estado"] == "procesada"
    assert len(detalle["movimientos"]) == 1
    assert detalle["movimientos"][0]["referencia_externa"] == "2000001"


def test_el_listado_de_ventas_filtra(cliente):
    _taller_por_api(cliente)
    cliente.post("/api/ventas", json={
        "canal": "ml", "id_externo": "2000001", "fecha_venta": "2026-10-26",
        "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}],
    })
    assert cliente.get("/api/ventas", params={"canal": "ml"}).json()["total"] == 1
    assert cliente.get("/api/ventas", params={"canal": "elgadget"}).json()["total"] == 0
    assert cliente.get("/api/ventas", params={"estado": "procesada"}).json()["total"] == 1


def test_una_venta_de_canal_invalido_es_400(cliente):
    r = cliente.post("/api/ventas", json={
        "canal": "shopify", "id_externo": "1", "items": [{"articulo_id": 1, "cantidad": 1}],
    })
    assert r.status_code == 400


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS, MOVIMIENTOS, CONFIG Y AUDITORÍA
# ════════════════════════════════════════════════════════════════════════════

def test_las_alertas_se_listan_en_la_unidad_del_socio(cliente):
    nuevo_insumo(cliente, nombre="Cairel escaso", stock_inicial=0.3)
    nuevo_insumo(cliente, nombre="Cairel sobrado", stock_inicial=5.0)

    r = cliente.get("/api/alertas").json()
    assert r["total"] == 1
    assert r["alertas"][0]["nombre"] == "Cairel escaso"
    assert r["alertas"][0]["unidad"] == "kg"
    assert r["alertas"][0]["stock_pantalla"] == 0.3


def test_el_libro_mayor_de_un_insumo_trae_el_saldo(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=1.0)   # 400 unidades
    cliente.post("/api/movimientos", json={
        "insumo_id": insumo["id"], "cantidad": 0.25, "tipo": "ingreso",
    })
    cliente.post("/api/movimientos", json={
        "insumo_id": insumo["id"], "cantidad": 0.1, "tipo": "merma",
    })

    r = cliente.get(f"/api/insumos/{insumo['id']}/movimientos").json()
    assert r["total"] == 3
    # Vienen del más nuevo al más viejo y el saldo del primero es el stock actual
    assert r["movimientos"][0]["saldo_unidades"] == r["stock"]["unidades"]
    assert r["movimientos"][0]["saldo_pantalla"] == pytest.approx(1.15)


def test_el_libro_mayor_general_se_filtra(cliente):
    insumo, articulo = _taller_por_api(cliente)
    cliente.post("/api/ventas", json={
        "canal": "ml", "id_externo": "2000001",
        "items": [{"id_externo_item": "MLA100000001", "cantidad": 1}],
    })

    todos = cliente.get("/api/movimientos").json()
    ventas = cliente.get("/api/movimientos", params={"tipo": "venta"}).json()
    assert todos["total"] == 2          # inventario inicial + venta
    assert ventas["total"] == 1
    assert ventas["movimientos"][0]["articulo"] == articulo["nombre"]
    assert ventas["movimientos"][0]["unidad_pantalla"] == "kg"


def test_la_auditoria_de_stock_cuadra(cliente):
    insumo, _ = _taller_por_api(cliente)
    cliente.post("/api/ventas", json={
        "canal": "ml", "id_externo": "2000001",
        "items": [{"id_externo_item": "MLA100000001", "cantidad": 3}],
    })
    cliente.post("/api/movimientos", json={
        "insumo_id": insumo["id"], "cantidad": 0.5, "tipo": "ingreso",
    })
    cliente.post(f"/api/insumos/{insumo['id']}/stock", json={"cantidad": 4.0})

    auditoria = cliente.get("/api/auditoria/stock").json()
    assert auditoria["cuadra"] is True
    assert auditoria["descuadres"] == []
    assert auditoria["insumos"][0]["stock_unidades"] == auditoria["insumos"][0]["suma_movimientos"]


def test_la_auditoria_detecta_un_stock_escrito_por_fuera(cliente, monkeypatch):
    """El endpoint tiene que servir para algo: se simula el bug que busca."""
    from insumos_app import db

    insumo = nuevo_insumo(cliente, stock_inicial=1.0)
    conn = db.conectar()
    conn.execute("UPDATE insumo SET stock_unidades = 123 WHERE id = ?", (insumo["id"],))
    conn.close()

    auditoria = cliente.get("/api/auditoria/stock").json()
    assert auditoria["cuadra"] is False
    assert auditoria["descuadres"][0]["insumo_id"] == insumo["id"]


def test_la_fecha_de_corte_se_puede_corregir(cliente):
    r = cliente.put("/api/config/fecha_corte", json={"valor": "2026-10-20"})
    assert r.json()["valor"] == "2026-10-20"
    assert cliente.get("/api/config").json()["fecha_corte"] == "2026-10-20"


def test_una_fecha_de_corte_invalida_se_rechaza(cliente):
    assert cliente.put("/api/config/fecha_corte", json={"valor": "el martes"}).status_code == 400


def test_no_se_puede_tocar_la_version_del_esquema(cliente):
    """Pisarla haría que una migración futura no corra."""
    assert cliente.put("/api/config/schema_version", json={"valor": "99"}).status_code == 400


def test_un_margen_por_defecto_menor_a_uno_se_rechaza(cliente):
    r = cliente.put("/api/config/margen_embalaje_default", json={"valor": "0.9"})
    assert r.status_code == 400


def test_cambiar_el_modo_de_stock_avisa_por_el_umbral(cliente):
    """El stock se conserva (se guarda en unidades) pero el umbral cambia de
    unidad: reinterpretarlo en silencio dejaría una alerta mintiendo."""
    insumo = nuevo_insumo(cliente, stock_inicial=1.0)   # 400 unidades, umbral 0,5 kg
    r = cliente.put(f"/api/insumos/{insumo['id']}", json={"modo_stock": "unidad"})

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["stock"]["unidades"] == 400.0          # el stock no se movió
    assert cuerpo["stock"]["cantidad_pantalla"] == 400.0  # ahora se muestra en unidades
    assert cuerpo["avisos"]
    assert "umbral" in cuerpo["avisos"][0]


def test_sin_umbral_cargado_no_avisa_al_cambiar_el_modo(cliente):
    insumo = nuevo_insumo(cliente, alerta_cuando_queden=0)
    r = cliente.put(f"/api/insumos/{insumo['id']}", json={"modo_stock": "unidad"})
    assert "avisos" not in r.json()


# ════════════════════════════════════════════════════════════════════════════
# VARIAS PUBLICACIONES PARA EL MISMO ARTÍCULO (caso real del socio)
# ════════════════════════════════════════════════════════════════════════════

def test_la_api_acepta_varias_publicaciones_para_el_mismo_articulo(cliente):
    articulo = nuevo_articulo(cliente)
    for publicacion in ("MLA200000001", "MLA200000002"):
        r = cliente.post("/api/mapeos", json={
            "articulo_id": articulo["id"], "canal": "ml", "id_externo": publicacion,
        })
        assert r.status_code == 201, r.text

    mapeos = cliente.get("/api/mapeos", params={"articulo_id": articulo["id"]}).json()
    assert {m["id_externo"] for m in mapeos} == {"MLA200000001", "MLA200000002"}
    # y el detalle del artículo las muestra las dos
    assert len(cliente.get(f"/api/articulos/{articulo['id']}").json()["mapeos"]) == 2


def test_la_api_rechaza_una_publicacion_hacia_dos_articulos(cliente):
    uno = nuevo_articulo(cliente, nombre="Borla", sku_elgadget="AFD-20")
    otro = nuevo_articulo(cliente, nombre="Guirnalda", sku_elgadget="AFD-21")
    cliente.post("/api/mapeos", json={
        "articulo_id": uno["id"], "canal": "ml", "id_externo": "MLA1"})
    r = cliente.post("/api/mapeos", json={
        "articulo_id": otro["id"], "canal": "ml", "id_externo": "MLA1"})
    assert r.status_code == 409


def test_las_dos_publicaciones_descuentan_por_separado(cliente):
    insumo = nuevo_insumo(cliente, stock_inicial=5.0)       # 2.000 unidades
    articulo = nuevo_articulo(cliente)
    cliente.put(f"/api/articulos/{articulo['id']}/receta",
                json={"items": [{"insumo_id": insumo["id"], "cantidad": 6}]})
    for publicacion in ("MLA200000001", "MLA200000002"):
        cliente.post("/api/mapeos", json={
            "articulo_id": articulo["id"], "canal": "ml", "id_externo": publicacion})

    for orden, publicacion in (("3000001", "MLA200000001"), ("3000002", "MLA200000002")):
        r = cliente.post("/api/ventas", json={
            "canal": "ml", "id_externo": orden,
            "items": [{"id_externo_item": publicacion, "cantidad": 1}]})
        assert r.json()["estado"] == "procesada"
        assert r.json()["ya_estaba_procesada"] is False

    assert cliente.get(f"/api/insumos/{insumo['id']}").json()["stock"]["unidades"] == 1988.0
    assert cliente.get("/api/auditoria/stock").json()["cuadra"] is True


def test_cargar_una_variante_sobre_un_comodin_avisa_quien_gana(cliente):
    uno = nuevo_articulo(cliente, nombre="Borla", sku_elgadget="AFD-20")
    otro = nuevo_articulo(cliente, nombre="Guirnalda", sku_elgadget="AFD-21")
    cliente.post("/api/mapeos", json={
        "articulo_id": uno["id"], "canal": "ml", "id_externo": "MLA9"})

    r = cliente.post("/api/mapeos", json={
        "articulo_id": otro["id"], "canal": "ml", "id_externo": "MLA9",
        "variacion_externa": "BRONCE"})

    assert r.status_code == 201
    aviso = r.json()["avisos"][0]
    assert "Borla" in aviso and "BRONCE" in aviso


def test_cargar_un_comodin_sobre_variantes_existentes_avisa(cliente):
    uno = nuevo_articulo(cliente, nombre="Borla", sku_elgadget="AFD-20")
    otro = nuevo_articulo(cliente, nombre="Guirnalda", sku_elgadget="AFD-21")
    cliente.post("/api/mapeos", json={
        "articulo_id": otro["id"], "canal": "ml", "id_externo": "MLA9",
        "variacion_externa": "BRONCE"})

    r = cliente.post("/api/mapeos", json={
        "articulo_id": uno["id"], "canal": "ml", "id_externo": "MLA9"})

    assert r.status_code == 201
    aviso = r.json()["avisos"][0]
    assert "BRONCE" in aviso and "Guirnalda" in aviso


def test_sin_conflicto_no_hay_aviso(cliente):
    """Varias publicaciones del mismo artículo es el caso normal, no una rareza."""
    articulo = nuevo_articulo(cliente)
    cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA1"})
    r = cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA2"})
    assert "avisos" not in r.json()

    # tampoco cuando el comodín y la variante van al MISMO artículo
    r = cliente.post("/api/mapeos", json={
        "articulo_id": articulo["id"], "canal": "ml", "id_externo": "MLA1",
        "variacion_externa": "BRONCE"})
    assert "avisos" not in r.json()
