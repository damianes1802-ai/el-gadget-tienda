#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SINCRONIZADOR A GOOGLE SHEETS - VERSIÓN 2.0
Lee desde metadata.json y actualiza 3 hojas en un mismo spreadsheet

HOJAS GENERADAS:
1. RAW - Todos los datos para uso interno
2. Facebook Catalog - Formato oficial de Facebook
3. Variantes - Productos con variantes agrupados visualmente

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-02-22
VERSION: 2.0
"""

import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import gspread
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('google_sheets_v2')


class SincronizadorGoogleSheets:
    """Sincroniza metadata.json a Google Sheets con 3 hojas especializadas"""
    
    # Scopes de Google
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]
    
    # Archivos de configuración
    CREDENTIALS_FILE = Config.CONFIG_DIR / 'credentials.json'
    TOKEN_FILE = Config.CONFIG_DIR / 'token.pickle'
    SHEETS_ID_FILE = Config.CONFIG_DIR / 'sheets_id.txt'
    
    # Nombres de las hojas
    HOJA_RAW = "Productos RAW"
    HOJA_FACEBOOK = "Facebook Catalog"
    HOJA_VARIANTES = "Variantes Agrupadas"
    
    def __init__(self):
        """Inicializa el sincronizador"""
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_id = None
        
        self.productos = []
        self.productos_variantes = {}
        
        self.stats = {
            'total_productos': 0,
            'total_disponibles': 0,
            'total_variantes': 0,
            'grupos_variantes': 0,
            'productos_raw': 0,
            'productos_facebook': 0,
            'errores': []
        }
        
        logger.info("Sincronizador Google Sheets V2 inicializado")
    
    # ============================================================
    # AUTENTICACIÓN GOOGLE
    # ============================================================
    
    def autenticar(self) -> bool:
        """Autentica con Google usando OAuth2"""
        print("🔐 Autenticando con Google...")
        
        creds = None
        
        # Cargar token guardado
        if self.TOKEN_FILE.exists():
            with open(self.TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        # Si no hay credenciales válidas
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("   Renovando token...")
                creds.refresh(Request())
            else:
                if not self.CREDENTIALS_FILE.exists():
                    print(f"❌ No existe: {self.CREDENTIALS_FILE}")
                    print("   Descargá credentials.json de Google Cloud Console")
                    return False
                
                print("   Abriendo navegador para autenticación...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.CREDENTIALS_FILE), 
                    self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Guardar token
            with open(self.TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        # Crear cliente
        self.client = gspread.authorize(creds)
        print("✅ Autenticación exitosa\n")
        logger.info("Autenticación exitosa")
        
        return True
    
    def obtener_o_crear_spreadsheet(self) -> bool:
        """Obtiene spreadsheet existente o crea uno nuevo"""
        
        # Intentar leer ID guardado
        if self.SHEETS_ID_FILE.exists():
            with open(self.SHEETS_ID_FILE, 'r', encoding='utf-8') as f:
                lines = f.read().strip().split('\n')
                if lines and lines[0]:
                    self.spreadsheet_id = lines[0]
        
        # Intentar abrir spreadsheet existente
        if self.spreadsheet_id:
            try:
                print(f"📄 Abriendo spreadsheet existente...")
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                print(f"✅ Spreadsheet abierto: {self.spreadsheet.title}")
                logger.info(f"Spreadsheet abierto: {self.spreadsheet_id}")
                return True
            except Exception as e:
                print(f"⚠️  No se pudo abrir spreadsheet guardado: {e}")
                logger.warning(f"Spreadsheet guardado no accesible: {e}")
                self.spreadsheet_id = None
        
        # Crear nuevo spreadsheet
        try:
            print("📝 Creando nuevo spreadsheet...")
            titulo = f"Catálogo Ecommerce - {datetime.now().strftime('%Y-%m-%d')}"
            self.spreadsheet = self.client.create(titulo)
            self.spreadsheet_id = self.spreadsheet.id
            
            # Guardar ID
            with open(self.SHEETS_ID_FILE, 'w', encoding='utf-8') as f:
                f.write(f"{self.spreadsheet_id}\n")
                f.write(f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}\n")
            
            print(f"✅ Spreadsheet creado: {titulo}")
            print(f"   ID guardado en: {self.SHEETS_ID_FILE}")
            logger.info(f"Nuevo spreadsheet creado: {self.spreadsheet_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creando spreadsheet: {e}")
            logger.error(f"Error creando spreadsheet: {e}")
            return False
    
    # ============================================================
    # CARGA DE DATOS
    # ============================================================
    
    def cargar_productos(self):
        """Carga productos desde metadata.json"""
        print("📦 Cargando productos desde metadata...\n")
        
        productos_dir = Config.PRODUCTOS_DIR
        
        # Primera pasada: cargar todos los productos
        todos_productos = []
        
        for carpeta in productos_dir.iterdir():
            if not carpeta.is_dir():
                continue
            
            metadata_file = carpeta / 'metadata.json'
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    producto = json.load(f)
                
                self.stats['total_productos'] += 1
                
                # Solo productos disponibles
                disponibilidad = producto.get('disponibilidad', producto.get('availability', 'in stock'))
                if disponibilidad == 'out of stock':
                    continue
                
                # Solo productos con precio
                precio_venta = producto.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in producto:
                    precio_venta = producto.get('calculo_precio', {}).get('precio_final', 0)
                
                if precio_venta == 0:
                    continue
                
                self.stats['total_disponibles'] += 1
                todos_productos.append(producto)
                
            except Exception as e:
                logger.error(f"Error cargando {carpeta}: {e}")
                self.stats['errores'].append(f"Error en {carpeta.name}: {e}")
        
        # Segunda pasada: detectar variantes por patrones de SKU
        import re
        from collections import defaultdict
        
        # Agrupar por base de SKU
        grupos_sku = defaultdict(list)
        
        for producto in todos_productos:
            sku = producto.get('sku', '')
            
            # Detectar patrón base del SKU
            # Ejemplos:
            # 600003-CE, 600003-FU, 600003-NA → base: 600003
            # DL1063-CE, DL1063-RO → base: DL1063
            # WH7184, WH7184-1-L, WH7184-1-M → base: WH7184
            
            # Quitar sufijos comunes de variantes
            base_match = re.match(r'^([A-Z0-9-]+?)(?:-[A-Z]{1,4})?(?:-\d)?(?:-[A-Z]{1,3})?$', sku)
            if base_match:
                base = base_match.group(1)
                # Limpiar base (quitar guiones finales)
                base = base.rstrip('-')
            else:
                base = sku
            
            grupos_sku[base].append(producto)
        
        # Identificar grupos de variantes (2 o más productos con misma base)
        for base, productos_grupo in grupos_sku.items():
            if len(productos_grupo) > 1:
                # Es un grupo de variantes
                item_group_id = f"grupo_{base}"
                self.productos_variantes[item_group_id] = productos_grupo
                self.stats['total_variantes'] += len(productos_grupo)
            
            # Agregar todos a la lista principal
            self.productos.extend(productos_grupo)
        
        self.stats['grupos_variantes'] = len(self.productos_variantes)
        
        print(f"✅ {self.stats['total_disponibles']} productos disponibles cargados")
        print(f"   ({self.stats['total_variantes']} variantes en {self.stats['grupos_variantes']} grupos)")
        print()
    
    # ============================================================
    # HOJA 1: RAW (Datos completos)
    # ============================================================
    
    def crear_hoja_raw(self):
        """Crea hoja RAW con todos los datos"""
        print(f"📊 Generando hoja: {self.HOJA_RAW}...")
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_RAW)
                hoja.clear()  # Limpiar contenido
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_RAW,
                    rows=len(self.productos) + 100,
                    cols=30
                )
            
            # Headers
            headers = [
                'SKU',
                'Nombre',
                'Descripción',
                'Precio Costo',
                'Precio Venta',
                'Categoría Principal',
                'Categorías Secundarias',
                'Item Group ID',
                'Es Variante',
                'Color',
                'Talle',
                'Stock',
                'Imágenes Droppers',
                'Imágenes Cloudinary',
                'URL Original',
                'Fecha Scraping',
                'Disponibilidad'
            ]
            
            datos = [headers]
            
            # Datos
            for prod in self.productos:
                sku = prod.get('sku', '')
                titulo = prod.get('titulo', '')
                descripcion = prod.get('descripcion', '')[:500]  # Limitar
                
                precio = prod.get('precio', 0)
                precio_venta = prod.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in prod:
                    precio_venta = prod.get('calculo_precio', {}).get('precio_final', 0)
                
                categoria = prod.get('categoria_principal', prod.get('categoria', ''))
                cats_sec = ', '.join(prod.get('categorias_secundarias', []))
                
                item_group = prod.get('item_group_id', '')
                es_variante = 'Sí' if prod.get('es_variante', False) else 'No'
                color = prod.get('color', '')
                talle = prod.get('talle', '')
                stock = 999  # Siempre en stock
                
                imagenes_droppers = ', '.join(prod.get('imagenes', [])[:3])
                imagenes_cloudinary = ', '.join(prod.get('imagenes_cloudinary', [])[:3])
                
                url_original = prod.get('url_original', '')
                fecha_scraping = prod.get('fecha_scraping', '')
                disponibilidad = prod.get('disponibilidad', 'in stock')
                
                fila = [
                    sku, titulo, descripcion, precio, precio_venta,
                    categoria, cats_sec, item_group, es_variante,
                    color, talle, stock, imagenes_droppers,
                    imagenes_cloudinary, url_original, fecha_scraping,
                    disponibilidad
                ]
                
                datos.append(fila)
            
            # Actualizar hoja
            hoja.update('A1', datos, value_input_option='USER_ENTERED')
            
            # Formato
            hoja.format('A1:Q1', {
                'backgroundColor': {'red': 0.2, 'green': 0.6, 'blue': 0.9},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            # Congelar primera fila
            hoja.freeze(rows=1)
            
            self.stats['productos_raw'] = len(datos) - 1
            
            print(f"✅ Hoja RAW creada: {len(datos)-1} productos\n")
            logger.info(f"Hoja RAW: {len(datos)-1} productos")
            
        except Exception as e:
            print(f"❌ Error creando hoja RAW: {e}\n")
            logger.error(f"Error hoja RAW: {e}")
            self.stats['errores'].append(f"Error hoja RAW: {e}")
    
    # ============================================================
    # HOJA 2: FACEBOOK CATALOG
    # ============================================================
    
    def crear_hoja_facebook(self):
        """Crea hoja en formato Facebook Catalog"""
        print(f"📱 Generando hoja: {self.HOJA_FACEBOOK}...")
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_FACEBOOK)
                hoja.clear()
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_FACEBOOK,
                    rows=len(self.productos) + 100,
                    cols=25
                )
            
            # Headers oficiales de Facebook
            headers = [
                'id',
                'title',
                'description',
                'availability',
                'condition',
                'price',
                'link',
                'image_link',
                'additional_image_link',
                'brand',
                'google_product_category',
                'product_type',
                'item_group_id',
                'color',
                'size',
                'age_group',
                'gender'
            ]
            
            datos = [headers]
            
            # Datos
            for prod in self.productos:
                sku = prod.get('sku', '')
                titulo = prod.get('titulo', '')
                descripcion = prod.get('descripcion', '')[:5000]  # FB permite 5000
                
                # Precio en formato Facebook (con currency)
                precio_venta = prod.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in prod:
                    precio_venta = prod.get('calculo_precio', {}).get('precio_final', 0)
                
                precio_fb = f"{int(precio_venta)} ARS"
                
                # Disponibilidad
                disponibilidad = 'in stock'  # Solo disponibles llegan aquí
                
                # Condición
                condition = 'new'
                
                # Link del producto (tu ecommerce)
                link = f"https://tutienda.com/producto/{sku}"  # Actualizar con tu dominio
                
                # Imágenes (priorizar Cloudinary)
                imagenes_cloud = prod.get('imagenes_cloudinary', [])
                imagenes_droppers = prod.get('imagenes', [])
                
                if imagenes_cloud:
                    image_link = imagenes_cloud[0]
                    additional = imagenes_cloud[1:20]  # Máximo 20 adicionales
                elif imagenes_droppers:
                    image_link = imagenes_droppers[0]
                    additional = imagenes_droppers[1:20]
                else:
                    image_link = ''
                    additional = []
                
                additional_str = ', '.join(additional) if additional else ''
                
                # Brand
                brand = 'Tu Marca'  # Actualizar
                
                # Categoría
                categoria = prod.get('categoria_principal', prod.get('categoria', ''))
                
                # Variantes
                item_group = prod.get('item_group_id', '')
                color = prod.get('color', '')
                talle = prod.get('talle', '')
                
                # Demografía
                age_group = 'adult'
                gender = 'unisex'
                
                fila = [
                    sku, titulo, descripcion, disponibilidad, condition,
                    precio_fb, link, image_link, additional_str, brand,
                    '', categoria, item_group, color, talle,
                    age_group, gender
                ]
                
                datos.append(fila)
            
            # Actualizar hoja
            hoja.update('A1', datos, value_input_option='USER_ENTERED')
            
            # Formato
            hoja.format('A1:Q1', {
                'backgroundColor': {'red': 0.26, 'green': 0.52, 'blue': 0.96},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            hoja.freeze(rows=1)
            
            self.stats['productos_facebook'] = len(datos) - 1
            
            print(f"✅ Hoja Facebook creada: {len(datos)-1} productos\n")
            logger.info(f"Hoja Facebook: {len(datos)-1} productos")
            
        except Exception as e:
            print(f"❌ Error creando hoja Facebook: {e}\n")
            logger.error(f"Error hoja Facebook: {e}")
            self.stats['errores'].append(f"Error hoja Facebook: {e}")
    
    # ============================================================
    # HOJA 3: VARIANTES AGRUPADAS
    # ============================================================
    
    def crear_hoja_variantes(self):
        """Crea hoja con variantes agrupadas visualmente"""
        print(f"🎨 Generando hoja: {self.HOJA_VARIANTES}...")
        
        if not self.productos_variantes:
            print("   ℹ️  No hay productos con variantes\n")
            return
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_VARIANTES)
                hoja.clear()
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_VARIANTES,
                    rows=1000,
                    cols=12
                )
            
            datos = []
            fila_actual = 1
            
            # Colores alternos para grupos
            colores_grupos = [
                {'red': 0.93, 'green': 0.95, 'blue': 1.0},    # Azul claro
                {'red': 1.0, 'green': 0.93, 'blue': 0.93},    # Rosa claro
                {'red': 0.93, 'green': 1.0, 'blue': 0.93},    # Verde claro
                {'red': 1.0, 'green': 1.0, 'blue': 0.85},     # Amarillo claro
            ]
            
            formatos = []
            
            for idx, (group_id, variantes) in enumerate(sorted(self.productos_variantes.items())):
                # Determinar nombre del grupo desde el primer producto
                primer_prod = variantes[0]
                titulo_completo = primer_prod.get('titulo', '')
                
                # Quitar sufijos de variante del título
                # Ej: "Bolso - Color Negro" → "Bolso"
                import re
                titulo_base = re.split(r'\s*-\s*(?:Color|Talle|Talla|Tamaño)', titulo_completo)[0].strip()
                
                # SKUs del grupo
                skus_grupo = [v.get('sku', '') for v in variantes]
                skus_str = ', '.join(skus_grupo[:5])  # Mostrar máximo 5
                if len(skus_grupo) > 5:
                    skus_str += f' ... (+{len(skus_grupo)-5})'
                
                # Header del grupo
                datos.append([
                    f"📦 GRUPO #{idx+1}: {titulo_base}",
                    f"{len(variantes)} variantes",
                    f"SKUs: {skus_str}",
                    '', '', '', '', '', '', '', '', ''
                ])
                
                # Formato para header del grupo
                color_grupo = colores_grupos[idx % len(colores_grupos)]
                formatos.append({
                    'range': f'A{fila_actual}:L{fila_actual}',
                    'format': {
                        'backgroundColor': color_grupo,
                        'textFormat': {'bold': True, 'fontSize': 12},
                        'borders': {
                            'top': {'style': 'SOLID_THICK', 'width': 2},
                            'bottom': {'style': 'SOLID'},
                            'left': {'style': 'SOLID_THICK', 'width': 2},
                            'right': {'style': 'SOLID_THICK', 'width': 2}
                        }
                    }
                })
                fila_actual += 1
                
                # Headers de columnas
                headers = [
                    'SKU', 'Nombre Completo', 'Color', 'Talle', 'Precio',
                    'Categoría', 'Stock', 'Imagen Principal', 'Total Imágenes'
                ]
                datos.append(headers)
                
                # Formato para headers
                formatos.append({
                    'range': f'A{fila_actual}:I{fila_actual}',
                    'format': {
                        'backgroundColor': {'red': 0.75, 'green': 0.75, 'blue': 0.75},
                        'textFormat': {'bold': True, 'fontSize': 9}
                    }
                })
                fila_actual += 1
                
                # Variantes del grupo
                for variante in variantes:
                    sku = variante.get('sku', '')
                    titulo = variante.get('titulo', '')
                    color = variante.get('color', '')
                    talle = variante.get('talle', variante.get('size', ''))
                    
                    precio_venta = variante.get('precio_venta', 0)
                    if precio_venta == 0 and 'calculo_precio' in variante:
                        precio_venta = variante.get('calculo_precio', {}).get('precio_final', 0)
                    
                    categoria = variante.get('categoria_principal', variante.get('categoria', ''))
                    stock = 999
                    
                    # Imagen principal
                    imagenes_cloud = variante.get('imagenes_cloudinary', [])
                    imagenes_droppers = variante.get('imagenes', [])
                    
                    if imagenes_cloud:
                        imagen = imagenes_cloud[0]
                        total_imgs = len(imagenes_cloud)
                    elif imagenes_droppers:
                        imagen = imagenes_droppers[0]
                        total_imgs = len(imagenes_droppers)
                    else:
                        imagen = ''
                        total_imgs = 0
                    
                    datos.append([
                        sku, titulo, color, talle, f"${precio_venta:.0f}",
                        categoria, stock, imagen, total_imgs
                    ])
                    
                    # Formato para variante
                    formatos.append({
                        'range': f'A{fila_actual}:I{fila_actual}',
                        'format': {
                            'backgroundColor': color_grupo,
                            'borders': {
                                'left': {'style': 'SOLID'},
                                'right': {'style': 'SOLID'}
                            }
                        }
                    })
                    fila_actual += 1
                
                # Línea separadora entre grupos
                datos.append(['', '', '', '', '', '', '', '', ''])
                formatos.append({
                    'range': f'A{fila_actual}:I{fila_actual}',
                    'format': {
                        'borders': {
                            'bottom': {'style': 'SOLID_THICK', 'width': 2}
                        }
                    }
                })
                fila_actual += 1
            
            # Actualizar datos
            if datos:
                hoja.update('A1', datos, value_input_option='USER_ENTERED')
                
                # Aplicar formatos
                for formato in formatos:
                    try:
                        hoja.format(formato['range'], formato['format'])
                    except Exception as e:
                        logger.debug(f"Error aplicando formato: {e}")
                        pass  # Ignorar errores de formato
                
                # Ajustar anchos de columna
                try:
                    hoja.format('A:A', {'numberFormat': {'type': 'TEXT'}})  # SKU como texto
                    hoja.columns_auto_resize(0, 8)  # Auto-ajustar columnas A-I
                except:
                    pass
            
            print(f"✅ Hoja Variantes creada: {len(self.productos_variantes)} grupos\n")
            logger.info(f"Hoja Variantes: {len(self.productos_variantes)} grupos")
            
        except Exception as e:
            print(f"❌ Error creando hoja Variantes: {e}\n")
            logger.error(f"Error hoja Variantes: {e}")
            self.stats['errores'].append(f"Error hoja Variantes: {e}")
    
    # ============================================================
    # EJECUCIÓN
    # ============================================================
    
    def ejecutar(self):
        """Ejecuta la sincronización completa"""
        print("\n" + "="*60)
        print("📊 SINCRONIZACIÓN A GOOGLE SHEETS")
        print("="*60 + "\n")
        
        # 1. Autenticar
        if not self.autenticar():
            return False
        
        # 2. Obtener/crear spreadsheet
        if not self.obtener_o_crear_spreadsheet():
            return False
        
        # 3. Cargar productos
        self.cargar_productos()
        
        if not self.productos:
            print("❌ No hay productos para sincronizar\n")
            return False
        
        # 4. Crear hojas
        print("="*60)
        print("GENERANDO HOJAS")
        print("="*60 + "\n")
        
        self.crear_hoja_raw()
        self.crear_hoja_facebook()
        self.crear_hoja_variantes()
        
        # 5. Resumen
        print("="*60)
        print("📊 RESUMEN")
        print("="*60)
        print(f"✅ Productos sincronizados: {self.stats['total_disponibles']}")
        print(f"   • Hoja RAW: {self.stats['productos_raw']}")
        print(f"   • Hoja Facebook: {self.stats['productos_facebook']}")
        print(f"   • Grupos variantes: {self.stats['grupos_variantes']}")
        
        if self.stats['errores']:
            print(f"\n⚠️  Errores: {len(self.stats['errores'])}")
            for error in self.stats['errores'][:3]:
                print(f"   • {error}")
        
        print("\n🔗 SPREADSHEET:")
        url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
        print(f"   {url}")
        print("="*60 + "\n")
        
        logger.info(f"Sincronización completada: {self.stats['total_disponibles']} productos")
        
        return True


def main():
    """Función principal"""
    try:
        sincronizador = SincronizadorGoogleSheets()
        exitoso = sincronizador.ejecutar()
        
        return 0 if exitoso else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Sincronización interrumpida")
        return 1
    
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        logger.exception("Error fatal")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
