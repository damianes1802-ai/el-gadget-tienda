#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORGANIZADOR DE IMÁGENES POR VARIANTES
Reorganiza imágenes descargadas en estructura de variantes
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('organizador_imagenes')


class OrganizadorImagenes:
    """Organiza imágenes en estructura de variantes"""
    
    def __init__(self, archivo_variantes: Path):
        """
        Inicializa el organizador
        
        Args:
            archivo_variantes: Path al archivo de variantes confirmadas
        """
        self.archivo_variantes = archivo_variantes
        self.grupos = []
        self.estadisticas = {
            'grupos_procesados': 0,
            'imagenes_movidas': 0,
            'imagenes_comunes_identificadas': 0,
            'carpetas_creadas': 0,
            'errores': 0
        }
        
        self.cargar_variantes()
        
        logger.info("Organizador de imágenes inicializado")
    
    def cargar_variantes(self):
        """Carga grupos de variantes desde el archivo"""
        with open(self.archivo_variantes, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        grupos_confirmados = datos.get('grupos_confirmados', [])
        
        # Solo grupos aprobados y manuales
        for grupo in grupos_confirmados:
            if grupo.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']:
                self.grupos.append({
                    'id_grupo': grupo.get('id_grupo'),
                    'nombre': grupo.get('producto_base', 'Grupo'),
                    'tipo_variante': grupo.get('atributo_variante'),
                    'skus': grupo.get('skus', []),
                    'valores_variantes': grupo.get('valores_variantes', {})
                })
        
        logger.info(f"✅ Cargados {len(self.grupos)} grupos de variantes")
    
    def analizar_grupo(self, grupo: Dict) -> Dict:
        """
        Analiza un grupo de variantes comparando URLs de imágenes
        
        Args:
            grupo: Datos del grupo
        
        Returns:
            dict: Análisis con URLs comunes y específicas
        """
        skus = grupo['skus']
        
        # Cargar URLs de cada variante
        urls_por_sku = {}
        
        for sku in skus:
            try:
                metadata = Config.cargar_metadata(sku)
                urls = metadata.get('imagenes', [])
                urls_por_sku[sku] = set(urls)
            except Exception as e:
                logger.warning(f"Error cargando {sku}: {e}")
                urls_por_sku[sku] = set()
        
        if not urls_por_sku or not any(urls_por_sku.values()):
            return {
                'tipo': 'sin_imagenes',
                'urls_comunes': [],
                'urls_por_variante': {}
            }
        
        # Encontrar intersección (URLs comunes a TODAS las variantes)
        sets_no_vacios = [urls for urls in urls_por_sku.values() if urls]
        
        if len(sets_no_vacios) > 1:
            urls_comunes = set.intersection(*sets_no_vacios)
        elif len(sets_no_vacios) == 1:
            urls_comunes = sets_no_vacios[0]
        else:
            urls_comunes = set()
        
        # Calcular URLs específicas por variante
        urls_especificas = {}
        for sku, urls in urls_por_sku.items():
            especificas = urls - urls_comunes
            if especificas:
                urls_especificas[sku] = especificas
        
        # Determinar tipo
        if not urls_comunes and not any(urls_especificas.values()):
            tipo = 'sin_imagenes'
        elif len(skus) == 1:
            tipo = 'producto_unico'
        elif not urls_especificas or all(len(u) == 0 for u in urls_especificas.values()):
            tipo = 'identicas'  # Todas las variantes tienen las mismas imágenes
        elif not urls_comunes:
            tipo = 'unicas'  # Cada variante tiene solo imágenes propias
        else:
            tipo = 'mixtas'  # Hay comunes + específicas
        
        return {
            'tipo': tipo,
            'urls_comunes': list(urls_comunes),
            'urls_por_variante': {sku: list(urls) for sku, urls in urls_especificas.items()},
            'urls_todas': {sku: list(urls) for sku, urls in urls_por_sku.items()}
        }
    
    def obtener_nombre_imagen_desde_url(self, url: str, imagenes_dir: Path) -> str:
        """
        Encuentra el nombre de archivo local que corresponde a una URL
        
        Args:
            url: URL de la imagen
            imagenes_dir: Directorio donde buscar
        
        Returns:
            str: Nombre del archivo encontrado o None
        """
        # Buscar en metadata inversa: comparar URLs
        # Como no sabemos qué archivo corresponde a qué URL exactamente,
        # asumimos que están en orden (img_001, img_002, etc.)
        return None  # Placeholder - se maneja por índice
    
    def reorganizar_grupo_identicas(self, grupo: Dict, analisis: Dict):
        """
        Reorganiza grupo donde todas las variantes tienen imágenes idénticas
        
        Args:
            grupo: Datos del grupo
            analisis: Análisis del grupo
        """
        skus = grupo['skus']
        sku_base = self.extraer_sku_base(skus[0])
        
        logger.info(f"  Tipo: IDÉNTICAS - Usando SKU base: {sku_base}")
        
        # Carpeta destino
        dir_destino = Config.PRODUCTOS_DIR / sku_base / 'imagenes_originales'
        
        # Solo necesitamos copiar de la primera variante
        primer_sku = skus[0]
        dir_origen = Config.PRODUCTOS_DIR / primer_sku / 'imagenes_originales'
        
        if not dir_origen.exists():
            logger.warning(f"  ❌ No existe: {dir_origen}")
            return
        
        # Mover/copiar imágenes
        dir_destino.mkdir(parents=True, exist_ok=True)
        
        imagenes = sorted(dir_origen.glob('img_*'))
        for imagen in imagenes:
            destino = dir_destino / imagen.name
            
            if not destino.exists():
                shutil.copy2(imagen, destino)
                self.estadisticas['imagenes_movidas'] += 1
        
        logger.info(f"  ✅ {len(imagenes)} imágenes organizadas en {sku_base}/")
        
        # Limpiar carpetas de variantes individuales (opcional)
        # Por ahora las dejamos
    
    def reorganizar_grupo_mixtas(self, grupo: Dict, analisis: Dict):
        """
        Reorganiza grupo con imágenes comunes + específicas
        
        Args:
            grupo: Datos del grupo
            analisis: Análisis del grupo
        """
        skus = grupo['skus']
        sku_base = self.extraer_sku_base(skus[0])
        valores_variantes = grupo['valores_variantes']
        
        logger.info(f"  Tipo: MIXTAS - Base: {sku_base}")
        logger.info(f"    Comunes: {len(analisis['urls_comunes'])}")
        
        # Crear carpeta base
        dir_base = Config.PRODUCTOS_DIR / sku_base
        dir_base.mkdir(parents=True, exist_ok=True)
        
        # 1. Organizar imágenes comunes
        if analisis['urls_comunes']:
            dir_comunes = dir_base / 'imagenes_generales'
            dir_comunes.mkdir(parents=True, exist_ok=True)
            self.estadisticas['carpetas_creadas'] += 1
            
            # Copiar de la primera variante
            primer_sku = skus[0]
            dir_origen = Config.PRODUCTOS_DIR / primer_sku / 'imagenes_originales'
            
            if dir_origen.exists():
                # Obtener metadata para mapear URLs a archivos
                metadata = Config.cargar_metadata(primer_sku)
                urls_producto = metadata.get('imagenes', [])
                
                # Mapear: índice de URL común -> nombre de archivo
                contador = 1
                for i, url in enumerate(urls_producto, 1):
                    if url in analisis['urls_comunes']:
                        # Buscar archivo img_XXX correspondiente
                        archivo_origen = dir_origen / f"img_{i:03d}.jpg"
                        if not archivo_origen.exists():
                            archivo_origen = dir_origen / f"img_{i:03d}.png"
                        if not archivo_origen.exists():
                            archivo_origen = dir_origen / f"img_{i:03d}.webp"
                        
                        if archivo_origen.exists():
                            extension = archivo_origen.suffix
                            destino = dir_comunes / f"img_{contador:03d}{extension}"
                            
                            if not destino.exists():
                                shutil.copy2(archivo_origen, destino)
                                self.estadisticas['imagenes_movidas'] += 1
                                self.estadisticas['imagenes_comunes_identificadas'] += 1
                            
                            contador += 1
                
                logger.info(f"    ✅ {contador - 1} comunes → imagenes_generales/")
        
        # 2. Organizar imágenes específicas por variante
        for sku in skus:
            if sku in analisis['urls_por_variante'] and analisis['urls_por_variante'][sku]:
                # Obtener nombre de carpeta (valor de variante personalizado)
                nombre_variante = valores_variantes.get(sku, sku)
                
                dir_variante = dir_base / nombre_variante
                dir_variante.mkdir(parents=True, exist_ok=True)
                self.estadisticas['carpetas_creadas'] += 1
                
                dir_origen = Config.PRODUCTOS_DIR / sku / 'imagenes_originales'
                
                if dir_origen.exists():
                    # Obtener metadata
                    metadata = Config.cargar_metadata(sku)
                    urls_producto = metadata.get('imagenes', [])
                    
                    # Copiar solo imágenes específicas
                    contador = 1
                    for i, url in enumerate(urls_producto, 1):
                        if url in analisis['urls_por_variante'][sku]:
                            archivo_origen = dir_origen / f"img_{i:03d}.jpg"
                            if not archivo_origen.exists():
                                archivo_origen = dir_origen / f"img_{i:03d}.png"
                            if not archivo_origen.exists():
                                archivo_origen = dir_origen / f"img_{i:03d}.webp"
                            
                            if archivo_origen.exists():
                                extension = archivo_origen.suffix
                                destino = dir_variante / f"img_{contador:03d}{extension}"
                                
                                if not destino.exists():
                                    shutil.copy2(archivo_origen, destino)
                                    self.estadisticas['imagenes_movidas'] += 1
                                
                                contador += 1
                    
                    logger.info(f"    ✅ {contador - 1} específicas → {nombre_variante}/")
    
    def reorganizar_grupo_unicas(self, grupo: Dict, analisis: Dict):
        """
        Reorganiza grupo donde cada variante tiene solo imágenes únicas
        
        Args:
            grupo: Datos del grupo
            analisis: Análisis del grupo
        """
        skus = grupo['skus']
        sku_base = self.extraer_sku_base(skus[0])
        valores_variantes = grupo['valores_variantes']
        
        logger.info(f"  Tipo: ÚNICAS - Base: {sku_base}")
        
        # Crear carpeta base
        dir_base = Config.PRODUCTOS_DIR / sku_base
        dir_base.mkdir(parents=True, exist_ok=True)
        
        # Organizar cada variante en su subcarpeta
        for sku in skus:
            nombre_variante = valores_variantes.get(sku, sku)
            
            dir_variante = dir_base / nombre_variante
            dir_variante.mkdir(parents=True, exist_ok=True)
            self.estadisticas['carpetas_creadas'] += 1
            
            dir_origen = Config.PRODUCTOS_DIR / sku / 'imagenes_originales'
            
            if dir_origen.exists():
                imagenes = sorted(dir_origen.glob('img_*'))
                
                for imagen in imagenes:
                    destino = dir_variante / imagen.name
                    
                    if not destino.exists():
                        shutil.copy2(imagen, destino)
                        self.estadisticas['imagenes_movidas'] += 1
                
                logger.info(f"    ✅ {len(imagenes)} imágenes → {nombre_variante}/")
    
    def extraer_sku_base(self, sku: str) -> str:
        """
        Extrae el SKU base (sin sufijo de variante)
        
        Args:
            sku: SKU completo
        
        Returns:
            str: SKU base
        """
        # Remover sufijos comunes de variantes
        import re
        
        # Patrones: -XX, -XXX, -XXXX al final
        sku_base = re.sub(r'-[A-Z0-9]{1,4}$', '', sku)
        
        # Si no cambió nada, devolver original
        if sku_base == sku or not sku_base:
            return sku
        
        return sku_base
    
    def organizar_todos(self):
        """Organiza todos los grupos de variantes"""
        if not self.grupos:
            print("\n⚠️  No hay grupos para organizar")
            return
        
        print(f"\n{'=' * 80}")
        print(f"📁 ORGANIZANDO {len(self.grupos)} GRUPOS DE VARIANTES")
        print(f"{'=' * 80}\n")
        
        for i, grupo in enumerate(self.grupos, 1):
            try:
                logger.info(f"[{i}/{len(self.grupos)}] {grupo['nombre']}")
                print(f"[{i}/{len(self.grupos)}] {grupo['nombre']}")
                
                # Analizar grupo
                analisis = self.analizar_grupo(grupo)
                tipo = analisis['tipo']
                
                # Reorganizar según tipo
                if tipo == 'identicas':
                    self.reorganizar_grupo_identicas(grupo, analisis)
                elif tipo == 'mixtas':
                    self.reorganizar_grupo_mixtas(grupo, analisis)
                elif tipo == 'unicas':
                    self.reorganizar_grupo_unicas(grupo, analisis)
                elif tipo == 'producto_unico':
                    logger.info(f"  Tipo: ÚNICO - No requiere reorganización")
                else:
                    logger.warning(f"  Tipo: {tipo} - Saltando")
                
                self.estadisticas['grupos_procesados'] += 1
                
            except Exception as e:
                logger.error(f"Error procesando grupo {grupo['id_grupo']}: {e}")
                self.estadisticas['errores'] += 1
                continue
        
        self.mostrar_resumen()
        self.generar_reporte()
    
    def mostrar_resumen(self):
        """Muestra resumen de la organización"""
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE ORGANIZACIÓN")
        print(f"{'=' * 80}")
        print(f"\n📦 Grupos procesados: {self.estadisticas['grupos_procesados']}")
        print(f"📁 Carpetas creadas: {self.estadisticas['carpetas_creadas']}")
        print(f"📷 Imágenes organizadas: {self.estadisticas['imagenes_movidas']}")
        print(f"♻️  Imágenes comunes identificadas: {self.estadisticas['imagenes_comunes_identificadas']}")
        
        if self.estadisticas['errores'] > 0:
            print(f"\n❌ Errores: {self.estadisticas['errores']}")
        
        print(f"\n{'=' * 80}")
    
    def generar_reporte(self):
        """Genera reporte JSON"""
        fecha = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        reporte_file = Config.LOGS_DIR / f"reporte_organizacion_{fecha}.json"
        
        reporte = {
            'fecha': datetime.now().isoformat(),
            'archivo_variantes': str(self.archivo_variantes),
            'estadisticas': self.estadisticas,
            'grupos_procesados': len(self.grupos)
        }
        
        with open(reporte_file, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte: {reporte_file}")
        logger.info(f"Reporte guardado en: {reporte_file}")


def main():
    """Ejecuta el organizador"""
    print("=" * 80)
    print("📁 ORGANIZADOR DE IMÁGENES POR VARIANTES")
    print("=" * 80)
    
    # Buscar archivo de variantes
    archivos_variantes = sorted(
        Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not archivos_variantes:
        print("\n❌ No se encontró archivo de variantes")
        print("   Ejecutar primero: python 08_revisor_variantes.py")
        return
    
    archivo = archivos_variantes[0]
    print(f"\n📄 Archivo de variantes: {archivo.name}")
    
    # Cargar para mostrar info
    with open(archivo, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    
    grupos_validos = [
        g for g in datos.get('grupos_confirmados', [])
        if g.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']
    ]
    
    print(f"📊 Grupos a organizar: {len(grupos_validos)}")
    
    print(f"\n{'─' * 80}")
    print("⚠️  NOTA: Este proceso:")
    print("   • Crea nuevas carpetas organizadas por variantes")
    print("   • NO elimina las carpetas originales")
    print("   • Copia (no mueve) las imágenes")
    print(f"{'─' * 80}")
    
    confirmar = input("\n¿Iniciar organización? (s/n): ").lower()
    
    if confirmar == 's':
        organizador = OrganizadorImagenes(archivo)
        organizador.organizar_todos()
    else:
        print("\nOrganización cancelada")


if __name__ == "__main__":
    main()
