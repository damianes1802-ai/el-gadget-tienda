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
`/docs` y **la interfaz web en `/app/`**. La base se crea sola en `data/insumos.db`
(gitignoreada) la primera vez.

Para recorrer las pantallas con datos inventados (el repo es público: nada real acá):

```bash
python -m insumos_app.datos_ejemplo
```

Carga categorías, insumos de los dos modos de stock —uno en alerta y otro en negativo—,
artículos con y sin receta, uno que se embala doblado, un artículo con DOS publicaciones de
Mercado Libre y ventas en los seis estados posibles. Si la base ya tiene insumos no toca
nada, para no pisar un inventario real.

Tests:

```bash
python -m pytest insumos_app/tests -q
```

192 tests, sin tocar ninguna base real: cada uno corre sobre un SQLite temporal. Todos los
datos de ejemplo son inventados — **el repositorio es público y el costo y el stock del
socio son datos comerciales suyos**.

### Variables de entorno

| Variable | Para qué |
|---|---|
| `INSUMOS_PASSWORD` | Secreto del header `X-Insumos-Password`. **Si no está, la API responde SIN autenticación** y lo avisa al arrancar. |
| `INSUMOS_DB_PATH` | Apunta la base a otro archivo. Sin esto, `data/insumos.db`. |

Se leen de `config/.env` o del entorno del sistema (en Render no hay `config/.env`).

### Migraciones

`db.migrar()` corre en cada arranque de la API y es idempotente. La versión del esquema
vive en `config.schema_version` y las migraciones están en `db._MIGRACIONES`, indexadas por
la versión a la que llevan. Una base sin `schema_version` se considera v1.

Esquema actual: **v2** (agregó el estado `cancelada` y las columnas de la cancelación).
Esa migración tuvo que **reconstruir** `venta_procesada`, porque SQLite no permite alterar
un CHECK; corre en una transacción explícita, ya que una base a mitad de camino perdería
el registro de qué ventas se procesaron, y eso significa descontar todo de nuevo en la
próxima sincronización. `test_cancelaciones.py` levanta una base v1 a mano y verifica que
las filas sobreviven.

Si agregás una migración: sumala a `_MIGRACIONES`, subí `SCHEMA_VERSION`, actualizá también
el DDL del `SCHEMA` (para que una base nueva nazca al día) y escribí el test que verifica
que no se pierden datos.

---

## Los módulos

| Archivo | Qué tiene |
|---|---|
| `db.py` | Esquema SQLite, conexión, transacciones, el libro mayor y la config |
| `calculos.py` | Funciones **puras**: peso de envío, conversiones de unidad, costos, alertas |
| `stock.py` | El motor: movimientos, descuento por venta, reproceso de pendientes, cancelación |
| `modelos.py` | Modelos de entrada de la API |
| `api.py` | FastAPI. Cáscara delgada: no tiene reglas de negocio propias |
| `servir_web.py` | Monta la interfaz de `web/` en `/app/` de esta misma app |
| `web/` | La interfaz: HTML, CSS y JS a mano, sin framework ni compilación |
| `datos_ejemplo.py` | Catálogo inventado para probar la interfaz |

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

46 en total. `GET /` y `GET /salud` son abiertos; todo `/api/*` pide el header
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
POST   /api/ventas/{canal}/{id_externo}/cancelar    restituye el stock
POST   /api/ventas/cancelaciones            {cancelaciones:[...]} para un sincronizador
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
| `cancelada` | se canceló; si había descontado, se restituyó |

`recien_cruzado` distingue el insumo que cruzó el umbral **con este movimiento** del que ya
venía abajo: sin eso, cada venta volvería a avisar por lo mismo y el aviso se vuelve ruido.

### Cancelar una venta y restituir el stock

`POST /api/ventas/ml/3000001/cancelar`, con `{motivo, usuario, registrar_si_no_existe}`
opcionales. Es también el enganche para El Gadget cuando Mercado Pago reporta un pago
reintegrado o anulado.

**Revierte los movimientos que realmente se hicieron; no recalcula la receta.** Es la
decisión central: si entre la venta y la cancelación alguien editó la receta del artículo,
recalcular restituiría una cantidad distinta de la que se descontó y el stock quedaría mal
**sin que nada falle**. La reversa lee `movimiento_stock` por `(origen_canal,
referencia_externa)` y asienta el opuesto exacto de cada consumo, con
`revierte_movimiento_id` apuntando al original. Para esto el libro mayor guarda la
referencia de la orden.

- **Idempotente**: cancelar dos veces no restituye dos veces.
- **Una venta que nunca descontó** (`pendiente_*` o `ignorada_fecha_corte`) se marca
  cancelada sin movimientos. `estado_previo` queda guardado para que esa cancelación sin
  restitución se explique sola.
- **`cancelada` es terminal**: la venta sale de la cola de pendientes y no puede volver a
  descontar, ni por `reprocesar`, ni por un reenvío de la orden, ni con `forzar`.

`POST /api/ventas/cancelaciones` hace lo mismo en lote. **Para quien haga el
sincronizador de Mercado Libre: las cancelaciones no llegan consultando "órdenes
nuevas"** — una orden cambia de estado en el canal *después* de que la vimos. El patrón
es releer el estado de las órdenes que ya se conocen:

1. `GET /api/ventas?canal=ml&estado=procesada&desde=<fecha>` da los `id_externo` que este
   sistema ya procesó.
2. Se consulta el estado actual de esas órdenes en el canal.
3. Las que volvieron canceladas se postean al lote, que se puede repetir sin consecuencias.

En el lote, `registrar_si_no_existe` viene en **true** (en la cancelación de una sola
venta viene en false, para que un id mal tipeado no cree una fila fantasma). Registrar una
orden desconocida **protege el stock**: si una orden se canceló en el canal antes de que
la viéramos y no quedara registro, una consulta de "órdenes nuevas" atrasada podría
postearla como venta y descontarla.

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

## La interfaz web

Vive en `insumos_app/web/` y la sirve esta misma app en `/app/`. HTML, CSS y JavaScript a
mano: sin framework, sin paso de compilación y sin dependencias que instalar. Habla con la
API por `fetch()` contra rutas relativas, así que **no hay ninguna URL de API que
configurar** — la trampa que en El Gadget dejó 534 corridas de nurturing en verde sin hacer
nada y publicó meses de URLs rotas en el feed de Meta.

Nueve pantallas: alertas (la primera que se ve), insumos, stock, artículos, categorías,
publicaciones, ventas manuales, cancelación de ventas y ajustes.

**Está escrita para un celular en el taller**, no para un escritorio al que después se le
agrega un `@media`: una columna, botones de 46 px para arriba, teclado decimal en los campos
numéricos y la lista de insumos buscable sin zoom. El menú lateral de escritorio entra recién
a los 900 px.

### Tres cosas que la interfaz sostiene y conviene no romper

**La unidad de stock no se puede confundir.** Toda pantalla que pide un número de stock
muestra un bloque grande, con color propio por modo —azul para kilos, violeta para
unidades— que dice en qué unidad está pidiendo ese número, y repite la unidad pegada al
campo. Mientras se escribe se muestra la equivalencia: quien iba a cargar "2" creyendo kilos
ve *2 kg ≈ 800 unidades* y se da cuenta antes de guardar. Cargar 2 unidades donde iban 2
kilos no falla, no avisa y no se nota hasta que falta material.

**Los números los calcula el backend, siempre.** El peso de envío se actualiza en vivo
mientras se edita la receta porque cada cambio se guarda al instante y el endpoint devuelve
el envío recalculado — no porque la interfaz repita la fórmula. Si el peso se calculara en
los dos lados, algún día discreparían y el que miente sería el de la pantalla. Las dos únicas
cuentas que hace el navegador son de presentación y están marcadas como tales en el código
(`equivalenciaAproximada`, la proyección del saldo).

**Un `0` de peso no se muestra como si fuera un peso.** Cuando el backend devuelve
`receta_incompleta: true`, el panel no muestra ningún número: muestra que falta la receta.

### Autenticación

Hoy `INSUMOS_PASSWORD` no está configurado y la API responde abierta, así que la interfaz
entra directo. La pantalla de ingreso ya está hecha y conectada: al arrancar consulta
`GET /` (abierto) y, si dice que hace falta credencial, la pide y la manda en el header
`X-Insumos-Password` de cada llamada. **El día que se configure la variable, funciona sin
tocar una línea** — probado levantando la API con la variable puesta. Un 401 en cualquier
llamada borra la credencial guardada y vuelve a pedirla.

---

## Lo que falta (tareas aparte)

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
