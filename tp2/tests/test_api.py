"""Pruebas de la API HTTP: creación, consulta, filtros y errores."""

import hashlib
import time

from .conftest import crear, esperar_estado


async def test_post_responde_inmediato_con_pendiente(cliente):
    inicio = time.perf_counter()
    r = await crear(cliente, "esperar", {"segundos": 1})
    assert r.status_code == 202
    assert r.json()["estado"] == "pendiente"
    assert time.perf_counter() - inicio < 0.5


async def test_esperar_completa(cliente):
    r = await crear(cliente, "esperar", {"segundos": 0.05})
    tarea = await esperar_estado(cliente, r.json()["id"], "completada")
    assert tarea["resultado"] == {"esperado": 0.05}
    assert tarea["finalizada"] >= tarea["iniciada"]


async def test_filtro_por_estado(cliente):
    larga = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
    corta = (await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
    await esperar_estado(cliente, corta, "completada")
    await esperar_estado(cliente, larga, "ejecutando")
    completadas = (await cliente.get("/tareas?estado=completada")).json()
    ejecutando = (await cliente.get("/tareas?estado=ejecutando")).json()
    assert [t["id"] for t in completadas] == [corta]
    assert [t["id"] for t in ejecutando] == [larga]
    assert len((await cliente.get("/tareas")).json()) == 2
    assert (await cliente.get("/tareas?estado=otro")).status_code == 422


async def test_cuerpo_invalido_422(cliente):
    assert (await crear(cliente, "esperar", {"segundos": -1})).status_code == 422
    assert (await crear(cliente, "hashear", {"texto": "x"})).status_code == 422
    assert (await crear(cliente, "descargar", {"urls": []})).status_code == 422
    assert (await crear(cliente, "inexistente", {})).status_code == 422
    assert (await cliente.post("/tareas", json={})).status_code == 422


async def test_tarea_inexistente_404(cliente):
    assert (await cliente.get("/tareas/nada")).status_code == 404
    assert (await cliente.delete("/tareas/nada")).status_code == 404


async def test_hashear_coincide_con_referencia(cliente):
    digest = hashlib.sha256(b"hola").digest()
    for _ in range(999):
        digest = hashlib.sha256(digest).digest()
    r = await crear(cliente, "hashear", {"texto": "hola", "iteraciones": 1000})
    tarea = await esperar_estado(cliente, r.json()["id"], "completada", 20)
    assert tarea["resultado"] == digest.hex()


async def test_estadisticas(cliente):
    ids = [(await crear(cliente, "esperar", {"segundos": 0})).json()["id"]
           for _ in range(3)]
    for i in ids:
        await esperar_estado(cliente, i, "completada")
    larga = (await crear(cliente, "esperar", {"segundos": 30})).json()["id"]
    await esperar_estado(cliente, larga, "ejecutando")
    est = (await cliente.get("/estadisticas")).json()
    assert est["total"] == 4
    assert est["por_estado"]["completada"] == 3
    assert est["por_estado"]["ejecutando"] == 1
    assert est["workers_ocupados"] == 1
    assert est["workers_total"] == 2
    assert est["duracion_promedio_por_tipo"]["esperar"] is not None
