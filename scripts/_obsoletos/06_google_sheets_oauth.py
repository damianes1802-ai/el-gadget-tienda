#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXPORTADOR A GOOGLE SHEETS (OAUTH2)
Exporta el catálogo a Google Sheets usando autenticación OAuth2

MODIFICADO: 2026-02-02
- Prioriza URLs de Cloudinary sobre URLs de Droppers
- Fallback automático si no hay URLs de Cloudinary
- Compatible con metadata generado antes y después de subir a Cloudinary
- Guarda ID del spreadsheet automáticamente en config/sheets_id.txt
- Limpia hojas viejas antes de actualizar (ejecución limpia)
- Limita additional_image_link a máximo 20 URLs (límite de Facebook Catalog)
- Agrega espacio después de cada coma en additional_image_link para mejor legibilidad
"""

import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import gspread
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('google_sheets_oauth')


class ExportadorGoogleSheetsOAuth:
    """Exporta datos del catálogo a Google Sheets usando OAuth2"""
    
    # Scopes necesarios
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]
    
    # Archivo donde se guarda el ID de la hoja
    SHEETS_ID_FILE = Config.CONFIG_DIR / 'sheets_id.txt'
    
    def __init__(self):
        """Inicializa el exportador"""
        self.productos = []
        self.grupos_variantes = {}
        
        self.estadisticas = {
            'total_productos': 0,
            'productos_exportados': 0,
            'grupos_exportados': 0,
            'errores': 0
        }
        
        # Conectar a Google Sheets
        self.client = None
        self.spreadsheet = None
        
        logger.info("Exportador Google Sheets (OAuth2) inicializado")
    
    def guardar_spreadsheet_id(self, spreadsheet_id: str, url: str):
        """
        Guarda el ID y URL de la hoja en un archivo
        
        Args:
            spreadsheet_id: ID de la hoja de Google Sheets
            url: URL completa de la hoja
        """
        try:
            with open(self.SHEETS_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(f"{spreadsheet_id}\n")
                f.write(f"{url}\n")
            
            logger.info(f"✅ ID guardado en {self.SHEETS_ID_FILE}")
            print(f"💾 ID guardado para futuras ejecuciones")
            
        except Exception as e:
            logger.warning(f"No se pudo guardar el ID: {e}")
    
    def leer_spreadsheet_id(self) -> tuple:
        """
        Lee el ID guardado de la hoja
        
        Returns:
            tuple: (spreadsheet_id, url) o (None, None) si no existe
        """
        try:
            if not self.SHEETS_ID_FILE.exists():
                return None, None
            
            with open(self.SHEETS_ID_FILE, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
                spreadsheet_id = lines[0] if len(lines) > 0 else None
                url = lines[1] if len(lines) > 1 else None
                
                return spreadsheet_id, url
                
        except Exception as e:
            logger.warning(f"Error leyendo ID guardado: {e}")
            return None, None
    
    def obtener_credenciales(self) -> Credentials:
        """
        Obtiene credenciales OAuth2, pidiendo autorización si es necesario
        
        Returns:
            Credentials: Credenciales de Google OAuth2
        """
        creds = None
        token_file = Config.CONFIG_DIR / 'google_token.pickle'
        creds_file = Config.CONFIG_DIR / 'google_oauth_credentials.json'
        
        # Verificar que existe el archivo de credenciales
        if not creds_file.exists():
            raise FileNotFoundError(
                f"\n❌ No se encontró: {creds_file}\n\n"
                "PASOS PARA OBTENER CREDENCIALES OAUTH2:\n"
                "1. Ir a: https://console.cloud.google.com/\n"
                "2. APIs & Services → Credentials\n"
                "3. CREATE CREDENTIALS → OAuth client ID\n"
                "4. Application type: Desktop app\n"
                "5. Descargar JSON y guardarlo como:\n"
                f"   {creds_file}\n"
            )
        
        # Si ya existe un token guardado, cargarlo
        if token_file.exists():
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # Si no hay credenciales válidas, obtenerlas
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    print("🔄 Renovando credenciales...")
                    creds.refresh(Request())
                except Exception as e:
                    # Si falla la renovación, pedir autorización de nuevo
                    logger.warning(f"No se pudo renovar token: {e}")
                    print("\n⚠️  Token expirado, solicitando nueva autorización...")
                    creds = None
            
            if not creds:
                print("\n🔐 AUTORIZACIÓN REQUERIDA")
                print("   Se abrirá tu navegador para que autorices la aplicación")
                print("   Esto puede tardar unos segundos...\n")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_file),
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Guardar credenciales para la próxima vez
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
            
            logger.info("✅ Credenciales guardadas")
        
        return creds
    
    def conectar_google_sheets(self) -> bool:
        """
        Conecta con Google Sheets usando OAuth2
        
        Returns:
            bool: True si conectó exitosamente
        """
        try:
            creds = self.obtener_credenciales()
            self.client = gspread.authorize(creds)
            
            logger.info("✅ Conectado a Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a Google Sheets: {e}")
            print(f"\n❌ Error de conexión: {e}")
            return False
    
    def cargar_productos(self):
        """Carga todos los productos con sus metadata desde carpetas individuales"""
        from pathlib import Path
        import json
        
        # Ruta a las carpetas de productos
        productos_dir = Path("../data/productos")
        
        if not productos_dir.exists():
            # Intentar sin ../
            productos_dir = Path("data/productos")
        
        if not productos_dir.exists():
            logger.error(f"No se encontró directorio de productos")
            return
        
        # Recorrer todas las carpetas de productos
        for carpeta in productos_dir.iterdir():
            if not carpeta.is_dir():
                continue
            
            # Buscar metadata.json en la carpeta
            metadata_file = carpeta / "metadata.json"
            
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    self.productos.append(metadata)
            except Exception as e:
                logger.warning(f"Error cargando {carpeta.name}: {e}")
        
        self.estadisticas['total_productos'] = len(self.productos)
        logger.info(f"✅ Cargados {len(self.productos)} productos desde carpetas individuales")
    
    def cargar_grupos_variantes(self):
        """Carga información de grupos de variantes"""
        archivos_variantes = sorted(
            Config.GRUPOS_VARIANTES_DIR.glob("variantes_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not archivos_variantes:
            logger.warning("No se encontró archivo de variantes")
            return
        
        archivo = archivos_variantes[0]
        
        with open(archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
        
        grupos_confirmados = datos.get('grupos_confirmados', [])
        
        # Indexar por item_group_id
        for grupo in grupos_confirmados:
            if grupo.get('accion') in ['APROBADO', 'MANUAL', 'MODIFICADO']:
                item_group_id = grupo.get('id_grupo')
                self.grupos_variantes[item_group_id] = grupo
        
        logger.info(f"✅ Cargados {len(self.grupos_variantes)} grupos de variantes")
    
    def obtener_o_crear_spreadsheet(self, nombre: str = "Catálogo Ecommerce - MASTER") -> bool:
        """
        Obtiene una hoja existente por ID guardado o crea una nueva
        
        Args:
            nombre: Nombre de la hoja (por defecto "Catálogo Ecommerce - MASTER")
        
        Returns:
            bool: True si se obtuvo/creó exitosamente
        """
        try:
            # Intentar leer ID guardado
            spreadsheet_id, saved_url = self.leer_spreadsheet_id()
            
            hoja_encontrada = False
            
            if spreadsheet_id:
                # Tenemos ID guardado, abrir por ID
                print(f"\n🔍 Abriendo hoja guardada...")
                print(f"   ID: {spreadsheet_id}")
                
                try:
                    self.spreadsheet = self.client.open_by_key(spreadsheet_id)
                    logger.info(f"✅ Hoja abierta por ID guardado")
                    print(f"✅ Hoja encontrada: {self.spreadsheet.title}")
                    print(f"   Se actualizará el contenido existente")
                    
                    # Eliminar hojas viejas para empezar limpio
                    self.limpiar_hojas_viejas()
                    
                    hoja_encontrada = True
                    
                except Exception as e:
                    # El ID guardado no funciona (hoja eliminada?)
                    logger.warning(f"⚠️  ID guardado no válido: {e}")
                    print(f"\n⚠️  LA HOJA GUARDADA YA NO EXISTE")
                    print(f"   ID guardado: {spreadsheet_id}")
                    print(f"   La hoja fue eliminada de Google Drive")
                    print(f"\n🔄 Eliminando ID viejo y creando nueva hoja...")
                    
                    # Eliminar el archivo de ID viejo
                    try:
                        if self.SHEETS_ID_FILE.exists():
                            self.SHEETS_ID_FILE.unlink()
                            logger.info("✅ Archivo de ID viejo eliminado")
                    except Exception as del_error:
                        logger.warning(f"No se pudo eliminar ID viejo: {del_error}")
                    
                    hoja_encontrada = False
            
            # Si NO encontró la hoja, crear nueva
            if not hoja_encontrada:
                print(f"\n📝 Creando nueva hoja: {nombre}")
            logger.info(f"Intentando crear spreadsheet: {nombre}")
            
            try:
                self.spreadsheet = self.client.create(nombre)
                logger.info(f"✅ Spreadsheet creado exitosamente")
            except Exception as create_error:
                logger.error(f"❌ Error al crear spreadsheet: {create_error}")
                print(f"\n❌ ERROR AL CREAR HOJA: {create_error}")
                raise
            
            # Guardar el nuevo ID para futuras ejecuciones
            spreadsheet_id = self.spreadsheet.id
            url = self.spreadsheet.url
            
            logger.info(f"Spreadsheet ID: {spreadsheet_id}")
            logger.info(f"Spreadsheet URL: {url}")
            
            self.guardar_spreadsheet_id(spreadsheet_id, url)
            
            logger.info(f"✅ Hoja creada: {nombre}")
            print(f"✅ Hoja de cálculo creada: {nombre}")
            print(f"📋 Nuevo ID: {spreadsheet_id}")
            print(f"🔗 Nueva URL: {url}")
            print(f"\n💡 IMPORTANTE: Actualiza esta URL en Facebook Catalog:")
            print(f"   {url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error obteniendo/creando spreadsheet: {e}")
            print(f"\n❌ Error: {e}")
            return False
    
    def limpiar_hojas_viejas(self):
        """
        Elimina hojas viejas antes de actualizar (para empezar limpio)
        Asegura que siempre quede al menos 1 hoja en el spreadsheet
        """
        try:
            print(f"\n🧹 Limpiando hojas viejas...")
            
            worksheets = self.spreadsheet.worksheets()
            
            # Nombres de las hojas que vamos a crear
            hojas_objetivo = ['RAW', 'FACEBOOK_CATALOG', 'VARIANTES']
            
            # Contar cuántas hojas objetivo existen
            hojas_a_eliminar = []
            for worksheet in worksheets:
                if worksheet.title in hojas_objetivo:
                    hojas_a_eliminar.append(worksheet)
            
            # Si vamos a eliminar TODAS las hojas, crear una temporal primero
            if len(hojas_a_eliminar) == len(worksheets):
                print(f"   ⚠️  Se eliminarán todas las hojas, creando hoja temporal...")
                self.spreadsheet.add_worksheet(title="Temp", rows=10, cols=10)
                print(f"   ✅ Hoja temporal creada")
            
            # Ahora eliminar las hojas viejas
            for worksheet in hojas_a_eliminar:
                try:
                    self.spreadsheet.del_worksheet(worksheet)
                    print(f"   🗑️  Eliminada hoja antigua: {worksheet.title}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar {worksheet.title}: {e}")
            
            logger.info("✅ Hojas limpias")
            print(f"   ✅ Listo para actualizar")
            
        except Exception as e:
            logger.warning(f"Error limpiando hojas: {e}")
            # No es crítico, continuar de todos modos
    
    def generar_datos_raw(self) -> List[List[Any]]:
        """Genera datos para la hoja RAW"""
        headers = [
            'SKU', 'Título', 'Descripción', 'Precio Compra', 'Precio Venta',
            'Margen %', 'Stock', 'Categoría', 'Marca', 'Item Group ID',
            'Es Variante', 'Variante Atributo', 'Variante Valor', 'Producto Base',
            'Cantidad Imágenes', 'URL Imagen Principal', 'Fecha Scraping', 'Fecha Actualización'
        ]
        
        rows = [headers]
        
        for producto in self.productos:
            precio_compra = producto.get('precio', 0)
            precio_venta = producto.get('precio_venta', 0)
            margen = 0
            if precio_compra > 0:
                margen = ((precio_venta - precio_compra) / precio_compra) * 100
            
            # Priorizar Cloudinary, fallback a Droppers
            imagenes_cloudinary = producto.get('imagenes_cloudinary', [])
            imagenes_droppers = producto.get('imagenes', [])
            
            if imagenes_cloudinary:
                url_imagen = imagenes_cloudinary[0]
            elif imagenes_droppers:
                url_imagen = imagenes_droppers[0]
            else:
                url_imagen = ''
            
            row = [
                producto.get('sku', ''), producto.get('titulo', ''),
                producto.get('descripcion', ''), precio_compra, precio_venta,
                round(margen, 2), producto.get('stock', 0),
                producto.get('categoria', ''), producto.get('marca', ''),
                producto.get('item_group_id', ''),
                'Sí' if producto.get('es_variante', False) else 'No',
                producto.get('variante_atributo', ''), producto.get('variante_valor', ''),
                producto.get('producto_base', ''), 
                len(imagenes_cloudinary) if imagenes_cloudinary else len(imagenes_droppers), 
                url_imagen,
                producto.get('fecha_scraping', ''),
                producto.get('fecha_actualizacion_variantes', '')
            ]
            
            rows.append(row)
        
        return rows
    
    def generar_datos_facebook(self) -> List[List[Any]]:
        """Genera datos para la hoja FACEBOOK_CATALOG"""
        headers = [
            'id', 'title', 'description', 'availability', 'condition', 'price',
            'link', 'image_link', 'brand', 'item_group_id', 'color', 'size',
            'additional_image_link'
        ]
        
        rows = [headers]
        
        for producto in self.productos:
            stock = producto.get('stock', 0)
            availability = 'in stock' if stock > 0 else 'out of stock'
            
            precio_venta = producto.get('precio_venta', 0)
            price = f"{precio_venta} ARS"
            
            # Priorizar Cloudinary, fallback a Droppers
            imagenes_cloudinary = producto.get('imagenes_cloudinary', [])
            imagenes_droppers = producto.get('imagenes', [])
            
            if imagenes_cloudinary:
                image_link = imagenes_cloudinary[0]
                # Facebook permite máximo 20 imágenes adicionales
                imagenes_adicionales = imagenes_cloudinary[1:21]  # Toma hasta 20 adicionales
                additional_images = ', '.join(imagenes_adicionales) if imagenes_adicionales else ''
            elif imagenes_droppers:
                image_link = imagenes_droppers[0]
                # Facebook permite máximo 20 imágenes adicionales
                imagenes_adicionales = imagenes_droppers[1:21]  # Toma hasta 20 adicionales
                additional_images = ', '.join(imagenes_adicionales) if imagenes_adicionales else ''
            else:
                image_link = ''
                additional_images = ''
            
            variante_atributo = producto.get('variante_atributo', '')
            variante_valor = producto.get('variante_valor', '')
            
            color = variante_valor if variante_atributo in ['color', 'indeterminado'] else ''
            size = variante_valor if variante_atributo in ['talle', 'numeros_talle'] else ''
            
            link = f"https://tutienda.com/producto/{producto.get('sku', '')}"
            
            row = [
                producto.get('sku', ''), producto.get('titulo', ''),
                producto.get('descripcion', ''), availability, 'new', price,
                link, image_link, producto.get('marca', ''),
                producto.get('item_group_id', ''), color, size, additional_images
            ]
            
            rows.append(row)
        
        return rows
    
    def generar_datos_variantes(self) -> List[List[Any]]:
        """Genera datos para la hoja VARIANTES"""
        headers = [
            'Item Group ID', 'Nombre Grupo', 'Tipo Variante', 'Cantidad Variantes',
            'SKUs', 'Valores Variantes', 'Precio Mínimo', 'Precio Máximo', 'Total Imágenes'
        ]
        
        rows = [headers]
        
        grupos = {}
        for producto in self.productos:
            if not producto.get('es_variante', False):
                continue
            
            item_group_id = producto.get('item_group_id', '')
            if not item_group_id:
                continue
            
            if item_group_id not in grupos:
                grupos[item_group_id] = []
            
            grupos[item_group_id].append(producto)
        
        for item_group_id, productos_grupo in sorted(grupos.items()):
            if not productos_grupo:
                continue
            
            info_grupo = self.grupos_variantes.get(item_group_id, {})
            nombre_grupo = info_grupo.get('producto_base', productos_grupo[0].get('producto_base', ''))
            tipo_variante = productos_grupo[0].get('variante_atributo', '')
            
            skus = [p.get('sku', '') for p in productos_grupo]
            valores = [p.get('variante_valor', '') for p in productos_grupo]
            
            precios = [p.get('precio_venta', 0) for p in productos_grupo]
            precio_min = min(precios) if precios else 0
            precio_max = max(precios) if precios else 0
            
            # Contar imágenes (priorizar Cloudinary)
            total_imagenes = 0
            for p in productos_grupo:
                imagenes_cloudinary = p.get('imagenes_cloudinary', [])
                imagenes_droppers = p.get('imagenes', [])
                total_imagenes += len(imagenes_cloudinary) if imagenes_cloudinary else len(imagenes_droppers)
            
            row = [
                item_group_id, nombre_grupo, tipo_variante, len(productos_grupo),
                ', '.join(skus), ', '.join(valores), precio_min, precio_max, total_imagenes
            ]
            
            rows.append(row)
        
        return rows
    
    def crear_hoja_raw(self):
        """Crea la hoja RAW (partiendo limpio)"""
        try:
            print("\n📊 Generando hoja RAW...")
            datos = self.generar_datos_raw()
            
            # Usar la primera hoja (puede ser "Temp" o cualquier otra)
            worksheets = self.spreadsheet.worksheets()
            if worksheets:
                worksheet = worksheets[0]
                worksheet.update_title('RAW')
            else:
                # No debería llegar aquí, pero por seguridad crear nueva
                worksheet = self.spreadsheet.add_worksheet(title='RAW', rows=len(datos)+100, cols=20)
            
            # Limpiar contenido previo
            worksheet.clear()
            
            worksheet.update('A1', datos)
            worksheet.format('A1:R1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.8}
            })
            logger.info(f"✅ Hoja RAW creada ({len(datos) - 1} filas)")
            print(f"✅ RAW: {len(datos) - 1} productos")
        except Exception as e:
            logger.error(f"Error creando hoja RAW: {e}")
            print(f"❌ Error en RAW: {e}")
            self.estadisticas['errores'] += 1
    
    def crear_hoja_facebook(self):
        """Crea la hoja FACEBOOK_CATALOG (partiendo limpio)"""
        try:
            print("\n📘 Generando hoja FACEBOOK_CATALOG...")
            datos = self.generar_datos_facebook()
            
            worksheet = self.spreadsheet.add_worksheet(
                title='FACEBOOK_CATALOG',
                rows=len(datos) + 100,
                cols=20
            )
            
            worksheet.update('A1', datos)
            worksheet.format('A1:M1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.26, 'green': 0.52, 'blue': 0.96}
            })
            logger.info(f"✅ Hoja FACEBOOK_CATALOG creada ({len(datos) - 1} filas)")
            print(f"✅ FACEBOOK_CATALOG: {len(datos) - 1} productos")
        except Exception as e:
            logger.error(f"Error creando hoja FACEBOOK_CATALOG: {e}")
            print(f"❌ Error en FACEBOOK_CATALOG: {e}")
            self.estadisticas['errores'] += 1
    
    def crear_hoja_variantes(self):
        """Crea la hoja VARIANTES (partiendo limpio)"""
        try:
            print("\n🔗 Generando hoja VARIANTES...")
            datos = self.generar_datos_variantes()
            
            worksheet = self.spreadsheet.add_worksheet(
                title='VARIANTES',
                rows=len(datos) + 100,
                cols=15
            )
            
            worksheet.update('A1', datos)
            worksheet.format('A1:I1', {
                'textFormat': {'bold': True},
                'backgroundColor': {'red': 0.4, 'green': 0.76, 'blue': 0.4}
            })
            logger.info(f"✅ Hoja VARIANTES creada ({len(datos) - 1} grupos)")
            print(f"✅ VARIANTES: {len(datos) - 1} grupos")
            self.estadisticas['grupos_exportados'] = len(datos) - 1
        except Exception as e:
            logger.error(f"Error creando hoja VARIANTES: {e}")
            print(f"❌ Error en VARIANTES: {e}")
            self.estadisticas['errores'] += 1
    
    def exportar_todo(self):
        """Exporta todas las hojas"""
        print(f"\n{'=' * 80}")
        print("📊 EXPORTANDO A GOOGLE SHEETS (OAUTH2)")
        print(f"{'=' * 80}")
        
        print("\n📦 Cargando productos...")
        self.cargar_productos()
        self.cargar_grupos_variantes()
        
        print(f"\n✅ {self.estadisticas['total_productos']} productos cargados")
        print(f"✅ {len(self.grupos_variantes)} grupos de variantes")
        
        print("\n🔗 Conectando a Google Sheets...")
        if not self.conectar_google_sheets():
            return False
        
        if not self.obtener_o_crear_spreadsheet():
            return False
        
        self.crear_hoja_raw()
        self.crear_hoja_facebook()
        self.crear_hoja_variantes()
        
        url = self.spreadsheet.url
        
        # Verificar si es una hoja nueva (URL diferente)
        saved_id, saved_url = self.leer_spreadsheet_id()
        url_cambio = saved_url and (saved_url != url)
        
        print(f"\n{'=' * 80}")
        print("📊 RESUMEN DE EXPORTACIÓN")
        print(f"{'=' * 80}")
        print(f"\n✅ Productos exportados: {self.estadisticas['total_productos']}")
        print(f"✅ Grupos de variantes: {self.estadisticas['grupos_exportados']}")
        
        if self.estadisticas['errores'] > 0:
            print(f"\n⚠️  Errores: {self.estadisticas['errores']}")
        
        print(f"\n{'─' * 80}")
        print("📋 HOJAS ACTUALIZADAS:")
        print("   • RAW - Todos los productos con todos los campos")
        print("   • FACEBOOK_CATALOG - Formato listo para Facebook")
        print("   • VARIANTES - Vista agrupada por item_group_id")
        print(f"{'─' * 80}")
        
        print(f"\n🔗 URL DE LA HOJA:")
        print(f"   {url}")
        
        if url_cambio:
            print(f"\n⚠️  ATENCIÓN: LA URL CAMBIÓ (hoja recreada)")
            print(f"   📝 Debes actualizar esta URL en Facebook Catalog")
        else:
            print(f"\n✅ La URL no cambió - Facebook Catalog se actualiza automáticamente")
        
        print(f"{'=' * 80}")
        
        return True


def main():
    """Ejecuta el exportador"""
    print("=" * 80)
    print("📊 EXPORTADOR A GOOGLE SHEETS (OAUTH2) - MODO ACTUALIZACIÓN")
    print("=" * 80)
    
    print("\n⚠️  IMPORTANTE:")
    print("   • Usa tu cuenta personal de Google (no Service Account)")
    print("   • Buscará la hoja 'Catálogo Ecommerce - MASTER'")
    print("   • Si existe, la ACTUALIZA (misma URL siempre)")
    print("   • Si no existe, la crea por primera vez")
    print("   • La URL nunca cambia - ideal para Facebook Catalog")
    
    confirmar = input("\n¿Exportar/Actualizar Google Sheets? (s/n): ").lower()
    
    if confirmar == 's':
        exportador = ExportadorGoogleSheetsOAuth()
        
        if exportador.exportar_todo():
            print("\n✅ Exportación/Actualización completada con éxito!")
        else:
            print("\n❌ Exportación fallida")
    else:
        print("\nExportación cancelada")


if __name__ == "__main__":
    main()
