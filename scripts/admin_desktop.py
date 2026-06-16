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
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests
import webview

sys.path.append(str(Path(__file__).parent))
from utils.config import Config

API_URL = "https://el-gadget-tienda.onrender.com"
PRECIOS_CONFIG_FILE = Config.PRECIOS_DIR / "config_precios_v2.json"
CATALOGO_DB_FILE = Config.DATA_DIR / "catalogo.db"


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

    def actualizar_producto(self, sku, cambios):
        """
        Edita un producto: guarda los cambios como overrides_manuales en
        data/catalogo.db (sobreviven a la sincronizacion diaria), los aplica
        de inmediato en la tienda en vivo (Render) y sube catalogo.db a git
        para que el proximo deploy/sincronizacion no los pierda.
        """
        try:
            conn = sqlite3.connect(CATALOGO_DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return {"error": f"Producto {sku} no encontrado en catalogo.db"}

            overrides = json.loads(row['overrides_manuales']) if row['overrides_manuales'] else {}

            set_cols = []
            set_vals = []

            if 'nombre' in cambios:
                set_cols.append('nombre')
                set_vals.append(cambios['nombre'])
            if 'descripcion' in cambios:
                set_cols.append('descripcion')
                set_vals.append(cambios['descripcion'])
            if 'nombre' in cambios or 'descripcion' in cambios:
                set_cols.append('seo_optimizado_at')
                set_vals.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            for campo in ('categoria', 'precio_venta', 'stock', 'imagen_principal', 'imagenes_adicionales'):
                if campo in cambios:
                    overrides[campo] = cambios[campo]
                    set_cols.append(campo)
                    set_vals.append(cambios[campo])

            set_cols.append('overrides_manuales')
            set_vals.append(json.dumps(overrides, ensure_ascii=False))

            set_clause = ", ".join(f"{c} = ?" for c in set_cols)
            cursor.execute(f"UPDATE productos SET {set_clause} WHERE sku = ?", (*set_vals, sku))
            conn.commit()

            cursor.execute("SELECT * FROM productos WHERE sku = ?", (sku,))
            producto = dict(cursor.fetchone())
            conn.close()
        except Exception as e:
            return {"error": f"Error al guardar en catalogo.db: {e}"}

        producto['_remoto'] = self._patch(f"/api/admin/producto/{sku}", json_body=cambios)
        producto['_git'] = self._git_commit_catalogo(sku, cambios)
        return producto

    def _git_commit_catalogo(self, sku, cambios):
        try:
            repo_dir = Config.BASE_DIR
            campos = ", ".join(cambios.keys())
            mensaje = f"Editar producto {sku} desde Panel El Gadget ({campos})"

            subprocess.run(['git', 'add', 'data/catalogo.db'], cwd=repo_dir, check=True, capture_output=True)

            commit = subprocess.run(['git', 'commit', '-m', mensaje], cwd=repo_dir, capture_output=True, text=True)
            if commit.returncode != 0:
                salida = (commit.stdout + commit.stderr).lower()
                if 'nothing to commit' in salida or 'nada para hacer commit' in salida:
                    return {"ok": True, "mensaje": "Sin cambios para confirmar en git"}
                return {"error": commit.stdout + commit.stderr}

            push = subprocess.run(['git', 'push'], cwd=repo_dir, capture_output=True, text=True)
            if push.returncode != 0:
                return {"error": push.stdout + push.stderr}

            return {"ok": True, "mensaje": "Cambios confirmados y subidos a git"}
        except Exception as e:
            return {"error": str(e)}

    # ── Clientes ──
    def get_clientes(self):
        return self._get("/api/clientes", admin=True)

    def eliminar_cliente(self, cliente_id):
        return self._delete(f"/api/admin/clientes/{cliente_id}")

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

    # ── Usuarios registrados ──
    def get_usuarios(self):
        return self._get("/api/admin/usuarios", admin=True)

    def descargar_usuarios_csv(self):
        try:
            resp = requests.get(
                f"{API_URL}/api/admin/usuarios/csv",
                headers=self._headers(admin=True),
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            return {"error": str(e)}

        ruta = webview.windows[0].create_file_dialog(
            webview.SAVE_DIALOG, save_filename='usuarios_el_gadget.csv'
        )
        if not ruta:
            return {"cancelado": True}

        destino = ruta[0] if isinstance(ruta, (list, tuple)) else ruta
        try:
            with open(destino, 'wb') as f:
                f.write(resp.content)
            return {"ok": True, "ruta": destino}
        except Exception as e:
            return {"error": str(e)}

    def eliminar_usuario(self, usuario_id):
        return self._delete(f"/api/admin/usuarios/{usuario_id}")

    # ── Historial de actualizaciones diarias (redeploys) ──
    def get_historial(self):
        return self._get("/api/admin/historial", admin=True)

    # ── Descuentos y campañas promocionales ──
    def get_descuentos(self):
        return self._get("/api/admin/descuentos", admin=True)

    def guardar_descuento(self, datos):
        datos = dict(datos)
        descuento_id = datos.pop('id', None)
        if descuento_id:
            return self._patch(f"/api/admin/descuentos/{descuento_id}", json_body=datos)
        return self._post("/api/admin/descuentos", json_body=datos)

    def eliminar_descuento(self, descuento_id):
        return self._delete(f"/api/admin/descuentos/{descuento_id}")

    # ── Programa de referidos ──
    def get_referidos(self):
        return self._get("/api/admin/referidos", admin=True)

    def desactivar_referido(self, ref_id):
        return self._delete(f"/api/admin/referidos/{ref_id}")

    def eliminar_referido(self, ref_id):
        return self._post(f"/api/admin/referidos/{ref_id}/eliminar", {})

    def marcar_referido_pagado(self, ref_id, periodo):
        return self._post(f"/api/admin/referidos/{ref_id}/marcar-pagado", {"periodo": periodo})

    # ── Redeploy de precios ──
    def trigger_redeploy(self):
        env = Config.cargar_env()
        token = env.get('GITHUB_TOKEN', '')
        if not token:
            return {"error": "GITHUB_TOKEN no configurado en config/.env"}

        # Commitear y pushear el archivo de precios antes de disparar el workflow,
        # porque GitHub Actions descarga el repo — sin push usaría la versión vieja.
        base_dir = Path(__file__).parent.parent
        precios_file = str(PRECIOS_CONFIG_FILE.relative_to(base_dir))
        try:
            subprocess.run(
                ["git", "add", precios_file],
                cwd=str(base_dir), check=True, capture_output=True,
            )
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(base_dir), capture_output=True,
            )
            if result.returncode != 0:
                subprocess.run(
                    ["git", "commit", "-m", "Actualizar configuracion de precios (panel)"],
                    cwd=str(base_dir), check=True, capture_output=True,
                )
                _push_env = os.environ.copy()
                _push_env.update({
                    'GIT_CONFIG_COUNT': '1',
                    'GIT_CONFIG_KEY_0': 'http.extraheader',
                    'GIT_CONFIG_VALUE_0': f'Authorization: Bearer {token}',
                    'GIT_TERMINAL_PROMPT': '0',
                })
                subprocess.run(
                    ["git", "push", "https://github.com/damianes1802-ai/el-gadget-tienda.git", "main"],
                    cwd=str(base_dir), check=True, capture_output=True, env=_push_env,
                )
        except subprocess.CalledProcessError as e:
            return {"error": f"Git push fallido: {e.stderr.decode(errors='replace')}"}

        repo = "damianes1802-ai/el-gadget-tienda"
        workflow = "redeploy_precios.yml"
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
        try:
            resp = requests.post(
                url,
                json={"ref": "main"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=15,
            )
            if resp.status_code == 204:
                return {"ok": True}
            return {"error": f"GitHub API: {resp.status_code} {resp.text}"}
        except Exception as e:
            return {"error": str(e)}


def main():
    base_dir = Path(__file__).parent.parent
    index_path = base_dir / "admin_app" / "index.html"
    icon_path = base_dir / "admin_app" / "assets" / "icon.ico"

    webview.create_window(
        "El Gadget — Panel",
        str(index_path),
        js_api=Api(),
        width=1320,
        height=860,
        min_size=(1024, 640),
    )
    webview.start(icon=str(icon_path))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from datetime import datetime

        logs_dir = Path(__file__).parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        log_file = logs_dir / "admin_desktop_error.log"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n=== {datetime.now().isoformat()} ===\n")
            f.write(traceback.format_exc())

        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"No se pudo iniciar el Panel El Gadget.\n\nDetalles en:\n{log_file}",
                "Panel El Gadget - Error",
                0x10,  # MB_ICONERROR
            )
        except Exception:
            pass
