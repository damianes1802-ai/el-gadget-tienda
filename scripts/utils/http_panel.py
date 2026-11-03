# -*- coding: utf-8 -*-
"""Cliente HTTP de los paneles de escritorio (admin y marketing).

Por qué existe
--------------
Render free duerme el servicio a los 15 minutos sin tráfico y tarda ~50s en
despertar; durante ese arranque —y durante cada deploy— el edge devuelve 502 o
corta la conexión en pleno handshake TLS, lo que llega como
`SSLError: SSLV3_ALERT_BAD_RECORD_MAC`. No es un error del panel ni del
servidor: es el servicio levantándose.

Hasta el 2026-09-27 los dos paneles llamaban con `requests.get(..., timeout=15)`
sin un solo reintento, así que cualquier pantalla abierta en ese momento
quedaba mostrando un traceback crudo de urllib3 hasta que el usuario recargaba
a mano.

No se comparte una `Session` entre llamadas a propósito: pywebview invoca estos
métodos desde varios hilos y una Session de requests no es thread-safe —
corrompe registros TLS, con el mismo síntoma que se quería arreglar.

El otro caso que llegaba ilegible es el SERVICIO SUSPENDIDO (2026-11-03): cuando
Render suspende el workspace —típicamente por un cobro rechazado— el edge
devuelve 503 con una página HTML "This service has been suspended", y a partir de
unas pocas peticiones seguidas pasa a contestar 429 a todo lo que venga de
esa IP. Como el 503 estaba en HTTP_REINTENTABLES, cada llamada del panel se
multiplicaba por 4 y lo que terminaba viendo el usuario era "El servidor
respondió 429", que suena a límite de uso propio y manda a buscar el problema en
el lugar equivocado. Ahora la suspensión se reconoce en el primer intento, no se
reintenta (reintentar solo acelera el 429) y el mensaje dice qué pasa y dónde se
arregla.
"""

import time

import requests

REINTENTOS = (0, 2, 5, 10)        # segundos de espera antes de cada intento
TIMEOUTS = (15, 30, 60, 60)       # el primero corto; los siguientes, arranque en frío

# Errores donde la petición no llegó a destino o murió en el transporte:
# repetirla no puede duplicar nada.
ERRORES_DE_CONEXION = (requests.exceptions.ConnectionError,
                       requests.exceptions.ConnectTimeout,
                       requests.exceptions.SSLError)
HTTP_REINTENTABLES = (502, 503, 504)

# Marca de la página que sirve el edge de Render cuando el servicio está
# suspendido. Es HTML, no JSON: no hay nada que reintentar hasta que alguien
# reactive el servicio desde el panel.
MARCA_SUSPENDIDO = "has been suspended"

MSG_SUSPENDIDO = (
    "El servicio de la API está SUSPENDIDO en Render (no es un problema del panel). "
    "Mientras siga así no hay checkout, pagos, referidos ni seguimiento en la tienda. "
    "Se reactiva desde el panel de Render → Billing (suele ser un cobro rechazado).")

MSG_429 = (
    "Render está contestando 429 (demasiados pedidos) a todo lo que sale de esta IP. "
    "Pasa cuando el servicio está suspendido o recién reiniciado y se lo llama varias "
    "veces seguidas. Esperá un minuto y, si sigue igual, revisá el estado del servicio "
    "en el panel de Render.")


def _esta_suspendido(resp) -> bool:
    """¿Esta respuesta es la página de servicio suspendido de Render?"""
    if resp is None or resp.status_code != 503:
        return False
    return MARCA_SUSPENDIDO in (resp.text or "")[:2000].lower()


def mensaje_humano(e: Exception) -> str:
    """Traduce el error de red a algo que se entienda desde el panel."""
    if isinstance(e, ERRORES_DE_CONEXION + (requests.exceptions.ReadTimeout,)):
        return ("No se pudo conectar con el servidor. Suele ser que está despertando "
                "(tarda hasta un minuto si estuvo inactivo). Probá de nuevo en unos segundos.")
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        if _esta_suspendido(e.response):
            return MSG_SUSPENDIDO
        if e.response.status_code == 429:
            return MSG_429
        if e.response.status_code in HTTP_REINTENTABLES:
            return "El servidor está reiniciando. Probá de nuevo en unos segundos."
        if e.response.status_code == 401:
            return "Contraseña de administrador incorrecta."
        return f"El servidor respondió {e.response.status_code}."
    return str(e)


def pedir(metodo, url, *, params=None, json_body=None, headers=None, idempotente=True,
          reintentos=REINTENTOS, timeouts=TIMEOUTS):
    """Llama a la API reintentando solo lo que es seguro reintentar.

    `idempotente` decide cuánto: en GET se reintenta todo (incluido un 502 o un
    read timeout), pero en POST/PATCH/DELETE solo los errores de CONEXIÓN. Un
    read timeout en un POST puede significar que el servidor sí lo procesó y la
    respuesta se perdió: repetirlo crearía dos descuentos, o dos de lo que sea.

    Devuelve el JSON de la respuesta, o {'error': <mensaje legible>}.
    """
    ultimo = None
    for intento, (espera, timeout) in enumerate(zip(reintentos, timeouts)):
        if espera:
            time.sleep(espera)
        try:
            resp = requests.request(metodo, url, params=params, json=json_body,
                                    headers=headers, timeout=timeout)
            if _esta_suspendido(resp):
                # Reintentar acá no despierta nada y acerca el 429 del edge.
                return {"error": MSG_SUSPENDIDO}
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            ultimo = e
            reintentable = isinstance(e, ERRORES_DE_CONEXION) or (
                idempotente and (
                    isinstance(e, requests.exceptions.ReadTimeout)
                    or (isinstance(e, requests.exceptions.HTTPError)
                        and e.response is not None
                        and e.response.status_code in HTTP_REINTENTABLES)))
            if not reintentable or intento == len(reintentos) - 1:
                break
    return {"error": mensaje_humano(ultimo)}
