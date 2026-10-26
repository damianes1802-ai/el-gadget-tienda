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
| **Peso máximo de PAQ.AR** | La ficha oficial se contradice sola: dice 30 kg en un lugar y 25 kg en otro | Confirmar al cotizar en MiCorreo |
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
