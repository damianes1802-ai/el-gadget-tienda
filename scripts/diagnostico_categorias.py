import json
from pathlib import Path

# Leer reporte de categorías
reporte_file = Path('../data/reporte_categorias_droppers.json')

if reporte_file.exists():
    with open(reporte_file, 'r', encoding='utf-8') as f:
        reporte = json.load(f)
    
    print("\n📊 ANÁLISIS DEL REPORTE DE CATEGORÍAS\n")
    print("="*60)
    
    categorias = reporte.get('categorias', {})
    
    for nombre, datos in sorted(categorias.items(), key=lambda x: x[1]['total'], reverse=True):
        print(f"📁 {nombre}: {datos['total']} productos")
    
    print("="*60)
    
    # Verificar algunos metadata
    print("\n🔍 VERIFICANDO METADATA DE PRODUCTOS\n")
    
    productos_dir = Path('../data/productos')
    
    # Tomar 5 productos al azar
    count = 0
    for carpeta in productos_dir.iterdir():
        if count >= 5:
            break
        
        if not carpeta.is_dir():
            continue
        
        meta_file = carpeta / 'metadata.json'
        if not meta_file.exists():
            continue
        
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        sku = meta.get('sku', carpeta.name)
        cat_principal = meta.get('categoria_principal', '')
        cats_secundarias = meta.get('categorias_secundarias', [])
        todas = meta.get('todas_las_categorias', [])
        
        print(f"SKU: {sku}")
        print(f"  Principal: {cat_principal}")
        print(f"  Secundarias: {cats_secundarias}")
        print(f"  Todas: {todas}")
        print()
        
        count += 1

else:
    print("❌ No existe el reporte de categorías")
