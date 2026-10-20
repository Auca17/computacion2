Fecha: 2026-10-20 01:46:09
Máquina (contenedor): Linux-6.18.54.1-microsoft-standard-WSL2-x86_64-with-glibc2.41, 8 CPU
Config: API WORKERS=4 (MODO_CPU=executor), Celery concurrency=4 (prefetch=1, acks_late), broker=redis://redis:6379/0

## (a) I/O simulado: 20 x esperar(1 s)

| Sistema | Total 20 x esperar(1 s) [s] |
|---|---|
| API asyncio (4 workers) | 5.31 |
| Celery (concurrency 4) | 5.31 |

## (b) CPU: 8 x hashear

1,240,000 iteraciones por tarea (~1 s)

| Sistema | Total 8 x hashear [s] |
|---|---|
| API asyncio (4 workers + ProcessPool) | 2.60 |
| Celery (concurrency 4, prefork) | 2.19 |

## (c) Descargas: 20 x lento ms=500

| Sistema | Total 20 descargas de 500 ms [s] |
|---|---|
| API: 1 tarea con 20 URLs (gather) | 0.65 |
| Celery: 20 tareas de 1 URL | 2.90 |
| Celery: 1 tarea con 20 URLs (asyncio.run + gather) | 0.63 |

## (d) Cancelación de esperar(30) tras 1 s

| Sistema | Hasta estado final [s] | Estado | Efecto en workers |
|---|---|---|---|
| API: DELETE (cancela el asyncio.Task) | 0.02 | cancelada | ninguno: el worker (corrutina) sigue vivo |
| Celery: revoke(terminate=True) | 0.01 | REVOKED | el proceso hijo se mata con SIGTERM y el pool lo repone; PIDs antes=[8, 9, 10, 11] despues=[8, 9, 10, 64] |

## (e) Latencia de envío de una tarea

| Sistema | Media [ms] | Mediana [ms] | Máx [ms] |
|---|---|---|---|
| API: POST /tareas | 10.61 | 10.33 | 18.27 |
| .delay() (publica en Redis) | 1.36 | 1.35 | 2.37 |

## Lectura de los resultados

- (a) Empate: con 4 procesos Celery y 4 workers asyncio, 20 tareas de 1 s son 5 rondas. El paralelismo es el límite, no el framework.
- (b) Celery es algo más rápido (2.19 s vs 2.60 s): la API suma el sondeo cada 50 ms y el paso por el event loop; ambos usan 4 procesos para la CPU.
- (c) Una tarea con 20 URLs concurrentes (0.63-0.65 s) gana por mucho a 20 tareas de una URL (2.90 s): con 4 procesos, la concurrencia de I/O de asyncio dentro de una tarea rinde más que repartir tareas chicas entre procesos.
- (d) Ambos llegan al estado final en pocos ms. En la API se cancela una corrutina y el worker sigue intacto; en Celery `terminate=True` mata el proceso hijo (SIGTERM) y el pool lo reemplaza por otro PID (8,9,10,11 -> 8,9,10,64).
- (e) `.delay()` (publicar en Redis, ~1.4 ms) es unas 8 veces más barato que el POST HTTP a la API (~10 ms), que además incluye el viaje HTTP y la validación.
- Nota: las mediciones se hicieron desde un contenedor de la misma red de Compose; la API se consulta por sondeo cada 50 ms y Celery con `AsyncResult.get`.
