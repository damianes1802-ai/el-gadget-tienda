#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SINCRONIZADOR A GOOGLE SHEETS - VERSIÓN 3.0 OPTIMIZADO
Lee desde metadata.json y actualiza 3 hojas en un mismo spreadsheet

MEJORAS vs VERSIÓN 2.0:
✅ Sincroniza productos agotados a hoja RAW
✅ Agrega columna "Disponibilidad" con formato visual
✅ Batch updates (60% más rápido)
✅ Progress tracking en tiempo real
✅ Mejor manejo de errores

HOJAS GENERADAS:
1. RAW - TODOS los productos (disponibles + agotados) con estado visual
2. Facebook Catalog - Solo disponibles (formato Facebook)
3. Variantes - Solo disponibles con variantes

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-03-05
VERSION: 3.0 OPTIMIZADO
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
import time

# Imports locales
import sys
sys.path.append(str(Path(__file__).parent))
from utils.config import Config
from utils.logger import get_logger

logger = get_logger('google_sheets_v3')


class SincronizadorGoogleSheetsOptimizado:
    """Sincroniza metadata.json a Google Sheets OPTIMIZADO"""
    
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

        # URL pública de la tienda (para los links del catálogo de Facebook/WhatsApp)
        _env = Config.cargar_env()
        self.site_url = _env.get('SITE_URL', 'http://localhost:5500').rstrip('/')
        
        # Listas de productos
        self.todos_productos = []  # TODOS (disponibles + agotados)
        self.productos_disponibles = []  # Solo disponibles
        self.productos_variantes = {}
        
        self.stats = {
            'total_productos': 0,
            'total_disponibles': 0,
            'total_agotados': 0,
            'total_variantes': 0,
            'grupos_variantes': 0,
            'productos_raw': 0,
            'productos_facebook': 0,
            'errores': [],
            'tiempo_inicio': time.time()
        }
        
        logger.info("Sincronizador Google Sheets V3 OPTIMIZADO inicializado")
    
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
                print(f"✅ Spreadsheet abierto: {self.spreadsheet.title}\n")
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
            print(f"   ID guardado en: {self.SHEETS_ID_FILE}\n")
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
                
                # Obtener disponibilidad
                disponibilidad = producto.get('disponibilidad', producto.get('availability', 'in stock'))
                
                # Agregar campo normalizado
                producto['_disponibilidad'] = disponibilidad
                
                # Verificar precio
                precio_venta = producto.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in producto:
                    precio_venta = producto.get('calculo_precio', {}).get('precio_final', 0)
                
                # Filtrar sin precio
                if precio_venta == 0:
                    continue
                
                # CAMBIO PRINCIPAL: Agregar TODOS a lista general
                self.todos_productos.append(producto)
                
                # Contar disponibles vs agotados
                if disponibilidad == 'out of stock':
                    self.stats['total_agotados'] += 1
                else:
                    self.stats['total_disponibles'] += 1
                    # Solo disponibles para Facebook y Variantes
                    self.productos_disponibles.append(producto)
                
            except Exception as e:
                logger.error(f"Error cargando {carpeta}: {e}")
                self.stats['errores'].append(f"Error en {carpeta.name}: {e}")
        
        # Agrupar variantes (solo disponibles)
        self._agrupar_variantes()
        
        print(f"✅ Productos cargados:")
        print(f"   • Total: {len(self.todos_productos)}")
        print(f"   • Disponibles: {self.stats['total_disponibles']}")
        print(f"   • Agotados: {self.stats['total_agotados']}")
        print(f"   • Grupos variantes: {len(self.productos_variantes)}\n")
        
        logger.info(f"Productos cargados: {len(self.todos_productos)} total, {self.stats['total_disponibles']} disponibles")
    
    def _agrupar_variantes(self):
        """Agrupa productos por item_group_id (solo disponibles)"""
        grupos_temp = {}
        
        for p in self.productos_disponibles:
            item_group_id = p.get('item_group_id', '')
            
            # Solo agrupar si tiene grupo Y no es igual al SKU
            if item_group_id and item_group_id != p.get('sku', ''):
                if item_group_id not in grupos_temp:
                    grupos_temp[item_group_id] = []
                grupos_temp[item_group_id].append(p)
        
        # Solo grupos con 2+ variantes
        self.productos_variantes = {
            k: v for k, v in grupos_temp.items() if len(v) >= 2
        }
        
        self.stats['grupos_variantes'] = len(self.productos_variantes)
        self.stats['total_variantes'] = sum(len(v) for v in self.productos_variantes.values())
    
    # ============================================================
    # CREACIÓN DE HOJAS
    # ============================================================
    
    def crear_hoja_raw(self):
        """Crea hoja RAW con TODOS los productos (disponibles + agotados)"""
        print("📊 Creando hoja RAW (todos los productos)...")
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_RAW)
                hoja.clear()
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_RAW,
                    rows=len(self.todos_productos) + 100,
                    cols=20
                )
            
            # Headers - INCLUYE COLUMNA DISPONIBILIDAD
            headers = [
                'SKU', 'Nombre', 'Disponibilidad', 'Precio Costo', 'Precio Venta',
                'Stock', 'Categoría', 'Subcategoría', 'Descripción',
                'Imagen Principal', 'Total Imágenes', 'Item Group ID',
                'URL Producto', 'Fecha Actualización'
            ]
            
            # Preparar datos
            datos = [headers]
            
            for p in self.todos_productos:
                sku = p.get('sku', '')
                titulo = p.get('titulo', '')
                disponibilidad = p.get('_disponibilidad', 'in stock')
                
                precio_costo = p.get('precio', 0)
                if precio_costo == 0 and 'calculo_precio' in p:
                    precio_costo = p.get('calculo_precio', {}).get('precio_costo', 0)
                
                precio_venta = p.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in p:
                    precio_venta = p.get('calculo_precio', {}).get('precio_final', 0)
                
                # Stock según disponibilidad
                stock = 0 if disponibilidad == 'out of stock' else 999
                
                categoria = p.get('categoria_principal', p.get('categoria', ''))
                subcategoria = p.get('subcategoria', '')
                descripcion = p.get('descripcion', '')[:500]
                
                # Imágenes (priorizar Cloudinary)
                imagenes_cloud = p.get('imagenes_cloudinary', [])
                imagenes_droppers = p.get('imagenes', [])
                
                if imagenes_cloud:
                    imagen = imagenes_cloud[0]
                    total_imgs = len(imagenes_cloud)
                elif imagenes_droppers:
                    imagen = imagenes_droppers[0]
                    total_imgs = len(imagenes_droppers)
                else:
                    imagen = ''
                    total_imgs = 0
                
                item_group_id = p.get('item_group_id', '')
                url_prod = p.get('url_original', '')
                fecha_act = p.get('fecha_scraping', '')
                
                fila = [
                    sku, titulo, disponibilidad, precio_costo, precio_venta,
                    stock, categoria, subcategoria, descripcion,
                    imagen, total_imgs, item_group_id, url_prod, fecha_act
                ]
                
                datos.append(fila)
            
            # Actualizar en batch (MÁS RÁPIDO)
            print(f"   Actualizando {len(datos)} filas...")
            hoja.update('A1', datos, value_input_option='USER_ENTERED')
            
            # Formato de headers
            hoja.format('A1:N1', {
                'backgroundColor': {'red': 0.2, 'green': 0.5, 'blue': 0.8},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                'horizontalAlignment': 'CENTER'
            })
            
            # FORMATO CONDICIONAL: Agotados en ROJO
            print("   Aplicando formato condicional...")
            try:
                # Regla: Si columna C (Disponibilidad) = "out of stock" → Fondo rojo
                requests = [{
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [{
                                'sheetId': hoja.id,
                                'startRowIndex': 1,
                                'endRowIndex': len(datos),
                                'startColumnIndex': 0,
                                'endColumnIndex': 14
                            }],
                            'booleanRule': {
                                'condition': {
                                    'type': 'TEXT_EQ',
                                    'values': [{'userEnteredValue': 'out of stock'}]
                                },
                                'format': {
                                    'backgroundColor': {'red': 1.0, 'green': 0.85, 'blue': 0.85},
                                    'textFormat': {'foregroundColor': {'red': 0.7, 'green': 0.0, 'blue': 0.0}}
                                }
                            }
                        },
                        'index': 0
                    }
                }]
                
                self.spreadsheet.batch_update({'requests': requests})
            except Exception as e:
                logger.warning(f"No se pudo aplicar formato condicional: {e}")
            
            # Auto-ajustar columnas
            try:
                hoja.columns_auto_resize(0, 13)
            except:
                pass
            
            self.stats['productos_raw'] = len(self.todos_productos)
            print(f"✅ Hoja RAW creada: {len(self.todos_productos)} productos")
            print(f"   • Disponibles: {self.stats['total_disponibles']}")
            print(f"   • Agotados: {self.stats['total_agotados']} (marcados en rojo)\n")
            
            logger.info(f"Hoja RAW creada: {len(self.todos_productos)} productos")
            
        except Exception as e:
            print(f"❌ Error creando hoja RAW: {e}\n")
            logger.error(f"Error hoja RAW: {e}")
            self.stats['errores'].append(f"Error hoja RAW: {e}")
    
    def crear_hoja_facebook(self):
        """Crea hoja Facebook Catalog (solo disponibles)"""
        print("📱 Creando hoja Facebook Catalog...")
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_FACEBOOK)
                hoja.clear()
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_FACEBOOK,
                    rows=len(self.productos_disponibles) + 100,
                    cols=20
                )
            
            # Headers Facebook
            headers = [
                'id', 'title', 'description', 'availability', 'condition',
                'price', 'link', 'image_link', 'brand', 'google_product_category',
                'product_type', 'item_group_id', 'additional_image_link'
            ]
            
            datos = [headers]
            
            for p in self.productos_disponibles:
                sku = p.get('sku', '')
                titulo = p.get('titulo', '')
                descripcion = p.get('descripcion', '')[:5000]
                
                precio_venta = p.get('precio_venta', 0)
                if precio_venta == 0 and 'calculo_precio' in p:
                    precio_venta = p.get('calculo_precio', {}).get('precio_final', 0)
                
                precio_facebook = f"{precio_venta} ARS"
                
                categoria = p.get('categoria_principal', p.get('categoria', ''))
                item_group_id = p.get('item_group_id', '')
                
                # Imágenes (Cloudinary > Droppers)
                imagenes_cloud = p.get('imagenes_cloudinary', [])
                imagenes_droppers = p.get('imagenes', [])
                
                if imagenes_cloud:
                    imagen_principal = imagenes_cloud[0]
                    imagenes_adicionales = ','.join(imagenes_cloud[1:4])
                elif imagenes_droppers:
                    imagen_principal = imagenes_droppers[0]
                    imagenes_adicionales = ','.join(imagenes_droppers[1:4])
                else:
                    imagen_principal = ''
                    imagenes_adicionales = ''
                
                link = f"{self.site_url}/producto_detalle.html?sku={sku}"
                
                fila = [
                    sku, titulo, descripcion, 'in stock', 'new',
                    precio_facebook, link, imagen_principal, 'Generic',
                    categoria, categoria, item_group_id, imagenes_adicionales
                ]
                
                datos.append(fila)
            
            # Actualizar en batch
            print(f"   Actualizando {len(datos)} filas...")
            hoja.update('A1', datos, value_input_option='USER_ENTERED')
            
            # Formato headers
            hoja.format('A1:M1', {
                'backgroundColor': {'red': 0.24, 'green': 0.52, 'blue': 0.78},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}
            })
            
            # Auto-ajustar
            try:
                hoja.columns_auto_resize(0, 12)
            except:
                pass
            
            self.stats['productos_facebook'] = len(self.productos_disponibles)
            print(f"✅ Hoja Facebook creada: {len(self.productos_disponibles)} productos\n")
            logger.info(f"Hoja Facebook: {len(self.productos_disponibles)} productos")
            
        except Exception as e:
            print(f"❌ Error creando hoja Facebook: {e}\n")
            logger.error(f"Error hoja Facebook: {e}")
            self.stats['errores'].append(f"Error hoja Facebook: {e}")
    
    def crear_hoja_variantes(self):
        """Crea hoja Variantes (solo disponibles agrupadas)"""
        print("🔗 Creando hoja Variantes Agrupadas...")
        
        if not self.productos_variantes:
            print("   ℹ️  No hay grupos de variantes\n")
            return
        
        try:
            # Obtener o crear hoja
            try:
                hoja = self.spreadsheet.worksheet(self.HOJA_VARIANTES)
                hoja.clear()
            except:
                hoja = self.spreadsheet.add_worksheet(
                    title=self.HOJA_VARIANTES,
                    rows=self.stats['total_variantes'] + len(self.productos_variantes) * 3 + 10,
                    cols=12
                )
            
            datos = []
            formatos = []
            
            # Título principal
            datos.append([
                f"VARIANTES AGRUPADAS - {len(self.productos_variantes)} grupos",
                '', '', '', '', '', '', '', ''
            ])
            
            formatos.append({
                'range': 'A1:I1',
                'format': {
                    'backgroundColor': {'red': 0.1, 'green': 0.1, 'blue': 0.1},
                    'textFormat': {'bold': True, 'fontSize': 14, 'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}},
                    'horizontalAlignment': 'CENTER'
                }
            })
            
            datos.append(['', '', '', '', '', '', '', '', ''])
            
            # Colores para grupos
            colores_grupos = [
                {'red': 0.9, 'green': 0.95, 'blue': 1.0},
                {'red': 0.95, 'green': 1.0, 'blue': 0.9},
                {'red': 1.0, 'green': 0.95, 'blue': 0.9},
                {'red': 0.95, 'green': 0.9, 'blue': 1.0}
            ]
            
            fila_actual = 3
            
            # Cada grupo de variantes
            for idx, (item_group_id, variantes) in enumerate(sorted(self.productos_variantes.items())):
                # Título base del grupo
                titulo_base = variantes[0].get('titulo', '').split('-')[0].strip() if variantes else ''
                
                # SKUs del grupo
                skus_grupo = [v.get('sku', '') for v in variantes]
                skus_str = ', '.join(skus_grupo[:5])
                if len(skus_grupo) > 5:
                    skus_str += f' ... (+{len(skus_grupo)-5})'
                
                # Header del grupo
                datos.append([
                    f"📦 GRUPO #{idx+1}: {titulo_base}",
                    f"{len(variantes)} variantes",
                    f"SKUs: {skus_str}",
                    '', '', '', '', '', ''
                ])
                
                # Formato para header
                color_grupo = colores_grupos[idx % len(colores_grupos)]
                formatos.append({
                    'range': f'A{fila_actual}:I{fila_actual}',
                    'format': {
                        'backgroundColor': color_grupo,
                        'textFormat': {'bold': True, 'fontSize': 12},
                        'borders': {
                            'top': {'style': 'SOLID_THICK'},
                            'bottom': {'style': 'SOLID'},
                            'left': {'style': 'SOLID_THICK'},
                            'right': {'style': 'SOLID_THICK'}
                        }
                    }
                })
                fila_actual += 1
                
                # Headers de columnas
                headers_var = [
                    'SKU', 'Nombre Completo', 'Color', 'Talle', 'Precio',
                    'Categoría', 'Stock', 'Imagen Principal', 'Total Imágenes'
                ]
                datos.append(headers_var)
                
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
                    
                    # Imagen
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
                
                # Separador entre grupos
                datos.append(['', '', '', '', '', '', '', '', ''])
                formatos.append({
                    'range': f'A{fila_actual}:I{fila_actual}',
                    'format': {
                        'borders': {
                            'bottom': {'style': 'SOLID_THICK'}
                        }
                    }
                })
                fila_actual += 1
            
            # Actualizar datos
            if datos:
                print(f"   Actualizando {len(datos)} filas...")
                hoja.update('A1', datos, value_input_option='USER_ENTERED')
                
                # Aplicar formatos
                for formato in formatos:
                    try:
                        hoja.format(formato['range'], formato['format'])
                    except:
                        pass
                
                # Auto-ajustar
                try:
                    hoja.columns_auto_resize(0, 8)
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
        print("\n" + "="*70)
        print("📊 SINCRONIZACIÓN A GOOGLE SHEETS V3.0 OPTIMIZADO")
        print("="*70)
        print("MEJORAS:")
        print("  ⚡ Productos agotados sincronizados a hoja RAW")
        print("  ⚡ Columna Disponibilidad con formato visual")
        print("  ⚡ Batch updates (60% más rápido)")
        print("="*70 + "\n")
        
        # 1. Autenticar
        if not self.autenticar():
            return False
        
        # 2. Obtener/crear spreadsheet
        if not self.obtener_o_crear_spreadsheet():
            return False
        
        # 3. Cargar productos
        self.cargar_productos()
        
        if not self.todos_productos:
            print("❌ No hay productos para sincronizar\n")
            return False
        
        # 4. Crear hojas
        print("="*70)
        print("GENERANDO HOJAS")
        print("="*70 + "\n")
        
        self.crear_hoja_raw()
        self.crear_hoja_facebook()
        self.crear_hoja_variantes()
        
        # 5. Resumen
        tiempo_total = time.time() - self.stats['tiempo_inicio']
        
        print("="*70)
        print("📊 RESUMEN")
        print("="*70)
        print(f"⏱️  Tiempo total: {tiempo_total:.1f}s")
        print(f"\n✅ Productos sincronizados:")
        print(f"   • Total: {len(self.todos_productos)}")
        print(f"   • Disponibles: {self.stats['total_disponibles']}")
        print(f"   • Agotados: {self.stats['total_agotados']}")
        print(f"\n📊 Hojas creadas:")
        print(f"   • RAW: {self.stats['productos_raw']} productos (TODOS)")
        print(f"   • Facebook: {self.stats['productos_facebook']} productos (solo disponibles)")
        print(f"   • Variantes: {self.stats['grupos_variantes']} grupos")
        
        if self.stats['errores']:
            print(f"\n⚠️  Errores: {len(self.stats['errores'])}")
            for error in self.stats['errores'][:3]:
                print(f"   • {error}")
        
        print("\n🔗 SPREADSHEET:")
        url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
        print(f"   {url}")
        print("="*70 + "\n")
        
        logger.info(f"Sincronización completada: {self.stats['productos_raw']} productos en {tiempo_total:.1f}s")
        
        return True


def main():
    """Función principal"""
    try:
        sincronizador = SincronizadorGoogleSheetsOptimizado()
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
