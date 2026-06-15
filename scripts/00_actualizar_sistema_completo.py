#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACTUALIZACIÓN MAESTRA DEL SISTEMA - VERSIÓN 3.0
Ejecuta todos los scripts en orden correcto con validaciones y manejo de errores

PIPELINE (flujo de 2 fases, basado en scraper_maestro_v2):
1. Detección de agotados/reingresados (17_deteccion_agotados_robusto.py)
2. Scraper de productos nuevos - FASE 1 sin categorías (scraper_maestro_v2_sin_categorias.py)
3. Mapeo de categorías - FASE 2 (mapear_categorias_post_scraping.py)
4. Asignación de categoría OFERTAS a disponibles sin categoría (asignar_categoria_ofertas.py)
5. Descarga de imágenes (02_descargar_imagenes_OPTIMIZADO.py)
6. Subida a Cloudinary (opcional) (03_subir_imagenes_cloudinary.py)
7. Cálculo de precios (04_calculo_precios.py)
8. Sincronización SQLite (11_sincronizar_sqlite.py)
9. Generación de páginas estáticas de producto / SEO (12_generar_paginas_producto.py)
10. Generación de feed Facebook/WhatsApp Catalog (generar_feed_facebook.py)
11. Sincronización Google Sheets / Facebook Catalog (opcional) (06_sincronizar_google_sheets_OPTIMIZADO.py)

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-06-12
VERSION: 3.0

USO:
    python 00_actualizar_sistema_completo.py

    Opciones:
    python 00_actualizar_sistema_completo.py --rapido          # Solo stock y precios
    python 00_actualizar_sistema_completo.py --completo        # Actualización completa (default)
    python 00_actualizar_sistema_completo.py --sin-scraper     # Sin scrapear productos nuevos
    python 00_actualizar_sistema_completo.py --con-cloudinary  # Incluye Cloudinary
    python 00_actualizar_sistema_completo.py --auto-push       # Publica catalogo.db (git commit + push) si hubo cambios
"""

import subprocess
import sys
import time
import sqlite3
from pathlib import Path
from datetime import datetime
import json

# Imports locales
sys.path.append(str(Path(__file__).parent))
from utils.logger import get_logger
from utils.config import Config

logger = get_logger('actualizacion_maestra')


class ActualizadorMaestro:
    """Orquesta la actualización completa del sistema"""
    
    def __init__(self, modo='completo', usar_cloudinary=False, auto_push=False):
        """
        Args:
            modo: 'completo', 'rapido', 'sin-scraper'
            usar_cloudinary: Si True, ejecuta Cloudinary
            auto_push: Si True, hace commit y push de data/catalogo.db al finalizar
        """
        self.modo = modo
        self.usar_cloudinary = usar_cloudinary
        self.auto_push = auto_push
        self.scripts_dir = Path(__file__).parent
        self.repo_dir = self.scripts_dir.parent
        self.inicio = datetime.now()
        
        # Estadísticas de ejecución
        self.stats = {
            'inicio': self.inicio.isoformat(),
            'modo': modo,
            'cloudinary': usar_cloudinary,
            'pasos_ejecutados': [],
            'pasos_exitosos': [],
            'pasos_fallidos': [],
            'errores': [],
            'advertencias': [],
            'tiempo_total': 0
        }
        
        # Scripts disponibles
        self.scripts = {
            'agotados': '17_deteccion_agotados_robusto.py',
            'alertas': '19_alertas_droppers.py',
            'scraper': 'scraper_maestro_v2_sin_categorias.py',
            'categorias': 'mapear_categorias_post_scraping.py',
            'ofertas': 'asignar_categoria_ofertas.py',
            'descarga_imagenes': '02_descargar_imagenes_OPTIMIZADO.py',
            'cloudinary': '03_subir_imagenes_cloudinary.py',
            'precios': '04_calculo_precios.py',
            'sqlite': '11_sincronizar_sqlite.py',
            'seo_ia': '13_optimizar_seo_ia.py',
            'paginas_producto': '12_generar_paginas_producto.py',
            'feed_facebook': 'generar_feed_facebook.py',
            'sheets': '06_sincronizar_google_sheets_OPTIMIZADO.py',
        }
    
    def banner(self, texto, char='='):
        """Imprime un banner"""
        ancho = 70
        print()
        print(char * ancho)
        print(f"  {texto}")
        print(char * ancho)
        print()
    
    def ejecutar_script(self, nombre, script, obligatorio=True, args=None):
        """
        Ejecuta un script de Python
        
        Args:
            nombre: Nombre descriptivo del paso
            script: Nombre del archivo .py
            obligatorio: Si es False, no aborta si falla
            args: Lista de argumentos adicionales
        
        Returns:
            bool: True si exitoso
        """
        self.banner(f"PASO: {nombre}", '-')
        
        script_path = self.scripts_dir / script
        
        if not script_path.exists():
            error = f"Script no encontrado: {script}"
            logger.error(error)
            print(f"❌ {error}")
            
            if obligatorio:
                self.stats['pasos_fallidos'].append(nombre)
                self.stats['errores'].append(error)
                return False
            else:
                self.stats['advertencias'].append(error)
                print(f"⏭️  Saltando paso no obligatorio...")
                return True
        
        print(f"🔄 Ejecutando: {script}")
        print(f"⏱️  Inicio: {datetime.now().strftime('%H:%M:%S')}\n")
        
        inicio_paso = time.time()
        
        try:
            # Preparar comando
            cmd = [sys.executable, str(script_path)]
            if args:
                cmd.extend(args)
            
            # Ejecutar el script
            result = subprocess.run(
                cmd,
                cwd=str(self.scripts_dir),
                capture_output=False,  # Mostrar output en tiempo real
                text=True,
                timeout=3600  # 1 hora de timeout
            )
            
            tiempo_paso = time.time() - inicio_paso
            
            if result.returncode == 0:
                print(f"\n✅ {nombre} completado en {tiempo_paso:.1f}s")
                logger.info(f"{nombre} exitoso ({tiempo_paso:.1f}s)")
                self.stats['pasos_exitosos'].append(nombre)
                self.stats['pasos_ejecutados'].append({
                    'nombre': nombre,
                    'script': script,
                    'exitoso': True,
                    'tiempo': tiempo_paso
                })
                return True
            else:
                error = f"{nombre} falló con código {result.returncode}"
                print(f"\n❌ {error}")
                logger.error(error)
                
                if obligatorio:
                    self.stats['pasos_fallidos'].append(nombre)
                    self.stats['errores'].append(error)
                    return False
                else:
                    self.stats['advertencias'].append(error)
                    print(f"⚠️  Error en paso no obligatorio, continuando...")
                    return True
        
        except subprocess.TimeoutExpired:
            error = f"{nombre} excedió el tiempo límite (1 hora)"
            print(f"\n⏱️ {error}")
            logger.error(error)
            
            if obligatorio:
                self.stats['pasos_fallidos'].append(nombre)
                self.stats['errores'].append(error)
                return False
            else:
                self.stats['advertencias'].append(error)
                return True
        
        except Exception as e:
            error = f"Error ejecutando {nombre}: {str(e)}"
            print(f"\n❌ {error}")
            logger.exception(error)
            
            if obligatorio:
                self.stats['pasos_fallidos'].append(nombre)
                self.stats['errores'].append(error)
                return False
            else:
                self.stats['advertencias'].append(error)
                return True
    
    def capturar_cambios_pre_sync(self):
        """
        Lee el reporte de agotados/reingresados/nuevos generado por el paso de
        detección (17_deteccion_agotados_robusto.py) y, para los agotados,
        busca sus nombres en catalogo.db ANTES de que 11_sincronizar_sqlite.py
        los borre de la tabla productos. Se usa luego para poblar
        historial_actualizaciones.
        """
        self.historial_agotados = []
        self.historial_reingresados_skus = []

        try:
            reportes = sorted(
                p for p in Config.DATA_DIR.glob('reporte_agotados_*.json')
                if not p.name.endswith('_FALLO.json')
            )
            if not reportes:
                return

            with open(reportes[-1], 'r', encoding='utf-8') as f:
                reporte = json.load(f)

            agotados_skus = reporte.get('agotados', {}).get('skus', [])
            self.historial_reingresados_skus = reporte.get('reingresados', {}).get('skus', [])

            if agotados_skus:
                db_path = Config.DATA_DIR / 'catalogo.db'
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(agotados_skus))
                cursor.execute(f"SELECT sku, nombre FROM productos WHERE sku IN ({placeholders})", agotados_skus)
                nombres = {fila[0]: fila[1] for fila in cursor.fetchall()}
                conn.close()
                self.historial_agotados = [
                    {'sku': sku, 'nombre': nombres.get(sku, '')} for sku in agotados_skus
                ]
        except Exception as e:
            logger.error(f"Error capturando cambios pre-sync para historial: {e}")

    def registrar_historial_actualizacion(self):
        """
        Guarda en historial_actualizaciones (tabla de catalogo.db) el resumen
        de esta corrida -total de productos y detalle de nuevos/agotados/
        reingresados- para mostrarlo en la pestaña Historial del Panel El Gadget.
        """
        try:
            db_path = Config.DATA_DIR / 'catalogo.db'
            if not db_path.exists():
                return

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS historial_actualizaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT DEFAULT (datetime('now')),
                    total_productos INTEGER DEFAULT 0,
                    nuevos_count INTEGER DEFAULT 0,
                    agotados_count INTEGER DEFAULT 0,
                    reingresados_count INTEGER DEFAULT 0,
                    nuevos_json TEXT DEFAULT '[]',
                    agotados_json TEXT DEFAULT '[]',
                    reingresados_json TEXT DEFAULT '[]',
                    exitoso INTEGER DEFAULT 1
                )
            """)

            cursor.execute("SELECT COUNT(*) FROM productos")
            total_productos = cursor.fetchone()[0]

            # Nuevos: SKUs agregados al catálogo en esta corrida
            nuevos_detalle = []
            nuevos_skus_file = Config.DATA_DIR / 'nuevos_skus.json'
            if nuevos_skus_file.exists():
                with open(nuevos_skus_file, 'r', encoding='utf-8') as f:
                    nuevos_skus = json.load(f)
                if nuevos_skus:
                    placeholders = ','.join('?' * len(nuevos_skus))
                    cursor.execute(f"SELECT sku, nombre FROM productos WHERE sku IN ({placeholders})", nuevos_skus)
                    nombres = {fila[0]: fila[1] for fila in cursor.fetchall()}
                    nuevos_detalle = [{'sku': sku, 'nombre': nombres.get(sku, '')} for sku in nuevos_skus]

            # Reingresados: vuelven a estar en la tabla productos (con stock) tras el sync
            reingresados_detalle = []
            reingresados_skus = getattr(self, 'historial_reingresados_skus', [])
            if reingresados_skus:
                placeholders = ','.join('?' * len(reingresados_skus))
                cursor.execute(f"SELECT sku, nombre FROM productos WHERE sku IN ({placeholders})", reingresados_skus)
                nombres = {fila[0]: fila[1] for fila in cursor.fetchall()}
                reingresados_detalle = [{'sku': sku, 'nombre': nombres.get(sku, '')} for sku in reingresados_skus]

            agotados_detalle = getattr(self, 'historial_agotados', [])

            exitoso = 1 if not self.stats['pasos_fallidos'] else 0

            cursor.execute("""
                INSERT INTO historial_actualizaciones
                    (total_productos, nuevos_count, agotados_count, reingresados_count,
                     nuevos_json, agotados_json, reingresados_json, exitoso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                total_productos,
                len(nuevos_detalle), len(agotados_detalle), len(reingresados_detalle),
                json.dumps(nuevos_detalle, ensure_ascii=False),
                json.dumps(agotados_detalle, ensure_ascii=False),
                json.dumps(reingresados_detalle, ensure_ascii=False),
                exitoso
            ))
            conn.commit()
            conn.close()

            print(f"\n📒 Historial de actualización registrado "
                  f"(nuevos: {len(nuevos_detalle)}, agotados: {len(agotados_detalle)}, "
                  f"reingresados: {len(reingresados_detalle)})")
        except Exception as e:
            logger.error(f"Error registrando historial de actualización: {e}")

    def optimizar_seo_productos_nuevos(self):
        """
        Optimiza el SEO (título y descripción) con IA solo para los productos
        nuevos detectados por 11_sincronizar_sqlite.py en este sync.
        """
        nuevos_skus_file = Config.DATA_DIR / 'nuevos_skus.json'

        if not nuevos_skus_file.exists():
            return

        try:
            with open(nuevos_skus_file, 'r', encoding='utf-8') as f:
                nuevos_skus = json.load(f)
        except Exception as e:
            logger.error(f"Error leyendo {nuevos_skus_file}: {e}")
            return

        if not nuevos_skus:
            print("\nℹ️  No hay productos nuevos para optimizar SEO")
            return

        self.ejecutar_script(
            f"9. Optimización SEO con IA de {len(nuevos_skus)} producto(s) nuevo(s)",
            self.scripts['seo_ia'],
            obligatorio=False,
            args=['--skus', ','.join(nuevos_skus)]
        )

    def verificar_resultado(self):
        """Verifica que la actualización fue exitosa"""
        self.banner("VERIFICACIÓN FINAL", '-')
        
        print("🔍 Verificando resultados...\n")
        
        # Verificar que existe catalogo.db
        db_path = Config.DATA_DIR / 'catalogo.db'
        if not db_path.exists():
            error = "Base de datos no fue creada"
            print(f"❌ {error}")
            self.stats['errores'].append(error)
            return False
        
        print(f"✅ Base de datos creada: {db_path}")
        
        # Verificar tamaño
        tamanio_kb = db_path.stat().st_size / 1024
        print(f"   Tamaño: {tamanio_kb:.1f} KB")
        
        if tamanio_kb < 10:
            advertencia = "Base de datos muy pequeña (< 10 KB)"
            print(f"⚠️  {advertencia}")
            self.stats['advertencias'].append(advertencia)
        
        # Verificar productos
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM productos")
            total = cursor.fetchone()[0]
            conn.close()
            
            print(f"✅ Total productos en DB: {total}")
            
            if total == 0:
                error = "Base de datos sin productos"
                print(f"❌ {error}")
                self.stats['errores'].append(error)
                return False
            
            if total < 50:
                advertencia = f"Pocos productos en DB ({total})"
                print(f"⚠️  {advertencia}")
                self.stats['advertencias'].append(advertencia)
            
        except Exception as e:
            error = f"Error verificando DB: {e}"
            print(f"❌ {error}")
            self.stats['errores'].append(error)
            return False
        
        print("\n✅ Verificación completada")
        return True

    def git_push_catalogo(self):
        """Publica catalogo.db, el feed Facebook/WhatsApp y el estado de productos/precios (git add + commit + push) si hubo cambios"""
        self.banner("PUBLICACIÓN DE CAMBIOS (git push)", '-')

        rutas = [
            'data/catalogo.db',
            'pages/facebook_catalog.csv',
            'data/productos',
            'data/precios',
            'pages/producto',
            'pages/sitemap.xml',
        ]

        try:
            # Detectar si hay cambios respecto al último commit (respeta .gitignore)
            result = subprocess.run(
                ['git', 'status', '--porcelain', *rutas],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True
            )

            if not result.stdout.strip():
                print("ℹ️  Sin cambios para publicar")
                return True

            subprocess.run(
                ['git', 'add', '-A', '--', *rutas],
                cwd=str(self.repo_dir),
                check=True
            )

            mensaje = f"Actualización automática del catálogo - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(
                ['git', 'commit', '-m', mensaje],
                cwd=str(self.repo_dir),
                check=True
            )

            subprocess.run(
                ['git', 'push'],
                cwd=str(self.repo_dir),
                check=True
            )

            print("✅ catalogo.db publicado (commit + push)")
            return True

        except subprocess.CalledProcessError as e:
            error = f"Error publicando catalogo.db: {e}"
            print(f"❌ {error}")
            logger.error(error)
            self.stats['advertencias'].append(error)
            return False

    def guardar_reporte(self):
        """Guarda reporte de la ejecución"""
        fin = datetime.now()
        self.stats['fin'] = fin.isoformat()
        self.stats['tiempo_total'] = (fin - self.inicio).total_seconds()
        
        reporte_file = Config.DATA_DIR / f'reporte_actualizacion_{fin.strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte guardado: {reporte_file}")
    
    def mostrar_resumen(self):
        """Muestra resumen de la ejecución"""
        self.banner("RESUMEN DE ACTUALIZACIÓN")
        
        fin = datetime.now()
        tiempo_total = (fin - self.inicio).total_seconds()
        minutos = int(tiempo_total // 60)
        segundos = int(tiempo_total % 60)
        
        print(f"⏱️  Tiempo total: {minutos}m {segundos}s")
        print(f"✅ Pasos exitosos: {len(self.stats['pasos_exitosos'])}")
        print(f"❌ Pasos fallidos: {len(self.stats['pasos_fallidos'])}")
        print(f"⚠️  Advertencias: {len(self.stats['advertencias'])}")
        
        if self.stats['pasos_exitosos']:
            print("\n✅ COMPLETADOS:")
            for paso in self.stats['pasos_exitosos']:
                print(f"   • {paso}")
        
        if self.stats['pasos_fallidos']:
            print("\n❌ FALLIDOS:")
            for paso in self.stats['pasos_fallidos']:
                print(f"   • {paso}")
        
        if self.stats['advertencias']:
            print("\n⚠️  ADVERTENCIAS:")
            for adv in self.stats['advertencias'][:5]:  # Mostrar máximo 5
                print(f"   • {adv}")
        
        print("\n" + "="*70)
        
        if len(self.stats['pasos_fallidos']) == 0:
            print("🎉 ACTUALIZACIÓN COMPLETADA EXITOSAMENTE")
        else:
            print("⚠️  ACTUALIZACIÓN COMPLETADA CON ERRORES")
        
        print("="*70 + "\n")
    
    def actualizar_completo(self):
        """Actualización completa del sistema"""
        self.banner("ACTUALIZACIÓN COMPLETA DEL SISTEMA")
        
        print(f"📅 Fecha: {self.inicio.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🔧 Modo: {self.modo}")
        print(f"☁️  Cloudinary: {'Sí' if self.usar_cloudinary else 'No'}")
        print()
        
        # PASO 1: Detectar agotados/reingresados en Droppers
        if not self.ejecutar_script(
            "1. Detección de agotados",
            self.scripts['agotados'],
            obligatorio=True,
            args=['--auto']
        ):
            print("\n⛔ Abortando actualización por error crítico")
            return False

        # Capturar agotados/reingresados (con nombres) antes de que el sync los modifique
        self.capturar_cambios_pre_sync()

        # PASO 1.5: Alertas de Droppers (productos nuevos y cambios de precio)
        if self.modo == 'completo':
            self.ejecutar_script(
                "1.5 Alertas de Droppers (productos nuevos y cambios de precio)",
                self.scripts['alertas'],
                obligatorio=False,
                args=['--auto']
            )
        else:
            print(f"\n⏭️  Saltando alertas de Droppers (modo: {self.modo})")

        # PASO 2: Scrapear productos nuevos - FASE 1 sin categorías (opcional según modo)
        scraper_ejecutado = False
        if self.modo == 'completo':
            scraper_ejecutado = self.ejecutar_script(
                "2. Scraper de productos nuevos (Fase 1)",
                self.scripts['scraper'],
                obligatorio=False  # No obligatorio, puede no haber nuevos
            )
        else:
            print(f"\n⏭️  Saltando scraper (modo: {self.modo})")

        # PASO 3: Mapear categorías - FASE 2 (solo si hubo scraping)
        if self.modo == 'completo' and scraper_ejecutado:
            self.ejecutar_script(
                "3. Mapeo de categorías (Fase 2)",
                self.scripts['categorias'],
                obligatorio=False
            )
        elif self.modo == 'completo':
            print("\n⏭️  Saltando mapeo de categorías (el scraper no se ejecutó)")

        # PASO 4: Asignar categoría OFERTAS a disponibles sin categoría (fallback)
        if self.modo == 'completo':
            self.ejecutar_script(
                "4. Asignación de categoría OFERTAS",
                self.scripts['ofertas'],
                obligatorio=False
            )
        else:
            print(f"\n⏭️  Saltando asignación de categoría OFERTAS (modo: {self.modo})")

        # PASO 5: Descargar imágenes (solo productos sin imágenes)
        if self.modo == 'completo':
            self.ejecutar_script(
                "5. Descarga de imágenes",
                self.scripts['descarga_imagenes'],
                obligatorio=False,
                args=['--silencioso']  # Ejecutar sin confirmación
            )

        # PASO 6: Subir imágenes a Cloudinary (opcional)
        if self.modo == 'completo' and self.usar_cloudinary:
            self.ejecutar_script(
                "6. Subir imágenes a Cloudinary",
                self.scripts['cloudinary'],
                obligatorio=False
            )
        elif self.usar_cloudinary:
            print(f"\n⏭️  Cloudinary solo disponible en modo completo")
        else:
            print(f"\n⏭️  Saltando Cloudinary (no solicitado)")

        # PASO 7: Calcular precios
        if not self.ejecutar_script(
            "7. Cálculo de precios",
            self.scripts['precios'],
            obligatorio=True,
            args=['--silencioso']
        ):
            print("\n⛔ Abortando actualización por error crítico")
            return False

        # PASO 8: Sincronizar a SQLite
        if not self.ejecutar_script(
            "8. Sincronización a SQLite",
            self.scripts['sqlite'],
            obligatorio=True
        ):
            print("\n⛔ Actualización falló en sincronización")
            return False

        # Registrar en el historial (pestaña "Historial" del Panel El Gadget)
        self.registrar_historial_actualizacion()

        # PASO 9: Optimizar SEO con IA de productos nuevos detectados en este sync
        self.optimizar_seo_productos_nuevos()

        # PASO 10: Generar páginas estáticas de producto (SEO)
        self.ejecutar_script(
            "10. Generación de páginas estáticas de producto (SEO)",
            self.scripts['paginas_producto'],
            obligatorio=False
        )

        # PASO 11: Generar feed de Facebook/WhatsApp Catalog
        self.ejecutar_script(
            "11. Generación de feed Facebook/WhatsApp",
            self.scripts['feed_facebook'],
            obligatorio=False
        )

        # PASO 12: Sincronizar Google Sheets / Facebook Catalog (opcional)
        sheets_script = self.scripts_dir / self.scripts.get('sheets', '')
        if sheets_script and sheets_script.exists():
            self.ejecutar_script(
                "12. Sincronización a Google Sheets / Facebook Catalog",
                self.scripts['sheets'],
                obligatorio=False
            )
        else:
            print("\n⏭️  Google Sheets no disponible (script no encontrado)")

        # PASO 13: Verificar resultado
        if not self.verificar_resultado():
            print("\n⚠️  Verificación falló, revisar manualmente")

        # PASO 14: Publicar catalogo.db (opcional)
        if self.auto_push:
            self.git_push_catalogo()
        else:
            print("\n⏭️  Saltando publicación (usar --auto-push para hacer git push)")

        return True

    def actualizar_rapido(self):
        """Actualización rápida (solo stock y precios)"""
        self.banner("ACTUALIZACIÓN RÁPIDA (Stock y Precios)")

        # Solo ejecutar lo esencial
        if not self.ejecutar_script(
            "1. Detección de agotados",
            self.scripts['agotados'],
            obligatorio=True,
            args=['--auto']
        ):
            return False

        # Capturar agotados/reingresados (con nombres) antes de que el sync los modifique
        self.capturar_cambios_pre_sync()

        if not self.ejecutar_script(
            "2. Cálculo de precios",
            self.scripts['precios'],
            obligatorio=True,
            args=['--silencioso']
        ):
            return False

        if not self.ejecutar_script(
            "3. Sincronización a SQLite",
            self.scripts['sqlite'],
            obligatorio=True
        ):
            return False

        # Registrar en el historial (pestaña "Historial" del Panel El Gadget)
        self.registrar_historial_actualizacion()

        # PASO 4: Optimizar SEO con IA de productos nuevos detectados en este sync
        self.optimizar_seo_productos_nuevos()

        # PASO 5: Generar páginas estáticas de producto (SEO)
        self.ejecutar_script(
            "5. Generación de páginas estáticas de producto (SEO)",
            self.scripts['paginas_producto'],
            obligatorio=False
        )

        if not self.verificar_resultado():
            print("\n⚠️  Verificación falló, revisar manualmente")

        # PASO 6: Publicar catalogo.db (opcional)
        if self.auto_push:
            self.git_push_catalogo()
        else:
            print("\n⏭️  Saltando publicación (usar --auto-push para hacer git push)")

        return True
    
    def ejecutar(self):
        """Ejecuta la actualización según el modo"""
        try:
            if self.modo == 'rapido':
                exitoso = self.actualizar_rapido()
            else:
                exitoso = self.actualizar_completo()
            
            # Guardar reporte
            self.guardar_reporte()
            
            # Mostrar resumen
            self.mostrar_resumen()
            
            return exitoso
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Actualización interrumpida por el usuario")
            logger.warning("Actualización interrumpida")
            self.guardar_reporte()
            return False
        
        except Exception as e:
            print(f"\n❌ Error fatal: {e}")
            logger.exception("Error fatal en actualización")
            self.stats['errores'].append(f"Error fatal: {e}")
            self.guardar_reporte()
            return False


def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Actualización completa del sistema de ecommerce'
    )
    parser.add_argument(
        '--modo',
        choices=['completo', 'rapido', 'sin-scraper'],
        default='completo',
        help='Modo de actualización (default: completo)'
    )
    parser.add_argument(
        '--rapido',
        action='store_true',
        help='Atajo para --modo rapido'
    )
    parser.add_argument(
        '--sin-scraper',
        action='store_true',
        help='Atajo para --modo sin-scraper'
    )
    parser.add_argument(
        '--con-cloudinary',
        action='store_true',
        help='Incluir subida a Cloudinary'
    )
    parser.add_argument(
        '--auto-push',
        action='store_true',
        help='Publicar data/catalogo.db (git commit + push) si hubo cambios'
    )

    args = parser.parse_args()

    # Determinar modo
    if args.rapido:
        modo = 'rapido'
    elif args.sin_scraper:
        modo = 'sin-scraper'
    else:
        modo = args.modo

    # Ejecutar
    actualizador = ActualizadorMaestro(
        modo=modo,
        usar_cloudinary=args.con_cloudinary,
        auto_push=args.auto_push
    )
    exitoso = actualizador.ejecutar()
    
    # Exit code
    sys.exit(0 if exitoso else 1)


if __name__ == "__main__":
    main()
