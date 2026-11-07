# -*- coding: utf-8 -*-
"""Tests del sistema de insumos.

Es un paquete (y no una carpeta suelta) a propósito: el repo ya tiene un
`tests/conftest.py` en la raíz, y sin `__init__.py` un `import conftest` desde
acá podía resolver a CUALQUIERA de los dos según el orden de `sys.path`.
Como paquete, los módulos se importan por su ruta completa y no hay ambigüedad.
"""
