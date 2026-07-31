"""
memoria.py — Analizador de memoria para todos los procesos.

Junta los detalles de memoria por proceso: tamaños de /proc/<pid>/status,
tamaños de segmentos de /proc/<pid>/maps, y fallos de pagina de stat.

Clave de snapshot: 'memoria'
Intervalo por defecto: 3 s
"""

import os
import sys
import time
import multiprocessing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from procfs import (
    list_pids,
    parse_stat,
    parse_status,
    parse_maps,
    get_memory_fields,
    PROC_BASE,
)


class MemoriaAnalyzer(multiprocessing.Process):
    """
    Analizador de detalles de memoria por proceso.
    
    Por cada PID saca memoria virtual (size, rss, swap, etc) del status,
    los segmentos del maps, y los page-faults del stat.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)

    def run(self):
        """Loop del proceso, junta los datos y los pone en la memoria compartida."""
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["memoria"] = {"data": data, "ts": time.time()}
            except Exception:
                # si pasa algo raro lo ignoro
                pass
            self.stop_event.wait(self.interval.value)

    def _collect(self):
        """
        Recorre todos los procesos y arma el diccionario de memoria.
        """
        pids = list_pids(self._proc_base)
        result = {}

        for pid in pids:
            try:
                # pido el status del proceso
                status = parse_status(pid, self._proc_base)
                if not status:
                    continue

                mem = get_memory_fields(status)
                # aca saco los segmentos
                segments = parse_maps(pid, self._proc_base)
                # y aca el stat para los page faults
                stat = parse_stat(pid, self._proc_base)

                # TODO: capaz esto ocupa mucha memoria si hay muchos procesos?
                result[pid] = {
                    "vm_size": mem.get("vm_size", 0),
                    "vm_rss": mem.get("vm_rss", 0),
                    "vm_data": mem.get("vm_data", 0),
                    "vm_stk": mem.get("vm_stk", 0),
                    "vm_exe": mem.get("vm_exe", 0),
                    "vm_lib": mem.get("vm_lib", 0),
                    "vm_hwm": mem.get("vm_hwm", 0),
                    "vm_swap": mem.get("vm_swap", 0),
                    "minflt": stat.get("minflt", 0),  # page faults menores
                    "majflt": stat.get("majflt", 0),  # mayores
                    "cminflt": stat.get("cminflt", 0),
                    "cmajflt": stat.get("cmajflt", 0),
                    "segments": {
                        "text": segments.get("text", 0),
                        "data": segments.get("data", 0),
                        "heap": segments.get("heap", 0),
                        "stack": segments.get("stack", 0),
                        "shared": segments.get("shared", 0),
                        "other": segments.get("other", 0),
                    },
                }
            except Exception:
                continue

        return result
