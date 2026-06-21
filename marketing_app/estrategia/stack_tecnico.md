# Stack Técnico del Sistema de Marketing — El Gadget

> Análisis del stack propuesto por Grok, adaptado a nuestra realidad.

## Evaluación: Grok vs nuestra situación

### Lo que Grok propone vs lo que ya tenemos

| Componente Grok | Nuestra realidad | Decisión |
|----------------|-----------------|----------|
| Ollama (LLM local) | ANTHROPIC_API_KEY (Claude API) | **Usar Claude API** — ya configurado, más potente, sin necesidad de GPU local |
| n8n (orquestador) | Python scripts + cron-job.org | **Mantener Python** — ya tenemos toda la infra, n8n agrega complejidad innecesaria |
| Instaloader (scraping) | No tenemos | **Evaluar** — útil para análisis de competidores |
| Canva Free | Cloudinary (ya configurado) | **Cloudinary** para composición automática + Canva manual cuando haga falta |
| CapCut | No tenemos | **Agregar** — para Reels, gratis |
| Instagram Graph API | No tenemos | **Implementar** — obligatorio para publicar desde el sistema |
| Google Sheets | SQLite + consola de marketing | **Mantener SQLite** — ya tenemos la consola |
| Buffer/Later | No tenemos | **No necesario** — publicamos via Graph API directo |
| Metricool/Iconosquare | No tenemos | **Evaluar Metricool free** — útil al inicio mientras no tengamos Insights API |

### Veredicto

El stack de Grok está pensado para alguien que empieza de cero. Nosotros ya tenemos:
- **Claude API** (mejor que Ollama para generación de contenido)
- **Cloudinary** (composición de imágenes con transformations)
- **Resend** (email marketing funcionando)
- **Python + FastAPI** (backend robusto)
- **SQLite** (almacenamiento)
- **Cron-job.org** (scheduling)
- **Consola de marketing** (desktop app para visualización)

No necesitamos n8n, Zapier, ni orquestadores externos. Nuestro orquestador ES el backend Python.

---

## Stack definitivo El Gadget

```
┌────────────────────────────────────────────────────────────────┐
│                    STACK DE MARKETING                          │
│                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ DATOS        │  │ GENERACIÓN   │  │ PUBLICACIÓN          │ │
│  │              │  │              │  │                      │ │
│  │ Backend API  │  │ Claude API   │  │ Meta Graph API (IG)  │ │
│  │ (métricas    │  │ (copy, ideas │  │ YouTube Data API     │ │
│  │  ventas,     │  │  guiones,    │  │ Resend (email)       │ │
│  │  productos)  │  │  hashtags)   │  │ WhatsApp Bus. API    │ │
│  │              │  │              │  │                      │ │
│  │ Meta Insights│  │ Cloudinary   │  │                      │ │
│  │ (engagement  │  │ (composición │  │                      │ │
│  │  reach, CTR) │  │  de imágenes)│  │                      │ │
│  │              │  │              │  │                      │ │
│  │ Instaloader  │  │ CapCut       │  │                      │ │
│  │ (competencia)│  │ (Reels,      │  │                      │ │
│  │              │  │  manual)     │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ORQUESTACIÓN                                             │  │
│  │                                                          │  │
│  │ scripts/marketing_content.py  (generador de contenido)   │  │
│  │ scripts/marketing_publisher.py (publicador con aprobación)│  │
│  │ scripts/marketing_metrics.py  (recolector de métricas)   │  │
│  │ POST /api/admin/nurturing/procesar (emails, ya funciona) │  │
│  │ cron-job.org (trigger cada 6-12hs)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ALMACENAMIENTO Y VISUALIZACIÓN                           │  │
│  │                                                          │  │
│  │ SQLite: contenido generado, estados, métricas por pieza  │  │
│  │ Consola Marketing (pywebview): aprobación + dashboard    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## Costo mensual estimado

| Servicio | Costo | Notas |
|----------|-------|-------|
| Claude API | ~$5-15/mes | Generación de contenido (Haiku para volumen, Sonnet para calidad) |
| Cloudinary | $0 | Free tier (25 créditos/mes, suficiente para composición) |
| Resend | $0 | Free tier (100 emails/día) |
| cron-job.org | $0 | Free |
| Meta Graph API | $0 | Gratis para publicar en tu propia cuenta |
| YouTube Data API | $0 | Gratis (cuota diaria generosa) |
| Instaloader | $0 | Open source |
| Render (backend) | $0 | Free tier actual |
| **TOTAL** | **~$5-15/mes** | Principalmente Claude API |

---

## Análisis de competencia con Instaloader

### Qué podemos extraer (gratis, datos públicos)

| Dato | Para qué sirve |
|------|----------------|
| Posts de competidores | Ver qué contenido les funciona |
| Likes/comentarios por post | Calcular engagement rate |
| Captions y hashtags | Identificar keywords y patrones de copy |
| Frecuencia de publicación | Benchmark de cadencia |
| Tipo de contenido (Reel/carrusel/foto) | Qué formato rinde más |
| Horarios de publicación | Mejores momentos para publicar |

### Competidores a analizar

| Tipo | Ejemplos | Qué aprender |
|------|----------|-------------|
| Ecommerce similar AR | Tiendas de hogar/gadgets en IG Argentina | Formatos, precios, engagement |
| Programas de afiliados | Cuentas que promuevan "ganar dinero con referidos" | Hooks, CTAs, pain points |
| Momfluencers | Mamás influencers que recomienden productos hogar | Tono, tipo de contenido que comparten |

### Workflow de análisis competitivo

```
Semanal (automático):
1. Instaloader descarga últimos 20 posts de 5-10 competidores
2. Extrae: caption, likes, comments, tipo, hora, hashtags
3. Claude API analiza patrones:
   - "De estos 100 posts, los top 10 por engagement tienen en común..."
   - "Los hooks más efectivos son..."
   - "Los hashtags con mejor rendimiento son..."
4. Genera recomendaciones para el próximo ciclo de contenido
5. Se muestra en la consola de marketing como "Insights de competencia"
```

---

## Modelo de generación de contenido con Claude API

### Prompt engineering por tipo de contenido

El sistema usa prompts especializados por formato y persona:

```
SYSTEM PROMPT (contexto permanente):
- Sos el community manager de El Gadget, tienda online argentina
- Tu objetivo: atraer referidos al programa de comisiones
- Tono: cercano, argentino (vos/voseo), directo, sin exagerar
- Nunca mencionar "Droppers" ni el proveedor
- Precios siempre actualizados desde la base de datos
- Descuento referido: 10-20% según monto del carrito
- Comisión referido: 7-15% según ventas del mes

USER PROMPT (por pieza):
- Formato: [Reel / Carrusel / Post / Story]
- Persona target: [María / Lucas / Ana / Sofi]
- Producto: {nombre, precio, descripción, categoría}
- Objetivo: [atraer referidos / mostrar producto / social proof]
- Generar: caption + hashtags + CTA + hook (primeras 3 palabras)
- Incluir variante B para A/B testing
```

### Modelo a usar por tarea

| Tarea | Modelo | Costo aprox | Por qué |
|-------|--------|-------------|---------|
| Generación de captions | Claude Haiku | ~$0.001/pieza | Rápido, barato, buena calidad para copy corto |
| Análisis de competencia | Claude Sonnet | ~$0.01/análisis | Necesita razonamiento sobre patrones |
| Guiones de video/blog | Claude Sonnet | ~$0.02/guión | Necesita creatividad + estructura |
| Optimización/scoring | Claude Haiku | ~$0.001/eval | Comparación numérica simple |

Con 5 piezas/día × 30 días = 150 piezas/mes → ~$1-3/mes en Claude API.

---

## RAG (Retrieval-Augmented Generation) para mejora continua

### Base de conocimiento del sistema

El agente creativo tiene acceso a:

| Fuente | Contenido | Actualización |
|--------|-----------|---------------|
| `buyer_personas.md` | Perfiles, pain points, tono por persona | Manual |
| `sistema_multiagente.md` | Reglas, guardrails, objetivos | Manual |
| DB: posts publicados con score >80 | Contenido que funcionó bien | Automática |
| DB: análisis de competencia | Patrones de alto engagement | Semanal |
| DB: productos top vendidos | Qué promover | Automática |
| DB: keywords SEO con tráfico | Términos a incluir en captions | Semanal |

### Ciclo de aprendizaje

```
Mes 1: El sistema genera con prompts genéricos + buyer personas
        → Owner aprueba/rechaza → el sistema aprende qué gustó

Mes 2: El sistema tiene 50+ posts con scores reales
        → RAG incluye los top performers como ejemplos
        → Calidad del contenido generado mejora

Mes 3+: El sistema tiene datos de competencia + propios
         → Predice con más precisión el rendimiento esperado
         → Las sugerencias del Optimizador son más acertadas
```

---

## Resumen: qué tomamos de Grok, qué descartamos

### TOMAMOS
- Instaloader para análisis de competencia (gratis, potente)
- CapCut para edición de Reels (gratis, manual)
- Concepto de RAG con "posts ganadores" para mejorar generación
- Loop de mejora continua (scrape → analizar → generar → publicar → medir)
- Metricool free tier como complemento inicial de analytics

### DESCARTAMOS
- Ollama (tenemos Claude API, más potente, sin GPU)
- n8n (tenemos Python + cron, más simple y ya integrado)
- Buffer/Later (publicamos directo via Graph API)
- Google Sheets (tenemos SQLite + consola propia)
- Zapier/Make (innecesario con nuestro stack)
- Stable Diffusion (no generamos imágenes, usamos fotos reales de Cloudinary)

### AGREGAMOS (nuestro, no estaba en Grok)
- Sistema de aprobación humana obligatoria
- Scoring esperado vs real por pieza
- Integración directa con el backend de El Gadget (productos, precios, stock)
- Descuento de referido como CTA principal en todo el contenido
- Consola de marketing dedicada (app desktop)
