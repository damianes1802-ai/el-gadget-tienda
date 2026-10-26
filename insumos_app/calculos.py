# -*- coding: utf-8 -*-
"""
CÁLCULOS DEL SISTEMA DE INSUMOS — Así Fue Deco

Funciones puras, sin base de datos: reciben diccionarios y devuelven números.
Están separadas a propósito para que se puedan testear sin montar una base y
para que la API y cualquier consumidor futuro (el cotizador de Correo
Argentino, que vive en el repo de El Gadget) calculen exactamente lo mismo.

LA REGLA QUE ORDENA TODO EL MÓDULO
    El stock se guarda SIEMPRE en unidades, también para los insumos de modo
    'peso'. La conversión a kilos ocurre únicamente acá, en la capa de
    presentación. Si el stock de unos insumos estuviera en gramos y el de
    otros en unidades, cada descuento tendría que convertir y ahí se acumulan
    los errores de redondeo que después nadie puede explicar.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

MM_POR_CM = 10.0
G_POR_KG = 1000.0


# ════════════════════════════════════════════════════════════════════════════
# CONVERSIÓN STOCK ↔ UNIDAD DE PANTALLA
# ════════════════════════════════════════════════════════════════════════════

def unidad_de_pantalla(modo_stock: str) -> str:
    """En qué unidad se carga y se muestra el stock de un insumo."""
    return "kg" if modo_stock == "peso" else "unidad"


def a_unidades(cantidad: float, modo_stock: str, peso_unitario_g: float) -> float:
    """Convierte lo que se cargó en pantalla a la unidad canónica interna.

    Modo 'peso': la pantalla pide kilos y acá se vuelven unidades.
    Modo 'unidad': ya viene en unidades.
    """
    if modo_stock == "peso":
        if not peso_unitario_g or peso_unitario_g <= 0:
            raise ValueError(
                "peso_unitario_g debe ser mayor que cero para convertir kilos a unidades"
            )
        return (float(cantidad) * G_POR_KG) / float(peso_unitario_g)
    return float(cantidad)


def desde_unidades(unidades: float, modo_stock: str, peso_unitario_g: float) -> float:
    """Convierte la unidad canónica interna a la unidad de pantalla."""
    if modo_stock == "peso":
        if not peso_unitario_g or peso_unitario_g <= 0:
            raise ValueError(
                "peso_unitario_g debe ser mayor que cero para convertir unidades a kilos"
            )
        return (float(unidades) * float(peso_unitario_g)) / G_POR_KG
    return float(unidades)


def stock_para_pantalla(insumo: Dict[str, Any]) -> Dict[str, Any]:
    """Bloque de stock listo para mostrar, en las dos unidades.

    Se devuelven ambas porque la pantalla de un insumo de modo 'peso' muestra
    kilos pero la receta se expresa en unidades: el socio necesita ver que
    "2,5 kg" son "1.000 caireles" para saber si le alcanzan.
    """
    modo = insumo["modo_stock"]
    peso_unitario = float(insumo["peso_unitario_g"])
    unidades = float(insumo.get("stock_unidades") or 0.0)

    return {
        "unidades": round(unidades, 4),
        "modo_stock": modo,
        "unidad_pantalla": unidad_de_pantalla(modo),
        "cantidad_pantalla": round(desde_unidades(unidades, modo, peso_unitario), 4),
        "kg": round((unidades * peso_unitario) / G_POR_KG, 4),
    }


# ════════════════════════════════════════════════════════════════════════════
# ALERTAS DE STOCK BAJO
# ════════════════════════════════════════════════════════════════════════════

def umbral_en_unidades(insumo: Dict[str, Any]) -> float:
    """El "avisar cuando queden N" convertido a la unidad canónica.

    El umbral se carga en la unidad del modo de stock (kilos para un insumo de
    modo 'peso'), así que hay que convertirlo antes de compararlo contra
    `stock_unidades`.
    """
    return a_unidades(
        float(insumo.get("alerta_cuando_queden") or 0.0),
        insumo["modo_stock"],
        float(insumo["peso_unitario_g"]),
    )


def en_alerta(insumo: Dict[str, Any], stock_unidades: Optional[float] = None) -> bool:
    """¿Este insumo está en o por debajo de su umbral?

    Un umbral en 0 no alerta nunca por "quedar poco", pero un stock negativo
    sí: significa que se vendió material que no estaba cargado, y eso hay que
    verlo aunque el socio no haya definido umbral.
    """
    umbral = umbral_en_unidades(insumo)
    stock = float(insumo.get("stock_unidades") or 0.0) if stock_unidades is None else float(stock_unidades)

    if stock < 0:
        return True
    if umbral <= 0:
        return False
    return stock <= umbral


def describir_alerta(insumo: Dict[str, Any]) -> Dict[str, Any]:
    """Alerta lista para mostrar o mandar, en la unidad que usa el socio."""
    modo = insumo["modo_stock"]
    peso_unitario = float(insumo["peso_unitario_g"])
    stock = float(insumo.get("stock_unidades") or 0.0)
    unidad = unidad_de_pantalla(modo)

    return {
        "insumo_id": insumo["id"],
        "nombre": insumo["nombre"],
        "stock_unidades": round(stock, 4),
        "stock_pantalla": round(desde_unidades(stock, modo, peso_unitario), 4),
        "umbral_pantalla": round(float(insumo.get("alerta_cuando_queden") or 0.0), 4),
        "unidad": unidad,
        "stock_negativo": stock < 0,
    }


# ════════════════════════════════════════════════════════════════════════════
# PESO Y MEDIDAS DE ENVÍO
# ════════════════════════════════════════════════════════════════════════════

def peso_insumos_g(receta: Iterable[Dict[str, Any]]) -> float:
    """Suma el peso de los insumos de la receta, sin margen de embalaje.

    Cada ítem necesita `cantidad` y `peso_unitario_g`.
    """
    return sum(
        float(item["cantidad"]) * float(item["peso_unitario_g"]) for item in receta
    )


def medidas_base_mm(articulo: Dict[str, Any]) -> Tuple[float, float, float]:
    """Las medidas desde las que se cotiza, antes del margen.

    El caso de la guirnalda: mide 2 metros y ese dato se conserva porque sirve
    para la ficha del producto, pero se embala doblada en cinco y queda un
    cuadrado de 25×25. El envío se cotiza con el cuadrado.
    """
    if articulo.get("se_embala_doblado"):
        return (
            float(articulo["largo_emb_mm"]),
            float(articulo["ancho_emb_mm"]),
            float(articulo["alto_emb_mm"]),
        )
    return (
        float(articulo["largo_real_mm"]),
        float(articulo["ancho_real_mm"]),
        float(articulo["alto_real_mm"]),
    )


def calcular_envio(
    articulo: Dict[str, Any],
    receta: Iterable[Dict[str, Any]],
    margen: Optional[float] = None,
) -> Dict[str, Any]:
    """Peso y medidas del paquete ya embalado. Es la razón de ser del sistema.

        peso_envio_g  = Σ(cantidad × peso_unitario_g) × margen
        medidas_envio = (dobladas si se embala doblado, si no reales) × margen

    Se devuelven milímetros y centímetros: el milímetro es la unidad canónica
    del modelo y el centímetro es con el que cotiza Correo Argentino.

    `volumen_cm3` va incluido porque Correo cobra por peso volumétrico cuando
    el paquete es voluminoso y liviano, que es exactamente el caso de una
    guirnalda, y porque deja ver el efecto del margen: 1,05 por dimensión
    infla el volumen 15,8%, no 5%.

    `receta_incompleta` avisa que el peso calculado NO sirve para cotizar: sin
    receta la suma da 0 y un 0 que parece un peso es peor que un error.
    """
    items = list(receta)
    factor = float(margen if margen is not None else articulo.get("margen_embalaje") or 1.0)

    bruto_g = peso_insumos_g(items)
    peso_g = bruto_g * factor

    largo, ancho, alto = medidas_base_mm(articulo)
    largo_e, ancho_e, alto_e = largo * factor, ancho * factor, alto * factor

    return {
        "peso_insumos_g": round(bruto_g, 3),
        "peso_envio_g": round(peso_g, 3),
        # 6 decimales = miligramos, la misma precisión que `peso_envio_g`.
        # Con 4 decimales se perdía hasta medio gramo por artículo, y el peso
        # es justo el dato que este sistema existe para dar bien.
        "peso_envio_kg": round(peso_g / G_POR_KG, 6),
        "margen_embalaje": factor,
        "se_embala_doblado": bool(articulo.get("se_embala_doblado")),
        "largo_envio_mm": round(largo_e, 2),
        "ancho_envio_mm": round(ancho_e, 2),
        "alto_envio_mm": round(alto_e, 2),
        "largo_envio_cm": round(largo_e / MM_POR_CM, 2),
        "ancho_envio_cm": round(ancho_e / MM_POR_CM, 2),
        "alto_envio_cm": round(alto_e / MM_POR_CM, 2),
        "volumen_cm3": round((largo_e * ancho_e * alto_e) / (MM_POR_CM ** 3), 2),
        "insumos_en_receta": len(items),
        "receta_incompleta": len(items) == 0,
    }


# ════════════════════════════════════════════════════════════════════════════
# COSTOS DERIVADOS
# ════════════════════════════════════════════════════════════════════════════

def costos_derivados(insumo: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Costo por unidad, por 100 g y por kg, a partir de cómo se compra.

    El socio compra caireles por kilo y cintas por unidad, pero necesita
    comparar: cuánto le sale un cairel suelto y cuánto le saldría el kilo de
    algo que compra por unidad.

    Devuelve None si el insumo no tiene costo cargado, en vez de un cero que
    se confundiría con "es gratis".
    """
    costo = insumo.get("costo_compra")
    unidad = insumo.get("unidad_compra")
    peso_unitario = float(insumo.get("peso_unitario_g") or 0.0)

    if costo is None or not unidad or peso_unitario <= 0:
        return None

    costo = float(costo)
    if unidad == "kg":
        por_kg = costo
        por_unidad = costo * peso_unitario / G_POR_KG
    else:
        por_unidad = costo
        por_kg = costo * G_POR_KG / peso_unitario

    return {
        "costo_por_unidad": round(por_unidad, 4),
        "costo_por_100g": round(por_kg / 10.0, 4),
        "costo_por_kg": round(por_kg, 4),
    }


# ════════════════════════════════════════════════════════════════════════════
# CONSUMO DE UNA VENTA
# ════════════════════════════════════════════════════════════════════════════

def consumo_de_receta(
    receta: Iterable[Dict[str, Any]], cantidad_vendida: float
) -> List[Dict[str, Any]]:
    """Cuántas unidades de cada insumo consume vender `cantidad_vendida`.

    Devuelve cantidades NEGATIVAS, que es como entran al libro mayor: la suma
    de la columna del libro mayor tiene que dar el stock, así que un egreso no
    puede guardarse en positivo con el signo "implícito" en el tipo.
    """
    consumo = []
    for item in receta:
        consumo.append(
            {
                "insumo_id": item["insumo_id"],
                "cantidad_unidades": -(float(item["cantidad"]) * float(cantidad_vendida)),
            }
        )
    return consumo
