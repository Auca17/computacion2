"""Configuración de la plataforma, leída de variables de entorno."""

import os

WORKERS = int(os.getenv("WORKERS", "4"))
TIMEOUT_DEFECTO = float(os.getenv("TIMEOUT_DEFECTO", "30"))
GRACIA_APAGADO = float(os.getenv("GRACIA_APAGADO", "10"))
MODO_CPU = os.getenv("MODO_CPU", "executor")  # "executor" o "bloqueante"
DIR_VOLCADOS = os.getenv("DIR_VOLCADOS", "./datos")
MAX_COLA = int(os.getenv("MAX_COLA", "1000"))
MAX_CONEXIONES = int(os.getenv("MAX_CONEXIONES", "20"))  # por tarea
PROCESOS_CPU = int(os.getenv("PROCESOS_CPU", str(os.cpu_count() or 1)))
ENVEJECIMIENTO_S = float(os.getenv("ENVEJECIMIENTO_S", "5.0"))
BACKOFF_BASE = float(os.getenv("BACKOFF_BASE", "1.0"))
RATE_LIMIT_POR_SEG = float(os.getenv("RATE_LIMIT_POR_SEG", "20"))
RATE_LIMIT_RAFAGA = float(os.getenv("RATE_LIMIT_RAFAGA", "40"))
