# -*- coding: utf-8 -*-
"""
MODELOS DE ENTRADA DE LA API — Así Fue Deco

Pydantic sin validadores a propósito, igual que `scripts/api_local.py`: tipos
y defaults, y las reglas de negocio validadas en el motor, que es el único
lugar donde valen para todos los caminos (API, carga manual, sincronización de
Mercado Libre).

`campos_enviados()` existe porque el proyecto corre con dos versiones de
pydantic: la 2.x en la máquina de desarrollo y la que arrastre
`fastapi==0.104.1` en Render y en CI. El nombre del método para "dame solo los
campos que el cliente mandó" cambió entre una y otra.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


def campos_enviados(modelo: BaseModel) -> Dict[str, Any]:
    """Solo los campos que el cliente mandó, para los PUT parciales.

    Distingue "no lo mandé" de "lo mandé en null", que es la diferencia entre
    dejar un costo como estaba y borrarlo.
    """
    if hasattr(modelo, "model_dump"):
        return modelo.model_dump(exclude_unset=True)
    return modelo.dict(exclude_unset=True)  # pydantic 1.x


# ════════════════════════════════════════════════════════════════════════════
# TAXONOMÍA
# ════════════════════════════════════════════════════════════════════════════

class CategoriaIn(BaseModel):
    nombre: str
    orden: int = 0


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    orden: Optional[int] = None


class SubcategoriaIn(BaseModel):
    categoria_id: int
    nombre: str
    orden: int = 0


class SubcategoriaUpdate(BaseModel):
    categoria_id: Optional[int] = None
    nombre: Optional[str] = None
    orden: Optional[int] = None


# ════════════════════════════════════════════════════════════════════════════
# INSUMOS
# ════════════════════════════════════════════════════════════════════════════

class InsumoIn(BaseModel):
    """Alta de insumo.

    `modo_stock` es 'peso' o 'unidad' y dice cómo se cuenta, no qué es el
    insumo (eso lo dicen categoría y subcategoría).

    `peso_unitario_g` es obligatorio SIEMPRE, también en modo 'peso': es el
    puente entre los kilos que se compran y las unidades que pide la receta, y
    sin él no hay peso de envío.

    `alerta_cuando_queden` y `stock_inicial` se expresan en la unidad del modo
    de stock (kilos si el modo es 'peso').
    """
    nombre: str
    modo_stock: str
    peso_unitario_g: float
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    largo_mm: Optional[float] = None
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    alerta_cuando_queden: float = 0
    costo_compra: Optional[float] = None
    unidad_compra: Optional[str] = None
    activo: bool = True
    stock_inicial: Optional[float] = None
    usuario: Optional[str] = None


class InsumoUpdate(BaseModel):
    """Edición de insumo. No incluye el stock a propósito.

    El stock solo cambia por un movimiento del libro mayor: se toca con
    `POST /api/insumos/{id}/stock` o `POST /api/movimientos`. Si se pudiera
    editar acá, `stock_unidades` dejaría de ser reconstruible desde los
    movimientos y la auditoría perdería sentido.
    """
    nombre: Optional[str] = None
    modo_stock: Optional[str] = None
    peso_unitario_g: Optional[float] = None
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    largo_mm: Optional[float] = None
    ancho_mm: Optional[float] = None
    alto_mm: Optional[float] = None
    alerta_cuando_queden: Optional[float] = None
    costo_compra: Optional[float] = None
    unidad_compra: Optional[str] = None
    activo: Optional[bool] = None


class StockIn(BaseModel):
    """Conteo de inventario: deja el stock en un valor absoluto.

    El sistema calcula la diferencia contra lo que tenía y asienta ESA
    diferencia como movimiento.
    """
    cantidad: float
    en_unidades: bool = False
    usuario: Optional[str] = None
    nota: Optional[str] = None


class MovimientoIn(BaseModel):
    """Movimiento manual: ingreso, merma, ajuste o devolución.

    El signo lo determina el tipo, salvo en 'ajuste', que acepta el delta con
    signo. `cantidad` viene en la unidad de pantalla del insumo salvo que
    `en_unidades` sea true.
    """
    insumo_id: int
    cantidad: float
    tipo: str
    en_unidades: bool = False
    usuario: Optional[str] = None
    nota: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# ARTÍCULOS Y RECETAS
# ════════════════════════════════════════════════════════════════════════════

class ArticuloIn(BaseModel):
    """Alta de artículo.

    Las tres medidas reales son obligatorias: Correo Argentino cotiza con peso
    volumétrico y topes de tamaño, y con dos dimensiones no se puede cotizar.

    Si `se_embala_doblado` es true, las tres medidas embaladas pasan a ser
    obligatorias y son las que se usan para el envío. Las reales se conservan
    igual, porque son las que describen el producto en la ficha.

    `margen_embalaje` en null toma el default configurable del sistema (1,05).
    """
    nombre: str
    largo_real_mm: float
    ancho_real_mm: float
    alto_real_mm: float
    sku_afd: Optional[str] = None
    sku_elgadget: Optional[str] = None
    id_empretienda: Optional[str] = None
    se_embala_doblado: bool = False
    largo_emb_mm: Optional[float] = None
    ancho_emb_mm: Optional[float] = None
    alto_emb_mm: Optional[float] = None
    margen_embalaje: Optional[float] = None
    activo: bool = True


class ArticuloUpdate(BaseModel):
    nombre: Optional[str] = None
    largo_real_mm: Optional[float] = None
    ancho_real_mm: Optional[float] = None
    alto_real_mm: Optional[float] = None
    sku_afd: Optional[str] = None
    sku_elgadget: Optional[str] = None
    id_empretienda: Optional[str] = None
    se_embala_doblado: Optional[bool] = None
    largo_emb_mm: Optional[float] = None
    ancho_emb_mm: Optional[float] = None
    alto_emb_mm: Optional[float] = None
    margen_embalaje: Optional[float] = None
    activo: Optional[bool] = None


class RecetaItemIn(BaseModel):
    """Una línea de receta. `cantidad` siempre en UNIDADES del insumo.

    También para un insumo de modo 'peso': la receta dice "3 caireles", no
    "7,5 gramos de caireles". Es lo que permite que el descuento sea una resta
    sin conversiones.
    """
    insumo_id: int
    cantidad: float


class RecetaIn(BaseModel):
    """Receta completa: reemplaza la que haya."""
    items: List[RecetaItemIn]


# ════════════════════════════════════════════════════════════════════════════
# MAPEO DE CANAL
# ════════════════════════════════════════════════════════════════════════════

class MapeoIn(BaseModel):
    """Qué publicación de qué canal corresponde a qué artículo.

    `id_externo` es el identificador de la PUBLICACIÓN (el `item_id` de
    Mercado Libre, el SKU de El Gadget), no el de la orden. Una publicación
    con variantes necesita una fila por variante; si se deja
    `variacion_externa` vacío, el mapeo cubre todas las variantes.
    """
    articulo_id: int
    canal: str
    id_externo: str
    variacion_externa: str = ""


# ════════════════════════════════════════════════════════════════════════════
# VENTAS
# ════════════════════════════════════════════════════════════════════════════

class VentaItemIn(BaseModel):
    """Un ítem vendido.

    El artículo se identifica con `articulo_id` (venta manual) o con
    `id_externo_item` + `variacion_externa` para que lo resuelva el mapeo.
    """
    cantidad: float
    articulo_id: Optional[int] = None
    id_externo_item: Optional[str] = None
    variacion_externa: str = ""


class VentaIn(BaseModel):
    """Una venta a procesar.

    `id_externo` es el identificador de la ORDEN en el canal y es la clave de
    idempotencia: dos llamadas con el mismo `(canal, id_externo)` descuentan
    una sola vez. Para una venta manual sirve cualquier identificador estable
    (por ejemplo `manual-2026-10-26-01`).
    """
    canal: str
    id_externo: str
    items: List[VentaItemIn]
    fecha_venta: Optional[str] = None
    usuario: Optional[str] = None
    nota: Optional[str] = None


class LoteVentasIn(BaseModel):
    """Varias ventas de una. Cada una se procesa por separado."""
    ventas: List[VentaIn]
    usuario: Optional[str] = None


class CancelacionIn(BaseModel):
    """Cancelación de una venta: restituye lo que había descontado.

    `registrar_si_no_existe` deja constancia de la cancelación de una orden
    que este sistema nunca procesó. Está en False por defecto para que un id
    mal tipeado no cree una fila fantasma; un sincronizador, donde el id lo
    pone el canal, conviene que lo mande en True.
    """
    motivo: Optional[str] = None
    usuario: Optional[str] = None
    registrar_si_no_existe: bool = False


class CancelacionLoteItemIn(BaseModel):
    canal: str
    id_externo: str
    motivo: Optional[str] = None
    usuario: Optional[str] = None


class LoteCancelacionesIn(BaseModel):
    """Varias cancelaciones de una.

    Para un sincronizador que relee el estado de órdenes que ya conoce: se le
    pasa la lista de las que el canal ahora reporta canceladas, y la misma
    lista se puede volver a pasar sin consecuencias.
    """
    cancelaciones: List[CancelacionLoteItemIn]
    usuario: Optional[str] = None
    registrar_si_no_existe: bool = True


# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

class ConfigIn(BaseModel):
    valor: Optional[str] = None
