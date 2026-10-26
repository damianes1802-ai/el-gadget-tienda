# Envíos por Correo Argentino — de dónde sale cada número

**Consulta: 26 de octubre de 2026.** Todo lo de acá se leyó ese día del sitio oficial de
Correo Argentino. Las tarifas postales cambian varias veces por año y **las páginas oficiales no
publican fecha de vigencia**, así que este documento existe para que dentro de seis meses se pueda
abrir cada link y comparar en cinco minutos.

Archivos que documenta:

| Archivo | Qué tiene |
|---|---|
| `data/envios/tarifario_correo_argentino.json` | Precios, topes, plazos, volumetría, adicionales |
| `data/envios/cp_provincias_argentina.json` | Tabla CP → provincia para decidir regional vs nacional |
| `scripts/utils/envio_correo_argentino.py` | El cotizador |
| `tests/test_envio_correo_argentino.py` | Los casos |

Nada de esto está enganchado al checkout todavía. Es una pieza aislada.

---

## 0. Por qué hay dos tarifas y no una

Correo Argentino vende el mismo camión por dos mostradores distintos, y la diferencia de precio
es enorme:

| | **Encomienda** (mostrador) | **PAQ.AR** (MiCorreo) |
|---|---|---|
| Cómo se contrata | Vas a la sucursal y pagás | Cuenta online: cotizás, pagás e imprimís el rótulo, después dejás el paquete |
| ¿Hace falta contrato? | No | Hace falta una cuenta de MiCorreo. **No verifiqué** si el alta es libre o si pasa por un alta comercial: no creé ninguna cuenta |
| Productos | Clásica (3-6 días) / Prioritaria (1-3 días) | Clásico (2-5 días) / Expreso (1-3 días) |
| Entrega | **Sólo a domicilio** | A domicilio **y a sucursal** |
| Precio 1 kg regional | **$19.500** | sin publicar (Correo las promociona como *tarifas preferenciales*, o sea más baratas) |

El brief de esta tarea decía "tarifa pública de mostrador" y, por otro lado, "Clásico y Expreso, a
domicilio y a sucursal". Son dos productos distintos: el primero es la Encomienda, el segundo es
PAQ.AR. **Los dos están modelados en el tarifario**, pero sólo la Encomienda tiene precios
confirmados. PAQ.AR queda con `precios: null` y el cotizador levanta `TarifaPendiente` si alguien
lo pide: preferimos un error visible a un número inventado.

> **Antes de publicar los productos de Así Fue Deco conviene decidir esto.** A $19.500 el envío
> regional más barato, una borla de $12.000 es invendible por Encomienda. Abrir la cuenta gratuita
> de MiCorreo y cotizar ahí los mismos paquetes es, probablemente, la diferencia entre que el
> catálogo funcione o no. El trabajo es: ver si el alta es libre, cotizar 4 o 5 destinos tipo, y
> cargar la tabla en `servicios.paqar_clasico.precios`. El cotizador ya la sabe usar.

---

## 1. Precios de las encomiendas — CONFIRMADO

**Fuentes** (tabla "PRECIO", leída el 2026-10-26):

- [Encomienda Correo Clásica](https://www.correoargentino.com.ar/servicios/paqueteria/encomienda-correo-clasica)
- [Encomienda Correo Prioritaria](https://www.correoargentino.com.ar/servicios/paqueteria/encomienda-correo-prioritaria)

| Hasta | Clásica regional | Clásica nacional | Prioritaria regional | Prioritaria nacional |
|---:|---:|---:|---:|---:|
| 1 kg | 19.500 | 26.400 | 31.100 | 38.900 |
| 5 kg | 23.100 | 32.000 | 35.500 | 53.000 |
| 10 kg | 31.100 | 45.200 | 47.500 | 97.500 |
| 15 kg | 38.200 | 56.600 | 61.100 | 131.200 |
| 20 kg | 45.100 | 65.800 | 68.900 | 163.100 |
| 25 kg | 54.200 | 80.900 | 81.500 | 202.400 |

**Lo que NO se pudo confirmar: desde cuándo rigen.** Ninguna de las dos páginas trae fecha de
vigencia, y el Internet Archive no sirve para fecharlas: el sitio está detrás de un WAF
(Incapsula) y las capturas guardaron la página de desafío, no la tabla. Las corridas de
`web.archive.org` entre enero de 2025 y octubre de 2026 no contienen ningún precio.

**Plazos y topes** (misma fuente):

- Clásica: 3 a 6 días. Prioritaria: 1 a 3 días hábiles.
- Peso máximo: **25 kg** en las dos.
- Medidas: la suma del mayor largo + mayor ancho + mayor alto **no puede pasar de 250 cm**, y
  **ningún lado puede pasar de 150 cm**.
- Entrega: *"en domicilio"*, textual. Ninguna de las dos fichas ofrece entrega en sucursal.

### Adicionales — CONFIRMADO

De la misma tabla ("ADICIONALES"):

| Adicional | Precio |
|---|---|
| Aviso de recibo | $9.300 por envío |
| Confronte y sellado | $27.600 por envío |
| Valor declarado $0,01 – $20.000 | $600 |
| Valor declarado $20.000,01 – $200.000 | 3 % |
| Contrareembolso $0,01 – $10.000 | $500 |
| Contrareembolso $10.000,01 – $150.000 | 5 % |

El contrareembolso no aplica a El Gadget (el cliente ya pagó online). Por encima de $200.000 de
valor declarado no hay tarifa publicada: el cotizador levanta `DatosInvalidos` en vez de
extrapolar el 3 %.

---

## 2. Peso volumétrico — CONFIRMADO, divisor 6000

La ficha de la Encomienda Clásica lo explica en texto y lo cierra con un diagrama:

> *"Para establecer el Rango de Peso de las encomiendas y paquetes se debe comparar el Peso
> volumétrico y el Peso real y tomar el mayor de los dos para determinar el Rango Tarifario."*

El diagrama (una imagen embebida en la página, por eso no aparece si se copia el texto) trae las
tres fórmulas:

| Forma | Cálculo volumétrico |
|---|---|
| Rectangular / cuadrada | `(L1 × L2 × L3) / 6000` |
| Triangular | `(L1 × L2 × L3 / 2) / 6000` |
| Cilíndrica | `Diámetro × Diámetro × Largo / 6000` |

Medidas en cm, resultado en kg.

> **Ojo con esto, que es la trampa real del negocio.** Con divisor 6000, los 25 kg de tope
> equivalen a apenas **150.000 cm³**. Una caja que respeta las medidas máximas al pie de la letra
> (150 + 50 + 50 = 250 cm) da **62,5 kg volumétricos** y Correo no la toma. Para la deco de Así
> Fue Deco —liviana y voluminosa— el tope que manda casi nunca es el peso: es el volumen. Una
> guirnalda de 400 g en una caja de 60×25×25 paga el escalón de **10 kg**, no el de 1 kg: $45.200
> en vez de $26.400. Hay un test que fija exactamente ese caso
> (`test_guirnalda_liviana_y_voluminosa_se_cobra_por_peso_volumetrico`).

---

## 3. Regional vs nacional — CONFIRMADO, con una inconsistencia de la propia fuente

**Fuente**: [Encomiendas: Alcance Regional y Nacional](https://www.correoargentino.com.ar/encomiendas-alcance-regional-y-nacional)

Textual:

- **Regional**: *"Cuando el domicilio del destinatario y el de imposición (orígen) se encuentran
  dentro de la misma provincia."*
- **Nacional**: cuando no.
- *"El territorio comprendido por la Ciudad Autónoma de Buenos Aires y el Gran Buenos Aires (área
  metropolitana, **códigos postales 1000 a 1893**) se considera como una provincia."*
- Los envíos a Malvinas, Georgias del Sur y Sandwich del Sur van siempre con rango **nacional**.

Consecuencia que conviene tener presente: como el AMBA cuenta como una provincia propia, un envío
del AMBA a Mar del Plata **es nacional**, aunque Mar del Plata esté en la provincia de Buenos
Aires. El cotizador lo resuelve así y hay un test que lo fija.

### La inconsistencia

La misma página da **dos criterios que no coinciden**: el rango de CP 1000–1893 y una lista de 24
partidos del GBA. Cruzando el rango contra la base oficial de localidades:

- Dentro de 1000–1893 hay localidades de partidos que **no están en la lista**: Cañuelas, Escobar,
  General Las Heras, General Rodríguez, La Plata, Lobos, Marcos Paz, Pilar, Presidente Perón y
  San Vicente.
- Al revés: **Berazategui**, que sí figura en la lista, tiene el CP **1894**, fuera del rango.

**El cotizador usa el rango de CP**, porque es el único dato que el checkout tiene en la mano.
Afecta sólo el borde, pero es un borde con plata adentro: un envío AMBA → Pilar sale *regional*
acá y podría cobrarse *nacional* en el mostrador. Si alguna vez aparece una diferencia en un
envío a esos partidos, esto es lo primero que hay que mirar.

---

## 4. La tabla CP → provincia — DERIVADA de fuente oficial

Para decidir el alcance hace falta saber en qué provincia cae un CP. No existe un dataset abierto
oficial de códigos postales argentinos (en `datos.gob.ar` el servicio Georef tiene provincias,
departamentos y localidades, pero **no** códigos postales). Así que la tabla se armó desde la base
del propio Correo.

### De dónde salió

El formulario público [Consulta de CPA](https://www.correoargentino.com.ar/formularios/cpa) carga
las localidades por AJAX contra un endpoint propio:

```
POST https://www.correoargentino.com.ar/sites/all/modules/custom/ca_forms/api/wsFacade.php
Content-Type: application/x-www-form-urlencoded
action=localidades&provincia=<letra>&localidad=&calle=&altura=&departamento=
```

Devuelve JSON: `[{id, nombre, partido, municipio, cp, latitud, longitud}, ...]`.

Se pidió una vez por cada una de las 24 jurisdicciones: **23.544 localidades**, **2.080 códigos
postales distintos**. Agrupando el campo `cp` por provincia salen los rangos de
`rangos_por_provincia`.

> **No se puede hacer con `curl`.** El sitio está detrás de un WAF que responde con una página de
> desafío. Hay que ejecutarlo desde un navegador ya cargado en el dominio (misma política de
> origen), por ejemplo desde la consola del navegador parado en `/formularios/cpa`.

### Las letras de provincia

El `<select id="provincias">` de ese mismo formulario trae el mapa oficial letra → provincia (el
`value` de cada opción es la letra del CPA): A Salta, B Buenos Aires, C CABA, D San Luis,
E Entre Ríos, F La Rioja, G Santiago del Estero, H Chaco, J San Juan, K Catamarca, L La Pampa,
M Mendoza, N Misiones, P Formosa, Q Neuquén, R Río Negro, S Santa Fe, T Tucumán, U Chubut,
V Tierra del Fuego, W Corrientes, X Córdoba, Y Jujuy, Z Santa Cruz.

**Por eso el cotizador acepta el CPA completo** (`B1824DXK`): si el cliente lo da, la primera
letra define la provincia y no hace falta tabla ninguna.

### Dos agujeros de esta tabla, los dos explícitos

1. **89 códigos postales ambiguos.** La base oficial los comparte entre dos o tres provincias
   (localidades homónimas o de frontera: 4141 es Salta, Catamarca *y* Tucumán; 9420 es Tierra del
   Fuego *y* Santa Cruz). Con 4 dígitos no hay forma de decidir. El cotizador levanta
   `ZonaNoResuelta` y pide el CPA completo. Están todos listados en `cp_ambiguos`.
2. **CABA no viene con CP.** El endpoint devuelve CABA como una sola localidad con `cp: null`
   (adentro de CABA el CPA se resuelve por calle y altura). El rango 1000–1499 que usa el
   cotizador **no sale de la fuente**: se dedujo de que (a) la página de alcances dice que
   CABA+GBA son 1000–1893 y (b) en el dataset oficial la localidad bonaerense con el CP más bajo
   es 1601. Está marcado `"confirmado": false`. Para decidir regional vs nacional da igual, porque
   CABA y GBA cuentan como una misma provincia y alcanza con el rango 1000–1893.

### Cómo regenerarla

Abrir `https://www.correoargentino.com.ar/formularios/cpa` en un navegador y, en la consola:

```js
const provs = ['C','B','K','H','U','X','W','E','P','Y','L','F','M','N','Q','R','A','J','D','Z','S','G','V','T'];
const cp = {};
for (const p of provs) {
  const r = await fetch('/sites/all/modules/custom/ca_forms/api/wsFacade.php', {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
    body: new URLSearchParams({action: 'localidades', provincia: p, localidad: '', calle: '', altura: '', departamento: ''})
  });
  for (const it of await r.json()) {
    const c = String(it.cp || '').trim();
    if (/^\d{4}$/.test(c)) (cp[c] = cp[c] || new Set()).add(p);
  }
}
// cp["4141"] -> Set {A, K, T}  => ambiguo
```

Después agrupar los no ambiguos en rangos y volcarlos a `rangos_por_provincia`. El test
`test_los_rangos_de_cp_no_se_pisan_entre_provincias` verifica que no queden solapados.

---

## 5. Lo que quedó PENDIENTE

| Qué | Por qué | Cómo se cierra |
|---|---|---|
| **Precios de PAQ.AR** (Clásico/Expreso, domicilio/sucursal) | MiCorreo exige iniciar sesión para cotizar. El único PDF público de precios ([lista-de-precios-CF-MiCorreo.pdf](https://www.correoargentino.com.ar/MiCorreo/public/files/lista-de-precios-CF-MiCorreo.pdf)) tiene fecha de creación **enero de 2023** y además está armado con imágenes | Dar de alta la cuenta en [micorreo.correoargentino.com.ar](https://micorreo.correoargentino.com.ar) y cotizar; o pedir la lista en sucursal |
| **Si el alta de MiCorreo es libre** | No creé ninguna cuenta: habría sido actuar a nombre de Damián sobre un servicio real | Lo resuelve el mismo paso de arriba |
| ~~**Peso máximo de PAQ.AR**~~ | **Resuelto** con el manual de la API (mayo 2026): 1 g a 50.000 g, 200 cm por lado, 300 cm sumados. La ficha web sigue diciendo 25/30 kg y 250/150 cm — ver §8 | Verificar en la primera cotización real antes de vender un paquete de más de 250 cm |
| ~~**Si el alta de MiCorreo es libre**~~ | **Resuelto**: la cuenta es autogestión y gratuita en `micorreo.correoargentino.com.ar/register`, y Correo publica que *"la integración es gratuita y sólo pagás por cada envío"*. Las credenciales de API, en cambio, las habilita un ejecutivo comercial — ver §8 | — |
| **Si la API pide cuenta corriente** | Correo lo exige para Shopify y VTEX; de las APIs propias no dice nada | Preguntárselo al ejecutivo comercial cuando conteste |
| **CP de origen de Así Fue Deco** | Nadie dijo desde qué sucursal despacha el socio, y sin eso no hay alcance que resolver | Preguntarle y cargarlo en `origen.cp` |
| **Fecha de vigencia de las encomiendas** | Correo no la publica y el Archive no la tiene (WAF) | No se puede cerrar desde afuera. Se mitiga re-chequeando los links |
| **Zona 1000–1499 = CABA** | El endpoint no da CP para CABA | Inocuo para el alcance. Si alguna vez se quiere exacto, se saca del CPA completo |

---

## 6. Chequeo de los seis meses

1. Abrir [Clásica](https://www.correoargentino.com.ar/servicios/paqueteria/encomienda-correo-clasica)
   y [Prioritaria](https://www.correoargentino.com.ar/servicios/paqueteria/encomienda-correo-prioritaria)
   y comparar las 12 celdas contra la tabla de arriba. Si cambiaron: editar
   `servicios.*.precios` en el JSON, actualizar `fecha_consulta`, y correr
   `pytest tests/test_envio_correo_argentino.py`. **Varios tests van a fallar a propósito** —
   fijan importes concretos. Ese es el aviso: revisar cada caso y actualizar el esperado.
2. Verificar que los topes (25 kg, 250 cm, 150 cm) y el divisor 6000 sigan igual.
3. Releer [la página de alcances](https://www.correoargentino.com.ar/encomiendas-alcance-regional-y-nacional):
   si el rango del AMBA dejó de ser 1000–1893, actualizar `alcances.amba_es_una_provincia`.
4. La tabla CP → provincia se mueve mucho más lento (localidades nuevas). Regenerarla una vez por
   año alcanza.

---

## 7. Cómo se usa

```python
from utils.envio_correo_argentino import cotizar, TarifaPendiente, PaqueteFueraDeTope

c = cotizar(cp_destino='5000', peso_kg=0.4,
            largo_cm=60, ancho_cm=25, alto_cm=25,
            modalidad='domicilio', cp_origen='1824')

c.costo            # 45200.0
c.alcance          # 'nacional'
c.peso_cobrado     # 'volumetrico'
c.escalon_kg       # 10
print(c.explicacion())
```

Errores, todos distinguibles y ninguno devuelve un número a medias:

| Excepción | Cuándo |
|---|---|
| `PaqueteFueraDeTope` | Pasa de 25 kg (reales o volumétricos), de 250 cm sumados o de 150 cm de lado |
| `ZonaNoResuelta` | CP ambiguo entre provincias o inexistente en la base de Correo |
| `TarifaPendiente` | El servicio existe pero su precio no está confirmado (PAQ.AR) |
| `ModalidadNoDisponible` | Se pidió entrega en sucursal a una Encomienda |
| `DatosInvalidos` | Peso o medidas sin sentido, CP mal formado, falta el origen |

Todas heredan de `ErrorCotizacion`.

---

## 8. Cotización automática con PAQ.AR

Correo tiene **dos APIs distintas y sólo una cotiza**. La diferencia es grande, así que conviene
no confundirlas.

| | **API MiCorreo** | **API Paq.ar 2.0** |
|---|---|---|
| ¿Cotiza? | **Sí** — `POST /rates`, `/rates/packages`, `/rates/calculate` | **No.** El manual entero no menciona cotización, precio, tarifa ni `price` |
| Qué hace | Cotizar, registrar usuarios, listar sucursales, importar el envío, tracking | Alta de orden, cancelar, rótulo, historial, sucursales |
| Credenciales | Basic → JWT. Se piden a Correo por ambiente (hay Test) | `agreement id` + API-Key, **gestionadas con el área Comercial** |
| Base | `https://api.correoargentino.com.ar/micorreo/v1` | `https://api.correoargentino.com.ar/paqar/v1/<endpoint>` |
| Manual | *Correo Argentino – API MiCorreo*, **2026-05-18**, 23 pág. | *Plataforma de Integración – API 2.0*, v1.2, **abril 2023** |

**Para este proyecto va MiCorreo.** Paq.ar 2.0 sirve para *operar* después de vender, no para
decidir cuánto cobrarle al cliente — y encima pide el acuerdo comercial que el socio no tiene.

> Hay una versión pública vieja del manual de MiCorreo
> ([08/2022](https://www.correoargentino.com.ar/MiCorreo/public/img/pag/apiMiCorreo.pdf)) con
> límites desactualizados (25 kg / 150 cm) y sin `/rates/packages`, `/rates/calculate` ni
> `/shipping/tracking`. Los datos de este documento salen del manual de **mayo 2026**.

### Lo que devuelve `/rates`

```jsonc
// POST /rates   (Authorization: Bearer <jwt>)
{ "customerId": "0000550367", "postalCodeOrigin": "1414",
  "postalCodeDestination": "1425", "deliveredType": null,   // null = las 4 combinaciones
  "dimensions": { "weight": 2500, "height": 10, "width": 20, "length": 30 } }
```

```jsonc
{ "customerId": "...", "validTo": "2026-09-18T02:36:58.088-03:00",
  "rates": [
    { "deliveredType": "S", "productType": "CP", "productName": "Correo Argentino Clasico",
      "price": 59611.21, "deliveryTimeMin": "2", "deliveryTimeMax": "5" },
    { "deliveredType": "S", "productType": "EP", "productName": "Correo Argentino Expreso",
      "price": 174928.12, "deliveryTimeMin": "1", "deliveryTimeMax": "3" }
    // ... y las dos variantes "D"
  ] }
```

Tres detalles que importan:

- **`deliveredType: null` trae las cuatro combinaciones** (Clásico/Expreso × domicilio/sucursal)
  en una sola llamada. `CP` = Clásico, `EP` = Expreso.
- **Trae el plazo junto con el precio** (`deliveryTimeMin/Max`), así que los días que publica el
  sitio salen de la misma fuente que el número.
- **La cotización vence** (`validTo`). No es un precio eterno que se pueda cachear para siempre.
- Peso en **gramos**, medidas en **cm**, todos enteros. Límites: 1–50.000 g, 200 cm por lado,
  **300 cm sumados** — bastante más que los 25 kg / 150 / 250 del mostrador. Para deco voluminosa
  eso puede ser la diferencia entre poder vender o no.
- `/rates/calculate` **apila** varios productos en un paquete lógico. Es exactamente el problema
  del carrito con 3 borlas, resuelto del lado de Correo en vez de a ojo.

### Cómo lo construiríamos

**La API no se llama desde el checkout.** Tres razones, todas del proyecto:

1. El sitio es **estático**: las fichas publican costo y plazo pre-generados. No pueden llamar a
   una API.
2. El checkout no puede depender de un tercero. Si Correo tarda o se cae, o cobrás mal o perdés
   la venta.
3. Ya existe el patrón acá: `10_sincronizar_campanas.py` baja datos de afuera, los escribe al
   repo y **falla en blando** (si no responde, deja todo como estaba).

Entonces: **un script del pipeline llena el JSON, y el cotizador que ya existe lo lee sin
cambios.** Pasos:

- **Paso 0 — bloqueante, del lado de Damián.** Pedir a Correo las credenciales de integración de
  MiCorreo (arrancar por el ambiente Test) y tener la cuenta MiCorreo del socio, de la que sale el
  `customerId` vía `POST /users/validate`.
- **Paso 1 — `scripts/utils/micorreo_api.py`.** Cliente de la API: `/token` con caché del JWT
  (viene con `expires`), reintentos vía `utils/http_panel.py` —regla de la casa: en POST sólo se
  reintentan errores de conexión—, y `rates()` / `rates_packages()`. Credenciales en `config/.env`
  (`MICORREO_USER`, `MICORREO_PASSWORD`, `MICORREO_CUSTOMER_ID`) y en el secret `ENV_FILE`. **Nunca
  en el repo, que es público.**
- **Paso 2 — un script numerado que sondea y escribe el tarifario.** Las tarifas de paq.ar son por
  zona × escalón de peso, pero la API cotiza punto a punto. Se descubre la grilla sondeando:
  (a) dimensiones fijas y un CP por provincia → la cantidad de precios distintos revela las zonas;
  (b) destino fijo y barrido de peso 1 g → 50.000 g → los escalones; (c) una muestra de control
  para validar. Sale la misma estructura que ya tiene
  `tarifario_correo_argentino.json`, con zonas de paq.ar en vez de regional/nacional.
  Dos cosas que no hay que olvidar: **falla en blando** (si la API no responde, no se toca el
  JSON — borrar tarifas por un timeout es peor que tenerlas viejas) y **agregar su ruta a la lista
  blanca de `git_push_catalogo()`** en `00_actualizar_sistema_completo.py`, o el archivo se
  regenera todos los días y se descarta en silencio, como pasó con el feed de Google Shopping.
- **Paso 3 — test de deriva.** Re-cotizar N casos de referencia contra la API y avisar si el JSON
  cacheado se separó más de un X %. Es la red que evita que Damián pague la diferencia durante
  semanas sin enterarse.

Después, `/shipping/import` + `/shipping/tracking` cierran el circuito operativo: la orden se crea
en MiCorreo sola y el número de seguimiento entra en el email que el sistema ya manda.

### Cómo se consiguen las credenciales

Son **dos trámites distintos** y conviene no mezclarlos:

**1. La cuenta de MiCorreo** — autogestión, gratis, al toque.
[micorreo.correoargentino.com.ar/register](https://micorreo.correoargentino.com.ar/register).
Pide DNI o CUIT, rubro (hay uno que es literalmente *Deco y Hogar*), domicilio y CP. Con esta
cuenta sola ya se puede **cotizar y despachar desde la web**, sin API. De acá sale el
`customerId` que después necesita `/rates`.

**2. Las credenciales de la API** — no son autogestión. La FAQ oficial de Correo lo dice así:

> *"¿Tengo que registrarme previamente? **Sí.** Nuestros ambientes requieren que cuentes con
> credenciales para conectar con las API's que **podrás gestionar con un ejecutivo comercial**.
> Mientras avanzamos con el alta, podés descargarte todos los manuales y comenzar tus desarrollos."*

El canal es el **formulario de integraciones**:
[correoargentino.com.ar/MiCorreo/public/contact](https://www.correoargentino.com.ar/MiCorreo/public/contact)
(se llega desde *Integraciones → Primeros pasos*). Campos:

| Campo | Qué va |
|---|---|
| Razón social | El Gadget |
| Nombre y apellido · CUIT/CUIL · email · cód. área · celular | Los de Damián |
| Sitio web | `https://elgadget.com.ar` |
| **Motivo del contacto** | Desplegable con tres opciones: *Asesoramiento sobre integración por app.* · *Requiero abrir cuenta MiCorreo.* · *Otros.* → va la **primera** |
| ¿Sos cliente de MiCorreo? | Sí/No + N° de cliente si ya hay cuenta (por eso conviene hacer el trámite 1 primero) |
| ¿Sos agencia? | No |
| Plugin que usás | Dejar vacío, o aclarar que es desarrollo propio |

Hay **reCAPTCHA**, así que el formulario lo manda una persona.

Dos datos de la misma FAQ que cambian el análisis:

- *"**¿Tiene algún costo la integración? No.** La integración es gratuita y sólo pagás por cada
  envío que realices."* — o sea que no hay cuota fija ni mínimo por tener la API.
- La página de integraciones aclara que *"si utilizás Shopify o VTEX necesitás tener una cuenta
  corriente para integrarte"*. No lo dice de las APIs propias, lo cual sugiere que por ahí no hace
  falta cuenta corriente — pero es una inferencia, no algo que Correo afirme. **Preguntarlo
  explícitamente** cuando responda el ejecutivo.

También existe [integracion.correoargentino.com.ar](https://integracion.correoargentino.com.ar/login),
un portal de integración con login propio. Responde, pero no se pudo ver qué hay adentro sin
credenciales.

### Mientras tanto, sin esperar las credenciales

Con el socio logueado en la web de MiCorreo se puede cosechar la grilla desde la consola del
navegador, llamando a los XHR de la propia aplicación — el mismo truco que se usó acá para la base
de localidades (§4). Eso llena el JSON esta semana y desbloquea la venta. **Cuando lleguen las
credenciales no hay que tocar el checkout**, porque lee el mismo archivo.
