"""
sistema.py — Analizador de estadisticas del sistema en general.

Junta metricas globales: uso de cpu, load avg, memoria, conteo de procesos, 
tiempo levantado, y el top 3 de los procesos que mas gastan cpu y memoria.

Clave de snapshot: 'sistema'
Intervalo: 2 s
"""

import os
import time
import multiprocessing
from procfs import (
    list_pids,
    parse_stat,
    parse_cmdline,
    parse_status,
    parse_proc_stat,
    parse_loadavg,
    parse_meminfo,
    parse_uptime,
    PROC_BASE,
)
from senales import ignorar_senales_en_hijo

# Diccionario para mapear las letras de estado a algo mas entendible
_STATE_MAP = {
    "R": "running",
    "S": "sleeping",
    "D": "sleeping",   # uninterruptible sleep, lo cuento como sleeping
    "T": "stopped",
    "t": "stopped",
    "Z": "zombie",
    "X": "zombie",     # muerto, por las dudas
}


class SistemaAnalyzer(multiprocessing.Process):
    """
    Analizador de los stats del sistema.
    
    Calcula de todo: los porcentajes de CPU global, memoria libre/usada, load,
    y cuenta cuantos procesos hay en cada estado. Ademas saca el top 3.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)
        
        # Guardo el proc stat anterior para sacar la diferencia de ticks
        self._prev_cpu = {}

    def run(self):
        """Loop infinito del analizador."""
        ignorar_senales_en_hijo()  # solo el proceso principal maneja las señales
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["sistema"] = {"data": data, "ts": time.time()}
            except Exception:
                pass
            self.stop_event.wait(self.interval.value)

    def _compute_cpu_pcts(self, cpu_now):
        """
        Saca el porcentaje de usuario, sistema, idle, y iowait usando los ticks.
        """
        # devuelvo esto por defecto o si es la primera vez
        result = {
            "user_pct": 0.0,
            "system_pct": 0.0,
            "idle_pct": 0.0,
            "iowait_pct": 0.0,
        }

        if not self._prev_cpu:
            return result

        deltas = {}
        total_delta = 0
        for key in cpu_now:
            # resto el valor actual menos el viejo
            d = cpu_now.get(key, 0) - self._prev_cpu.get(key, 0)
            deltas[key] = max(d, 0)
            total_delta += deltas[key]

        if total_delta <= 0:
            return result

        user_d = deltas.get("user", 0) + deltas.get("nice", 0)
        sys_d = (
            deltas.get("system", 0)
            + deltas.get("irq", 0)
            + deltas.get("softirq", 0)
        )
        idle_d = deltas.get("idle", 0) + deltas.get("steal", 0)
        iowait_d = deltas.get("iowait", 0)

        # calculo los porcentajes sobre 100
        result["user_pct"] = round((user_d / total_delta) * 100.0, 2)
        result["system_pct"] = round((sys_d / total_delta) * 100.0, 2)
        result["idle_pct"] = round((idle_d / total_delta) * 100.0, 2)
        result["iowait_pct"] = round((iowait_d / total_delta) * 100.0, 2)

        return result

    def _collect(self):
        """
        Junta toda la info global.
        """
        # ---- stats de CPU ----
        proc_stat = parse_proc_stat(self._proc_base)
        cpu_now = proc_stat.get("cpu", {})
        cpu_pcts = self._compute_cpu_pcts(cpu_now)
        self._prev_cpu = cpu_now

        # ---- Load average ----
        loadavg = parse_loadavg(self._proc_base)

        # ---- Memoria info ----
        meminfo = parse_meminfo(self._proc_base)

        # ---- Uptime ----
        uptime_data = parse_uptime(self._proc_base)

        # ---- Buscar PIDs para contar estados y hacer rankings ----
        pids = list_pids(self._proc_base)
        state_counts = {"running": 0, "sleeping": 0, "stopped": 0, "zombie": 0}
        total_threads = 0

        # Para los tops que armo aca
        cpu_ranking = []  # formato: (pid, cmd, utime+stime)
        mem_ranking = []  # formato: (pid, cmd, rss_kb)

        for pid in pids:
            try:
                stat = parse_stat(pid, self._proc_base)
                if not stat:
                    continue

                # me fijo el estado y lo cuento
                state_char = stat.get("state", "?")
                bucket = _STATE_MAP.get(state_char, "sleeping")
                state_counts[bucket] += 1

                total_threads += stat.get("num_threads", 0)

                cmd = parse_cmdline(pid, self._proc_base) or stat.get("comm", "")

                cpu_ranking.append(
                    (pid, cmd, stat.get("utime", 0) + stat.get("stime", 0))
                )

                # TODO: mejorar como leo rss
                status = parse_status(pid, self._proc_base)
                rss_raw = status.get("VmRSS", "0 kB")
                rss_kb = int(rss_raw.split()[0]) if rss_raw else 0
                mem_ranking.append((pid, cmd, rss_kb))
            except Exception:
                continue

        total_procs = sum(state_counts.values())

        # ---- Top 3 CPU ----
        top_cpu = []
        try:
            # me trato de robar los calculos del resumen que son mejores
            resumen_entry = self.snapshot.get("resumen")
            if resumen_entry:
                resumen_data = resumen_entry.get("data", {})
                sorted_cpu = sorted(
                    resumen_data.values(),
                    key=lambda p: p.get("cpu_pct", 0.0),
                    reverse=True,
                )[:3] # me quedo con los 3 primeros
                
                top_cpu = [
                    {
                        "pid": p["pid"],
                        "cmd": p.get("cmd", ""),
                        "cpu_pct": p.get("cpu_pct", 0.0),
                    }
                    for p in sorted_cpu
                ]
        except Exception:
            pass

        if not top_cpu:
            # si falla armo el top con los ticks q junte recien
            cpu_ranking.sort(key=lambda x: x[2], reverse=True)
            top_cpu = [
                {"pid": r[0], "cmd": r[1], "cpu_pct": 0.0}
                for r in cpu_ranking[:3]
            ]

        # ---- Top 3 Memoria ----
        mem_ranking.sort(key=lambda x: x[2], reverse=True)
        top_mem = [
            {"pid": r[0], "cmd": r[1], "rss_kb": r[2]}
            for r in mem_ranking[:3]
        ]

        # devuelvo el choclo de datos
        return {
            "cpu": cpu_pcts,
            "load": {
                "load1": loadavg.get("load1", 0.0),
                "load5": loadavg.get("load5", 0.0),
                "load15": loadavg.get("load15", 0.0),
            },
            "memory": {
                "total": meminfo.get("MemTotal", 0),
                "free": meminfo.get("MemFree", 0),
                "buffers": meminfo.get("Buffers", 0),
                "cached": meminfo.get("Cached", 0),
                "swap_total": meminfo.get("SwapTotal", 0),
                "swap_free": meminfo.get("SwapFree", 0),
            },
            "processes": {
                "total": total_procs,
                "running": state_counts["running"],
                "sleeping": state_counts["sleeping"],
                "stopped": state_counts["stopped"],
                "zombie": state_counts["zombie"],
                "threads_total": total_threads,
            },
            "uptime": uptime_data.get("uptime", 0.0),
            "boot_time": proc_stat.get("btime", 0),
            "top_cpu": top_cpu,
            "top_mem": top_mem,
        }
