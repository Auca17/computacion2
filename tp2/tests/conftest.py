"""Fixtures: aplicación con plataforma arrancada y cliente HTTP en memoria."""

import asyncio

import httpx
import pytest

from app import config
from app.estado import registro
from app.cola import plataforma
from app.limite import limitador
from app.main import app


@pytest.fixture(autouse=True)
def configuracion(monkeypatch, tmp_path):
    """Configuración chica y volcados en un directorio temporal."""
    monkeypatch.setattr(config, "WORKERS", 2)
    monkeypatch.setattr(config, "TIMEOUT_DEFECTO", 5.0)
    monkeypatch.setattr(config, "MAX_COLA", 100)
    monkeypatch.setattr(config, "MODO_CPU", "executor")
    monkeypatch.setattr(config, "DIR_VOLCADOS", str(tmp_path / "volcados"))
    registro.clear()
    limitador.reiniciar()
    plataforma.aceptando = True
    plataforma.ocupados = 0
    plataforma.en_ejecucion.clear()
    plataforma.temporizadores.clear()
    yield
    registro.clear()


@pytest.fixture
async def cliente():
    """Cliente HTTP contra la app; ASGITransport no corre el lifespan."""
    plataforma.iniciar()
    transporte = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transporte,
                                 base_url="http://test") as c:
        yield c
    await plataforma.apagar(0.05)


async def crear(cliente, tipo, parametros, **extra):
    """POST /tareas; devuelve la respuesta."""
    return await cliente.post(
        "/tareas", json={"tipo": tipo, "parametros": parametros, **extra})


async def esperar_estado(cliente, id_tarea, estado, limite=5.0):
    """Consulta la tarea hasta que alcanza `estado` y la devuelve."""
    async with asyncio.timeout(limite):
        while True:
            tarea = (await cliente.get(f"/tareas/{id_tarea}")).json()
            if tarea["estado"] == estado:
                return tarea
            await asyncio.sleep(0.01)
