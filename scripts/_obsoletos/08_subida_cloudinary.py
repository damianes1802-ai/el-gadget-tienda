#!/usr/bin/env python3
"""
Módulo 08: Subida de imágenes a Cloudinary (ADAPTADO)
======================================================

Versión adaptada para la estructura real del proyecto:
- data/productos/SKU/imagenes_originales/
- data/productos/GRUPO/VARIANTE/

Sube todas las imágenes a Cloudinary y actualiza los metadata.json

Autor: Sistema de Gestión Ecommerce
Fecha: 2026-02-02
"""

import os
import json
import time
import base64
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

class SubidorCloudinaryAdaptado:
    """Maneja la subida de imágenes a Cloudinary con estructura adaptada"""
    
    def __init__(self, config_path: str = "../config/.env"):
        """
        Inicializa el subidor de Cloudinary
        
        Args:
            config_path: Ruta al archivo .env con credenciales
        """
        # Cargar configuración
        load_dotenv(config_path)
        
        self.cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
        self.api_key = os.getenv('CLOUDINARY_API_KEY')
        self.api_secret = os.getenv('CLOUDINARY_API_SECRET')
        
        if not all([self.cloud_name, self.api_key, self.api_secret]):
            raise ValueError("Faltan credenciales de Cloudinary en .env")
        
        # URLs de API
        self.upload_url = f"https://api.cloudinary.com/v1_1/{self.cloud_name}/image/upload"
        self.base_url = f"https://res.cloudinary.com/{self.cloud_name}/image/upload"
        
        # Directorios
        self.base_dir = Path("../data/productos")
        
        # Estadísticas
        self.stats = {
            'total_imagenes': 0,
            'subidas_exitosas': 0,
            'subidas_fallidas': 0,
            'ya_existentes': 0,
            'productos_procesados': 0,
            'grupos_procesados': 0,
            'tiempo_inicio': None,
            'tiempo_fin': None
        }
        
        # Reporte
        self.reporte = {
            'productos': {},
            'grupos': {},
            'errores': []
        }
    
    def generar_firma(self, params: dict) -> str:
        """
        Genera firma para autenticación de Cloudinary
        
        Args:
            params: Parámetros de la petición
            
        Returns:
            Firma SHA256
        """
        # Ordenar parámetros alfabéticamente
        sorted_params = sorted(params.items())
        
        # Crear string de parámetros
        params_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # Agregar API secret
        params_str += self.api_secret
        
        # Generar hash SHA256
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    def subir_imagen(
        self, 
        ruta_imagen: Path, 
        public_id: str,
        carpeta: str = "ecommerce",
        max_reintentos: int = 3
    ) -> Optional[Dict]:
        """
        Sube una imagen a Cloudinary
        
        Args:
            ruta_imagen: Ruta a la imagen local
            public_id: ID público en Cloudinary
            carpeta: Carpeta en Cloudinary
            max_reintentos: Número máximo de reintentos
            
        Returns:
            Respuesta de Cloudinary o None si falla
        """
        # Verificar que la imagen existe
        if not ruta_imagen.exists():
            print(f"❌ Imagen no encontrada: {ruta_imagen}")
            return None
        
        # Leer imagen
        with open(ruta_imagen, 'rb') as f:
            imagen_data = f.read()
        
        # Codificar en base64
        imagen_base64 = base64.b64encode(imagen_data).decode('utf-8')
        
        # Timestamp
        timestamp = int(time.time())
        
        # Parámetros de subida
        upload_params = {
            'file': f'data:image/jpeg;base64,{imagen_base64}',
            'public_id': public_id,
            'folder': carpeta,
            'timestamp': str(timestamp),
            'api_key': self.api_key
        }
        
        # Generar firma (sin 'file')
        signature_params = {
            'public_id': public_id,
            'folder': carpeta,
            'timestamp': str(timestamp)
        }
        
        signature = self.generar_firma(signature_params)
        upload_params['signature'] = signature
        
        # Intentar subida con reintentos
        for intento in range(max_reintentos):
            try:
                response = requests.post(
                    self.upload_url,
                    data=upload_params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    # Puede ser que ya existe
                    error_data = response.json()
                    if 'error' in error_data and 'already exists' in str(error_data['error']):
                        print(f"⚠️  Ya existe", end="")
                        self.stats['ya_existentes'] += 1
                        # Construir URL manualmente
                        return {
                            'secure_url': f"{self.base_url}/v1/{carpeta}/{public_id}",
                            'public_id': f"{carpeta}/{public_id}",
                            'already_exists': True
                        }
                    else:
                        print(f"❌ Error 400: {error_data}")
                        
                else:
                    print(f"❌ Error {response.status_code}")
                
                if intento < max_reintentos - 1:
                    time.sleep(2 ** intento)
                    
            except Exception as e:
                print(f"❌ Excepción: {str(e)[:50]}")
                if intento < max_reintentos - 1:
                    time.sleep(2 ** intento)
        
        return None
    
    def es_grupo_con_variantes(self, carpeta: Path) -> bool:
        """
        Determina si una carpeta es un grupo con variantes
        
        Args:
            carpeta: Carpeta a verificar
            
        Returns:
            True si es grupo con variantes, False si es producto simple
        """
        # Si tiene subcarpetas que no son imagenes_originales/cloudinary/textos_ia
        subdirs = [d for d in carpeta.iterdir() if d.is_dir()]
        
        # Excluir carpetas conocidas
        subdirs_filtrados = [
            d for d in subdirs 
            if d.name not in ['imagenes_originales', 'imagenes_cloudinary', 'textos_ia', 'general']
        ]
        
        # Si tiene subcarpetas con imágenes, es grupo con variantes
        for subdir in subdirs_filtrados:
            if any(subdir.glob("*.jpg")) or any(subdir.glob("*.png")) or any(subdir.glob("*.webp")):
                return True
        
        return False
    
    def procesar_producto_simple(self, carpeta_producto: Path) -> Dict:
        """
        Procesa un producto simple con imagenes_originales
        
        Args:
            carpeta_producto: Carpeta del producto
            
        Returns:
            Diccionario con URLs de Cloudinary
        """
        sku = carpeta_producto.name
        print(f"\n📦 Producto simple: {sku}")
        
        # Buscar carpeta imagenes_originales
        carpeta_imagenes = carpeta_producto / "imagenes_originales"
        
        if not carpeta_imagenes.exists():
            print(f"  ⚠️  No se encontró imagenes_originales, buscando en raíz...")
            carpeta_imagenes = carpeta_producto
        
        # Obtener imágenes
        imagenes = sorted(carpeta_imagenes.glob("*.jpg")) + \
                   sorted(carpeta_imagenes.glob("*.png")) + \
                   sorted(carpeta_imagenes.glob("*.webp"))
        
        if not imagenes:
            print(f"  ⚠️  No se encontraron imágenes")
            return {'sku': sku, 'urls': []}
        
        urls_cloudinary = []
        
        for imagen in imagenes:
            # Generar public_id
            nombre_imagen = imagen.stem
            public_id = f"{sku}/{nombre_imagen}"
            
            # Subir imagen
            print(f"  ⬆️  {imagen.name}...", end=" ")
            
            resultado = self.subir_imagen(
                ruta_imagen=imagen,
                public_id=public_id,
                carpeta="ecommerce"
            )
            
            if resultado:
                url = resultado.get('secure_url')
                if url:
                    urls_cloudinary.append(url)
                    self.stats['subidas_exitosas'] += 1
                    print(f"✅")
                else:
                    print(f"❌")
                    self.stats['subidas_fallidas'] += 1
            else:
                print(f"❌")
                self.stats['subidas_fallidas'] += 1
            
            self.stats['total_imagenes'] += 1
        
        print(f"  ✅ Completado: {len(urls_cloudinary)}/{len(imagenes)} imágenes")
        
        # Guardar en reporte
        self.reporte['productos'][sku] = {
            'total_imagenes': len(imagenes),
            'subidas_exitosas': len(urls_cloudinary),
            'urls': urls_cloudinary
        }
        
        return {
            'sku': sku,
            'urls': urls_cloudinary
        }
    
    def procesar_grupo_variantes(self, carpeta_grupo: Path) -> Dict:
        """
        Procesa un grupo con variantes (subcarpetas por variante)
        
        Args:
            carpeta_grupo: Carpeta del grupo
            
        Returns:
            Diccionario con URLs por variante
        """
        grupo_base = carpeta_grupo.name
        print(f"\n📁 Grupo con variantes: {grupo_base}")
        
        # Obtener subcarpetas de variantes
        subdirs = [d for d in carpeta_grupo.iterdir() if d.is_dir()]
        variantes = [
            d for d in subdirs 
            if d.name not in ['imagenes_originales', 'imagenes_cloudinary', 'textos_ia', 'general', 'metadata.json']
        ]
        
        urls_por_variante = {}
        total_imagenes_grupo = 0
        total_subidas_grupo = 0
        
        for variante_dir in variantes:
            variante = variante_dir.name
            print(f"  📂 Variante: {variante}")
            
            # Obtener imágenes de la variante
            imagenes = sorted(variante_dir.glob("*.jpg")) + \
                       sorted(variante_dir.glob("*.png")) + \
                       sorted(variante_dir.glob("*.webp"))
            
            if not imagenes:
                print(f"    ⚠️  Sin imágenes")
                continue
            
            urls_variante = []
            
            for imagen in imagenes:
                # Generar public_id
                nombre_imagen = imagen.stem
                public_id = f"{grupo_base}/{variante}/{nombre_imagen}"
                
                # Subir imagen
                print(f"    ⬆️  {imagen.name}...", end=" ")
                
                resultado = self.subir_imagen(
                    ruta_imagen=imagen,
                    public_id=public_id,
                    carpeta="ecommerce"
                )
                
                if resultado:
                    url = resultado.get('secure_url')
                    if url:
                        urls_variante.append(url)
                        self.stats['subidas_exitosas'] += 1
                        total_subidas_grupo += 1
                        print(f"✅")
                    else:
                        print(f"❌")
                        self.stats['subidas_fallidas'] += 1
                else:
                    print(f"❌")
                    self.stats['subidas_fallidas'] += 1
                
                self.stats['total_imagenes'] += 1
                total_imagenes_grupo += 1
            
            urls_por_variante[variante] = urls_variante
            print(f"    ✅ {len(urls_variante)}/{len(imagenes)} imágenes")
        
        print(f"  ✅ Grupo completado: {total_subidas_grupo}/{total_imagenes_grupo} imágenes")
        
        # Guardar en reporte
        self.reporte['grupos'][grupo_base] = {
            'variantes': urls_por_variante,
            'total_imagenes': total_imagenes_grupo,
            'subidas_exitosas': total_subidas_grupo
        }
        
        return {
            'grupo': grupo_base,
            'urls_por_variante': urls_por_variante
        }
    
    def actualizar_metadata_producto(self, carpeta: Path, urls: List[str]):
        """
        Actualiza metadata.json del producto con URLs de Cloudinary
        
        Args:
            carpeta: Carpeta del producto
            urls: Lista de URLs de Cloudinary
        """
        metadata_file = carpeta / "metadata.json"
        
        if not metadata_file.exists():
            return
        
        # Leer metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Agregar URLs de Cloudinary
        metadata['imagenes_cloudinary'] = urls
        
        # Guardar
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def actualizar_metadata_grupo(self, carpeta: Path, urls_por_variante: Dict):
        """
        Actualiza metadata.json del grupo con URLs por variante
        
        Args:
            carpeta: Carpeta del grupo
            urls_por_variante: Diccionario con URLs por variante
        """
        metadata_file = carpeta / "metadata.json"
        
        if not metadata_file.exists():
            return
        
        # Leer metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Agregar URLs de Cloudinary por variante
        metadata['imagenes_cloudinary_por_variante'] = urls_por_variante
        
        # Guardar
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def generar_reporte(self) -> str:
        """
        Genera reporte detallado de la subida
        
        Returns:
            Ruta al archivo de reporte
        """
        # Calcular tiempo total
        tiempo_total = self.stats['tiempo_fin'] - self.stats['tiempo_inicio']
        minutos = int(tiempo_total // 60)
        segundos = int(tiempo_total % 60)
        
        # Crear reporte
        reporte_texto = f"""
╔══════════════════════════════════════════════════════════════╗
║         REPORTE DE SUBIDA A CLOUDINARY                       ║
╚══════════════════════════════════════════════════════════════╝

📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
⏱️  Tiempo total: {minutos}m {segundos}s

📊 ESTADÍSTICAS GENERALES
{'─' * 60}
Total de imágenes procesadas:    {self.stats['total_imagenes']:,}
Subidas exitosas:                 {self.stats['subidas_exitosas']:,}
Subidas fallidas:                 {self.stats['subidas_fallidas']:,}
Imágenes ya existentes:           {self.stats['ya_existentes']:,}
Productos simples procesados:     {self.stats['productos_procesados']:,}
Grupos con variantes procesados:  {self.stats['grupos_procesados']:,}

📈 TASA DE ÉXITO
{'─' * 60}
"""
        
        if self.stats['total_imagenes'] > 0:
            tasa_exito = (self.stats['subidas_exitosas'] / self.stats['total_imagenes']) * 100
            reporte_texto += f"Tasa de éxito: {tasa_exito:.2f}%\n"
        
        # Productos simples
        if self.reporte['productos']:
            reporte_texto += f"\n\n📦 PRODUCTOS SIMPLES ({len(self.reporte['productos'])})\n{'─' * 60}\n"
            for sku, info in list(self.reporte['productos'].items())[:10]:
                tasa = (info['subidas_exitosas'] / info['total_imagenes']) * 100 if info['total_imagenes'] > 0 else 0
                reporte_texto += f"{sku}: {info['subidas_exitosas']}/{info['total_imagenes']} ({tasa:.0f}%)\n"
            
            if len(self.reporte['productos']) > 10:
                reporte_texto += f"... y {len(self.reporte['productos']) - 10} productos más\n"
        
        # Grupos con variantes
        if self.reporte['grupos']:
            reporte_texto += f"\n\n📁 GRUPOS CON VARIANTES ({len(self.reporte['grupos'])})\n{'─' * 60}\n"
            for grupo, info in list(self.reporte['grupos'].items())[:10]:
                tasa = (info['subidas_exitosas'] / info['total_imagenes']) * 100 if info['total_imagenes'] > 0 else 0
                reporte_texto += f"{grupo}: {info['subidas_exitosas']}/{info['total_imagenes']} ({tasa:.0f}%)\n"
                for variante, urls in info['variantes'].items():
                    reporte_texto += f"  └─ {variante}: {len(urls)} imágenes\n"
            
            if len(self.reporte['grupos']) > 10:
                reporte_texto += f"... y {len(self.reporte['grupos']) - 10} grupos más\n"
        
        # Errores
        if self.reporte['errores']:
            reporte_texto += f"\n\n⚠️  ERRORES ({len(self.reporte['errores'])})\n{'─' * 60}\n"
            for error in self.reporte['errores'][:20]:
                reporte_texto += f"  • {error}\n"
            
            if len(self.reporte['errores']) > 20:
                reporte_texto += f"\n  ... y {len(self.reporte['errores']) - 20} errores más\n"
        
        # Guardar reporte
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archivo_reporte = Path(f"../logs/reporte_cloudinary_{timestamp}.txt")
        
        # Crear carpeta logs si no existe
        archivo_reporte.parent.mkdir(exist_ok=True)
        
        with open(archivo_reporte, 'w', encoding='utf-8') as f:
            f.write(reporte_texto)
        
        print(reporte_texto)
        
        return str(archivo_reporte)
    
    def ejecutar(self):
        """Ejecuta el proceso completo de subida"""
        
        print("\n" + "=" * 60)
        print("🚀 INICIANDO SUBIDA A CLOUDINARY")
        print("=" * 60)
        
        self.stats['tiempo_inicio'] = time.time()
        
        # Verificar directorio
        if not self.base_dir.exists():
            raise FileNotFoundError(f"Directorio no encontrado: {self.base_dir}")
        
        # Obtener todas las carpetas de productos
        carpetas_productos = sorted([
            d for d in self.base_dir.iterdir() 
            if d.is_dir()
        ])
        
        print(f"\n📁 Carpetas encontradas: {len(carpetas_productos)}")
        
        # Procesar cada carpeta
        for carpeta in carpetas_productos:
            
            # Determinar tipo
            if self.es_grupo_con_variantes(carpeta):
                # Grupo con variantes
                resultado = self.procesar_grupo_variantes(carpeta)
                self.actualizar_metadata_grupo(carpeta, resultado['urls_por_variante'])
                self.stats['grupos_procesados'] += 1
            else:
                # Producto simple
                resultado = self.procesar_producto_simple(carpeta)
                self.actualizar_metadata_producto(carpeta, resultado['urls'])
                self.stats['productos_procesados'] += 1
            
            # Pequeña pausa entre carpetas
            time.sleep(0.2)
        
        # Finalizar
        self.stats['tiempo_fin'] = time.time()
        
        # Generar reporte
        archivo_reporte = self.generar_reporte()
        
        print("\n" + "=" * 60)
        print("✅ SUBIDA COMPLETADA")
        print("=" * 60)
        print(f"\n📄 Reporte guardado en: {archivo_reporte}")
        print(f"📊 Estadísticas:")
        print(f"   • Total procesadas: {self.stats['total_imagenes']:,}")
        print(f"   • Exitosas: {self.stats['subidas_exitosas']:,}")
        print(f"   • Fallidas: {self.stats['subidas_fallidas']:,}")
        print(f"   • Productos: {self.stats['productos_procesados']}")
        print(f"   • Grupos: {self.stats['grupos_procesados']}")


def main():
    """Función principal"""
    try:
        # Crear subidor
        subidor = SubidorCloudinaryAdaptado()
        
        # Ejecutar subida
        subidor.ejecutar()
        
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
