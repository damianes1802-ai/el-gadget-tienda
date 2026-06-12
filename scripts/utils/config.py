#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GESTOR DE CONFIGURACIÓN
Carga configuraciones desde archivos JSON y variables de entorno
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

class Config:
    """Gestor centralizado de configuración"""
    
    # Directorios del proyecto
    BASE_DIR = Path(__file__).parent.parent.parent
    CONFIG_DIR = BASE_DIR / "config"
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    SCRIPTS_DIR = BASE_DIR / "scripts"
    
    # Subdirectorios de data
    PRODUCTOS_DIR = DATA_DIR / "productos"
    PRECIOS_DIR = DATA_DIR / "precios"
    GRUPOS_VARIANTES_DIR = DATA_DIR / "grupos_variantes"
    
    # Archivos de configuración
    SCRAPING_CONFIG_FILE = CONFIG_DIR / "scraping_config.json"
    PRECIOS_CONFIG_FILE = PRECIOS_DIR / "config_precios.json"
    ENV_FILE = CONFIG_DIR / ".env"
    
    _config_cache = {}
    
    @classmethod
    def cargar_json(cls, archivo: Path) -> Dict[str, Any]:
        """
        Carga un archivo JSON de configuración
        
        Args:
            archivo (Path): Ruta al archivo JSON
        
        Returns:
            dict: Contenido del archivo
        """
        if not archivo.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {archivo}")
        
        # Usar caché si ya fue cargado
        archivo_str = str(archivo)
        if archivo_str in cls._config_cache:
            return cls._config_cache[archivo_str]
        
        with open(archivo, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        cls._config_cache[archivo_str] = config
        return config
    
    @classmethod
    def cargar_env(cls) -> Dict[str, str]:
        """
        Carga variables de entorno desde .env
        
        Returns:
            dict: Variables de entorno
        """
        env_vars = {}
        
        if not cls.ENV_FILE.exists():
            print(f"⚠️  Archivo .env no encontrado en: {cls.ENV_FILE}")
            print(f"   Crear desde: {cls.CONFIG_DIR}/.env.example")
            return env_vars
        
        with open(cls.ENV_FILE, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                
                # Ignorar comentarios y líneas vacías
                if not linea or linea.startswith('#'):
                    continue
                
                # Parsear KEY=VALUE
                if '=' in linea:
                    key, value = linea.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    @classmethod
    def get_scraping_config(cls) -> Dict[str, Any]:
        """Obtiene configuración de scraping"""
        return cls.cargar_json(cls.SCRAPING_CONFIG_FILE)
    
    @classmethod
    def get_precios_config(cls) -> Dict[str, Any]:
        """Obtiene configuración de precios"""
        return cls.cargar_json(cls.PRECIOS_CONFIG_FILE)
    
    @classmethod
    def get_credenciales_droppers(cls) -> Dict[str, str]:
        """
        Obtiene credenciales de Droppers desde .env
        
        Returns:
            dict: {'username': '...', 'password': '...'}
        """
        env = cls.cargar_env()
        
        username = env.get('DROPPERS_USER', '')
        password = env.get('DROPPERS_PASS', '')
        
        if not username or not password:
            raise ValueError(
                "Credenciales de Droppers no configuradas. "
                f"Editar archivo: {cls.ENV_FILE}"
            )
        
        return {
            'username': username,
            'password': password
        }
    
    @classmethod
    def crear_directorio_producto(cls, sku: str) -> Path:
        """
        Crea la estructura de directorios para un producto
        
        Args:
            sku (str): SKU del producto
        
        Returns:
            Path: Ruta al directorio del producto
        """
        producto_dir = cls.PRODUCTOS_DIR / sku
        producto_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear subdirectorios
        (producto_dir / "imagenes_originales").mkdir(exist_ok=True)
        (producto_dir / "imagenes_cloudinary").mkdir(exist_ok=True)
        (producto_dir / "textos_ia").mkdir(exist_ok=True)
        
        return producto_dir
    
    @classmethod
    def get_ruta_metadata(cls, sku: str) -> Path:
        """Obtiene ruta al archivo metadata.json de un producto"""
        return cls.PRODUCTOS_DIR / sku / "metadata.json"
    
    @classmethod
    def guardar_metadata(cls, sku: str, datos: Dict[str, Any]) -> None:
        """
        Guarda metadata de un producto
        
        Args:
            sku (str): SKU del producto
            datos (dict): Datos a guardar
        """
        producto_dir = cls.crear_directorio_producto(sku)
        metadata_file = producto_dir / "metadata.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def cargar_metadata(cls, sku: str) -> Dict[str, Any]:
        """
        Carga metadata de un producto
        
        Args:
            sku (str): SKU del producto
        
        Returns:
            dict: Datos del producto
        """
        metadata_file = cls.get_ruta_metadata(sku)
        
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata no encontrada para SKU: {sku}")
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def listar_productos(cls) -> list:
        """
        Lista todos los SKUs de productos existentes
        
        Returns:
            list: Lista de SKUs
        """
        if not cls.PRODUCTOS_DIR.exists():
            return []
        
        skus = []
        for item in cls.PRODUCTOS_DIR.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                skus.append(item.name)
        
        return sorted(skus)
    
    @classmethod
    def get_directorio_producto(cls, sku: str) -> Path:
        """
        Obtiene el directorio de un producto (sin crearlo)
        
        Args:
            sku (str): SKU del producto
        
        Returns:
            Path: Ruta al directorio del producto
        """
        return cls.PRODUCTOS_DIR / sku
    
    @classmethod
    def get_credenciales_cloudinary(cls) -> Dict[str, str]:
        """
        Obtiene credenciales de Cloudinary desde .env
        
        Returns:
            dict: Credenciales de Cloudinary
        """
        env = cls.cargar_env()
        
        cloud_name = env.get('CLOUDINARY_CLOUD_NAME', '')
        api_key = env.get('CLOUDINARY_API_KEY', '')
        api_secret = env.get('CLOUDINARY_API_SECRET', '')
        
        if not all([cloud_name, api_key, api_secret]):
            raise ValueError(
                "Credenciales de Cloudinary no configuradas.\n"
                f"Agregar en archivo: {cls.ENV_FILE}\n\n"
                "Agregar estas líneas:\n"
                "  CLOUDINARY_CLOUD_NAME=tu-cloud-name\n"
                "  CLOUDINARY_API_KEY=tu-api-key\n"
                "  CLOUDINARY_API_SECRET=tu-api-secret\n\n"
                "Obtener credenciales en: https://cloudinary.com/console"
            )
        
        return {
            'cloud_name': cloud_name,
            'api_key': api_key,
            'api_secret': api_secret
        }
    
    @classmethod
    def get_ruta_google_credentials(cls) -> Path:
        """
        Obtiene la ruta al archivo de credenciales de Google
        
        Returns:
            Path: Ruta al archivo google_credentials.json
        """
        env = cls.cargar_env()
        
        # Nombre del archivo desde .env o usar default
        filename = env.get('GOOGLE_CREDENTIALS_FILE', 'google_credentials.json')
        
        # Ruta completa
        creds_path = cls.CONFIG_DIR / filename
        
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Archivo de credenciales de Google no encontrado: {creds_path}\n"
                "Copiar google_credentials.json a la carpeta config/\n"
                "Obtener credenciales en: https://console.cloud.google.com/"
            )
        
        return creds_path


if __name__ == "__main__":
    # Tests
    print("=" * 80)
    print("TEST DEL GESTOR DE CONFIGURACIÓN")
    print("=" * 80)
    
    print(f"\n📁 Directorios del proyecto:")
    print(f"   BASE: {Config.BASE_DIR}")
    print(f"   CONFIG: {Config.CONFIG_DIR}")
    print(f"   DATA: {Config.DATA_DIR}")
    print(f"   PRODUCTOS: {Config.PRODUCTOS_DIR}")
    print(f"   LOGS: {Config.LOGS_DIR}")
    
    print(f"\n📄 Archivos de configuración:")
    print(f"   Scraping: {Config.SCRAPING_CONFIG_FILE}")
    print(f"   Precios: {Config.PRECIOS_CONFIG_FILE}")
    print(f"   ENV: {Config.ENV_FILE}")
    
    # Cargar configuraciones
    try:
        scraping_config = Config.get_scraping_config()
        print(f"\n✅ Configuración de scraping cargada:")
        print(f"   Sitio: {scraping_config['sitio']}")
        print(f"   Login URL: {scraping_config['login']['url']}")
    except Exception as e:
        print(f"\n❌ Error cargando configuración de scraping: {e}")
    
    try:
        precios_config = Config.get_precios_config()
        print(f"\n✅ Configuración de precios cargada:")
        print(f"   Moneda: {precios_config['moneda']}")
        print(f"   Redondeo múltiplo: {precios_config['redondeo_comercial']['multiplo']}")
    except Exception as e:
        print(f"\n❌ Error cargando configuración de precios: {e}")
    
    # Test de creación de directorio de producto
    print(f"\n📁 Test de creación de directorio:")
    test_dir = Config.crear_directorio_producto("TEST_SKU_001")
    print(f"   Directorio creado: {test_dir}")
    print(f"   Subdirectorios:")
    for subdir in test_dir.iterdir():
        print(f"     - {subdir.name}")
    
    print("\n" + "=" * 80)
