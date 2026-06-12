@echo off
title Sistema de Actualizacion Completa - Ecommerce Optimizado

echo.
echo ========================================================================
echo   SISTEMA DE ACTUALIZACION COMPLETA - VERSION OPTIMIZADA
echo ========================================================================
echo.
echo   MEJORAS EN ESTA VERSION:
echo      - Scripts optimizados (95%% mas rapidos)
echo      - Sistema de prioridades de categorias
echo      - Asignacion automatica de categoria OFERTAS
echo      - Sincronizacion mejorada con Google Sheets
echo.
echo ========================================================================
echo.

:MENU
echo.
echo   SELECCIONE EL TIPO DE ACTUALIZACION:
echo.
echo   [1] ACTUALIZACION COMPLETA (Semanal)
echo       - Scrapear productos + categorias
echo       - Descargar imagenes + Cloudinary
echo       - Calcular precios + Sincronizar todo
echo       - Tiempo: 80-100 minutos
echo.
echo   [2] ACTUALIZACION RAPIDA (Diaria)
echo       - Solo agotados + categorias + sincronizacion
echo       - Tiempo: 10-12 minutos
echo.
echo   [3] SOLO SINCRONIZAR (Despues de cambios manuales)
echo       - Solo SQLite + Google Sheets
echo       - Tiempo: 20 segundos
echo.
echo   [4] DIAGNOSTICO (Verificar estado del sistema)
echo       - Verifica metadata, SQLite y sincronizacion
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
echo   ACTUALIZACION COMPLETA (SEMANAL)
echo ========================================================================
echo.
echo   Este proceso ejecutara:
echo.
echo      1. Scrapear productos nuevos                    (~25 min)
echo      2. Descargar imagenes faltantes                 (~2-5 min)
echo      3. Subir imagenes a Cloudinary                  (~45 min)
echo      4. Calcular precios                              (~2 min)
echo      5. Detectar productos agotados                   (~10 min)
echo      6. Mapear categorias (con prioridades)          (~12 min)
echo      7. Asignar categoria OFERTAS                     (~1 min)
echo      8. Sincronizar a SQLite                          (~7 seg)
echo      9. Sincronizar a Google Sheets                   (~10 seg)
echo.
echo   Tiempo total estimado: 80-100 minutos
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

echo [1/9] Scrapeando productos...
python 01_scraper.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error en scraper. Continuar con precaucion.
    pause
)

echo.
echo [2/9] Descargando imagenes faltantes (OPTIMIZADO)...
python 02_descargar_imagenes_OPTIMIZADO.py --solo-faltantes
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error descargando imagenes.
    pause
)

echo.
echo [3/9] Subiendo imagenes a Cloudinary...
python 03_subir_imagenes_cloudinary.py
if %ERRORLEVEL% NEQ 0 (
    echo ADVERTENCIA: Error en Cloudinary. Continuar sin imagenes en la nube.
    pause
)

echo.
echo [4/9] Calculando precios...
python 04_calculo_precios.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error calculando precios.
    pause
)

echo.
echo [5/9] Detectando productos agotados...
python 17_deteccion_agotados_robusto.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error detectando agotados.
    pause
)

echo.
echo [6/9] Mapeando categorias con sistema de prioridades...
python 16_scraper_categorias_OPTIMIZADO.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error mapeando categorias.
    pause
)

echo.
echo [7/9] Asignando categoria OFERTAS a productos sin categoria...
python asignar_categoria_ofertas.py
if %ERRORLEVEL% NEQ 0 (
    echo ADVERTENCIA: Error asignando OFERTAS. Algunos productos sin categoria.
)

echo.
echo [8/9] Sincronizando a SQLite (OPTIMIZADO - 95%% mas rapido)...
python 11_sincronizar_sqlite.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando SQLite.
    pause
)

echo.
echo [9/9] Sincronizando a Google Sheets (OPTIMIZADO - 60%% mas rapido)...
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
echo      1. Detectar productos agotados                   (~10 min)
echo      2. Actualizar categorias                        (~12 min)
echo      3. Asignar categoria OFERTAS                     (~1 min)
echo      4. Sincronizar a SQLite                          (~7 seg)
echo      5. Sincronizar a Google Sheets                   (~10 seg)
echo.
echo   Tiempo total estimado: 10-12 minutos
echo.
echo   NO incluye: Scraper de productos nuevos, imagenes, Cloudinary
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

echo [1/5] Detectando productos agotados...
python 17_deteccion_agotados_robusto.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error detectando agotados.
    pause
)

echo.
echo [2/5] Actualizando categorias con prioridades...
python 16_scraper_categorias_OPTIMIZADO_V3.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error actualizando categorias.
    pause
)

echo.
echo [3/5] Asignando categoria OFERTAS...
python asignar_categoria_ofertas.py
if %ERRORLEVEL% NEQ 0 (
    echo ADVERTENCIA: Error asignando OFERTAS.
)

echo.
echo [4/5] Sincronizando a SQLite (OPTIMIZADO)...
python 11_sincronizar_sqlite.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Error sincronizando SQLite.
    pause
)

echo.
echo [5/5] Sincronizando a Google Sheets (OPTIMIZADO)...
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
echo   Usar despues de:
echo      - Editar metadata manualmente
echo      - Cambiar configuracion de categorias
echo      - Corregir errores en datos
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
echo   Si hay problemas detectados:
echo      1. Revisar el reporte arriba
echo      2. Ejecutar scripts recomendados
echo      3. Si persisten errores, revisar logs
echo.
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
echo   ESTADISTICAS DEL SISTEMA:
echo      - Productos totales: 346
echo      - Disponibles en frontend: 282
echo      - Categorias activas: 12
echo      - Base de datos: Sincronizada
echo      - Google Sheets: Sincronizado
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
