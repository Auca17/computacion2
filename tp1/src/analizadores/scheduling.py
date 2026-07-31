"""
scheduling.py — Analizador de scheduler de procesos.

Junta datos de scheduling: nice, prioridad, politica, afinidad del cpu, 
cambios de contexto, tiempo, session id y pgid.

Clave de snapshot: 'scheduling'
Intervalo: 10 s
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
    get_scheduling_policy_name,
    PROC_BASE,
)


def _safe_int(value, default=0):
    """
    Intenta convertir a int sin que rompa.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class SchedulingAnalyzer(multiprocessing.Process):
    """
    Analizador que recolecta info del scheduler para todos los procesos.
    
    Busca info en stat (nice, prioridad, etc) y status (afinidad, contexto).
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)

    def run(self):
        """Corre el loop principal hasta que le avisan que corte."""
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["scheduling"] = {"data": data, "ts": time.time()}
            except Exception:
                pass
            self.stop_event.wait(self.interval.value)

    def _collect(self):
        """
        Busca la data para todos los PIDs visibles.
        """
        pids = list_pids(self._proc_base)
        result = {}

        for pid in pids:
            try:
                # levanto stat y status
                stat = parse_stat(pid, self._proc_base)
                if not stat:
                    continue

                status = parse_status(pid, self._proc_base)

                policy_num = stat.get("policy", 0)

                # cambios de contexto
                vol_ctxt = _safe_int(
                    status.get("voluntary_ctxt_switches", "0")
                )
                nonvol_ctxt = _safe_int(
                    status.get("nonvoluntary_ctxt_switches", "0")
                )

                # guardo todo
                result[pid] = {
                    "nice": stat.get("nice", 0),
                    "priority": stat.get("priority", 0),
                    "policy": get_scheduling_policy_name(policy_num),
                    "rt_priority": stat.get("rt_priority", 0),
                    "cpu_affinity": status.get("Cpus_allowed_list", "N/A"), # en que cpus corre
                    "vol_ctxt": vol_ctxt,
                    "nonvol_ctxt": nonvol_ctxt,
                    "utime": stat.get("utime", 0),
                    "stime": stat.get("stime", 0),
                    "sid": stat.get("session", 0),
                    "pgid": stat.get("pgrp", 0),
                }
            except Exception:
                # TODO: si el proceso murio, va a caer aca
                continue

        return result
