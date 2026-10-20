"""Cola de tareas y pool de workers (corrutinas)."""

import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from . import config
from .eventos import publicar
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
        # Ejecución de cada tarea en curso como asyncio.Task propio: id -> Task
        self.en_ejecucion: dict[str, asyncio.Task] = {}

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
        try:
            async with asyncio.timeout(tarea.timeout):
                tarea.resultado = await EJECUTORES[tarea.tipo](
                    tarea.parametros, self.executor
                )
            tarea.estado = "completada"
        except TimeoutError:
            tarea.estado = "fallida"
            tarea.error = f"timeout: superó {tarea.timeout} segundos"
        except asyncio.CancelledError:
            tarea.estado = "cancelada"
            raise  # la cancelación nunca se traga
        except Exception as exc:
            log.exception("La tarea %s falló", tarea.id)
            tarea.estado = "fallida"
            tarea.error = f"{type(exc).__name__}: {exc}"
        finally:
            tarea.finalizada = time.time()
            publicar(tarea)

    async def cancelar(self, tarea: Tarea) -> None:
        """Cancela una tarea pendiente o en ejecución (estado no final)."""
        if tarea.estado == "pendiente":
            # El worker la descarta al sacarla de la cola.
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
