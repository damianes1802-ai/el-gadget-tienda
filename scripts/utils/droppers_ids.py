# -*- coding: utf-8 -*-
"""Identidad de productos de Droppers por ID numérico.

Droppers (Magento) reusa los slugs de URL: `body-para-bebes-de-algodon-1.html`
fue WH7167-66BL y hoy sirve WH7167-1-73BL. Cualquier verificación por URL
"bonita" termina mirando otro producto, y el listado /productos.html y las
categorías no muestran todo (hay productos que solo existen por
/catalog/product/view/id/N/). Lo único estable es el ID. Este módulo
mantiene el mapa sku → id (data/droppers_ids.json, versionado) y da la URL
canónica por id.
"""
import json
import re
from pathlib import Path
from typing import Dict, Optional

from utils.config import Config

BASE_URL = "https://droppers.com.ar"
IDS_FILE = Config.DATA_DIR / "droppers_ids.json"
# URLs (por id) que el scraper de Fase 1 tiene que visitar además del listado:
# productos nuevos descubiertos por id y productos en stock que no aparecen
# en /productos.html. Lo escribe 17_deteccion_agotados_robusto.py.
URLS_EXTRA_FILE = Config.DATA_DIR / "droppers_urls_extra.json"

_RE_ID = [
    re.compile(r'<input[^>]+name="product"[^>]+value="(\d+)"'),
    re.compile(r'data-product-id="(\d+)"'),
    re.compile(r'"productId"\s*:\s*"?(\d+)'),
]


def cargar() -> Dict[str, int]:
    if not IDS_FILE.exists():
        return {}
    try:
        return {k: int(v) for k, v in json.loads(IDS_FILE.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def guardar(mapa: Dict[str, int]) -> None:
    IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    IDS_FILE.write_text(json.dumps(dict(sorted(mapa.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def url_por_id(pid: int) -> str:
    return f"{BASE_URL}/catalog/product/view/id/{int(pid)}/"


def es_url_por_id(url: str) -> bool:
    return bool(re.search(r"/catalog/product/view/id/\d+", url or ""))


def extraer_id(html: str) -> Optional[int]:
    """ID de producto a partir del HTML de su ficha (form de carrito)."""
    for rx in _RE_ID:
        m = rx.search(html or "")
        if m:
            return int(m.group(1))
    return None


def leer_ficha(session, url: str, timeout: int = 20) -> dict:
    """Lee una ficha de Droppers y devuelve {http, sku, id, disponible}.
    `disponible` es None si no se pudo determinar (no se toca nada en ese caso)."""
    from bs4 import BeautifulSoup
    r = session.get(url, timeout=timeout, allow_redirects=True)
    out = {"http": r.status_code, "sku": None, "id": None, "disponible": None}
    if r.status_code != 200 or "product-info-main" not in r.text:
        if r.status_code == 404:
            out["disponible"] = False
        return out
    soup = BeautifulSoup(r.content, "html.parser")
    el = soup.select_one("div.product.attribute.sku .value") or soup.find("meta", {"itemprop": "sku"}) or soup.select_one("[itemprop=sku]")
    if el is not None:
        out["sku"] = re.sub(r"\s+", "-", (el.get("content") if el.name == "meta" else el.get_text(strip=True)) or "").strip()
    out["id"] = extraer_id(r.text)
    stock_el = soup.select_one(".stock")
    if stock_el is not None:
        out["disponible"] = "unavailable" not in (stock_el.get("class") or [])
    else:
        btn = soup.select_one("#product-addtocart-button")
        if btn is not None:
            out["disponible"] = not btn.has_attr("disabled")
    return out


def cargar_urls_extra() -> list:
    if not URLS_EXTRA_FILE.exists():
        return []
    try:
        return list(json.loads(URLS_EXTRA_FILE.read_text(encoding="utf-8")))
    except Exception:
        return []


def guardar_urls_extra(urls: list) -> None:
    URLS_EXTRA_FILE.parent.mkdir(parents=True, exist_ok=True)
    URLS_EXTRA_FILE.write_text(json.dumps(sorted(set(urls)), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
