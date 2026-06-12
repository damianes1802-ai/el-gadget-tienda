@echo off
title Sistema de Actualizacion - Scraper Maestro Unificado

echo.
echo ========================================================================
echo   SISTEMA DE ACTUALIZACION - CON SCRAPER MAESTRO UNIFICADO
echo ========================================================================
echo.
echo   NUEVA VERSION CON SCRAPER MAESTRO:
echo      - 1 sola visita por producto (vs 3 visitas antes)
echo      - 60%% mas rapido en scraping (15-20 min vs 47 min)
echo      - Obtiene TODO: SKU, titulo, precio, categorias, stock
echo      - Sistema de prioridades integrado
echo.
echo ========================================================================
echo.

:MENU
echo.
echo   SELECCIONE EL TIPO DE ACTUALIZACION:
echo.
echo   [1] ACTUALIZACION COMPLETA (Semanal)
echo       - Scraper Maestro Unificado (TODO en 1)
echo       - Descargar imagenes + Cloudinary
echo       - Calcular precios + Sincronizar
echo       - Tiempo: 65-75 minutos (vs 100 min antes)
echo       - AHORRO: 25-35 minutos
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
echo   ACTUALIZACION COMPLETA CON SCRAPER MAESTRO
echo ========================================================================
echo.
echo   Este proceso ejecutara:
echo.
echo      1. Scraper Maestro Unificado                    (~15-20 min)
echo         Obtiene TODO en 1 visita:
echo         - SKU, titulo, precio, descripcion, imagenes
echo         - Categorias (con prioridades)
echo         - Disponibilidad/stock
echo.
echo      2. Descargar imagenes faltantes                 (~2-5 min)
echo      3. Subir imagenes a Cloudinary                  (~45 min)
echo      4. Calcular precios                              (~2 min)
echo      5. Asignar categoria OFERTAS                     (~1 min)
echo      6. Sincronizar a SQLite                          (~7 seg)
echo      7. Sincronizar a Google Sheets                   (~10 seg)
echo.
echo   Tiempo total estimado: 65-75 minutos
echo   (vs 100 minutos con scripts separados)
echo.
echo   AHORRO DE TIEMPO: 25-35 minutos
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
echo   INICIANDO ACTUALIZACION COMPLETA
echo ========================================================================
echo.

echo [1/7] Ejecutando Scraper Maestro Unificado...
echo       Esto puede tardar 15-20 minutos. Por favor espere...
echo.
python scraper_maestro_unificado.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error en Scraper Maestro.
    pause
)

echo.
echo [2/7] Descargando imagenes faltantes (OPTIMIZADO)...
python 02_descargar_imagenes_OPTIMIZADO.py --solo-faltantes
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error descargando imagenes.
    pause
)

echo.
echo [3/7] Subiendo imagenes a Cloudinary...
echo       Esto puede tardar 45 minutos. Por favor espere...
python 03_subir_imagenes_cloudinary.py
if %ERRORLEVEL% NEQ 0 (
    echo ADVERTENCIA: Error en Cloudinary. Continuar sin imagenes en la nube.
    pause
)

echo.
echo [4/7] Calculando precios...
python 04_calculo_precios.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error calculando precios.
    pause
)

echo.
echo [5/7] Asignando categoria OFERTAS a productos sin categoria...
python asignar_categoria_ofertas.py
if %ERRORLEVEL% NEQ 0 (
    echo ADVERTENCIA: Error asignando OFERTAS.
)

echo.
echo [6/7] Sincronizando a SQLite (OPTIMIZADO - 95%% mas rapido)...
python 11_sincronizar_sqlite.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando SQLite.
    pause
)

echo.
echo [7/7] Sincronizando a Google Sheets (OPTIMIZADO - 60%% mas rapido)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando Google Sheets.
    pause
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
echo   NOTA: No scrapea productos nuevos.
echo         Usar Opcion [1] si hay productos nuevos en Droppers.
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
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando SQLite.
    pause
)

echo.
echo [3/3] Sincronizando a Google Sheets (OPTIMIZADO)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando Google Sheets.
    pause
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
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando SQLite.
    pause
)

echo.
echo [3/3] Sincronizando a Google Sheets (OPTIMIZADO)...
python 06_sincronizar_google_sheets_OPTIMIZADO.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando Google Sheets.
    pause
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
echo   COMPARATIVA DE TIEMPOS:
echo.
echo   ANTES (scripts separados):
echo      - Scraping: ~47 minutos (3 visitas por producto)
echo      - Total: ~100 minutos
echo.
echo   AHORA (Scraper Maestro):
echo      - Scraping: ~15-20 minutos (1 visita por producto)
echo      - Total: ~65-75 minutos
echo.
echo   AHORRO: ~25-35 minutos por actualizacion completa
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
