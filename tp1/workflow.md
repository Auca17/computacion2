# Workflow — Monitor de Procesos

Acá explico cómo funciona todo el proyecto, archivo por archivo, función por función.

---

## ¿Qué hace el proyecto?

Es un **monitor de procesos en tiempo real** para Linux, parecido a `htop`. Lee toda la información directamente del filesystem `/proc` (sin usar librerías como `psutil`). Muestra los datos en una interfaz de terminal (TUI) hecha con `curses`.

Lo importante: es un **sistema multiproceso**. Hay 7 procesos analizadores corriendo en paralelo, cada uno recogiendo un tipo de dato distinto a su propio ritmo. Todos escriben a una memoria compartida (`Manager.dict()`) y la interfaz lee de ahí para mostrar los datos.

---

## Cómo levantar el proyecto

```bash
docker compose up --build
```

Eso construye la imagen Docker y levanta el contenedor. El monitor arranca automáticamente.

---

## Arquitectura general

```
┌──────────────────────────────────────┐
│           SNAPSHOT GLOBAL            │
│      (Manager dict compartido)       │
│                                      │
│  Cada analizador escribe acá         │
│  El display lee de acá               │
└────────▲─────────────────────▲───────┘
         │ escriben            │ lee
┌────────┼─────────┬──────────┴────────┐
│        │         │                    │
│ Resumen│ Memoria │ FDs    ...  Display│
│ (2s)   │ (3s)    │ (5s)        (TUI) │
└────────┘─────────┘────────────────────┘
```

### El flujo es así:

1. `main.py` arranca todo: crea la memoria compartida, lanza los 7 analizadores como procesos daemon, configura las señales, y arranca la interfaz curses.
2. Cada **analizador** corre en un loop infinito: lee datos de `/proc`, los mete en el snapshot, y duerme su intervalo.
3. El **display** lee del snapshot y dibuja la pantalla.
4. Cuando el usuario aprieta `q` o llega un SIGINT/SIGTERM, se setea el `stop_event` y todos terminan limpiamente.

---

## Archivos del proyecto y qué hace cada uno

### `main.py` — Punto de entrada

Es el orquestador. Hace esto:

1. **Carga la configuración** de `config.json` (intervalos, filtros, modo verbose)
2. **Crea recursos compartidos**:
   - `manager.dict()` → el snapshot donde los analizadores escriben
   - `multiprocessing.Event()` → el `stop_event` para shutdown
   - `multiprocessing.Value('d', X)` → un float compartido por cada analizador para controlar su intervalo
   - `multiprocessing.Value('b', False)` → flag booleano para modo verbose
3. **Importa y arranca** los 7 analizadores como procesos daemon
4. **Configura** el manejo de señales con `SignalHandler`
5. **Arranca** la TUI con `curses.wrapper(display.run)`
6. **Al salir**: setea el stop_event, espera que los hijos terminen (join con timeout de 3s), y si alguno no termina lo mata con terminate()

#### Funciones:
- `load_config(path)` → Busca `config.json` en dos lugares posibles y devuelve un dict con los intervalos, filtros y verbose. Si no encuentra nada, devuelve valores por defecto.
- `main()` → Toda la orquestación descrita arriba.

---

### `procfs.py` — Helpers para leer /proc

Es el corazón del proyecto. Todas las funciones que leen y parsean archivos de `/proc` están acá. Ningún analizador toca `/proc` directamente — siempre pasa por estas funciones.

#### Constantes importantes:
- `PROC_BASE` → Ruta base de /proc. Por defecto es `/proc`, pero en Docker se cambia a `/host_proc` con la variable de entorno `PROC_BASE`.
- `_SIGNAL_NAMES` → Diccionario que mapea número de señal → nombre (ej: 15 → "SIGTERM")
- `_STAT_FIELDS` → Mapeo de índices del archivo `/proc/<pid>/stat` a nombres legibles
- `SCHED_POLICIES` → Mapeo de número de política de scheduling → nombre (ej: 0 → "OTHER")

#### Funciones principales:

| Función | Qué hace |
|---------|----------|
| `read_file(path)` | Lee un archivo de forma segura. Si falla (permiso denegado, archivo desapareció) devuelve string vacío en vez de tirar error. |
| `_safe_int(value, default)` | Convierte un string a int. Si falla, devuelve el default (0). Esto evita que el programa crashee por un dato raro. |
| `list_pids(proc_base)` | Lista todas las carpetas numéricas en `/proc` — cada una es un PID. Devuelve una lista ordenada de enteros. |
| `parse_stat(pid, proc_base)` | Parsea `/proc/<pid>/stat`. Este archivo tiene muchos campos separados por espacios, pero el campo 2 (comm) está entre paréntesis y puede contener espacios, así que hay que buscar el primer `(` y el último `)` para no romper el parseo. |
| `_parse_stat_line(content)` | La lógica interna del parseo de stat. Busca los paréntesis, extrae el comm, y mapea los campos a un dict con nombres legibles. |
| `parse_status(pid, proc_base)` | Parsea `/proc/<pid>/status` que tiene formato "Clave:\tValor" por línea. Devuelve un dict con todas las claves. |
| `parse_cmdline(pid, proc_base)` | Lee `/proc/<pid>/cmdline` — los argumentos del comando están separados por bytes nulos (`\x00`), los reemplaza por espacios. |
| `parse_maps(pid, proc_base)` | Parsea `/proc/<pid>/maps` para obtener los segmentos de memoria. Agrupa por tipo: text (ejecutable), data (escritura), heap, stack, shared, other. |
| `list_fds(pid, proc_base)` | Lista los file descriptors abiertos de un proceso leyendo los symlinks en `/proc/<pid>/fd/`. |
| `_classify_fd(target)` | Clasifica un FD según su destino: socket, pipe, tty, file, etc. |
| `list_threads(pid, proc_base)` | Lista los TIDs (Thread IDs) de un proceso leyendo `/proc/<pid>/task/`. |
| `parse_thread_stat/comm/status(pid, tid)` | Leen los archivos stat, comm y status de un thread específico. |
| `decode_signal_mask(hex_mask)` | **Función clave**: Convierte una máscara hexadecimal de 64 bits (como `0000000000004003`) a una lista de nombres de señales. Cada bit representa una señal: bit 0 = señal 1 (SIGHUP), bit 1 = señal 2 (SIGINT), etc. |
| `parse_proc_stat(proc_base)` | Parsea `/proc/stat` (global, no por proceso) para obtener tiempos de CPU del sistema, boot time, y total de forks. |
| `parse_loadavg(proc_base)` | Parsea `/proc/loadavg` para obtener load average de 1, 5 y 15 minutos. |
| `parse_meminfo(proc_base)` | Parsea `/proc/meminfo` para obtener memoria total, libre, buffers, cached, swap. |
| `parse_uptime(proc_base)` | Parsea `/proc/uptime` para obtener segundos desde el boot. |
| `get_username(uid)` | Convierte un UID numérico al nombre de usuario usando `pwd.getpwuid()`. |
| `calc_cpu_percent(prev_utime, prev_stime, curr_utime, curr_stime, total_elapsed)` | Calcula CPU% como: `((delta_utime + delta_stime) / total_elapsed_ticks) * 100`. Necesita valores previos para calcular el delta. |
| `get_memory_fields(status_dict)` | Extrae los campos de memoria de un dict de status y los convierte de "12345 kB" a enteros. |
| `get_scheduling_policy_name(policy_num)` | Convierte número de política de scheduling a nombre legible (0 → "OTHER", 1 → "FIFO", etc.). |

---

### `recolector.py` — Utilidad para listar PIDs

Módulo simple con una sola función `get_pids()` que delega a `procfs.list_pids()`. Existe como abstracción pero en la práctica los analizadores llaman directamente a `list_pids()`.

---

### `senales.py` — Manejo de señales del monitor

Maneja las señales que recibe el propio monitor (NO las señales que lee de otros procesos — eso es otro archivo).

#### El patrón self-pipe:

Cuando llega una señal (ej: SIGINT), Python ejecuta el handler en cualquier momento interrumpiendo lo que estaba haciendo. Dentro de un handler NO podés hacer cosas complejas (como escribir JSON o leer archivos) porque podés corromper datos.

La solución es el **self-pipe**:
1. Se crea un pipe (`os.pipe()`) con los dos extremos no-bloqueantes
2. Se registra el extremo de escritura con `signal.set_wakeup_fd()` — Python escribe automáticamente un byte ahí cuando llega una señal
3. El handler solo hace `self._received_signals.append(signum)` — mínimo y seguro
4. En el loop principal, se llama a `process_pending()` que drena el pipe y procesa las señales acumuladas de forma segura

#### Clase `SignalHandler`:

| Método | Qué hace |
|--------|----------|
| `__init__(...)` | Crea el pipe, guarda referencias a stop_event, snapshot, intervals, verbose |
| `setup()` | Registra los handlers para SIGINT, SIGTERM, SIGHUP, SIGUSR1, SIGUSR2 |
| `_handler(signum, frame)` | Handler mínimo — solo guarda el número de señal |
| `process_pending()` | Drena el pipe, revisa señales acumuladas, y ejecuta la acción correspondiente |
| `_handle_shutdown()` | SIGINT/SIGTERM → setea el stop_event |
| `_reload_config()` | SIGHUP → relee config.json y actualiza intervalos y filtros |
| `_dump_snapshot()` | SIGUSR1 → escribe el snapshot a `dump_<timestamp>.json` |
| `_toggle_verbose()` | SIGUSR2 → invierte el flag verbose |
| `_drain_pipe()` | Lee y descarta todos los bytes del pipe |
| `cleanup()` | Cierra los file descriptors del pipe |

---

### `display.py` — Interfaz de terminal (TUI)

El archivo más grande. Dibuja toda la interfaz con `curses`.

#### Layout de pantalla:
```
┌─────────────────────────────────────────┐
│ HEADER: título, vista activa, stats     │  ← línea 0
├─────────────────────────────────────────┤
│ LISTA DE PROCESOS (scrollable)          │  ← 60% de la pantalla
│  PID   USER   ST   CPU%  RSS   THR CMD │
│  1234  root    S   2.3   45678  4  bash│
│  ...                                    │
├─────────────────────────────────────────┤
│ PANEL DE DETALLE (cambia según vista)   │  ← 40% restante
│  Depende de qué vista esté activa       │
├─────────────────────────────────────────┤
│ FOOTER: keybindings                     │  ← última línea
└─────────────────────────────────────────┘
```

La vista "Sistema" (tecla 7/g) es especial: usa toda la pantalla en vez de dividirla.

#### Constantes:
- `VIEW_KEYS` → Lista de tuplas (tecla_num, tecla_letra, clave_snapshot, label) para las 7 vistas
- `MIN_INTERVALS` → Intervalos mínimos por vista (no podés bajar de ahí con `-`)
- `SORT_MODES` → Modos de ordenamiento: cpu, rss, pid (se ciclan con `c`)
- `CP_*` → IDs de pares de colores para curses

#### Clase `Display`:

**Estado interno:**
- `_current_view` → qué vista está activa ("resumen", "memoria", etc.)
- `_cursor` → qué fila de la lista está seleccionada
- `_scroll_top` → primera fila visible (para scroll)
- `_pinned_pid` → PID fijado (no cambia aunque cambie el orden)
- `_sort_mode_idx` → modo de ordenamiento actual
- `_filter_cmd` / `_filter_user` → filtros activos

**Métodos principales:**

| Método | Qué hace |
|--------|----------|
| `run(stdscr)` | Loop principal: procesa señales → dibuja → lee input. Usa `halfdelay(5)` para que `getch()` bloquee máximo 500ms. |
| `_init_curses()` | Configura colores, oculta cursor, setea halfdelay |
| `_handle_input(stdscr)` | Lee una tecla y ejecuta la acción correspondiente (cambiar vista, navegar, filtrar, etc.) |
| `_read_input(stdscr, prompt)` | Muestra un prompt en la última línea y lee texto del usuario (para filtros) |
| `_adjust_interval(delta)` | Sube o baja el intervalo de la vista activa (respetando el mínimo) |
| `_get_resumen_data()` | Obtiene los datos de resumen del snapshot |
| `_get_pid_list()` | Filtra y ordena los PIDs según filtros y modo de sort activos |
| `_selected_pid()` | Devuelve el PID seleccionado (el pinned si hay, sino el del cursor) |
| `_draw(stdscr)` | Dibuja toda la pantalla: header + lista + detalle + footer |
| `_draw_header(stdscr, w)` | Dibuja la barra superior con título, vista activa, CPU/Mem/Load mini |
| `_draw_process_list(...)` | Dibuja la tabla de procesos con scroll |
| `_draw_detail_panel(...)` | Dibuja el panel de detalle según la vista activa |
| `_detail_resumen(pid)` | Genera líneas de detalle para vista Resumen |
| `_detail_memoria(pid)` | Genera líneas de detalle para vista Memoria |
| `_detail_fds(pid)` | Genera líneas de detalle para vista FDs (limita a 5 sin verbose) |
| `_detail_threads(pid)` | Genera líneas de detalle para vista Threads |
| `_detail_senales(pid)` | Genera líneas de detalle para vista Señales |
| `_detail_scheduling(pid)` | Genera líneas de detalle para vista Scheduling |
| `_draw_sistema_full(...)` | Dibuja la vista Sistema en pantalla completa |
| `_draw_footer(stdscr, h, w)` | Dibuja la barra inferior con keybindings |
| `_draw_help_overlay(...)` | Dibuja el overlay de ayuda centrado |

**Funciones auxiliares (fuera de la clase):**
- `_trunc(text, max_len)` → Trunca un string y agrega "…" si se pasa
- `_kb_human(kb)` → Convierte KB a formato legible (KB, MB, GB)
- `_fmt_uptime(seconds)` → Formatea uptime como "3d 4h 12m 5s"
- `_fmt_epoch(epoch)` → Formatea timestamp Unix a fecha legible

---

### Los 7 analizadores (`src/analizadores/`)

Todos siguen el mismo patrón:

```python
class XxxAnalyzer(multiprocessing.Process):
    def __init__(self, snapshot, interval_value, stop_event):
        # guarda referencias a la memoria compartida
        
    def run(self):
        # loop infinito: collect → store → sleep
        while not self.stop_event.is_set():
            data = self._collect()
            self.snapshot["clave"] = {"data": data, "ts": time.time()}
            self.stop_event.wait(self.interval.value)
    
    def _collect(self):
        # lee /proc para todos los PIDs y devuelve un dict
```

#### Detalles por analizador:

**`resumen.py`** — Clave: `"resumen"`, Intervalo: 2s
- Lee stat, status y cmdline de cada proceso
- Calcula CPU% usando deltas de jiffies entre ciclos
- Guarda: PID, PPID, UID, GID, usuario, estado, comando, CPU%, threads, RSS

**`memoria.py`** — Clave: `"memoria"`, Intervalo: 3s
- Lee status (para VmSize, VmRSS, etc.) y maps (para segmentos)
- Guarda: 8 campos de memoria virtual + page faults + segmentos agrupados

**`fds.py`** — Clave: `"fds"`, Intervalo: 5s
- Lee los symlinks en `/proc/<pid>/fd/`
- Clasifica cada FD por tipo (socket, pipe, tty, file)

**`threads.py`** — Clave: `"threads"`, Intervalo: 2s
- Lee `/proc/<pid>/task/` para listar threads
- Por cada thread: stat (estado, CPU%), comm (nombre), status (context switches)
- Calcula CPU% por thread con deltas

**`senales.py`** (analizador, no confundir con el handler) — Clave: `"senales"`, Intervalo: 10s
- Lee las máscaras SigBlk, SigIgn, SigCgt, SigPnd, ShdPnd de status
- Las decodifica a nombres legibles con `decode_signal_mask()`

**`scheduling.py`** — Clave: `"scheduling"`, Intervalo: 10s
- Lee stat para nice, priority, policy, rt_priority, utime, stime, SID, PGID
- Lee status para CPU affinity y context switches

**`sistema.py`** — Clave: `"sistema"`, Intervalo: 2s
- Lee `/proc/stat` para CPU global (calcula porcentajes con deltas)
- Lee `/proc/loadavg`, `/proc/meminfo`, `/proc/uptime`
- Recorre todos los PIDs una vez para contar estados, zombies, threads totales
- Saca el top 3 por CPU y top 3 por memoria

---

## Comunicación entre procesos (IPC)

### `Manager.dict()` — El snapshot

Es un diccionario compartido gestionado por un proceso Manager que Python crea automáticamente. Funciona así:
- El Manager crea un proceso servidor que tiene el dict real en su memoria
- Los demás procesos acceden mediante objetos Proxy que se comunican por socket Unix
- Cada escritura `snapshot["resumen"] = {...}` se serializa y envía al servidor
- Cada lectura `snapshot.get("resumen")` hace lo mismo en reversa

¿Por qué no usar un dict normal? Porque cada proceso tiene su propio espacio de memoria (después del fork). Un dict normal en el proceso padre no se ve en los hijos (o se ve una copia congelada).

### `Value('d', 2.0)` — Los intervalos

Para los intervalos usamos `multiprocessing.Value` que es memoria compartida directa (mmap). Un `Value('d', 2.0)` es un float de 64 bits compartido. Cuando el display hace `intervals["resumen"].value = 3.0`, el analizador de resumen lo ve inmediatamente en su próximo ciclo.

¿Por qué no Manager para esto? Porque es un solo float — `Value` es más rápido y simple que pasar por el socket del Manager.

### `Event()` — El stop_event

Un `multiprocessing.Event` es un flag booleano compartido. Cuando alguien hace `stop_event.set()`, todos los procesos que están en `stop_event.wait(timeout)` se despiertan. Es la forma limpia de decir "ya terminamos".

---

## Manejo de señales

El monitor responde a estas señales:

| Señal | Cómo enviarla | Qué hace |
|-------|---------------|----------|
| SIGINT | Ctrl+C o `kill -2 <pid>` | Shutdown limpio |
| SIGTERM | `kill <pid>` | Shutdown limpio |
| SIGHUP | `kill -1 <pid>` | Recarga config.json |
| SIGUSR1 | `kill -10 <pid>` | Dump snapshot a JSON |
| SIGUSR2 | `kill -12 <pid>` | Toggle modo verbose |

Para mandar señales desde otra terminal:
```bash
# Primero encontrar el PID del monitor
docker compose exec monitor ps aux | grep main.py

# Después mandar la señal
docker compose exec monitor kill -SIGUSR1 <pid>
```

---

## Docker

### `Dockerfile`
```dockerfile
FROM python:3.11-slim     # imagen base con Python
WORKDIR /app              # directorio de trabajo
COPY requirements.txt .   # copiar dependencias
RUN pip install ...        # instalar (en este caso no hay externas)
COPY config.json .         # copiar config
COPY src/ src/             # copiar código
ENV TERM=xterm-256color    # para que curses tenga colores
ENV PYTHONUNBUFFERED=1     # output sin buffer (para ver logs)
CMD ["python", "-u", "src/main.py"]  # comando de arranque
```

### `docker-compose.yml`
```yaml
services:
  monitor:
    build: .              # construir desde el Dockerfile
    tty: true             # asignar una pseudo-terminal (para curses)
    stdin_open: true       # mantener stdin abierto (para input)
    pid: "host"           # compartir el namespace de PIDs del host
    volumes:
      - /proc:/host_proc:ro  # montar /proc del host como solo lectura
    environment:
      - PROC_BASE=/host_proc  # decirle al código que use /host_proc
      - TERM=xterm-256color
```

**¿Por qué `pid: "host"`?** Para que el contenedor vea los procesos del host. Sin esto solo vería sus propios procesos.

**¿Por qué montar `/proc` como `/host_proc`?** Porque el `/proc` dentro del contenedor muestra solo los procesos del contenedor. Montando el `/proc` del host podemos leer la info de TODOS los procesos.

---

## config.json

```json
{
    "intervalos": {
        "resumen": 2.0,
        "memoria": 3.0,
        "fds": 5.0,
        "threads": 2.0,
        "senales": 10.0,
        "scheduling": 10.0,
        "sistema": 2.0
    },
    "filtros": {
        "usuario": null,
        "comando": null
    },
    "verbose": false
}
```

- **intervalos**: cada cuántos segundos cada analizador recoge datos. Se pueden ajustar en tiempo real con `+`/`-` o recargando con SIGHUP.
- **filtros**: filtros por defecto al arrancar. `null` = sin filtro.
- **verbose**: si está en `true`, la vista de FDs muestra todos los file descriptors en vez de solo 5.

---

## Conceptos clave

### ¿Qué es /proc?
Es un filesystem virtual de Linux. No son archivos reales en disco — son ventanas al kernel. Cada carpeta numérica (`/proc/1234/`) es un proceso, y los archivos dentro tienen info del proceso.

### ¿Qué es un jiffy/tick?
Es la unidad de tiempo del scheduler de Linux. Los campos utime y stime en `/proc/<pid>/stat` están en jiffies. Para calcular CPU% necesitás comparar los jiffies del proceso contra los jiffies totales del sistema.

### ¿Qué es un zombie?
Un proceso que ya terminó pero su padre no llamó a `wait()`. Aparece con estado `Z` en `/proc/<pid>/stat`. El kernel mantiene la entrada para que el padre pueda leer el exit status.

### ¿Qué es un LWP (Light Weight Process)?
Es cómo Linux implementa threads. Cada thread es un LWP con su propio TID visible en `/proc/<pid>/task/<tid>/`. Comparten memoria con el proceso padre pero tienen su propio stack y estado de CPU.

### ¿Qué es el GIL?
El Global Interpreter Lock de Python. Solo un thread puede ejecutar código Python a la vez. Por eso usamos **procesos** en vez de **threads** para los analizadores — necesitamos paralelismo real.
