"""
threads.py — Analizador de hilos.

Lista los TIDs de cada proceso y junta el estado, nombre, % CPU
(calculado con los ticks) y cambios de contexto.

Clave de snapshot: 'threads'
Intervalo: 2 s
"""

import os
import sys
import time
import multiprocessing

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from procfs import (
    list_pids,
    list_threads,
    parse_thread_stat,
    parse_thread_comm,
    parse_thread_status,
    parse_proc_stat,
    calc_cpu_percent,
    PROC_BASE,
)


def _safe_int(value, default=0):
    """
    Trata de convertir a entero, si falla devuelve un valor por defecto.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class ThreadsAnalyzer(multiprocessing.Process):
    """
    Analizador que recolecta info de cada hilo de los procesos.
    
    Itera por cada PID y sus TIDs, lee el stat, comm y status.
    El % de CPU se saca igual que en los procesos, con los ticks.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)
        
        # guardo ticks previos con la tupla (pid, tid)
        self._prev_ticks = {}
        # ticks del sistema previos
        self._prev_total = 0

    def run(self):
        """Loop que corre y duerme."""
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["threads"] = {"data": data, "ts": time.time()}
            except Exception:
                pass
            self.stop_event.wait(self.interval.value)

    def _get_total_cpu_ticks(self):
        """
        Suma de todos los tiempos de CPU en /proc/stat.
        """
        cpu = parse_proc_stat(self._proc_base).get("cpu", {})
        return sum(cpu.values())

    def _collect(self):
        """
        Recolecta info de PIDs y TIDs.
        """
        pids = list_pids(self._proc_base)
        curr_total = self._get_total_cpu_ticks()
        total_elapsed = curr_total - self._prev_total

        result = {}
        new_ticks = {}

        for pid in pids:
            try:
                # busco los hilos del proceso
                tids = list_threads(pid, self._proc_base)
                if not tids:
                    continue

                thread_list = []
                for tid in tids:
                    try:
                        # leo datos del hilo
                        tstat = parse_thread_stat(pid, tid, self._proc_base)
                        if not tstat:
                            continue

                        name = parse_thread_comm(pid, tid, self._proc_base)
                        tstatus = parse_thread_status(pid, tid, self._proc_base)

                        utime = tstat.get("utime", 0)
                        stime = tstat.get("stime", 0)
                        key = (pid, tid)
                        new_ticks[key] = (utime, stime)

                        # calculo el cpu usado por este thread
                        prev = self._prev_ticks.get(key, (utime, stime))
                        cpu_pct = calc_cpu_percent(
                            prev[0], prev[1], utime, stime, total_elapsed
                        )

                        # context switches
                        vol_ctxt = _safe_int(
                            tstatus.get("voluntary_ctxt_switches", "0")
                        )
                        nonvol_ctxt = _safe_int(
                            tstatus.get("nonvoluntary_ctxt_switches", "0")
                        )

                        # agrego a la lista del proceso
                        thread_list.append({
                            "tid": tid,
                            "name": name,
                            "state": tstat.get("state", "?"),
                            "cpu_pct": round(cpu_pct, 2),
                            "vol_ctxt": vol_ctxt,
                            "nonvol_ctxt": nonvol_ctxt,
                        })
                    except Exception:
                        continue

                # si encontre threads, los pongo en el dict
                if thread_list:
                    result[pid] = thread_list
            except Exception:
                continue

        # actualizo las variables con los datos de ahora
        self._prev_ticks = new_ticks
        self._prev_total = curr_total
        return result
