# -*- coding: utf-8 -*-
"""Integración: crear_orden con la regla 'código vs oferta' y el descuento de
stock. Usa data/catalogo.db LOCAL con datos de prueba que se limpian al final.
Los emails, MP y AFIP están apagados por conftest.py."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

import api_local

CLIENTE = {'nombre': 'Test', 'apellido': 'Pytest', 'email': 'pytest@of.com',
           'telefono': '1112223334', 'direccion': 'Calle 1', 'ciudad': 'CABA',
           'codigo_postal': '1000', 'provincia': 'CABA', 'cuit_dni': ''}


@pytest.fixture()
def entorno():
    """Producto de lista $26.000 + campaña 20% + bienvenida 50% y 10%."""
    conn = sqlite3.connect('data/catalogo.db')
    conn.row_factory = sqlite3.Row
    conn.execute("""INSERT OR REPLACE INTO productos (sku, nombre, descripcion, precio_costo,
        precio_venta, stock, categoria, marca, imagen_principal, imagenes_adicionales,
        link_producto, url_amigable) VALUES ('PYTESTSKU','Prod Pytest','d',10000,26000,50,
        'TestCat','','','','','')""")
    conn.execute("""INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo, activo,
        recurrente_anual, fecha_inicio, fecha_fin) VALUES
        ('Pytest Temporada','porcentaje',20,'todos',NULL,1,1,'2020-01-01','2020-12-31')""")
    conn.execute("""INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo,
        email_asociado, activo, uso_maximo) VALUES
        ('Pytest B50','porcentaje',50,'todos','PYT-B50','pytest@of.com',1,1)""")
    conn.execute("""INSERT INTO descuentos (nombre, tipo, valor, alcance, codigo,
        email_asociado, activo, uso_maximo) VALUES
        ('Pytest B10','porcentaje',10,'todos','PYT-B10','pytest@of.com',1,1)""")
    conn.commit()
    api_local._cache_invalidar()

    yield conn

    cur = conn.cursor()
    cur.execute("""DELETE FROM orden_items WHERE orden_id IN
        (SELECT o.id FROM ordenes o JOIN clientes c ON o.cliente_id=c.id WHERE c.email='pytest@of.com')""")
    cur.execute("""DELETE FROM comisiones_referidos WHERE orden_id NOT IN (SELECT id FROM ordenes)""")
    cur.execute("""DELETE FROM ordenes WHERE cliente_id IN (SELECT id FROM clientes WHERE email='pytest@of.com')""")
    cur.execute("DELETE FROM clientes WHERE email='pytest@of.com'")
    cur.execute("DELETE FROM descuentos WHERE nombre LIKE 'Pytest %'")
    cur.execute("DELETE FROM resenas WHERE producto_sku='PYTESTSKU'")
    cur.execute("DELETE FROM productos WHERE sku='PYTESTSKU'")
    conn.commit()
    conn.close()
    api_local._cache_invalidar()


def _crear(conn, codigo=None):
    c = TestClient(api_local.app)
    r = c.post('/api/orden', json={'cliente': CLIENTE,
                                   'items': [{'sku': 'PYTESTSKU', 'cantidad': 1}],
                                   'codigo_descuento': codigo})
    assert r.status_code == 200, r.text
    oid = r.json()['orden_id']
    fila = conn.execute(
        "SELECT total, costo_envio, descuento_codigo FROM ordenes WHERE id=?", (oid,)
    ).fetchone()
    return oid, dict(fila)


def test_sin_codigo_cobra_oferta(entorno):
    _, o = _crear(entorno)
    assert abs((o['total'] - o['costo_envio']) - 20800) < 0.01  # 26.000 − 20%


def test_codigo_grande_gana_sobre_oferta(entorno):
    _, o = _crear(entorno, codigo='PYT-B50')
    assert abs((o['total'] - o['costo_envio']) - 13000) < 0.01  # 26.000 × 50%
    assert o['descuento_codigo'] == 'PYT-B50'


def test_oferta_gana_y_no_consume_codigo_chico(entorno):
    _, o = _crear(entorno, codigo='PYT-B10')
    assert abs((o['total'] - o['costo_envio']) - 20800) < 0.01  # oferta 20% > código 10%
    assert o['descuento_codigo'] is None
    usos = entorno.execute("SELECT usos_actuales FROM descuentos WHERE codigo='PYT-B10'").fetchone()[0]
    assert usos == 0  # el código sigue disponible


def test_recurrente_sin_fechas_rechazada(entorno):
    c = TestClient(api_local.app)
    r = c.post('/api/admin/descuentos',
               json={'nombre': 'Pytest Mal', 'valor': 10, 'recurrente_anual': True},
               headers={'X-Admin-Password': api_local.ADMIN_PASSWORD})
    assert r.status_code == 400


def test_resena_flujo_completo(entorno):
    """Comprador real deja reseña → pendiente (no pública) → aprobada → pública."""
    oid, _ = _crear(entorno)
    c = TestClient(api_local.app)

    # Solo un comprador real puede reseñar
    r = c.post('/api/resena', json={'producto_sku': 'PYTESTSKU', 'orden_id': oid,
                                    'email': 'otro@mail.com', 'rating': 5})
    assert r.status_code == 403

    # Rating fuera de rango
    r = c.post('/api/resena', json={'producto_sku': 'PYTESTSKU', 'orden_id': oid,
                                    'email': 'pytest@of.com', 'rating': 6})
    assert r.status_code == 400

    # Reseña válida → queda pendiente y NO aparece en el listado público
    r = c.post('/api/resena', json={'producto_sku': 'PYTESTSKU', 'orden_id': oid,
                                    'email': 'pytest@of.com', 'rating': 4,
                                    'comentario': 'Muy bueno'})
    assert r.status_code == 200, r.text
    assert c.get('/api/producto/PYTESTSKU/resenas').json()['total'] == 0

    # Duplicada para la misma orden → 409
    r = c.post('/api/resena', json={'producto_sku': 'PYTESTSKU', 'orden_id': oid,
                                    'email': 'pytest@of.com', 'rating': 5})
    assert r.status_code == 409

    # El admin aprueba con nombre público → aparece en el listado
    rid = entorno.execute("SELECT id FROM resenas WHERE producto_sku='PYTESTSKU'").fetchone()[0]
    r = c.patch(f'/api/admin/resena/{rid}', params={'estado': 'aprobada', 'nombre': 'Tester P.'},
                headers={'X-Admin-Password': api_local.ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    pub = c.get('/api/producto/PYTESTSKU/resenas').json()
    assert pub['total'] == 1 and pub['promedio'] == 4.0
    assert pub['resenas'][0]['nombre'] == 'Tester P.'
    assert pub['resenas'][0]['comentario'] == 'Muy bueno'
