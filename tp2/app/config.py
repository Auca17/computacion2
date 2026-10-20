"""Configuración de la plataforma, leída de variables de entorno."""

import os

WORKERS = int(os.getenv("WORKERS", "4"))
TIMEOUT_DEFECTO = float(os.getenv("TIMEOUT_DEFECTO", "30"))
GRACIA_APAGADO = float(os.getenv("GRACIA_APAGADO", "10"))
MODO_CPU = os.getenv("MODO_CPU", "executor")  # "executor" o "bloqueante"
DIR_VOLCADOS = os.getenv("DIR_VOLCADOS", "./datos")
MAX_COLA = int(os.getenv("MAX_COLA", "1000"))
