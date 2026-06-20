#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARKETING EL GADGET — consola de métricas

Ventana nativa (pywebview) que carga marketing_app/index.html y expone una API
Python (clase Api) de solo lectura vía window.pywebview.api.*. Consume los
mismos endpoints admin de la API de Render que usa el Panel El Gadget.
"""

import json
import sys
from pathlib import Path

import requests
import webview

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

API_URL = "https://el-gadget-tienda.onrender.com"
MARKETING_CONFIG_FILE = Path(__file__).parent.parent / "marketing_app" / "config.json"


class Api:
    def __init__(self):
        env = Config.cargar_env()
        self.admin_password = env.get('ADMIN_PASSWORD', 'admin2024')

    def _headers(self):
        return {"X-Admin-Password": self.admin_password}

    def _get(self, path, params=None):
        try:
            resp = requests.get(f"{API_URL}{path}", params=params, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ── Data fetching (solo lectura) ──

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


def main():
    base_dir = Path(__file__).parent.parent
    index_path = base_dir / "marketing_app" / "index.html"
    icon_path = base_dir / "marketing_app" / "assets" / "icon.ico"

    window = webview.create_window(
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
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "marketing_desktop_error.log").write_text(
            f"{e.__class__.__name__}: {e}", encoding="utf-8"
        )
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Error al iniciar Marketing El Gadget:\n\n{e}", "Error", 0x10)
