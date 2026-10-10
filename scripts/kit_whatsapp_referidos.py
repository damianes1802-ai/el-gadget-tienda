#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PANEL DE RECONTACTO POR WHATSAPP A LOS REFERIDOS

Genera `salidas/kit_whatsapp_referidos.html`: una tarjeta por referido con el
botón para abrir WhatsApp con el primer mensaje ya escrito, el kit para
mandarle cuando responda, y sus links con el código cargado.

POR QUÉ ES MANUAL Y UNO POR UNO
-------------------------------
- Las **listas de difusión** de WhatsApp Business solo llegan a quien tiene el
  número de la tienda agendado. Estos 29 no lo tienen, así que una difusión
  no llegaría casi a nadie. Con 29 contactos, 1 a 1 es viable y convierte más.
- Un envío masivo automatizado desde un número nuevo es la forma más rápida de
  que lo bloqueen. Por eso este script **no manda nada**: arma los links y la
  persona decide y envía.
- Los textos se personalizan con nombre y fecha de alta: mensajes idénticos en
  serie es justo el patrón que WhatsApp marca como spam.

EL EMBUDO (4 pasos, explicado también dentro del HTML)
------------------------------------------------------
1. Reconexión: un mensaje corto que pide UNA respuesta, no una venta, y ofrece
   salida ("si no te interesa, decímelo"). Sin respuesta no hay paso 2.
2. Kit: recién a quien contesta, porque un kit sin contexto se ignora.
3. Una sola acción concreta con fecha (la fecha comercial vigente da el motivo).
4. Seguimiento a las 48 h: cómo le fue, o qué lo frenó.

PRIVACIDAD: la salida tiene nombres y teléfonos de personas reales y el repo es
público. Por eso se escribe en `salidas/`, que está en .gitignore. No moverla.

Uso:  python scripts/kit_whatsapp_referidos.py
"""

import html
import json
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.bloques_productos import fechas_comerciales_vigentes

CANONICAL_DOMAIN = "https://elgadget.com.ar"
API_PUBLICA = "https://el-gadget-tienda.onrender.com"
SALIDA = Path(__file__).parent.parent / 'salidas' / 'kit_whatsapp_referidos.html'

# Cuántos mensajes nuevos por día conviene mandar desde un número que todavía no
# tiene historial de conversaciones: ir de a tandas baja el riesgo de bloqueo.
TANDA_DIARIA = 10


def normalizar_telefono(crudo: str):
    """(e164, nota). e164=None cuando no se puede afirmar el número.

    Los 29 registros traen cinco formatos distintos, así que las reglas van
    explícitas y lo ambiguo se marca para revisar a mano: mandarle un WhatsApp
    a un número equivocado es peor que no mandarlo.
    """
    n = re.sub(r'\D', '', crudo or '')
    if not n:
        return None, 'sin teléfono cargado'
    if len(n) == 10:                       # 1167927434 -> móvil sin 54 ni 9
        return '549' + n, ''
    if len(n) == 11 and n.startswith('9'):  # 92235037684 -> 9 + 10 dígitos
        return '54' + n, ''
    if len(n) == 12 and n.startswith('54'):  # 543454109008 -> 54 + 10, falta el 9
        return '549' + n[2:], ''
    if len(n) == 13 and n.startswith('549'):  # ya está completo
        return n, ''
    return None, f'formato no reconocido ({len(n)} dígitos)'


def ocasion_vigente():
    """La fecha comercial que corre hoy: da el motivo para escribir ahora."""
    vigentes = [f for f in fechas_comerciales_vigentes() if f.get('entrega')]
    if not vigentes:
        return None
    ev = vigentes[0]
    dias = (ev['fecha'] - date.today()).days
    return {
        'nombre': ev['nombre'],
        'cuando': 'es hoy' if dias == 0 else ('es mañana' if dias == 1 else f'faltan {dias} días'),
        'path': ev['href'],
    }


def traer_referidos():
    env = Config.cargar_env()
    pwd = env.get('ADMIN_PASSWORD')
    if not pwd:
        raise SystemExit('Falta ADMIN_PASSWORD en config/.env')
    req = urllib.request.Request(
        f'{API_PUBLICA}/api/admin/referidos', headers={'X-Admin-Password': pwd})
    for intento in range(3):   # Render puede devolver 502 mientras despierta
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read().decode('utf-8'))
                return d if isinstance(d, list) else d.get('referidos', [])
        except Exception as e:
            if intento == 2:
                raise
            print(f'   reintento {intento + 1}/3 ({e})')
    return []


def mensajes(ref, oc):
    """Los tres textos del embudo, ya personalizados."""
    nombre = (ref.get('nombre') or '').strip().split(' ')[0] or 'Hola'
    codigo = ref['codigo']
    alta = (ref.get('creado_at') or '')[:10]
    try:
        alta_txt = datetime.strptime(alta, '%Y-%m-%d').strftime('%d/%m')
    except ValueError:
        alta_txt = alta
    link = f'{CANONICAL_DOMAIN}/?ref={quote(codigo)}'
    link_oc = f'{CANONICAL_DOMAIN}{oc["path"]}?ref={quote(codigo)}' if oc else link

    m1 = (
        f'Hola {nombre}, soy Damián de El Gadget 👋\n\n'
        f'Te escribo porque te anotaste en nuestro programa de referidos el {alta_txt} '
        f'y nunca te dimos las herramientas para arrancar. Error nuestro.\n\n'
        f'¿Seguís con ganas de ganar comisiones recomendando productos? '
        f'Si me decís que sí, te paso tu kit (la imagen lista para subir y tu link con descuento) '
        f'en un solo mensaje.\n\n'
        f'Y si no te interesa, decímelo tranquilo y no te escribo más 🙌'
    )

    motivo = ''
    if oc:
        motivo = (f'\n\n📅 Justo ahora conviene: {oc["nombre"]} {oc["cuando"]}. '
                  f'Esta es la página de regalos con tu descuento ya cargado:\n{link_oc}')

    m2 = (
        f'¡Genial {nombre}! Acá va tu kit 👇\n\n'
        f'1️⃣ *Tu link:* {link}\n'
        f'El que entra por ahí ya tiene el descuento cargado: no tiene que escribir ningún código. '
        f'Y la venta te queda registrada a vos automáticamente.\n\n'
        f'2️⃣ *La imagen* que te mando acá arriba es para tu estado de WhatsApp o tu historia de Instagram.\n\n'
        f'3️⃣ *Mensaje listo para reenviar:*\n'
        f'"Te paso mi link de El Gadget: entrás y ya te queda cargado hasta 20% OFF. {link}"'
        f'{motivo}'
    )

    m3 = (
        f'{nombre}, una sola cosa para hoy: subí la imagen a tu estado de WhatsApp.\n\n'
        f'Es lo que mejor funciona y te lleva 10 segundos. Con que la vean 20 personas '
        f'suele aparecer la primera consulta.\n\n'
        f'Cualquier cosa que te pregunten y no sepas, me escribís y te respondo al toque 💪'
    )
    return m1, m2, m3, link, link_oc


def render(refs, oc):
    hoy = date.today()
    listos, revisar = [], []
    for ref in refs:
        e164, nota = normalizar_telefono(ref.get('telefono'))
        (listos if e164 else revisar).append((ref, e164, nota))

    tarjetas = []
    for i, (ref, e164, _) in enumerate(listos, 1):
        m1, m2, m3, link, link_oc = mensajes(ref, oc)
        codigo = html.escape(ref['codigo'])
        nombre = html.escape(ref.get('nombre') or '—')
        alta = (ref.get('creado_at') or '')[:10]
        try:
            dias = (hoy - datetime.strptime(alta, '%Y-%m-%d').date()).days
        except ValueError:
            dias = '—'
        placa = f'{API_PUBLICA}/api/referidos/placa?codigo={quote(ref["codigo"])}'
        tanda = (i - 1) // TANDA_DIARIA + 1
        tarjetas.append(f'''
  <article class="c" data-id="{codigo}" data-tanda="{tanda}">
    <header>
      <label class="hecho"><input type="checkbox" data-k="{codigo}"> <span>Contactado</span></label>
      <div>
        <h2>{nombre} <span class="cod">{codigo}</span></h2>
        <p class="meta">Alta {alta} · hace {dias} días · tanda {tanda}</p>
      </div>
    </header>
    <a class="btn wa" href="https://wa.me/{e164}?text={quote(m1)}" target="_blank" rel="noopener">
      Abrir WhatsApp con el mensaje 1
    </a>
    <details>
      <summary>Mensaje 2 — el kit (solo si contesta)</summary>
      <p class="aviso">Antes de pegarlo, adjuntá la placa: <a href="{placa}" target="_blank" rel="noopener">descargar imagen</a></p>
      <pre id="m2-{codigo}">{html.escape(m2)}</pre>
      <button class="btn copy" data-t="m2-{codigo}">Copiar mensaje 2</button>
    </details>
    <details>
      <summary>Mensaje 3 — una acción concreta (al día siguiente)</summary>
      <pre id="m3-{codigo}">{html.escape(m3)}</pre>
      <button class="btn copy" data-t="m3-{codigo}">Copiar mensaje 3</button>
    </details>
    <p class="links">
      <a href="{html.escape(link)}" target="_blank" rel="noopener">su link</a> ·
      <a href="{html.escape(link_oc)}" target="_blank" rel="noopener">link de la ocasión</a> ·
      <a href="{placa}" target="_blank" rel="noopener">placa</a>
    </p>
  </article>''')

    filas_rev = ''.join(
        f'<tr><td>{html.escape(r.get("nombre") or "—")}</td><td>{html.escape(r["codigo"])}</td>'
        f'<td>{html.escape(r.get("telefono") or "")}</td><td>{html.escape(nota)}</td></tr>'
        for r, _, nota in revisar)
    bloque_rev = f'''
  <section class="rev">
    <h2>A revisar a mano ({len(revisar)})</h2>
    <p>No se pudo afirmar el número, así que no se arma el link: mandarle un WhatsApp
       a un número equivocado es peor que no mandarlo.</p>
    <table><tr><th>Nombre</th><th>Código</th><th>Teléfono cargado</th><th>Motivo</th></tr>{filas_rev}</table>
  </section>''' if revisar else ''

    oc_txt = (f'{oc["nombre"]} — {oc["cuando"]}' if oc else 'sin fecha comercial vigente')

    return f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recontacto por WhatsApp — referidos</title>
<style>
  :root {{ --ink:#14151A; --accent:#FFC700; --wa:#25D366; --g200:#E6E4DF; --g600:#6B6B70; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; padding:28px 16px 60px; background:#F7F6F3; color:var(--ink);
         font:15px/1.6 'Segoe UI',Helvetica,Arial,sans-serif }}
  .wrap {{ max-width:780px; margin:0 auto }}
  h1 {{ font-size:25px; margin:0 0 6px; text-align:center }}
  .sub {{ text-align:center; color:var(--g600); margin:0 0 24px; font-size:14px }}
  .plan {{ background:#fff; border:1.5px solid var(--g200); border-radius:14px; padding:18px 22px; margin-bottom:24px }}
  .plan h2 {{ font-size:16px; margin:0 0 10px }}
  .plan ol {{ margin:0; padding-left:20px }} .plan li {{ margin-bottom:6px }}
  .plan .reglas {{ margin:14px 0 0; padding:12px 14px; background:#FFF7DD; border-radius:10px; font-size:13.5px }}
  .c {{ background:#fff; border:1.5px solid var(--g200); border-radius:14px; padding:16px 18px; margin-bottom:14px }}
  .c.ok {{ opacity:.5 }}
  .c header {{ display:flex; gap:12px; align-items:flex-start; margin-bottom:12px }}
  .c h2 {{ font-size:17px; margin:0 }}
  .cod {{ background:var(--ink); color:var(--accent); font-size:12px; padding:2px 8px; border-radius:6px; vertical-align:middle }}
  .meta {{ margin:2px 0 0; font-size:12.5px; color:var(--g600) }}
  .hecho {{ display:flex; align-items:center; gap:6px; font-size:12px; color:var(--g600); white-space:nowrap }}
  .btn {{ display:inline-block; border:0; cursor:pointer; font:inherit; font-weight:700; font-size:14px;
          padding:11px 20px; border-radius:10px; text-decoration:none }}
  .wa {{ background:var(--wa); color:#fff; display:block; text-align:center }}
  .copy {{ background:var(--accent); color:var(--ink); margin-top:8px }}
  details {{ margin-top:10px; border-top:1px solid var(--g200); padding-top:10px }}
  summary {{ cursor:pointer; font-size:13.5px; font-weight:600 }}
  pre {{ white-space:pre-wrap; background:#F7F6F3; border:1px solid var(--g200); border-radius:10px;
         padding:12px 14px; font:13px/1.55 'Segoe UI',Helvetica,Arial,sans-serif; margin:10px 0 0 }}
  .aviso {{ font-size:12.5px; color:var(--g600); margin:8px 0 0 }}
  .links {{ margin:12px 0 0; font-size:12.5px; color:var(--g600) }}
  .rev {{ background:#fff; border:1.5px solid #E58B8B; border-radius:14px; padding:16px 20px; margin-top:26px }}
  .rev h2 {{ font-size:16px; margin:0 0 8px }}
  table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px }}
  th,td {{ text-align:left; padding:7px 8px; border-bottom:1px solid var(--g200) }}
</style></head><body><div class="wrap">
<h1>Recontacto por WhatsApp</h1>
<p class="sub">{len(listos)} referidos con número usable · {len(revisar)} a revisar · ocasión: {html.escape(oc_txt)}</p>

<div class="plan">
  <h2>El embudo</h2>
  <ol>
    <li><strong>Mensaje 1 — reconexión.</strong> Pide una respuesta, no una venta, y ofrece salida. Sin respuesta no se sigue.</li>
    <li><strong>Mensaje 2 — el kit.</strong> Solo a quien contesta: la placa adjunta + su link + el texto para reenviar.</li>
    <li><strong>Mensaje 3 — una acción.</strong> Al día siguiente, una sola cosa concreta: subir la placa al estado.</li>
    <li><strong>A las 48 h.</strong> Si la subió, preguntarle cómo le fue. Si no, preguntarle qué lo frenó (ahí está la información que falta).</li>
  </ol>
  <div class="reglas">
    <strong>Reglas que evitan que bloqueen el número:</strong> mandá de a {TANDA_DIARIA} por día
    (las tarjetas ya vienen numeradas por tanda) · nunca el mismo texto idéntico a todos:
    estos ya salen personalizados · no insistas más de una vez a quien no contesta ·
    las listas de difusión no sirven acá, solo llegan a quien te tenga agendado.
  </div>
</div>
{''.join(tarjetas)}
{bloque_rev}
</div>
<script>
  // Marca local (este archivo es tuyo, no sale de tu máquina).
  document.querySelectorAll('.hecho input').forEach(function (cb) {{
    var k = 'wa_' + cb.dataset.k;
    try {{ cb.checked = localStorage.getItem(k) === '1'; }} catch (e) {{}}
    cb.closest('.c').classList.toggle('ok', cb.checked);
    cb.addEventListener('change', function () {{
      try {{ localStorage.setItem(k, cb.checked ? '1' : '0'); }} catch (e) {{}}
      cb.closest('.c').classList.toggle('ok', cb.checked);
    }});
  }});
  document.querySelectorAll('.copy').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var t = document.getElementById(b.dataset.t).innerText;
      navigator.clipboard.writeText(t).then(function () {{
        var o = b.textContent; b.textContent = '¡Copiado!';
        setTimeout(function () {{ b.textContent = o; }}, 1400);
      }});
    }});
  }});
</script>
</body></html>
'''


def main():
    print('\n' + '=' * 70)
    print('📲 PANEL DE RECONTACTO POR WHATSAPP A LOS REFERIDOS')
    print('=' * 70 + '\n')
    refs = [r for r in traer_referidos()
            if r.get('activo') and not (r.get('cantidad_ventas') or 0)]
    if not refs:
        print('No hay referidos activos sin ventas.')
        return 1
    refs.sort(key=lambda r: r.get('creado_at') or '', reverse=True)
    oc = ocasion_vigente()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(render(refs, oc), encoding='utf-8')

    usables = sum(1 for r in refs if normalizar_telefono(r.get('telefono'))[0])
    print(f'👥 Referidos activos sin ventas: {len(refs)}')
    print(f'📱 Con número usable: {usables} · a revisar a mano: {len(refs) - usables}')
    print(f'📅 Ocasión: {oc["nombre"]} {oc["cuando"]}' if oc else '📅 Sin fecha comercial vigente')
    print(f'🗂️  Tandas de {TANDA_DIARIA} por día -> {-(-usables // TANDA_DIARIA)} días')
    print(f'\n✅ Panel: {SALIDA}')
    print('   (tiene datos personales y queda en salidas/, que está gitignoreado)')
    print('\n' + '=' * 70 + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
