"""Servidor de prueba con demora configurable, para mediciones reproducibles."""

import asyncio

import uvicorn
from fastapi import FastAPI, Query

app = FastAPI(title="Servidor lento")


@app.get("/demora")
async def demora(ms: int = Query(0, ge=0, le=60_000)):
    """Responde luego de `ms` milisegundos, sin bloquear el event loop."""
    await asyncio.sleep(ms / 1000)
    return {"demora_ms": ms}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
