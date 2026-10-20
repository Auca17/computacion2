"""Cola de tareas y pool de workers (corrutinas)."""

import asyncio
import logging
import random
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from . import config
from .eventos import publicar
from .estado import Tarea, registro
from .tareas import EJECUTORES

log = logging.getLogger("plataforma")


class ColaConPrioridad(asyncio.Queue):
    """Cola acotada que entrega primero la tarea de menor prioridad efectiva.

    Hereda de `asyncio.Queue` y solo redefine los hooks `_init/_put/_get`,
    igual que `asyncio.PriorityQueue`: `maxsize`, `put_nowait` (QueueFull),
    `get`, `task_done` y `join` funcionan sin cambios.

    Anti-inanición (envejecimiento): la prioridad efectiva es
    `prioridad - espera / ENVEJECIMIENTO_S`. Cuanto más espera una tarea,
    más baja su valor, así que una de baja prioridad que lleva suficiente
    tiempo en la cola termina ganándole a las tareas nuevas de alta
    prioridad y nunca queda postergada para siempre. A igual valor gana la
    que entró antes (FIFO).
    """

    def _init(self, maxsize: int) -> None:
        self._queue = []

    def _put(self, tarea: Tarea) -> None:
        tarea.encolada = time.time()  # la espera se mide desde acá
        self._queue.append(tarea)

    def _get(self) -> Tarea:
        # Búsqueda lineal: n <= MAX_COLA y se calcula con el instante actual.
        ahora = time.time()
        indice = min(
            range(len(self._queue)),
            key=lambda i: (
                self._queue[i].prioridad
                - (ahora - self._queue[i].encolada) / config.ENVEJECIMIENTO_S,
                self._queue[i].encolada,
            ),
        )
        return self._queue.pop(indice)


class Plataforma:
    """Cola acotada, workers y executor para tareas CPU-bound."""

    def __init__(self) -> None:
        self.cola: Optional[ColaConPrioridad] = None
        self.workers: list[asyncio.Task] = []
        self.executor: Optional[ProcessPoolExecutor] = None
        self.ocupados = 0
        self.aceptando = True
        # Ejecución de cada tarea en curso como asyncio.Task propio: id -> Task
        self.en_ejecucion: dict[str, asyncio.Task] = {}
        # Temporizadores de backoff de tareas por reintentar: id -> Task
        self.temporizadores: dict[str, asyncio.Task] = {}
        self.reintentos_programados = 0
        self.rechazadas_por_limite = 0

    def iniciar(self) -> None:
        """Crea la cola, el executor y las corrutinas worker."""
        self.cola = ColaConPrioridad(maxsize=config.MAX_COLA)
        self.executor = ProcessPoolExecutor(max_workers=config.PROCESOS_CPU)
        self.workers = [
            asyncio.create_task(self._worker()) for _ in range(config.WORKERS)
        ]

    async def detener(self) -> None:
        """Detiene los workers y cierra el executor."""
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
        if self.executor is not None:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.executor = None

    def encolar(self, tarea: Tarea) -> None:
        """Encola y registra; lanza asyncio.QueueFull si la cola está llena."""
        self.cola.put_nowait(tarea)
        registro[tarea.id] = tarea

    async def _worker(self) -> None:
        """Consume tareas de la cola; una excepción en una tarea no lo mata."""
        while True:
            tarea = await self.cola.get()
            try:
                if tarea.estado == "cancelada":
                    continue  # cancelada mientras esperaba en la cola
                self.ocupados += 1
                try:
                    await self._correr(tarea)
                finally:
                    self.ocupados -= 1
            finally:
                self.cola.task_done()

    async def _correr(self, tarea: Tarea) -> None:
        """Ejecuta la tarea en su propio asyncio.Task y espera a que termine.

        Cancelar ese Task (DELETE) no afecta al worker. `asyncio.wait` no
        propaga la cancelación del Task interno; si lo cancelan al worker
        (apagado), se cancela también la tarea interna y se re-lanza.
        """
        tarea.estado = "ejecutando"
        tarea.iniciada = time.time()
        publicar(tarea)
        interna = asyncio.create_task(self._ejecutar(tarea))
        self.en_ejecucion[tarea.id] = interna
        try:
            await asyncio.wait({interna})
        except asyncio.CancelledError:
            interna.cancel()
            await asyncio.wait({interna})
            raise
        finally:
            self.en_ejecucion.pop(tarea.id, None)

    async def _ejecutar(self, tarea: Tarea) -> None:
        """Ejecuta una tarea y registra su resultado o su motivo de fallo."""
        tarea.intentos += 1
        try:
            async with asyncio.timeout(tarea.timeout):
                tarea.resultado = await EJECUTORES[tarea.tipo](
                    tarea.parametros, self.executor
                )
            tarea.estado = "completada"
        except TimeoutError:
            self._fallar(tarea, f"timeout: superó {tarea.timeout} segundos")
        except asyncio.CancelledError:
            tarea.estado = "cancelada"
            raise  # la cancelación nunca se traga
        except Exception as exc:
            log.exception("La tarea %s falló", tarea.id)
            self._fallar(tarea, f"{type(exc).__name__}: {exc}")
        finally:
            if tarea.estado != "pendiente":  # pendiente = espera un reintento
                tarea.finalizada = time.time()
            publicar(tarea)

    def _fallar(self, tarea: Tarea, motivo: str) -> None:
        """Registra el fallo; si quedan reintentos, programa el reencolado.

        La espera del backoff la hace un temporizador aparte: el worker queda
        libre de inmediato. El cambio de estado lo publica quien llama.
        """
        tarea.errores.append(motivo)
        if tarea.intentos > tarea.reintentos:
            tarea.estado = "fallida"
            tarea.error = motivo
            return
        demora = (config.BACKOFF_BASE * 2 ** (tarea.intentos - 1)
                  * random.uniform(0.8, 1.2))
        tarea.estado = "pendiente"
        tarea.proximo_intento = time.time() + demora
        self.reintentos_programados += 1
        self.temporizadores[tarea.id] = asyncio.create_task(
            self._reencolar_tras(tarea, demora))

    async def _reencolar_tras(self, tarea: Tarea, demora: float) -> None:
        """Espera el backoff y vuelve a encolar la tarea."""
        await asyncio.sleep(demora)
        self.temporizadores.pop(tarea.id, None)
        tarea.proximo_intento = None
        try:
            self.cola.put_nowait(tarea)
        except asyncio.QueueFull:
            tarea.estado = "fallida"
            tarea.error = f"{tarea.errores[-1]} (cola llena al reintentar)"
            tarea.finalizada = time.time()
            publicar(tarea)

    async def cancelar(self, tarea: Tarea) -> None:
        """Cancela una tarea pendiente o en ejecución (estado no final)."""
        if tarea.estado == "pendiente":
            # El worker la descarta al sacarla de la cola; si espera un
            # reintento, se cancela su temporizador.
            temporizador = self.temporizadores.pop(tarea.id, None)
            if temporizador is not None:
                temporizador.cancel()
            tarea.proximo_intento = None
            tarea.estado = "cancelada"
            tarea.finalizada = time.time()
            publicar(tarea)
        elif tarea.estado == "ejecutando":
            interna = self.en_ejecucion.get(tarea.id)
            if interna is not None:
                interna.cancel()
                await asyncio.wait({interna})
            if tarea.estado == "ejecutando":
                # Cancelada antes de arrancar: su manejador no llegó a correr.
                tarea.estado = "cancelada"
                tarea.finalizada = time.time()
                publicar(tarea)

    async def apagar(self, gracia: float) -> None:
        """Deja de aceptar, espera hasta `gracia` s, cancela el resto y cierra."""
        self.aceptando = False
        try:
            await asyncio.wait_for(self.cola.join(), gracia)
        except TimeoutError:
            log.warning("Fin de la gracia (%ss): se cancelan las tareas restantes",
                        gracia)
        for tarea in list(registro.values()):
            if tarea.estado in ("pendiente", "ejecutando"):
                await self.cancelar(tarea)
        await self.detener()


plataforma = Plataforma()
