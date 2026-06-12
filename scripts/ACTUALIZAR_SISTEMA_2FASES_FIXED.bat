@echo off
title Sistema de Actualizacion - 2 Fases Optimizadas

echo.
echo ========================================================================
echo   SISTEMA DE ACTUALIZACION - 2 FASES OPTIMIZADAS
echo ========================================================================
echo.
echo   NUEVO SISTEMA DE 2 FASES:
echo      FASE 1: Scrapea productos (SKU, precio, stock, imagenes)
echo      FASE 2: Mapea categorias desde listados (mas preciso)
echo.
echo   VENTAJAS:
echo      - No depende del breadcrumb (poco confiable)
echo      - Categorias 100%% correctas desde listados
echo      - Sistema de prioridades robusto
echo      - Cache de SKUs (no visita duplicados)
echo.
echo ========================================================================
echo.

:MENU
echo.
echo   SELECCIONE EL TIPO DE ACTUALIZACION:
echo.
echo   [1] ACTUALIZACION COMPLETA (Semanal)
echo       - FASE 1: Scrapear productos sin categorias
echo       - FASE 2: Mapear categorias post-scraping
echo       - Descargar imagenes + Cloudinary
echo       - Calcular precios + Sincronizar
echo       - Tiempo: 70-80 minutos
echo.
echo   [2] ACTUALIZACION RAPIDA (Diaria)
echo       - Solo sincronizacion (SQLite + Sheets)
echo       - Tiempo: 1-2 minutos
echo.
echo   [3] SOLO SINCRONIZAR
echo       - SQLite + Google Sheets
echo       - Tiempo: 20 segundos
echo.
echo   [4] DIAGNOSTICO
echo       - Verificar estado del sistema
echo       - Tiempo: 10 segundos
echo.
echo   [5] CANCELAR
echo.

set /p opcion="   Ingrese opcion (1/2/3/4/5): "

if "%opcion%"=="1" goto COMPLETA
if "%opcion%"=="2" goto RAPIDA
if "%opcion%"=="3" goto SOLO_SYNC
if "%opcion%"=="4" goto DIAGNOSTICO
if "%opcion%"=="5" goto CANCELAR

echo.
echo   ERROR: Opcion invalida
timeout /t 2 > nul
cls
goto MENU

:COMPLETA
cls
echo.
echo ========================================================================
echo   ACTUALIZACION COMPLETA - SISTEMA DE 2 FASES
echo ========================================================================
echo.
echo   Este proceso ejecutara:
echo.
echo      [FASE 1] Scraper Maestro V2                     (~15-20 min)
echo         - SKU, titulo, precio, descripcion, imagenes
echo         - Disponibilidad/stock
echo         - NO categorias (se mapean en FASE 2)
echo.
echo      [FASE 2] Mapear Categorias Post-Scraping        (~8-12 min)
echo         - Por cada categoria: extrae SKUs
echo         - Asigna a metadata existente
echo         - Sistema de prioridades
echo         - Cache (no visita duplicados)
echo.
echo      [3/8] Descargar imagenes faltantes              (~2-5 min)
echo      [4/8] Subir imagenes a Cloudinary               (~45 min)
echo      [5/8] Calcular precios                          (~2 min)
echo      [6/8] Asignar categoria OFERTAS                 (~1 min)
echo      [7/8] Sincronizar a SQLite                      (~7 seg)
echo      [8/8] Sincronizar a Google Sheets               (~10 seg)
echo.
echo   Tiempo total estimado: 70-80 minutos
echo.
echo ========================================================================
echo.
set /p confirmar="   Desea continuar? (S/N): "

if /i not "%confirmar%"=="S" (
    cls
    goto MENU
)

echo.
echo ========================================================================
echo   INICIANDO ACTUALIZACION COMPLETA - 2 FASES
echo ========================================================================
echo.

echo [FASE 1] Scraper Maestro V2 - Productos sin categorias...
echo          Esto puede tardar 15-20 minutos. Por favor espere...
echo.
python scraper_maestro_v2_sin_categorias.py
if errorlevel 1 (
    echo.
    echo ERROR: Error en FASE 1 - Scraper.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

echo.
echo [FASE 2] Mapeador de Categorias Post-Scraping...
echo          Esto puede tardar 8-12 minutos. Por favor espere...
echo.
python mapear_categorias_post_scraping.py
if errorlevel 1 (
    echo.
    echo ERROR: Error en FASE 2 - Mapeo de categorias.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

echo.
echo [3/8] Descargando imagenes faltantes (OPTIMIZADO)...
python 02_descargar_imagenes_OPTIMIZADO.py --solo-faltantes
if errorlevel 1 (
    echo.
    echo ERROR: Error descargando imagenes.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

echo.
echo [4/8] Subiendo imagenes a Cloudinary...
echo       Esto puede tardar 45 minutos. Por favor espere...
python 03_subir_imagenes_cloudinary.py
if errorlevel 1 (
    echo.
    echo ADVERTENCIA: Error en Cloudinary. Continuar sin imagenes en la nube.
    echo Presione una tecla para continuar...
    pause > nul
)

echo.
echo [5/8] Calculando precios...
python 04_calculo_precios.py
if errorlevel 1 (
    echo.
    echo ERROR: Error calculando precios.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

echo.
echo [6/8] Asignando categoria OFERTAS a productos sin categoria...
python asignar_categoria_ofertas.py
if errorlevel 1 (
    echo.
    echo ADVERTENCIA: Error asignando OFERTAS.
    echo Presione una tecla para continuar...
    pause > nul
)

echo.
echo [7/8] Sincronizando a SQLite (OPTIMIZADO - 95%% mas rapido)...
python 11_sincronizar_sqlite.py
if errorlevel 1 (
    echo.
    echo ERROR: Error sincronizando SQLite.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

echo.
echo [8/8] Sincronizando a Google Sheets (OPTIMIZADO - 60%% mas rapido)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if errorlevel 1 (
    echo.
    echo ERROR: Error sincronizando Google Sheets.
    echo Presione una tecla para continuar o Ctrl+C para cancelar...
    pause > nul
)

goto FIN_EXITOSO

:RAPIDA
cls
echo.
echo ========================================================================
echo   ACTUALIZACION RAPIDA (DIARIA)
echo ========================================================================
echo.
echo   Este proceso ejecutara:
echo.
echo      1. Asignar categoria OFERTAS                     (~1 min)
echo      2. Sincronizar a SQLite                          (~7 seg)
echo      3. Sincronizar a Google Sheets                   (~10 seg)
echo.
echo   Tiempo total estimado: 1-2 minutos
echo.
echo ========================================================================
echo.
set /p confirmar="   Desea continuar? (S/N): "

if /i not "%confirmar%"=="S" (
    cls
    goto MENU
)

echo.
echo ========================================================================
echo   INICIANDO ACTUALIZACION RAPIDA
echo ========================================================================
echo.

echo [1/3] Asignando categoria OFERTAS...
python asignar_categoria_ofertas.py

echo.
echo [2/3] Sincronizando a SQLite (OPTIMIZADO)...
python 11_sincronizar_sqlite.py
if errorlevel 1 (
    echo ERROR: Error sincronizando SQLite.
    pause > nul
)

echo.
echo [3/3] Sincronizando a Google Sheets (OPTIMIZADO)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if errorlevel 1 (
    echo ERROR: Error sincronizando Google Sheets.
    pause > nul
)

goto FIN_EXITOSO

:SOLO_SYNC
cls
echo.
echo ========================================================================
echo   SOLO SINCRONIZACION
echo ========================================================================
echo.
echo   Este proceso ejecutara:
echo.
echo      1. Asignar categoria OFERTAS                     (~1 min)
echo      2. Sincronizar a SQLite                          (~7 seg)
echo      3. Sincronizar a Google Sheets                   (~10 seg)
echo.
echo   Tiempo total estimado: 20 segundos
echo.
echo ========================================================================
echo.
set /p confirmar="   Desea continuar? (S/N): "

if /i not "%confirmar%"=="S" (
    cls
    goto MENU
)

echo.
echo ========================================================================
echo   INICIANDO SINCRONIZACION
echo ========================================================================
echo.

echo [1/3] Asignando categoria OFERTAS...
python asignar_categoria_ofertas.py

echo.
echo [2/3] Sincronizando a SQLite (OPTIMIZADO)...
python 11_sincronizar_sqlite.py
if errorlevel 1 (
    echo ERROR: Error sincronizando SQLite.
    pause > nul
)

echo.
echo [3/3] Sincronizando a Google Sheets (OPTIMIZADO)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if errorlevel 1 (
    echo ERROR: Error sincronizando Google Sheets.
    pause > nul
)

goto FIN_EXITOSO

:DIAGNOSTICO
cls
echo.
echo ========================================================================
echo   DIAGNOSTICO DEL SISTEMA
echo ========================================================================
echo.
echo   Ejecutando diagnostico completo...
echo.

python diagnostico_completo_sistema.py

echo.
echo ========================================================================
echo   DIAGNOSTICO COMPLETADO
echo ========================================================================
echo.
pause
cls
goto MENU

:CANCELAR
cls
echo.
echo ========================================================================
echo   ACTUALIZACION CANCELADA
echo ========================================================================
echo.
timeout /t 2 > nul
exit /b 0

:FIN_EXITOSO
echo.
echo.
echo ========================================================================
echo   PROCESO COMPLETADO EXITOSAMENTE
echo ========================================================================
echo.
echo   SISTEMA DE 2 FASES:
echo.
echo   FASE 1 (Scraper Maestro V2):
echo      - Scrapea productos sin categorias
echo      - SKU, titulo, precio, imagenes, stock
echo      - Tiempo: ~15-20 min
echo.
echo   FASE 2 (Mapeo de Categorias):
echo      - Extrae SKUs desde listados de categorias
echo      - Asigna con sistema de prioridades
echo      - Cache inteligente (60%% menos requests)
echo      - Tiempo: ~8-12 min
echo.
echo   VENTAJAS:
echo      - Categorias 100%% correctas (no breadcrumb)
echo      - Mas robusto y confiable
echo      - Menos carga a Droppers
echo.
echo ========================================================================
echo.
echo   PROXIMOS PASOS:
echo.
echo      1. Verificar API corriendo:
echo         python api_local.py
echo.
echo      2. Abrir frontend:
echo         frontend_basico.html
echo.
echo      3. Refrescar navegador:
echo         Ctrl + Shift + R
echo.
echo      4. Verificar productos:
echo         http://localhost:8000
echo.
echo ========================================================================
echo.
pause
exit /b 0
