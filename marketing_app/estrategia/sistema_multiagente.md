# Sistema Multiagente de Marketing — Definición Técnica

## Objetivo principal (Fase actual)

**MAXIMIZAR REFERIDOS ACTIVOS** — todo el contenido, toda la medición y toda la
optimización apuntan a que más personas se registren como referidos Y que los
referidos existentes compartan más y generen ventas.

Métrica norte: **referidos activos con ≥1 venta en los últimos 30 días**

---

## Principios del sistema

1. **Nada se publica sin aprobación del owner** — el sistema genera, el humano aprueba
2. **Todo es medible** — cada pieza de contenido tiene métricas esperadas vs reales
3. **Auto-ajuste basado en datos** — el sistema aprende qué funciona y propone más de eso
4. **Multi-canal coordinado** — Instagram, YouTube (SEO), email, WhatsApp
5. **Contenido adaptado por persona** — María, Lucas, Ana, Sofi, Martín

---

## Canales y prioridad

| Canal | Prioridad | Estado | Objetivo |
|-------|-----------|--------|----------|
| Instagram | ALTA | Por crear cuenta | Reels, posts, stories para atraer referidos |
| YouTube | ALTA | Por crear canal | SEO orgánico con keywords de alto volumen |
| Email | IMPLEMENTADO | En producción | Nurturing de referidos, carritos, post-compra |
| WhatsApp | IMPLEMENTADO | Templates en panel | Share de productos por referidos |
| TikTok | MEDIA | Futuro | Amplificación cuando IG esté funcionando |
| Facebook | BAJA | Página inactiva | Reactivar con contenido de IG (cross-post) |

---

## Arquitectura del sistema

### Flujo completo

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. ANALISTA │────→│  2. CREATIVO │────→│  3. REVISIÓN │────→│ 4. PUBLICADOR│
│              │     │              │     │   (HUMANO)   │     │              │
│ Analiza      │     │ Genera       │     │              │     │ Publica en   │
│ métricas,    │     │ copy, imagen │     │ Owner ve el  │     │ IG/YT/Email  │
│ elige qué   │     │ hashtags,    │     │ borrador en  │     │ cuando el    │
│ promover,   │     │ variantes    │     │ la consola   │     │ owner aprueba│
│ keywords    │     │ A/B          │     │ y aprueba o  │     │              │
│ SEO         │     │              │     │ pide cambios │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
┌─────────────────────────────────────────────────────────────────────┘
│
▼
┌──────────────┐     ┌──────────────┐
│ 5. MÉTRICAS  │────→│6. OPTIMIZADOR│
│              │     │              │
│ Recolecta    │     │ Compara      │
│ engagement,  │     │ esperado vs  │
│ reach, clicks│     │ real.        │
│ conversiones │     │ Ajusta       │
│ por pieza    │     │ próximo      │
│              │     │ ciclo        │
└──────────────┘     └──────────────┘
```

### Flujo de aprobación en la consola

```
Estado del contenido:
  BORRADOR → PENDIENTE APROBACIÓN → APROBADO → PROGRAMADO → PUBLICADO → MIDIENDO

En la consola de marketing, el owner ve:
┌─────────────────────────────────────────────────────────┐
│ Contenido pendiente de aprobación                       │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [IMG preview]  Reel para Instagram                  │ │
│ │                                                     │ │
│ │ Caption: "¿Tu placard es un caos? Mirá cómo..."    │ │
│ │ Hashtags: #organizacion #hogar #argentina           │ │
│ │ Persona target: María                               │ │
│ │ Producto: Organizador DL2126-NE                     │ │
│ │ Hora sugerida: Mié 10:30hs                          │ │
│ │                                                     │ │
│ │ Efecto esperado:                                    │ │
│ │   Reach: 500-2.000  Engagement: 3-5%               │ │
│ │   Clicks al link: 15-40  Registros ref: 1-3        │ │
│ │                                                     │ │
│ │ [✅ Aprobar]  [✏️ Editar]  [❌ Rechazar]            │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Después de publicado, misma tarjeta muestra:            │
│                                                         │
│   Efecto esperado    vs    Efecto real                   │
│   Reach: 500-2.000         Reach: 1.847 ✅              │
│   Engagement: 3-5%         Engagement: 4.2% ✅          │
│   Clicks: 15-40            Clicks: 28 ✅                │
│   Registros ref: 1-3       Registros: 2 ✅              │
│                                                         │
│   Score: 87/100 — BUEN RENDIMIENTO                      │
└─────────────────────────────────────────────────────────┘
```

---

## Estrategia de contenido para Instagram

### Pilares de contenido (alineados a buyer personas)

| Pilar | % del feed | Persona target | Objetivo | Ejemplo |
|-------|-----------|----------------|----------|---------|
| Producto en acción | 35% | María | Mostrar uso real del producto | "Antes/después: placard con organizador" |
| Oportunidad de ingreso | 30% | Lucas, María | Atraer referidos | "Así gano plata recomendando productos" |
| Educativo/tips | 20% | Ana, María | Valor + autoridad | "5 tips para organizar espacios chicos" |
| Social proof | 15% | Todos | Confianza | Capturas de reviews, testimonios, stats |

### Formatos por frecuencia

| Formato | Frecuencia | Automatizable |
|---------|-----------|---------------|
| Reels (15-30s) | 4-5/semana | Parcial: slideshow de fotos + texto overlay + música |
| Posts carrusel | 2-3/semana | Sí: Cloudinary compone slides con datos de DB |
| Stories | Diario | Sí: templates con producto + precio + código |
| Post estático | 1-2/semana | Sí: foto de producto + caption IA |

### Estructura de un Reel automatizado

```
Slide 1 (0-3s):  Hook de texto sobre imagen del problema
                 "¿Tu placard es un caos?"
                 
Slide 2 (3-8s):  Foto del producto (Cloudinary)
                 Texto overlay: nombre + precio

Slide 3 (8-12s): Foto del producto en uso (si hay imagen adicional)
                 Texto: "Antes → Después"

Slide 4 (12-15s): CTA
                  "Link en bio · Código XXXX = hasta 20% OFF"
                  
Audio: música trending (seleccionada manualmente o de librería libre)
```

---

## Estrategia SEO orgánico (YouTube + Blog)

### Investigación de keywords

El sistema debe buscar keywords con:
- Volumen de búsqueda alto en Argentina
- Competencia baja/media
- Intención de compra o de "ganar dinero"

### Categorías de keywords

| Categoría | Ejemplos | Persona | Formato |
|-----------|----------|---------|---------|
| Producto + review | "mejor organizador de placard 2026" | María | Video YT + blog |
| Ganar dinero | "ganar dinero desde casa argentina 2026" | Lucas | Video YT + blog /ganar/ |
| Comparativa | "shein vs tienda argentina envío rápido" | María | Video YT + blog |
| Tutorial/tips | "cómo organizar espacios chicos" | María, Ana | Video YT + IG Reel |
| Programa afiliados | "programa afiliados argentina ecommerce" | Lucas, Sofi | Video YT + blog /ganar/ |

### Flujo de contenido SEO

```
1. Agente Analista busca keywords (YouTube Search Suggest + Google Trends)
2. Selecciona las de mayor oportunidad (volumen / competencia)
3. Agente Creativo genera:
   - Guión de video (para YouTube)
   - Artículo blog (para Google)
   - Caption de IG (para cross-post)
4. Owner aprueba el guión
5. Video se produce (inicialmente manual, después slideshow automático)
6. Se publica con SEO optimizado (título, descripción, tags)
7. Métricas: views, watch time, CTR del link, registros de referidos
```

---

## Métricas por pieza de contenido

### Efecto esperado (calculado por el Analista)

Para cada pieza de contenido, el sistema predice:

| Métrica | Cómo se calcula la expectativa |
|---------|-------------------------------|
| Reach | Promedio de reach de posts similares anteriores (o benchmark de la industria si es nuevo) |
| Engagement rate | Promedio histórico del formato × ajuste por hora de publicación |
| Clicks al link | Reach × CTR promedio del formato |
| Registros referido | Clicks × tasa de conversión de /referidos |
| Ventas generadas | Registros × tasa de activación de referidos |

### Efecto real (recolectado por el Collector)

- Instagram: Meta Insights API (impressions, reach, engagement, saves, shares)
- YouTube: YouTube Analytics API (views, watch time, CTR, subscribers gained)
- Link clicks: UTM tracking en backend
- Registros: backend DB (referidos.creado_at correlacionado con fecha de publicación)

### Score de rendimiento

```
Score = promedio ponderado de (real / esperado) por métrica

  Reach:       peso 20%
  Engagement:  peso 25%
  Clicks:      peso 25%
  Registros:   peso 30%  (más peso porque es el objetivo)

  Score > 100: superó expectativas → hacer más de este tipo
  Score 70-100: normal → mantener
  Score < 70: bajo rendimiento → analizar por qué, ajustar
```

---

## Guardrails (reglas inquebrantables)

1. NADA se publica sin aprobación del owner
2. Los precios SIEMPRE se sacan de la DB en tiempo real
3. NUNCA mencionar "Droppers" (proveedor)
4. Máximo 2 publicaciones por día en IG (no parecer spam)
5. No modificar descuentos/comisiones sin aprobación
6. Todo contenido debe cumplir Ley de Defensa del Consumidor
7. No prometer envío gratis si no corresponde al producto
8. Las imágenes de productos solo usan las de Cloudinary (no generar con IA)
9. Los testimonios deben ser reales (no inventar reviews)

---

## Lo que falta construir (orden de implementación)

### Sprint 1: Content Generator + Consola de aprobación
- Script Python que usa Claude API para generar contenido por persona/canal
- Sección "Contenido" en la consola de marketing con cola de aprobación
- DB local para almacenar contenido generado + estado + métricas esperadas

### Sprint 2: Image Composer + Instagram Publisher
- Cloudinary transformations para componer imágenes de producto con texto
- Conectar Meta Content Publishing API para publicar posts aprobados
- Crear cuenta de Instagram para El Gadget

### Sprint 3: Metrics Collector + Optimizer
- Conectar Meta Insights API para leer métricas de posts publicados
- Implementar comparación esperado vs real en la consola
- Score de rendimiento por pieza
- El Optimizador sugiere ajustes para el próximo ciclo

### Sprint 4: YouTube SEO + Video Generator
- Investigación automática de keywords (YouTube Search Suggest API)
- Generación de guiones y artículos de blog
- Slideshow video generator (fotos + texto + música)
- YouTube Data API para publicar (con aprobación)

### Sprint 5: Auto-adjustment loop
- El sistema completo corriendo: analiza → genera → aprueba → publica → mide → ajusta
- Dashboard de tendencias en la consola
- Alertas automáticas cuando un post performa muy bien o muy mal
- Sugerencias de qué tipo de contenido escalar
