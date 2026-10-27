# -*- coding: utf-8 -*-
"""
MONTAJE DE LA INTERFAZ WEB — Así Fue Deco

La interfaz vive en `insumos_app/web/` (HTML, CSS y JS a mano, sin framework
ni paso de compilación) y la sirve ESTA MISMA app de FastAPI, en `/app/`.

POR QUÉ EL MISMO PROCESO Y NO UN SERVIDOR APARTE
    Un solo origen significa que el navegador no necesita CORS, que no hay
    una `API_URL` que configurar en el front —la trampa que en El Gadget dejó
    534 corridas de nurturing en verde sin hacer nada— y que desplegar es
    desplegar una cosa. El front pega a rutas relativas (`../api/...`) y
    funciona igual en `localhost:8010` que en Render, sin tocar nada.

POR QUÉ EN `/app/` Y NO EN LA RAÍZ
    `GET /` devuelve el JSON de salud del sistema y hay un test que lo
    verifica. Montar la interfaz ahí lo rompería.

Este módulo no tiene reglas de negocio: solo expone los archivos.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent / "web"
RUTA = "/app"


def montar_interfaz(app: FastAPI, ruta: str = RUTA) -> bool:
    """Monta `insumos_app/web/` en `ruta`. Devuelve si pudo.

    `html=True` hace que `/app/` sirva `index.html`, que es todo lo que hace
    falta: la interfaz es una sola página y el ruteo entre pantallas ocurre en
    el navegador, sin rutas del servidor que mantener en dos lados.

    Si la carpeta no está (un despliegue que solo quiera la API), no falla:
    devuelve False y la API arranca igual.
    """
    if not WEB_DIR.is_dir():
        return False
    app.mount(ruta, StaticFiles(directory=str(WEB_DIR), html=True), name="interfaz")
    return True
