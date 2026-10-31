# -*- coding: utf-8 -*-
"""
SISTEMA DE INSUMOS Y PRODUCCIÓN — Así Fue Deco

Backend del control de stock de insumos y del peso/medidas de envío de los
artículos. Diseño funcional completo en `docs/ESPECIFICACION.md`.

Módulos:
    db        esquema SQLite, conexión, libro mayor y config
    calculos  funciones puras: peso de envío, conversiones, costos, alertas
    stock     motor: movimientos, descuento por venta, reproceso de pendientes
    modelos   modelos de entrada de la API
    api       FastAPI

El dato que justifica todo el sistema: el peso del paquete embalado, derivado
de los insumos de la receta en vez de pesado producto por producto.
"""

__version__ = "1.0.0"
