# -*- coding: utf-8 -*-
"""Lógica pura de campañas y descuentos (sin base de datos)."""
from utils.campanas import fecha_campana_vigente, calcular_precio_oferta
from api_local import _descuento_referido_escalonado, _validar_descuento_row


# ── Vigencia de campañas (incluye recurrentes anuales) ──────────────────────

NAVIDAD = {'recurrente_anual': 1, 'fecha_inicio': '2026-12-01', 'fecha_fin': '2026-12-24'}
REYES = {'recurrente_anual': 1, 'fecha_inicio': '2026-12-26', 'fecha_fin': '2027-01-06'}
UNA_VEZ = {'recurrente_anual': 0, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-08-16'}


def test_recurrente_aplica_cualquier_anio():
    assert fecha_campana_vigente(NAVIDAD, '2026-12-10')
    assert fecha_campana_vigente(NAVIDAD, '2028-12-20')   # otro año
    assert fecha_campana_vigente(NAVIDAD, '2030-12-01')   # borde inicio
    assert fecha_campana_vigente(NAVIDAD, '2030-12-24')   # borde fin


def test_recurrente_fuera_de_ventana():
    assert not fecha_campana_vigente(NAVIDAD, '2027-01-05')
    assert not fecha_campana_vigente(NAVIDAD, '2029-12-25')


def test_recurrente_cruza_fin_de_anio():
    assert fecha_campana_vigente(REYES, '2028-12-30')
    assert fecha_campana_vigente(REYES, '2029-01-03')
    assert fecha_campana_vigente(REYES, '2030-01-06')      # borde
    assert not fecha_campana_vigente(REYES, '2030-01-07')
    assert not fecha_campana_vigente(REYES, '2028-03-01')


def test_no_recurrente_una_sola_vez():
    assert fecha_campana_vigente(UNA_VEZ, '2026-08-10')
    assert not fecha_campana_vigente(UNA_VEZ, '2027-08-10')  # otro año NO
    assert not fecha_campana_vigente(UNA_VEZ, '2026-09-01')  # vencida


def test_sin_fechas_siempre_vigente():
    assert fecha_campana_vigente({'recurrente_anual': 0, 'fecha_inicio': None, 'fecha_fin': None}, '2026-07-08')


# ── Precio de oferta ─────────────────────────────────────────────────────────

def test_precio_oferta_porcentaje_todos():
    prod = {'sku': 'X', 'categoria': 'Deco', 'precio_venta': 26000}
    campanas = [{'alcance': 'todos', 'tipo': 'porcentaje', 'valor': 20}]
    assert calcular_precio_oferta(prod, campanas) == 20800


def test_precio_oferta_no_aplica_otra_categoria():
    prod = {'sku': 'X', 'categoria': 'Deco', 'precio_venta': 26000}
    campanas = [{'alcance': 'categoria', 'categoria': 'Tecnología', 'tipo': 'porcentaje', 'valor': 20}]
    assert calcular_precio_oferta(prod, campanas) is None


def test_precio_oferta_gana_la_mejor():
    prod = {'sku': 'X', 'categoria': 'Deco', 'precio_venta': 26000}
    campanas = [
        {'alcance': 'todos', 'tipo': 'porcentaje', 'valor': 10},
        {'alcance': 'skus', 'skus': '["X"]', 'tipo': 'porcentaje', 'valor': 25},
    ]
    assert calcular_precio_oferta(prod, campanas) == 19500


# ── Descuento escalonado del comprador (umbrales 2026) ──────────────────────

def test_escalonado_umbral_2026():
    assert _descuento_referido_escalonado(15000) == 10.0
    assert _descuento_referido_escalonado(24999) == 10.0
    assert _descuento_referido_escalonado(25000) == 15.0
    assert _descuento_referido_escalonado(60000) == 15.0
    assert _descuento_referido_escalonado(60001) == 20.0


# ── Validación de códigos: flag "permanente" (auto-saneo del frontend) ──────

BASE_CODIGO = {'id': 1, 'activo': 1, 'tipo': 'porcentaje', 'valor': 10, 'alcance': 'todos',
               'codigo': 'TEST', 'email_asociado': None, 'uso_maximo': None,
               'usos_actuales': 0, 'nombre': 'Test'}


def test_codigo_inexistente_es_permanente():
    r = _validar_descuento_row(None, 'x@x.com', 1000)
    assert not r['valido'] and r['permanente'] is True


def test_codigo_agotado_es_permanente():
    r = _validar_descuento_row({**BASE_CODIGO, 'uso_maximo': 1, 'usos_actuales': 1}, 'x@x.com', 1000)
    assert not r['valido'] and r['permanente'] is True


def test_falta_minimo_no_es_permanente():
    r = _validar_descuento_row({**BASE_CODIGO, 'monto_minimo': 100000}, 'x@x.com', 1000)
    assert not r['valido'] and r['permanente'] is False


def test_email_ajeno_no_es_permanente():
    r = _validar_descuento_row({**BASE_CODIGO, 'email_asociado': 'otra@x.com'}, 'x@x.com', 1000)
    assert not r['valido'] and r['permanente'] is False


def test_recurrente_fuera_de_fecha_no_es_permanente():
    d = {**BASE_CODIGO, 'recurrente_anual': 1, 'fecha_inicio': '2020-12-01', 'fecha_fin': '2020-12-24'}
    r = _validar_descuento_row(d, 'x@x.com', 1000)  # hoy no es diciembre... salvo que lo sea
    from datetime import datetime
    if 12 != datetime.now().month or not (1 <= datetime.now().day <= 24):
        assert not r['valido'] and r['permanente'] is False
