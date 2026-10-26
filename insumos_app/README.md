# Sistema de Insumos y Producción — Así Fue Deco

Backend del control de stock de insumos y del **peso y las medidas de envío** de los
artículos del socio. El diseño funcional completo y acordado está en
[`docs/ESPECIFICACION.md`](docs/ESPECIFICACION.md), que es la fuente de verdad.

Para qué existe, en una línea: El Gadget necesita cobrar el envío real de Correo Argentino
en el checkout, hace falta el peso del paquete embalado, y ese dato no existe — así que se
**deriva de los insumos de la receta** en vez de pesar producto por producto.

---

## Cómo correrlo

```bash
python -m insumos_app.api
```

Desde la raíz del repo. Levanta en `http://localhost:8010`, con las docs interactivas en
`/docs`. La base se crea sola en `data/insumos.db` (gitignoreada) la primera vez.

Tests:

```bash
python -m pytest insumos_app/tests -q
```

138 tests, sin tocar ninguna base real: cada uno corre sobre un SQLite temporal. Todos los
datos de ejemplo son inventados — **el repositorio es público y el costo y el stock del
socio son datos comerciales suyos**.

### Variables de entorno

| Variable | Para qué |
|---|---|
| `INSUMOS_PASSWORD` | Secreto del header `X-Insumos-Password`. **Si no está, la API responde SIN autenticación** y lo avisa al arrancar. |
| `INSUMOS_DB_PATH` | Apunta la base a otro archivo. Sin esto, `data/insumos.db`. |

Se leen de `config/.env` o del entorno del sistema (en Render no hay `config/.env`).

---

## Los módulos

| Archivo | Qué tiene |
|---|---|
| `db.py` | Esquema SQLite, conexión, transacciones, el libro mayor y la config |
| `calculos.py` | Funciones **puras**: peso de envío, conversiones de unidad, costos, alertas |
| `stock.py` | El motor: movimientos, descuento por venta, reproceso de pendientes |
| `modelos.py` | Modelos de entrada de la API |
| `api.py` | FastAPI. Cáscara delgada: no tiene reglas de negocio propias |

Las reglas viven en `calculos.py` y `stock.py` y **no se duplican en la API**, por el mismo
motivo por el que la lógica de campañas de El Gadget vive en `utils/campanas.py`: la carga
manual, la sincronización de Mercado Libre y la interfaz web tienen que calcular lo mismo.

---

## Las cuatro propiedades de las que depende que el stock no mienta

**1. El stock se guarda siempre en unidades.** También para un insumo de modo `peso`: la
pantalla pide kilos y la conversión ocurre solo en la presentación, usando
`peso_unitario_g`. Las recetas se expresan en unidades ("lleva 3 caireles"), así que el
descuento es una resta sin conversiones y no acumula errores de redondeo.

**2. `movimiento_stock` es el libro mayor.** `insumo.stock_unidades` **nunca** se escribe a
mano: `db.recalcular_stock()` lo reescribe como la suma de los movimientos del insumo. La
invariante "stock == Σ movimientos" no se *mantiene*, se cumple por construcción. Se puede
comprobar en cualquier momento con `GET /api/auditoria/stock`, y
`test_el_stock_se_reconstruye_sumando_los_movimientos` la verifica sobre una secuencia
larga y mezclada.

**3. El descuento es idempotente** por `(canal, id_externo)`, con la clave primaria de
`venta_procesada` haciéndolo cumplir. Mercado Libre va a devolver la misma orden más de una
vez.

**4. Nada se descarta en silencio.** Una venta sin receta, sin mapeo o anterior a la
`fecha_corte` igual deja su fila en `venta_procesada` con el estado que explica qué pasó.

---

## Decisiones que conviene conocer antes de tocar esto

- **El stock solo cambia por un movimiento.** `PUT /api/insumos/{id}` no acepta stock. Un
  conteo de inventario (`POST /api/insumos/{id}/stock`) manda el valor **absoluto** y el
  sistema asienta la **diferencia**.

- **Todo o nada por venta.** Si una orden trae dos ítems y a uno le falta la receta, no se
  descuenta ninguno: la venta queda `pendiente_receta` con sus ítems guardados en
  `items_json`. Descontar la mitad obligaría a recordar qué parte ya se descontó para no
  duplicar al reprocesar. Cuando el socio carga la receta,
  `POST /api/ventas/pendientes/reprocesar` la asienta completa y exactamente una vez.

- **El reproceso no es una puerta trasera.** `reprocesar_venta` solo actúa sobre estados
  `pendiente_*`; una venta `procesada` nunca se vuelve a descontar.

- **El stock puede quedar negativo y se avisa.** Si se vende un artículo cuyo insumo no
  estaba cargado, la venta se asienta igual. Rechazarla sería perder el dato real; el
  negativo se reporta como alerta y se corrige con un ajuste.

- **La `fecha_corte` se fija sola** con la primera carga de stock (es, por definición, la
  fecha de esa carga). Sin corte, una sincronización de ML traería el historial completo y
  lo descontaría de un inventario que recién se carga. Se corrige por
  `PUT /api/config/fecha_corte`.

- **Un insumo o artículo con historia se desactiva, no se borra.** Borrarlo dejaría al libro
  mayor sin poder explicar movimientos existentes. El `DELETE` lo detecta y desactiva,
  informándolo en la respuesta.

- **El margen de embalaje de 1,05 por dimensión infla el VOLUMEN 15,8%**, no 5%
  (1,05³ = 1,158). Queda en 1,05 como lo pidió el socio, configurable por artículo y con
  default en `config.margen_embalaje_default`. Importa porque Correo Argentino cobra por
  peso volumétrico con paquetes livianos y voluminosos, que es exactamente el caso de una
  guirnalda. `GET /api/articulos/{id}/envio?margen=1.016` simula otro factor sin guardar
  nada.

- **Las fechas se guardan en hora local (ART)**, no en UTC como el resto del repo: la
  `fecha_corte` se compara por día calendario y un `datetime('now')` de SQLite correría el
  borde del día tres horas.

---

## Endpoints

44 en total. `GET /` y `GET /salud` son abiertos; todo `/api/*` pide el header
`X-Insumos-Password` cuando `INSUMOS_PASSWORD` está configurado.

### Taxonomía
```
GET    /api/categorias                      lista con subcategorías anidadas y cuenta de insumos
POST   /api/categorias                      {nombre, orden}
PUT    /api/categorias/{id}                 parcial
DELETE /api/categorias/{id}                 409 si tiene insumos
GET    /api/categorias/{id}/subcategorias
POST   /api/subcategorias                   {categoria_id, nombre, orden}
PUT    /api/subcategorias/{id}
DELETE /api/subcategorias/{id}              409 si tiene insumos
```

### Insumos
```
GET    /api/insumos                         ?activo&categoria_id&subcategoria_id&q&solo_alerta
GET    /api/insumos/{id}                    + `usado_en`: en qué artículos entra
POST   /api/insumos                         + `stock_inicial` opcional (en la unidad del modo)
PUT    /api/insumos/{id}                    parcial, NO toca el stock
DELETE /api/insumos/{id}                    borra si no tiene historia; si la tiene, desactiva
POST   /api/insumos/{id}/stock              conteo: {cantidad, en_unidades, usuario, nota}
GET    /api/insumos/{id}/movimientos        libro mayor del insumo, con saldo por fila
```

Cada insumo sale con `stock` (unidades + la unidad de pantalla + kg), `costos`
(por unidad / por 100 g / por kg, o `null` si no hay costo cargado), `en_alerta` y los
nombres de su categoría y subcategoría.

### Artículos, recetas y envío
```
GET    /api/articulos                       ?activo&q&sin_receta
GET    /api/articulos/{id}                  + receta, mapeos y envío calculado
POST   /api/articulos
PUT    /api/articulos/{id}
DELETE /api/articulos/{id}                  desactiva si tiene ventas
GET    /api/articulos/{id}/envio            ?margen= para simular
GET    /api/envio                           ?sku_elgadget= | ?sku_afd= | ?id_empretienda=
GET    /api/articulos/{id}/receta
PUT    /api/articulos/{id}/receta           {items:[{insumo_id, cantidad}]} reemplaza todo
POST   /api/articulos/{id}/receta           una línea; repetirla actualiza la cantidad
DELETE /api/articulos/{id}/receta/{insumo_id}
```

**`GET /api/envio?sku_elgadget=AFD-20` es la puerta para el cotizador de Correo Argentino
del checkout de El Gadget**, que conoce el SKU y nada más. Devuelve:

Respuesta real para una guirnalda de 40 caireles de 2,5 g y 25 eslabones de 1,8 g, que
mide 2 m pero se embala doblada en un cuadrado de 25×25×6:

```json
{
  "articulo_id": 1, "nombre": "Guirnalda de caireles 2 m",
  "sku_afd": null, "sku_elgadget": "AFD-21",
  "medidas_reales_mm": {"largo": 2000.0, "ancho": 60.0, "alto": 20.0},
  "peso_insumos_g": 145.0, "peso_envio_g": 152.25, "peso_envio_kg": 0.15225,
  "margen_embalaje": 1.05, "se_embala_doblado": true,
  "largo_envio_mm": 262.5, "ancho_envio_mm": 262.5, "alto_envio_mm": 63.0,
  "largo_envio_cm": 26.25, "ancho_envio_cm": 26.25, "alto_envio_cm": 6.3,
  "volumen_cm3": 4341.09,
  "insumos_en_receta": 2, "receta_incompleta": false
}
```

Se ve ahí la decisión de la especificación: el artículo conserva sus 2.000 mm como dato
real, pero el envío se cotiza con el cuadrado de 262,5 mm.

`receta_incompleta: true` significa que **el peso no sirve para cotizar**: sin receta la
suma da 0, y un 0 que parece un peso es peor que un error.

### Mapeo de canal (lo que va a usar la integración con Mercado Libre)
```
GET    /api/mapeos                          ?canal&articulo_id
POST   /api/mapeos                          {articulo_id, canal, id_externo, variacion_externa}
DELETE /api/mapeos/{id}
```

`canal` es `ml`, `elgadget` o `empretienda` (`manual` no se mapea: elige el artículo en
pantalla). `id_externo` es el id de la **publicación** (el `item_id` de ML), no de la orden.

**Varias publicaciones pueden apuntar al mismo artículo**, y es un caso real: el socio
tiene productos publicados más de una vez en la misma cuenta de ML, con ventas en las dos.
Lo permite el `UNIQUE (canal, id_externo, variacion_externa)`, que deja `articulo_id`
afuera a propósito — **si un refactor lo mete ahí, rompe este caso**. La asimetría también
es deliberada: una publicación **no** puede apuntar a dos artículos, porque una venta no
sabría cuál descontar (da 409). La idempotencia es por **orden**, así que dos ventas del
mismo artículo por publicaciones distintas descuentan las dos.

**Precedencia de variantes.** Una publicación con variantes puede tener una fila por
variante, y dejar `variacion_externa` vacío carga un **comodín** que cubre todas. Cuando
conviven los dos:

| la venta trae | gana |
|---|---|
| una variante con fila propia | **el mapeo específico** |
| una variante sin fila propia | el comodín |
| ninguna variante | el comodín |
| ninguna variante y no hay comodín | nada: `pendiente_mapeo` (no se adivina la variante) |

Cargar un comodín hacia un artículo y una variante hacia otro es legítimo pero confunde,
así que `POST /api/mapeos` lo devuelve en `avisos` explicando quién gana.

### Ventas — el motor
```
POST   /api/ventas                          el punto de entrada único
POST   /api/ventas/lote                     {ventas:[...]} cada una independiente
GET    /api/ventas                          ?canal&estado&desde&hasta&limit&offset
GET    /api/ventas/pendientes
POST   /api/ventas/pendientes/reprocesar
GET    /api/ventas/{canal}/{id_externo}     + los movimientos que generó
POST   /api/ventas/{canal}/{id_externo}/reprocesar
```

`POST /api/ventas`:

```json
{
  "canal": "ml",
  "id_externo": "2000001",
  "fecha_venta": "2026-10-26T14:33:00.000-03:00",
  "items": [
    {"id_externo_item": "MLA100000001", "variacion_externa": "VAR-DORADO", "cantidad": 2},
    {"articulo_id": 7, "cantidad": 1}
  ]
}
```

`id_externo` es el id de la **orden** y es la clave de idempotencia. Cada ítem resuelve su
artículo con `articulo_id` directo o con `id_externo_item` vía `mapeo_canal` (con respaldo
por `sku_elgadget` / `id_empretienda`; ML no tiene respaldo y exige mapeo).

Respuesta:

```json
{
  "canal": "ml", "id_externo": "2000001",
  "estado": "procesada",
  "ya_estaba_procesada": false,
  "articulos": [{"articulo_id": 1, "nombre": "...", "cantidad": 2}],
  "movimientos": [{"movimiento_id": 12, "insumo_id": 3, "insumo": "Cairel...",
                   "articulo_id": 1, "cantidad_unidades": -12.0,
                   "stock_resultante": {...}}],
  "alertas": [{"insumo_id": 3, "nombre": "...", "stock_pantalla": 0.49,
               "umbral_pantalla": 0.5, "unidad": "kg",
               "stock_negativo": false, "recien_cruzado": true}],
  "avisos": []
}
```

`estado` es uno de:

| estado | qué pasó |
|---|---|
| `procesada` | se descontó |
| `pendiente_receta` | falta la receta de algún artículo; **no se descontó nada** |
| `pendiente_mapeo` | no se pudo resolver el artículo; **no se descontó nada** |
| `ignorada_fecha_corte` | la venta es anterior a la primera carga de stock |

`recien_cruzado` distingue el insumo que cruzó el umbral **con este movimiento** del que ya
venía abajo: sin eso, cada venta volvería a avisar por lo mismo y el aviso se vuelve ruido.

### Movimientos, alertas, config y auditoría
```
GET    /api/movimientos                     ?insumo_id&articulo_id&tipo&canal&desde&hasta
POST   /api/movimientos                     {insumo_id, cantidad, tipo, en_unidades, nota}
GET    /api/alertas                         ?incluir_inactivos
GET    /api/config
PUT    /api/config/{clave}                  solo fecha_corte y margen_embalaje_default
GET    /api/auditoria/stock                 stock vs Σ movimientos, insumo por insumo
```

Tipos de movimiento manual: `ingreso`, `merma`, `ajuste`, `devolucion`,
`inventario_inicial`. **El signo lo pone el tipo** (una merma cargada en positivo no puede
sumar stock); `ajuste` es el único que acepta un delta con signo. Las ventas **no** entran
por acá: van a `POST /api/ventas`, el único camino idempotente.

---

## Lo que falta (tareas aparte)

- **Interfaz web.** Todo lo que necesita está en los endpoints de arriba.
- **Integración con Mercado Libre.** La tabla `mapeo_canal` y el punto de entrada están
  listos: la sincronización solo tiene que traer las órdenes desde `fecha_corte` y
  postearlas a `POST /api/ventas/lote`. OAuth contra la cuenta del socio sigue pendiente de
  registrar la aplicación. Nota de la experiencia previa: `api.mercadolibre.com/items/{id}`
  ya **no** responde sin autenticación, devuelve `403 PolicyAgent`.
- **Enganche con El Gadget.** Cuando una orden queda aprobada y tiene ítems con
  `proveedor = 'asifuedeco'`, postear el consumo a `POST /api/ventas` con
  `canal: "elgadget"`.
- **Usuarios y permisos**, que la especificación deja sin definir. Mientras tanto hay un
  secreto compartido; ver arriba.
- **Canal de las alertas** (pantalla, mail o WhatsApp), también sin definir.
- **Dónde se hostea.** Reusa el patrón de Render de El Gadget, pero la base necesita disco
  persistente: `data/insumos.db` es el único lugar donde van a vivir el stock y los costos.
