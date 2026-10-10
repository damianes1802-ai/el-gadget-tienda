#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pie legal único del sitio (identidad, contacto, políticas y Data Fiscal).

POR QUÉ ESTÁ CENTRALIZADO (2026-10-10)
--------------------------------------
Merchant Center suspendió la cuenta por **Misrepresentation** ("prevents all
products from showing in Argentina"), cuyo checklist pide transparencia sobre
quién vende, cómo contactarlo y **cuáles son sus políticas**. La auditoría del
sitio en vivo mostró que ese pie estaba copiado en cuatro plantillas y veinte
HTML sueltos, y que cada copia linkeaba cosas distintas:

| página         | términos | privacidad | arrepentimiento | Data Fiscal |
|----------------|----------|------------|-----------------|-------------|
| home           | sí       | sí         | sí              | sí          |
| ficha          | **no**   | **no**     | sí              | **no**      |
| blog           | **no**   | **no**     | **no**          | **no**      |
| carrito        | **no**   | **no**     | **no**          | **no**      |
| **checkout**   | **no**   | **no**     | **no**          | **no**      |

O sea: la página donde el cliente paga no tenía forma de llegar a los términos
ni a la política de privacidad, y la ficha —que es donde aterriza el revisor de
Google desde un anuncio o un resultado— tampoco. Con una sola constante, todas
las páginas publican lo mismo y no se puede volver a desincronizar.

Además se suma el link a la **Ventanilla Única Federal de Defensa del
Consumidor** (Res. 1033/2021), que en Argentina es obligatorio junto con el
botón de arrepentimiento y no estaba en ninguna página. La URL oficial
`argentina.gob.ar/produccion/defensadelconsumidor/formulario` redirige (301) a
la de abajo, verificado el 2026-10-10.

El `<div class="footer-legal">` tiene su CSS en `pages/assets/css/style.css`
(centrado, chico, sobre el fondo oscuro del footer).
"""

# Datos del titular tal como figuran en ARCA. Cambiarlos acá los cambia en todo
# el sitio: no editar el HTML generado a mano.
TITULAR = "Dami&aacute;n Ezequiel S&aacute;nchez"
CUIT = "20-42396477-5"
CONDICION = "Responsable Monotributo"
DOMICILIO = "Esteban Echeverr&iacute;a 964, Wilde (B1875ATT), Provincia de Buenos Aires, Argentina"
EMAIL = "tienda@elgadget.com.ar"
WHATSAPP_NUM = "5491126228481"
WHATSAPP_VISIBLE = "+54 9 11 2622-8481"

# QR de Data Fiscal de ARCA (RG 4004-E). El target `_F960AFIPInfo` es el que
# exige el organismo para que abra en su ventana.
DATA_FISCAL_URL = "https://qr.afip.gob.ar/?qr=OyqHTfkU-QEoIQOd4mE62A,,"
DATA_FISCAL_IMG = "/assets/img/DATAWEB.jpg"

# Ventanilla Única Federal de Defensa del Consumidor (Res. 1033/2021).
DEFENSA_CONSUMIDOR_URL = "https://autogestion.produccion.gob.ar/consumidores"

_POLITICAS = [
    ("/terminos", "T&eacute;rminos y condiciones"),
    ("/privacidad", "Pol&iacute;tica de privacidad"),
    ("/devoluciones", "Devoluciones y garant&iacute;as"),
    ("/arrepentimiento", "Bot&oacute;n de arrepentimiento"),
    ("/faq", "Preguntas frecuentes"),
]


def footer_legal() -> str:
    """El bloque completo, idéntico en toda página del sitio."""
    politicas = ' &middot; '.join(f'<a href="{u}">{t}</a>' for u, t in _POLITICAS)
    return f'''<div class="footer-legal">
    <strong>El Gadget</strong> &middot; {TITULAR} &middot; CUIT {CUIT} &middot; {CONDICION}<br>
    {DOMICILIO}<br>
    <a href="mailto:{EMAIL}">{EMAIL}</a> &middot; <a href="https://wa.me/{WHATSAPP_NUM}" target="_blank" rel="noopener">WhatsApp {WHATSAPP_VISIBLE}</a> &middot; <a href="/contacto">Contacto</a> &middot; <a href="/envios">Env&iacute;os</a><br>
    {politicas} &middot; <a href="{DEFENSA_CONSUMIDOR_URL}" target="_blank" rel="noopener">Defensa del Consumidor</a>
    <a href="{DATA_FISCAL_URL}" target="_F960AFIPInfo" rel="noopener"><img src="{DATA_FISCAL_IMG}" alt="Data Fiscal ARCA" loading="lazy" width="239" height="327" style="height:48px;width:auto;margin:10px auto 0;display:block"></a>
  </div>'''


FOOTER_LEGAL = footer_legal()
