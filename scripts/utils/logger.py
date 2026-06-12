#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE LOGGING CENTRALIZADO
Gestiona logs para todos los módulos del sistema
"""

import logging
import os
from datetime import datetime
from pathlib import Path

# Directorio de logs
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

class LoggerManager:
    """Gestiona la creación y configuración de loggers"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, nombre_modulo):
        """
        Obtiene o crea un logger para el módulo especificado
        
        Args:
            nombre_modulo (str): Nombre del módulo (ej: 'scraper', 'imagenes', 'ia')
        
        Returns:
            logging.Logger: Logger configurado
        """
        
        if nombre_modulo in cls._loggers:
            return cls._loggers[nombre_modulo]
        
        # Crear logger
        logger = logging.getLogger(nombre_modulo)
        logger.setLevel(logging.DEBUG)
        
        # Evitar duplicación de handlers
        if logger.handlers:
            return logger
        
        # Formato de logs
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para archivo (logs detallados)
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        archivo_log = LOGS_DIR / f"{nombre_modulo}_{fecha_hoy}.log"
        
        file_handler = logging.FileHandler(archivo_log, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Handler para consola (solo INFO y superior)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Agregar handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Guardar en caché
        cls._loggers[nombre_modulo] = logger
        
        return logger
    
    @classmethod
    def log_separador(cls, logger, titulo=""):
        """Agrega un separador visual en los logs"""
        separador = "=" * 80
        if titulo:
            logger.info(separador)
            logger.info(f"  {titulo}")
            logger.info(separador)
        else:
            logger.info(separador)
    
    @classmethod
    def log_inicio_proceso(cls, logger, nombre_proceso, total_items=None):
        """Log estandarizado para inicio de procesos"""
        cls.log_separador(logger, f"INICIO: {nombre_proceso}")
        if total_items:
            logger.info(f"Items a procesar: {total_items}")
        logger.info(f"Hora de inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    @classmethod
    def log_fin_proceso(cls, logger, nombre_proceso, items_procesados=None, items_error=None):
        """Log estandarizado para fin de procesos"""
        logger.info(f"Hora de finalización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if items_procesados is not None:
            logger.info(f"Items procesados exitosamente: {items_procesados}")
        if items_error is not None:
            logger.info(f"Items con errores: {items_error}")
        cls.log_separador(logger, f"FIN: {nombre_proceso}")


# Función helper para usar directamente
def get_logger(nombre_modulo):
    """Atajo para obtener un logger"""
    return LoggerManager.get_logger(nombre_modulo)


if __name__ == "__main__":
    # Test del sistema de logging
    logger = get_logger("test")
    
    LoggerManager.log_inicio_proceso(logger, "Test del Sistema de Logging", total_items=5)
    
    logger.debug("Esto es un mensaje DEBUG (solo en archivo)")
    logger.info("Esto es un mensaje INFO (consola + archivo)")
    logger.warning("Esto es un WARNING")
    logger.error("Esto es un ERROR")
    
    try:
        1 / 0
    except Exception as e:
        logger.exception("Esto es una EXCEPTION con traceback completo")
    
    LoggerManager.log_fin_proceso(logger, "Test del Sistema de Logging", 
                                   items_procesados=4, items_error=1)
    
    print(f"\n✅ Log guardado en: {LOGS_DIR}/test_{datetime.now().strftime('%Y-%m-%d')}.log")
