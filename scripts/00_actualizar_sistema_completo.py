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
9. Generación de feed Facebook/WhatsApp Catalog (generar_feed_facebook.py)
10. Sincronización Google Sheets / Facebook Catalog (opcional) (06_sincronizar_google_sheets_OPTIMIZADO.py)

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
            'scraper': 'scraper_maestro_v2_sin_categorias.py',
            'categorias': 'mapear_categorias_post_scraping.py',
            'ofertas': 'asignar_categoria_ofertas.py',
            'descarga_imagenes': '02_descargar_imagenes_OPTIMIZADO.py',
            'cloudinary': '03_subir_imagenes_cloudinary.py',
            'precios': '04_calculo_precios.py',
            'sqlite': '11_sincronizar_sqlite.py',
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
    
    def borrar_base_datos(self):
        """Borra la base de datos SQLite para reconstruirla"""
        db_path = Config.DATA_DIR / 'catalogo.db'
        
        if db_path.exists():
            try:
                db_path.unlink()
                print("✅ Base de datos antigua eliminada")
                logger.info("Base de datos borrada")
                return True
            except Exception as e:
                error = f"Error borrando DB: {e}"
                print(f"❌ {error}")
                logger.error(error)
                self.stats['errores'].append(error)
                return False
        else:
            print("ℹ️  No existe base de datos previa")
            return True
    
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
        """Publica data/catalogo.db y el feed de Facebook/WhatsApp (git add + commit + push) si hubo cambios"""
        self.banner("PUBLICACIÓN DE CAMBIOS (git push)", '-')

        archivos = ['data/catalogo.db', 'pages/facebook_catalog.csv']

        try:
            # Detectar si hay cambios respecto al último commit
            result = subprocess.run(
                ['git', 'status', '--porcelain', *archivos],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True
            )

            if not result.stdout.strip():
                print("ℹ️  Sin cambios en catalogo.db ni en el feed, nada para publicar")
                return True

            subprocess.run(
                ['git', 'add', *archivos],
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

        # PASO 8: Borrar base de datos
        self.banner("8. Preparación de base de datos", '-')
        if not self.borrar_base_datos():
            print("\n⚠️  No se pudo borrar DB, continuando...")

        # PASO 9: Sincronizar a SQLite
        if not self.ejecutar_script(
            "9. Sincronización a SQLite",
            self.scripts['sqlite'],
            obligatorio=True
        ):
            print("\n⛔ Actualización falló en sincronización")
            return False

        # PASO 10: Generar feed de Facebook/WhatsApp Catalog
        self.ejecutar_script(
            "10. Generación de feed Facebook/WhatsApp",
            self.scripts['feed_facebook'],
            obligatorio=False
        )

        # PASO 11: Sincronizar Google Sheets / Facebook Catalog (opcional)
        sheets_script = self.scripts_dir / self.scripts.get('sheets', '')
        if sheets_script and sheets_script.exists():
            self.ejecutar_script(
                "11. Sincronización a Google Sheets / Facebook Catalog",
                self.scripts['sheets'],
                obligatorio=False
            )
        else:
            print("\n⏭️  Google Sheets no disponible (script no encontrado)")

        # PASO 12: Verificar resultado
        if not self.verificar_resultado():
            print("\n⚠️  Verificación falló, revisar manualmente")

        # PASO 13: Publicar catalogo.db (opcional)
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

        if not self.ejecutar_script(
            "2. Cálculo de precios",
            self.scripts['precios'],
            obligatorio=True,
            args=['--silencioso']
        ):
            return False

        self.banner("3. Preparación de base de datos", '-')
        if not self.borrar_base_datos():
            print("\n⚠️  No se pudo borrar DB, continuando...")

        if not self.ejecutar_script(
            "4. Sincronización a SQLite",
            self.scripts['sqlite'],
            obligatorio=True
        ):
            return False

        if not self.verificar_resultado():
            print("\n⚠️  Verificación falló, revisar manualmente")

        # PASO 5: Publicar catalogo.db (opcional)
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
