#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PANEL EL GADGET — aplicación de escritorio

Ventana nativa (pywebview) que carga admin_app/index.html y expone una API
Python (clase Api) vía window.pywebview.api.*. El frontend nunca habla
directo con Render: todo pasa por estos métodos, que usan requests + la
contraseña admin de config/.env.

Datos de productos/órdenes/clientes/etc: API de Render (el-gadget-tienda).
Configuración de precios: archivo local data/precios/config_precios_v2.json
(mismo que usa 04_calculo_precios.py / config_precios_interactivo.py).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests
import webview

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

API_URL = "https://el-gadget-tienda.onrender.com"
PRECIOS_CONFIG_FILE = Config.PRECIOS_DIR / "config_precios_v2.json"


class Api:
    def __init__(self):
        env = Config.cargar_env()
        self.admin_password = env.get('ADMIN_PASSWORD', 'admin2024')

    def _headers(self, admin=False):
        return {"X-Admin-Password": self.admin_password} if admin else {}

    def _get(self, path, params=None, admin=False):
        try:
            resp = requests.get(f"{API_URL}{path}", params=params, headers=self._headers(admin), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _patch(self, path, json_body=None, params=None, admin=True):
        try:
            resp = requests.patch(f"{API_URL}{path}", json=json_body, params=params, headers=self._headers(admin), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _post(self, path, json_body=None, admin=True):
        try:
            resp = requests.post(f"{API_URL}{path}", json=json_body, headers=self._headers(admin), timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _delete(self, path, admin=True):
        try:
            resp = requests.delete(f"{API_URL}{path}", headers=self._headers(admin), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ── Estadísticas ──
    def get_estadisticas(self):
        return self._get("/api/estadisticas")

    # ── Pedidos ──
    def get_ordenes(self, estado=None):
        params = {"limit": 200}
        if estado:
            params["estado"] = estado
        return self._get("/api/ordenes", params=params)

    def get_orden(self, orden_id):
        return self._get(f"/api/orden/{orden_id}")

    def actualizar_tracking(self, orden_id, tracking_url):
        return self._patch(f"/api/orden/{orden_id}/tracking", json_body={"tracking_url": tracking_url})

    def cambiar_estado_orden(self, orden_id, estado):
        return self._patch(f"/api/orden/{orden_id}/estado", params={"estado": estado}, admin=False)

    def eliminar_orden(self, orden_id):
        return self._delete(f"/api/orden/{orden_id}")

    def procesar_pago(self, orden_id):
        return self._post(f"/api/admin/orden/{orden_id}/procesar-pago")

    # ── Productos ──
    def get_productos(self, categoria=None, search=None, incluir_agotados=False):
        params = {"limit": 1000, "incluir_agotados": str(bool(incluir_agotados)).lower()}
        if categoria:
            params["categoria"] = categoria
        if search:
            params["search"] = search
        return self._get("/api/productos", params=params)

    def get_categorias(self):
        return self._get("/api/categorias")

    # ── Clientes ──
    def get_clientes(self):
        return self._get("/api/clientes", admin=True)

    # ── Arrepentimientos ──
    def get_arrepentimientos(self):
        return self._get("/api/arrepentimientos", admin=True)

    def actualizar_estado_arrepentimiento(self, solicitud_id, estado):
        return self._patch(f"/api/arrepentimiento/{solicitud_id}/estado", params={"estado": estado})

    # ── Precios ──
    def get_precios_config(self):
        try:
            with open(PRECIOS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}

    def guardar_precios_config(self, perfil_default):
        try:
            with open(PRECIOS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)

            config['perfiles_precio']['default'].update({
                'margen_porcentaje': perfil_default['margen_porcentaje'],
                'cargos_fijos': perfil_default['cargos_fijos'],
                'redondeo': perfil_default['redondeo'],
            })
            config['fecha_actualizacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            config.setdefault('historial_cambios', []).append({
                'fecha': datetime.now().isoformat(),
                'usuario': 'panel_escritorio',
                'cambio': 'Perfil editado: Estándar',
                'perfil_modificado': 'default',
            })

            with open(PRECIOS_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}


def main():
    base_dir = Path(__file__).parent.parent
    index_path = base_dir / "admin_app" / "index.html"

    webview.create_window(
        "El Gadget — Panel",
        str(index_path),
        js_api=Api(),
        width=1320,
        height=860,
        min_size=(1024, 640),
    )
    webview.start()


if __name__ == "__main__":
    main()
