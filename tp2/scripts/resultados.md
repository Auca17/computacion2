# Resultados de las mediciones

Fecha: 2026-10-19. Host Windows 10 con Docker Desktop (motor Linux).
`os.cpu_count()` = 8 en el host y 8 dentro del contenedor `api`
(`docker compose exec api python -c "import os;print(os.cpu_count())"`).
Stack levantado con `docker compose up --build -d`; los scripts corren en el
host. Tiempos en segundos salvo que se indique. Cada tabla es la salida real
del script (una corrida por configuración).

## Medición 1: 20 descargas secuenciales contra 20 concurrentes

Configuración: WORKERS=4, MODO_CPU=executor. Comando: `python scripts/medir_io.py`
(URLs `/demora?ms=500&i=<n>` sobre el servidor lento).

| Modo | Tiempo total (s) | Speedup |
|---|---|---|
| 20 tareas de 1 URL, una por vez | 12.153 | 1.00x |
| 1 tarea con 20 URLs (gather) | 0.659 | 18.45x |

Tiempos propios por URL de la tarea concurrente: min 0.515 s, max 0.528 s, media 0.521 s.
Ideal secuencial: 10.000 s; ideal concurrente: 0.500 s.

Referencia directa con httpx desde el host (sin la API), mismas 20 URLs:

| Estrategia | Tiempo total (s) | Speedup |
|---|---|---|
| for con await | 10.066 | 1.00x |
| asyncio.gather | 0.552 | 18.24x |

Lectura: `for` con `await` espera cada respuesta antes de lanzar la siguiente
(20 x 0.5 s = 10 s); `gather` lanza las 20 y espera todas a la vez (~0.5 s).
La versión por API en modo secuencial suma ~2 s de sobrecarga de 20 ciclos
POST + sondeo cada 50 ms (~0.1 s por tarea).

## Medición 2: el event loop bloqueado

Comando: `python scripts/medir_bloqueo.py --modo <modo> --iteraciones 20000000`
(un `hashear` de 20 millones de iteraciones; `GET /tareas` cada 100 ms).
WORKERS=4. La API se reinició con `MODO_CPU=bloqueante docker compose up -d api`
para la segunda corrida.

### MODO_CPU=executor

| Situación | Muestras | Media (ms) | p50 (ms) | p95 (ms) | Máx (ms) |
|---|---|---|---|---|---|
| Sin carga (línea base) | 28 | 3.8 | 3.1 | 6.7 | 14.1 |
| Durante hashear (executor) | 80 | 3.4 | 3.3 | 4.2 | 5.5 |

Hash: completada; duración total desde el POST: 7.88 s.

### MODO_CPU=bloqueante

| Situación | Muestras | Media (ms) | p50 (ms) | p95 (ms) | Máx (ms) |
|---|---|---|---|---|---|
| Sin carga (línea base) | 28 | 2.9 | 2.4 | 4.6 | 12.7 |
| Durante hashear (bloqueante) | 7 | 1116.1 | 4.3 | 7789.6 | 7789.6 |

Hash: completada; duración total desde el POST: 7.93 s.

Lectura: con executor la API responde en ~3 ms durante el hash (80 muestras en
~8 s). Con el hash en el event loop, la única consulta en vuelo tardó 7.79 s
(casi todo el hash) y en ese lapso solo se completaron 7 muestras (las previas
al inicio del bloqueo); la latencia máxima fue ~2650 veces la de reposo. El
tiempo total del hash es el mismo en ambos modos (~7.9 s): el executor no hace
el cálculo más rápido, evita que congele a los demás.

## Medición 3: techo del pool

Comando: `python scripts/medir_techo.py --exp <esperar|hashear|descargar> --workers <W>`.
Todas las tareas de cada fila se postean a la vez. "Espera media en cola" es
`iniciada - creada`. MODO_CPU=executor en todas las corridas.

### 3a. `esperar(1 s)`, WORKERS=4

| N tareas | Tiempo total (s) | Espera media en cola (s) | No completadas |
|---|---|---|---|
| 1 | 1.08 | 0.00 | 0 |
| 2 | 1.10 | 0.00 | 0 |
| 4 | 1.10 | 0.00 | 0 |
| 8 | 2.07 | 0.48 | 0 |
| 16 | 4.09 | 1.49 | 0 |
| 32 | 8.08 | 3.49 | 0 |
| 64 | 16.04 | 7.46 | 0 |

### 3b. `esperar(1 s)`, WORKERS=16

| N tareas | Tiempo total (s) | Espera media en cola (s) | No completadas |
|---|---|---|---|
| 1 | 1.07 | 0.00 | 0 |
| 2 | 1.11 | 0.00 | 0 |
| 4 | 1.08 | 0.00 | 0 |
| 8 | 1.10 | 0.00 | 0 |
| 16 | 1.08 | 0.00 | 0 |
| 32 | 2.09 | 0.49 | 0 |
| 64 | 4.14 | 1.50 | 0 |

Lectura: el tiempo total es ~ceil(N / WORKERS) x 1 s. El techo está en
N = WORKERS (4 en 3a, 16 en 3b): pasado ese punto las tareas esperan en la
cola y el tiempo crece linealmente. Al subir el pool el techo se mueve.

### 3c. `hashear` (2.000.000 iteraciones por tarea), WORKERS=16

| N tareas | Tiempo total (s) | Espera media en cola (s) | No completadas |
|---|---|---|---|
| 1 | 0.89 | 0.00 | 0 |
| 2 | 1.05 | 0.00 | 0 |
| 4 | 1.34 | 0.00 | 0 |
| 8 | 3.31 | 0.00 | 0 |
| 16 | 13.16 | 0.00 | 0 |

Lectura: con 16 workers ninguna tarea espera en la cola, pero el cómputo se
satura por CPU: casi plano hasta N = 4 (0.89 a 1.34 s), luego el tiempo crece
más que proporcionalmente (N = 8: 3.31 s; N = 16: 13.16 s). El techo lo marca
el hardware, no WORKERS: `ProcessPoolExecutor` usa `os.cpu_count()` = 8
procesos, y esos 8 núcleos lógicos del host (posiblemente 4 físicos con
hyperthreading, por la degradación desde N = 4) se comparten con el resto del
sistema y de Docker Desktop. Con N > núcleos, los bloques de las tareas se
intercalan y todas terminan tarde. El crecimiento supralineal entre N = 8 y
16 (x4 para x2 tareas) no está explicado por esta medición; es un dato
observado, probablemente por competencia de CPU y cambio de contexto.

### 3d. `descargar` (10 URLs de `/demora?ms=500` por tarea), WORKERS=4

| N tareas | Tiempo total (s) | Espera media en cola (s) | No completadas |
|---|---|---|---|
| 1 | 0.61 | 0.00 | 0 |
| 4 | 0.62 | 0.00 | 0 |
| 16 | 2.26 | 0.84 | 0 |
| 64 | 9.03 | 4.18 | 0 |

### 3e. `descargar` (10 URLs de `/demora?ms=500` por tarea), WORKERS=16

| N tareas | Tiempo total (s) | Espera media en cola (s) | No completadas |
|---|---|---|---|
| 1 | 0.69 | 0.00 | 0 |
| 4 | 0.70 | 0.01 | 0 |
| 16 | 1.05 | 0.01 | 0 |
| 64 | 5.19 | 1.62 | 0 |

Lectura: las tareas de I/O no saturan el event loop (con N = 4 siguen en
~0.6 s) pero cada tarea ocupa un worker mientras dura, así que el límite es
WORKERS: con 4 workers, 16 tareas ya esperan en cola (2.26 s); con 16
workers el mismo caso casi no espera (1.05 s). Con N = 64 y 16 workers el
tiempo (5.19 s) es mayor que el ideal (4 rondas x ~0.6 s = 2.4 s); la causa
no se investigó (hasta 160 conexiones concurrentes y 64 sondeos cada 50 ms
sobre un único proceso de la API).
