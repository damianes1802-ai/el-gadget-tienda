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

# ── Pilares y formatos de contenido Instagram ──
# Distribución: 35% educativo + 30% motivacional + 20% engagement + 15% producto
PILARES = {
    "educativo":    {"peso": 35, "desc": "Contenido de valor que enseña cómo funciona el programa de referidos y cómo ganar dinero"},
    "motivacional": {"peso": 30, "desc": "Historias de éxito, cálculos de ganancias, inspiración para empezar"},
    "engagement":   {"peso": 20, "desc": "Preguntas, encuestas, interacción con la comunidad"},
    "producto":     {"peso": 15, "desc": "Producto en acción con ángulo de referido (compartí y ganá)"},
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

    # PRODUCTO (15%) — showcase con ángulo referido
    "PR-01": {"tipo": "reel",     "pilar": "producto",     "persona": "maria", "desc": "Producto en acción: problema → solución. Al final: 'Compartilo con tu código y ganá comisión por cada venta'"},
    "PR-02": {"tipo": "carrusel", "pilar": "producto",     "persona": "sofi",  "desc": "Selección curada: 'Top 5 productos de El Gadget que se venden solos — ideales para compartir como referido'"},
    "PR-03": {"tipo": "reel",     "pilar": "producto",     "persona": "lucas", "desc": "Producto viral + código: 'Este producto está volando. Con tu código le das hasta 20% OFF a quien compre'"},
}

PERSONAS_DESC = {
    "maria": "Mamá urbana 25-40 años. Compra para la familia. Activa en grupos de WhatsApp de mamás. Valora ahorro y praticidad. Tono: cálido, cercano, de mamá a mamá.",
    "lucas": "Joven 18-34 años. Busca ingreso extra sin inversión. Activo en TikTok/IG. Le motiva el estatus y las recompensas rápidas. Tono: directo, energético, motivacional.",
    "ana":   "Profesional 35-50 años. Compras de alto ticket. Solo recomienda lo que probó. Tono: adulto, claro, sin exageraciones, profesional.",
    "sofi":  "Influencer/micro-influencer 18-45 años. Genera contenido auténtico para su audiencia. Tono: natural, instagrameable, creativo.",
    "martin":"Mayorista/revendedor 30-50 años. Piensa en márgenes. Tono: directo, con números, orientado al negocio.",
}

SYSTEM_PROMPT = """Sos el community manager de El Gadget, una tienda online argentina de productos para el hogar, moda, tecnología y más.

OBJETIVO PRINCIPAL: conseguir que más personas se registren como referidos en el programa de comisiones de El Gadget. El 80% del contenido debe aportar VALOR (educar sobre cómo ganar dinero, motivar, generar comunidad) y solo el 20% debe ser promoción directa de productos.

Datos clave del programa de referidos:
- Registrarse es gratis, sin inversión, sin stock, sin envíos
- El referido comparte su código personalizado con amigos/familia/seguidores
- Quien compra con el código obtiene 10-20% de descuento (según monto del carrito)
- El referido gana comisión: 7% (base), 11% (5+ ventas/mes), 15% (15+ ventas/mes)
- Las comisiones se cobran el día 5 de cada mes
- URL de registro: elgadget.com.ar/referidos

Reglas de tono:
- Español argentino (vos/voseo): "mirá", "registrate", "compartí"
- Cercano, directo, sin exagerar. No uses lenguaje corporativo ni de "gurú"
- NUNCA menciones "Droppers" ni ningún proveedor
- Los precios que te doy son reales y actuales
- No prometas envío gratis salvo que se indique
- No inventes testimonios ni reviews
- Emojis con moderación (1-3 por caption)
- El contenido debe sentirse natural, no un aviso publicitario

Respondé SOLAMENTE con un objeto JSON válido (sin texto adicional, sin markdown):
{"caption": "...", "caption_b": "...", "hashtags": "...", "hook": "...", "cta": "..."}

Donde:
- caption: el texto principal del post (máx 2200 caracteres para IG, ideal 150-300)
- caption_b: una variante alternativa para A/B testing
- hashtags: 8-12 hashtags relevantes separados por espacio (mezcla de populares y nicho)
- hook: las primeras 3-5 palabras impactantes que detienen el scroll
- cta: call to action final claro (1 línea, orientado a registro como referido cuando aplique)"""


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

            user_prompt = f"""Generá contenido para Instagram.

Formato: {formato} — {fmt['desc']}
Tipo: {fmt['tipo']}
Persona target: {persona.upper()} — {persona_desc}

Producto:
- Nombre: {nombre}
- Precio: ${precio:,.0f}
- Categoría: {cat}
- Descripción: {desc}

El objetivo es que quien vea este contenido quiera comprar el producto o registrarse como referido para ganar comisiones compartiéndolo."""

            client = anthropic.Anthropic(api_key=self.anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )

            data = self._parse_json_response(response.content[0].text)

            conn = self._contenidos_db()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contenidos (tipo, formato, persona, producto_sku, producto_nombre,
                    producto_precio, producto_imagen, caption, caption_variante_b,
                    hashtags, hook, cta, score_esperado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            for i, fmt_key in enumerate(distribucion):
                fmt = FORMATOS[fmt_key]
                persona = fmt["persona"]
                prod = prods_top[i % len(prods_top)] if prods_top else {}

                result = self.generar_contenido(prod, fmt_key, persona)
                if "error" not in result:
                    resultados.append(result)

            return {"ok": True, "generados": len(resultados), "contenidos": resultados}

        except Exception as e:
            return {"error": str(e)}

    # ── CRUD contenidos ──

    def get_contenidos(self, estado=None):
        try:
            conn = self._contenidos_db()
            if estado and estado != 'todos':
                rows = conn.execute("SELECT * FROM contenidos WHERE estado = ? ORDER BY creado_at DESC", (estado,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM contenidos ORDER BY creado_at DESC").fetchall()
            result = [dict(r) for r in rows]
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
