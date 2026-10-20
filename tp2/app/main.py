"""Punto de entrada: aplicación FastAPI con ciclo de vida de workers."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api import router
from .cola import plataforma


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Arranca workers y executor; los detiene al apagar."""
    plataforma.iniciar()
    yield
    await plataforma.detener()


app = FastAPI(title="Plataforma de tareas", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
