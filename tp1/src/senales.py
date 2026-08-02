"""
senales.py
Módulo para atrapar las señales del sistema operativo que le llegan al monitor.
No confundir con el analizador de señales de los otros procesos.
"""

import json
import os
import signal
import time


# Señales que los procesos hijos deben ignorar.
# SIGTERM NO está en la lista a propósito: es como Process.terminate() del padre
# le pide al hijo que se cierre. Si lo ignoramos, los hijos quedan vivos para siempre
# después del shutdown (bug real si no lo tenés en cuenta).
_SENALES_A_IGNORAR_EN_HIJO = (
    signal.SIGINT,
    signal.SIGHUP,
    signal.SIGUSR1,
    signal.SIGUSR2,
)


def ignorar_senales_en_hijo():
    """
    Los analizadores y el recolector llaman esto al inicio de su run().
    La decisión de qué hacer con cada señal del monitor la toma SOLO el
    proceso principal — los hijos se desentieden de todo eso.
    """
    for sig in _SENALES_A_IGNORAR_EN_HIJO:
        signal.signal(sig, signal.SIG_IGN)


class SignalHandler:
    """
    Manejador de señales usando el patrón "self-pipe".
    Esto del self-pipe lo usamos para que el handler de la señal sea súper cortito y
    no tengamos problemas de re-entrada. Solo escribimos un byte en un pipe y después
    el hilo principal lo lee tranquilo.
    """

    def __init__(self, stop_event, snapshot, intervals, verbose_flag,
                 config_path="config.json", display=None):
        """
        Inicializa el handler guardando las referencias a la memoria compartida
        y creando los file descriptors del pipe.
        """
        self._stop_event = stop_event
        self._snapshot = snapshot
        self._intervals = intervals
        self._verbose = verbose_flag
        self._config_path = config_path
        self._display = display

        # Creo el self-pipe (los dos extremos son no bloqueantes)
        self._pipe_r, self._pipe_w = os.pipe()
        os.set_blocking(self._pipe_r, False)
        os.set_blocking(self._pipe_w, False)

        # Acá vamos a ir guardando las señales que van llegando
        self._received_signals = []

    # --- Setup ---

    def setup(self):
        """
        Registra los callbacks de las señales y engancha el wakeup fd.
        Tiene que llamarse desde el hilo principal antes del loop de la UI.
        """
        signal.set_wakeup_fd(self._pipe_w)
        for sig in (signal.SIGINT, signal.SIGTERM,
                    signal.SIGHUP, signal.SIGUSR1, signal.SIGUSR2):
            signal.signal(sig, self._handler)

    # --- Callbacks ---

    def _handler(self, signum, frame):
        """
        El handler real de la señal. Súper simple, solo anota qué señal llegó.
        El set_wakeup_fd se encarga de escribir en el pipe por atrás.
        """
        self._received_signals.append(signum)

    # --- Procesamiento desde el hilo principal ---

    def process_pending(self):
        """
        Lee el pipe y procesa de verdad las señales que fueron cayendo.
        Se tiene que llamar de a ratos en el loop principal.
        """
        # Vacío el pipe para que el select/poll no se vuelva loco
        self._drain_pipe()

        # Copio la lista de señales y la vacío
        signals = list(self._received_signals)
        self._received_signals.clear()

        # TODO: Revisar si importa el orden en que proceso las señales
        for sig in signals:
            if sig in (signal.SIGINT, signal.SIGTERM):
                self._handle_shutdown()
            elif sig == signal.SIGHUP:
                self._reload_config()
            elif sig == signal.SIGUSR1:
                self._dump_snapshot()
            elif sig == signal.SIGUSR2:
                self._toggle_verbose()

    # --- Acciones por cada señal ---

    def _handle_shutdown(self):
        """Para cerrar todo de manera prolija (SIGINT / SIGTERM)."""
        self._stop_event.set()

    def _reload_config(self):
        """
        Recarga la config.json (SIGHUP) y actualiza los tiempos y filtros.
        Si hay un error al leer el archivo, no hace nada y sigue de largo.
        """
        config = None
        candidates = [
            self._config_path,
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                self._config_path,
            ),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        config = json.load(f)
                    break
                except (json.JSONDecodeError, OSError):
                    continue

        if config is None:
            return

        # Actualizo los intervalos de a uno
        new_intervals = config.get("intervalos", {})
        for key, value in new_intervals.items():
            if key in self._intervals:
                try:
                    self._intervals[key].value = float(value)
                except (TypeError, ValueError):
                    pass

        # Le aviso al display de los filtros nuevos si está seteado
        if self._display:
            filtros = config.get("filtros", {})
            self._display.set_filters(
                filtros.get("comando"),
                filtros.get("usuario")
            )

    def _dump_snapshot(self):
        """
        Vuelca el estado actual en un archivo JSON (SIGUSR1).
        El nombre del archivo tiene la fecha y hora para no pisarlos.
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"dump_{ts}.json"

        try:
            # Paso el dict de Manager a un dict normal para poder guardarlo
            plain = {}
            for key in list(self._snapshot.keys()):
                try:
                    plain[key] = self._snapshot[key]
                except (KeyError, TypeError):
                    pass

            with open(filename, "w") as f:
                json.dump(plain, f, indent=2, default=str)
        except (OSError, TypeError):
            pass

    def _toggle_verbose(self):
        """Cambia el modo verbose prendido/apagado (SIGUSR2)."""
        self._verbose.value = not self._verbose.value

    # --- Helpers ---

    def _drain_pipe(self):
        """
        Saca todos los bytes que hayan quedado trabados en el pipe.
        Esto lo llamamos adentro de process_pending.
        """
        try:
            while True:
                os.read(self._pipe_r, 4096)
        except (BlockingIOError, OSError):
            pass

    @property
    def pipe_r(self):
        """
        Devuelve el file descriptor de lectura del pipe.
        Sirve por si el loop principal usa select().
        """
        return self._pipe_r

    def cleanup(self):
        """
        Cierra los file descriptors del pipe.
        Hay que llamarlo al final para no dejar fds colgados.
        """
        for fd in (self._pipe_r, self._pipe_w):
            try:
                os.close(fd)
            except OSError:
                pass
