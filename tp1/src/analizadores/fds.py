"""
fds.py — Analizador de file descriptors para los procesos.

Saca la lista de file descriptors abiertos leyendo /proc/<pid>/fd/.
Tiene el numero, a donde apunta y el tipo (archivo, socket, etc).

Clave de snapshot: 'fds'
Intervalo: 5 s
"""

import os
import sys
import time
import multiprocessing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from procfs import (
    list_pids,
    list_fds,
    PROC_BASE,
)


class FDsAnalyzer(multiprocessing.Process):
    """
    Analizador que lista los fd de todos los procesos visibles.
    Lee los symlinks adentro de /proc/<pid>/fd/ y se fija de que tipo son.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True) # proceso demonio
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)

    def run(self):
        """Corre hasta que salte el evento de stop."""
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["fds"] = {"data": data, "ts": time.time()}
            except Exception:
                pass
            # duerme hasta la prox
            self.stop_event.wait(self.interval.value)

    def _collect(self):
        """
        Hace un ciclo sobre todos los PIDs visibles.
        """
        pids = list_pids(self._proc_base)
        result = {}

        for pid in pids:
            try:
                # TODO: usar try-except adentro por si justo se cierra un FD
                fds = list_fds(pid, self._proc_base)
                result[pid] = fds
            except Exception:
                continue

        return result
