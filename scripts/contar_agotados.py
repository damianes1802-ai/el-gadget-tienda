import json
from pathlib import Path

productos_dir = Path('../data/productos')
agotados = 0
disponibles = 0
sin_campo = 0

for carpeta in productos_dir.iterdir():
    if not carpeta.is_dir():
        continue
    
    meta_file = carpeta / 'metadata.json'
    if not meta_file.exists():
        continue
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        
        disponibilidad = meta.get('disponibilidad', meta.get('availability', ''))
        
        if disponibilidad == 'out of stock':
            agotados += 1
        elif disponibilidad == 'in stock':
            disponibles += 1
        else:
            sin_campo += 1
    except:
        pass

total = agotados + disponibles + sin_campo

print(f"\n📊 ESTADO DE PRODUCTOS:\n")
print(f"Total productos: {total}")
print(f"✅ Disponibles: {disponibles}")
print(f"🔴 Agotados: {agotados}")
print(f"⚠️  Sin campo disponibilidad: {sin_campo}")
print()
