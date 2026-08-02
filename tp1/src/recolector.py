"""
recolector.py - Obtiene la lista de procesos activos.

Tener esto en un módulo separado hace que sea fácil de probar (podemos
pasarle un PROC_BASE diferente) y de extender si en algún momento
queremos filtrar procesos antes de mandarlos a los analizadores.
"""

import os

from procfs import list_pids, PROC_BASE


def get_pids(proc_base=None):
    """Devuelve la lista de PIDs corriendo en este momento."""
    base = proc_base or os.environ.get("PROC_BASE", PROC_BASE)
    return list_pids(base)
