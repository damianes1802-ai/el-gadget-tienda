# Cosechar la grilla de tarifas PAQ.AR desde MiCorreo

**Para Damián. Se corre una sola vez, tarda unos 10 minutos, y no hay que pensar nada.**

Mientras Correo no conteste el pedido de credenciales de API, esta es la forma de llenar
`data/envios/tarifario_correo_argentino.json` con precios reales de PAQ.AR. Usás tu propia cuenta
de MiCorreo cotizando tus propios envíos, igual que si los cargaras a mano — sólo que el navegador
hace las consultas por vos.

Cuando lleguen las credenciales, **el checkout no cambia**: lee el mismo JSON. Lo único que cambia
es quién lo llena (un script del pipeline en vez de esto).

---

## Antes de empezar

### 1. Asociá la sucursal cabecera (obligatorio, y define el origen)

El manual oficial del plugin de WooCommerce lo dice sin vueltas:

> *"En el caso de que hayas creado una cuenta, accedé a la página web MiCorreo y asociale una
> **sucursal cabecera**, luego volvé al plugin […] para autenticarte ante el servicio."*

Y el manual de la API agrega:

> *"La cotización toma como origen **la sucursal del cliente MiCorreo** indicado en `customerId`."*

O sea: **el CP de origen no es un parámetro, es la sucursal que tenga asociada la cuenta.** Si no
hay ninguna, MiCorreo no cotiza (es la causa más común de "no me aparecen envíos" en las tiendas).

Entonces, en MiCorreo: asociá la sucursal donde el socio va a despachar de verdad, y **anotá su CP**.
Ese es el `origen.cp` del tarifario, el dato que quedó pendiente desde el principio.

### 2. Dejá a mano una cotización hecha a mano

Hacé **una** cotización normal en MiCorreo, de las que ya sabés hacer. Sirve para dos cosas: para
confirmar que la cuenta cotiza, y para capturar el pedido en el paso siguiente.

---

## Paso 1 — Capturar el pedido de cotización

No puedo escribirte el llamado exacto porque la aplicación de MiCorreo es privada y hay que estar
logueado para verla. Lo sacás vos en 30 segundos:

1. En MiCorreo, abrí las herramientas de desarrollador: **F12** (o Ctrl+Shift+I).
2. Pestaña **Network** (Red). Arriba, filtro **Fetch/XHR**.
3. Hacé una cotización cualquiera en la pantalla de MiCorreo.
4. En la lista aparece el pedido de la cotización — se reconoce porque la respuesta trae los
   precios. Hacé clic para confirmarlo en la pestaña *Response*.
5. **Clic derecho sobre ese pedido → Copy → Copy as fetch.**

Pegámelo en el chat. Con eso te devuelvo el script del paso 2 ya completo, sin TODOs.

> Si preferís avanzar sin esperarme: en el script del paso 2 hay un bloque marcado
> `/* ===== PEGAR ACÁ ===== */`. Pegás lo copiado adentro de la función `cotizar` y reemplazás los
> valores fijos (el CP de destino, el peso, las medidas) por las variables `cpDestino`,
> `pesoGramos`, `largo`, `ancho`, `alto`. Nada más.

---

## Paso 2 — Correr la cosecha

**Dónde**: en la consola del navegador (F12 → pestaña *Console*), **con MiCorreo abierto y la
sesión iniciada**. Si cerrás la pestaña se corta.

**Cuánto**: unas **285 consultas**, con 1,5 segundos de pausa entre una y otra → **alrededor de 8
a 10 minutos**. Son cuatro fases y podés parar entre una y otra.

**Por qué alcanza con 285 y no hace falta barrer los 2.080 códigos postales del país**: la tarifa
de PAQ.AR es una función escalonada de dos variables, la **zona** del destino y el **escalón de
peso aforado**. Una vez que sabés a qué zona pertenece cada CP y dónde están los cortes de peso, la
tabla queda completamente determinada: `zonas × escalones`. Consultar 2.080 CP sería preguntar
2.080 veces lo mismo, tardaría horas y es la forma más rápida de que Correo te corte.

### Las reglas de la casa, antes del código

- **Una consulta cada 1,5 segundos.** No lo bajes.
- **Si algo devuelve 429, 403 o un error de sesión, el script frena solo.** No lo reintentes a lo
  bruto: esperá un rato largo y retomá desde la fase que quedó a medias.
- Esto es tu cuenta cotizando tus envíos. Si el ejecutivo comercial de Correo te dice que prefieren
  que no, o si los términos del servicio lo prohíben, **se tira a la basura y se espera a la API**.
  No vale la pena pelearse con el proveedor del que depende el negocio por ahorrarse una semana.

### El script

```js
/* ============================================================
   COSECHA DE TARIFAS PAQ.AR - correr en la consola de MiCorreo
   ============================================================ */
const PAUSA_MS   = 1500;
const RESULTADOS = [];
let   ABORTADO   = false;

const dormir = ms => new Promise(r => setTimeout(r, ms));

async function cotizar({ cpDestino, pesoGramos, largo, ancho, alto }) {
  /* ===== PEGAR ACÁ el "Copy as fetch" del paso 1 =====
     Reemplazá los valores fijos por las variables de arriba y
     devolvé la respuesta ya parseada. Queda algo así:

     const r = await fetch("https://.../cotizar", {
       headers: { ...lo que copiaste... },
       body: JSON.stringify({
         codigoPostalDestino: cpDestino,
         peso: pesoGramos,
         largo, ancho, alto
       }),
       method: "POST"
     });
     if (!r.ok) throw new Error("HTTP " + r.status);
     return await r.json();
  ===================================================== */
}

async function pedir(params) {
  if (ABORTADO) return null;
  try {
    const data = await cotizar(params);
    RESULTADOS.push({ ...params, data, ts: Date.now() });
    await dormir(PAUSA_MS);
    return data;
  } catch (e) {
    ABORTADO = true;
    console.error('FRENADO en', params, e.message);
    console.error('Esperá un rato y retomá desde la fase que quedó a medias.');
    return null;
  }
}

// Saca el precio del Clásico a domicilio. Ajustar si la respuesta
// de MiCorreo viene con otra forma (lo vemos con el paso 1).
const precioClasicoDomicilio = d => {
  const r = (d?.rates || d?.cotizaciones || d || [])
    .find?.(x => (x.productType === 'CP' || /clasic/i.test(x.productName || ''))
              && (x.deliveredType === 'D' || /domicilio/i.test(x.deliveredType || '')));
  return r ? Number(r.price ?? r.precio) : null;
};

const CAJA_CHICA = { largo: 10, ancho: 10, alto: 10 };   // 1.000 cm3: el peso real manda
const CAJA_MEDIA = { largo: 20, ancho: 15, alto: 10 };
```

#### Fase 1 — cuántas zonas hay (~30 consultas, 1 minuto)

```js
// Un CP por jurisdicción + los bordes que sabemos que importan.
const CPS_SONDEO = [
  '1425','1824','1878','1900','7600','8000','2000','2300','3000','3100',
  '3200','3400','3500','3600','4000','4200','4400','4600','5000','5500',
  '5700','5800','8300','8400','9000','9100','9200','9300','9400','9410'
];

async function fase1() {
  for (const cp of CPS_SONDEO) {
    const d = await pedir({ cpDestino: cp, pesoGramos: 1000, ...CAJA_MEDIA });
    if (!d) return;
    console.log(cp, precioClasicoDomicilio(d));
  }
  // Agrupa CPs por precio idéntico: cada grupo es una zona.
  const porPrecio = {};
  for (const r of RESULTADOS) {
    const p = precioClasicoDomicilio(r.data);
    (porPrecio[p] = porPrecio[p] || []).push(r.cpDestino);
  }
  console.table(porPrecio);
  console.log('ZONAS DISTINTAS:', Object.keys(porPrecio).length);
}
await fase1();
```

**Checkpoint.** Mirá cuántas zonas salieron:

- **Entre 3 y 8** → perfecto, es el modelo esperado. Seguí.
- **Más de 15, casi una por CP** → **pará acá y avisame.** Significa que PAQ.AR no cotiza por zona
  sino por distancia o algo más fino, y entonces toda esta estrategia no sirve: habría que esperar
  la API y cotizar en vivo. Mejor saberlo a los 30 llamados que a los 285.

#### Fase 2 — dónde están los cortes de peso (~110 consultas, 3 minutos)

```js
// Elegí el CP de la zona MÁS CARA de la fase 1: ahí los saltos se ven mejor.
const CP_REFERENCIA = '9410';   // <-- cambialo según la fase 1

async function fase2() {
  const gruesa = [200,500,1000,1500,2000,3000,4000,5000,7500,10000,
                  12500,15000,20000,25000,30000,40000,50000];
  const precios = [];
  for (const g of gruesa) {
    const d = await pedir({ cpDestino: CP_REFERENCIA, pesoGramos: g, ...CAJA_CHICA });
    if (!d) return;
    precios.push([g, precioClasicoDomicilio(d)]);
    console.log(g + 'g', precioClasicoDomicilio(d));
  }
  // Bisecta cada salto hasta encontrar el gramo exacto del corte.
  const cortes = [];
  for (let i = 1; i < precios.length; i++) {
    if (precios[i][1] === precios[i-1][1]) continue;
    let lo = precios[i-1][0], hi = precios[i][0];
    const pLo = precios[i-1][1];
    while (hi - lo > 10) {
      const mid = Math.round((lo + hi) / 2);
      const d = await pedir({ cpDestino: CP_REFERENCIA, pesoGramos: mid, ...CAJA_CHICA });
      if (!d) return;
      (precioClasicoDomicilio(d) === pLo ? lo = mid : hi = mid);
    }
    cortes.push(lo);
    console.log('corte en', lo, 'g');
  }
  console.log('ESCALONES (gramos):', cortes);
  window.CORTES = cortes;
}
await fase2();
```

#### Fase 3 — el divisor volumétrico (~15 consultas, 30 segundos)

No doy por sentado que PAQ.AR use el mismo divisor 6000 que la encomienda de mostrador. Con peso
real fijo y bajo, agrandamos la caja hasta que el precio salte: el volumen del salto dividido por el
primer escalón **es** el divisor.

```js
async function fase3() {
  const PESO = 200;           // bajo, para que mande el volumétrico
  let lo = 10, hi = 100;      // lado del cubo, en cm
  const base = precioClasicoDomicilio(
    await pedir({ cpDestino: CP_REFERENCIA, pesoGramos: PESO, largo: lo, ancho: lo, alto: lo }));
  while (hi - lo > 1) {
    const mid = Math.round((lo + hi) / 2);
    const d = await pedir({ cpDestino: CP_REFERENCIA, pesoGramos: PESO,
                            largo: mid, ancho: mid, alto: mid });
    if (!d) return;
    (precioClasicoDomicilio(d) === base ? lo = mid : hi = mid);
  }
  const volumen = lo ** 3;
  const primerEscalonKg = (window.CORTES?.[0] ?? 1000) / 1000;
  console.log('El precio salta a los', volumen, 'cm3');
  console.log('DIVISOR ESTIMADO:', Math.round(volumen / primerEscalonKg));
}
await fase3();
```

#### Fase 4 — la grilla completa (~120 consultas, 4 minutos)

```js
async function fase4(cpsPorZona) {
  // cpsPorZona: un CP representante de cada zona de la fase 1. Ej: ['1878','7600','5000','9410']
  // Pesos: el punto medio de cada escalón, para caer bien adentro y no en el borde.
  const cortes = window.CORTES;
  const pesos = cortes.map((c, i) => Math.round(((i ? cortes[i-1] : 0) + c) / 2));
  for (const cp of cpsPorZona) {
    for (const g of pesos) {
      const d = await pedir({ cpDestino: cp, pesoGramos: g, ...CAJA_CHICA });
      if (!d) return;
      console.log(cp, g + 'g', precioClasicoDomicilio(d));
    }
  }
  console.log('LISTO:', RESULTADOS.length, 'consultas');
}
await fase4(['1878','7600','5000','9410']);   // <-- ajustar con las zonas reales
```

> **Si MiCorreo cotiza las cuatro combinaciones de una** (Clásico/Expreso × domicilio/sucursal) en
> una sola respuesta —como hace `/rates` de la API cuando `deliveredType` va en `null`— con esto ya
> tenés todo. Si en cambio la pantalla te obliga a elegir una, hay que repetir la fase 4 por cada
> combinación. Lo vemos con lo que capturaste en el paso 1.

---

## Paso 3 — Mandarme el resultado

```js
// Descarga todo como archivo
const blob = new Blob([JSON.stringify(RESULTADOS, null, 2)], { type: 'application/json' });
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = 'cosecha-micorreo.json';
a.click();
```

Pasame **`cosecha-micorreo.json`** tal cual, sin tocarlo, más estos dos datos sueltos:

1. El **CP de la sucursal cabecera** que asociaste (el origen).
2. Cuántas **zonas** salieron en la fase 1 y qué CPs cayeron en cada una.

Con eso armo la tabla `zonas × escalones` en
`data/envios/tarifario_correo_argentino.json`, le pongo fecha y fuente, y saco a PAQ.AR del estado
`TarifaPendiente`. El cotizador y los tests ya están escritos esperando esos números.

---

## Una cosa que conviene decirle al ejecutivo comercial

Cuando Correo conteste, serví este dato: **el plugin oficial de WooCommerce cotiza con sólo el
usuario y la contraseña de MiCorreo del comerciante** — en su manual, el modo "PAQ.AR API MiCorreo"
pide eso y nada más, y tiene un interruptor explícito de *"¿vas a usar el cotizador de Correo
Argentino?"*. El modo que pide `Agreement` + `Apikey` es el **otro**, PAQ.AR API 2.0.

O sea que Correo ya le da cotización a un titular de cuenta sin acuerdo comercial, cuando entra por
un plugin. Lo que necesitamos es el equivalente para un desarrollo propio. Es un pedido chico y
tiene antecedente, no hay que plantearlo como una integración corporativa.
