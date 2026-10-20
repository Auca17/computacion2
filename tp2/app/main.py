"""Punto de entrada: aplicación FastAPI con ciclo de vida de workers."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api import router
from .eventos import cerrar_todos, router as router_eventos
from .metricas import router as router_metricas
from . import config
from .cola import plataforma
from .estado import reportar_volcado_previo, volcar_registro

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger("plataforma")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca workers y executor; al apagar los detiene y vuelca el estado."""
    reportar_volcado_previo()
    plataforma.iniciar()
    yield
    log.info("Apagado: no se aceptan tareas nuevas")
    await plataforma.apagar(config.GRACIA_APAGADO)
    cerrar_todos()  # los WebSocket abiertos no deben frenar el apagado
    ruta = volcar_registro()
    log.info("Estado volcado en %s", ruta)


app = FastAPI(title="Plataforma de tareas", lifespan=lifespan)
app.include_router(router)
app.include_router(router_eventos)
app.include_router(router_metricas)

if __name__ == "__main__":
    # Un solo proceso: el estado vive en memoria. El timeout evita que
    # conexiones abiertas bloqueen el apagado para siempre.
    uvicorn.run(app, host="0.0.0.0", port=8000,
                timeout_graceful_shutdown=config.GRACIA_APAGADO + 5)
