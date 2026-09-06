#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DETECTOR DE BINARIOS EN RUTAS INUSUALES

Chequeo de integridad del repositorio: busca archivos binarios o ejecutables
que estén donde este proyecto NO debería tener ninguno.

Este repo es de código + HTML estático: los únicos binarios legítimos son
imágenes/fuentes/audio bajo las carpetas `assets/` y `data/catalogo.db`.
Cualquier otra cosa binaria (un ELF, un .exe, un .so, un .zip, un dex, un
WASM, un script con shebang colado dentro de `pages/`) es una anomalía que
hay que mirar: el sitio se publica solo desde `pages/` y los workflows de
`.github/` corren con secrets, así que un binario ahí no es un detalle.

QUÉ MARCA
  1. Firmas de ejecutable (ELF, PE/MZ, Mach-O, Java class, dex, WASM, .a/.deb)
     y de contenedores (zip, gzip, xz, 7z, rar, OLE) — en CUALQUIER ruta,
     incluso las permitidas.
  2. Archivos binarios (con bytes NUL) fuera de la allowlist de media.
  3. Binarios camuflados: extensión de imagen/fuente/audio cuyo contenido real
     no coincide con el magic number de esa extensión (polyglot / renombrado).
  4. Extensiones ejecutables por sí solas (.exe, .dll, .so, .dylib, .bin, .apk...).
  5. Scripts con shebang o con bit de ejecución fuera de `scripts/`.

MODOS
  - Por defecto analiza los archivos VERSIONADOS (`git ls-files`): es lo que
    viaja al repo público y a GitHub Pages.
  - Con `--todo` recorre el working tree completo (incluye lo gitignoreado:
    `data/productos/`, descargas, temporales), salteando venvs y caches.

USO
    python scripts/detectar_binarios_inusuales.py
    python scripts/detectar_binarios_inusuales.py --todo --json data/reporte_binarios.json
    python scripts/detectar_binarios_inusuales.py --umbral ALTA

SALIDA: 0 = limpio · 1 = hallazgos por encima del umbral · 2 = error de ejecución.

Excepciones sin tocar código: `config/binarios_permitidos.json` (opcional)
    {"archivos": ["ruta/exacta.bin"], "directorios_media": ["otra/carpeta/assets/"]}

Hallazgos ya revisados: `config/binarios_conocidos.json` (baseline). Se siguen
mostrando, con su nota, pero NO hacen fallar la corrida — salvo que cambie el
sha256 del archivo, en cuyo caso vuelve a ser un hallazgo nuevo. Se regenera
con `--registrar-baseline` (revisar y anotar cada entrada a mano después).

Sin dependencias externas (solo stdlib) a propósito: es un chequeo de
seguridad y tiene que poder correr aunque `pip install` falle.

AUTOR: Sistema Ecommerce Automation
FECHA: 2026-09-05
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SEVERIDADES = {'CRITICA': 3, 'ALTA': 2, 'MEDIA': 1}

# --- Allowlist -------------------------------------------------------------

# Binarios legítimos por ruta exacta.
ARCHIVOS_PERMITIDOS = {
    'data/catalogo.db',          # catálogo versionado (única excepción del .gitignore)
}

# Carpetas donde SÍ se esperan archivos de media (y solo media).
DIRECTORIOS_MEDIA = (
    'pages/assets/',
    'marketing_app/assets/',
    'admin_app/assets/',
    'data/productos/',           # imágenes descargadas (gitignoreadas, se ven con --todo)
    'data/imagenes/',
)

EXTENSIONES_MEDIA = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.ico', '.svg', '.avif', '.bmp',
    '.mp3', '.wav', '.ogg', '.m4a', '.mp4', '.webm', '.mov',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
    '.pdf',
}

# Extensiones que son ejecutables/librerías por definición: sospechosas siempre.
EXTENSIONES_EJECUTABLES = {
    '.exe', '.dll', '.so', '.dylib', '.bin', '.com', '.scr', '.msi', '.cpl',
    '.pyd', '.o', '.a', '.lib', '.apk', '.jar', '.class', '.dex', '.deb',
    '.rpm', '.appimage', '.elf', '.out', '.wasm', '.ps1', '.vbe', '.jse',
}

# Rutas de alto impacto: un binario acá sube a CRITICA.
# `pages/` se publica en elgadget.com.ar; `.github/` corre con los secrets.
RUTAS_CRITICAS = ('pages/', '.github/', 'config/')

# Carpetas que se saltean en modo --todo (ruido conocido, no son del proyecto).
DIRECTORIOS_EXCLUIDOS = {
    '.git', '__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env.d',
    'site-packages', '.mypy_cache', '.pytest_cache', '.ruff_cache', 'dist',
    'build', '.idea', '.vscode',
}

# --- Firmas ----------------------------------------------------------------

# (magic, descripción, severidad). Se evalúan en orden.
FIRMAS_EJECUTABLES = [
    (b'\x7fELF',             'ejecutable/librería ELF (Linux)',        'CRITICA'),
    (b'\xfe\xed\xfa\xce',    'ejecutable Mach-O 32 (macOS)',           'CRITICA'),
    (b'\xfe\xed\xfa\xcf',    'ejecutable Mach-O 64 (macOS)',           'CRITICA'),
    (b'\xce\xfa\xed\xfe',    'ejecutable Mach-O 32 LE (macOS)',        'CRITICA'),
    (b'\xcf\xfa\xed\xfe',    'ejecutable Mach-O 64 LE (macOS)',        'CRITICA'),
    (b'\xca\xfe\xba\xbe',    'Java .class / Mach-O universal',         'CRITICA'),
    (b'dex\n',               'ejecutable Android DEX',                 'CRITICA'),
    (b'\x00asm',             'módulo WebAssembly',                     'ALTA'),
    (b'!<arch>',             'archivo .a / paquete .deb',              'ALTA'),
    (b'PK\x03\x04',          'contenedor ZIP (zip/jar/whl/apk/docx)',  'ALTA'),
    (b'\x1f\x8b',            'contenedor GZIP (.gz/.tgz)',             'ALTA'),
    (b'BZh',                 'contenedor BZIP2',                       'ALTA'),
    (b'\xfd7zXZ\x00',        'contenedor XZ',                          'ALTA'),
    (b'7z\xbc\xaf\x27\x1c',  'contenedor 7-Zip',                       'ALTA'),
    (b'Rar!\x1a\x07',        'contenedor RAR',                         'ALTA'),
    (b'\xd0\xcf\x11\xe0',    'documento OLE (posible macro Office)',   'ALTA'),
]

# Magic esperado por extensión de media, para detectar binarios camuflados.
MAGIC_MEDIA = {
    '.jpg':   [b'\xff\xd8\xff'],
    '.jpeg':  [b'\xff\xd8\xff'],
    '.png':   [b'\x89PNG\r\n\x1a\n'],
    '.gif':   [b'GIF87a', b'GIF89a'],
    '.ico':   [b'\x00\x00\x01\x00', b'\x00\x00\x02\x00'],
    '.bmp':   [b'BM'],
    '.mp3':   [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2', b'\xff\xe3'],
    '.wav':   [b'RIFF'],
    '.ogg':   [b'OggS'],
    '.ttf':   [b'\x00\x01\x00\x00', b'true', b'ttcf'],
    '.otf':   [b'OTTO', b'\x00\x01\x00\x00'],
    '.woff':  [b'wOFF'],
    '.woff2': [b'wOF2'],
    '.webm':  [b'\x1aE\xdf\xa3'],
    '.pdf':   [b'%PDF-'],
    '.db':    [b'SQLite format 3\x00'],
}

TAM_CABECERA = 8192

ARCHIVO_PERMITIDOS = RAIZ / 'config' / 'binarios_permitidos.json'
ARCHIVO_BASELINE = RAIZ / 'config' / 'binarios_conocidos.json'


def _cargar_excepciones() -> None:
    """Suma la allowlist opcional de config/binarios_permitidos.json."""
    if not ARCHIVO_PERMITIDOS.exists():
        return
    try:
        extra = json.loads(ARCHIVO_PERMITIDOS.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[!] No se pudo leer {ARCHIVO_PERMITIDOS.name}: {e}", file=sys.stderr)
        return
    ARCHIVOS_PERMITIDOS.update(extra.get('archivos', []))
    globals()['DIRECTORIOS_MEDIA'] = DIRECTORIOS_MEDIA + tuple(
        extra.get('directorios_media', [])
    )


def _cargar_baseline() -> dict:
    """Hallazgos ya revisados: {(ruta, motivo, sha256): nota}.

    El sha256 forma parte de la clave a propósito: si el archivo cambia, la
    aceptación caduca y el hallazgo vuelve a fallar la corrida.
    """
    if not ARCHIVO_BASELINE.exists():
        return {}
    try:
        datos = json.loads(ARCHIVO_BASELINE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[!] No se pudo leer {ARCHIVO_BASELINE.name}: {e}", file=sys.stderr)
        return {}
    return {
        (e.get('ruta'), e.get('motivo'), e.get('sha256')): e.get('nota', '')
        for e in datos.get('hallazgos_aceptados', [])
    }


def guardar_baseline(hallazgos: list) -> None:
    """Reescribe el baseline con los hallazgos actuales, conservando las notas."""
    previas = _cargar_baseline()
    entradas = [
        {
            'ruta': h['ruta'],
            'motivo': h['motivo'],
            'sha256': h['sha256'],
            'nota': previas.get((h['ruta'], h['motivo'], h['sha256']), 'PENDIENTE DE REVISAR'),
            'registrado': datetime.now(timezone.utc).date().isoformat(),
        }
        for h in hallazgos
    ]
    ARCHIVO_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_BASELINE.write_text(
        json.dumps({'hallazgos_aceptados': entradas}, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    print(f'Baseline actualizado ({len(entradas)} entradas): {ARCHIVO_BASELINE}')


def _es_media_permitida(rel: str) -> bool:
    """True si la ruta es una carpeta de assets y la extensión es de media."""
    ext = Path(rel).suffix.lower()
    return ext in EXTENSIONES_MEDIA and rel.startswith(DIRECTORIOS_MEDIA)


def _permitido(rel: str) -> bool:
    return rel in ARCHIVOS_PERMITIDOS or _es_media_permitida(rel)


def _firma_ejecutable(cabecera: bytes):
    """Devuelve (descripción, severidad) si la cabecera es de un ejecutable."""
    for magic, desc, sev in FIRMAS_EJECUTABLES:
        if cabecera.startswith(magic):
            return desc, sev
    # 'MZ' son dos bytes ASCII imprimibles: solo cuenta si además hay NULs,
    # así un .txt que arranca con "MZ" no dispara la alerta.
    if cabecera.startswith(b'MZ') and b'\x00' in cabecera[:512]:
        return 'ejecutable PE/DOS (Windows .exe/.dll)', 'CRITICA'
    return None, None


def _es_binario(cabecera: bytes) -> bool:
    """Heurística de `git`/`grep`: hay NUL en los primeros KB."""
    return b'\x00' in cabecera


def _magic_coincide(rel: str, cabecera: bytes) -> bool:
    """Valida que el contenido corresponda a la extensión declarada."""
    ext = Path(rel).suffix.lower()

    if ext == '.webp':
        return cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP'
    if ext in ('.mp4', '.mov', '.m4a'):
        return cabecera[4:8] == b'ftyp'
    if ext == '.avif':
        return cabecera[4:8] == b'ftyp'
    if ext == '.svg':
        return not _es_binario(cabecera)

    esperados = MAGIC_MEDIA.get(ext)
    if not esperados:
        return True  # sin firma conocida: no se puede afirmar que esté mal
    return any(cabecera.startswith(m) for m in esperados)


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    try:
        with ruta.open('rb') as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b''):
                h.update(bloque)
    except OSError:
        return ''
    return h.hexdigest()


def _severidad_por_ruta(rel: str, base: str) -> str:
    """Sube un escalón la severidad si la ruta es de alto impacto.

    `pages/` se publica en el dominio, `.github/` corre con los secrets y
    `config/` guarda credenciales: lo mismo pesa más ahí que en otra carpeta.
    """
    if not rel.startswith(RUTAS_CRITICAS):
        return base
    escalado = {'MEDIA': 'ALTA', 'ALTA': 'CRITICA', 'CRITICA': 'CRITICA'}
    return escalado[base]


def analizar_archivo(rel: str, ejecutable: bool = False) -> list:
    """Analiza un archivo y devuelve la lista de hallazgos que dispara."""
    ruta = RAIZ / rel
    hallazgos = []

    try:
        if ruta.is_symlink() or not ruta.is_file():
            return []
        tamano = ruta.stat().st_size
        with ruta.open('rb') as f:
            cabecera = f.read(TAM_CABECERA)
    except OSError as e:
        print(f"[!] No se pudo leer {rel}: {e}", file=sys.stderr)
        return []

    ext = Path(rel).suffix.lower()

    def agregar(motivo, detalle, severidad):
        hallazgos.append({
            'ruta': rel,
            'severidad': severidad,
            'motivo': motivo,
            'detalle': detalle,
            'tamano_bytes': tamano,
            'sha256': _sha256(ruta),
        })

    # 1. Firma de ejecutable/contenedor: alerta aunque la ruta esté permitida.
    desc, sev = _firma_ejecutable(cabecera)
    if desc:
        agregar(
            'firma_ejecutable',
            f'Contenido de {desc}',
            _severidad_por_ruta(rel, sev),
        )

    # 2. Extensión ejecutable por sí sola.
    if ext in EXTENSIONES_EJECUTABLES:
        agregar(
            'extension_ejecutable',
            f'Extensión {ext}: este proyecto no distribuye binarios ni librerías compiladas',
            _severidad_por_ruta(rel, 'ALTA'),
        )

    permitido = _permitido(rel)

    # 3. Binario camuflado dentro de una carpeta de assets.
    if permitido and not _magic_coincide(rel, cabecera):
        agregar(
            'extension_no_coincide',
            f'La extensión {ext} no coincide con el contenido real del archivo',
            'ALTA',
        )

    # 4. Binario fuera de la allowlist.
    if not permitido and _es_binario(cabecera) and not desc:
        agregar(
            'binario_en_ruta_inusual',
            'Archivo binario en una ruta donde solo se esperan texto/código',
            _severidad_por_ruta(rel, 'ALTA'),
        )

    # 5. Scripts colados fuera de scripts/ (shebang o bit de ejecución).
    en_scripts = rel.startswith('scripts/') or rel.startswith('tests/')
    if not en_scripts:
        if cabecera.startswith(b'#!'):
            interprete = cabecera.split(b'\n', 1)[0].decode('utf-8', 'replace')
            agregar(
                'shebang_fuera_de_scripts',
                f'Script ejecutable ({interprete.strip()}) fuera de scripts/',
                _severidad_por_ruta(rel, 'MEDIA'),
            )
        elif ejecutable and ext not in ('.sh', '.py', '.vbs', '.bat'):
            agregar(
                'bit_de_ejecucion',
                'Archivo con permiso de ejecución (modo 100755) fuera de scripts/',
                'MEDIA',
            )

    return hallazgos


def listar_versionados() -> list:
    """Archivos versionados + su modo git (para detectar el bit ejecutable)."""
    salida = subprocess.run(
        ['git', 'ls-files', '-s', '-z'],
        cwd=RAIZ, capture_output=True, text=False, check=True,
    ).stdout.decode('utf-8', 'surrogateescape')

    archivos = []
    for linea in salida.split('\0'):
        if not linea:
            continue
        meta, _, rel = linea.partition('\t')
        if not rel:
            continue
        modo = meta.split(' ', 1)[0]
        if modo == '120000':      # symlink: no se lee el destino
            continue
        archivos.append((rel, modo == '100755'))
    return archivos


def listar_working_tree() -> list:
    """Todo el árbol de trabajo, salteando caches, venvs y .git."""
    archivos = []
    for carpeta, subcarpetas, nombres in os.walk(RAIZ):
        subcarpetas[:] = [d for d in subcarpetas if d not in DIRECTORIOS_EXCLUIDOS]
        for nombre in nombres:
            ruta = Path(carpeta) / nombre
            rel = ruta.relative_to(RAIZ).as_posix()
            ejecutable = os.access(ruta, os.X_OK) and not ruta.is_dir()
            archivos.append((rel, ejecutable))
    return archivos


def escanear(modo_todo: bool = False) -> dict:
    _cargar_excepciones()
    archivos = listar_working_tree() if modo_todo else listar_versionados()

    baseline = _cargar_baseline()

    hallazgos = []
    for rel, ejecutable in archivos:
        hallazgos.extend(analizar_archivo(rel, ejecutable))

    for h in hallazgos:
        clave = (h['ruta'], h['motivo'], h['sha256'])
        h['conocido'] = clave in baseline
        h['nota'] = baseline.get(clave, '')

    hallazgos.sort(key=lambda h: (h['conocido'], -SEVERIDADES[h['severidad']], h['ruta']))
    nuevos = [h for h in hallazgos if not h['conocido']]

    return {
        'generado': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'modo': 'working_tree' if modo_todo else 'versionados',
        'archivos_analizados': len(archivos),
        'total_hallazgos': len(hallazgos),
        'hallazgos_nuevos': len(nuevos),
        'por_severidad': {
            sev: sum(1 for h in nuevos if h['severidad'] == sev)
            for sev in SEVERIDADES
        },
        'hallazgos': hallazgos,
    }


def _relevantes(reporte: dict, umbral: str) -> list:
    """Hallazgos nuevos (no baseline) por encima del umbral: los que fallan."""
    return [
        h for h in reporte['hallazgos']
        if not h['conocido'] and SEVERIDADES[h['severidad']] >= SEVERIDADES[umbral]
    ]


def imprimir_reporte(reporte: dict, umbral: str, formato_ci: bool) -> None:
    print('=' * 70)
    print('DETECTOR DE BINARIOS EN RUTAS INUSUALES')
    print('=' * 70)
    print(f"Modo:       {reporte['modo']}")
    print(f"Analizados: {reporte['archivos_analizados']} archivos")
    print(f"Umbral:     {umbral} y superiores")

    conocidos = [h for h in reporte['hallazgos'] if h['conocido']]
    if conocidos:
        print(f"\nYa revisados ({len(conocidos)}, no fallan la corrida):")
        for h in conocidos:
            print(f"  · [{h['severidad']}] {h['ruta']} — {h['motivo']}"
                  + (f" ({h['nota']})" if h['nota'] else ''))

    relevantes = _relevantes(reporte, umbral)

    if not relevantes:
        print('\nSin binarios nuevos en rutas inusuales. Repo limpio.')
        return

    print(f"\n{len(relevantes)} hallazgo(s) NUEVO(s):\n")
    for h in relevantes:
        print(f"  [{h['severidad']}] {h['ruta']}")
        print(f"      motivo : {h['motivo']}")
        print(f"      detalle: {h['detalle']}")
        print(f"      tamaño : {h['tamano_bytes']} bytes · sha256 {h['sha256'][:16]}...")
        print()
        if formato_ci:
            # Anotación de GitHub Actions: aparece resaltada en el resumen.
            nivel = 'error' if h['severidad'] in ('CRITICA', 'ALTA') else 'warning'
            print(f"::{nivel} file={h['ruta']}::[{h['severidad']}] {h['motivo']} — {h['detalle']}")

    conteo = ' · '.join(
        f"{sev}: {n}" for sev, n in reporte['por_severidad'].items() if n
    )
    print(f"Resumen de hallazgos nuevos: {conteo}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Detecta binarios/ejecutables en rutas donde no deberían estar.'
    )
    parser.add_argument('--todo', action='store_true',
                        help='Recorre todo el working tree (incluye archivos gitignoreados)')
    parser.add_argument('--json', metavar='ARCHIVO',
                        help='Guarda el reporte completo en JSON')
    parser.add_argument('--umbral', choices=sorted(SEVERIDADES), default='MEDIA',
                        help='Severidad mínima para reportar y fallar (default: MEDIA)')
    parser.add_argument('--ci', action='store_true',
                        help='Emite anotaciones ::error::/::warning:: de GitHub Actions')
    parser.add_argument('--registrar-baseline', action='store_true',
                        help='Guarda los hallazgos actuales como ya revisados '
                             '(config/binarios_conocidos.json)')
    args = parser.parse_args()

    try:
        reporte = escanear(modo_todo=args.todo)
    except subprocess.CalledProcessError as e:
        print(f'[X] git ls-files falló: {e}', file=sys.stderr)
        return 2
    except OSError as e:
        print(f'[X] Error de E/S durante el escaneo: {e}', file=sys.stderr)
        return 2

    if args.registrar_baseline:
        guardar_baseline(reporte['hallazgos'])
        return 0

    imprimir_reporte(reporte, args.umbral, args.ci)

    if args.json:
        destino = Path(args.json)
        if not destino.is_absolute():
            destino = RAIZ / destino
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(reporte, indent=2, ensure_ascii=False), encoding='utf-8'
        )
        print(f'Reporte JSON: {destino}')

    return 1 if _relevantes(reporte, args.umbral) else 0


if __name__ == '__main__':
    sys.exit(main())
