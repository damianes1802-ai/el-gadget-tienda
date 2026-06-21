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

# ── Formatos de contenido Instagram ──
FORMATOS = {
    "RS-01": {"tipo": "reel",     "persona": "maria", "desc": "Problema → Solución: mostrar cómo el producto resuelve un problema cotidiano"},
    "RS-02": {"tipo": "story",    "persona": "maria", "desc": "Antes/Después: transformación visual con el producto"},
    "RS-03": {"tipo": "reel",     "persona": "lucas", "desc": "Unboxing/Haul: abrir paquete, mostrar productos, reacción auténtica"},
    "RS-04": {"tipo": "reel",     "persona": "lucas", "desc": "Storytime 'Así gano plata': contar cómo se gana dinero recomendando"},
    "RS-05": {"tipo": "reel",     "persona": "lucas", "desc": "Producto viral + código: mostrar producto trending con código de descuento"},
    "RS-06": {"tipo": "story",    "persona": "maria", "desc": "Testimonio: captura de chat o review real de un cliente"},
    "RS-07": {"tipo": "carrusel", "persona": "maria", "desc": "FAQ visual: responder preguntas frecuentes en slides"},
    "RS-08": {"tipo": "post",     "persona": "sofi",  "desc": "Selección curada: 'Mi top 5 de El Gadget para tu hogar'"},
}

PERSONAS_DESC = {
    "maria": "Mamá urbana 25-40 años. Compra para la familia. Activa en grupos de WhatsApp de mamás. Valora ahorro y praticidad. Tono: cálido, cercano, de mamá a mamá.",
    "lucas": "Joven 18-34 años. Busca ingreso extra sin inversión. Activo en TikTok/IG. Le motiva el estatus y las recompensas rápidas. Tono: directo, energético, motivacional.",
    "ana":   "Profesional 35-50 años. Compras de alto ticket. Solo recomienda lo que probó. Tono: adulto, claro, sin exageraciones, profesional.",
    "sofi":  "Influencer/micro-influencer 18-45 años. Genera contenido auténtico para su audiencia. Tono: natural, instagrameable, creativo.",
    "martin":"Mayorista/revendedor 30-50 años. Piensa en márgenes. Tono: directo, con números, orientado al negocio.",
}

SYSTEM_PROMPT = """Sos el community manager de El Gadget, una tienda online argentina de productos para el hogar, moda, tecnología y más.

Tu objetivo principal: atraer referidos al programa de comisiones de El Gadget. Cada pieza de contenido debe motivar a la audiencia a registrarse como referido o a comprar usando un código de referido.

Reglas:
- Usá español argentino (vos/voseo): "mirá", "comprá", "registrate"
- Tono cercano, directo, sin exagerar. No uses lenguaje corporativo.
- NUNCA menciones "Droppers" ni ningún proveedor
- Los precios que te doy son reales y actuales
- Descuento para compradores con código de referido: 10-20% según monto del carrito
- Comisión para referidos: 7% a 15% según cantidad de ventas en el mes
- No prometas envío gratis salvo que se indique explícitamente
- No inventes testimonios ni reviews
- Usá emojis con moderación (1-3 por caption)

Respondé SOLAMENTE con un objeto JSON válido (sin texto adicional, sin markdown):
{"caption": "...", "caption_b": "...", "hashtags": "...", "hook": "...", "cta": "..."}

Donde:
- caption: el texto principal del post (máx 300 caracteres)
- caption_b: una variante alternativa para A/B testing (máx 300 caracteres)
- hashtags: 8-12 hashtags relevantes separados por espacio
- hook: las primeras 3-5 palabras impactantes (para Reels)
- cta: call to action final (1 línea)"""


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

            # Máximo 2 por categoría
            seleccionados = []
            cat_count = {}
            for p in productos:
                cat = p.get("categoria", "General")
                if cat_count.get(cat, 0) >= 2:
                    continue
                seleccionados.append(p)
                cat_count[cat] = cat_count.get(cat, 0) + 1
                if len(seleccionados) >= cantidad:
                    break

            formatos_keys = list(FORMATOS.keys())
            resultados = []

            for i, prod in enumerate(seleccionados):
                fmt_key = formatos_keys[i % len(formatos_keys)]
                fmt = FORMATOS[fmt_key]
                persona = fmt["persona"]

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
