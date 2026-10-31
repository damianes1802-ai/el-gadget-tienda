# -*- coding: utf-8 -*-
"""Tests del cotizador de Correo Argentino (tarifa de mostrador).

Los numeros esperados salen del tarifario oficial que esta en
`data/envios/tarifario_correo_argentino.json`; cada uno tiene su fuente anotada
en `docs/envio_correo_argentino.md`. Si Correo actualiza precios se edita el
JSON y estos tests fallan a proposito: son el aviso de que hay que revisar los
casos, no una copia paralela del tarifario.

Origen de referencia: CP 1824 (Lomas de Zamora, dentro del AMBA). El origen
real de Asi Fue Deco esta pendiente de confirmar, asi que acá se pasa siempre
explicito.
"""
import pytest

from utils.envio_correo_argentino import (
    Cotizacion,
    DatosInvalidos,
    ModalidadNoDisponible,
    PaqueteFueraDeTope,
    TarifaPendiente,
    ZonaNoResuelta,
    cargar_cp_provincias,
    cargar_tarifario,
    cotizar,
    normalizar_cp,
    peso_volumetrico,
    resolver_alcance,
    resolver_provincia,
    servicios_disponibles,
)

AMBA = '1824'          # Lomas de Zamora
CABA = '1425'          # Palermo
QUILMES = '1878'
MAR_DEL_PLATA = '7600'
CORDOBA_CAPITAL = '5000'
RIO_CUARTO = '5800'
USHUAIA = '9410'


# ---------------------------------------------------------------- codigos postales

def test_normalizar_acepta_cp_de_4_digitos_y_cpa_completo():
    assert normalizar_cp('1824') == (1824, None)
    assert normalizar_cp(1824) == (1824, None)
    assert normalizar_cp('B1824') == (1824, 'B')
    assert normalizar_cp('b1824dxk') == (1824, 'B')
    assert normalizar_cp('X5000 ABC'.replace(' ', '')) == (5000, 'X')


@pytest.mark.parametrize('cp', ['', 'hola', '12', '123456', 'Ñ1824', None])
def test_cp_invalido_es_datos_invalidos(cp):
    with pytest.raises(DatosInvalidos):
        normalizar_cp(cp)


def test_resolver_provincia_en_casos_conocidos():
    assert resolver_provincia(CABA) == 'C'
    assert resolver_provincia(MAR_DEL_PLATA) == 'B'
    assert resolver_provincia(CORDOBA_CAPITAL) == 'X'
    assert resolver_provincia('2000') == 'S'       # Rosario
    assert resolver_provincia('4000') == 'T'       # San Miguel de Tucuman
    assert resolver_provincia(USHUAIA) == 'V'      # Tierra del Fuego


def test_cp_compartido_entre_provincias_no_se_adivina():
    # 4141 lo comparten Salta, Catamarca y Tucuman en la base de Correo.
    with pytest.raises(ZonaNoResuelta) as e:
        resolver_provincia('4141')
    assert 'CPA' in str(e.value)
    # Con el CPA completo la primera letra define la provincia y se resuelve.
    assert resolver_provincia('T4141') == 'T'
    assert resolver_provincia('K4141') == 'K'


def test_cp_inexistente_no_devuelve_una_provincia_cualquiera():
    with pytest.raises(ZonaNoResuelta):
        resolver_provincia('9999')


# ---------------------------------------------------------------- alcance

def test_dentro_del_amba_es_regional():
    alcance, origen, destino = resolver_alcance(AMBA, QUILMES)
    assert alcance == 'regional'
    assert origen == destino == 'AMBA'


def test_amba_incluye_caba_aunque_sean_jurisdicciones_distintas():
    # Correo trata CABA + GBA (CP 1000-1893) como UNA sola provincia.
    assert resolver_alcance(AMBA, CABA)[0] == 'regional'


def test_del_amba_al_interior_de_buenos_aires_es_nacional():
    # Consecuencia de lo anterior: Mar del Plata es provincia de Buenos Aires,
    # pero queda fuera del bloque AMBA, asi que cuenta como otra provincia.
    alcance, origen, destino = resolver_alcance(AMBA, MAR_DEL_PLATA)
    assert alcance == 'nacional'
    assert (origen, destino) == ('AMBA', 'B')


def test_dentro_de_una_misma_provincia_del_interior_es_regional():
    assert resolver_alcance(CORDOBA_CAPITAL, RIO_CUARTO)[0] == 'regional'
    assert resolver_alcance(CORDOBA_CAPITAL, MAR_DEL_PLATA)[0] == 'nacional'


def test_borde_del_amba_1893_vs_1894():
    # El rango oficial corta en 1893. 1894 (Berazategui) queda afuera aunque
    # Berazategui figure en la lista de partidos del GBA: inconsistencia
    # documentada en el tarifario y en docs/.
    assert resolver_alcance(AMBA, '1893')[0] == 'regional'
    assert resolver_alcance(AMBA, '1894')[0] == 'nacional'


# ---------------------------------------------------------------- volumetria

def test_peso_volumetrico_usa_divisor_6000():
    assert peso_volumetrico(30, 40, 20) == pytest.approx(24000 / 6000)


def test_peso_volumetrico_triangular_divide_por_dos():
    assert peso_volumetrico(60, 20, 20, forma='triangular') == pytest.approx(
        peso_volumetrico(60, 20, 20) / 2)


def test_forma_desconocida_es_datos_invalidos():
    with pytest.raises(DatosInvalidos):
        peso_volumetrico(10, 10, 10, forma='piramide')


# ---------------------------------------------------------------- cotizaciones reales

def test_encomienda_clasica_regional_1kg():
    c = cotizar(QUILMES, peso_kg=0.8, largo_cm=15, ancho_cm=10, alto_cm=8,
                cp_origen=AMBA)
    assert isinstance(c, Cotizacion)
    assert c.alcance == 'regional'
    assert c.escalon_kg == 1
    assert c.peso_cobrado == 'real'
    assert c.costo == 19500


def test_encomienda_clasica_nacional_1kg_a_cordoba():
    c = cotizar(CORDOBA_CAPITAL, peso_kg=0.8, largo_cm=30, ancho_cm=20, alto_cm=10,
                cp_origen=AMBA)
    assert c.alcance == 'nacional'
    assert c.provincia_destino == 'X'
    assert c.costo == 26400


def test_encomienda_clasica_nacional_a_ushuaia_5kg():
    c = cotizar(USHUAIA, peso_kg=4.2, largo_cm=40, ancho_cm=30, alto_cm=20,
                cp_origen=AMBA)
    assert c.alcance == 'nacional'
    assert c.escalon_kg == 5
    assert c.costo == 32000


def test_prioritaria_es_mas_cara_que_clasica_en_el_mismo_envio():
    comun = dict(peso_kg=0.8, largo_cm=30, ancho_cm=20, alto_cm=10, cp_origen=AMBA)
    clasica = cotizar(CORDOBA_CAPITAL, servicio='encomienda_clasica', **comun)
    prioritaria = cotizar(CORDOBA_CAPITAL, servicio='encomienda_prioritaria', **comun)
    assert prioritaria.costo == 38900
    assert prioritaria.costo > clasica.costo
    assert prioritaria.plazo_dias == [1, 3]


def test_guirnalda_liviana_y_voluminosa_se_cobra_por_peso_volumetrico():
    # Caso tipico de Asi Fue Deco: una guirnalda pesa 400 g pero ocupa una caja
    # de 60x25x25 -> 37.500 cm3 / 6000 = 6,25 kg volumetricos. Correo cobra el
    # mayor de los dos, asi que paga el escalon de 10 kg y no el de 1 kg.
    c = cotizar(CORDOBA_CAPITAL, peso_kg=0.4, largo_cm=60, ancho_cm=25, alto_cm=25,
                cp_origen=AMBA)
    assert c.peso_real_kg == 0.4
    assert c.peso_volumetrico_kg == pytest.approx(6.25)
    assert c.peso_cobrado == 'volumetrico'
    assert c.peso_facturable_kg == pytest.approx(6.25)
    assert c.escalon_kg == 10
    assert c.costo == 45200
    # Y la diferencia contra cobrar el peso real es justamente la que se pierde
    # si alguien cotiza mal: $26.400 vs $45.200.
    chico = cotizar(CORDOBA_CAPITAL, peso_kg=0.4, largo_cm=15, ancho_cm=10, alto_cm=8,
                    cp_origen=AMBA)
    assert chico.peso_cobrado == 'real'
    assert c.costo - chico.costo == 18800


def test_el_escalon_es_el_primero_que_cubre_el_peso():
    base = dict(largo_cm=20, ancho_cm=15, alto_cm=10, cp_origen=AMBA)
    assert cotizar(QUILMES, peso_kg=1.0, **base).escalon_kg == 1
    assert cotizar(QUILMES, peso_kg=1.01, **base).escalon_kg == 5
    assert cotizar(QUILMES, peso_kg=5.0, **base).escalon_kg == 5
    assert cotizar(QUILMES, peso_kg=5.1, **base).escalon_kg == 10
    assert cotizar(QUILMES, peso_kg=25.0, **base).escalon_kg == 25


# ---------------------------------------------------------------- topes

def test_paquete_mas_pesado_que_el_tope_no_cotiza():
    with pytest.raises(PaqueteFueraDeTope) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=30, largo_cm=40, ancho_cm=30, alto_cm=20,
                cp_origen=AMBA)
    assert '25' in str(e.value)


def test_paquete_voluminoso_que_supera_el_tope_por_peso_volumetrico():
    # 100x80x60 = 480.000 cm3 / 6000 = 80 kg volumetricos. Las medidas entran
    # (suma 240, lado maximo 100) pero el peso aforado no.
    with pytest.raises(PaqueteFueraDeTope) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=2, largo_cm=100, ancho_cm=80, alto_cm=60,
                cp_origen=AMBA)
    assert 'volumetrico' in str(e.value)


def test_suma_de_medidas_mayor_a_250_no_cotiza():
    with pytest.raises(PaqueteFueraDeTope) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=2, largo_cm=120, ancho_cm=80, alto_cm=60,
                cp_origen=AMBA)
    assert '250' in str(e.value)


def test_lado_mayor_a_150_no_cotiza():
    with pytest.raises(PaqueteFueraDeTope) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=2, largo_cm=160, ancho_cm=10, alto_cm=10,
                cp_origen=AMBA)
    assert '150' in str(e.value)


def test_el_lado_de_150_justo_si_entra():
    c = cotizar(CORDOBA_CAPITAL, peso_kg=2, largo_cm=150, ancho_cm=30, alto_cm=20,
                cp_origen=AMBA)
    assert c.peso_volumetrico_kg == pytest.approx(15)
    assert c.escalon_kg == 15
    assert c.costo == 56600


def test_en_la_practica_el_tope_que_manda_es_el_volumetrico():
    """Con divisor 6000, 25 kg aforados son apenas 150.000 cm3.

    Una caja que respeta las medidas maximas (150+50+50 = 250, ningun lado
    sobre 150) da 62,5 kg volumetricos y Correo no la toma. Para la deco
    voluminosa de Asi Fue Deco este es el limite real, no los 25 kg.
    """
    with pytest.raises(PaqueteFueraDeTope) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=2, largo_cm=150, ancho_cm=50, alto_cm=50,
                cp_origen=AMBA)
    assert 'volumetrico' in str(e.value)


@pytest.mark.parametrize('kwargs', [
    dict(peso_kg=0, largo_cm=10, ancho_cm=10, alto_cm=10),
    dict(peso_kg=-1, largo_cm=10, ancho_cm=10, alto_cm=10),
    dict(peso_kg=1, largo_cm=0, ancho_cm=10, alto_cm=10),
    dict(peso_kg='pesado', largo_cm=10, ancho_cm=10, alto_cm=10),
])
def test_entradas_sin_sentido_son_datos_invalidos(kwargs):
    with pytest.raises(DatosInvalidos):
        cotizar(CORDOBA_CAPITAL, cp_origen=AMBA, **kwargs)


# ---------------------------------------------------------------- errores distinguibles

def test_encomienda_no_entrega_en_sucursal():
    with pytest.raises(ModalidadNoDisponible):
        cotizar(CORDOBA_CAPITAL, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                modalidad='sucursal', cp_origen=AMBA)


@pytest.mark.parametrize('servicio', ['paqar_clasico', 'paqar_expreso'])
@pytest.mark.parametrize('modalidad', ['domicilio', 'sucursal'])
def test_paqar_avisa_que_la_tarifa_esta_pendiente(servicio, modalidad):
    # PAQ.AR si tiene entrega a sucursal, pero sus precios no se pudieron
    # confirmar: tiene que fallar fuerte, nunca devolver un numero inventado.
    with pytest.raises(TarifaPendiente) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                servicio=servicio, modalidad=modalidad, cp_origen=AMBA)
    assert 'PENDIENTE' in str(e.value)


def test_servicio_inexistente():
    with pytest.raises(DatosInvalidos):
        cotizar(CORDOBA_CAPITAL, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                servicio='paloma_mensajera', cp_origen=AMBA)


def test_sin_cp_de_origen_avisa_que_falta_confirmarlo():
    # `origen.cp` del tarifario esta en null a proposito: nadie confirmo todavia
    # desde que sucursal despacha Asi Fue Deco.
    assert cargar_tarifario()['origen']['cp'] is None
    with pytest.raises(DatosInvalidos) as e:
        cotizar(CORDOBA_CAPITAL, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10)
    assert 'origen' in str(e.value).lower()


def test_destino_ambiguo_no_cotiza():
    with pytest.raises(ZonaNoResuelta):
        cotizar('4141', peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                cp_origen=AMBA)


# ---------------------------------------------------------------- adicionales

def test_valor_declarado_tramo_fijo_y_porcentual():
    base = dict(peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10, cp_origen=AMBA)
    fijo = cotizar(QUILMES, valor_declarado=15000, **base)
    assert fijo.adicionales['valor declarado'] == 600
    assert fijo.costo == 19500 + 600

    porcentual = cotizar(QUILMES, valor_declarado=50000, **base)
    assert porcentual.adicionales['valor declarado'] == 1500
    assert porcentual.costo == 19500 + 1500


def test_valor_declarado_fuera_de_tabla_no_se_extrapola():
    with pytest.raises(DatosInvalidos):
        cotizar(QUILMES, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                cp_origen=AMBA, valor_declarado=500000)


def test_aviso_de_recibo_suma_el_adicional_publicado():
    c = cotizar(QUILMES, peso_kg=1, largo_cm=20, ancho_cm=15, alto_cm=10,
                cp_origen=AMBA, aviso_de_recibo=True)
    assert c.adicionales['aviso de recibo'] == 9300
    assert c.costo == 19500 + 9300


# ---------------------------------------------------------------- explicacion y metadatos

def test_la_cotizacion_explica_como_llego_al_numero():
    c = cotizar(CORDOBA_CAPITAL, peso_kg=0.4, largo_cm=60, ancho_cm=25, alto_cm=25,
                cp_origen=AMBA)
    texto = c.explicacion()
    for esperado in ('nacional', 'volumetrico', '10 kg', 'correoargentino.com.ar'):
        assert esperado in texto


def test_servicios_disponibles_marca_cuales_tienen_tarifa():
    por_clave = {s['clave']: s for s in servicios_disponibles()}
    assert por_clave['encomienda_clasica']['precios_confirmados'] is True
    assert por_clave['paqar_clasico']['precios_confirmados'] is False
    assert 'sucursal' in por_clave['paqar_expreso']['modalidades']
    assert 'sucursal' not in por_clave['encomienda_clasica']['modalidades']


# ---------------------------------------------------------------- integridad de los datos

def test_el_tarifario_no_tiene_precios_a_medias():
    """O el servicio tiene la tabla completa, o esta marcado como pendiente."""
    tar = cargar_tarifario()
    for clave, s in tar['servicios'].items():
        if not s['precios_confirmados']:
            assert s['precios'] is None, f'{clave}: marcado sin confirmar pero con precios'
            assert s.get('pendiente'), f'{clave}: sin confirmar y sin explicar por que'
            continue
        assert s.get('fuente', '').startswith('http'), f'{clave}: sin fuente'
        escalones = s['escalones_kg']
        assert escalones == sorted(escalones)
        for alcance in ('regional', 'nacional'):
            tabla = s['precios'][alcance]
            assert [int(k) for k in tabla] == escalones, f'{clave}/{alcance}: escalones'
            valores = list(tabla.values())
            assert all(isinstance(v, (int, float)) and v > 0 for v in valores)
            assert valores == sorted(valores), f'{clave}/{alcance}: precios no crecientes'


def test_nacional_nunca_sale_mas_barato_que_regional():
    tar = cargar_tarifario()
    for clave, s in tar['servicios'].items():
        if not s['precios_confirmados']:
            continue
        for escalon in s['escalones_kg']:
            k = str(escalon)
            assert s['precios']['nacional'][k] >= s['precios']['regional'][k], \
                f'{clave}: el escalon {k} kg sale mas barato nacional que regional'


def test_los_rangos_de_cp_no_se_pisan_entre_provincias():
    """Si dos provincias reclamaran el mismo CP, el alcance saldria al azar."""
    data = cargar_cp_provincias()
    indice = sorted(data['_indice'])
    for (d1, h1, p1), (d2, h2, p2) in zip(indice, indice[1:]):
        assert h1 < d2, f'Se pisan {p1} ({d1}-{h1}) y {p2} ({d2}-{h2})'


def test_los_cp_ambiguos_no_estan_tambien_en_los_rangos():
    data = cargar_cp_provincias()
    for cp in data['cp_ambiguos']:
        numero = int(cp)
        for desde, hasta, prov in data['_indice']:
            assert not (desde <= numero <= hasta), \
                f'El CP ambiguo {cp} tambien figura como {prov}'


def test_el_rango_de_caba_no_choca_con_ninguna_provincia():
    data = cargar_cp_provincias()
    caba = data['caba']
    for desde, hasta, prov in data['_indice']:
        assert hasta < caba['cp_desde'] or desde > caba['cp_hasta'], \
            f'El rango de CABA se pisa con {prov} ({desde}-{hasta})'
