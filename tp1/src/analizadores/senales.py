"""
senales.py — Analizador de mascaras de señales para procesos.

Lee las mascaras en hexadecimal de /proc/<pid>/status y las convierte 
a una lista de nombres de señales POSIX con decode_signal_mask().

Clave de snapshot: 'senales'
Intervalo: 10 s
"""

import os
import time
import multiprocessing
from procfs import (
    list_pids,
    parse_status,
    decode_signal_mask,
    PROC_BASE,
)
from senales import ignorar_senales_en_hijo


class SenalesAnalyzer(multiprocessing.Process):
    """
    Analizador que decodifica las señales.
    
    Lee 5 campos de /proc/<pid>/status para sacar las bloqueadas,
    ignoradas, etc y pasa los hex a nombres faciles de leer.
    """

    def __init__(self, snapshot, interval_value, stop_event):
        super().__init__(daemon=True)
        self.snapshot = snapshot
        self.interval = interval_value
        self.stop_event = stop_event
        self._proc_base = os.environ.get("PROC_BASE", PROC_BASE)

    def run(self):
        """Loop que recolecta y guarda la data."""
        ignorar_senales_en_hijo()  # solo el proceso principal maneja las señales
        while not self.stop_event.is_set():
            try:
                data = self._collect()
                self.snapshot["senales"] = {"data": data, "ts": time.time()}
            except Exception:
                pass
            self.stop_event.wait(self.interval.value)

    def _collect(self):
        """
        Recolecta info de los PIDs.
        """
        pids = list_pids(self._proc_base)
        result = {}

        for pid in pids:
            try:
                # leo el status
                status = parse_status(pid, self._proc_base)
                if not status:
                    continue

                # decodifico cada mascara que encuentro
                result[pid] = {
                    "blocked": decode_signal_mask(status.get("SigBlk", "0")),
                    "ignored": decode_signal_mask(status.get("SigIgn", "0")),
                    "caught": decode_signal_mask(status.get("SigCgt", "0")),
                    "pending": decode_signal_mask(status.get("SigPnd", "0")),
                    "shared_pending": decode_signal_mask(
                        status.get("ShdPnd", "0")
                    ),
                }
            except Exception:
                continue

        return result
