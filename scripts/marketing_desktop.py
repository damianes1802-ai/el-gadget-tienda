#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — consola de métricas + generador de contenido

Ventana nativa (pywebview) que carga marketing_app/index.html y expone una API
Python (clase Api) vía window.pywebview.api.*. Consume los endpoints admin de
Render para métricas y usa Claude API para generar contenido de Instagram.
"""

import json
import random
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import requests
import webview

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

API_URL = "https://el-gadget-tienda.onrender.com"
BASE_DIR = Path(__file__).parent.parent
MARKETING_CONFIG_FILE = BASE_DIR / "marketing_app" / "config.json"
CONTENIDOS_DB = BASE_DIR / "marketing_app" / "data" / "contenidos.db"
CLOUDINARY_BASE = "https://res.cloudinary.com/deq2ofluf/image/upload"

# ── Pilares y formatos de contenido Instagram ──
# Distribución: 2/7 educativo + 1/7 motivacional + 2/7 engagement + 2/7 producto
# El perfil debe verse como tienda desde el primer momento (2 de cada 7 posts son producto)
PILARES = {
    "educativo":    {"peso": 28, "desc": "Contenido de valor que enseña cómo funciona el programa de referidos y cómo ganar dinero"},
    "motivacional": {"peso": 15, "desc": "Historias de éxito, cálculos de ganancias, inspiración para empezar"},
    "engagement":   {"peso": 28, "desc": "Preguntas, encuestas, interacción con la comunidad"},
    "producto":     {"peso": 29, "desc": "Producto destacado con precio, descuento referido y ángulo de venta"},
}

FORMATOS = {
    # EDUCATIVO (35%) — enseñar sobre el programa
    "ED-01": {"tipo": "reel",     "pilar": "educativo",    "persona": "lucas", "desc": "Tutorial: 'Así funciona el programa de referidos de El Gadget — paso a paso en 30 segundos'"},
    "ED-02": {"tipo": "carrusel", "pilar": "educativo",    "persona": "maria", "desc": "Guía visual: '5 formas de compartir tu código y ganar comisiones' (slide por forma: WA, IG Stories, grupos, link directo, redes)"},
    "ED-03": {"tipo": "reel",     "pilar": "educativo",    "persona": "lucas", "desc": "Tips de venta: '3 errores que comete todo referido nuevo (y cómo evitarlos)'"},
    "ED-04": {"tipo": "carrusel", "pilar": "educativo",    "persona": "ana",   "desc": "FAQ del programa: responder las 5 preguntas más comunes sobre cómo cobrar, cuánto se gana, cómo subir de tier"},

    # MOTIVACIONAL (30%) — inspirar a registrarse
    "MO-01": {"tipo": "reel",     "pilar": "motivacional", "persona": "lucas", "desc": "Storytime: 'Así gano plata extra sin inversión — mi experiencia como referido de El Gadget'"},
    "MO-02": {"tipo": "post",     "pilar": "motivacional", "persona": "maria", "desc": "Cálculo real: 'Si compartís con 10 amigos y 3 compran, ganás $X por mes. Sin invertir un peso.'"},
    "MO-03": {"tipo": "reel",     "pilar": "motivacional", "persona": "lucas", "desc": "Comparación: 'El Gadget vs otros programas de afiliados en Argentina — por qué este conviene más'"},
    "MO-04": {"tipo": "story",    "pilar": "motivacional", "persona": "sofi",  "desc": "Behind the scenes: mostrar el panel de comisiones con números reales (difuminados) y reaccionar"},

    # ENGAGEMENT (20%) — interacción y comunidad
    "EN-01": {"tipo": "story",    "pilar": "engagement",   "persona": "maria", "desc": "Encuesta/Poll: '¿Qué harías con $30.000 extra por mes?' con opciones divertidas"},
    "EN-02": {"tipo": "post",     "pilar": "engagement",   "persona": "lucas", "desc": "Pregunta abierta: '¿Cuál es el producto de El Gadget que más recomendarías? Contanos en comentarios'"},
    "EN-03": {"tipo": "reel",     "pilar": "engagement",   "persona": "maria", "desc": "Challenge: 'Compartí este reel con alguien que necesita un ingreso extra — taggealo'"},

    # PRODUCTO (29%) — showcase con ángulo referido (2 de cada 7 posts)
    "PR-01": {"tipo": "reel",     "pilar": "producto",     "persona": "maria", "desc": "Producto en acción: problema → solución. Mostrá el antes/después. CTA: 'Compartilo con tu código y ganá comisión'"},
    "PR-02": {"tipo": "post",     "pilar": "producto",     "persona": "sofi",  "desc": "Foto producto destacada: nombre, precio público tachado, precio con descuento referido, CTA 'link en bio'"},
    "PR-03": {"tipo": "reel",     "pilar": "producto",     "persona": "lucas", "desc": "Producto viral: 'Este producto está volando — con código referido hasta 20% OFF'. Mostrar el producto y el ahorro"},
    "PR-04": {"tipo": "post",     "pilar": "producto",     "persona": "ana",   "desc": "Review/reseña: opinión honesta del producto con datos (material, medidas, utilidad real). Enfoque profesional"},
    "PR-05": {"tipo": "carrusel", "pilar": "producto",     "persona": "maria", "desc": "Comparativa de valor: precio El Gadget vs precio en otros lados. Mostrar el ahorro + descuento referido adicional"},
}

PERSONAS_DESC = {
    "maria": """PERSONA: María — mamá urbana 25-40 años, CABA/GBA.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "El sueldo no alcanza y los precios suben cada mes"
- "Quiero algo flexible que pueda hacer desde casa, con los chicos"
- "Mis amigas me piden recomendaciones de productos todo el tiempo"
- "No tengo capital para arrancar un emprendimiento"
- "Ya recomiendo cosas gratis en el grupo de mamás, ¿por qué no cobrar?"
TONO: cálido, de mamá a mamá. Hablale como si fueras una amiga que le cuenta un dato útil, no como vendedor.
ÁNGULOS que funcionan con María: ahorro familiar, practicidad, hijos, organización del hogar, grupos de WhatsApp, ganar sin salir de casa.""",

    "lucas": """PERSONA: Lucas — joven 18-34 años, urbano, nativo digital.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Estoy cansado de laburar para otro y ganar poco"
- "Quiero un side hustle que no me consuma todo el día"
- "Mis amigos ganan plata en redes y yo no arranco nunca"
- "No tengo plata para invertir en un negocio"
- "Quiero ganar por mi cuenta, no depender de un sueldo fijo"
TONO: directo, sin vueltas, como un amigo que te cuenta algo que funciona. Nada de "gurú" ni promesas exageradas.
ÁNGULOS que funcionan con Lucas: libertad, independencia, estatus ("mirá cuánto generé"), competencia amistosa, tendencias, resultados rápidos.""",

    "ana": """PERSONA: Ana — profesional 35-50 años, buen poder adquisitivo.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Si un producto me gusta, lo recomiendo naturalmente a colegas y familia"
- "No necesito otro trabajo, pero un ingreso extra no viene mal"
- "Solo recomiendo cosas que yo misma probé y me gustaron"
- "No quiero quemar mi reputación profesional con algo trucho"
- "Valoro la transparencia y saber exactamente cuánto gano"
TONO: adulto, profesional, sin exageraciones. Datos concretos, sin emojis excesivos. Hablale con respeto a su inteligencia.
ÁNGULOS que funcionan con Ana: calidad del producto, confianza, transparencia del programa, números concretos, recomendación genuina.""",

    "sofi": """PERSONA: Sofi — creadora de contenido 18-45 años, tiene audiencia.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Busco marcas que paguen bien y sean transparentes con el tracking"
- "No quiero recomendar algo malo y perder credibilidad"
- "Necesito productos instagrameables que mi audiencia quiera comprar"
- "Quiero flexibilidad, no contratos ni obligaciones de publicación"
- "Los programas de afiliados suelen pagar poco y tarde"
TONO: natural, como una creadora hablando de una oportunidad real. Sin parecer publicidad.
ÁNGULOS que funcionan con Sofi: monetización de audiencia, productos reales para mostrar, comisiones competitivas, tracking transparente.""",

    "martin": """PERSONA: Martín — revendedor/mayorista 30-50 años.
PAIN POINTS que debés tocar (elegí 1 por post, NO todos):
- "Necesito margen real, no descuentos que no dejan ganancia"
- "Quiero variedad de productos para ofrecer a mis clientes"
- "Me importa que el envío sea confiable y llegue bien"
- "Necesito factura para mi negocio"
TONO: directo, con números, orientado al negocio. Mostrá márgenes concretos.
ÁNGULOS que funcionan con Martín: 25% OFF, márgenes de reventa, variedad de catálogo, envío confiable.""",
}

SYSTEM_PROMPT = """Sos el community manager de El Gadget, una tienda online argentina. Publicás desde la CUENTA OFICIAL de El Gadget en Instagram.

OBJETIVO: conseguir referidos para el programa de comisiones + mostrar productos.

DATOS DEL PROGRAMA:
- Registro gratis, sin inversión, sin stock, sin envíos
- Comisión: 7% (base), 11% (5+ ventas/mes), 15% (15+ ventas/mes)
- Descuento para quien compra: 10-20% según monto
- Cobro el día 5 de cada mes · URL: elgadget.com.ar/referidos

REGLAS DE STORYTELLING (MUY IMPORTANTE):
- Publicás desde la cuenta de EL GADGET, NO desde una persona. No digas "yo gané" ni "me pasó".
- Usá escenarios relatables: "Imaginá que...", "¿Te pasó que...?", "Hay quienes ya..."
- Usá datos reales del programa (te los paso en el prompt) para dar credibilidad
- Mostrá situaciones cotidianas: el grupo de mamás, la charla con amigos, el scroll en el celu
- NUNCA inventes testimonios ni reviews de personas específicas
- No hagas promesas de ingresos específicos salvo que uses cálculos verificables
- Cada post debe tener UN SOLO ángulo/pain point, no listar todos los beneficios

REGLAS DE HOOKS (OBLIGATORIO):
- SIEMPRE generá un hook. Nunca lo dejes vacío.
- El hook son las primeras palabras que detienen el scroll. Debe generar curiosidad o identificación.
- Buenos hooks: preguntas que la persona se hace, datos sorprendentes, situaciones que identifican
- MAL: "Te cuento cómo funciona" (aburrido), "¿Sabías que...?" (sobreusado)
- BIEN: "El grupo de mamás puede ser tu mejor fuente de ingresos", "3 compras de tus amigos = $10.000 en tu bolsillo"

REGLAS DE VARIEDAD:
- NO repitas la misma estructura. Variá entre: pregunta, afirmación impactante, dato numérico, situación cotidiana
- NO uses siempre "Sin inversión, sin stock, sin envíos" como lista. Integralo naturalmente en la historia
- Variá los CTAs: "link en bio", "registrate gratis", "conocé el programa", "empezá hoy"
- NO empieces todos los captions igual. Variá el arranque.

REGLAS DE TONO:
- Español argentino (vos/voseo): "mirá", "registrate", "compartí"
- Cercano y directo, sin exagerar. NO uses lenguaje de "gurú" ni promesas infladas
- NUNCA menciones "Droppers" ni ningún proveedor
- Precios siempre reales y actuales
- Emojis: máximo 2-3 por caption, nunca al inicio de cada línea
- NO hagas listas con emoji al principio de cada punto (❌ "📱 Registrate / 💰 Ganá / 📦 Sin stock")

HASHTAGS (8-12 por post, mezcla populares + nicho):
PROGRAMA: #referidoselgadget #ganardinero #ingresosextra #comisiones #dineroextra #negocioonline
ARGENTINA: #emprendedoresargentinos #tiendaonlineargentina #compraonline #ofertasargentina
HOGAR: #organizaciondelhogar #decoracion #hogarorganizado #ordenencasa #ideasparaelhogar
MODA: #modaargentina #accesorios #tendencias #moda2026
MAMÁS: #mamasargentinas #mamaemprendedora #vidademama #cosasdemama
TECH: #gadgets #tecnologia #productosvirales #tiktokfinds

Respondé SOLAMENTE con un objeto JSON válido (sin texto adicional, sin markdown).
Los campos varían según el pilar de contenido indicado en el prompt del usuario:

TODOS los pilares DEBEN incluir "hook" (NUNCA vacío). El hook es la frase corta que detiene el scroll.

PILAR EDUCATIVO:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "titulo": "título corto (máx 6 palabras)", "puntos": ["punto 1 (MÁXIMO 40 chars)", "punto 2", ...max 5], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto corto para barra inferior"}
Puntos MÁXIMO 40 caracteres. Ej: "Mandalo por WhatsApp", NO "WhatsApp directo: mandá tu código a una amiga"

PILAR MOTIVACIONAL:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "numero_grande": "$X.XXX (número impactante)", "subtexto": "qué representa (máx 50 chars)", "bullets": ["beneficio (máx 35 chars)", ...max 4], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}

PILAR ENGAGEMENT:
{"hook": "frase que detiene el scroll (OBLIGATORIO)", "pregunta": "pregunta (máx 50 chars)", "opciones": ["opción (máx 30 chars)", ...max 4], "caption": "texto para IG", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}

PILAR PRODUCTO:
{"hook": "frase sobre el PROBLEMA que resuelve el producto (OBLIGATORIO)", "caption": "texto para IG con ángulo de referido", "caption_b": "variante B", "hashtags": "8-12 hashtags", "cta": "CTA final", "cta_bar": "texto para barra inferior"}"""


class Api:
    def __init__(self):
        env = Config.cargar_env()
        self.admin_password = env.get('ADMIN_PASSWORD', 'admin2024')
        self.anthropic_key = env.get('ANTHROPIC_API_KEY', '')
        self._init_contenidos_db()

    def _init_contenidos_db(self):
        CONTENIDOS_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CONTENIDOS_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contenidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                formato TEXT NOT NULL,
                persona TEXT NOT NULL,
                producto_sku TEXT,
                producto_nombre TEXT,
                producto_precio REAL,
                producto_imagen TEXT,
                caption TEXT NOT NULL,
                caption_variante_b TEXT,
                hashtags TEXT,
                hook TEXT,
                cta TEXT,
                estado TEXT DEFAULT 'borrador',
                media_url TEXT,
                score_esperado TEXT,
                score_real TEXT,
                notas_owner TEXT,
                creado_at TEXT DEFAULT (datetime('now')),
                aprobado_at TEXT,
                publicado_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _contenidos_db(self):
        conn = sqlite3.connect(str(CONTENIDOS_DB))
        conn.row_factory = sqlite3.Row
        return conn

    def _headers(self):
        return {"X-Admin-Password": self.admin_password}

    def _get(self, path, params=None):
        try:
            resp = requests.get(f"{API_URL}{path}", params=params, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ── Data fetching (métricas) ──

    def get_estadisticas(self):
        return self._get("/api/estadisticas")

    def get_all_ordenes(self):
        return self._get("/api/ordenes", params={"limit": 200})

    def get_referidos(self):
        return self._get("/api/admin/referidos")

    def get_clientes(self):
        return self._get("/api/clientes")

    def get_usuarios(self):
        return self._get("/api/admin/usuarios")

    def get_descuentos(self):
        return self._get("/api/admin/descuentos")

    def get_productos(self):
        return self._get("/api/productos", params={"limit": 1000, "incluir_agotados": "true"})

    # ── Config local ──

    def get_marketing_config(self):
        try:
            if MARKETING_CONFIG_FILE.exists():
                return json.loads(MARKETING_CONFIG_FILE.read_text(encoding="utf-8"))
            return {}
        except Exception as e:
            return {"error": str(e)}

    def guardar_marketing_config(self, config):
        try:
            MARKETING_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def check_connection(self):
        import time
        t0 = time.time()
        result = self._get("/api/estadisticas")
        latency = round((time.time() - t0) * 1000)
        if "error" in result:
            return {"ok": False, "error": result["error"], "latency_ms": latency}
        return {"ok": True, "latency_ms": latency}

    # ── Content Generator (Claude API) ──

    def _parse_json_response(self, text):
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)
        return json.loads(cleaned)

    def generar_contenido(self, producto, formato, persona):
        try:
            if not self.anthropic_key:
                return {"error": "ANTHROPIC_API_KEY no configurada"}

            fmt = FORMATOS.get(formato)
            if not fmt:
                return {"error": f"Formato {formato} no existe"}

            persona_desc = PERSONAS_DESC.get(persona, PERSONAS_DESC.get(fmt["persona"], ""))
            nombre = producto.get("nombre", "Producto")
            precio = producto.get("precio_venta", 0)
            desc = producto.get("descripcion", "")[:200]
            cat = producto.get("categoria", "")

            pilar = fmt.get("pilar", "producto")

            # Datos reales del programa para enriquecer el contenido
            stats_line = ""
            try:
                refs = self.get_referidos()
                if isinstance(refs, list) and refs:
                    activos = len([r for r in refs if r.get("activo")])
                    total_com = sum(r.get("comision_total", 0) for r in refs)
                    stats_line = f"""
DATOS REALES DEL PROGRAMA (usá estos números en el contenido cuando sea relevante):
- Referidos activos actualmente: {activos}
- Comisiones totales generadas: ${total_com:,.0f}
- Comisión promedio por referido: ${total_com / max(activos, 1):,.0f}"""
            except Exception:
                pass

            # Few-shot: incluir captions aprobados como ejemplo de tono
            few_shot = ""
            try:
                conn_fs = self._contenidos_db()
                aprobados = conn_fs.execute(
                    "SELECT caption FROM contenidos WHERE estado = 'aprobado' ORDER BY aprobado_at DESC LIMIT 3"
                ).fetchall()
                conn_fs.close()
                if aprobados:
                    ejemplos = "\n".join(f"- \"{row['caption'][:200]}\"" for row in aprobados)
                    few_shot = f"""
EJEMPLOS DE CAPTIONS APROBADOS ANTERIORMENTE (usá como referencia de tono, NO copies):
{ejemplos}"""
            except Exception:
                pass

            # Instrucciones específicas por pilar
            pilar_instrucciones = {
                "educativo": """INSTRUCCIONES PARA ESTE POST EDUCATIVO:
- Enseñá algo útil y concreto sobre el programa de referidos
- Usá un escenario cotidiano como punto de entrada (NO empeces explicando el programa)
- Los puntos/bullets deben ser accionables y cortos (máx 40 caracteres cada uno)
- El tono debe ser "te cuento un dato que te va a servir", no "te vendo algo"
- Terminá con una invitación suave, no un CTA agresivo""",
                "motivacional": """INSTRUCCIONES PARA ESTE POST MOTIVACIONAL:
- Arrancá con un número impactante o una situación que genere identificación
- Mostrá el cálculo real de cuánto se puede ganar (con números verificables)
- Los bullets deben ser beneficios DISTINTOS entre sí (no parafrasear lo mismo)
- El número grande debe ser un dato real o un cálculo honesto, no inflado
- El tono es "mirá lo que es posible", no "¡hacete millonario!"
- Bullets máximo 35 caracteres cada uno""",
                "engagement": """INSTRUCCIONES PARA ESTE POST DE ENGAGEMENT:
- La pregunta debe generar una respuesta REAL (que la gente quiera comentar)
- NO hagas preguntas obvias ni que se respondan con sí/no
- Las opciones deben ser divertidas, relatables y variadas (máx 30 chars cada una)
- El post debe provocar que la gente se sienta identificada con una opción
- Relacioná la pregunta con la vida cotidiana de la persona target, no con el programa directamente
- La conexión con el programa de referidos debe ser sutil, en el caption, no en la pregunta""",
                "producto": """INSTRUCCIONES PARA ESTE POST DE PRODUCTO:
- El producto es el protagonista. Mostrá cómo resuelve un problema real
- El hook debe describir el PROBLEMA, no el producto
- Mencioná el precio con y sin descuento de referido
- El ángulo de referido es secundario: "y si lo compartís con tu código, ganás comisión"
- Describí la experiencia de uso, no las especificaciones técnicas
- El CTA puede ser "compralo" o "compartilo con tu código" según el ángulo""",
            }

            user_prompt = f"""Generá contenido para Instagram. Publicás desde la CUENTA OFICIAL de El Gadget.

PILAR: {pilar.upper()}
Formato: {formato} — {fmt['desc']}
Tipo de publicación: {fmt['tipo']}

{pilar_instrucciones.get(pilar, '')}

PERSONA A LA QUE LE HABLÁS:
{persona_desc}
Elegí UN SOLO pain point de la lista y basá todo el post en ese ángulo.
{stats_line}
{few_shot}

Producto disponible (usalo si el pilar es PRODUCTO, sino como contexto):
- Nombre: {nombre}
- Precio: ${precio:,.0f}
- Categoría: {cat}
- Descripción: {desc}

RECORDÁ: hook OBLIGATORIO (nunca vacío), máximo 2 emojis, no empieces con emoji, variá la estructura."""

            client = anthropic.Anthropic(api_key=self.anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_prompt}]
            )

            data = self._parse_json_response(response.content[0].text)

            conn = self._contenidos_db()
            cursor = conn.cursor()

            from image_composer import compose_image
            import time as _time
            try:
                branded_url = compose_image(
                    producto_nombre=nombre,
                    producto_precio=precio,
                    producto_imagen_url=producto.get("imagen_principal", ""),
                    persona=persona,
                    pilar=pilar,
                    formato=formato,
                    hook=data.get("hook", ""),
                    output_filename=f"{formato}_{producto.get('sku', '')}_{int(_time.time())}.jpg",
                    titulo=data.get("titulo", ""),
                    puntos=data.get("puntos"),
                    numero_grande=data.get("numero_grande", ""),
                    subtexto=data.get("subtexto", ""),
                    bullets=data.get("bullets"),
                    pregunta=data.get("pregunta", ""),
                    opciones=data.get("opciones"),
                    cta_bar=data.get("cta_bar", ""),
                    emoji=data.get("emoji", ""),
                )
            except Exception:
                branded_url = producto.get("imagen_principal", "")

            cursor.execute("""
                INSERT INTO contenidos (tipo, formato, persona, producto_sku, producto_nombre,
                    producto_precio, producto_imagen, caption, caption_variante_b,
                    hashtags, hook, cta, media_url, score_esperado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fmt["tipo"], formato, persona,
                producto.get("sku", ""),
                nombre, precio,
                producto.get("imagen_principal", ""),
                data.get("caption", ""),
                data.get("caption_b", ""),
                data.get("hashtags", ""),
                data.get("hook", ""),
                data.get("cta", ""),
                branded_url,
                json.dumps({"reach_min": 500, "reach_max": 2000, "eng_min": 3, "eng_max": 5}),
            ))
            conn.commit()
            contenido_id = cursor.lastrowid

            cursor.execute("SELECT * FROM contenidos WHERE id = ?", (contenido_id,))
            result = dict(cursor.fetchone())
            conn.close()
            return result

        except json.JSONDecodeError as e:
            return {"error": f"Error parseando respuesta de Claude: {e}"}
        except Exception as e:
            return {"error": str(e)}

    def generar_lote(self, cantidad=5):
        try:
            productos_raw = self.get_productos()
            if isinstance(productos_raw, dict) and "error" in productos_raw:
                return {"error": productos_raw["error"]}

            productos = [p for p in productos_raw if p.get("stock", 0) > 0 and p.get("precio_venta", 0) > 0]
            productos.sort(key=lambda p: p.get("precio_venta", 0) * p.get("stock", 0), reverse=True)

            # Seleccionar productos top con variedad de categoría
            prods_top = []
            cat_count = {}
            for p in productos:
                cat = p.get("categoria", "General")
                if cat_count.get(cat, 0) >= 2:
                    continue
                prods_top.append(p)
                cat_count[cat] = cat_count.get(cat, 0) + 1
                if len(prods_top) >= 10:
                    break

            # Distribuir formatos según pilares: 35% edu + 30% moti + 20% eng + 15% prod
            formatos_por_pilar = {}
            for k, v in FORMATOS.items():
                pilar = v.get("pilar", "producto")
                formatos_por_pilar.setdefault(pilar, []).append(k)

            distribucion = []
            for pilar, peso in [("educativo", 35), ("motivacional", 30), ("engagement", 20), ("producto", 15)]:
                n = max(1, round(cantidad * peso / 100))
                fmts = formatos_por_pilar.get(pilar, [])
                for i in range(n):
                    if len(distribucion) >= cantidad:
                        break
                    distribucion.append(fmts[i % len(fmts)])

            distribucion = distribucion[:cantidad]
            random.shuffle(distribucion)

            resultados = []
            errores = []
            for i, fmt_key in enumerate(distribucion):
                fmt = FORMATOS[fmt_key]
                persona = fmt["persona"]
                prod = prods_top[i % len(prods_top)] if prods_top else {}

                try:
                    result = self.generar_contenido(prod, fmt_key, persona)
                    if isinstance(result, dict) and "error" in result:
                        errores.append(f"{fmt_key}: {result['error']}")
                    else:
                        resultados.append(result)
                except Exception as e:
                    errores.append(f"{fmt_key}: {e}")

            return {"ok": True, "generados": len(resultados), "contenidos": resultados, "errores": errores}

        except Exception as e:
            return {"error": str(e)}

    # ── CRUD contenidos ──

    def get_contenidos(self, estado=None):
        try:
            import base64
            conn = self._contenidos_db()
            if estado and estado != 'todos':
                rows = conn.execute("SELECT * FROM contenidos WHERE estado = ? ORDER BY creado_at DESC", (estado,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM contenidos ORDER BY creado_at DESC").fetchall()
            result = []
            for r in rows:
                d = dict(r)
                media = d.get("media_url", "")
                if media and not media.startswith("http") and not media.startswith("data:"):
                    p = Path(media)
                    if p.exists():
                        b64 = base64.b64encode(p.read_bytes()).decode()
                        d["media_url"] = f"data:image/jpeg;base64,{b64}"
                    else:
                        d["media_url"] = ""
                result.append(d)
            conn.close()
            return result
        except Exception as e:
            return {"error": str(e)}

    def aprobar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("UPDATE contenidos SET estado = 'aprobado', aprobado_at = datetime('now') WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def rechazar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("UPDATE contenidos SET estado = 'rechazado' WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def editar_contenido(self, contenido_id, cambios):
        try:
            campos_ok = {'caption', 'caption_variante_b', 'hashtags', 'hook', 'cta', 'notas_owner'}
            sets = []
            vals = []
            for k, v in cambios.items():
                if k in campos_ok:
                    sets.append(f"{k} = ?")
                    vals.append(v)
            if not sets:
                return {"error": "Sin cambios válidos"}
            vals.append(contenido_id)
            conn = self._contenidos_db()
            conn.execute(f"UPDATE contenidos SET {', '.join(sets)} WHERE id = ?", vals)
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def eliminar_contenido(self, contenido_id):
        try:
            conn = self._contenidos_db()
            conn.execute("DELETE FROM contenidos WHERE id = ?", (contenido_id,))
            conn.commit()
            conn.close()
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}


def main():
    index_path = BASE_DIR / "marketing_app" / "index.html"
    icon_path = BASE_DIR / "marketing_app" / "assets" / "icon.ico"

    webview.create_window(
        "El Gadget — Marketing",
        str(index_path),
        js_api=Api(),
        width=1400,
        height=900,
        min_size=(1100, 700),
    )
    webview.start(icon=str(icon_path) if icon_path.exists() else None)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "marketing_desktop_error.log").write_text(
            f"{e.__class__.__name__}: {e}", encoding="utf-8"
        )
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Error al iniciar Marketing El Gadget:\n\n{e}", "Error", 0x10)
