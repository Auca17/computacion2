"""Pruebas de cancelación, timeout, resiliencia de workers y apagado."""

import asyncio
import json
import time
from pathlib import Path

import httpx

from app import config, tareas
from app.cola import plataforma
from app.estado import volcar_registro

from .conftest import crear, esperar_estado


async def test_cancelar_pendiente_nunca_corre(cliente):
    # Dos tareas largas ocupan los dos workers
    for _ in range(2):
        id_ = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
        await esperar_estado(cliente, id_, "ejecutando")
    pendiente = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    r = await cliente.delete(f"/tareas/{pendiente}")
    assert r.status_code == 200 and r.json()["estado"] == "cancelada"
    await asyncio.sleep(0.2)
    tarea = (await cliente.get(f"/tareas/{pendiente}")).json()
    assert tarea["estado"] == "cancelada" and tarea["iniciada"] is None


async def test_cancelar_esperar_en_ejecucion_y_worker_sigue(cliente):
    id_ = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
    await esperar_estado(cliente, id_, "ejecutando")
    inicio = time.perf_counter()
    r = await cliente.delete(f"/tareas/{id_}")
    assert r.json()["estado"] == "cancelada"
    assert time.perf_counter() - inicio < 1
    # Los workers siguen atendiendo tareas
    siguiente = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    await esperar_estado(cliente, siguiente, "completada")
    await asyncio.sleep(0.05)  # el worker libera su cupo tras el estado final
    assert plataforma.ocupados == 0


async def test_cancelar_hashear_en_ejecucion(cliente):
    id_ = (await crear(cliente, "hashear",
                       {"texto": "x", "iteraciones": 10**9})).json()["id"]
    await esperar_estado(cliente, id_, "ejecutando")
    r = await cliente.delete(f"/tareas/{id_}")
    assert r.json()["estado"] == "cancelada"
    assert id_ not in plataforma.en_ejecucion


async def test_cancelar_tarea_finalizada_409(cliente):
    id_ = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    await esperar_estado(cliente, id_, "completada")
    assert (await cliente.delete(f"/tareas/{id_}")).status_code == 409


async def test_timeout_marca_fallida_con_motivo(cliente):
    id_ = (await crear(cliente, "esperar", {"segundos": 30},
                       timeout=0.1)).json()["id"]
    tarea = await esperar_estado(cliente, id_, "fallida")
    assert "timeout" in tarea["error"]


async def test_worker_sobrevive_a_excepcion(cliente, monkeypatch):
    original = tareas.EJECUTORES["esperar"]

    async def roto(parametros, executor):
        if parametros["segundos"] == 99:
            raise ValueError("falla simulada")
        return await original(parametros, executor)

    monkeypatch.setitem(tareas.EJECUTORES, "esperar", roto)
    malo = (await crear(cliente, "esperar", {"segundos": 99})).json()["id"]
    tarea = await esperar_estado(cliente, malo, "fallida")
    assert "ValueError" in tarea["error"] and "falla simulada" in tarea["error"]
    # Más tareas que workers: todos los workers deben seguir vivos
    ids = [(await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
           for _ in range(4)]
    for i in ids:
        await esperar_estado(cliente, i, "completada")
    assert all(not w.done() for w in plataforma.workers)


async def test_cola_llena_429(cliente, monkeypatch):
    monkeypatch.setattr(plataforma.cola, "_maxsize", 1)
    # Ocupan los workers
    for _ in range(2):
        id_ = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
        await esperar_estado(cliente, id_, "ejecutando")
    assert (await crear(cliente, "esperar", {"segundos": 0})).status_code == 202
    assert (await crear(cliente, "esperar", {"segundos": 0})).status_code == 429


async def test_no_acepta_durante_apagado_503(cliente):
    plataforma.aceptando = False
    r = await crear(cliente, "esperar", {"segundos": 0})
    assert r.status_code == 503


async def test_descargar_con_servidor_simulado(cliente, monkeypatch):
    """Descarga con transporte simulado; una URL falla y las demás no."""
    def responder(request):
        if "falla" in request.url.path:
            raise httpx.ConnectError("sin conexión")
        return httpx.Response(200, content=b"abc")

    real = httpx.AsyncClient
    monkeypatch.setattr(
        tareas.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(responder)))
    urls = ["http://sitio/ok", "http://sitio/falla"]
    id_ = (await crear(cliente, "descargar", {"urls": urls})).json()["id"]
    tarea = await esperar_estado(cliente, id_, "completada")
    ok, mala = tarea["resultado"]
    assert ok["estado_http"] == 200 and ok["bytes"] == 3
    assert "ConnectError" in mala["error"]


async def test_apagado_cancela_y_vuelca_estado(cliente):
    hecha = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    await esperar_estado(cliente, hecha, "completada")
    larga = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
    await esperar_estado(cliente, larga, "ejecutando")

    await plataforma.apagar(0.1)  # lo mismo que hace el lifespan
    ruta = volcar_registro()

    assert ruta.parent == Path(config.DIR_VOLCADOS)
    assert ruta.name.startswith("estado_") and ruta.suffix == ".json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    estados = {t["id"]: t["estado"] for t in datos["tareas"]}
    assert estados == {hecha: "completada", larga: "cancelada"}
    assert datos["total"] == 2
