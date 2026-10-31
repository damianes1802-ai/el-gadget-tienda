# Sistema de Insumos y Producción — Así Fue Deco

Especificación funcional. Fecha: 2026-10-26.
Este documento es la fuente de verdad del diseño. Si algo acá choca con una decisión
posterior, se actualiza acá primero.

---

## 1. Por qué existe

El Gadget vende productos de Así Fue Deco y necesita cobrarle al cliente el costo real
del envío por Correo Argentino en el checkout, sin errores de cotización. Para eso hace
falta el **peso y las medidas del paquete ya embalado**, y hoy ese dato no existe:

- El export de Empretienda trae `0,01 kg` en 257 productos y `0,05` en otros 139. Es un
  valor de relleno, no un peso.
- Los pesos y medidas que el socio declaró en Mercado Libre **no son reales** (lo confirmó
  él mismo el 26/10/2026).

En vez de pesar producto por producto, el peso se **deriva de los insumos** que lo componen.
Así Fue Deco produce a partir de insumos sueltos que compra por peso, así que si se conoce
el peso de cada insumo y la receta de cada artículo, el peso del artículo sale solo.

Como efecto secundario, el sistema le da a Así Fue Deco un control de stock de insumos que
hoy no tienen. Ese es un objetivo del proyecto, no un accidente.

### El flujo de venta que esto habilita

1. Alguien compra en El Gadget.
2. Damián le pasa a Así Fue Deco los datos del cliente y el pago del producto más el envío.
3. Así Fue Deco produce, embala y despacha el paquete en una sucursal de Correo Argentino.

---

## 2. Alcance

**Entra:**

- Catálogo de insumos con categorías y subcategorías, peso y medidas por unidad, costo,
  stock y alertas de stock bajo.
- Catálogo de artículos ensamblados, con la receta de qué insumos lleva cada uno.
- Cálculo automático del peso y las medidas de envío de cada artículo.
- Descuento automático de stock por ventas de Mercado Libre y de El Gadget.
- Carga manual de ventas de los otros canales.
- Alertas cuando un insumo baja del umbral definido.

**No entra (por ahora):**

- Facturación.
- Órdenes de compra a proveedores de insumos.
- Costo de mano de obra y cálculo de costo total del artículo.
- Reposición automática.

---

## 3. Plataforma

Aplicación **web**: backend FastAPI y la interfaz en el navegador, responsive. Una sola base
de código sirve en Windows y en Android, sin app nativa. El socio entra con su usuario desde
la PC o desde el celular, y Damián ve el stock sin tener que pedirlo.

Vive dentro del repo de El Gadget, en `insumos_app/`, siguiendo la convención que ya usan
`admin_app/` y `marketing_app/`. Reusa el stack que ya está andando: FastAPI, el despliegue
en Render y el patrón de credenciales en `config/.env`.

**Una advertencia que hay que respetar:** `damianes1802-ai/el-gadget-tienda` es un repositorio
**público**. El código puede estar ahí, pero el costo de los insumos y el stock son datos
comerciales del socio y **no se commitean nunca**. La base va bajo `data/`, que ya está en
`.gitignore`, y las credenciales en `config/.env`, que también. Cualquier fixture o seed de
ejemplo tiene que ser inventado, no un export real del socio.

---

## 4. Modelo de datos

### `categoria`
`id`, `nombre`, `orden`

### `subcategoria`
`id`, `categoria_id`, `nombre`, `orden`

Ejemplo: CATEGORÍA *caireles* → SUBCATEGORÍAS *de vidrio*, *de acrílico*.

### `insumo`
| campo | tipo | nota |
|---|---|---|
| `id` | | |
| `nombre` | texto | |
| `categoria_id`, `subcategoria_id` | fk | |
| `modo_stock` | `'peso'` \| `'unidad'` | cómo se carga y se muestra el stock |
| `peso_unitario_g` | real, obligatorio | **siempre**, incluso si `modo_stock='peso'` |
| `largo_mm`, `ancho_mm`, `alto_mm` | real, opcional | aproximados, para estimar medidas |
| `stock_unidades` | real | unidad canónica interna |
| `alerta_cuando_queden` | real | expresado en la unidad de `modo_stock` |
| `costo_compra`, `unidad_compra` | real, `'kg'`\|`'unidad'` | para derivar precio x 100 g, x kg |
| `activo` | bool | |

#### Dos decisiones acá que se apartan de cómo lo planteaste

**1. "Stock por peso" y "stock por unidad" no son subcategorías.**

Las nombraste en la misma lista que *de vidrio* y *de acrílico*, pero son cosas de distinta
naturaleza: una dice **qué es** el insumo, la otra **cómo se cuenta**. Si vivieran en la
misma lista, un cairel de vidrio que se compra por peso tendría que elegir entre *de vidrio*
y *stock por peso*, y perderías uno de los dos datos.

Por eso el modo de stock es un campo propio y obligatorio que se elige al cargar el insumo.
Funcionalmente es lo que pediste —aparece como un selector en el alta— pero sin romper la
taxonomía.

**2. El stock se guarda siempre en unidades.**

Si el insumo es de modo `peso`, la pantalla pide kilos y el sistema convierte usando
`peso_unitario_g`. Internamente todo son unidades.

El motivo: las recetas se expresan en unidades ("este artículo lleva 3 caireles"). Si el
stock de unos insumos estuviera en gramos y el de otros en unidades, cada descuento tendría
que convertir, y ahí es donde se cuelan los errores de redondeo. Guardando siempre unidades,
el descuento es una resta y la conversión queda solo en la pantalla.

### `articulo`
| campo | nota |
|---|---|
| `id`, `nombre` | |
| `sku_afd`, `sku_elgadget`, `id_empretienda` | para cruzar con los otros sistemas |
| `largo_real_mm`, `ancho_real_mm`, `alto_real_mm` | medidas del producto, para mostrar |
| `se_embala_doblado` | bool |
| `largo_emb_mm`, `ancho_emb_mm`, `alto_emb_mm` | solo si se embala doblado |
| `margen_embalaje` | default `1,05` |
| `activo` | |

Campos calculados, no almacenados:

```
peso_envio_g = Σ(receta.cantidad × insumo.peso_unitario_g) × margen_embalaje
medidas_envio = (se_embala_doblado ? medidas_embaladas : medidas_reales) × margen_embalaje
```

El caso que planteaste: una guirnalda de 2 metros se dobla en 5 y queda un cuadrado de
25×25. El artículo conserva sus 2 metros como dato real —sirve para la ficha del producto y
para que el cliente sepa qué compra— pero el envío se cotiza con los 25×25.

### `receta`
`articulo_id`, `insumo_id`, `cantidad` — clave primaria compuesta.

### `mapeo_canal`
`articulo_id`, `canal` (`'ml'`\|`'elgadget'`\|`'empretienda'`), `id_externo`, `variacion_externa`

Sin esto, una venta de Mercado Libre no sabe a qué artículo corresponde. Una publicación de
ML con variantes necesita una fila por variante.

### `movimiento_stock`
`id`, `insumo_id`, `cantidad_unidades` (positiva ingreso, negativa egreso), `tipo`,
`origen_canal`, `referencia_externa`, `articulo_id`, `fecha`, `usuario`, `nota`

Es el libro mayor del stock. **`insumo.stock_unidades` siempre tiene que poder reconstruirse
sumando los movimientos.** Sin esta tabla, cuando un número no cierre no hay forma de
averiguar por qué, y en un sistema de stock eso pasa siempre.

### `venta_procesada`
`canal`, `id_externo` — clave primaria compuesta. Más `fecha_venta`, `fecha_proceso`.

Antes de descontar nada se consulta acá. Si la API de Mercado Libre devuelve dos veces la
misma orden —y lo va a hacer, por reintentos o por superposición de ventanas de consulta—
sin esta tabla el stock se descuenta dos veces y nadie se entera hasta que falta material.

### `config`
`fecha_corte`: la fecha de la primera carga de stock. Ninguna venta anterior a esa fecha se
procesa, tal como pediste.

---

## 5. Reglas de cálculo

### El margen de embalaje del 5%

Pediste sumar 5% a cada medida y al peso, para contemplar el embalaje.

Una consecuencia que conviene que veas: aplicar 5% a las **tres** dimensiones infla el
**volumen** un 15,8%, porque 1,05³ = 1,158. Si la intención era que el paquete ocupe un 5%
más de volumen, el factor por dimensión tendría que ser 1,016.

No lo decidí por mi cuenta: queda en 1,05 por dimensión como lo pediste, pero configurable
por artículo, así lo cambiás sin tocar código. Importa porque Correo Argentino cobra por
peso volumétrico cuando el paquete es voluminoso y liviano, que es exactamente el caso de
una guirnalda.

### La tercera dimensión

Mencionaste largo y ancho. Correo Argentino cotiza con **las tres medidas**: aplica peso
volumétrico y además tiene topes de tamaño por servicio. Con dos medidas no se puede cotizar.

Por eso agregué `alto` en los insumos, en los artículos y en el bloque de medidas dobladas.
En los insumos es opcional, porque muchos son planos y el alto no cambia nada; en el
artículo es obligatorio.

### Descuento de stock

Una venta se resuelve siempre igual, venga del canal que venga:

```
venta → artículo (vía mapeo_canal) → receta → un movimiento_stock por insumo
```

- **Mercado Libre y El Gadget**: automático.
- **Empretienda y ventas manuales o mayoristas**: pantalla donde se elige el artículo y la
  cantidad vendida, y se procesa por el mismo motor.
- Idempotente por `(canal, id_externo)`.
- Las ventas anteriores a `fecha_corte` se ignoran.

Si un artículo no tiene receta cargada, la venta se registra igual pero queda marcada como
pendiente de recetar, y se avisa. Descartarla en silencio haría que el stock mienta.

### Alertas

Cada insumo tiene su "avisar cuando queden N", en la unidad de su modo de stock. Se evalúa
después de cada movimiento. El canal de aviso está sin definir.

---

## 6. Integraciones

### Mercado Libre
OAuth contra la cuenta del socio. Consulta de órdenes desde `fecha_corte`. Mapeo de
`item_id` + `variation_id` al artículo. **Pendiente**: registrar la aplicación y que el socio
la autorice.

Nota de la experiencia previa: `api.mercadolibre.com/items/{id}` ya **no** responde sin
autenticación, devuelve `403 PolicyAgent`. Todo pasa por el token.

### El Gadget
Enganche en el webhook de pagos y en la conciliación: cuando una orden queda aprobada y
tiene ítems con `proveedor = 'asifuedeco'`, se postea el consumo a este sistema.

### Correo Argentino
Tarifa **pública de mostrador** (el socio despacha sin contrato comercial). El cotizador vive
en el repo de El Gadget, no acá; este sistema solo provee peso y medidas.

---

## 7. Lo que falta definir

- Usuarios y permisos: quiénes entran y qué puede tocar cada uno.
- Canal de las alertas: pantalla, mail o WhatsApp.
- Dónde se hostea y con qué base de datos.
- Si el costo de los insumos tiene que alimentar el precio de venta del artículo.
- Qué pasa con el stock de insumos que ya tienen hoy: la carga inicial es un inventario
  físico y conviene planificar cuándo se hace, porque fija la `fecha_corte`.
