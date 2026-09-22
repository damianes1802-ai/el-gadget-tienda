#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GENERADOR DE LA PÁGINA PÚBLICA /envios (pages/envios.html)

Publica el tarifario real de envíos (data/envios/zonas_envio.json, la misma
fuente que usa el checkout) como una página con datos concretos y
estructurados: tabla de zonas con costo/modalidad/plazo, partidos del GBA por
zona, y un FAQPage en JSON-LD. Es la página que Google y los asistentes (ChatGPT
y similares citan páginas con números concretos) pueden usar para responder
"cuánto cuesta / cuánto tarda el envío de El Gadget".

La página NO se edita a mano: cuando cambia el tarifario se edita el JSON y se
vuelve a correr este script (12_generar_paginas_producto.py también lo llama al
final de cada corrida, así que el pipeline diario la mantiene al día sola).

USO:
    python scripts/generar_pagina_envios.py

AUTOR: Sistema Ecommerce Automation
"""

import html
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.envios import resumen_envios, frases_envio, DEVOLUCION_DIAS

CANONICAL_DOMAIN = "https://elgadget.com.ar"
BRAND = "El Gadget"
WHATSAPP_NUM = "5491126228481"
OUTPUT_FILE = Config.BASE_DIR / 'pages' / 'envios.html'

FAVICON = ("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
           "<rect width='100' height='100' rx='22' fill='%2314151A'/>"
           "<rect x='14' y='34' width='72' height='34' rx='17' fill='none' stroke='white' stroke-width='7'/>"
           "<circle cx='34' cy='51' r='6' fill='white'/>"
           "<rect x='58' y='42' width='6' height='18' rx='2' fill='%23FFC700'/>"
           "<rect x='68' y='36' width='6' height='30' rx='2' fill='%23FFC700'/>"
           "<rect x='78' y='45' width='6' height='12' rx='2' fill='%23FFC700'/></svg>")


def _fecha_larga(iso: str) -> str:
    """'2026-06-14' -> '14 de junio de 2026' (sin depender del locale)."""
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    try:
        a, m, d = iso.split('-')
        return f"{int(d)} de {meses[int(m) - 1]} de {a}"
    except Exception:
        return iso


def armar_faq(res: dict, fr: dict) -> list:
    """Preguntas y respuestas (texto plano) — se usan tanto en el HTML visible
    como en el JSON-LD FAQPage, para que coincidan exactamente."""
    caba, resto, bsas = res['caba'], res['resto'], res['bsas']
    bonif = res.get('bonificado')
    gba = [z for z in res['zonas'] if z['modalidad'] == 'moto' and z['codigo'] != caba['codigo']]
    gba_min = min(gba, key=lambda z: z['costo'])['costo_fmt'] if gba else caba['costo_fmt']
    gba_max = max(gba, key=lambda z: z['costo'])['costo_fmt'] if gba else caba['costo_fmt']
    return [
        (
            "¿Cuánto cuesta el envío?",
            f"Depende de la zona: {caba['costo_fmt']} en CABA (moto), entre "
            f"{gba_min} y {gba_max} en el Gran Buenos Aires "
            f"según el cordón (moto), {bsas['costo_fmt']} al resto de la provincia de Buenos Aires (correo) "
            f"y {resto['costo_fmt']} al resto del país (correo). El costo exacto se calcula solo en el "
            f"checkout al indicar tu provincia y partido." + (f" {fr['bonificado']}" if fr['bonificado'] else ''),
        ),
        (
            "¿Cuánto tarda en llegar mi pedido?",
            f"En CABA y GBA el envío va en moto y llega {fr['moto']} desde el despacho. "
            f"Al resto de la provincia de Buenos Aires y al interior del país va por correo y demora "
            f"{fr['correo']}, según la distancia.",
        ),
        (
            "¿Hacen envíos a todo el país?",
            "Sí. Enviamos a todas las provincias de Argentina: en moto dentro de CABA y el Gran Buenos "
            "Aires, y por correo al resto de la provincia de Buenos Aires y al interior del país.",
        ),
    ] + ([
        (
            "¿Cuándo el envío es gratis?",
            f"Cuando el total de los productos del pedido, ya con descuentos aplicados, es de {bonif['minimo_fmt']} "
            f"o más y la dirección de entrega está en {fr['bonificado_zonas']}. El checkout lo aplica solo: "
            f"si se cumplen las dos condiciones, el envío figura en $0. En el resto de las zonas se cobra la "
            f"tarifa de la tabla.",
        ),
    ] if bonif else []) + [
        (
            "¿Cómo sigo mi pedido?",
            "Apenas se despacha te mandamos por email el número y el link de seguimiento. También podés "
            f"consultarlo en cualquier momento en {CANONICAL_DOMAIN}/seguimiento con tu número de orden. "
            "Si el pedido superó el plazo estimado para tu zona, escribinos por WhatsApp con el número de "
            "orden y lo revisamos en el día.",
        ),
    ]


def render(res: dict) -> str:
    fr = frases_envio(res)
    faq = armar_faq(res, fr)
    caba, resto = res['caba'], res['resto']
    bonif = res.get('bonificado')
    moto_hi = res['dias_moto'][1] if res['dias_moto'] else None
    correo = res['dias_correo']

    filas = '\n'.join(
        f"        <tr><td>{html.escape(z['nombre'])}</td><td>{html.escape(z['modalidad_fmt'])}</td>"
        f"<td>{html.escape(z['plazo'])}</td><td class=\"costo\">{z['costo_fmt']}"
        + (f"<br><span class=\"bonif\">Gratis desde {bonif['minimo_fmt']}</span>" if z['bonificado'] and bonif else '')
        + "</td></tr>"
        for z in res['zonas']
    )

    partidos_html = '\n'.join(
        f"      <details class=\"zona-partidos\"><summary>{html.escape(z['nombre'])} — "
        f"{z['costo_fmt']} · {html.escape(z['modalidad_fmt'].lower())} ({len(z['partidos'])} partidos)</summary>"
        f"<p>{html.escape(', '.join(z['partidos']))}.</p></details>"
        for z in res['zonas'] if z['partidos']
    )

    faq_html = '\n'.join(
        '    <div class="faq-item">\n'
        '      <button class="faq-question" onclick="toggleFaq(this)">\n'
        f'        {html.escape(q)}\n'
        '        <span class="icon">+</span>\n'
        '      </button>\n'
        '      <div class="faq-answer"><div class="faq-answer-inner">\n'
        f'        {html.escape(a)}\n'
        '      </div></div>\n'
        '    </div>'
        for q, a in faq
    )

    jsonld = [
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in faq
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{CANONICAL_DOMAIN}/"},
                {"@type": "ListItem", "position": 2, "name": "Envíos"},
            ],
        },
    ]

    meta_desc = (
        f"Envíos de {BRAND} a todo el país: moto en CABA y GBA ({fr['moto']}, desde {caba['costo_fmt']}), "
        f"correo al interior ({fr['correo']}). "
        + (f"{fr['bonificado_corto']} " if fr['bonificado_corto'] else '')
        + "Zonas, costos y plazos."
    )

    plazo_moto_txt = f"{moto_hi * 24} h" if moto_hi else "—"
    plazo_correo_txt = f"{correo[0]}-{correo[1]}" if correo else "—"
    if bonif:
        tarjeta3 = (f"<p style=\"font-size:28px;font-weight:700;color:var(--paper);margin:0 0 4px\">$0</p>"
                    f"<p style=\"font-size:12.5px;color:var(--paper);opacity:.8;margin:0\">envío gratis desde {bonif['minimo_fmt']}<br>"
                    f"<strong>{html.escape(fr['bonificado_zonas'])}</strong></p>")
    else:
        tarjeta3 = (f"<p style=\"font-size:28px;font-weight:700;color:var(--paper);margin:0 0 4px\">{caba['costo_fmt']}</p>"
                    "<p style=\"font-size:12.5px;color:var(--paper);opacity:.8;margin:0\">costo de envío<br><strong>desde (CABA)</strong></p>")

    seccion_bonif = f"""
  <div class="content-section">
    <h2>Envío gratis desde {bonif['minimo_fmt']} en {html.escape(fr['bonificado_zonas'])}</h2>
    <p>
      Si el total de los productos de tu pedido, <strong>ya con los descuentos aplicados</strong>, es de
      <strong>{bonif['minimo_fmt']} o más</strong> y la dirección de entrega está en {html.escape(fr['bonificado_zonas'])},
      el envío sale <strong>$0</strong>. No hace falta ningún código: el checkout lo aplica solo al calcular el envío.
      En el resto de las zonas se cobra la tarifa de la tabla.
    </p>
  </div>
""" if bonif else ''

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Envíos a todo el país: zonas, costos y plazos | {BRAND}</title>
<meta name="description" content="{html.escape(meta_desc)}">
<link rel="canonical" href="{CANONICAL_DOMAIN}/envios">
<meta property="og:type" content="website">
<meta property="og:title" content="Envíos a todo el país: zonas, costos y plazos | {BRAND}">
<meta property="og:description" content="{html.escape(meta_desc)}">
<meta property="og:url" content="{CANONICAL_DOMAIN}/envios">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="es_AR">
<meta name="theme-color" content="#14151A">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/css/style.css">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<style>
  .envios-tabla-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 10px; }}
  .envios-tabla {{ width: 100%; border-collapse: collapse; font-size: 13.5px; min-width: 520px; }}
  .envios-tabla thead tr {{ background: var(--gray-100); }}
  .envios-tabla th {{ padding: 9px 10px; text-align: left; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--gray-600); }}
  .envios-tabla td {{ padding: 10px; border-bottom: 1px solid var(--gray-100); vertical-align: middle; color: var(--gray-600); }}
  .envios-tabla td:first-child {{ font-weight: 600; color: var(--ink); }}
  .envios-tabla td.costo {{ font-family: 'Space Grotesk', sans-serif; font-weight: 700; color: var(--ink); white-space: nowrap; }}
  .zona-partidos {{ border: 1.5px solid var(--gray-200); border-radius: var(--radius-sm); padding: 10px 14px; margin-bottom: 8px; background: var(--paper); }}
  .zona-partidos summary {{ cursor: pointer; font-size: 13.5px; font-weight: 600; color: var(--ink); }}
  .zona-partidos p {{ margin: 8px 0 0; font-size: 13px; color: var(--gray-600); line-height: 1.7; }}
  .envios-nota {{ font-size: 12.5px; color: var(--gray-600); }}
  .envios-tabla .bonif {{ display: inline-block; margin-top: 4px; font-family: 'Inter', sans-serif; font-size: 10.5px; font-weight: 700; color: var(--green-ok); background: var(--green-pale); padding: 2px 8px; border-radius: 20px; white-space: nowrap; }}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="header-inner">
    <a href="/" class="logo">
      <div class="logo-badge">
        <img src="assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42">
      </div>
      <div class="logo-text">
        <div class="logo-name">El<span> Gadget</span></div>
        <div class="logo-tagline">Tienda online</div>
      </div>
    </a>
    <a href="carrito" class="cart-pill">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 01-8 0"/>
      </svg>
      <span class="label">Mi pedido</span>
      <span class="cart-badge" id="cartBadge">0</span>
    </a>
  </div>
</header>

<!-- BREADCRUMB -->
<div class="breadcrumb">
  <a href="/">Inicio</a>
  <span class="sep">/</span>
  <span class="current">Envíos</span>
</div>

<!-- CONTENIDO -->
<div class="page-wrap" style="max-width:760px">
  <h1 class="page-title">Envíos: zonas, costos y plazos</h1>

  <!-- RESUMEN VISUAL -->
  <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px">
    <div style="flex:1;min-width:160px;background:var(--cream);border-radius:12px;padding:16px 18px;text-align:center">
      <p style="font-size:28px;font-weight:700;color:var(--ink);margin:0 0 4px">{plazo_moto_txt}</p>
      <p style="font-size:12.5px;color:var(--gray-600);margin:0">hábiles en moto<br><strong>CABA y GBA</strong></p>
    </div>
    <div style="flex:1;min-width:160px;background:var(--cream);border-radius:12px;padding:16px 18px;text-align:center">
      <p style="font-size:28px;font-weight:700;color:var(--ink);margin:0 0 4px">{plazo_correo_txt}</p>
      <p style="font-size:12.5px;color:var(--gray-600);margin:0">días hábiles por correo<br><strong>resto del país</strong></p>
    </div>
    <div style="flex:1;min-width:160px;background:var(--ink);border-radius:12px;padding:16px 18px;text-align:center">
      {tarjeta3}
    </div>
  </div>

  <div class="content-section">
    <h2>Tarifario por zona</h2>
    <p>
      Enviamos a todo el país. El costo y el plazo dependen de la zona de entrega; el checkout los
      calcula solo cuando indicás tu provincia (y tu partido, si estás en la provincia de Buenos Aires).
    </p>
    <div class="envios-tabla-wrap">
      <table class="envios-tabla">
        <thead><tr><th>Zona</th><th>Modalidad</th><th>Plazo estimado</th><th>Costo</th></tr></thead>
        <tbody>
{filas}
        </tbody>
      </table>
    </div>
    <p class="envios-nota">Tarifas en pesos argentinos, vigentes al {_fecha_larga(res['fecha_actualizacion'])}. Los plazos son hábiles y se cuentan desde el despacho.</p>
  </div>
{seccion_bonif}
  <div class="content-section">
    <h2>Moto en CABA y Gran Buenos Aires</h2>
    <p>
      Dentro de la Ciudad de Buenos Aires y los partidos del Gran Buenos Aires el pedido va en moto
      (mensajería) y llega <strong>{fr['moto']}</strong> desde que lo despachamos. El GBA se divide en
      tres cordones con distinto costo; abajo podés ver a qué zona pertenece cada partido.
    </p>
{partidos_html}
  </div>

  <div class="content-section">
    <h2>Correo al resto de la provincia y al interior del país</h2>
    <p>
      Fuera del GBA (resto de la provincia de Buenos Aires y todas las demás provincias) el envío va por
      correo y demora <strong>{fr['correo']}</strong> según la distancia. Cuesta {res['bsas']['costo_fmt']}
      dentro de la provincia de Buenos Aires y {resto['costo_fmt']} al resto del país.
    </p>
    <p>
      Apenas se despacha te mandamos el número y el link de seguimiento por email; también podés
      consultarlo en <a href="seguimiento" style="color:var(--ink);font-weight:600">Seguimiento de pedido</a>.
    </p>
  </div>

  <div class="content-section">
    <h2>Cambios y devoluciones</h2>
    <p>
      Tenés <strong>{DEVOLUCION_DIAS} días hábiles</strong> desde que recibís el pedido para arrepentirte sin dar
      explicaciones: coordinamos el retiro sin costo y el reembolso va por el mismo medio de pago
      (Mercado Pago). Más detalle en <a href="devoluciones" style="color:var(--ink);font-weight:600">Devoluciones y garantías</a>.
    </p>
  </div>

  <div class="faq-category">
    <h2>Preguntas frecuentes sobre envíos</h2>
{faq_html}
  </div>

  <div class="content-section">
    <p style="font-size:12.5px">
      ¿Alguna otra duda? Escribinos por <a href="https://wa.me/{WHATSAPP_NUM}?text=Hola!%20Tengo%20una%20consulta%20sobre%20env%C3%ADos" target="_blank" rel="noopener" style="color:var(--ink);font-weight:600">WhatsApp</a> y te respondemos en el día.
    </p>
  </div>
</div>

<!-- FOOTER -->
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <div class="logo">
        <div class="logo-badge">
          <img src="assets/img/logo-badge-animado.gif" alt="El Gadget" width="42" height="42">
        </div>
        <div class="logo-text">
          <div class="logo-name">El<span> Gadget</span></div>
          <div class="logo-tagline">Tienda online</div>
        </div>
      </div>
      <p>Productos para el hogar, moda, tecnología y mucho más. Elegí tus productos, pagá online de forma segura y te lo enviamos a tu casa.</p>
    </div>
    <div class="footer-col">
      <h4>Ayuda</h4>
      <a href="carrito">Mi pedido</a>
      <a href="seguimiento">Seguimiento de pedido</a>
      <a href="faq">Preguntas frecuentes</a>
      <a href="https://wa.me/{WHATSAPP_NUM}?text=Hola!%20Tengo%20una%20consulta" target="_blank" rel="noopener">Hablar por WhatsApp</a>
    </div>
    <div class="footer-col">
      <h4>Información</h4>
      <a href="sobre_nosotros">Sobre nosotros</a>
      <a href="envios">Envíos</a>
      <a href="privacidad">Política de privacidad</a>
      <a href="devoluciones">Devoluciones y garantías</a>
      <a href="arrepentimiento">Botón de arrepentimiento</a>
      <a href="terminos">Términos y condiciones</a>
    </div>
  </div>
  <div class="footer-bottom">© <span id="year"></span> El Gadget · Todos los derechos reservados · <a href="privacidad" style="color:inherit;opacity:.8;text-decoration:none">Privacidad</a> · <a href="arrepentimiento" style="color:inherit;opacity:.8;text-decoration:none">Arrepentimiento</a> · <a href="terminos" style="color:inherit;opacity:.8;text-decoration:none">Términos</a></div>
  <div class="footer-legal">
    <strong>El Gadget</strong> &middot; Dami&aacute;n Ezequiel S&aacute;nchez &middot; CUIT 20-42396477-5 &middot; Responsable Monotributo<br>
    Esteban Echeverr&iacute;a 964, Wilde (B1875ATT), Provincia de Buenos Aires, Argentina<br>
    <a href="mailto:tienda@elgadget.com.ar">tienda@elgadget.com.ar</a> &middot; <a href="https://wa.me/{WHATSAPP_NUM}" target="_blank" rel="noopener">WhatsApp +54 9 11 2622-8481</a> &middot; <a href="/contacto">Contacto</a> &middot; <a href="/envios">Env&iacute;os</a>
  </div>
</footer>

<script src="assets/js/cart.js"></script>
<script>
document.getElementById('year').textContent = new Date().getFullYear();
function toggleFaq(btn) {{
  const item = btn.closest('.faq-item');
  item.classList.toggle('open');
}}
</script>
</body>
</html>
"""


def generar() -> int:
    res = resumen_envios()
    OUTPUT_FILE.write_text(render(res), encoding='utf-8')
    print(f"✅ Página de envíos generada: {OUTPUT_FILE} ({len(res['zonas'])} zonas, "
          f"tarifario del {res['fecha_actualizacion']})")
    return 0


if __name__ == "__main__":
    sys.exit(generar())
