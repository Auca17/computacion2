"""
recolector.py - Consigue la lista de procesos activos.

Los otros módulos lo llaman para saber qué PIDs hay que analizar.
Es solo una función re simple.
"""

import os
import sys

# agrego la carpeta actual al path para poder importar procfs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from procfs import list_pids, PROC_BASE


def get_pids(proc_base=None):
    # Trae los PIDs que están corriendo ahora.
    # Llama directo a la función de procfs.
    
    # TODO: capaz esto es medio redundante si ya lo hace list_pids?
    base = proc_base or os.environ.get("PROC_BASE", PROC_BASE)
    return list_pids(base)
