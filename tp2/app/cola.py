"""Cola de tareas y pool de workers (corrutinas)."""

import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from . import config
from .estado import Tarea, registro
from .tareas import EJECUTORES

log = logging.getLogger("plataforma")


class Plataforma:
    """Cola acotada, workers y executor para tareas CPU-bound."""

    def __init__(self) -> None:
        self.cola: Optional[asyncio.Queue] = None
        self.workers: list[asyncio.Task] = []
        self.executor: Optional[ProcessPoolExecutor] = None
        self.ocupados = 0
        self.aceptando = True

    def iniciar(self) -> None:
        """Crea la cola, el executor y las corrutinas worker."""
        self.cola = asyncio.Queue(maxsize=config.MAX_COLA)
        self.executor = ProcessPoolExecutor()
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
            self.ocupados += 1
            try:
                await self._ejecutar(tarea)
            finally:
                self.ocupados -= 1
                self.cola.task_done()

    async def _ejecutar(self, tarea: Tarea) -> None:
        """Ejecuta una tarea y registra su resultado o su motivo de fallo."""
        tarea.estado = "ejecutando"
        tarea.iniciada = time.time()
        try:
            async with asyncio.timeout(tarea.timeout):
                tarea.resultado = await EJECUTORES[tarea.tipo](
                    tarea.parametros, self.executor
                )
            tarea.estado = "completada"
        except TimeoutError:
            tarea.estado = "fallida"
            tarea.error = f"timeout: superó {tarea.timeout} segundos"
        except Exception as exc:
            log.exception("La tarea %s falló", tarea.id)
            tarea.estado = "fallida"
            tarea.error = f"{type(exc).__name__}: {exc}"
        finally:
            tarea.finalizada = time.time()


plataforma = Plataforma()
