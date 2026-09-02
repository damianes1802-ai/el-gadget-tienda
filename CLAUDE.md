# CLAUDE.md — El Gadget (ecommerce automático)

Guía operativa para cualquier sesión de Claude que trabaje en este proyecto. Objetivo: elegir la
herramienta correcta ANTES de abrir el navegador — casi todo (catálogo, órdenes, referidos, logs de
CI, deploys) se resuelve con una llamada de `curl` o un script, más rápido y verificable que clickear.

Las credenciales reales viven en `config/.env` (gitignoreado). Este archivo NO las repite: solo dice
qué clave usar y para qué. Los mismos valores están en el secret `ENV_FILE` de GitHub Actions.

---

## 0. Arquitectura en una pantalla

Tres piezas **separadas**, no un monolito:

| Pieza | Dónde vive | Qué hace |
|---|---|---|
| **Sitio público** | GitHub Pages, carpeta `pages/`, dominio `elgadget.com.ar` (CNAME) | HTML estático **pre-generado**. Nunca toca la base: pide todo por `fetch` a la API |
| **API** | Render free — `https://el-gadget-tienda.onrender.com` | FastAPI, ~75 endpoints: órdenes, MercadoPago, AFIP, referidos, reseñas, emails |
| **Pipeline** | GitHub Actions (6 workflows) | Scrapea Droppers, calcula precios, sincroniza, **regenera el sitio y lo despliega solo** |

Repo: `damianes1802-ai/el-gadget-tienda` (rama única `main`).
Modelo de negocio: dropshipping del catálogo de **Droppers** + **programa de referidos** (comisión
7% base → 11% con 5 ventas/mes → 15% con 15 ventas/mes; el comprador recibe 10-20% off).

### El pipeline diario

`scripts/00_actualizar_sistema_completo.py` encadena 11 pasos. Lo dispara un **cron externo
(cron-job.org)** vía `repository_dispatch` ~06:07 UTC (03:06 ART); el `schedule` del workflow es
solo respaldo y se saltea solo si ya hubo corrida en las últimas 20 h.

1. agotados/reingresados → 2. scraper fase 1 (sin categorías) → 3. mapeo de categorías fase 2 →
4. categoría OFERTAS → 5. descarga de imágenes → 6. Cloudinary → 7. **precios** → 8. sync SQLite →
9. **páginas estáticas + sitemap** → 10. feed Facebook → 11. Google Sheets.

Después: `git push` automático → deploy de Pages → backup de órdenes → email de aviso si falló.

### Workflows

| Archivo | Cuándo | Qué hace |
|---|---|---|
| `actualizacion_diaria.yml` | dispatch externo + cron 08:15 UTC de respaldo | El pipeline completo + backup + deploy |
| `nurturing.yml` | cada 2 h | POST a `/api/admin/nurturing/procesar` (carrito abandonado, referidos, post-compra) |
| `amigo_invisible_limpieza.yml` | diario 02:59 UTC | Borra sorteos vencidos (minimización de datos) |
| `seo_mensual.yml` | día 1, 08:00 UTC | Reescribe títulos/descripciones con **Gemini 2.5 Flash** + regenera páginas |
| `pages.yml` | push a `pages/**` | Deploy de GitHub Pages |
| `redeploy_precios.yml` | manual | Recalcula precios y regenera páginas sin scrapear |

---

## 1. Por API / CLI (preferido — rápido y verificable)

### API propia (Render)

Auth admin: header `X-Admin-Password` con `ADMIN_PASSWORD` de `config/.env`. Docs interactivas en
`/docs`.

```bash
PWD_ADMIN=$(grep '^ADMIN_PASSWORD=' config/.env | cut -d= -f2- | tr -d '\r')
API=https://el-gadget-tienda.onrender.com

curl -s "$API/api/categorias"                                    # público
curl -s -H "X-Admin-Password: $PWD_ADMIN" "$API/api/estadisticas" # admin
curl -s -H "X-Admin-Password: $PWD_ADMIN" "$API/api/admin/referidos"
```

Familias de endpoints: catálogo público · registro/login · órdenes + MercadoPago (webhook con
firma HMAC) · AFIP (Factura C automática al aprobarse el pago, + nota de crédito) · mayoristas ·
descuentos y campañas · referidos y comisiones · reseñas moderadas · arrepentimiento ·
amigo invisible · admin (backup, CSVs para Droppers y comisiones, estadísticas, nurturing).

**Ojo con los endpoints que MANDAN EMAILS a gente real** (`/api/admin/nurturing/procesar` y
cualquier cosa que dispare `enviar_email_*`): no llamarlos "para probar". Son idempotentes por
flags en la base, pero un disparo manual manda correo de verdad a clientes y referidos.

### GitHub API (estado del CI, sin abrir el navegador)

`GITHUB_TOKEN` está en `config/.env`. Esto reemplaza entrar a la pestaña Actions:

```bash
TOK=$(grep '^GITHUB_TOKEN=' config/.env | cut -d= -f2- | tr -d '\r')
REPO=damianes1802-ai/el-gadget-tienda

# Últimas corridas de un workflow
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.github.com/repos/$REPO/actions/workflows/nurturing.yml/runs?per_page=5"

# Log completo de una corrida (viene como .zip)
curl -sL -H "Authorization: Bearer $TOK" \
  "https://api.github.com/repos/$REPO/actions/runs/<RUN_ID>/logs" -o log.zip
```

**Un workflow "success" NO significa que hizo algo.** Varios pasos terminan en `|| echo "..."`, así
que un fallo total queda verde. Para saber si de verdad corrió, leer el log — no el ícono.

### Lo que la API NO expone (no perder tiempo)

- **Logs de Render**: no hay acceso por API con las credenciales que hay. Solo panel de Render.
- **Secrets de GitHub**: se pueden escribir por API (cifrando con la public key del repo) pero
  **no leer**. Para ver qué contiene `ENV_FILE` hay que ir al panel.
- **Base de datos de Render**: no hay shell. Lo único que la exporta es `POST /api/admin/backup`.

---

## 2. Datos

`data/catalogo.db` (SQLite) es **la única excepción del `.gitignore`**: está versionada y el CI la
reescribe y commitea todos los días.

- **19 tablas**: `productos`, `ordenes`/`orden_items`, `clientes`, `referidos`/`comisiones_referidos`,
  `descuentos`, `resenas`, `usuarios_registrados`, `amigo_sorteos`/`amigo_participantes`,
  `historial_precios`, `historial_actualizaciones`, `sesiones_usuario`, `solicitudes_*`.
- **En Render las órdenes NO viven en el archivo del repo.** `api_local.py` usa
  `PERSISTENT_DATA_DIR` (variable de entorno seteada en Render) para poner `catalogo.db` en el disco
  persistente; el catálogo del repo se copia ahí en cada deploy **sin pisar** clientes/órdenes
  (`DB_PATH` vs `CATALOGO_REPO_PATH`, `api_local.py:105-117`). Sin esa variable (desarrollo local)
  usa el archivo del repo directamente.
- **La copia local de `catalogo.db` es siempre el catálogo, nunca los datos de venta**: 0 órdenes,
  0 clientes. Los datos reales solo se ven por la API.

Configuración que también está versionada a propósito: `data/precios/config_precios_v2.json`
(margen 160% + redondeo a $500 arriba), `data/envios/zonas_envio.json` (tarifario Droppers por
zona/partido), `data/sitemap_lastmod.json`, `data/droppers_alertas_estado.json`.

---

## 3. Lo que sí requiere navegador (no hay atajo)

- **Panel de Render**: logs de la API, variables de entorno, estado del disco persistente.
- **Secrets de GitHub Actions** (`ENV_FILE`, `GEMINI_API_KEY`, `GOOGLE_CREDENTIALS_JSON`,
  `GOOGLE_TOKEN_PICKLE_B64`, `GOOGLE_SHEETS_ID`): se leen y editan solo desde
  Settings → Secrets and variables → Actions.
- **cron-job.org**: el disparador real del pipeline diario. No hay credenciales en el repo.
- **MercadoPago, Cloudinary, Resend, Google Ads/Keyword Planner, AFIP/ARCA**: paneles propios.
- **Verificación visual** de cualquier cambio de CSS/layout en `pages/`.

---

## 4. Convenciones del código

- **`scripts/` está numerado por orden de pipeline** (`00_` a `19_`, con huecos). Los números
  retirados no se reusan; lo viejo vive en `scripts/_obsoletos/`.
- **`scripts/api_local.py`** es un solo archivo de ~5.000 líneas con toda la API. Los helpers
  compartidos están en `scripts/utils/` (`campanas.py`, `email_notificaciones.py`,
  `facturacion_afip.py`, `factura_pdf.py`, `placa_referido.py`, `seo_categorias.py`, `blog_posts.py`,
  `validaciones.py`, `config.py`, `logger.py`).
- **La lógica de campañas vive en `utils/campanas.py` a propósito**: la usan tanto la API como el
  generador de páginas estáticas, para que el precio calculado nunca se desincronice entre ambos.
  Si tocás reglas de descuento, tocalas ahí, no en los dos lados.
- **Regla de negocio del checkout**: los códigos de descuento se calculan sobre el precio de lista y
  **no se combinan** con ofertas de temporada; se cobra el camino que más conviene al cliente. Está
  documentado en `api_local.py` dentro de `crear_orden` — respetarlo al tocar precios.
- **Tests**: `pytest tests/` (campañas y órdenes/reseñas de integración). Correrlos antes de tocar
  precios, descuentos o el flujo de órdenes.
- **Paneles de escritorio** (`admin_desktop.py`, `marketing_desktop.py`, pywebview + `admin_app/` y
  `marketing_app/`): el frontend **nunca** habla directo con Render, todo pasa por métodos de la
  clase `Api` expuestos en `window.pywebview.api.*`. Se lanzan con los `.vbs` de la raíz.
- **Generación de contenido con IA**: Claude (`marketing_desktop.py`, posts y guiones de reels) y
  Gemini (`13_optimizar_seo_ia.py`, SEO mensual). El video se genera vía
  `scripts/video_ai_provider.py`, que ya abstrae providers (`local` / `heygen` / `kling`) — cualquier
  proveedor nuevo se agrega ahí, no dentro de `reel_composer.py`.

---

## 5. Lecciones ya aprendidas (no volver a probar estos caminos)

- **El secret `ENV_FILE` no define `API_URL`.** Los tres pasos de Actions que llamaban a la API
  (`nurturing`, `amigo_invisible_limpieza`, backup del pipeline diario) construían la URL con esa
  variable vacía: curl recibía una ruta relativa, fallaba en **milisegundos** (no era cold start de
  Render, como decía el mensaje) y el `|| echo` dejaba el workflow en verde. 534 corridas de
  nurturing sin hacer nada. **Corregido en 2026-09-02** con un fallback a la URL pública en cada
  workflow + warm-up + 3 reintentos + anotación `::error::`. Si aparece otro paso que use
  `$API_URL`, aplicarle el mismo fallback. El nurturing real, mientras tanto, lo venía cubriendo
  **cron-job.org** (por eso los flags `nurturing_d3/d7_enviado` sí estaban marcados).
- **Un paso terminado en `|| echo` es un fallo invisible.** Antes de dar por bueno cualquier
  automatismo de este repo, leer el log de la corrida, no el check verde.
- **La copia local del repo se atrasa sola.** El CI commitea `data/catalogo.db` + `pages/producto/`
  todos los días, así que en una semana quedás decenas de commits atrás. **Siempre `git pull` antes
  de tocar nada**, y nunca pushear un `catalogo.db` local: pisa un mes de catálogo con datos viejos.
- **`api_local.py` corriendo en local ensucia el working tree.** Sus migraciones de arranque crean
  tablas vacías (`referidos`, `resenas`, `comisiones_referidos`, `amigo_*`, `solicitudes_mayorista`)
  dentro de `data/catalogo.db` y git lo marca como modificado. Es ruido, no datos: se descarta con
  `git checkout -- data/catalogo.db`. Verificar antes comparando contra `git show HEAD:data/catalogo.db`.
- **El pin de `anthropic` estaba en `0.7.7` mientras el código usaba `system` como bloques con
  `cache_control`** — sintaxis que esa versión ni soporta. Nunca explotó porque nada en CI ni en
  Render importa `anthropic` (es solo el panel de marketing, que corre local con una versión
  moderna). Actualizado a `0.111.0` en 2026-09-02. Moraleja: `requirements.txt` acá cubre tres
  entornos distintos (CI, Render, escritorio) y un pin roto puede quedar latente meses.
- **Escribir YAML con `bash <<'EOF'` rompe las continuaciones de línea**: el heredoc se come un
  backslash y `curl ... \` + salto queda pegado en una sola línea. Para editar workflows, usar la
  herramienta de escritura de archivos (o un script Python en el scratchpad), no heredocs. Validar
  siempre después con `bash -n` sobre el bloque `run:` extraído.
- **Los slugs de producto incluyen el SKU al final** (`...-diatomita-beige-pisadas-secas-dl1172-5-be`).
  Adivinar la URL desde el nombre da 404: sacarla de `productos.url_amigable` o de `pages/sitemap.xml`.
- **Render free duerme.** La primera llamada después de un rato puede tardar ~50 s. Cualquier script
  o workflow que le pegue debería despertarlo primero con un GET a `/` y reintentar, en vez de
  asumir que un timeout es un error real.
- **`SEO-KEYWORDS/` y `.claude/` están gitignoreados**: existen solo en la máquina local. No asumir
  que un colaborador (o el CI) los tiene.
- **Escribir JSON con acentos por `curl -d '...'` inline en PowerShell/Bash corrompe el UTF-8.**
  Escribir el JSON a un archivo y mandarlo con `curl --data-binary @archivo.json`. Para scripts
  Python en Windows, `PYTHONIOENCODING=utf-8` (los `.bat` y workflows ya lo setean).
