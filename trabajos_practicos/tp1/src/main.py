"""
main.py
Punto de entrada para el monitor de procesos. Levanta la config, crea la memoria compartida
y arranca todos los procesos analizadores junto con la interfaz.
"""

import os
import sys
import json
import multiprocessing
import curses

# Agrego src/ al path para que funcionen los imports relativos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_config(path="config.json"):
    """
    Carga el archivo de configuración en formato JSON.
    Busca en el directorio actual o en la carpeta padre.
    Si no encuentra nada, tira valores por defecto.
    """
    candidates = [
        path,
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            path,
        ),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

    # TODO: Podríamos mostrar un warning si no carga el archivo, pero por ahora uso defaults
    return {
        "intervalos": {
            "resumen": 2.0,
            "memoria": 3.0,
            "fds": 5.0,
            "threads": 2.0,
            "senales": 10.0,
            "scheduling": 10.0,
            "sistema": 2.0,
        },
        "filtros": {"usuario": None, "comando": None},
        "verbose": False,
    }


def main():
    """
    Función principal. Orquesta todo: memoria compartida, procesos, señales y la UI en curses.
    """
    config = load_config()

    # --- Recursos compartidos ---
    manager = multiprocessing.Manager()
    snapshot = manager.dict() # Acá van a guardar los datos los analizadores
    stop_event = multiprocessing.Event()

    # Un Value('d') para cada analizador así le paso el intervalo
    intervals = {}
    for key, default_val in config["intervalos"].items():
        intervals[key] = multiprocessing.Value("d", float(default_val))

    verbose_flag = multiprocessing.Value("b", config.get("verbose", False))

    # --- Importo los analizadores después de acomodar sys.path ---
    from analizadores.resumen import ResumenAnalyzer
    from analizadores.memoria import MemoriaAnalyzer
    from analizadores.fds import FDsAnalyzer
    from analizadores.threads import ThreadsAnalyzer
    from analizadores.senales import SenalesAnalyzer
    from analizadores.scheduling import SchedulingAnalyzer
    from analizadores.sistema import SistemaAnalyzer
    from senales import SignalHandler
    from display import Display

    # --- Creación de los procesos analizadores ---
    analyzers = [
        ResumenAnalyzer(snapshot, intervals["resumen"], stop_event),
        MemoriaAnalyzer(snapshot, intervals["memoria"], stop_event),
        FDsAnalyzer(snapshot, intervals["fds"], stop_event),
        ThreadsAnalyzer(snapshot, intervals["threads"], stop_event),
        SenalesAnalyzer(snapshot, intervals["senales"], stop_event),
        SchedulingAnalyzer(snapshot, intervals["scheduling"], stop_event),
        SistemaAnalyzer(snapshot, intervals["sistema"], stop_event),
    ]

    # Arranco todos los procesos como daemon para que mueran si el main se muere
    for analyzer in analyzers:
        analyzer.daemon = True
        analyzer.start()

    # --- Interfaz gráfica ---
    display = Display(snapshot, intervals, stop_event, verbose_flag)

    # --- Manejo de señales ---
    sig_handler = SignalHandler(
        stop_event, snapshot, intervals, verbose_flag, display=display
    )
    sig_handler.setup()

    # Le paso el manejador de señales al display para que lo lea en su loop
    display._sig_handler = sig_handler

    try:
        curses.wrapper(display.run)
    except KeyboardInterrupt:
        # TODO: Quizás atrapar esto no haga falta por las señales, pero por las dudas
        pass
    finally:
        # --- Limpieza al salir ---
        stop_event.set()

        for analyzer in analyzers:
            analyzer.join(timeout=3)
            if analyzer.is_alive():
                analyzer.terminate()

        sig_handler.cleanup()

        try:
            manager.shutdown()
        except (OSError, EOFError):
            pass


if __name__ == "__main__":
    main()
