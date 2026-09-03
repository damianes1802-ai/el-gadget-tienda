# YouArt — generación de material audiovisual publicitario con IA

> Evaluación técnica y de costos hecha el **2026-09-02**. Nada implementado todavía:
> esto es una salida posible para el material audiovisual de marketing, con los números
> y los límites ya verificados para no volver a investigarlos.

## Qué es y cómo se accede

[YouArt](https://youart.ai) es un estudio de generación con IA (imagen, video, audio) que
expone **111 tipos de nodo** en un canvas de workflow, más un módulo UGC aparte.

**No tiene API REST pública.** La única vía de integración es su **servidor MCP**, ya conectado
a las sesiones de Claude de este proyecto. Consecuencia directa de arquitectura:

> YouArt **no puede sumarse como provider dentro de `scripts/video_ai_provider.py`** (al lado de
> `heygen` o `kling`), porque ese módulo necesita una API con key que se llame desde Python.
> YouArt se maneja desde una sesión de Claude, no desde el panel de escritorio.

El flujo realista es: Claude genera/corre las piezas en YouArt → descarga los MP4 a
`marketing_app/data/generated_reels/` → el panel las levanta en su cola de aprobación como
cualquier otro contenido. Sigue valiendo el principio de "nada se publica sin aprobación".

## Las tres salidas posibles

### A. Híbrido — YouArt hace el B-roll, `reel_composer` arma el reel

YouArt anima la foto real del producto en 9:16 y devuelve clips; el compositor que ya existe
los usa de fondo detrás de los overlays, el ritmo por persona y el CTA que ya están afinados.
La voz sigue con el ElevenLabs propio (ya se paga aparte) y la música con los mp3 locales.

- **Costo: ~90–150 créditos por reel ≈ USD 0,90–1,50.**
- Conserva la identidad de marca ya construida.
- **Requiere trabajo de código**: hoy `reel_composer.py` **no tiene ninguna entrada de video**
  (ni siquiera importa `VideoFileClip` — arma los frames con PIL sobre color plano). Hay que
  agregarle una capa de video de fondo.

### B. Full YouArt — el reel entero adentro

Clips con audio nativo + TTS + stitch + overlays con el nodo `VideoEditor`.

- **Costo: ~1.000–2.500 créditos por reel ≈ USD 10–25.** Entre **15 y 20 veces** el híbrido.
- Se pierden las paletas, el ritmo y el CTA por persona ya afinados.
- Se paga la voz dos veces (YouArt tiene su propio nodo de ElevenLabs).
- Si se prueba igual, hacerlo con **Wan 3.0** (20–1200 cr, 2-30s con audio nativo en un solo
  nodo) o **Kling v2.6** (90–240 cr), no con Seedance 2.5 — baja el piloto a ~USD 3-5.

### C. Módulo UGC — la vía para unboxing / demo / reseña

Superficie aparte del canvas, con **agente propio del lado del servidor**: se crea una campaña,
se le manda un brief en lenguaje natural con las fotos adjuntas, y él planifica el aviso, elige
modelos y planos, y monta el corte final. Sale 9:16 a 1080p, de 9 a 30 segundos.

Formatos que ofrece: **unboxing, demo de producto, reseña, respuesta a comentario,
antes/después, testimonio**. Su galería de ejemplos usa exactamente nuestras categorías
(licuadora portátil, bandeja para cables, vaporizador de ropa, lámpara de amanecer).

- Herramientas MCP: `create_ugc_campaign` (gratis) → `send_ugc_campaign_brief` (cobra) →
  `get_ugc_campaign_status` (polling; mirar `delivery.final_video_ready`, no alcanza con `status`).
- **Costo por brief: NO publicado.** Se cobra "como un turno de chat" y el agente genera varios
  clips, así que probablemente esté en el orden del full-YouArt. Solo se sabe mandando uno.
- **Las fotos hay que subirlas a YouArt primero** (`create_asset_upload`): el brief **rechaza URLs
  de terceros**, o sea que las de Cloudinary no entran directo.

## Costos verificados (2026-09-02)

**Valor del crédito:** top-up USD 5 / 500 = **USD 0,010**. Dentro de plan: Basic USD 0,0100 ·
Pro USD 0,0091 · Max USD 0,0083. Planes: Basic 9,99/1.000 cr · Pro 29,99/3.300 cr ·
Max 149,99/18.000 cr · Team 329,99/36.300 cr.

Modelos con entrada de imagen y salida vertical 9:16 (los que sirven para producto):

| Modelo | Rango publicado | 9:16 | Duración | ~cr/seg (estimado) |
|---|---|---|---|---|
| Grok Video v1.5 | 4–90 | sí | 1–15s, 480/720p | ~6 |
| Seedance 1.5 Pro | 20–120 | sí | 4–12s, 480/720p | ~10 |
| Kling v2.5 Turbo | 50–100 | sí | 5 o 10s | 10 |
| Seedance 2.0 Mini | 32–240 | sí | 4–15s, 480/720p | ~16 |
| Vidu Image-to-Video | 5–144 | sigue la imagen | 1–8s | ~10 |
| Kling v3.0 (audio nativo) | 36–900 | sí | — | 30 @4K |
| Seedance 2.5 (audio nativo) | 80–3000 | sí | hasta 30s | ~100 @1080p |

Audio: **ElevenLabs v3 = 40 cr por 1.000 caracteres** (un guión nuestro ≈ 400 chars ≈ 16 cr).
Música: MiniMax 6 cr, Suno 12 cr. Las herramientas (stitch, trim, editor) no son generativas:
los créditos se gastan al generar, así que el ensamblado no debería cobrar.

> ⚠️ **Los cr/seg son estimaciones propias dividiendo el rango publicado** por la duración y
> resolución máximas. YouArt no publica tarifa por segundo: muestra el costo exacto en el editor
> justo antes de generar. Confirmar contra esta tabla en la primera corrida real.

Referencia práctica con plan Pro (3.300 cr/mes): **~25 reels híbridos** o **~2 full-YouArt**.

## Lo que juega a favor

**177 de los 206 productos con stock tienen 2 o más fotos, y ~100 tienen entre 4 y 9.** Los
modelos omni-reference (Seedance 2.x Omni, Wan 3.0 Omni, HappyHorse, Vidu Reference) aceptan
hasta 9 imágenes del mismo sujeto. Es la diferencia entre que el modelo invente un producto
parecido y que reproduzca el nuestro. Las URLs salen de `productos.imagen_principal` +
`imagenes_adicionales` (Cloudinary).

Además, `LoadImage` del canvas **acepta URL directa**, así que para las salidas A y B las fotos
de Cloudinary entran sin subir nada. Se puede incluso pedir un recorte 9:16 por transformación
de Cloudinary antes de alimentarlas (ver `cloudinary_main()` en `12_generar_paginas_producto.py`).

## Límites honestos

1. **El detalle fino derrapa.** Logos, texto de etiquetas y mecanismos chicos se deforman con el
   movimiento. Sirve para feed a velocidad de scroll, no para pieza de marca en pantalla grande.
2. **Las manos son lo más difícil.** Un unboxing es justamente manos manipulando un objeto:
   hay que contar con artefactos ocasionales y descartar tomas.
3. **No se puede leer el saldo de créditos por MCP** (ese scope no está habilitado en el
   conector), así que el gasto no se puede medir de antemano desde una sesión.

## ⚠️ Advertencia de negocio sobre el formato "unboxing"

El Gadget hace dropshipping de Droppers: **el cliente no recibe packaging de marca propia**
(a confirmar). Un video de unboxing mostrando una caja de El Gadget publicita algo que nunca
va a llegar — publicidad engañosa bajo la **Ley 24.240 de Defensa del Consumidor**, además de
crear una expectativa que el paquete real desinfla.

Si no hay packaging propio, los formatos que convierten igual o mejor sin prometer nada falso
son **demo del producto en uso** y **reseña/testimonio**. Si igual se quiere unboxing, hacerlo
con un mailer neutro parecido al que Droppers despacha de verdad.

## Piloto propuesto (sin ejecutar)

**Organizador Escurridor de Platos Metálico** (SKU DL2276, $75.500, 8 fotos): es uno de los
cuatro productos con landing de Google Ads, así que el video tiene destino inmediato —landing y
campaña— y tiene fotos suficientes para anclar el sujeto. Formato: demo de producto, 15 segundos.

Crear la campaña no cuesta; el primer brief sí. Ese primer brief es también la única forma de
conocer el costo real del módulo UGC.
