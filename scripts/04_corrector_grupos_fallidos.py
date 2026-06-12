#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CORRECTOR DE GRUPOS FALLIDOS
Reorganiza los grupos que fallaron en el organizador principal
"""

import json
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('corrector_grupos')


class CorrectorGruposFallidos:
    """Corrige grupos que fallaron en la organización inicial"""
    
    def __init__(self, archivo_variantes: Path):
        """
        Inicializa el corrector
        
        Args:
            archivo_variantes: Path al archivo de variantes confirmadas
        """
        self.archivo_variantes = archivo_variantes
        self.grupos_fallidos = []
        
        self.estadisticas = {
            'grupos_procesados': 0,
            'imagenes_movidas': 0,
            'carpetas_creadas': 0,
            'errores': 0
        }
        
        logger.info("Corrector de grupos fallidos inicializado")
    
    def sanitizar_nombre_carpeta(self, nombre: str) -> str:
        """
        Sanitiza un nombre para que sea válido como carpeta en Windows
        
        Args:
            nombre: Nombre original
        
        Returns:
            str: Nombre sanitizado
        """
        # Caracteres no permitidos en Windows: < > : " / \ | ? *
        caracteres_invalidos = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        
        nombre_limpio = nombre
        for char in caracteres_invalidos:
            nombre_limpio = nombre_limpio.replace(char, '_')
        
        # Eliminar espacios múltiples
        nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
        
        # Eliminar guiones bajos múltiples
        nombre_limpio = re.sub(r'_+', '_', nombre_limpio)
        
        # Si quedó vacío o solo símbolos, usar "variante"
        if not nombre_limpio or nombre_limpio.replace('_', '').replace(' ', '').strip() == '':
            nombre_limpio = 'variante'
        
        return nombre_limpio
    
    def extraer_sku_base(self, skus: List[str]) -> str:
        """
        Extrae el SKU base de un grupo de variantes
        
        Args:
            skus: Lista de SKUs
        
        Returns:
            str: SKU base
        """
        if not skus:
            return 'grupo'
        
        sku = skus[0]
        
        # Remover sufijos comunes de variantes
        # Patrones: -XX, -XXX, -XXXX al final
        sku_base = re.sub(r'-[A-Z0-9]{1,4}$', '', sku)
        
        # Si no cambió nada, devolver original
        if sku_base == sku or not sku_base:
            return sku
        
        return sku_base
    
    def identificar_grupos_fallidos(self, log_file: Path = None) -> List[str]:
        """
        Identifica grupos que fallaron leyendo el log
        
        Args:
            log_file: Path al archivo de log (opcional)
        
        Returns:
            list: IDs de grupos que fallaron
        """
        grupos_con_error = []
        
        if log_file and log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                for linea in f:
                    if 'ERROR' in linea and 'Error procesando grupo' in linea:
                        # Extraer ID del grupo
                        match = re.search(r'grupo_(\d+)', linea)
                        if match:
                            grupo_id = f"grupo_{match.group(1)}"
                            if grupo_id not in grupos_con_error:
                                grupos_con_error.append(grupo_id)
                                logger.info(f"Detectado error en: {grupo_id}")
        
        return grupos_con_error
    
    def cargar_grupos_fallidos(self, ids_fallidos: List[str] = None):
        """
        Carga los grupos que fallaron
        
        Args:
            ids_fallidos: Lista de IDs de grupos fallidos (opcional)
        """
        with open(self.archivo_variantes, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        grupos_confirmados = datos.get('grupos_confirmados', [])
        
        # Si no se especifican IDs, cargar todos los grupos aprobados/manuales
        if not ids_fallidos:
            logger.info("Cargando TODOS los grupos (modo recuperación completa)")
            
            for grupo in grupos_confirmados:
                if grupo.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']:
                    self.grupos_fallidos.append({
                        'id_grupo': grupo.get('id_grupo'),
                        'nombre': grupo.get('producto_base', 'Grupo'),
                        'tipo_variante': grupo.get('atributo_variante'),
                        'skus': grupo.get('skus', []),
                        'valores_variantes': grupo.get('valores_variantes', {})
                    })
        else:
            logger.info(f"Cargando {len(ids_fallidos)} grupos específicos")
            
            for grupo in grupos_confirmados:
                if grupo.get('id_grupo') in ids_fallidos:
                    self.grupos_fallidos.append({
                        'id_grupo': grupo.get('id_grupo'),
                        'nombre': grupo.get('producto_base', 'Grupo'),
                        'tipo_variante': grupo.get('atributo_variante'),
                        'skus': grupo.get('skus', []),
                        'valores_variantes': grupo.get('valores_variantes', {})
                    })
        
        logger.info(f"✅ {len(self.grupos_fallidos)} grupos cargados para corrección")
    
    def obtener_nombre_variante_seguro(self, sku: str, grupo: Dict) -> str:
        """
        Obtiene un nombre de variante seguro para usar como carpeta
        
        Args:
            sku: SKU de la variante
            grupo: Datos del grupo
        
        Returns:
            str: Nombre seguro de la variante
        """
        valores = grupo.get('valores_variantes', {})
        
        # Si hay un valor personalizado
        if sku in valores:
            nombre = valores[sku]
            
            # Si es '?' o vacío, usar el SKU completo
            if nombre == '?' or not nombre or nombre.strip() == '':
                logger.debug(f"  Valor '{nombre}' inválido para {sku}, usando SKU")
                return sku
            
            # Sanitizar el nombre
            nombre_limpio = self.sanitizar_nombre_carpeta(nombre)
            
            # Si después de sanitizar quedó inválido, usar SKU
            if nombre_limpio in ['_', 'variante']:
                logger.debug(f"  Nombre sanitizado inválido, usando SKU: {sku}")
                return sku
            
            return nombre_limpio
        
        # Si no hay valor personalizado, usar el SKU
        return sku
    
    def reorganizar_grupo(self, grupo: Dict, num: int, total: int):
        """
        Reorganiza un grupo fallido
        
        Args:
            grupo: Datos del grupo
            num: Número de grupo actual
            total: Total de grupos
        """
        logger.info(f"[{num}/{total}] {grupo['nombre']}")
        print(f"[{num}/{total}] {grupo['nombre']}")
        
        try:
            skus = grupo['skus']
            sku_base = self.extraer_sku_base(skus)
            
            logger.info(f"  SKU base: {sku_base}")
            logger.info(f"  Variantes: {len(skus)}")
            
            # Crear carpeta base
            dir_base = Config.PRODUCTOS_DIR / sku_base
            dir_base.mkdir(parents=True, exist_ok=True)
            
            # Organizar cada variante
            for sku in skus:
                # Obtener nombre seguro
                nombre_variante = self.obtener_nombre_variante_seguro(sku, grupo)
                
                logger.info(f"  Procesando: {sku} → {nombre_variante}/")
                
                # Carpeta de la variante
                dir_variante = dir_base / nombre_variante
                dir_variante.mkdir(parents=True, exist_ok=True)
                self.estadisticas['carpetas_creadas'] += 1
                
                # Carpeta origen
                dir_origen = Config.PRODUCTOS_DIR / sku / 'imagenes_originales'
                
                if not dir_origen.exists():
                    logger.warning(f"    ⚠️  No existe: {dir_origen}")
                    continue
                
                # Copiar imágenes
                imagenes = sorted(dir_origen.glob('img_*'))
                
                if not imagenes:
                    logger.warning(f"    ⚠️  Sin imágenes en: {dir_origen}")
                    continue
                
                for img in imagenes:
                    destino = dir_variante / img.name
                    
                    if not destino.exists():
                        shutil.copy2(img, destino)
                        self.estadisticas['imagenes_movidas'] += 1
                
                logger.info(f"    ✅ {len(imagenes)} imágenes copiadas")
                print(f"    ✅ {len(imagenes)} imágenes → {nombre_variante}/")
            
            self.estadisticas['grupos_procesados'] += 1
            
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            print(f"  ❌ Error: {e}")
            self.estadisticas['errores'] += 1
    
    def corregir_todos(self):
        """Corrige todos los grupos fallidos"""
        if not self.grupos_fallidos:
            print("\n⚠️  No hay grupos para corregir")
            return
        
        print(f"\n{'=' * 80}")
        print(f"🔧 CORRIGIENDO {len(self.grupos_fallidos)} GRUPOS")
        print(f"{'=' * 80}\n")
        
        for i, grupo in enumerate(self.grupos_fallidos, 1):
            self.reorganizar_grupo(grupo, i, len(self.grupos_fallidos))
        
        self.mostrar_resumen()
        self.generar_reporte()
    
    def mostrar_resumen(self):
        """Muestra resumen de la corrección"""
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE CORRECCIÓN")
        print(f"{'=' * 80}")
        print(f"\n✅ Grupos corregidos: {self.estadisticas['grupos_procesados']}")
        print(f"📁 Carpetas creadas: {self.estadisticas['carpetas_creadas']}")
        print(f"📷 Imágenes copiadas: {self.estadisticas['imagenes_movidas']}")
        
        if self.estadisticas['errores'] > 0:
            print(f"\n❌ Errores: {self.estadisticas['errores']}")
        
        print(f"\n{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_correccion_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'archivo_variantes': str(self.archivo_variantes),
            'estadisticas': self.estadisticas,
            'grupos_corregidos': len(self.grupos_fallidos)
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte: {reporte_file}")
        logger.info(f"Reporte guardado: {reporte_file}")


def main():
    """Ejecuta el corrector"""
    print("=" * 80)
    print("🔧 CORRECTOR DE GRUPOS FALLIDOS")
    print("=" * 80)
    
    # Buscar archivo de variantes
    archivos_variantes = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_variantes:
        print("\n❌ No se encontró archivo de variantes")
        return
    
    archivo = archivos_variantes[0]
    print(f"\n📄 Archivo de variantes: {archivo.name}")
    
    # Buscar log más reciente del organizador
    logs_organizador = sorted(
        Config.LOGS_DIR.glob("organizador_imagenes_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    print(f"\n{'─' * 80}")
    print("📋 OPCIONES:")
    print("  1️⃣  Corregir solo grupos que fallaron (según log)")
    print("  2️⃣  Procesar TODOS los grupos (modo recuperación completa)")
    print(f"{'─' * 80}")
    
    opcion = input("\nSeleccionar opción (1/2): ").strip()
    
    corrector = CorrectorGruposFallidos(archivo)
    
    if opcion == '1' and logs_organizador:
        log_file = logs_organizador[0]
        print(f"\n📄 Usando log: {log_file.name}")
        
        # Identificar grupos fallidos
        ids_fallidos = corrector.identificar_grupos_fallidos(log_file)
        
        if not ids_fallidos:
            print("\n✅ No se detectaron grupos con errores en el log")
            print("   ¿Ejecutar modo recuperación completa? (s/n): ", end='')
            if input().lower() == 's':
                corrector.cargar_grupos_fallidos()
            else:
                return
        else:
            print(f"\n⚠️  Detectados {len(ids_fallidos)} grupos con errores")
            corrector.cargar_grupos_fallidos(ids_fallidos)
    
    elif opcion == '2':
        print("\n🔄 Modo recuperación completa activado")
        corrector.cargar_grupos_fallidos()
    
    else:
        print("\n❌ Opción inválida o no hay logs disponibles")
        return
    
    if not corrector.grupos_fallidos:
        print("\n⚠️  No hay grupos para procesar")
        return
    
    print(f"\n📊 Grupos a corregir: {len(corrector.grupos_fallidos)}")
    
    confirmar = input("\n¿Iniciar corrección? (s/n): ").lower()
    
    if confirmar == 's':
        corrector.corregir_todos()
    else:
        print("\nCorrección cancelada")


if __name__ == "__main__":
    main()
