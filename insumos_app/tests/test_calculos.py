# -*- coding: utf-8 -*-
"""Cálculos puros: conversiones, peso de envío, medidas, costos y alertas."""

import pytest

from insumos_app import calculos


# ════════════════════════════════════════════════════════════════════════════
# CONVERSIÓN STOCK ↔ PANTALLA
# ════════════════════════════════════════════════════════════════════════════

def test_unidad_de_pantalla():
    assert calculos.unidad_de_pantalla("peso") == "kg"
    assert calculos.unidad_de_pantalla("unidad") == "unidad"


def test_kilos_a_unidades():
    # 2,5 kg de caireles de 2,5 g son 1.000 caireles
    assert calculos.a_unidades(2.5, "peso", 2.5) == 1000.0


def test_unidades_a_kilos():
    assert calculos.desde_unidades(1000.0, "peso", 2.5) == 2.5


def test_modo_unidad_no_convierte():
    assert calculos.a_unidades(7, "unidad", 0.4) == 7
    assert calculos.desde_unidades(7, "unidad", 0.4) == 7


def test_ida_y_vuelta_no_pierde_precision_relevante():
    for kilos in (0.7, 1.3, 2.25, 10.0):
        unidades = calculos.a_unidades(kilos, "peso", 3.3)
        assert calculos.desde_unidades(unidades, "peso", 3.3) == pytest.approx(kilos)


def test_peso_unitario_cero_es_error_no_division_por_cero():
    """Es el motivo del CHECK `peso_unitario_g > 0` en el esquema."""
    with pytest.raises(ValueError):
        calculos.a_unidades(1.0, "peso", 0)
    with pytest.raises(ValueError):
        calculos.desde_unidades(1.0, "peso", 0)


def test_stock_para_pantalla_muestra_las_dos_unidades():
    insumo = {"modo_stock": "peso", "peso_unitario_g": 2.5, "stock_unidades": 1000.0}
    salida = calculos.stock_para_pantalla(insumo)
    assert salida["unidades"] == 1000.0
    assert salida["cantidad_pantalla"] == 2.5
    assert salida["unidad_pantalla"] == "kg"
    assert salida["kg"] == 2.5


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS
# ════════════════════════════════════════════════════════════════════════════

def _insumo_peso(stock_unidades, alerta_kg):
    return {
        "id": 1,
        "nombre": "Cairel de vidrio 10 mm",
        "modo_stock": "peso",
        "peso_unitario_g": 2.5,
        "stock_unidades": stock_unidades,
        "alerta_cuando_queden": alerta_kg,
    }


def test_umbral_en_kilos_se_convierte_a_unidades():
    # avisar cuando queden 0,5 kg = 200 caireles de 2,5 g
    assert calculos.umbral_en_unidades(_insumo_peso(0, 0.5)) == 200.0


def test_alerta_por_debajo_del_umbral():
    assert calculos.en_alerta(_insumo_peso(199.0, 0.5))


def test_alerta_justo_en_el_umbral():
    """El umbral es "avisar cuando queden N", así que N dispara."""
    assert calculos.en_alerta(_insumo_peso(200.0, 0.5))


def test_sin_alerta_por_encima_del_umbral():
    assert not calculos.en_alerta(_insumo_peso(201.0, 0.5))


def test_umbral_cero_no_alerta():
    assert not calculos.en_alerta(_insumo_peso(0.0, 0))


def test_stock_negativo_alerta_aunque_no_haya_umbral():
    """Negativo significa que se vendió material que no estaba cargado."""
    insumo = _insumo_peso(-3.0, 0)
    assert calculos.en_alerta(insumo)
    assert calculos.describir_alerta(insumo)["stock_negativo"] is True


def test_describir_alerta_habla_en_la_unidad_del_socio():
    alerta = calculos.describir_alerta(_insumo_peso(120.0, 0.5))
    assert alerta["unidad"] == "kg"
    assert alerta["stock_pantalla"] == 0.3   # 120 × 2,5 g
    assert alerta["umbral_pantalla"] == 0.5


# ════════════════════════════════════════════════════════════════════════════
# PESO Y MEDIDAS DE ENVÍO
# ════════════════════════════════════════════════════════════════════════════

RECETA_BORLA = [
    {"insumo_id": 1, "cantidad": 6, "peso_unitario_g": 2.5},   # caireles
    {"insumo_id": 2, "cantidad": 2, "peso_unitario_g": 0.4},   # argollas
    {"insumo_id": 3, "cantidad": 1, "peso_unitario_g": 12.0},  # cinta
]

ARTICULO_BORLA = {
    "largo_real_mm": 180.0, "ancho_real_mm": 60.0, "alto_real_mm": 50.0,
    "se_embala_doblado": 0, "margen_embalaje": 1.05,
}

ARTICULO_GUIRNALDA = {
    "largo_real_mm": 2000.0, "ancho_real_mm": 60.0, "alto_real_mm": 20.0,
    "se_embala_doblado": 1,
    "largo_emb_mm": 250.0, "ancho_emb_mm": 250.0, "alto_emb_mm": 60.0,
    "margen_embalaje": 1.05,
}


def test_peso_de_los_insumos_es_la_suma_de_la_receta():
    # 6×2,5 + 2×0,4 + 1×12 = 27,8 g
    assert calculos.peso_insumos_g(RECETA_BORLA) == pytest.approx(27.8)


def test_peso_de_envio_aplica_el_margen():
    envio = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA)
    assert envio["peso_insumos_g"] == pytest.approx(27.8)
    assert envio["peso_envio_g"] == pytest.approx(27.8 * 1.05)
    assert envio["peso_envio_kg"] == pytest.approx(27.8 * 1.05 / 1000)


def test_medidas_de_envio_aplican_el_margen_a_las_tres():
    envio = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA)
    assert envio["largo_envio_mm"] == pytest.approx(189.0)
    assert envio["ancho_envio_mm"] == pytest.approx(63.0)
    assert envio["alto_envio_mm"] == pytest.approx(52.5)
    # Correo Argentino cotiza en centímetros
    assert envio["largo_envio_cm"] == pytest.approx(18.9)


def test_guirnalda_se_cotiza_doblada_no_estirada():
    """Conserva sus 2 metros como dato real, pero el envío usa el cuadrado."""
    envio = calculos.calcular_envio(ARTICULO_GUIRNALDA, [])
    assert envio["se_embala_doblado"] is True
    assert envio["largo_envio_mm"] == pytest.approx(262.5)   # 250 × 1,05
    assert envio["largo_envio_mm"] < ARTICULO_GUIRNALDA["largo_real_mm"]


def test_medidas_base_elige_segun_se_embala_doblado():
    assert calculos.medidas_base_mm(ARTICULO_BORLA) == (180.0, 60.0, 50.0)
    assert calculos.medidas_base_mm(ARTICULO_GUIRNALDA) == (250.0, 250.0, 60.0)


def test_el_margen_por_dimension_infla_el_volumen_15_coma_8_por_ciento():
    """La consecuencia que la especificación pide tener a la vista.

    1,05 en las tres dimensiones no es 5% más de volumen: es 15,8%, y Correo
    Argentino cobra por peso volumétrico cuando el paquete es liviano y
    voluminoso. Si alguna vez se quiere 5% de volumen, el factor es 1,016.
    """
    sin_margen = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA, margen=1.0)
    con_margen = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA, margen=1.05)
    assert con_margen["volumen_cm3"] / sin_margen["volumen_cm3"] == pytest.approx(1.158, abs=0.001)

    cinco_por_ciento = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA, margen=1.016)
    assert cinco_por_ciento["volumen_cm3"] / sin_margen["volumen_cm3"] == pytest.approx(1.05, abs=0.002)


def test_margen_explicito_pisa_el_del_articulo():
    envio = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA, margen=1.0)
    assert envio["margen_embalaje"] == 1.0
    assert envio["peso_envio_g"] == pytest.approx(27.8)


def test_sin_receta_el_peso_no_sirve_y_se_avisa():
    """Un peso de 0 que parece un peso es peor que un error."""
    envio = calculos.calcular_envio(ARTICULO_BORLA, [])
    assert envio["peso_envio_g"] == 0
    assert envio["receta_incompleta"] is True
    assert envio["insumos_en_receta"] == 0


def test_con_receta_no_marca_incompleta():
    envio = calculos.calcular_envio(ARTICULO_BORLA, RECETA_BORLA)
    assert envio["receta_incompleta"] is False
    assert envio["insumos_en_receta"] == 3


# ════════════════════════════════════════════════════════════════════════════
# COSTOS DERIVADOS
# ════════════════════════════════════════════════════════════════════════════

def test_costo_comprado_por_kilo_se_baja_a_la_unidad():
    insumo = {"costo_compra": 18000, "unidad_compra": "kg", "peso_unitario_g": 2.5}
    costos = calculos.costos_derivados(insumo)
    assert costos["costo_por_kg"] == 18000
    assert costos["costo_por_100g"] == 1800
    assert costos["costo_por_unidad"] == pytest.approx(45.0)  # 18000 × 2,5/1000


def test_costo_comprado_por_unidad_se_sube_al_kilo():
    insumo = {"costo_compra": 35, "unidad_compra": "unidad", "peso_unitario_g": 0.4}
    costos = calculos.costos_derivados(insumo)
    assert costos["costo_por_unidad"] == 35
    assert costos["costo_por_kg"] == pytest.approx(87500.0)  # 35 × 1000/0,4


def test_sin_costo_cargado_devuelve_none_no_cero():
    assert calculos.costos_derivados(
        {"costo_compra": None, "unidad_compra": "kg", "peso_unitario_g": 2.5}
    ) is None
    assert calculos.costos_derivados(
        {"costo_compra": 100, "unidad_compra": None, "peso_unitario_g": 2.5}
    ) is None


# ════════════════════════════════════════════════════════════════════════════
# CONSUMO
# ════════════════════════════════════════════════════════════════════════════

def test_el_consumo_es_negativo_porque_entra_al_libro_mayor():
    """El signo va en la cantidad, no implícito en el tipo de movimiento:
    la suma de la columna del libro mayor tiene que dar el stock."""
    consumo = calculos.consumo_de_receta(RECETA_BORLA, 1)
    assert [c["cantidad_unidades"] for c in consumo] == [-6, -2, -1]


def test_el_consumo_se_expresa_en_unidades_no_en_gramos():
    """Vender una borla consume 6 caireles, no 15 gramos de caireles."""
    consumo = calculos.consumo_de_receta(RECETA_BORLA, 1)
    assert consumo[0]["cantidad_unidades"] == -6


def test_el_consumo_escala_con_la_cantidad_vendida():
    consumo = calculos.consumo_de_receta(RECETA_BORLA, 3)
    por_insumo = {c["insumo_id"]: c["cantidad_unidades"] for c in consumo}
    assert por_insumo[1] == -18   # 6 caireles × 3 borlas
    assert por_insumo[2] == -6    # 2 argollas × 3
    assert por_insumo[3] == -3    # 1 cinta × 3
