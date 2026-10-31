#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cotizador de envios por Correo Argentino (tarifa publica de mostrador).

Lo necesita el segundo proveedor, Asi Fue Deco: no usa la logistica de Droppers
(tarifa plana por zona, `zonas_envio.json`), sino que el socio despacha el
paquete el mismo en una sucursal y paga el precio de lista, como cualquier
persona. Lo que el cliente paga en el checkout tiene que ser ese numero: la
diferencia la pone Damian.

Este modulo NO toca nada del flujo de Droppers y todavia no esta enganchado al
checkout: es una pieza aislada con sus tests.

Reglas de la casa
-----------------
- Ningun precio vive aca: todo sale de `data/envios/tarifario_correo_argentino.json`
  y de `data/envios/cp_provincias_argentina.json`. Las tarifas de Correo cambian
  seguido; se edita el JSON y listo.
- Si un dato no se pudo confirmar contra fuente oficial, el JSON lo deja en
  `null` con una nota `pendiente` y el cotizador levanta `TarifaPendiente`.
  Preferimos un error visible a un numero inventado.
- Si el paquete excede los topes de Correo, levanta `PaqueteFueraDeTope`. Un
  paquete que Correo no acepta no se puede vender con envio.

Uso
---
    from utils.envio_correo_argentino import cotizar

    c = cotizar(cp_destino='5000', peso_kg=0.4,
                largo_cm=60, ancho_cm=25, alto_cm=25,
                cp_origen='1824')
    c.costo            # 26400.0
    c.alcance          # 'nacional'
    c.peso_cobrado     # 'volumetrico'
    print(c.explicacion())
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .config import Config

TARIFARIO_FILE = Config.DATA_DIR / 'envios' / 'tarifario_correo_argentino.json'
CP_PROVINCIAS_FILE = Config.DATA_DIR / 'envios' / 'cp_provincias_argentina.json'

FORMAS = ('rectangular', 'triangular', 'cilindrica')


# --------------------------------------------------------------------------
# Errores: todos distinguibles, ninguno devuelve un numero a medias.
# --------------------------------------------------------------------------

class ErrorCotizacion(Exception):
    """Base de todos los errores del cotizador."""


class DatosInvalidos(ErrorCotizacion):
    """Peso, medidas, servicio o modalidad que no tienen sentido."""


class PaqueteFueraDeTope(ErrorCotizacion):
    """El paquete supera el peso o las medidas maximas del servicio.

    Correo no lo admite en el mostrador: no hay precio que cobrar.
    """


class ZonaNoResuelta(ErrorCotizacion):
    """No se pudo decidir si el envio es regional o nacional.

    Pasa con los 89 codigos postales que la base de Correo comparte entre
    provincias, o con un CP que no figura en esa base.
    """


class TarifaPendiente(ErrorCotizacion):
    """El servicio existe pero su tarifa no esta confirmada en el JSON."""


class ModalidadNoDisponible(ErrorCotizacion):
    """El servicio no ofrece esa modalidad de entrega (domicilio / sucursal)."""


# --------------------------------------------------------------------------
# Carga de datos
# --------------------------------------------------------------------------

_cache: Dict[str, dict] = {}


def cargar_tarifario(forzar: bool = False) -> dict:
    """Devuelve el tarifario completo (dict). Cacheado."""
    if forzar or 'tarifario' not in _cache:
        with open(TARIFARIO_FILE, encoding='utf-8') as f:
            _cache['tarifario'] = json.load(f)
    return _cache['tarifario']


def cargar_cp_provincias(forzar: bool = False) -> dict:
    """Devuelve la tabla CP -> provincia (dict). Cacheado."""
    if forzar or 'cps' not in _cache:
        with open(CP_PROVINCIAS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        data['_indice'] = _indexar_rangos(data['rangos_por_provincia'])
        _cache['cps'] = data
    return _cache['cps']


def _indexar_rangos(rangos_por_provincia: Dict[str, str]) -> List[Tuple[int, int, str]]:
    """'4190-4191,4193' -> [(4190, 4191, 'A'), (4193, 4193, 'A'), ...] ordenado."""
    indice: List[Tuple[int, int, str]] = []
    for letra, texto in rangos_por_provincia.items():
        for tramo in texto.split(','):
            tramo = tramo.strip()
            if not tramo:
                continue
            if '-' in tramo:
                desde, hasta = tramo.split('-', 1)
                indice.append((int(desde), int(hasta), letra))
            else:
                indice.append((int(tramo), int(tramo), letra))
    indice.sort()
    return indice


# --------------------------------------------------------------------------
# Codigo postal -> provincia
# --------------------------------------------------------------------------

_RE_CPA = re.compile(r'^\s*([A-Za-z])\s*(\d{4})\s*([A-Za-z]{3})?\s*$')
_RE_CP = re.compile(r'^\s*(\d{4})\s*$')


def normalizar_cp(cp) -> Tuple[int, Optional[str]]:
    """Acepta '1824', 1824, 'B1824', 'B1824ABC' (con o sin espacios).

    Devuelve (numero_de_4_digitos, letra_de_provincia_o_None). La letra, cuando
    viene, es autoritativa: en el CPA el primer caracter ES la provincia.
    """
    if cp is None:
        raise DatosInvalidos('Falta el codigo postal.')
    texto = str(cp).strip().replace(' ', '')
    m = _RE_CP.match(texto)
    if m:
        return int(m.group(1)), None
    m = _RE_CPA.match(texto)
    if m:
        letra = m.group(1).upper()
        provincias = cargar_cp_provincias()['provincias']
        if letra not in provincias:
            raise DatosInvalidos(
                f"'{cp}' no parece un CPA valido: '{letra}' no es una letra de provincia."
            )
        return int(m.group(2)), letra
    raise DatosInvalidos(
        f"Codigo postal '{cp}' invalido. Se espera 4 digitos ('1824') o un CPA ('B1824' / 'B1824ABC')."
    )


def resolver_provincia(cp) -> str:
    """CP -> letra de provincia. Levanta ZonaNoResuelta si no se puede decidir.

    Si el CP viene como CPA completo, la letra manda y no hace falta la tabla.
    """
    numero, letra = normalizar_cp(cp)
    if letra:
        return letra

    data = cargar_cp_provincias()

    caba = data['caba']
    if caba['cp_desde'] <= numero <= caba['cp_hasta']:
        return caba['letra']

    ambiguos = data['cp_ambiguos'].get(str(numero))
    if ambiguos:
        nombres = ', '.join(data['provincias'][p] for p in ambiguos)
        raise ZonaNoResuelta(
            f"El CP {numero} lo comparten {nombres}. Con 4 digitos no alcanza: "
            f"pedi el CPA completo (la primera letra define la provincia) o la provincia."
        )

    for desde, hasta, prov in data['_indice']:
        if desde <= numero <= hasta:
            return prov
        if desde > numero:
            break

    raise ZonaNoResuelta(
        f"El CP {numero} no figura en la base de localidades de Correo Argentino "
        f"(extraida el {data['fecha_extraccion']}). Verificalo en "
        f"{data['fuente']['url_formulario']}."
    )


def resolver_alcance(cp_origen, cp_destino) -> Tuple[str, str, str]:
    """Devuelve (alcance, provincia_origen, provincia_destino).

    `alcance` es 'regional' o 'nacional', tal como los define Correo: regional
    cuando imposicion y destino caen en la misma provincia. CABA + GBA
    (CP 1000-1893) cuentan como UNA provincia.
    """
    tar = cargar_tarifario()
    amba = tar['alcances']['amba_es_una_provincia']

    num_origen, _ = normalizar_cp(cp_origen)
    num_destino, _ = normalizar_cp(cp_destino)

    origen_amba = amba['cp_desde'] <= num_origen <= amba['cp_hasta']
    destino_amba = amba['cp_desde'] <= num_destino <= amba['cp_hasta']

    # AMBA es su propia "provincia": si uno de los dos extremos esta adentro,
    # el alcance se decide ahi y no hace falta mirar la tabla de provincias.
    if origen_amba or destino_amba:
        alcance = 'regional' if (origen_amba and destino_amba) else 'nacional'
        prov_origen = 'AMBA' if origen_amba else resolver_provincia(cp_origen)
        prov_destino = 'AMBA' if destino_amba else resolver_provincia(cp_destino)
        return alcance, prov_origen, prov_destino

    prov_origen = resolver_provincia(cp_origen)
    prov_destino = resolver_provincia(cp_destino)
    alcance = 'regional' if prov_origen == prov_destino else 'nacional'
    return alcance, prov_origen, prov_destino


# --------------------------------------------------------------------------
# Peso volumetrico
# --------------------------------------------------------------------------

def peso_volumetrico(largo_cm: float, ancho_cm: float, alto_cm: float,
                     forma: str = 'rectangular',
                     tarifario: Optional[dict] = None) -> float:
    """Peso volumetrico en kg, con el divisor y la formula que publica Correo.

    Para 'cilindrica', las tres medidas son (largo, diametro, diametro) en
    cualquier orden: la formula oficial es Diametro x Diametro x Largo / 6000,
    que da lo mismo que multiplicar las tres.
    """
    if forma not in FORMAS:
        raise DatosInvalidos(f"Forma '{forma}' desconocida. Opciones: {', '.join(FORMAS)}.")
    tar = tarifario or cargar_tarifario()
    vol = tar['volumetria']
    producto = float(largo_cm) * float(ancho_cm) * float(alto_cm)
    if forma == 'triangular':
        producto /= 2
    return producto / vol['divisor']


def _escalon(peso_kg: float, escalones: Sequence[float]) -> Optional[float]:
    """Primer escalon que cubre el peso; None si lo supera."""
    for e in escalones:
        if peso_kg <= e:
            return e
    return None


# --------------------------------------------------------------------------
# Resultado
# --------------------------------------------------------------------------

@dataclass
class Cotizacion:
    """Lo que costo y como se llego a ese numero."""
    costo: float
    costo_envio: float
    servicio: str
    servicio_nombre: str
    modalidad: str
    alcance: str
    cp_origen: str
    cp_destino: str
    provincia_origen: str
    provincia_destino: str
    peso_real_kg: float
    peso_volumetrico_kg: float
    peso_facturable_kg: float
    peso_cobrado: str          # 'real' | 'volumetrico'
    escalon_kg: float
    plazo_dias: Optional[List[int]]
    adicionales: Dict[str, float] = field(default_factory=dict)
    fuente: str = ''
    vigencia_nota: str = ''

    def explicacion(self) -> str:
        """Texto de una sola pieza, para pegar en un log o en el panel."""
        lineas = [
            f"{self.servicio_nombre} - entrega a {self.modalidad}",
            f"CP {self.cp_origen} ({self.provincia_origen}) -> CP {self.cp_destino} "
            f"({self.provincia_destino}): alcance {self.alcance}",
            f"Peso real {self.peso_real_kg:g} kg / volumetrico {self.peso_volumetrico_kg:.3f} kg "
            f"-> se cobra el {self.peso_cobrado} ({self.peso_facturable_kg:.3f} kg)",
            f"Escalon: hasta {self.escalon_kg:g} kg -> ${self.costo_envio:,.0f}".replace(',', '.'),
        ]
        for nombre, monto in self.adicionales.items():
            lineas.append(f"Adicional {nombre}: ${monto:,.0f}".replace(',', '.'))
        if self.adicionales:
            lineas.append(f"Total: ${self.costo:,.0f}".replace(',', '.'))
        if self.plazo_dias:
            lineas.append(f"Plazo: {self.plazo_dias[0]} a {self.plazo_dias[1]} dias")
        lineas.append(f"Fuente: {self.fuente}")
        if self.vigencia_nota:
            lineas.append(self.vigencia_nota)
        return '\n'.join(lineas)


# --------------------------------------------------------------------------
# Cotizacion
# --------------------------------------------------------------------------

def servicios_disponibles(tarifario: Optional[dict] = None) -> List[dict]:
    """Resumen de cada servicio: si tiene tarifa confirmada y que modalidades da."""
    tar = tarifario or cargar_tarifario()
    salida = []
    for clave, s in tar['servicios'].items():
        salida.append({
            'clave': clave,
            'nombre': s['nombre'],
            'modalidades': list(s['modalidades']),
            'precios_confirmados': bool(s['precios_confirmados']),
            'requiere_cuenta': bool(s.get('requiere_cuenta')),
            'pendiente': s.get('pendiente'),
        })
    return salida


def cotizar(cp_destino, peso_kg: float,
            largo_cm: float, ancho_cm: float, alto_cm: float,
            modalidad: str = 'domicilio',
            *,
            servicio: str = 'encomienda_clasica',
            cp_origen=None,
            forma: str = 'rectangular',
            valor_declarado: Optional[float] = None,
            aviso_de_recibo: bool = False,
            tarifario: Optional[dict] = None) -> Cotizacion:
    """Cotiza un envio por Correo Argentino a tarifa de mostrador.

    Args:
        cp_destino: CP del destinatario. 4 digitos ('5000') o CPA ('X5000ABC').
        peso_kg: peso real del paquete ya embalado.
        largo_cm, ancho_cm, alto_cm: medidas externas del paquete.
        modalidad: 'domicilio' o 'sucursal'.
        servicio: clave del servicio en el tarifario.
        cp_origen: CP de la sucursal de imposicion. Si no se pasa, se usa
            `origen.cp` del tarifario (hoy pendiente de confirmar).
        forma: 'rectangular' (por defecto), 'triangular' o 'cilindrica'.
        valor_declarado: si se quiere declarar valor, el monto en pesos.
        aviso_de_recibo: suma el adicional de aviso de recibo.

    Returns:
        Cotizacion con el costo y el detalle del calculo.

    Raises:
        DatosInvalidos, ModalidadNoDisponible, TarifaPendiente,
        PaqueteFueraDeTope, ZonaNoResuelta.
    """
    tar = tarifario or cargar_tarifario()

    # --- servicio y modalidad -------------------------------------------------
    servicios = tar['servicios']
    if servicio not in servicios:
        raise DatosInvalidos(
            f"Servicio '{servicio}' desconocido. Opciones: {', '.join(servicios)}."
        )
    s = servicios[servicio]

    modalidad = (modalidad or '').strip().lower()
    if modalidad not in ('domicilio', 'sucursal'):
        raise DatosInvalidos(f"Modalidad '{modalidad}' invalida. Usa 'domicilio' o 'sucursal'.")
    if modalidad not in s['modalidades']:
        raise ModalidadNoDisponible(
            f"{s['nombre']} no entrega a {modalidad} "
            f"(solo {', '.join(s['modalidades'])}). {s.get('modalidades_nota', '')}".strip()
        )

    if not s['precios_confirmados'] or not s.get('precios'):
        raise TarifaPendiente(
            f"{s['nombre']}: {s.get('pendiente') or 'sin tarifa confirmada en el tarifario.'}"
        )

    # --- origen ---------------------------------------------------------------
    origen = tar.get('origen') or {}
    cp_origen = cp_origen if cp_origen not in (None, '') else origen.get('cp')
    if cp_origen in (None, ''):
        raise DatosInvalidos(
            'Falta el CP de origen (la sucursal donde se despacha). '
            + (origen.get('pendiente') or
               'Cargalo en origen.cp del tarifario o pasalo por parametro.')
        )

    # --- medidas y peso -------------------------------------------------------
    medidas = (float(largo_cm), float(ancho_cm), float(alto_cm))
    if any(m <= 0 for m in medidas):
        raise DatosInvalidos('Las tres medidas tienen que ser mayores a cero.')
    try:
        peso_kg = float(peso_kg)
    except (TypeError, ValueError):
        raise DatosInvalidos(f"Peso '{peso_kg}' invalido.") from None
    if peso_kg <= 0:
        raise DatosInvalidos('El peso real tiene que ser mayor a cero.')

    topes = s['medidas_max']
    suma = sum(medidas)
    if suma > topes['suma_lados_cm']:
        raise PaqueteFueraDeTope(
            f"{s['nombre']}: la suma de las medidas es {suma:g} cm y el maximo es "
            f"{topes['suma_lados_cm']} cm. Correo no admite este paquete."
        )
    if max(medidas) > topes['lado_max_cm']:
        raise PaqueteFueraDeTope(
            f"{s['nombre']}: el lado mas largo mide {max(medidas):g} cm y el maximo es "
            f"{topes['lado_max_cm']} cm. Correo no admite este paquete."
        )

    pvol = peso_volumetrico(*medidas, forma=forma, tarifario=tar)
    peso_facturable = max(peso_kg, pvol)
    peso_cobrado = 'volumetrico' if pvol > peso_kg else 'real'

    peso_max = s.get('peso_max_kg')
    if peso_max is None:
        raise TarifaPendiente(
            f"{s['nombre']}: {s.get('peso_max_nota') or 'peso maximo sin confirmar.'}"
        )
    if peso_facturable > peso_max:
        detalle = ('volumetrico' if peso_cobrado == 'volumetrico' else 'real')
        raise PaqueteFueraDeTope(
            f"{s['nombre']}: el peso {detalle} es {peso_facturable:.3f} kg y el maximo es "
            f"{peso_max} kg. Correo no admite este paquete."
        )

    escalones = [float(e) for e in s['escalones_kg']]
    escalon = _escalon(peso_facturable, escalones)
    if escalon is None:
        raise PaqueteFueraDeTope(
            f"{s['nombre']}: {peso_facturable:.3f} kg supera el ultimo escalon "
            f"({escalones[-1]:g} kg)."
        )

    # --- alcance y precio -----------------------------------------------------
    alcance, prov_origen, prov_destino = resolver_alcance(cp_origen, cp_destino)

    tabla = s['precios'].get(alcance)
    if not tabla:
        raise TarifaPendiente(
            f"{s['nombre']}: no hay precios cargados para alcance '{alcance}'."
        )
    clave = _clave_escalon(escalon)
    if clave not in tabla:
        raise TarifaPendiente(
            f"{s['nombre']}: falta el precio del escalon de {escalon:g} kg "
            f"({alcance}) en el tarifario."
        )
    costo_envio = float(tabla[clave])

    # --- adicionales ----------------------------------------------------------
    adicionales: Dict[str, float] = {}
    ad = tar.get('adicionales') or {}
    if servicio in (ad.get('aplican_a') or []):
        if aviso_de_recibo:
            adicionales['aviso de recibo'] = float(ad['aviso_de_recibo']['por_envio'])
        if valor_declarado:
            adicionales['valor declarado'] = _costo_por_tramos(
                float(valor_declarado), ad['valor_declarado']['tramos'],
                'valor declarado')
    elif aviso_de_recibo or valor_declarado:
        raise DatosInvalidos(
            f"Los adicionales no estan confirmados para {s['nombre']}."
        )

    return Cotizacion(
        costo=costo_envio + sum(adicionales.values()),
        costo_envio=costo_envio,
        servicio=servicio,
        servicio_nombre=s['nombre'],
        modalidad=modalidad,
        alcance=alcance,
        cp_origen=str(cp_origen),
        cp_destino=str(cp_destino),
        provincia_origen=prov_origen,
        provincia_destino=prov_destino,
        peso_real_kg=peso_kg,
        peso_volumetrico_kg=pvol,
        peso_facturable_kg=peso_facturable,
        peso_cobrado=peso_cobrado,
        escalon_kg=escalon,
        plazo_dias=s.get('plazo_dias'),
        adicionales=adicionales,
        fuente=s.get('fuente', ''),
        vigencia_nota=s.get('vigencia_nota', ''),
    )


def _clave_escalon(escalon: float) -> str:
    """5.0 -> '5' (las claves del JSON son enteros en texto)."""
    return str(int(escalon)) if float(escalon).is_integer() else str(escalon)


def _costo_por_tramos(monto: float, tramos: Sequence[dict], etiqueta: str) -> float:
    """Resuelve un adicional escalonado (fijo o porcentaje) o explica por que no puede."""
    for t in tramos:
        if t['desde'] <= monto <= t['hasta']:
            if 'fijo' in t:
                return float(t['fijo'])
            return round(monto * float(t['porcentaje']) / 100, 2)
    tope = max(float(t['hasta']) for t in tramos)
    raise DatosInvalidos(
        f"El adicional de {etiqueta} no tiene tarifa publicada para ${monto:,.2f} "
        f"(el ultimo tramo llega a ${tope:,.2f}).".replace(',', '.')
    )
