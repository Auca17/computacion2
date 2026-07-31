"""
resumen.py — Analizador de resumen para todos los procesos.

Obtiene info básica por proceso: PID, PPID, UID/GID, usuario, estado, 
comando, porcentaje de CPU, hilos y RSS. El CPU se saca con los ticks
del sistema comparando iteraciones.

Clave de snapshot: 'resumen'
Intervalo por defecto: 2 s
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
    parse_cmdline,
    parse_proc_stat,
    get_username,
    calc_cpu_percent,
    PROC_BASE,
)


class ResumenAnalyzer(multiprocessing.Process):
    """
    Clase que hereda de Process para armar el resumen por PID.
    
    Corre como daemon. En cada ciclo lee stat, status y cmdline 
    para cada PID visible, calcula el % de CPU y guarda todo en
    el snapshot bajo la clave 'resumen'.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True) # lo hacemos daemon
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)
        
        # TODO: revisar si hace falta limpiar los pids muertos del dict
        # guardo los ticks anteriores por PID aca: {pid: (utime, stime)}
        self._prev_ticks = {}
        # ticks totales anteriores del sistema
        self._prev_total = 0

    def run(self):
        """Loop principal: recolecta, guarda y duerme hasta que nos paren."""
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                # guardo la data con su timestamp
                self.snapshot["resumen"] = {"data": data, "ts": time.time()}
            except Exception:
                pass # si falla sigo de largo nomas
            # espero el intervalo definido
            self.stop_event.wait(self.interval.value)

    def _get_total_cpu_ticks(self):
        """
        Suma todos los tiempos de CPU en /proc/stat para sacar
        los ticks totales desde que arranco el sistema.
        """
        # traigo los stats de proc y devuelvo la suma de todo
        cpu = parse_proc_stat(self._proc_base).get("cpu", {})
        return sum(cpu.values())

    def _collect(self):
        """
        Da una vuelta por todos los PIDs visibles y junta la info.
        Retorna un diccionario que va al snapshot.
        """
        pids = list_pids(self._proc_base)
        curr_total = self._get_total_cpu_ticks()
        total_elapsed = curr_total - self._prev_total

        result = {}
        new_ticks = {}

        for pid in pids:
            try:
                stat = parse_stat(pid, self._proc_base)
                if not stat:
                    continue

                status = parse_status(pid, self._proc_base)
                # si no hay cmdline uso el de stat
                cmd = parse_cmdline(pid, self._proc_base) or stat.get("comm", "")

                # saco uid y gid del status (es el primer valor nomas)
                uid = int(status.get("Uid", "0").split()[0])
                gid = int(status.get("Gid", "0").split()[0])
                user = get_username(uid)

                # mem RSS (en kB)
                rss_raw = status.get("VmRSS", "0 kB")
                rss_kb = int(rss_raw.split()[0]) if rss_raw else 0

                # saco los ticks del proceso
                utime = stat.get("utime", 0)
                stime = stat.get("stime", 0)
                new_ticks[pid] = (utime, stime)

                # saco el CPU% comparando con la iteracion anterior
                prev = self._prev_ticks.get(pid, (utime, stime))
                cpu_pct = calc_cpu_percent(
                    prev[0], prev[1], utime, stime, total_elapsed
                )

                # armo el dict final para este pid
                result[pid] = {
                    "pid": pid,
                    "ppid": stat.get("ppid", 0),
                    "uid": uid,
                    "gid": gid,
                    "user": user,
                    "state": stat.get("state", "?"),
                    "cmd": cmd,
                    "cpu_pct": round(cpu_pct, 2),
                    "threads": stat.get("num_threads", 0),
                    "rss_kb": rss_kb,
                }
            except Exception:
                # si explota un pid, sigo con el que viene
                continue

        # me guardo los valores para la proxima vuelta
        self._prev_ticks = new_ticks
        self._prev_total = curr_total
        return result
