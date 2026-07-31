# Guía de Estudio Completa — Computación II

> **Apunte integral** que cubre todas las unidades de la materia, con conceptos profundos, ejemplos
> reales, errores típicos y preguntas de examen. Conectado con el TP1 (Monitor de Procesos en Linux).

---

## Índice

- [Bloque 0 — Autónomo](#bloque-0--autónomo)
  - [0.1 argparse y getopt](#01-argparse-y-getopt)
  - [0.2 Filesystem Linux](#02-filesystem-linux)
  - [0.3 Git](#03-git)
  - [0.4 Python Avanzado](#04-python-avanzado)
- [Clase 01 — Docker Intro](#clase-01--docker-intro)
- [Clase 02 — Docker Aplicado](#clase-02--docker-aplicado)
- [Clase 03 — Procesos Fundamentos](#clase-03--procesos-fundamentos)
- [Clase 04 — Fork, Exec, Wait](#clase-04--fork-exec-wait)
- [Clase 05 — Pipes](#clase-05--pipes)
- [Clase 06 — Señales](#clase-06--señales)
- [Clase 07 — MMAP y Memoria Compartida](#clase-07--mmap-y-memoria-compartida)
- [Clase 08 — Multiprocessing Fundamentos](#clase-08--multiprocessing-fundamentos)
- [Clase 09 — Multiprocessing Avanzado](#clase-09--multiprocessing-avanzado)
- [Clase 10 — Threading](#clase-10--threading)
- [Clase 11 — Sincronización](#clase-11--sincronización)
- [Cheat Sheet Final](#cheat-sheet-final)

---

## Bloque 0 — Autónomo

### 0.1 argparse y getopt

#### Conceptos Clave

##### `sys.argv` — El nivel más bajo

`sys.argv` es una lista de strings que contiene los argumentos pasados al script de Python. El primer
elemento (`sys.argv[0]`) siempre es el nombre del script. **Todo elemento es un `str`**, sin
importar si el usuario pasó un número o un flag.

```python
# Si ejecutás: python script.py 42 --verbose
import sys
print(sys.argv)  # ['script.py', '42', '--verbose']
print(type(sys.argv[1]))  # <class 'str'> — NO es int
```

Parsear `sys.argv` a mano es propenso a errores porque hay que validar manualmente la cantidad de
argumentos, los tipos, manejar flags opcionales, generar mensajes de ayuda, y controlar errores.
En proyectos reales nunca se usa directamente.

##### `getopt` — Parser heredado de C

El módulo `getopt` sigue el estilo POSIX de C (`getopt(3)`). Parsea opciones cortas (`-v`) y
largas (`--verbose`) pero no genera ayuda automática, no valida tipos, y tiene una API confusa.

```python
import getopt, sys

opts, args = getopt.getopt(sys.argv[1:], "vt:", ["verbose", "timeout="])
# -v / --verbose: sin argumento (flag)
# -t / --timeout: requiere argumento (el ":" y "=" lo indican)
```

**No usar en proyectos nuevos.** Existe solo por compatibilidad histórica. `argparse` lo reemplaza
completamente.

##### `argparse` — El estándar moderno

`argparse` es el módulo estándar de Python para construir interfaces de línea de comandos. Genera
ayuda automática (`--help`), valida tipos, maneja errores, y soporta subcomandos.

**Argumentos posicionales vs opcionales:**

| Tipo | Sintaxis | Obligatorio | Ejemplo |
|------|----------|-------------|---------|
| Posicional | `add_argument('input')` | Sí (por defecto) | `script.py datos.csv` |
| Opcional | `add_argument('--timeout')` | No (por defecto) | `script.py --timeout 5` |

**Parámetros principales de `add_argument()`:**

| Parámetro | Qué hace | Ejemplo |
|-----------|----------|---------|
| `type` | Convierte el string a un tipo | `type=int` |
| `default` | Valor si no se pasa | `default=5` |
| `choices` | Restringe a un conjunto | `choices=['json', 'csv']` |
| `nargs` | Cantidad de valores | `nargs='+'` (uno o más) |
| `metavar` | Nombre en el help | `metavar='SECS'` |
| `dest` | Nombre del atributo | `dest='timeout_secs'` |
| `required` | Fuerza un opcional | `required=True` |
| `help` | Texto de ayuda | `help='Timeout in seconds'` |

**Acciones (`action`):**

| Action | Efecto |
|--------|--------|
| `store` | Almacena el valor (default) |
| `store_true` | Si se pasa, almacena `True` |
| `store_false` | Si se pasa, almacena `False` |
| `store_const` | Almacena un valor constante definido con `const=` |
| `count` | Cuenta cuántas veces aparece (`-vvv` → 3) |
| `append` | Acumula valores en una lista (`--tag a --tag b` → `['a','b']`) |

**`nargs` — Cantidad de valores:**

| Valor | Significado | Resultado |
|-------|-------------|-----------|
| `N` (int) | Exactamente N valores | Lista de N elementos |
| `'?'` | 0 o 1 valor | Valor o `default` |
| `'*'` | 0 o más | Lista (puede estar vacía) |
| `'+'` | 1 o más | Lista (error si vacía) |

**Grupos mutuamente excluyentes:**

```python
group = parser.add_mutually_exclusive_group()
group.add_argument('--json', action='store_true')
group.add_argument('--csv', action='store_true')
# El usuario puede pasar --json O --csv, pero no ambos
```

**Subcomandos (estilo `git commit`, `git push`):**

```python
subparsers = parser.add_subparsers(dest='command')
start_parser = subparsers.add_parser('start', help='Start the monitor')
start_parser.add_argument('--daemon', action='store_true')
stop_parser = subparsers.add_parser('stop', help='Stop the monitor')
```

**Manejo de errores:** Cuando el usuario pasa argumentos inválidos, `argparse` imprime un mensaje
de error y llama a `sys.exit(2)`, lanzando `SystemExit`. En tests o en aplicaciones que envuelven
al parser, hay que capturar esta excepción.

#### Ejemplo Completo

```python
import argparse

def build_parser():
    parser = argparse.ArgumentParser(
        description="Monitor de procesos del sistema",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ejemplo: %(prog)s --interval 2 --format json"
    )

    parser.add_argument(
        '--config', type=str, default='config.json',
        help='Path to the configuration file (default: config.json)'
    )
    parser.add_argument(
        '--interval', type=float, default=2.0,
        metavar='SECS', help='Refresh interval in seconds'
    )
    parser.add_argument(
        '--format', choices=['json', 'text', 'csv'],
        default='text', help='Output format'
    )
    parser.add_argument(
        '--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO', help='Logging verbosity'
    )
    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help='Increase verbosity (-v, -vv, -vvv)'
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument('--stdout', action='store_true', help='Print to stdout')
    output_group.add_argument('--output', type=str, metavar='FILE', help='Write to file')

    return parser

if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    print(f"Config: {args.config}")
    print(f"Interval: {args.interval}s")
    print(f"Verbose level: {args.verbose}")
```

#### Errores Típicos

**❌ Operar con `sys.argv` sin convertir tipos:**

```python
# MAL — sys.argv[1] es siempre str
timeout = sys.argv[1] + 10  # TypeError: can't add str and int

# BIEN — argparse convierte automáticamente
parser.add_argument('--timeout', type=int, default=10)
```

**❌ Usar `getopt` en proyectos nuevos:** No genera help, no valida tipos, API confusa. Usar
`argparse` siempre.

**❌ No manejar `SystemExit` en tests:** `argparse` llama a `sys.exit(2)` ante errores. Si estás
testeando el parser, envolvé en `try/except SystemExit`.

#### 📌 Conexión con tu TP1

Tu monitor de procesos usa `argparse` para toda la interfaz CLI: `--data-dir`, `--output-dir`,
`--config`, `--log-level`, `--timeout`, `--format`. Esto permite que el usuario configure el
comportamiento sin modificar código — exactamente el caso de uso para el que `argparse` fue diseñado.

#### Preguntas de Examen

1. **¿Cuál es la diferencia semántica entre un argumento posicional y uno opcional en `argparse`?**
   <details><summary>Respuesta</summary>
   Los argumentos posicionales son obligatorios y su significado depende de la posición en la que
   se pasan (ej: `script.py input.csv output.json`). Los opcionales comienzan con `-` o `--`, no son
   obligatorios (a menos que se use `required=True`), y su orden no importa. Los posicionales definen
   QUÉ procesar, los opcionales definen CÓMO procesarlo.
   </details>

2. **¿Qué ocurre internamente cuando un usuario pasa un flag inválido a un script que usa `argparse`?**
   <details><summary>Respuesta</summary>
   `argparse` imprime un mensaje de error descriptivo a `stderr`, muestra un resumen de uso, y llama
   a `parser.exit(2)`, que internamente ejecuta `sys.exit(2)`. Esto lanza una excepción `SystemExit`
   con código 2, terminando el proceso. El código 2 sigue la convención Unix para errores de uso.
   </details>

3. **Si definís `add_argument('-v', '--verbose', action='count', default=0)`, ¿qué valor tiene `args.verbose` si el usuario ejecuta `script.py -vvv`?**
   <details><summary>Respuesta</summary>
   El valor es `3`. La acción `count` incrementa el contador por cada aparición del flag. `-vvv` es
   equivalente a `-v -v -v`, resultando en 3 incrementos sobre el valor default de 0.
   </details>

4. **Diseñá un `add_argument` que acepte una lista de PIDs como enteros, con al menos 1 valor obligatorio.**
   <details><summary>Respuesta</summary>

   ```python
   parser.add_argument('pids', type=int, nargs='+', metavar='PID',
                        help='One or more process IDs to monitor')
   ```

   `nargs='+'` exige al menos un valor y los almacena como lista. `type=int` valida que cada valor
   sea un entero. Si el usuario pasa `script.py 123 456`, `args.pids` será `[123, 456]`.
   </details>

---

### 0.2 Filesystem Linux

#### Conceptos Clave

##### Filosofía Unix: "Everything is a File"

En Unix/Linux, prácticamente todo se representa como un archivo: archivos regulares, directorios,
dispositivos de hardware, sockets de red, pipes. Esta abstracción unificada permite usar las mismas
operaciones (`open`, `read`, `write`, `close`) para interactuar con recursos muy diferentes.

##### FHS — Filesystem Hierarchy Standard

El FHS define la estructura de directorios estándar en sistemas Linux:

| Directorio | Contenido | Ejemplo |
|------------|-----------|---------|
| `/` | Raíz del sistema completo | — |
| `/bin` | Binarios esenciales del sistema | `ls`, `cp`, `cat`, `bash` |
| `/sbin` | Binarios de administración (root) | `iptables`, `fdisk`, `mount` |
| `/etc` | Archivos de configuración del sistema | `/etc/passwd`, `/etc/nginx/` |
| `/home` | Directorios personales de usuarios | `/home/rufda/` |
| `/var` | Datos variables (logs, caches, mail) | `/var/log/syslog` |
| `/tmp` | Archivos temporales (se borran al reiniciar) | Archivos de sesión |
| `/usr` | Programas y datos de usuario (jerarquía secundaria) | `/usr/bin/`, `/usr/lib/` |
| `/dev` | Archivos de dispositivos (block, char) | `/dev/sda`, `/dev/null`, `/dev/tty` |
| `/proc` | **Filesystem virtual del kernel** — info de procesos y sistema | `/proc/1/status` |
| `/sys` | sysfs — información de hardware y drivers | `/sys/class/net/` |
| `/opt` | Software opcional/terceros | `/opt/google/chrome/` |
| `/lib` | Bibliotecas compartidas esenciales | `libc.so`, `libpthread.so` |

##### `/proc` — El filesystem virtual (CRÍTICO para el TP1)

`/proc` no existe en disco. Es un filesystem virtual que el kernel genera en memoria en tiempo real.
Cuando leés `/proc/[pid]/stat`, el kernel construye los datos en ese momento, por eso los archivos
muestran tamaño cero en `ls -l`.

Cada proceso tiene su directorio en `/proc/[pid]/`:

| Archivo | Contenido | Formato |
|---------|-----------|---------|
| `stat` | Estado compacto del proceso | Línea única, campos separados por espacio |
| `status` | Estado legible | Clave: Valor, uno por línea |
| `cmdline` | Línea de comandos original | Argumentos separados por `\0` |
| `maps` | Mapeados de memoria | Líneas con rangos de direcciones |
| `fd/` | Directorio con file descriptors abiertos | Symlinks a recursos |
| `task/` | Subdirectorio por cada thread (LWP) | `/proc/[pid]/task/[tid]/` |

Archivos globales del sistema:

| Archivo | Contenido |
|---------|-----------|
| `/proc/stat` | Estadísticas de CPU del sistema (user, nice, system, idle, etc.) |
| `/proc/meminfo` | Información de memoria (MemTotal, MemFree, Buffers, Cached) |
| `/proc/loadavg` | Load average a 1, 5 y 15 minutos |
| `/proc/uptime` | Tiempo de actividad del sistema |

##### Inodos

Un inodo es la estructura de datos en el filesystem que almacena los **metadatos** de un archivo:

- Tipo de archivo (regular, directorio, symlink, device, socket, pipe)
- Permisos (rwxrwxrwx)
- UID y GID del propietario
- Tamaño en bytes
- Timestamps (atime, mtime, ctime)
- Contador de hard links
- Punteros a los bloques de datos en disco

**El nombre del archivo NO está en el inodo.** Los nombres viven en el directorio padre, que es una
tabla que mapea nombres a números de inodo.

Podés ver el inodo de un archivo con `ls -i`:

```bash
ls -i archivo.txt
# 1234567 archivo.txt
```

##### Hard Links vs Symbolic Links

| Característica | Hard Link | Symbolic Link (Symlink) |
|----------------|-----------|------------------------|
| Apunta a | El mismo inodo | Una ruta (path) |
| Cruza filesystems | No | Sí |
| Enlaza directorios | No (salvo `.` y `..`) | Sí |
| Si el original se borra | El archivo sobrevive (mientras haya ≥1 link) | Queda roto (dangling) |
| Creación | `ln original link` | `ln -s original link` |
| Verifica existencia | `stat` muestra link count | `readlink -f` resuelve la ruta |

```bash
# Hard link — mismo inodo, dos nombres
ln archivo.txt hardlink.txt
ls -li  # Ambos tienen el mismo número de inodo

# Symlink — apunta a la ruta, no al inodo
ln -s archivo.txt symlink.txt
ls -l  # symlink.txt -> archivo.txt
```

##### APIs de Python para filesystem

**`os.path` — funcional:**

```python
import os.path
os.path.join('/proc', str(pid), 'stat')  # '/proc/123/stat'
os.path.exists('/proc/1/status')          # True
os.path.isfile('/proc/cpuinfo')           # True
os.path.isdir('/proc/1')                  # True
os.path.getsize('/etc/passwd')            # Tamaño en bytes
os.path.abspath('.')                      # Ruta absoluta
```

**`pathlib.Path` — orientado a objetos (preferido):**

```python
from pathlib import Path

proc = Path('/proc')
stat_file = proc / str(pid) / 'stat'        # Operador / para concatenar
content = stat_file.read_text()              # Lee todo el archivo
for child in proc.iterdir():                 # Lista directorio
    if child.is_dir() and child.name.isdigit():
        print(f"PID: {child.name}")
list(Path('/etc').glob('*.conf'))            # Glob en un nivel
list(Path('.').rglob('*.py'))                # Glob recursivo
```

**`os.walk()` — recorrido recursivo:**

```python
import os
for dirpath, dirnames, filenames in os.walk('/var/log'):
    for fname in filenames:
        full_path = os.path.join(dirpath, fname)
        print(full_path)
```

**`shutil` — operaciones de alto nivel:**

```python
import shutil
shutil.copy2('src.txt', 'dst.txt')   # Copia preservando metadatos
shutil.move('old.txt', 'new.txt')    # Mover/renombrar
shutil.rmtree('/tmp/mi_dir')         # Borrar directorio recursivamente
```

#### Ejemplo: Listar procesos leyendo /proc

```python
from pathlib import Path
import os

def list_processes():
    """List all running processes by reading /proc directly."""
    proc = Path('/proc')
    processes = []

    for entry in proc.iterdir():
        if not entry.is_dir() or not entry.name.isdigit():
            continue

        pid = int(entry.name)
        try:
            # Read command line (null-separated arguments)
            cmdline = (entry / 'cmdline').read_bytes()
            cmd = cmdline.replace(b'\x00', b' ').decode().strip()

            # Read status for process name and state
            status_text = (entry / 'status').read_text()
            name = state = ''
            for line in status_text.splitlines():
                if line.startswith('Name:'):
                    name = line.split('\t', 1)[1]
                elif line.startswith('State:'):
                    state = line.split('\t', 1)[1]

            processes.append({
                'pid': pid,
                'name': name,
                'state': state,
                'cmdline': cmd or f'[{name}]'
            })
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            # Process may have exited between listing and reading
            continue

    return sorted(processes, key=lambda p: p['pid'])
```

#### Errores Típicos

**❌ Concatenar rutas con strings:**

```python
# MAL — se rompe con distintos OS, olvida separadores
path = '/proc/' + str(pid) + '/stat'

# BIEN — usa pathlib o os.path.join
path = Path('/proc') / str(pid) / 'stat'
path = os.path.join('/proc', str(pid), 'stat')
```

**❌ Confundir hard links con symlinks:**

Un hard link **es** el archivo (otro nombre para el mismo inodo). Un symlink **apunta** a un nombre
de archivo. Si borrás el original, el hard link sigue funcionando, el symlink queda roto.

**❌ Usar `shutil.rmtree()` sin cuidado:** Borra todo recursivamente sin confirmación. Si no tenés
permisos sobre algún archivo interno, falla a mitad del camino dejando el directorio parcialmente
borrado. Usar `shutil.rmtree(path, ignore_errors=True)` o manejar con `onerror`.

**❌ No manejar procesos efímeros al leer `/proc`:** Un proceso puede terminar entre que lo listás
en `/proc` y que intentás leer su archivo. Siempre envolver en `try/except (FileNotFoundError,
ProcessLookupError, PermissionError)`.

#### 📌 Conexión con tu TP1

TODO tu TP1 se basa en leer `/proc`. El módulo `procfs.py` lee directamente `stat`, `status`,
`cmdline`, `maps` y `fd/` de cada proceso. El analizador de threads recorre `/proc/[pid]/task/[tid]/`
para inspeccionar LWPs. El analizador de sistema lee `/proc/stat`, `/proc/meminfo` y
`/proc/loadavg` para métricas globales. Tu código maneja correctamente los procesos efímeros con
bloques try/except.

#### Preguntas de Examen

1. **¿Por qué los archivos dentro de `/proc` muestran tamaño 0 bytes al hacer `ls -l`, pero al leerlos con `cat` producen contenido?**
   <details><summary>Respuesta</summary>
   Porque `/proc` es un filesystem virtual en memoria generado por el kernel. Los archivos no existen
   en disco — el kernel los construye dinámicamente al momento de la lectura. Como no tienen bloques
   de datos asignados en disco, `stat()` reporta tamaño 0, pero la operación `read()` dispara la
   generación del contenido en el kernel.
   </details>

2. **Explicá la diferencia entre un hard link y un symlink. ¿Qué pasa con cada uno si se elimina el archivo original?**
   <details><summary>Respuesta</summary>
   Un hard link es otro nombre (entrada de directorio) que apunta al mismo inodo del archivo original.
   Ambos nombres son equivalentes — no hay "original" y "copia". Si se borra uno, el otro sigue
   funcionando porque el inodo persiste mientras su contador de links sea ≥ 1.

   Un symlink apunta a la **ruta** del archivo, no al inodo. Si se borra el archivo al que apunta,
   el symlink queda "colgando" (dangling) y al intentar leerlo se obtiene un error `FileNotFoundError`.
   </details>

3. **En Python, ¿por qué se recomienda usar `pathlib.Path` sobre `os.path.join` para manipular rutas?**
   <details><summary>Respuesta</summary>
   `pathlib` ofrece una interfaz orientada a objetos donde las rutas son objetos con métodos
   (`read_text()`, `iterdir()`, `glob()`) y operadores sobrecargados (`/` para concatenar). Esto
   produce código más legible y menos propenso a errores que encadenar funciones de `os.path`.
   Además, `pathlib` es cross-platform por defecto.
   </details>

4. **Al recorrer `/proc` para listar procesos, ¿por qué es necesario envolver las lecturas en `try/except`?**
   <details><summary>Respuesta</summary>
   Porque existe una condición de carrera inherente: un proceso puede terminar entre el momento en
   que lo descubrimos (listando `/proc`) y el momento en que intentamos leer sus archivos
   (`/proc/[pid]/stat`). Esto lanza `FileNotFoundError` o `ProcessLookupError`. También puede
   haber `PermissionError` si el proceso pertenece a otro usuario y no tenemos privilegios.
   </details>

---

### 0.3 Git

#### Conceptos Clave

##### Modelo interno de Git

Git NO almacena diffs entre versiones. Almacena **snapshots** completos del proyecto, organizados
en cuatro tipos de objetos internos:

| Objeto | Qué almacena |
|--------|-------------|
| **Blob** | Contenido de un archivo (sin nombre ni permisos) |
| **Tree** | Un directorio: lista de (nombre, permisos, referencia a blob o tree) |
| **Commit** | Puntero a un tree + autor + fecha + mensaje + padre(s) |
| **Tag** | Referencia con nombre a un commit (anotado: incluye mensaje y firma) |

Todo se identifica por su hash SHA-1 (40 caracteres hex). Esto hace a Git un **almacenamiento
direccionado por contenido**: si dos archivos tienen el mismo contenido, se almacenan una sola vez.

##### Las 3 áreas de trabajo

```
Working Directory  ──git add──>  Staging Area (Index)  ──git commit──>  Repository (.git)
    (archivos)                     (preparados)                          (historial)
```

1. **Working Directory**: tus archivos editables en disco.
2. **Staging Area (Index)**: una "foto" preparada de lo que irá en el próximo commit. Permite
   hacer commits selectivos (parte de los cambios, no todos).
3. **Repository (`.git/`)**: la base de datos completa de objetos y referencias.

##### Branching y Merging

Una rama en Git es simplemente un **puntero** a un commit. Crear una rama es instantáneo (solo crea
un puntero). `HEAD` apunta a la rama activa.

**Fast-forward merge:** Cuando la rama base no avanzó desde que se creó la feature branch, Git
simplemente mueve el puntero de la rama base hacia adelante. No crea commit de merge.

```
main: A → B → C
                  \
feature:           D → E
                        ↑ (merge = mover main a E)
```

**3-way merge:** Cuando ambas ramas divergieron, Git crea un nuevo commit de merge que tiene dos
padres.

```
main: A → B → C → F (merge commit, padres: C y E)
                \   /
feature:         D → E
```

**Conflictos:** Cuando ambas ramas modificaron las mismas líneas, Git marca el conflicto en el
archivo y el usuario debe resolverlo manualmente.

##### Rebase vs Merge

| Aspecto | Merge | Rebase |
|---------|-------|--------|
| Historia | Preserva la ramificación (no-lineal) | Re-escribe como historia lineal |
| Commits | Crea un commit de merge extra | Recrea los commits sobre la nueva base |
| Riesgo | Seguro (no cambia historia existente) | Peligroso si se re-escribe historia compartida |
| Uso | Integrar ramas públicas | Limpiar historia local antes de merge |

**Regla de oro:** Nunca hacer `rebase` de commits que ya se pushearon a un remoto compartido.

##### Comandos esenciales

**Inspección:**
```bash
git status                         # Estado actual
git diff                           # Cambios no staged
git diff --staged                  # Cambios staged (próximo commit)
git log --oneline --graph --all    # Historia visual
```

**Staging y commits:**
```bash
git add archivo.py                 # Agregar archivo al staging
git add -p                         # Staging interactivo (por hunks)
git commit -m "feat: add monitor"  # Commit con mensaje
git commit --amend                 # Modificar último commit
```

**Branching:**
```bash
git branch                         # Listar ramas
git checkout -b feature/monitor    # Crear rama y cambiar a ella
git switch -c feature/monitor      # Equivalente moderno
git merge feature/monitor          # Fusionar rama
git branch -d feature/monitor      # Borrar rama fusionada
```

**Deshacer:**
```bash
git restore archivo.py             # Descartar cambios en working dir
git restore --staged archivo.py    # Quitar del staging
git reset --soft HEAD~1            # Deshacer commit, mantener staging
git reset --mixed HEAD~1           # Deshacer commit + staging (default)
git reset --hard HEAD~1            # BORRAR todo (commit + staging + archivos)
git stash                          # Guardar cambios temporalmente
git stash pop                      # Restaurar cambios guardados
git reflog                         # Ver TODOS los movimientos de HEAD (red de seguridad)
git cherry-pick <hash>             # Copiar un commit específico a la rama actual
```

##### `git reset` — Los 3 modos

| Modo | Commit | Staging | Working Dir | Uso |
|------|--------|---------|-------------|-----|
| `--soft` | ❌ Deshace | ✅ Mantiene | ✅ Mantiene | Rehacer el mensaje del commit |
| `--mixed` | ❌ Deshace | ❌ Deshace | ✅ Mantiene | Re-seleccionar qué va en staging |
| `--hard` | ❌ Deshace | ❌ Deshace | ❌ **BORRA** | Descartar todo (peligroso) |

##### Conventional Commits

Estándar para mensajes de commit estructurados:

```
<tipo>(<alcance>): <descripción>

feat: add process monitor TUI
fix: handle zombie process detection
docs: update README with Docker instructions
style: format code with black
refactor: extract /proc parser to separate module
test: add unit tests for signal handler
chore: update dependencies
```

#### Errores Típicos

**❌ `git reset --hard` sin respaldo:** Destruye cambios de forma aparentemente irrecuperable.
Aunque `git reflog` puede salvar la situación por 30 días, es mejor hacer `git stash` antes.

**❌ `git push --force` en ramas públicas:** Re-escribe la historia del remoto, rompiendo el
trabajo de cualquier otro desarrollador que haya basado sus cambios en la historia anterior.

**❌ Subir credenciales al repositorio:** Una vez que un secreto está en la historia de Git,
borrar el archivo no alcanza (queda en commits anteriores). Hay que usar herramientas como
`git filter-branch` o `BFG Repo-Cleaner` para purgarlo. Prevenir con `.gitignore`.

**❌ Ignorar el staging area:** Hacer `git add .` + `git commit` indiscriminadamente en vez de
usar `git add -p` para seleccionar cambios lógicamente coherentes por commit.

#### Preguntas de Examen

1. **¿Qué diferencia hay entre `git merge` y `git rebase`? ¿Cuándo usarías cada uno?**
   <details><summary>Respuesta</summary>
   `merge` integra ramas creando un nuevo commit de fusión que tiene dos padres, preservando la
   historia no lineal original. `rebase` toma los commits de tu rama y los recrea sobre la punta
   de otra rama, produciendo una historia lineal.

   Se usa `merge` para integrar ramas públicas/compartidas (seguro, no altera historia). Se usa
   `rebase` para limpiar la historia de una rama local antes de fusionarla, evitando commits de
   merge innecesarios (más limpio pero peligroso si la rama ya fue compartida).
   </details>

2. **Hiciste `git reset --hard HEAD~3` por error. ¿Cómo recuperás los 3 commits perdidos?**
   <details><summary>Respuesta</summary>
   Usar `git reflog` para ver el historial de todos los movimientos de HEAD. Encontrar el hash del
   commit anterior al reset, y ejecutar `git reset --hard <hash>` para restaurarlo. El reflog
   retiene estas referencias por 30 días por defecto, así que hay que actuar rápido.
   </details>

3. **Explicá las 3 áreas de trabajo de Git y el flujo de un cambio desde la edición hasta que queda en la historia.**
   <details><summary>Respuesta</summary>
   1. **Working Directory**: editás un archivo. Git detecta que hay diferencias vs el último commit.
   2. **Staging Area (Index)**: con `git add` seleccionás qué cambios incluir en el próximo commit.
      Esto permite hacer commits parciales y lógicamente coherentes.
   3. **Repository (.git/)**: con `git commit` los cambios staged se convierten en un commit
      (objeto blob + tree + commit) almacenado permanentemente en la base de datos de Git.
   </details>

4. **¿Qué es el Staging Area y qué problema resuelve que no tendríamos si los commits tomaran todo directamente del Working Directory?**
   <details><summary>Respuesta</summary>
   El Staging Area es una capa intermedia que permite al desarrollador seleccionar exactamente qué
   cambios incluir en cada commit, aunque haya múltiples archivos modificados. Sin ella, cada commit
   incluiría TODOS los cambios actuales, forzando a hacer commits "todo o nada". El staging permite
   crear commits atómicos y lógicamente coherentes (ej: un commit para el bugfix, otro para el
   refactor, aunque ambos cambios coexistan en el working directory).
   </details>

---

### 0.4 Python Avanzado

#### Conceptos Clave

##### Generadores

Un generador es una función que produce una secuencia de valores bajo demanda, pausando su
ejecución entre cada valor con `yield`. A diferencia de una función normal que computa todo y
retorna una lista, un generador aplica **evaluación perezosa (lazy evaluation)**: solo computa el
siguiente valor cuando se lo piden con `next()`.

```python
# Una lista de 10 millones de elementos consume ~400MB de RAM
numeros = [x ** 2 for x in range(10_000_000)]

# Un generador consume ~100 bytes sin importar el tamaño
numeros = (x ** 2 for x in range(10_000_000))
```

**Función generadora vs función normal:**

```python
def mi_generador(n):
    """Genera cuadrados de 0 a n-1, uno a la vez."""
    for i in range(n):
        print(f"  Computando {i}²...")  # Se ejecuta solo cuando piden el valor
        yield i ** 2
    # Al llegar aquí, lanza StopIteration automáticamente

gen = mi_generador(3)
print(next(gen))  # Computando 0²... → 0
print(next(gen))  # Computando 1²... → 1
# El generador está PAUSADO entre llamadas, conservando su estado local
```

**`yield from` — delegación:**

```python
def generador_compuesto():
    yield from range(3)       # Delega a otro iterable
    yield from [10, 20, 30]   # Encadena múltiples fuentes

list(generador_compuesto())  # [0, 1, 2, 10, 20, 30]
```

**`send()`, `throw()`, `close()` — protocolo coroutine:**

```python
def acumulador():
    total = 0
    while True:
        valor = yield total  # Recibe valor vía send(), retorna total
        if valor is None:
            break
        total += valor

gen = acumulador()
next(gen)           # Inicializa (avanza hasta el primer yield) → 0
gen.send(10)        # Envía 10, recibe total → 10
gen.send(20)        # Envía 20, recibe total → 30
gen.close()         # Termina el generador (lanza GeneratorExit internamente)
```

**Patrón pipeline — encadenando generadores:**

```python
def leer_lineas(path):
    with open(path) as f:
        for line in f:
            yield line.strip()

def filtrar_errores(lineas):
    for linea in lineas:
        if 'ERROR' in linea:
            yield linea

def extraer_timestamp(lineas):
    for linea in lineas:
        yield linea.split()[0]

# Pipeline: cada generador procesa un item a la vez, sin cargar todo en memoria
timestamps = extraer_timestamp(filtrar_errores(leer_lineas('/var/log/app.log')))
for ts in timestamps:
    print(ts)
```

##### Decoradores

Un decorador es una función que toma una función, le agrega comportamiento, y devuelve una nueva
función. Son posibles porque en Python las funciones son **objetos de primera clase** (se pueden
pasar como argumentos, retornar, y asignar a variables).

**Decorador simple:**

```python
import functools
import time

def timer(func):
    @functools.wraps(func)  # Preserva nombre, docstring y metadata de func
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"{func.__name__} took {elapsed:.4f}s")
        return result
    return wrapper

@timer
def heavy_computation(n):
    """Compute sum of squares."""
    return sum(i ** 2 for i in range(n))

# @timer es azúcar sintáctico para: heavy_computation = timer(heavy_computation)
```

**Decorador con argumentos (triple anidamiento):**

```python
def retry(max_attempts=3, delay=1.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    print(f"Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(max_attempts=5, delay=2.0)
def fetch_data(url):
    ...
```

**Stacking — orden de ejecución:**

```python
@decorator_a
@decorator_b
def func():
    ...

# Equivale a: func = decorator_a(decorator_b(func))
# Al llamar func(): decorator_a wraps → decorator_b wraps → func original
```

##### Context Managers

Los context managers garantizan que un recurso se limpie correctamente, incluso si ocurre una
excepción. Se usan con la sentencia `with`.

**Protocolo:**

```python
class DatabaseConnection:
    def __enter__(self):
        self.conn = connect_to_db()
        return self.conn  # Lo que retorna __enter__ se asigna al "as"

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()  # SIEMPRE se ejecuta, haya o no excepción
        # Si retorna True, la excepción se suprime
        # Si retorna False/None, la excepción se propaga
        return False

with DatabaseConnection() as conn:
    conn.execute("SELECT ...")
# conn.close() se llamó automáticamente al salir del bloque
```

**`@contextmanager` — atajo con generadores:**

```python
from contextlib import contextmanager

@contextmanager
def open_proc_file(pid, filename):
    """Safely open a /proc file, handling disappearing processes."""
    path = f"/proc/{pid}/{filename}"
    f = None
    try:
        f = open(path, 'r')
        yield f
    except FileNotFoundError:
        yield None  # Process disappeared
    finally:
        if f:
            f.close()

with open_proc_file(1234, 'status') as f:
    if f:
        content = f.read()
```

**`ExitStack` — para cantidad variable de recursos:**

```python
from contextlib import ExitStack

with ExitStack() as stack:
    files = [stack.enter_context(open(f)) for f in file_list]
    # Todos los archivos se cierran al salir, incluso si uno falla
```

##### Closures

Una closure es una función interna que **captura** variables del scope de la función que la envuelve.
La función interna "recuerda" esas variables incluso después de que la función externa haya terminado.

```python
def make_counter(start=0):
    count = start
    def increment():
        nonlocal count  # Permite MODIFICAR la variable capturada
        count += 1
        return count
    return increment

counter = make_counter(10)
print(counter())  # 11
print(counter())  # 12
# La variable count vive en la closure, no es global
```

**`nonlocal`:** Sin `nonlocal`, asignar a `count` dentro de `increment` crearía una variable local
nueva en vez de modificar la capturada. `nonlocal` le dice a Python que busque en el scope envolvente.

#### Errores Típicos

**❌ Argumentos por defecto mutables:**

```python
# MAL — la lista es la MISMA entre todas las llamadas
def add_item(item, lista=[]):
    lista.append(item)
    return lista

add_item(1)  # [1]
add_item(2)  # [1, 2] ← ¡acumula!

# BIEN — usar None como sentinel
def add_item(item, lista=None):
    if lista is None:
        lista = []
    lista.append(item)
    return lista
```

**❌ Olvidar `@functools.wraps`:**

```python
# Sin @wraps, el decorador oculta la identidad de la función:
print(decorated_func.__name__)  # 'wrapper' (debería ser 'original_name')
print(decorated_func.__doc__)   # None (perdió el docstring)
help(decorated_func)            # Muestra info del wrapper, no de la función
```

**❌ Consumir un generador dos veces:**

```python
gen = (x for x in range(5))
list(gen)  # [0, 1, 2, 3, 4]
list(gen)  # [] ← ¡vacío! El generador se agotó
# Solución: recrear el generador o usar una función generadora
```

**❌ Late binding en closures con loops:**

```python
# MAL — todas las funciones capturan la MISMA variable i
funcs = [lambda: i for i in range(3)]
print([f() for f in funcs])  # [2, 2, 2] ← i vale 2 al final del loop

# BIEN — capturar con argumento por defecto (early binding)
funcs = [lambda i=i: i for i in range(3)]
print([f() for f in funcs])  # [0, 1, 2]
```

#### Preguntas de Examen

1. **¿Por qué un generador es más eficiente en memoria que una lista para procesar 10 millones de registros?**
   <details><summary>Respuesta</summary>
   Un generador aplica evaluación perezosa: solo mantiene en memoria un elemento a la vez (el actual
   que fue `yield`-eado), más el estado local de la función (variables, punto de ejecución). Una lista
   materializa los 10 millones de elementos simultáneamente en memoria. Para un pipeline de
   procesamiento, el generador usa O(1) de memoria vs O(n) de la lista.
   </details>

2. **¿Para qué sirve `functools.wraps` y qué pasa si no lo usás en un decorador?**
   <details><summary>Respuesta</summary>
   `@functools.wraps(func)` copia el `__name__`, `__doc__`, `__module__` y `__qualname__` de la
   función original al wrapper. Sin `@wraps`, la función decorada pierde su identidad: `__name__`
   muestra `'wrapper'`, el docstring se pierde, y herramientas como `help()`, debuggers e
   introspección muestran información incorrecta.
   </details>

3. **¿Qué hace `__exit__` si retorna `True`? ¿Y si retorna `False`?**
   <details><summary>Respuesta</summary>
   Si `__exit__` retorna `True`, la excepción que ocurrió dentro del bloque `with` se **suprime**
   (no se propaga). Si retorna `False` o `None`, la excepción se propaga normalmente hacia arriba.
   `__exit__` recibe tres argumentos (tipo de excepción, valor, traceback), que son `None` si no
   hubo excepción. En todos los casos, el código de limpieza en `__exit__` se ejecuta.
   </details>

4. **Explicá el problema de late binding en closures dentro de loops y cómo solucionarlo.**
   <details><summary>Respuesta</summary>
   Cuando creás funciones (lambdas o closures) dentro de un loop, todas capturan una **referencia**
   a la misma variable del loop, no su valor. Cuando finalmente se invocan, leen el valor final de
   esa variable. La solución es forzar un "early binding" usando un argumento por defecto
   (`lambda i=i: i`) que evalúa la variable al momento de la definición y la copia como parámetro
   local de la lambda.
   </details>

---

## Clase 01 — Docker Intro

#### Conceptos Clave

##### Virtualización: VMs vs Contenedores

| Aspecto | Máquina Virtual | Contenedor |
|---------|----------------|------------|
| Aislamiento | SO huésped completo sobre hipervisor | Procesos aislados sobre el kernel del host |
| Tamaño | GB (incluye SO completo) | MB (solo app + dependencias) |
| Arranque | Minutos | Segundos |
| Overhead | Alto (emulación de hardware) | Mínimo (nativo) |
| Tecnología | Hipervisor (KVM, VirtualBox, Hyper-V) | Namespaces + cgroups del kernel Linux |

**Namespaces** — aislamiento de recursos:

| Namespace | Qué aísla |
|-----------|-----------|
| PID | Tabla de procesos (el contenedor ve sus propios PIDs) |
| NET | Interfaces de red, puertos, tablas de ruteo |
| MNT | Puntos de montaje del filesystem |
| UTS | Hostname y domainname |
| IPC | Colas de mensajes, semáforos, shared memory |
| USER | UIDs y GIDs |

**cgroups** — control de recursos: limitan CPU, memoria, I/O de disco, y red que un grupo de
procesos puede usar.

##### Arquitectura de Docker

```
Docker CLI ──REST API──> Docker Daemon (dockerd) ──> containerd ──> runc ──> Container
 (cliente)                  (servidor)                                        (proceso)
```

El usuario interactúa con el CLI. El daemon gestiona imágenes, contenedores, redes y volúmenes.
`containerd` maneja el ciclo de vida de los contenedores. `runc` ejecuta el contenedor usando
las primitivas del kernel (namespaces, cgroups).

##### Imágenes vs Contenedores

- **Imagen**: plantilla de solo lectura compuesta por capas (OverlayFS). Cada instrucción del
  Dockerfile crea una capa. Las capas se cachean y reutilizan entre imágenes.
- **Contenedor**: una instancia en ejecución de una imagen. Agrega una capa de lectura-escritura
  sobre las capas de la imagen. Cuando el contenedor se destruye, esta capa se pierde.

Analogía OOP: la imagen es la **clase**, el contenedor es el **objeto** (instancia).

##### Instrucciones del Dockerfile

| Instrucción | Qué hace | Ejemplo |
|-------------|----------|---------|
| `FROM` | Imagen base | `FROM python:3.11-slim` |
| `WORKDIR` | Directorio de trabajo dentro del contenedor | `WORKDIR /app` |
| `COPY` | Copia archivos del host al contenedor | `COPY requirements.txt .` |
| `ADD` | Como COPY pero extrae tars y soporta URLs | `ADD app.tar.gz /app/` |
| `RUN` | Ejecuta comando y crea una capa | `RUN pip install -r requirements.txt` |
| `CMD` | Comando por defecto (sobreescribible) | `CMD ["python", "app.py"]` |
| `ENTRYPOINT` | Ejecutable principal (fijo) | `ENTRYPOINT ["python"]` |
| `EXPOSE` | Documenta puertos (NO los publica) | `EXPOSE 8080` |
| `ENV` | Variable de entorno (persiste en runtime) | `ENV PYTHONUNBUFFERED=1` |
| `ARG` | Variable de entorno (solo build-time) | `ARG VERSION=1.0` |
| `VOLUME` | Declara punto de montaje | `VOLUME /data` |

**CMD vs ENTRYPOINT — la diferencia clave:**

```dockerfile
# Solo CMD — el usuario puede sobreescribir todo:
CMD ["python", "app.py"]
# docker run mi-imagen              → python app.py
# docker run mi-imagen bash         → bash (CMD sobreescrito)

# ENTRYPOINT + CMD — CMD se vuelve argumento de ENTRYPOINT:
ENTRYPOINT ["python"]
CMD ["app.py"]
# docker run mi-imagen              → python app.py
# docker run mi-imagen test.py      → python test.py (solo CMD sobreescrito)
```

**Shell form vs Exec form:**

```dockerfile
# Shell form — se ejecuta como /bin/sh -c "..."
CMD python app.py

# Exec form — se ejecuta directamente (PREFERIDO)
CMD ["python", "app.py"]
# No pasa por shell, el proceso es PID 1, recibe señales correctamente
```

##### Comandos Docker esenciales

```bash
# Construcción
docker build -t mi-app:1.0 .                  # Construir imagen
docker build -t mi-app:1.0 -f other/Dockerfile . # Dockerfile alternativo

# Ejecución
docker run mi-app                              # Ejecutar y salir
docker run -d --name monitor mi-app            # Background (detached)
docker run -it mi-app bash                     # Interactivo con TTY
docker run --rm mi-app                         # Auto-borrar al terminar
docker run -p 8080:80 mi-app                   # Mapear puerto host:container
docker run -v /host/data:/app/data mi-app      # Montar directorio

# Inspección
docker ps                                      # Contenedores corriendo
docker ps -a                                   # Todos (incluyendo parados)
docker logs -f my-container                    # Logs en tiempo real
docker exec -it my-container bash              # Abrir shell en contenedor activo
docker inspect my-container                    # JSON completo del contenedor

# Limpieza
docker stop my-container                       # Detener (SIGTERM → 10s → SIGKILL)
docker rm my-container                         # Eliminar contenedor parado
docker rmi mi-app:1.0                          # Eliminar imagen
docker system prune -a                         # Limpiar todo lo no usado
```

#### Ejemplo Completo: Dockerfile del TP1

```dockerfile
FROM python:3.11-slim

# TERM needed for curses, PYTHONUNBUFFERED for real-time log output
ENV TERM=xterm-256color
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first — leverages layer caching
# If requirements.txt hasn't changed, pip install is cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code (changes more frequently → last layer)
COPY src/ ./src/
COPY config.json .

CMD ["python", "src/main.py"]
```

#### Errores Típicos

**❌ Confundir CMD con ENTRYPOINT:** CMD define el comando por defecto pero se sobreescribe
fácilmente. ENTRYPOINT define el ejecutable principal. Si querés un contenedor que siempre ejecute
Python pero con distintos scripts como argumento, usá ENTRYPOINT para Python y CMD para el script.

**❌ No limpiar cachés en la misma capa:**

```dockerfile
# MAL — la caché queda en una capa intermedia, inflando la imagen
RUN apt-get update
RUN apt-get install -y gcc
RUN apt-get clean

# BIEN — todo en un RUN, caché limpiada antes de consolidar la capa
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
```

**❌ No aprovechar el cache de capas:** Copiar todo el código antes de instalar dependencias invalida
la caché de `pip install` con cada cambio de código. Copiar `requirements.txt` primero y luego
el código.

**❌ Olvidar `.dockerignore`:** Sin él, `COPY . .` copia `.git/`, `__pycache__/`, `node_modules/`
y otros directorios pesados e innecesarios a la imagen.

#### 📌 Conexión con tu TP1

Tu `Dockerfile` usa `python:3.11-slim` como base y configura `TERM=xterm-256color` (necesario para
que `curses` funcione correctamente) y `PYTHONUNBUFFERED=1` (para que los logs se impriman en
tiempo real sin buffering). Sin estas variables de entorno, la TUI no se renderizaría correctamente.

#### Preguntas de Examen

1. **¿Qué dos mecanismos del kernel Linux permiten el aislamiento de los contenedores? Explicá qué aporta cada uno.**
   <details><summary>Respuesta</summary>
   **Namespaces**: aíslan la visibilidad de los recursos del sistema. Cada contenedor tiene su propia
   tabla de procesos (PID namespace), interfaces de red (NET namespace), puntos de montaje (MNT
   namespace), etc. El contenedor no puede ver ni interferir con los recursos de otros contenedores
   o del host.

   **cgroups (control groups)**: limitan la CANTIDAD de recursos que un contenedor puede consumir.
   Permiten establecer límites de CPU, memoria RAM, I/O de disco, y ancho de banda de red. Sin
   cgroups, un contenedor podría consumir todos los recursos del host.
   </details>

2. **¿Por qué se recomienda usar la exec form `["python", "app.py"]` en vez de la shell form `python app.py` en un Dockerfile?**
   <details><summary>Respuesta</summary>
   La shell form ejecuta el comando como argumento de `/bin/sh -c`, lo que significa que el proceso
   de la aplicación no es PID 1 dentro del contenedor (PID 1 es el shell). Esto causa que las
   señales como SIGTERM (usadas por `docker stop`) lleguen al shell y no a la aplicación, impidiendo
   un graceful shutdown. La exec form ejecuta el proceso directamente como PID 1, recibiendo las
   señales correctamente.
   </details>

3. **Explicá por qué el orden de las instrucciones en un Dockerfile afecta la velocidad de build.**
   <details><summary>Respuesta</summary>
   Docker cachea cada capa. Si una instrucción cambia, todas las capas posteriores se invalidan y
   reconstruyen. Por eso se colocan primero las instrucciones que cambian menos frecuentemente
   (ej: `COPY requirements.txt` + `RUN pip install`) y al final las que cambian más (ej: `COPY . .`).
   Así, un cambio en el código no fuerza la re-instalación de dependencias.
   </details>

4. **¿Cuál es la diferencia entre una imagen y un contenedor Docker?**
   <details><summary>Respuesta</summary>
   Una imagen es una plantilla inmutable de solo lectura compuesta por capas superpuestas (filesystem
   layered). Es como una clase en OOP. Un contenedor es una instancia en ejecución de esa imagen que
   agrega una capa superior de lectura-escritura temporal. Cuando el contenedor se destruye, su capa
   de escritura se pierde (a menos que se haya mapeado un volumen).
   </details>

---

## Clase 02 — Docker Aplicado

#### Conceptos Clave

##### Persistencia de datos

Los datos dentro de un contenedor viven en la capa de lectura-escritura, que se **pierde** cuando
el contenedor se elimina. Para persistir datos hay tres opciones:

| Tipo | Qué es | Cuándo usar |
|------|--------|-------------|
| **Bind mount** | Mapeo directo de un path del host al contenedor | Desarrollo, compartir código fuente |
| **Named volume** | Almacenamiento gestionado por Docker | Datos persistentes (DBs, uploads) |
| **tmpfs** | Almacenamiento en RAM, no persiste | Datos sensibles temporales |

```bash
# Bind mount — el host controla la ruta
docker run -v /home/user/data:/app/data:ro mi-app  # :ro = read-only

# Named volume — Docker gestiona la ubicación
docker volume create mi_volumen
docker run -v mi_volumen:/app/data mi-app

# tmpfs — en RAM, desaparece al parar
docker run --tmpfs /app/tmp mi-app
```

##### Redes Docker

| Driver | Descripción | Uso |
|--------|-------------|-----|
| `bridge` | Red virtual aislada (default) | Contenedores en el mismo host |
| `host` | Usa la red del host directamente | Máximo rendimiento de red |
| `none` | Sin red | Contenedores totalmente aislados |
| `overlay` | Red entre múltiples hosts Docker | Docker Swarm / clusters |

**DNS interno:** Los contenedores en la misma red Docker pueden comunicarse usando el **nombre del
servicio** como hostname. No necesitás IPs estáticas.

```yaml
services:
  web:
    build: .
    ports: ["8080:80"]
  redis:
    image: redis:7
# web puede conectarse a redis usando: redis://redis:6379
```

##### Docker Compose

Docker Compose define aplicaciones multi-contenedor en un archivo YAML declarativo.

```yaml
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:80"
    volumes:
      - ./src:/app/src:ro   # Bind mount (desarrollo)
      - app_data:/app/data  # Named volume (persistencia)
    environment:
      - LOG_LEVEL=INFO
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16
    volumes:
      - db_data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: ${DB_PASS}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

volumes:
  app_data:
  db_data:
```

**`depends_on` sin healthcheck:** Solo espera a que el contenedor **arranque** (proceso iniciado),
NO a que el servicio esté **listo** (ej: la DB aceptando conexiones). Para esperar readiness, se
necesita `healthcheck` + `condition: service_healthy`.

##### Multi-stage builds

Permiten usar una imagen "gorda" para compilar y una "flaca" para ejecutar:

```dockerfile
# Stage 1: Build (imagen grande con compilador)
FROM golang:1.21 AS builder
WORKDIR /app
COPY . .
RUN go build -o server .

# Stage 2: Production (imagen mínima)
FROM alpine:3.18
COPY --from=builder /app/server /usr/local/bin/
CMD ["server"]
# Resultado: imagen final de ~10MB en vez de ~1GB
```

#### Ejemplo: docker-compose.yml del TP1

```yaml
version: '3.8'
services:
  monitor:
    build: .
    tty: true          # Necesario para curses (asigna pseudo-terminal)
    stdin_open: true    # Permite entrada interactiva
    pid: "host"         # Usa el namespace PID del host (ve TODOS los procesos)
    volumes:
      - /proc:/host_proc:ro  # Monta /proc del host como read-only
```

**¿Por qué `pid: "host"`?** Sin esto, Docker crea un namespace PID aislado donde el contenedor
solo ve sus propios procesos. Un monitor como htop necesita ver los procesos del host, así que se
comparte el namespace PID.

**¿Por qué montar `/proc`?** Aunque `pid: "host"` permite ver los PIDs del host, el filesystem
`/proc` dentro del contenedor sigue mostrando la vista del namespace original. Montando `/proc`
del host se obtiene acceso a toda la información de procesos.

#### Errores Típicos

**❌ Asumir que `depends_on` espera a readiness:**

```yaml
# MAL — app puede arrancar antes de que la DB acepte conexiones
depends_on:
  - db

# BIEN — espera el healthcheck de la DB
depends_on:
  db:
    condition: service_healthy
```

**❌ Exponer puertos sin precaución:** `ports: ["8080:80"]` mapea en `0.0.0.0` por defecto
(accesible desde cualquier IP). Para limitar al host local: `ports: ["127.0.0.1:8080:80"]`.

**❌ Usar `:latest` en producción:** El tag `latest` es mutable — puede apuntar a distintas
versiones en distintos momentos. Siempre usar tags específicos (`python:3.11-slim`, `redis:7.2`).

#### 📌 Conexión con tu TP1

Tu compose usa `tty: true` (para que curses tenga un terminal), `pid: "host"` (para ver procesos
del host), y monta `/proc` como read-only. Esta combinación es la que permite que un contenedor
Docker funcione como monitor de procesos del sistema anfitrión, escapando del aislamiento por defecto.

#### Preguntas de Examen

1. **¿Cuál es la diferencia entre un Bind Mount y un Named Volume? ¿Cuándo usarías cada uno?**
   <details><summary>Respuesta</summary>
   Un Bind Mount vincula una ruta específica y absoluta del host al contenedor. Docker no lo gestiona
   — depende de la estructura del host. Se usa en desarrollo para compartir código fuente.

   Un Named Volume es gestionado por Docker en su almacenamiento interno (`/var/lib/docker/volumes/`).
   Es portable, se puede respaldar con `docker volume`, y no depende de rutas del host. Se usa para
   datos persistentes como bases de datos.
   </details>

2. **¿Por qué un contenedor Docker que ejecuta un monitor de procesos (como htop) necesita `pid: "host"` en su configuración?**
   <details><summary>Respuesta</summary>
   Docker crea un namespace PID aislado por defecto: el contenedor solo ve sus propios procesos,
   con PID 1 asignado al proceso principal del contenedor. Un monitor necesita ver TODOS los procesos
   del sistema. `pid: "host"` comparte el namespace PID del host con el contenedor, dándole
   visibilidad completa sobre la tabla de procesos del sistema operativo anfitrión.
   </details>

3. **Explicá qué problema resuelven los multi-stage builds y cómo reducen el tamaño de la imagen.**
   <details><summary>Respuesta</summary>
   En un build normal, las herramientas de compilación (gcc, make, dependencias de desarrollo)
   quedan en la imagen final aunque no se necesiten en runtime. Un multi-stage build usa una primera
   etapa con todas las herramientas para compilar, y una segunda etapa mínima (como `alpine`) donde
   solo se copia el binario compilado con `COPY --from=builder`. El resultado es una imagen de
   producción dramáticamente más pequeña (ej: de 1GB a 10MB).
   </details>

---

## Clase 03 — Procesos Fundamentos

#### Conceptos Clave

##### Proceso vs Programa

- **Programa**: archivo ejecutable estático en disco (código + datos iniciales).
- **Proceso**: instancia en ejecución de un programa con su propio contexto: registros de CPU,
  espacio de memoria, archivos abiertos, PID, estado, señales pendientes.

Un mismo programa puede tener múltiples procesos ejecutándose simultáneamente (ej: múltiples
instancias de `bash`).

##### PCB — Process Control Block

Estructura del kernel que almacena TODO sobre un proceso:

- **PID, PPID** (process ID, parent PID)
- **UID, GID** (user/group ID del dueño)
- **Estado** (Running, Ready, Blocked, Zombie, etc.)
- **Registros de CPU** (program counter, stack pointer, flags)
- **Mapa de memoria** (rangos de direcciones virtuales)
- **Tabla de file descriptors** (archivos abiertos, pipes, sockets)
- **Información de señales** (pendientes, bloqueadas, handlers)
- **Información de scheduling** (prioridad, política, tiempo de CPU usado)

##### Identificadores de proceso

| ID | Qué identifica | Cómo obtenerlo |
|----|----------------|----------------|
| PID | El proceso | `os.getpid()` |
| PPID | El proceso padre | `os.getppid()` |
| UID | El usuario dueño | `os.getuid()` |
| GID | El grupo dueño | `os.getgid()` |
| PGID | El grupo de procesos | `os.getpgid(pid)` |
| SID | La sesión | `os.getsid(pid)` |

##### Layout de Memoria Virtual

Cada proceso tiene su propio espacio de direcciones virtuales:

```
Dirección alta   ┌──────────────────────┐
                 │       Stack          │ ← Variables locales, frames de función
                 │    (crece hacia ↓)   │   Se asigna automáticamente al entrar a funciones
                 ├──────────────────────┤
                 │                      │
                 │    (espacio libre)   │
                 │                      │
                 ├──────────────────────┤
                 │       Heap           │ ← Memoria dinámica (malloc/new/Python objects)
                 │    (crece hacia ↑)   │   Se asigna explícita o automáticamente
                 ├──────────────────────┤
                 │  Memory-mapped       │ ← Bibliotecas compartidas, mmap
                 ├──────────────────────┤
                 │       BSS            │ ← Variables globales NO inicializadas (zeroed)
                 ├──────────────────────┤
                 │       Data           │ ← Variables globales inicializadas
                 ├──────────────────────┤
Dirección baja   │       Text           │ ← Código ejecutable (read-only)
                 └──────────────────────┘
```

##### Estados de un proceso

```
              ┌──────────────────────────────────────┐
              │                                      │
  New ──admitted──> Ready ──scheduler──> Running ──exit──> Terminated
                     ↑                    │  │                │
                     │    preempt/        │  │                ↓
                     │    time slice      │  │            Zombie
                     │                    │  │          (esperando wait)
                     │                    │  │
                     └──I/O complete──  Blocked
                                       (waiting I/O)
```

**Zombie**: el proceso terminó pero su padre NO llamó a `wait()` para leer su exit status. Ocupa
una entrada en la tabla de procesos (PID + exit code) pero no consume CPU ni memoria significativa.
Se soluciona cuando el padre llama a `wait()`.

**Huérfano**: el padre muere antes que el hijo. El proceso init (PID 1) adopta al huérfano y
automáticamente lo limpia cuando termine.

##### Context switching

Cuando la CPU cambia de un proceso a otro:

1. Guarda los registros del proceso actual en su PCB
2. Carga los registros del nuevo proceso desde su PCB
3. Invalida la TLB (Translation Lookaside Buffer) para la nueva tabla de páginas
4. Reanuda la ejecución del nuevo proceso

Este cambio tiene un **costo real**: invalidar la TLB genera cache misses hasta que se recarga.
Por eso crear demasiados procesos puede degradar el rendimiento.

##### Módulo `subprocess`

**`subprocess.run()` — ejecución simple y bloqueante:**

```python
import subprocess

# Ejecutar comando y capturar salida
result = subprocess.run(
    ['ls', '-la', '/proc/1'],
    capture_output=True,  # Capturar stdout y stderr
    text=True,            # Decodificar como string (no bytes)
    check=True            # Lanzar CalledProcessError si returncode != 0
)
print(result.stdout)
print(f"Exit code: {result.returncode}")
```

**`subprocess.Popen()` — control avanzado y no-bloqueante:**

```python
proc = subprocess.Popen(
    ['ping', '-c', '3', 'localhost'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# communicate() espera a que termine y recoge toda la salida
stdout, stderr = proc.communicate(timeout=10)
print(f"Exit code: {proc.returncode}")

# Alternativa: poll() para chequear sin bloquear
# proc.poll()  # None si aún corre, returncode si terminó
```

#### Ejemplo: Leer información de un proceso desde /proc

```python
import os

def get_process_info(pid):
    """Read comprehensive process info from /proc filesystem."""
    proc_dir = f"/proc/{pid}"

    try:
        # Read stat — compact, space-separated, single line
        with open(f"{proc_dir}/stat") as f:
            stat_line = f.read()

        # comm field is in parentheses and can contain spaces/parens
        start = stat_line.index('(')
        end = stat_line.rindex(')')
        comm = stat_line[start+1:end]
        fields = stat_line[end+2:].split()
        # fields[0] = state, fields[1] = ppid, etc.

        # Read status — human-readable key:value pairs
        info = {}
        with open(f"{proc_dir}/status") as f:
            for line in f:
                key, _, value = line.partition(':')
                info[key.strip()] = value.strip()

        return {
            'pid': pid,
            'comm': comm,
            'state': fields[0],
            'ppid': int(fields[1]),
            'vm_size': info.get('VmSize', 'N/A'),
            'vm_rss': info.get('VmRSS', 'N/A'),
            'threads': int(info.get('Threads', 1)),
        }
    except (FileNotFoundError, ProcessLookupError):
        return None  # Process disappeared
```

#### Errores Típicos

**❌ Confundir VIRT con RES:** `VmSize` (virtual) es la memoria total mapeada — incluye bibliotecas
compartidas, archivos mapeados, y memoria reservada pero no usada. `VmRSS` (resident) es la
memoria física real ocupada en RAM. Un proceso con 2GB de VIRT puede tener solo 50MB de RES.

**❌ Asumir que variables globales se comparten entre procesos:** Cada proceso tiene su propio
espacio de memoria. Modificar una variable global en un hijo NO afecta al padre ni a otros hijos.
Para compartir datos, se necesitan mecanismos de IPC (pipes, shared memory, etc.).

**❌ No usar `communicate()` con Popen:** Leer `stdout.read()` y `stderr.read()` por separado
puede causar deadlocks si los buffers se llenan. `communicate()` lee ambos simultáneamente.

#### 📌 Conexión con tu TP1

Tu `procfs.py` implementa exactamente lo del ejemplo: parseo robusto de `/proc/[pid]/stat` usando
`find('(')` y `rfind(')')` para aislar el campo `comm` que puede contener espacios y paréntesis.
Tu `_parse_stat_line` es una implementación production-ready de esta técnica. Los 7 analizadores
leen distintos archivos de `/proc` para distintas métricas.

#### Preguntas de Examen

1. **¿Qué es un proceso zombie y cómo se previene su acumulación?**
   <details><summary>Respuesta</summary>
   Un proceso zombie es un proceso hijo que ya terminó su ejecución pero cuyo estado de salida aún
   no fue recolectado por el padre con `wait()`/`waitpid()`. Retiene una entrada en la tabla de
   procesos (PID + exit status) hasta que el padre lo recolecte.

   Se previene: (1) llamando a `wait()`/`waitpid()` en el padre, (2) manejando `SIGCHLD` para
   recolectar hijos asincrónicamente, o (3) usando el truco del doble fork (fork un hijo que forkea
   un nieto y termina inmediatamente — el nieto es adoptado por init que lo recolecta).
   </details>

2. **¿Cuál es la diferencia entre la sección Heap y Stack en la memoria de un proceso?**
   <details><summary>Respuesta</summary>
   El **Stack** es memoria automática (LIFO) para variables locales, frames de función y direcciones
   de retorno. Crece hacia abajo, se asigna/libera automáticamente al entrar/salir de funciones,
   y tiene tamaño limitado (típicamente 8MB).

   El **Heap** es memoria dinámica para objetos alocados explícitamente (`malloc`/`new`) o por el
   runtime (objetos Python). Crece hacia arriba, debe liberarse explícitamente (o por GC), y su
   tamaño está limitado por la memoria disponible del sistema.
   </details>

3. **El archivo `/proc/[pid]/stat` tiene el nombre del proceso entre paréntesis. ¿Por qué es incorrecto parsearlo simplemente con `split()` y tomar el campo por índice?**
   <details><summary>Respuesta</summary>
   Porque el nombre del comando (`comm`) puede contener espacios y paréntesis anidados. Un `split()`
   ingenuo rompería el campo en múltiples tokens, desplazando todos los índices posteriores. La
   forma correcta es encontrar el primer `(` y el último `)` para aislar `comm`, y parsear el
   resto de los campos a partir del carácter después del último `)`.
   </details>

4. **¿Por qué usar `subprocess.run()` con `communicate()` en vez de leer `stdout` y `stderr` directamente?**
   <details><summary>Respuesta</summary>
   `subprocess.run()` ya usa `communicate()` internamente. Pero si usás `Popen` directamente y
   leés `proc.stdout.read()` seguido de `proc.stderr.read()`, el primer `read()` puede bloquearse
   indefinidamente si el proceso escribe mucho a stderr — el buffer de stderr se llena, el proceso
   se bloquea esperando que alguien lo lea, y tu código está bloqueado leyendo stdout. Es un
   deadlock. `communicate()` lee ambos streams simultáneamente (con threads internos) evitando esto.
   </details>

---

## Clase 04 — Fork, Exec, Wait

#### Conceptos Clave

##### `os.fork()` — Duplicar un proceso

`fork()` crea una **copia exacta** del proceso actual. Después de `fork()`, hay dos procesos
ejecutando el mismo código desde la misma línea:

```python
import os

pid = os.fork()
# A partir de acá, hay DOS procesos ejecutando

if pid == 0:
    # Estamos en el HIJO (fork retorna 0)
    print(f"Soy el hijo, mi PID: {os.getpid()}, mi padre: {os.getppid()}")
    os._exit(0)
else:
    # Estamos en el PADRE (fork retorna el PID del hijo)
    print(f"Soy el padre, mi hijo tiene PID: {pid}")
    os.waitpid(pid, 0)
```

**Copy-on-Write (COW):** Aunque fork "copia" todo el proceso, la copia real de memoria se
difiere hasta que padre o hijo **modifican** algo. Inicialmente comparten las mismas páginas
físicas de RAM. Solo cuando uno escribe en una página, el kernel copia esa página específica.
Esto hace que fork sea muy eficiente si el hijo ejecuta `exec()` inmediatamente.

**Qué se hereda en el fork:**

| Se hereda ✅ | NO se hereda ❌ |
|-------------|----------------|
| Memoria completa (COW) | PID (el hijo tiene uno nuevo) |
| File descriptors abiertos | PPID (el hijo tiene nuevo padre) |
| Signal handlers | Señales pendientes |
| Variables de entorno | File locks |
| Working directory | Timers (`alarm`) |

##### `os.exec*()` — Reemplazar la imagen del proceso

La familia `exec` **reemplaza completamente** el código, datos y stack del proceso actual con un
nuevo programa. El PID no cambia — es el mismo proceso ejecutando un programa diferente.

| Variante | Argumentos | PATH | Entorno |
|----------|------------|------|---------|
| `execl(path, arg0, arg1, ...)` | Lista de args | No busca | Hereda |
| `execlp(file, arg0, arg1, ...)` | Lista de args | Busca en PATH | Hereda |
| `execle(path, arg0, ..., env)` | Lista de args | No busca | Custom |
| `execv(path, [args])` | Vector (lista) | No busca | Hereda |
| `execvp(file, [args])` | Vector (lista) | Busca en PATH | Hereda |
| `execve(path, [args], env)` | Vector (lista) | No busca | Custom |

Nemotecnia: `l` = list, `v` = vector, `p` = PATH, `e` = environment.

**Si `exec` tiene éxito, NUNCA retorna.** El código después de `exec` solo se ejecuta si `exec`
falla (ej: comando no encontrado).

**Patrón Fork-Exec:**

```python
pid = os.fork()
if pid == 0:
    # Hijo: reemplazar con otro programa
    os.execlp('ls', 'ls', '-la', '/proc')
    # Si llegamos acá, exec falló
    print("Error: exec falló", file=sys.stderr)
    os._exit(1)
else:
    # Padre: esperar al hijo
    _, status = os.waitpid(pid, 0)
    if os.WIFEXITED(status):
        print(f"Hijo terminó con código: {os.WEXITSTATUS(status)}")
```

##### `os.wait()` y `os.waitpid()`

| Función | Espera a | Bloquea | Retorna |
|---------|----------|---------|---------|
| `os.wait()` | Cualquier hijo | Sí | `(pid, status)` |
| `os.waitpid(pid, 0)` | Hijo específico (o cualquiera si pid=-1) | Sí | `(pid, status)` |
| `os.waitpid(-1, os.WNOHANG)` | Cualquier hijo | No | `(pid, status)` o `(0, 0)` si ninguno terminó |

**Decodificación del status:**

```python
pid, status = os.waitpid(child_pid, 0)
if os.WIFEXITED(status):
    exit_code = os.WEXITSTATUS(status)    # Código de salida (0-255)
elif os.WIFSIGNALED(status):
    signal_num = os.WTERMSIG(status)      # Señal que lo mató
```

##### `sys.exit()` vs `os._exit()`

| Aspecto | `sys.exit()` | `os._exit()` |
|---------|-------------|-------------|
| Mecanismo | Lanza `SystemExit` | Llamada directa al kernel |
| atexit handlers | ✅ Los ejecuta | ❌ No los ejecuta |
| Buffers de I/O | ✅ Los flushea | ❌ No los flushea |
| finally blocks | ✅ Los ejecuta | ❌ No los ejecuta |
| Usar en | Programa principal | Hijos creados con `fork()` |

**¿Por qué `os._exit()` en hijos?** Porque el hijo hereda los buffers de I/O del padre. Si el
hijo hace `sys.exit()`, flushea esos buffers duplicados, causando que la salida aparezca dos veces.

#### Ejemplo: Crear múltiples hijos en un loop

```python
import os
import sys

NUM_WORKERS = 3

children = []
for i in range(NUM_WORKERS):
    pid = os.fork()
    if pid == 0:
        # Child process — do work and exit
        print(f"Worker {i} (PID={os.getpid()}) starting")
        result = i * i  # Simulate computation
        print(f"Worker {i} computed: {result}")
        os._exit(0)  # CRITICAL: use os._exit, not sys.exit
    else:
        children.append(pid)

# Parent: wait for all children to finish
for child_pid in children:
    pid, status = os.waitpid(child_pid, 0)
    if os.WIFEXITED(status):
        print(f"Child {pid} exited with code {os.WEXITSTATUS(status)}")
    elif os.WIFSIGNALED(status):
        print(f"Child {pid} killed by signal {os.WTERMSIG(status)}")

print("All workers finished")
```

**Error sutil:** Si olvidás `os._exit(0)` en el hijo, cuando el loop continúa, el hijo TAMBIÉN
forkea nuevos hijos en las siguientes iteraciones, provocando una explosión exponencial de procesos.

#### Errores Típicos

**❌ Usar `sys.exit()` en un hijo forkeado:**

```python
pid = os.fork()
if pid == 0:
    do_work()
    sys.exit(0)   # ❌ Flushea buffers del padre → salida duplicada
    # os._exit(0) # ✅ Sale limpiamente sin efectos secundarios
```

**❌ No llamar a `wait()` — zombies:**

```python
# MAL — el padre no recolecta al hijo, creando un zombie
pid = os.fork()
if pid == 0:
    os._exit(0)
# El hijo terminó pero su PCB sigue en la tabla de procesos

# BIEN — recolectar con wait
pid = os.fork()
if pid == 0:
    os._exit(0)
os.waitpid(pid, 0)  # Limpia el zombie
```

**❌ Fork bomb — falta de control en loops:**

```python
# PELIGROSO — fork() sin condición de salida del hijo
while True:
    os.fork()  # Crea procesos exponencialmente, colapsa el sistema
```

#### 📌 Conexión con tu TP1

Tu TP1 usa `os.fork()` para crear los procesos del pipeline. El padre crea hijos en orden inverso
(reporte primero, luego estadísticas, validación, ingesta) para que las etapas downstream estén
listas antes de que upstream empiece a enviar datos. Usa `os.waitpid()` para recolectar hijos y
`os._exit()` en todos los hijos — decisiones de diseño que evitan zombies y corrupción de I/O.

#### Preguntas de Examen

1. **¿Qué es Copy-on-Write (COW) y cómo hace eficiente al `fork()`?**
   <details><summary>Respuesta</summary>
   COW es una optimización del kernel: al hacer `fork()`, padre e hijo comparten las mismas páginas
   físicas de RAM marcadas como read-only. Solo cuando uno de los dos intenta ESCRIBIR en una página,
   el kernel la copia en ese momento (copia "a demanda"). Esto hace que `fork()` sea casi instantáneo
   independientemente del tamaño del proceso, y si el hijo ejecuta `exec()` inmediatamente, casi
   ninguna página se copia.
   </details>

2. **¿Por qué es CRÍTICO usar `os._exit()` en vez de `sys.exit()` en un proceso hijo creado con `fork()`?**
   <details><summary>Respuesta</summary>
   `sys.exit()` lanza `SystemExit` que ejecuta los handlers de `atexit`, flushea los buffers de I/O,
   y ejecuta bloques `finally`. Como el hijo hereda los buffers de I/O del padre (duplicados por el
   fork), flushearlos causa que la salida acumulada se escriba dos veces. `os._exit()` llama
   directamente a `_exit()` del kernel, terminando el proceso sin ninguna limpieza de Python.
   </details>

3. **Dado este código, ¿cuántos procesos existen en total al final? ¿Por qué?**
   ```python
   os.fork()
   os.fork()
   ```
   <details><summary>Respuesta</summary>
   4 procesos. El primer `fork()` crea 1 hijo (total: 2). El segundo `fork()` se ejecuta en AMBOS
   procesos (padre original e hijo), creando 2 hijos más (total: 4). Cada `fork()` duplica todos
   los procesos existentes: 1 → 2 → 4. En general, N llamadas a `fork()` sin control producen 2^N
   procesos.
   </details>

4. **¿Cuáles son las 4 condiciones de Coffman necesarias para un zombie y cómo se resuelve?**
   <details><summary>Respuesta</summary>
   Un zombie NO requiere las condiciones de Coffman (eso es para deadlocks). Un zombie ocurre cuando:
   (1) un hijo termina (`exit()`), (2) el padre está vivo pero NO ha llamado a `wait()`/`waitpid()`.
   El PCB del hijo queda en la tabla de procesos con su exit status hasta que alguien lo lea.

   Se resuelve: llamando a `wait()`/`waitpid()` en el padre, manejando `SIGCHLD` con
   `waitpid(-1, WNOHANG)`, o usando el doble-fork trick (el hijo intermedio termina inmediato y
   el nieto es adoptado por init).
   </details>

---

## Clase 05 — Pipes

#### Conceptos Clave

##### Pipes anónimos

Un pipe es un canal unidireccional de bytes en memoria del kernel. `os.pipe()` retorna dos file
descriptors: uno para leer y otro para escribir.

```python
read_fd, write_fd = os.pipe()
# read_fd: file descriptor para LEER del pipe
# write_fd: file descriptor para ESCRIBIR al pipe
```

**Características del pipe:**

- **Unidireccional**: los datos fluyen en una sola dirección (writer → reader).
- **En memoria**: los datos viven en un buffer del kernel (~64KB en Linux).
- **Bloqueante**: `read()` bloquea si no hay datos. `write()` bloquea si el buffer está lleno.
- **EOF**: `read()` retorna 0 bytes (EOF) **solo cuando TODOS los file descriptors de escritura
  están cerrados**. Esto es CRÍTICO.

##### Cierre de extremos — LA regla más importante de pipes

Después de un `fork()`, tanto padre como hijo tienen copias de AMBOS file descriptors. **Cada
proceso debe cerrar el extremo que no usa.**

```
Antes del fork:
  Proceso: read_fd(abierto), write_fd(abierto)

Después del fork:
  Padre: read_fd(ABIERTO), write_fd(→ CERRAR)    ← solo lee
  Hijo:  read_fd(→ CERRAR), write_fd(ABIERTO)    ← solo escribe
```

**¿Qué pasa si NO cerrás el write_fd en el padre (lector)?**

El padre intenta leer del pipe. Cuando el hijo termina y cierra su write_fd, el kernel NO envía
EOF porque el PADRE todavía tiene abierto su write_fd. El padre se queda bloqueado en `read()`
para siempre → **DEADLOCK**.

##### `os.read()` y `os.write()`

```python
# Escritura — envía bytes crudos
bytes_written = os.write(write_fd, b"Hello from child\n")

# Lectura — lee hasta N bytes (puede retornar menos)
data = os.read(read_fd, 4096)  # Lee hasta 4096 bytes
# data == b'' significa EOF (todos los writers cerraron)
```

##### `os.dup2()` — Redirección de file descriptors

`os.dup2(old_fd, new_fd)` hace que `new_fd` apunte al mismo recurso que `old_fd`. Se usa para
redirigir stdin/stdout/stderr a un pipe:

```python
import os
import sys

r, w = os.pipe()
pid = os.fork()

if pid == 0:
    os.close(r)
    os.dup2(w, sys.stdout.fileno())  # stdout ahora escribe al pipe
    os.close(w)                       # El fd original ya no se necesita
    # Todo lo que este proceso imprima va al pipe
    print("This goes through the pipe!")
    os._exit(0)
else:
    os.close(w)
    output = os.read(r, 4096).decode()
    print(f"Parent received: {output}")
    os.close(r)
    os.wait()
```

##### Named Pipes (FIFOs)

Los pipes anónimos solo funcionan entre procesos con relación padre-hijo (comparten los FDs del
fork). Los **FIFOs** son pipes con nombre en el filesystem, permitiendo IPC entre procesos
no relacionados.

```python
import os

# Crear el FIFO (se ve como archivo en el filesystem)
fifo_path = '/tmp/my_fifo'
os.mkfifo(fifo_path)  # Crea el archivo especial

# Proceso escritor (puede ser un script separado):
with open(fifo_path, 'w') as fifo:
    fifo.write("Message through FIFO\n")

# Proceso lector (otro script):
with open(fifo_path, 'r') as fifo:
    msg = fifo.readline()
    print(f"Received: {msg}")

# Limpiar
os.unlink(fifo_path)  # Eliminar el FIFO del filesystem
```

**Comportamiento bloqueante:** `open()` de un FIFO bloquea hasta que exista al menos un proceso
en el otro extremo. Si abrís para lectura, bloquea hasta que alguien abra para escritura, y viceversa.

##### Comunicación bidireccional

Un pipe es unidireccional. Para comunicación bidireccional entre padre e hijo, se necesitan
**dos pipes**:

```
Pipe 1: Padre → Hijo     (padre escribe, hijo lee)
Pipe 2: Hijo → Padre     (hijo escribe, padre lee)
```

##### Serialización de datos sobre pipes

Los pipes transmiten bytes crudos. Para enviar datos estructurados:

```python
import json
import os

# Escritor — serializar como JSON + delimitador
data = {'pid': 1234, 'cpu': 45.2, 'name': 'python'}
message = json.dumps(data) + '\n'  # \n como delimitador entre mensajes
os.write(write_fd, message.encode())

# Lector — acumular bytes y parsear en el delimitador
buffer = b''
while True:
    chunk = os.read(read_fd, 4096)
    if not chunk:  # EOF
        break
    buffer += chunk
    while b'\n' in buffer:
        line, buffer = buffer.split(b'\n', 1)
        record = json.loads(line.decode())
        process(record)
```

##### `select.select()` — Multiplexación de I/O

`select()` monitorea múltiples file descriptors simultáneamente sin bloquear:

```python
import select

# readable contiene los FDs que tienen datos para leer
readable, _, _ = select.select([fd1, fd2, fd3], [], [], timeout_secs)
for fd in readable:
    data = os.read(fd, 4096)
```

Útil cuando un proceso necesita leer de múltiples pipes sin saber cuál tendrá datos primero.

#### Ejemplo: Pipeline padre-hijo con JSON

```python
import os
import json

def writer_process(write_fd):
    """Child: send JSON records through pipe."""
    records = [
        {'pid': 1, 'name': 'init', 'cpu': 0.1},
        {'pid': 42, 'name': 'python', 'cpu': 85.3},
        {'pid': 100, 'name': 'bash', 'cpu': 0.0},
    ]
    for record in records:
        msg = json.dumps(record) + '\n'
        os.write(write_fd, msg.encode())
    os.close(write_fd)  # Signal EOF to reader

def reader_process(read_fd):
    """Parent: read JSON records from pipe."""
    buffer = b''
    while True:
        chunk = os.read(read_fd, 4096)
        if not chunk:
            break
        buffer += chunk
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            record = json.loads(line.decode())
            print(f"Received process: {record['name']} (CPU: {record['cpu']}%)")
    os.close(read_fd)

r, w = os.pipe()
pid = os.fork()

if pid == 0:
    os.close(r)  # Child doesn't read
    writer_process(w)
    os._exit(0)
else:
    os.close(w)  # Parent doesn't write
    reader_process(r)
    os.wait()
```

#### Errores Típicos

**❌ No cerrar extremos no usados (DEADLOCK):**

```python
r, w = os.pipe()
pid = os.fork()
if pid == 0:
    # os.close(r)  ← OLVIDADO: el hijo tiene el read_fd abierto innecesariamente
    os.write(w, b"data")
    os.close(w)
    os._exit(0)
else:
    # os.close(w)  ← OLVIDADO: el padre tiene el write_fd abierto
    data = os.read(r, 4096)  # Lee "data"
    data = os.read(r, 4096)  # DEADLOCK: espera EOF que nunca llega
    #                          porque el padre mismo tiene w abierto
```

**❌ SIGPIPE:** Escribir a un pipe cuyo extremo de lectura fue cerrado por todos los lectores
genera `SIGPIPE` (que por defecto mata el proceso) o `BrokenPipeError` en Python.

**❌ Buffer overflow:** El buffer del pipe es ~64KB. Si el escritor produce datos más rápido de lo
que el lector consume, `write()` se bloquea cuando el buffer se llena. Esto puede causar deadlocks
en pipelines complejos.

#### 📌 Conexión con tu TP1

Tu TP1 usa dos pipes anónimos para el pipeline: `ingesta → validación` y `validación → estadísticas`.
Los datos fluyen como registros JSON delimitados por `\n`. Tu función `read_from_pipe()` en
`utils.py` implementa exactamente el patrón de lectura por chunks con acumulación en buffer y
split en delimitador. El cierre correcto de extremos garantiza que cada etapa detecte EOF cuando
la anterior termina.

#### Preguntas de Examen

1. **Explicá paso a paso por qué el padre DEBE cerrar el extremo de escritura si solo va a leer del pipe.**
   <details><summary>Respuesta</summary>
   El kernel envía EOF (read retorna 0 bytes) a los lectores solo cuando el contador de file
   descriptors de escritura del pipe llega a 0. Después del fork, tanto padre como hijo tienen una
   copia del write_fd. Si el padre no cierra su copia, el contador nunca llega a 0, y el padre
   queda bloqueado en `read()` eternamente esperando EOF, aun después de que el hijo cerró su
   extremo y terminó. Esto es un deadlock.
   </details>

2. **¿Qué ocurre cuando un proceso llama `os.read()` en un pipe vacío? ¿Y si todos los escritores cerraron?**
   <details><summary>Respuesta</summary>
   Si el pipe está vacío pero hay escritores con el FD abierto, `read()` bloquea al proceso
   hasta que alguien escriba datos. Si todos los escritores cerraron su extremo de escritura,
   `read()` retorna `b''` (cadena de bytes vacía), señalizando EOF.
   </details>

3. **¿Cómo enviarías objetos Python complejos (diccionarios, listas) a través de un pipe?**
   <details><summary>Respuesta</summary>
   Serializando a un formato de bytes: JSON (`json.dumps(obj) + '\n'`) es legible y portable,
   ideal para datos simples. Para datos más complejos o rendimiento, `pickle.dumps(obj)` con un
   header de longitud. El delimitador (newline para JSON, longitud fija para pickle) es esencial
   para que el lector sepa dónde termina un mensaje y empieza otro, ya que el pipe es un stream
   de bytes sin fronteras de mensaje.
   </details>

4. **¿Cuál es la diferencia entre un pipe anónimo y un FIFO (named pipe)? ¿Cuándo usarías cada uno?**
   <details><summary>Respuesta</summary>
   Un pipe anónimo solo existe en memoria y es accesible por procesos que comparten los file
   descriptors (ej: padre-hijo vía fork). Un FIFO tiene un nombre en el filesystem
   (`os.mkfifo(path)`) y puede ser usado por procesos sin relación de parentesco.

   Pipe anónimo: IPC rápido entre procesos padre-hijo o hermanos en el mismo pipeline.
   FIFO: comunicación entre procesos independientes (ej: un daemon y un cliente), como colas
   de mensajes simples.
   </details>

---

## Clase 06 — Señales

#### Conceptos Clave

##### ¿Qué es una señal?

Una señal es una **notificación asíncrona** enviada por el kernel a un proceso. "Asíncrona" significa
que llega en cualquier momento, interrumpiendo lo que el proceso esté haciendo. Es como una
interrupción de software.

##### Disposición de señales

Cuando una señal llega, puede pasar una de tres cosas (la "disposición"):

1. **Acción por defecto** (`SIG_DFL`): el kernel aplica la acción predefinida (terminar, pausar, ignorar, core dump).
2. **Handler personalizado**: una función Python que el programador registró para esa señal.
3. **Ignorar** (`SIG_IGN`): la señal se descarta silenciosamente.

##### Señales comunes

| Señal | Nro | Default | ¿Capturable? | Cuándo se envía |
|-------|-----|---------|-------------|-----------------|
| `SIGINT` | 2 | Terminar | ✅ | Ctrl+C en terminal |
| `SIGTERM` | 15 | Terminar | ✅ | `kill pid`, `docker stop` |
| `SIGKILL` | 9 | Terminar | ❌ NUNCA | `kill -9`, último recurso |
| `SIGSTOP` | 19 | Pausar | ❌ NUNCA | `kill -STOP`, Ctrl+Z |
| `SIGCONT` | 18 | Continuar | ✅ | `fg`, `kill -CONT` |
| `SIGCHLD` | 17 | Ignorar | ✅ | Un hijo cambió de estado |
| `SIGALRM` | 14 | Terminar | ✅ | Timer de `alarm()` expiró |
| `SIGUSR1` | 10 | Terminar | ✅ | Definido por usuario |
| `SIGUSR2` | 12 | Terminar | ✅ | Definido por usuario |
| `SIGHUP` | 1 | Terminar | ✅ | Terminal cerrada / reload config |
| `SIGPIPE` | 13 | Terminar | ✅ | Write a pipe sin lectores |

**`SIGKILL` y `SIGSTOP` son INCAPTURABLES.** El kernel las maneja directamente sin dar al proceso
oportunidad de reaccionar. Esto garantiza que siempre se pueda matar o pausar un proceso.

##### Registrar handlers

```python
import signal
import os

def handle_sigterm(signum, frame):
    print(f"Received signal {signum}, cleaning up...")
    # Perform cleanup
    os._exit(0)

# Register the handler
signal.signal(signal.SIGTERM, handle_sigterm)

# Ignore a signal
signal.signal(signal.SIGINT, signal.SIG_IGN)

# Restore default behavior
signal.signal(signal.SIGINT, signal.SIG_DFL)
```

##### Enviar señales

```python
import os
import signal

os.kill(pid, signal.SIGTERM)      # Enviar SIGTERM a un proceso
os.kill(pid, signal.SIGUSR1)      # Enviar SIGUSR1
signal.raise_signal(signal.SIGINT) # Enviarse una señal a sí mismo
os.killpg(pgid, signal.SIGTERM)   # Enviar a un grupo de procesos
```

##### `signal.alarm()` — Timeouts

```python
import signal

def alarm_handler(signum, frame):
    raise TimeoutError("Operation timed out")

signal.signal(signal.SIGALRM, alarm_handler)
signal.alarm(5)  # SIGALRM en 5 segundos

try:
    result = slow_operation()  # Si tarda más de 5s, se interrumpe
    signal.alarm(0)  # Cancelar la alarma si terminó a tiempo
except TimeoutError:
    print("Operation timed out!")
```

##### `signal.pause()` — Esperar una señal

`signal.pause()` suspende el proceso hasta que llegue una señal que tenga un handler registrado.
Útil para procesos que solo reaccionan a señales.

##### Async-Signal-Safety — LA regla de oro

Los handlers de señal interrumpen el código en un punto ARBITRARIO. Si el código interrumpido
estaba en medio de una operación compleja (ej: escribiendo en un archivo, alocando memoria, dentro
de un lock), hacer esas mismas operaciones en el handler puede corromper el estado del programa.

**Operaciones SEGURAS en un handler:**
- Setear una variable booleana/flag
- Escribir un byte a un pipe (para el self-pipe trick)
- Llamar a `os._exit()`

**Operaciones NO SEGURAS en un handler:**
- `print()`, logging, I/O de archivos
- Alocar memoria, crear objetos
- Adquirir locks
- Llamar a funciones de librería complejas

##### Self-Pipe Pattern (el patrón correcto)

El problema: querés integrar el manejo de señales con un event loop basado en `select()`.
Pero las señales llegan asincrónicamente y pueden interrumpir `select()`.

La solución: crear un pipe no-bloqueante y usar `signal.set_wakeup_fd()`:

```python
import os
import signal
import select
import fcntl

# 1. Create a non-blocking pipe
wakeup_r, wakeup_w = os.pipe()
flags = fcntl.fcntl(wakeup_w, fcntl.F_GETFL)
fcntl.fcntl(wakeup_w, fcntl.F_SETFL, flags | os.O_NONBLOCK)

# 2. Tell Python to write signal numbers to this pipe
old_fd = signal.set_wakeup_fd(wakeup_w)

# 3. Register signal handlers (can be minimal)
def handler(signum, frame):
    pass  # The real work happens in the main loop

signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGHUP, handler)

# 4. Main event loop using select()
running = True
while running:
    readable, _, _ = select.select([wakeup_r, other_fds...], [], [])
    for fd in readable:
        if fd == wakeup_r:
            sig_byte = os.read(wakeup_r, 1)
            sig_num = sig_byte[0]
            if sig_num == signal.SIGTERM:
                print("Graceful shutdown...")
                running = False
            elif sig_num == signal.SIGHUP:
                print("Reloading config...")
                reload_config()
```

**¿Por qué funciona?** El handler no hace nada complejo (async-signal-safe). `set_wakeup_fd()`
escribe el número de señal como un byte al pipe, lo que despierta a `select()`. El procesamiento
real ocurre en el loop principal, en contexto normal (no interrumpido), donde es seguro hacer
cualquier operación.

##### Máscaras de señales en `/proc`

`/proc/[pid]/status` contiene las máscaras de señales como hex de 64 bits:

```
SigPnd: 0000000000000000    # Signals pending for this thread
ShdPnd: 0000000000000000    # Signals pending for the process
SigBlk: 0000000000000000    # Signals blocked
SigIgn: 0000000000000004    # Signals ignored (bit 2 = SIGQUIT)
SigCgt: 0000000180014002    # Signals caught (con handler)
```

Para decodificar: cada bit corresponde a una señal. Bit 1 = SIGHUP, bit 2 = SIGINT, etc.

#### Ejemplo: Graceful shutdown con SIGCHLD para reaping

```python
import signal
import os
import sys

children = []
running = True

def handle_sigterm(signum, frame):
    global running
    running = False  # Flag — safe in handler

def handle_sigchld(signum, frame):
    # Reap ALL finished children (multiple may have died)
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                break  # No more children to reap
            children.remove(pid)
            print(f"Child {pid} reaped")
        except ChildProcessError:
            break  # No children at all

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGCHLD, handle_sigchld)

# Fork some workers
for i in range(3):
    pid = os.fork()
    if pid == 0:
        # Child: do work
        import time
        time.sleep(5)
        os._exit(0)
    children.append(pid)

# Parent: main loop
while running and children:
    signal.pause()  # Sleep until any signal arrives

# Cleanup: terminate remaining children
for pid in children:
    os.kill(pid, signal.SIGTERM)
    os.waitpid(pid, 0)

print("All children cleaned up")
```

#### Errores Típicos

**❌ Intentar capturar SIGKILL/SIGSTOP:**

```python
signal.signal(signal.SIGKILL, handler)  # OSError: [Errno 22] Invalid argument
signal.signal(signal.SIGSTOP, handler)  # OSError: [Errno 22] Invalid argument
```

**❌ Hacer I/O complejo en el handler:**

```python
def bad_handler(signum, frame):
    # MAL — estas operaciones no son async-signal-safe
    logging.info("Signal received")       # I/O + locks internos
    with open('state.json', 'w') as f:    # Alocación + I/O
        json.dump(state, f)
    database.close()                      # Red + locks

# BIEN — solo setear flag
shutdown_requested = False
def good_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True             # Solo asignación simple
```

**❌ Solo manejar señales en el hilo principal:** En Python, `signal.signal()` solo funciona en el
`MainThread`. Intentar registrar handlers en threads secundarios lanza `ValueError`.

#### 📌 Conexión con tu TP1

Tu TP1 tiene un uso avanzado de señales:
- **SIGTERM/SIGINT**: shutdown limpio — el handler setea `stop_event` (Event) que detiene todos
  los analizadores.
- **SIGHUP**: recarga `config.json` sin reiniciar.
- **SIGUSR1**: dump del estado actual a JSON para depuración.
- **SIGUSR2**: toggle del modo verbose.
- **Self-pipe pattern** con `signal.set_wakeup_fd()`: integra señales con el loop de curses.
- **Decodificación de máscaras**: tu analizador de señales decodifica las máscaras hex de 64 bits
  de `/proc/[pid]/status` mapeando cada bit a nombres POSIX.

#### Preguntas de Examen

1. **¿Qué problema resuelve el Self-Pipe Trick y cómo funciona?**
   <details><summary>Respuesta</summary>
   Resuelve la integración segura de señales con un event loop basado en `select()`. El problema
   es que las señales llegan asincrónicamente y pueden interrumpir `select()` en momentos
   arbitrarios, o llegar entre que chequeás un flag y llamás a `select()` (race condition).

   El trick: crear un pipe no-bloqueante y registrarlo con `set_wakeup_fd()`. Cuando llega una
   señal, Python automáticamente escribe el número de señal al pipe. `select()` monitorea ese pipe
   junto con los otros FDs. Cuando la señal llega, `select()` retorna porque el pipe tiene datos
   para leer, y el procesamiento ocurre en el loop principal de forma sincrónica y segura.
   </details>

2. **¿Por qué `SIGKILL` no puede ser capturado ni ignorado?**
   <details><summary>Respuesta</summary>
   Por diseño del kernel: `SIGKILL` existe como garantía absoluta de que un proceso SIEMPRE puede
   ser terminado. Si fuera capturable, un proceso malicioso o con bugs podría ignorarlo y ser
   imposible de matar. El kernel maneja `SIGKILL` directamente sin pasar por el espacio de usuario.
   Lo mismo aplica a `SIGSTOP` para pausar procesos.
   </details>

3. **Al recibir `SIGCHLD` en un handler, ¿por qué se debe llamar a `waitpid(-1, WNOHANG)` en un loop?**
   <details><summary>Respuesta</summary>
   Porque múltiples hijos pueden haber terminado antes de que el handler se ejecute (las señales
   del mismo tipo no se encolan — si llegan dos SIGCHLD antes de que se atienda el primero, solo
   se registra una). El loop con `WNOHANG` recolecta TODOS los hijos terminados, no solo el
   primero. Sin el loop, quedarían zombies.
   </details>

4. **¿Por qué es peligroso llamar a `print()` o `logging.info()` dentro de un signal handler?**
   <details><summary>Respuesta</summary>
   Porque `print()` y `logging` internamente adquieren locks y hacen I/O buffereado. Si la señal
   interrumpió al proceso mientras ya estaba dentro de `print()` (teniendo el lock de stdout),
   intentar hacer `print()` en el handler causa un deadlock (intentar adquirir un lock que ya
   tenemos). Además, la I/O puede quedar en un estado inconsistente si se interrumpe a mitad
   de una escritura. Solo operaciones "async-signal-safe" (setear flags, escribir a pipes) son
   seguras en handlers.
   </details>

---

## Clase 07 — MMAP y Memoria Compartida

#### Conceptos Clave

##### Memory-Mapped I/O

`mmap` proyecta un archivo (o memoria anónima) directamente en el espacio de direcciones del proceso.
En vez de hacer `read()` → copiar a buffer de kernel → copiar a buffer de usuario, con mmap el
proceso accede directamente a las páginas de memoria respaldadas por el archivo. **Zero-copy.**

##### `mmap.mmap()` — File-backed vs Anónimo

```python
import mmap

# File-backed — mapea un archivo existente a memoria
with open('data.bin', 'r+b') as f:
    mm = mmap.mmap(f.fileno(), 0)  # 0 = mapear todo el archivo
    content = mm[0:100]             # Leer como si fuera un bytearray
    mm[0:5] = b"HELLO"             # Escribir directamente (modifica el archivo)
    mm.close()

# Anónimo — memoria pura en RAM, sin archivo (ideal para IPC con fork)
mm = mmap.mmap(-1, 1024)  # -1 = sin archivo, 1024 bytes
```

**Modos de acceso:**

| Modo | Comportamiento |
|------|---------------|
| `ACCESS_READ` | Solo lectura. Intento de escritura → error |
| `ACCESS_WRITE` | Lectura/escritura. Cambios se reflejan en el archivo |
| `ACCESS_COPY` | Copy-on-Write. Cambios son locales, NO afectan el archivo |

##### mmap vs read()/write()

| Aspecto | read()/write() | mmap |
|---------|---------------|------|
| Copias de datos | 2 (kernel → user, user → kernel) | 0 (acceso directo) |
| Acceso aleatorio | Lento (seek + read) | Rápido (indexación directa) |
| Archivos grandes | Lento si no cabe en RAM | Eficiente (paginación del OS) |
| Secuencial pequeño | Adecuado | Overhead de setup innecesario |

##### Anonymous mmap para IPC

Creás mmap anónimo **antes** del fork. Padre e hijo comparten las mismas páginas físicas.
Los cambios de uno son visibles para el otro instantáneamente.

```python
import mmap
import os
import struct

# Create shared memory BEFORE fork
shared = mmap.mmap(-1, 128)

pid = os.fork()
if pid == 0:
    # Child: write a double (8 bytes) at offset 0
    struct.pack_into('d', shared, 0, 3.14159)
    os._exit(0)
else:
    os.wait()
    # Parent: read the double written by child
    value = struct.unpack_from('d', shared, 0)[0]
    print(f"Child sent: {value}")  # 3.14159
    shared.close()
```

##### Módulo `struct` — Empaquetado binario

`struct` convierte entre valores Python y representaciones binarias C:

| Carácter | Tipo C | Tamaño | Python |
|----------|--------|--------|--------|
| `b` | signed char | 1 byte | int |
| `B` | unsigned char | 1 byte | int |
| `i` | int | 4 bytes | int |
| `I` | unsigned int | 4 bytes | int |
| `f` | float | 4 bytes | float |
| `d` | double | 8 bytes | float |
| `Q` | uint64 | 8 bytes | int |
| `s` | char[] | N bytes | bytes |

**Byte order:** `<` little-endian, `>` big-endian, `!` network (big-endian), `@` nativo.

**Diseñando un layout de memoria compartida:**

```python
import struct

# Layout: Header (4 bytes: metric count) + N records of 72 bytes each
# Record: name (32 bytes) + count (8) + sum (8) + mean (8) + std (8) + min (8) + max (8)
HEADER_FMT = '<I'          # unsigned int for metric count
RECORD_FMT = '<32s5d'      # 32-byte name + 5 doubles
HEADER_SIZE = struct.calcsize(HEADER_FMT)   # 4 bytes
RECORD_SIZE = struct.calcsize(RECORD_FMT)   # 72 bytes

# Write
struct.pack_into(HEADER_FMT, mm, 0, num_metrics)
for i, metric in enumerate(metrics):
    offset = HEADER_SIZE + i * RECORD_SIZE
    struct.pack_into(RECORD_FMT, mm, offset,
                     metric.name.encode().ljust(32, b'\x00'),
                     metric.count, metric.sum, metric.mean, metric.std, metric.min)
```

##### `SharedMemory` (Python 3.8+)

Permite compartir memoria entre procesos **sin relación de parentesco**, por nombre:

```python
from multiprocessing.shared_memory import SharedMemory

# Proceso creador
shm = SharedMemory(create=True, size=1024, name='my_data')
shm.buf[0:5] = b'HELLO'

# Otro proceso (independiente)
shm2 = SharedMemory(name='my_data')
print(bytes(shm2.buf[0:5]))  # b'HELLO'
shm2.close()

# Creador limpia al final
shm.close()
shm.unlink()  # CRITICAL: destruye el bloque en /dev/shm
```

**`close()` vs `unlink()`:** `close()` desconecta ESTE proceso. `unlink()` destruye el bloque
de memoria compartida del OS. Llamar `unlink()` solo una vez, desde el proceso propietario.

##### `multiprocessing.Value` y `multiprocessing.Array`

Wrappers de alto nivel sobre shared memory (mmap-backed):

```python
from multiprocessing import Value, Array

# Value: un solo valor de tipo C
counter = Value('i', 0)        # int, inicializado en 0
interval = Value('d', 2.0)     # double, inicializado en 2.0

# Array: array de tipo C
data = Array('i', [1, 2, 3, 4, 5])  # array de ints

# Acceso con lock incorporado
with counter.get_lock():
    counter.value += 1
```

#### Errores Típicos

**❌ Olvidar `unlink()` — memory leak en `/dev/shm`:**

```python
# MAL — el bloque persiste en RAM después de que el programa termina
shm = SharedMemory(create=True, size=1024, name='leak')
shm.close()  # Desconecta pero NO destruye

# BIEN
shm.close()
shm.unlink()  # Destruye el bloque
```

**❌ Race conditions sin sincronización:**

```python
# MAL — dos procesos escriben al mmap simultáneamente
# Proceso A:                    Proceso B:
# mm[0:4] = pack('i', 10)     mm[0:4] = pack('i', 20)
# Resultado: corrupto e impredecible

# BIEN — usar Lock
with lock:
    struct.pack_into('i', mm, 0, value)
```

**❌ Llamar `flush()` excesivamente:** `mm.flush()` fuerza la escritura a disco en mmap con
archivo. Llamarlo tras cada escritura menor destruye el rendimiento. Solo usar al final o en
puntos de sincronización.

#### 📌 Conexión con tu TP1

Tu TP1 usa mmap anónimo con struct para compartir estadísticas entre el proceso `estadísticas` y
el proceso `reporte`. El layout es: header de 4 bytes (cantidad de métricas) + bloques de 72 bytes
por métrica (nombre 32B + 5 doubles). También usás `multiprocessing.Value('d')` para los intervalos
de refresco que el proceso Display puede ajustar en tiempo real (`+`/`-`).

#### Preguntas de Examen

1. **¿Por qué el acceso a archivos mediante mmap es más rápido que con `read()`/`write()` para patrones de acceso aleatorio?**
   <details><summary>Respuesta</summary>
   Porque `read()`/`write()` requieren una syscall por cada operación y copian datos entre el buffer
   del kernel y el espacio de usuario (dos copias). Con mmap, el archivo se mapea directamente en el
   espacio de direcciones del proceso — el acceso es como leer/escribir en un array de bytes en
   memoria. El OS maneja la paginación transparentemente. Para acceso aleatorio, no hay que hacer
   `seek()` repetidamente.
   </details>

2. **Al usar `struct`, ¿qué significa el formato `'<3i2d'`?**
   <details><summary>Respuesta</summary>
   `<` indica byte order little-endian. `3i` son 3 enteros con signo de 4 bytes cada uno (12 bytes
   total). `2d` son 2 doubles de 8 bytes cada uno (16 bytes total). El tamaño total del struct es
   28 bytes. `struct.pack('<3i2d', 1, 2, 3, 1.5, 2.5)` produciría 28 bytes.
   </details>

3. **¿Cuál es la diferencia entre `SharedMemory.close()` y `SharedMemory.unlink()`?**
   <details><summary>Respuesta</summary>
   `close()` desconecta al proceso actual del bloque de memoria compartida — el proceso ya no puede
   accederlo, pero el bloque sigue existiendo en `/dev/shm` para otros procesos. `unlink()` solicita
   al OS destruir el bloque de memoria compartida por completo. Se debe llamar `unlink()` exactamente
   una vez (desde el proceso propietario/creador) después de que todos los demás procesos hayan
   llamado `close()`.
   </details>

4. **¿Por qué la memoria compartida (mmap/SharedMemory) NO incluye mecanismos de sincronización y qué consecuencia tiene esto?**
   <details><summary>Respuesta</summary>
   Porque la memoria compartida es un mecanismo de TRANSPORTE, no de COORDINACIÓN. Su propósito es
   mapear las mismas páginas físicas en múltiples procesos para acceso directo y rápido. Si dos
   procesos escriben simultáneamente sin coordinación, se producen race conditions y datos corruptos.
   Es responsabilidad del programador agregar mecanismos de sincronización (locks, semáforos, eventos)
   sobre la memoria compartida.
   </details>

---

## Clase 08 — Multiprocessing Fundamentos

#### Conceptos Clave

##### ¿Por qué multiprocessing?

Python tiene el **GIL** (Global Interpreter Lock) que impide que múltiples threads ejecuten bytecode
Python simultáneamente. Para tareas CPU-bound, threads NO dan speedup real. `multiprocessing` crea
procesos del OS independientes, cada uno con su propio intérprete y GIL, logrando **paralelismo real**
en múltiples cores.

##### `multiprocessing.Process`

```python
from multiprocessing import Process

def worker(name, count):
    for i in range(count):
        print(f"{name}: iteration {i}")

if __name__ == '__main__':
    p = Process(target=worker, args=('Worker-1', 5), daemon=True)
    p.start()         # Fork/spawn the process
    p.join(timeout=10) # Wait up to 10 seconds
    print(f"Exit code: {p.exitcode}")  # 0=success, >0=error, <0=signal
```

**Métodos principales:**

| Método | Descripción |
|--------|-------------|
| `start()` | Inicia el proceso (fork/spawn) |
| `join(timeout)` | Espera a que termine (None = indefinido) |
| `is_alive()` | True si sigue corriendo |
| `terminate()` | Envía SIGTERM |
| `kill()` | Envía SIGKILL |
| `exitcode` | None (corriendo), 0 (éxito), >0 (error), <0 (killed by signal N) |

##### Start methods

| Método | OS | Velocidad | Seguridad | Requisitos |
|--------|-----|-----------|-----------|------------|
| `fork` | Linux default | Rápido (COW) | ⚠️ Peligroso con threads/locks previos | — |
| `spawn` | Windows/macOS | Lento (nuevo intérprete) | ✅ Seguro | `__main__` guard, pickling |
| `forkserver` | Linux/macOS | Medio | ✅ Seguro | `__main__` guard |

```python
import multiprocessing
multiprocessing.set_start_method('spawn')  # Set globally (once)

# Or per-context
ctx = multiprocessing.get_context('forkserver')
p = ctx.Process(target=worker)
```

##### Daemon processes

```python
p = Process(target=background_task, daemon=True)
```

- **Python daemon ≠ Unix daemon.** Un daemon de multiprocessing es simplemente un proceso hijo
  que se mata automáticamente cuando el proceso padre termina.
- No puede crear subprocesos hijos propios (`AssertionError`).
- No se le da oportunidad de cleanup (no ejecuta `finally`, no flushea buffers).
- Útil para workers que no necesitan terminar limpiamente.

##### Comunicación entre procesos

**Queue — FIFO thread-safe y process-safe:**

```python
from multiprocessing import Process, Queue

def producer(q):
    for item in ['a', 'b', 'c']:
        q.put(item)
    q.put(None)  # Sentinel: signal "no more data"

def consumer(q):
    while True:
        item = q.get()
        if item is None:  # Sentinel received
            break
        print(f"Got: {item}")

if __name__ == '__main__':
    q = Queue()
    p1 = Process(target=producer, args=(q,))
    p2 = Process(target=consumer, args=(q,))
    p1.start(); p2.start()
    p1.join(); p2.join()
```

**Pipe — más rápido para 2 procesos:**

```python
from multiprocessing import Process, Pipe

def sender(conn):
    conn.send({'pid': 123, 'cpu': 45.2})
    conn.close()

if __name__ == '__main__':
    parent_conn, child_conn = Pipe()  # Bidireccional por defecto
    p = Process(target=sender, args=(child_conn,))
    p.start()
    data = parent_conn.recv()
    print(data)  # {'pid': 123, 'cpu': 45.2}
    p.join()
```

##### `if __name__ == '__main__'` — La guarda obligatoria

En Windows/macOS (start method `spawn`), el nuevo proceso **importa** el módulo principal. Sin la
guarda, el código de creación de procesos se ejecuta recursivamente al importar, creando procesos
infinitamente.

```python
# MAL en Windows — crea procesos recursivamente
p = Process(target=worker)
p.start()

# BIEN — protegido contra importación recursiva
if __name__ == '__main__':
    p = Process(target=worker)
    p.start()
```

##### Pickling — qué se puede enviar entre procesos

Todo dato que cruza la frontera entre procesos debe ser serializable con `pickle`:

| ✅ Funciona | ❌ No funciona |
|-------------|--------------|
| int, float, str, bytes | Lambdas (`lambda x: x+1`) |
| Listas, dicts, tuples | Funciones anidadas (inner functions) |
| Funciones definidas a nivel módulo | Sockets, conexiones de DB |
| Clases definidas a nivel módulo | File handles abiertos |
| `None`, `True`, `False` | Generadores activos |

#### Errores Típicos

**❌ Olvidar `if __name__ == '__main__'` en Windows:**

```python
# Windows con spawn: al importar el módulo, Process() se ejecuta otra vez,
# que importa el módulo otra vez, que ejecuta Process() otra vez... ∞
# RuntimeError: An attempt has been made to start a new process before...
```

**❌ Enviar objetos non-picklable:**

```python
# MAL
import socket
s = socket.socket()
p = Process(target=worker, args=(s,))  # pickle.PicklingError

# BIEN — crear el socket dentro del proceso hijo
def worker():
    s = socket.socket()  # Create in child's own memory
```

**❌ Daemon que intenta crear hijos:**

```python
def daemon_worker():
    child = Process(target=subtask)
    child.start()  # AssertionError: daemonic processes can't have children
```

#### 📌 Conexión con tu TP1

Tu TP1 usa 7 `multiprocessing.Process` con `daemon=True` para los analizadores (resumen, memoria,
FDs, threads, señales, scheduling, sistema). Cada uno corre a su propio ritmo (2s, 3s, 5s, 10s) y
comparte datos a través de `Manager.dict()`. El shutdown coordinado se logra con
`multiprocessing.Event` (`stop_event.set()`). Elegiste multiprocessing sobre threading conscientemente
porque el parseo de `/proc` es CPU-bound.

#### Preguntas de Examen

1. **¿Por qué `multiprocessing` logra paralelismo real en Python mientras que `threading` no?**
   <details><summary>Respuesta</summary>
   `multiprocessing` crea procesos del sistema operativo independientes, cada uno con su propio
   intérprete de Python y su propio GIL. Pueden ejecutar bytecode Python genuinamente en paralelo
   en múltiples cores. `threading` crea threads dentro del MISMO proceso, compartiendo el mismo GIL,
   que solo permite que UN thread ejecute bytecode a la vez.
   </details>

2. **¿Qué es el `exitcode` de un `Process` y qué significan sus posibles valores?**
   <details><summary>Respuesta</summary>
   `exitcode` es un atributo que indica cómo terminó el proceso:
   - `None`: el proceso aún está corriendo
   - `0`: terminó exitosamente
   - `> 0`: terminó con error (el valor es el código de error)
   - `< 0`: fue matado por una señal (el valor negado es el número de señal, ej: -9 = SIGKILL)
   </details>

3. **¿Cuál es la diferencia entre los start methods `fork` y `spawn`?**
   <details><summary>Respuesta</summary>
   `fork` usa la syscall `fork()` que clona el proceso completo (con COW). Es rápido pero peligroso
   si el padre tiene threads activos o locks adquiridos (el hijo hereda un estado inconsistente).
   `spawn` inicia un intérprete Python completamente nuevo e importa el módulo — más lento pero
   seguro. `spawn` requiere la guarda `if __name__ == '__main__'` y que todos los argumentos sean
   serializables con pickle.
   </details>

4. **¿Por qué un proceso marcado como `daemon=True` no puede crear procesos hijos propios?**
   <details><summary>Respuesta</summary>
   Porque un daemon es terminado forzosamente (SIGTERM/SIGKILL) cuando su padre termina, sin
   oportunidad de cleanup. Si el daemon pudiera crear hijos, esos "nietos" quedarían huérfanos sin
   control cuando el daemon sea matado. Python previene esto lanzando `AssertionError` al intentar
   crear hijos desde un daemon.
   </details>

---

## Clase 09 — Multiprocessing Avanzado

#### Conceptos Clave

##### `multiprocessing.Pool` — Pool de trabajadores

Un Pool mantiene un número fijo de procesos workers reutilizables:

```python
from multiprocessing import Pool

def compute(x):
    return x ** 2

if __name__ == '__main__':
    with Pool(processes=4) as pool:  # 4 workers
        # map — bloqueante, resultado ordenado
        results = pool.map(compute, range(100))

        # apply_async — no-bloqueante, resultado individual
        future = pool.apply_async(compute, args=(42,))
        result = future.get(timeout=5)  # Espera hasta 5 segundos

        # imap_unordered — lazy, orden de llegada (más rápido)
        for result in pool.imap_unordered(compute, range(1000)):
            process(result)
```

| Método | Bloqueante | Orden | Uso |
|--------|-----------|-------|-----|
| `map(f, iter)` | Sí | Preserva | Batch processing simple |
| `starmap(f, iter_of_tuples)` | Sí | Preserva | Funciones con múltiples args |
| `imap(f, iter)` | Lazy | Preserva | Streaming ordenado |
| `imap_unordered(f, iter)` | Lazy | Llegada | Streaming más rápido |
| `apply_async(f, args)` | No | N/A | Tareas individuales |
| `map_async(f, iter)` | No | Preserva | Batch no-bloqueante |

**Cleanup obligatorio:** `pool.close()` (no acepta más tareas) + `pool.join()` (espera que
terminen). O usar `with Pool() as pool:`.

##### `concurrent.futures.ProcessPoolExecutor`

API moderna y más limpia (misma interfaz que `ThreadPoolExecutor`):

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def analyze(pid):
    return {'pid': pid, 'cpu': read_cpu(pid)}

if __name__ == '__main__':
    with ProcessPoolExecutor(max_workers=4) as executor:
        # submit() retorna Future
        future = executor.submit(analyze, 1234)
        result = future.result()  # Bloquea hasta completar

        # as_completed() — procesar en orden de finalización
        futures = {executor.submit(analyze, pid): pid for pid in pids}
        for future in as_completed(futures):
            try:
                data = future.result()
                print(data)
            except Exception as e:
                print(f"Error: {e}")
```

##### `multiprocessing.Manager`

Crea un proceso servidor que mantiene objetos Python compartidos. Los demás procesos interactúan
a través de **objetos proxy** que envían mensajes IPC (Unix domain socket):

```python
from multiprocessing import Process, Manager

def worker(shared_dict, pid):
    shared_dict[pid] = {'cpu': 45.2, 'mem': 128}

if __name__ == '__main__':
    with Manager() as manager:
        snapshot = manager.dict()  # Dict compartido via proxy
        procs = [Process(target=worker, args=(snapshot, i)) for i in range(4)]
        for p in procs: p.start()
        for p in procs: p.join()
        print(dict(snapshot))
```

**Gotcha — mutación anidada:**

```python
# MAL — la modificación al dict anidado NO se propaga a través del proxy
snapshot['process_1'] = {'cpu': 10, 'threads': []}
snapshot['process_1']['cpu'] = 20  # ¡NO se actualiza en el Manager!

# BIEN — reasignar el objeto completo
temp = snapshot['process_1']
temp['cpu'] = 20
snapshot['process_1'] = temp  # Esto SÍ notifica al proxy
```

**Manager vs Value/Array vs SharedMemory:**

| | Manager | Value/Array | SharedMemory/mmap |
|---|---------|------------|-------------------|
| Tipos de datos | Cualquier Python (dict, list, etc.) | Solo tipos C (int, float, char) | Bytes crudos |
| Velocidad | Lenta (IPC por socket) | Rápida (mmap directo) | Más rápida (acceso directo) |
| Sincronización | Incluida (proxy serializa) | Lock incluido (opcional) | Manual |
| Complejidad | Baja | Media | Alta |
| Uso ideal | Datos complejos, baja frecuencia | Valores simples, alta frecuencia | Alto rendimiento |

##### Primitivas de sincronización (multiprocessing)

Las mismas que en `threading`, pero inter-proceso:

- **`Lock`**: exclusión mutua básica entre procesos.
- **`RLock`**: reentrant — mismo proceso puede adquirir múltiples veces.
- **`Semaphore(N)`**: permite hasta N procesos simultáneos.
- **`BoundedSemaphore(N)`**: como Semaphore pero lanza error si se libera de más.
- **`Event`**: flag booleano, `.set()`, `.clear()`, `.wait()`, `.is_set()`.
- **`Condition`**: lock + wait/notify para coordinación compleja.
- **`Barrier(N)`**: todos N procesos deben llegar antes de continuar.

#### Ejemplo: Map-Reduce con Pool

```python
from multiprocessing import Pool
from functools import reduce
from collections import Counter

def count_words(text_chunk):
    """Map phase: count words in a chunk."""
    return Counter(text_chunk.lower().split())

def merge_counts(c1, c2):
    """Reduce phase: merge two counters."""
    c1.update(c2)
    return c1

if __name__ == '__main__':
    chunks = ["hello world hello", "world foo bar", "hello bar baz"]

    with Pool() as pool:
        # Map: distribute word counting across workers
        partial_counts = pool.map(count_words, chunks)

        # Reduce: merge all partial counts
        total = reduce(merge_counts, partial_counts)
        print(total)  # Counter({'hello': 3, 'world': 2, 'bar': 2, ...})
```

#### Errores Típicos

**❌ Manager overhead para operaciones frecuentes:**

```python
# MAL — cada acceso a shared_dict es una llamada IPC (lenta)
for i in range(1_000_000):
    shared_dict[f'key_{i}'] = i  # Un millón de llamadas IPC

# BIEN — acumular localmente y actualizar en batch
local_data = {f'key_{i}': i for i in range(1_000_000)}
shared_dict.update(local_data)  # Una sola llamada IPC
```

**❌ Nested pools:** Crear un Pool dentro de un worker de otro Pool puede causar deadlocks
(los workers del pool interno compiten por los mismos recursos del scheduler).

**❌ No manejar excepciones en workers:**

```python
# MAL — excepción silenciada
result = pool.apply_async(buggy_function, args=(data,))
# Si buggy_function lanza excepción, se pierde silenciosamente

# BIEN
result = pool.apply_async(buggy_function, args=(data,),
                          error_callback=lambda e: print(f"Error: {e}"))
# O usar result.get() que re-lanza la excepción
```

#### 📌 Conexión con tu TP1

Tu TP1 tomó un tradeoff consciente: `Manager.dict()` para el snapshot de procesos (datos complejos
anidados: dict de dicts con listas) y `multiprocessing.Value('d')` para los intervalos de refresco
(un solo float que se actualiza con alta frecuencia desde la TUI). El `Event` (`stop_event`) coordina
el shutdown limpio de los 7 analizadores.

#### Preguntas de Examen

1. **¿Cuál es la ventaja principal y la desventaja principal de `Manager().dict()` vs shared memory pura?**
   <details><summary>Respuesta</summary>
   **Ventaja**: puede contener cualquier tipo de dato Python nativo (dicts anidados, listas, strings,
   objetos) de forma transparente. No requiere serialización manual ni diseño de layouts binarios.

   **Desventaja**: cada acceso (lectura o escritura) pasa por IPC — el Manager mantiene un proceso
   servidor y los clientes se comunican vía Unix domain sockets con pickle. Esto es MUCHO más lento
   que acceder directamente a memoria compartida (mmap/Value/Array).
   </details>

2. **¿Por qué `pool.imap_unordered()` es más rápido que `pool.map()` para procesar resultados?**
   <details><summary>Respuesta</summary>
   `map()` espera a que TODAS las tareas terminen y retorna los resultados en el orden original.
   `imap_unordered()` es un iterador lazy que yield-ea cada resultado apenas el worker lo completa,
   sin importar el orden. Esto permite comenzar a procesar resultados mientras otros workers aún
   están computando, reduciendo el tiempo total de espera.
   </details>

3. **Dado este código, ¿por qué la modificación anidada NO se refleja en otros procesos?**
   ```python
   d = manager.dict()
   d['stats'] = {'count': 0}
   d['stats']['count'] = 10
   ```
   <details><summary>Respuesta</summary>
   Porque `d['stats']` retorna un dict Python NORMAL (no un proxy). La modificación `['count'] = 10`
   se hace sobre esta copia local, no sobre el objeto en el servidor Manager. Para que el cambio
   se propague, hay que reasignar el objeto completo: `temp = d['stats']; temp['count'] = 10;
   d['stats'] = temp`. La asignación a `d['stats']` sí pasa por el proxy y notifica al servidor.
   </details>

4. **¿Cuántos workers debería tener un Pool para tareas CPU-bound? ¿Y para I/O-bound?**
   <details><summary>Respuesta</summary>
   CPU-bound: `os.cpu_count()` workers (uno por core lógico). Más workers causarían context switching
   sin beneficio, degradando el rendimiento. I/O-bound: más workers que cores, ya que la mayoría
   estarán bloqueados esperando I/O. Un ratio de 2-5x `cpu_count()` es común, pero para I/O-bound
   es mejor usar `ThreadPoolExecutor` que tiene menor overhead que procesos.
   </details>

---

## Clase 10 — Threading

#### Conceptos Clave

##### Thread vs Proceso

| Aspecto | Thread | Proceso |
|---------|--------|---------|
| Espacio de memoria | Compartido (heap, globals) | Independiente (COW) |
| Stack | Propio | Propio |
| GIL | Compartido (un thread ejecuta a la vez) | Propio (paralelismo real) |
| Creación | Rápida (~microsegundos) | Lenta (~milisegundos) |
| Comunicación | Directa (variables compartidas) | IPC (pipes, queues, shm) |
| Crash | Puede afectar todo el proceso | Aislado |
| Uso ideal | I/O-bound | CPU-bound |

##### GIL — Global Interpreter Lock

El GIL es un **mutex** interno de CPython que permite que solo UN thread ejecute bytecode Python
a la vez. Existe para proteger el reference counting (manejo de memoria) de CPython.

**Impacto en CPU-bound:**

```python
import threading, time

def cpu_intensive():
    total = sum(i * i for i in range(10_000_000))

# Serial: 2 seconds
start = time.time()
cpu_intensive()
cpu_intensive()
print(f"Serial: {time.time() - start:.2f}s")

# Threads: ~2 seconds (NO mejora, puede ser PEOR por context switching)
start = time.time()
t1 = threading.Thread(target=cpu_intensive)
t2 = threading.Thread(target=cpu_intensive)
t1.start(); t2.start()
t1.join(); t2.join()
print(f"Threaded: {time.time() - start:.2f}s")
```

**Impacto en I/O-bound:** El GIL se **libera** durante operaciones de I/O (red, disco, sleep).
Mientras un thread espera I/O, otro puede ejecutar Python:

```python
# ESTO SÍ ES MÁS RÁPIDO con threads
import urllib.request

def download(url):
    urllib.request.urlopen(url).read()

urls = ['http://example.com'] * 10

# Serial: ~5 seconds (cada download espera)
# Threaded: ~0.5 seconds (downloads concurrentes mientras esperan I/O)
```

**Python 3.13+ free-threaded:** Modo experimental (PEP 703/779) que elimina el GIL. Activable
con `--disable-gil`. Permite paralelismo real con threads, pero es experimental y puede romper
extensiones C existentes.

##### `threading.Thread`

```python
import threading

def worker(name, iterations):
    for i in range(iterations):
        print(f"{name}: {i}")

# Basic usage
t = threading.Thread(target=worker, args=('Worker-1', 5), daemon=True)
t.start()
t.join(timeout=10)

# Subclassing
class MyThread(threading.Thread):
    def run(self):
        # Override run() with the thread's work
        self.result = expensive_computation()

t = MyThread()
t.start()
t.join()
print(t.result)
```

##### `threading.local()` — Storage por thread

Cada thread ve sus propias variables, sin interferencia:

```python
data = threading.local()

def worker(user_id):
    data.user_id = user_id  # Each thread has its own data.user_id
    process_request()

def process_request():
    print(f"Processing for user {data.user_id}")  # Thread-safe access
```

##### `queue.Queue` — Cola thread-safe

```python
import queue
import threading

q = queue.Queue(maxsize=100)  # Buffer acotado

def producer():
    for item in range(10):
        q.put(item)           # Bloquea si la cola está llena
    q.put(None)               # Sentinel

def consumer():
    while True:
        item = q.get()         # Bloquea si la cola está vacía
        if item is None:
            break
        print(f"Got: {item}")
        q.task_done()          # Señala que el item fue procesado

t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start(); t2.start()
q.join()  # Espera que todos los items sean procesados (task_done)
```

##### `concurrent.futures.ThreadPoolExecutor`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

def fetch(url):
    return urllib.request.urlopen(url).read()

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch, url): url for url in urls}
    for future in as_completed(futures):
        url = futures[future]
        try:
            data = future.result()
            print(f"{url}: {len(data)} bytes")
        except Exception as e:
            print(f"{url}: error {e}")
```

##### Atomicidad — NADA es atómico

```python
counter = 0

def increment():
    global counter
    counter += 1  # NO es atómico — son 3 operaciones de bytecode:
                  # 1. LOAD_GLOBAL counter  (lee 5)
                  # 2. LOAD_CONST 1
                  # 3. BINARY_ADD           (calcula 6)
                  # Si otro thread lee counter entre 1 y 4, lee 5 también
                  # 4. STORE_GLOBAL counter (guarda 6)
                  # Ambos guardan 6 en vez de 7 → incremento perdido
```

#### Errores Típicos

**❌ Usar threads para CPU-bound:**

```python
# MAL — threads para cálculo intensivo (el GIL serializa la ejecución)
threads = [threading.Thread(target=cpu_task) for _ in range(4)]
# No hay speedup, puede ser más lento que serial

# BIEN — usar multiprocessing para CPU-bound
from multiprocessing import Pool
with Pool(4) as pool:
    pool.map(cpu_task, data)  # Paralelismo real
```

**❌ Asumir que `counter += 1` es atómico:**

```python
# MAL — race condition
counter = 0
for _ in range(100):
    threading.Thread(target=lambda: globals().__setitem__('counter', counter+1)).start()
# Resultado impredecible (puede ser < 100)

# BIEN — usar Lock
lock = threading.Lock()
def safe_increment():
    global counter
    with lock:
        counter += 1
```

#### 📌 Conexión con tu TP1

Tu TP1 eligió `multiprocessing` sobre `threading` conscientemente. El parseo de archivos en `/proc`
es CPU-bound (procesamiento intensivo de texto y números), donde el GIL de threads impediría
paralelismo real. Además, tu analizador de threads inspecciona los LWPs (Light Weight Processes)
de cada proceso leyendo `/proc/[pid]/task/[tid]/`, mapeando el concepto teórico de threads del
kernel a datos observables.

#### Preguntas de Examen

1. **¿Por qué el GIL no afecta significativamente el rendimiento de una aplicación que descarga archivos por red con threads?**
   <details><summary>Respuesta</summary>
   Porque CPython libera el GIL automáticamente antes de ejecutar operaciones de I/O bloqueantes
   (syscalls de red, disco, sleep). Mientras un thread espera la respuesta del servidor (I/O-bound),
   el GIL está libre y otro thread puede ejecutar Python. Como el cuello de botella es la latencia
   de red (no la CPU), los threads proporcionan concurrencia efectiva.
   </details>

2. **Demostrá por qué `x += 1` no es atómico en Python, describiendo los pasos de bytecode.**
   <details><summary>Respuesta</summary>
   `x += 1` se compila en 3+ instrucciones de bytecode:
   1. `LOAD_GLOBAL x` — lee el valor actual de x (ej: 5)
   2. `LOAD_CONST 1` — carga la constante 1
   3. `BINARY_ADD` — calcula 5 + 1 = 6
   4. `STORE_GLOBAL x` — guarda 6 en x

   Si entre los pasos 1 y 4 ocurre un context switch a otro thread que también ejecuta `x += 1`,
   ambos leen 5, ambos calculan 6, y ambos guardan 6. Se perdió un incremento.
   </details>

3. **¿Cuándo usarías `ThreadPoolExecutor` y cuándo `ProcessPoolExecutor`?**
   <details><summary>Respuesta</summary>
   `ThreadPoolExecutor`: tareas I/O-bound (descargas, consultas a DB, llamadas a APIs, lectura de
   archivos). Los threads tienen menor overhead de creación y comunicación directa vía memoria.

   `ProcessPoolExecutor`: tareas CPU-bound (cálculos, parsing, compresión, procesamiento de imágenes).
   Los procesos tienen su propio GIL, logrando paralelismo real en múltiples cores.
   </details>

4. **¿Qué es `threading.local()` y qué problema resuelve?**
   <details><summary>Respuesta</summary>
   `threading.local()` crea un objeto donde cada thread ve sus propios atributos, independientes de
   los demás threads. Resuelve el problema de pasar contexto (ej: user_id, session, database
   connection) a través de una cadena de funciones sin pasar argumentos explícitamente, manteniendo
   aislamiento entre threads sin necesidad de locks.
   </details>

---

## Clase 11 — Sincronización

#### Conceptos Clave

##### Race Conditions

Una race condition ocurre cuando el resultado de un programa depende del **orden de ejecución** de
threads/procesos concurrentes, que es impredecible. El scheduler del OS decide cuándo cambiar de
contexto.

```python
# Race condition: resultado impredecible
counter = 0
lock = threading.Lock()

def unsafe_increment():
    global counter
    temp = counter      # Thread A lee 5
    # ← context switch! Thread B lee 5 también
    counter = temp + 1  # Thread A escribe 6, Thread B también escribe 6
                        # Se perdió un incremento

def safe_increment():
    global counter
    with lock:          # Solo un thread a la vez
        counter += 1    # Sección crítica protegida
```

##### `threading.Lock` — Exclusión mutua básica

```python
lock = threading.Lock()

# Uso con context manager (SIEMPRE preferir esto)
with lock:
    # Critical section — solo un thread a la vez
    shared_resource.modify()

# Uso manual (más propenso a errores)
lock.acquire()
try:
    shared_resource.modify()
finally:
    lock.release()  # SIEMPRE liberar, incluso con excepción

# Non-blocking
if lock.acquire(blocking=False):
    try:
        shared_resource.modify()
    finally:
        lock.release()
else:
    print("Resource busy, trying later")

# Con timeout
if lock.acquire(timeout=5.0):
    try:
        shared_resource.modify()
    finally:
        lock.release()
```

**Peligro:** Si un thread adquiere un Lock y intenta adquirirlo de nuevo → **DEADLOCK** (se
bloquea a sí mismo esperando liberarse).

##### `threading.RLock` — Lock Reentrante

Un RLock permite que el **mismo thread** lo adquiera múltiples veces sin deadlock. Debe liberarlo
el mismo número de veces.

```python
rlock = threading.RLock()

def outer():
    with rlock:
        inner()  # inner() también adquiere rlock — OK con RLock

def inner():
    with rlock:  # Mismo thread, segunda adquisición — no bloquea
        do_work()
```

Útil para funciones recursivas o métodos que se llaman entre sí, todos protegiendo el mismo recurso.

##### `threading.Semaphore(N)` — Control de concurrencia

Un semáforo mantiene un contador interno inicializado en N. `acquire()` decrementa (bloquea si
llegaría a 0). `release()` incrementa.

```python
# Limitar a 3 conexiones simultáneas a la base de datos
db_semaphore = threading.Semaphore(3)

def query_db(sql):
    with db_semaphore:  # Solo 3 threads pueden estar aquí a la vez
        conn = get_connection()
        return conn.execute(sql)
```

**`BoundedSemaphore(N)`**: como Semaphore pero lanza `ValueError` si se llama a `release()` más
veces que `acquire()`. Detecta bugs de programación.

##### `threading.Event` — Señalización booleana

```python
start_event = threading.Event()

def worker():
    print("Waiting for start signal...")
    start_event.wait()       # Bloquea hasta que alguien llame set()
    print("Started!")

# Otro thread:
start_event.set()            # Desbloquea a TODOS los que esperan
start_event.clear()          # Reset para reutilizar
start_event.is_set()         # Check sin bloquear
```

Ideal para señales one-shot: "la inicialización terminó", "hay que apagar", "los datos están listos".

##### `threading.Condition` — Wait/Notify

Combina un Lock con la capacidad de que threads **esperen** hasta que una condición se cumpla:

```python
import threading
from collections import deque

buffer = deque(maxlen=10)
condition = threading.Condition()

def producer():
    for i in range(20):
        with condition:
            while len(buffer) >= 10:     # Buffer lleno — esperar
                condition.wait()         # Libera lock, bloquea, re-adquiere al despertar
            buffer.append(i)
            condition.notify()           # Despertar a UN consumer

def consumer():
    while True:
        with condition:
            while len(buffer) == 0:      # Buffer vacío — esperar
                condition.wait()
            item = buffer.popleft()
            condition.notify()           # Despertar al producer
        process(item)
```

**⚠️ SIEMPRE `while`, NUNCA `if` antes de `wait()`:**

```python
# MAL — vulnerable a spurious wakeups y stolen conditions
with condition:
    if len(buffer) == 0:    # ← Solo chequea UNA vez
        condition.wait()
    item = buffer.popleft() # Puede fallar si otro thread consumió primero

# BIEN — re-chequea después de cada despertar
with condition:
    while len(buffer) == 0:  # ← Re-evalúa cada vez que despierta
        condition.wait()
    item = buffer.popleft()  # Garantizado que hay datos
```

##### `threading.Barrier(N)`

Bloquea hasta que N threads hayan llamado a `barrier.wait()`. Entonces TODOS continúan:

```python
barrier = threading.Barrier(4)  # Esperar a 4 threads

def worker(id):
    prepare_data(id)
    print(f"Worker {id} ready")
    barrier.wait()              # Todos esperan aquí
    print(f"Worker {id} GO!")   # Todos arrancan juntos
```

##### Deadlock

**Qué es:** Dos o más threads esperándose mutuamente, bloqueados para siempre.

**Ejemplo clásico:**

```python
lock_a = threading.Lock()
lock_b = threading.Lock()

def thread_1():
    with lock_a:             # Adquiere A
        time.sleep(0.1)
        with lock_b:         # Intenta adquirir B → BLOQUEADO (thread_2 tiene B)
            do_work()

def thread_2():
    with lock_b:             # Adquiere B
        time.sleep(0.1)
        with lock_a:         # Intenta adquirir A → BLOQUEADO (thread_1 tiene A)
            do_work()

# Thread 1 tiene A, espera B. Thread 2 tiene B, espera A. → DEADLOCK
```

**Condiciones de Coffman** (las 4 deben cumplirse para que haya deadlock):

1. **Exclusión mutua**: el recurso no es compartible simultáneamente.
2. **Hold and wait**: un thread retiene un recurso mientras espera otro.
3. **No preemption**: no se pueden forzar la liberación de recursos.
4. **Espera circular**: A espera a B, B espera a A (ciclo).

**Prevención:**

| Estrategia | Cómo |
|-----------|------|
| Orden de locks | Siempre adquirir locks en el mismo orden global |
| Timeout | `lock.acquire(timeout=5)` — desistir si tarda |
| Try-lock | `acquire(blocking=False)` — liberar todo y reintentar |
| Lock único | Usar un solo lock grueso (menos concurrencia pero sin deadlock) |

##### Livelock y Starvation

- **Livelock**: Los threads no están bloqueados — responden activamente al otro — pero no hacen
  progreso. Como dos personas en un pasillo que se mueven al mismo lado indefinidamente.
- **Starvation**: Un thread nunca obtiene el recurso porque otros se lo llevan constantemente.
  Puede pasar con prioridades desbalanceadas o fairness pobre en el scheduler.

#### Ejemplo: Bounded Buffer con Condition

```python
import threading
from collections import deque

class BoundedBuffer:
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)
        self.capacity = capacity
        self.condition = threading.Condition()

    def put(self, item):
        with self.condition:
            while len(self.buffer) >= self.capacity:
                self.condition.wait()  # Wait until space available
            self.buffer.append(item)
            self.condition.notify_all()  # Wake consumers

    def get(self):
        with self.condition:
            while len(self.buffer) == 0:
                self.condition.wait()  # Wait until data available
            item = self.buffer.popleft()
            self.condition.notify_all()  # Wake producers
            return item
```

#### Errores Típicos

**❌ `if` en vez de `while` antes de `Condition.wait()`:**

```python
# MAL — puede consumir de un buffer vacío
if buffer_empty:
    condition.wait()
item = buffer.pop()  # IndexError si otro thread consumió primero

# BIEN
while buffer_empty:
    condition.wait()
item = buffer.pop()  # Garantizado que hay datos
```

**❌ Adquirir locks en distinto orden:**

```python
# Thread A: lock_1 → lock_2
# Thread B: lock_2 → lock_1
# → DEADLOCK

# BIEN: SIEMPRE el mismo orden global
# Thread A: lock_1 → lock_2
# Thread B: lock_1 → lock_2
```

**❌ No liberar locks con excepciones:**

```python
# MAL — si do_work() lanza excepción, el lock queda adquirido
lock.acquire()
do_work()  # Si falla...
lock.release()  # ...nunca se ejecuta → otros threads bloqueados

# BIEN — context manager SIEMPRE libera
with lock:
    do_work()
```

#### 📌 Conexión con tu TP1

Tu TP1 usa `multiprocessing.Event` (`stop_event`) como mecanismo de shutdown coordinado. Cuando
el signal handler recibe SIGTERM/SIGINT, llama a `stop_event.set()`. Todos los 7 analizadores
daemon chequean `stop_event.is_set()` en cada iteración de su loop y salen limpiamente. Es el
patrón correcto: una señal booleana simple que se propaga a múltiples consumidores sin race
conditions.

#### Preguntas de Examen

1. **¿Por qué se DEBE usar `while` y no `if` antes de `Condition.wait()`?**
   <details><summary>Respuesta</summary>
   Dos razones: (1) **Spurious wakeups**: el sistema operativo puede despertar un thread sin que
   nadie haya llamado `notify()`. (2) **Stolen conditions**: si `notify_all()` despierta a
   múltiples threads, el primero en re-adquirir el lock puede consumir el recurso; cuando el
   segundo despierta, el recurso ya no está. El `while` fuerza una re-evaluación de la condición
   después de cada despertar, garantizando que solo se procede cuando la condición es verdadera.
   </details>

2. **¿Qué es un deadlock y cómo lo prevendrías con la estrategia de "lock ordering"?**
   <details><summary>Respuesta</summary>
   Un deadlock es una situación donde dos o más threads están bloqueados permanentemente, cada uno
   esperando un recurso que otro tiene. La prevención por "lock ordering" consiste en asignar un
   orden global numérico a todos los locks del sistema (ej: lock_A=1, lock_B=2) y SIEMPRE
   adquirirlos en ese orden. Esto rompe la condición de "espera circular" de Coffman, haciendo
   imposible que se forme un ciclo de dependencias.
   </details>

3. **¿Cuál es la diferencia entre un Lock y un Semaphore? Dá un ejemplo de cuándo usarías cada uno.**
   <details><summary>Respuesta</summary>
   Un Lock permite que exactamente UN thread entre a la sección crítica (exclusión mutua binaria).
   Un Semaphore(N) permite que hasta N threads accedan simultáneamente.

   Lock: proteger la escritura a un archivo de log (solo uno puede escribir a la vez).
   Semaphore(5): limitar las conexiones simultáneas a una base de datos que soporta máximo 5
   conexiones concurrentes.
   </details>

4. **Explicá las 4 condiciones de Coffman necesarias para que ocurra un deadlock.**
   <details><summary>Respuesta</summary>
   1. **Exclusión mutua**: al menos un recurso no puede ser compartido simultáneamente.
   2. **Hold and wait**: un thread retiene al menos un recurso mientras espera adquirir otro.
   3. **No preemption**: los recursos no pueden ser forzados a liberarse — solo el thread que los
      tiene puede liberarlos voluntariamente.
   4. **Espera circular**: existe un ciclo de threads donde cada uno espera un recurso del siguiente
      (A→B→C→A).

   Si se rompe CUALQUIERA de las 4 condiciones, el deadlock es imposible.
   </details>

5. **¿Cuál es la diferencia entre un RLock y un Lock normal?**
   <details><summary>Respuesta</summary>
   Un Lock normal solo puede ser adquirido una vez — si el mismo thread intenta adquirirlo de nuevo,
   se bloquea a sí mismo (deadlock). Un RLock (Reentrant Lock) permite que el MISMO thread lo
   adquiera múltiples veces sin bloquearse, manteniendo un contador de adquisiciones. Debe ser
   liberado el mismo número de veces. Útil para funciones recursivas o métodos que se llaman entre
   sí, todos necesitando proteger el mismo recurso compartido.
   </details>

---

## Cheat Sheet Final

### Mecanismos IPC

| Mecanismo | Velocidad | Complejidad | Mejor para | Limitaciones |
|-----------|-----------|-------------|------------|--------------|
| `os.pipe()` | Alta | Media | Pipeline padre-hijo unidireccional | Solo bytes, unidireccional, requiere fork |
| `multiprocessing.Queue` | Media | Baja | Producer-consumer multiproceso | Overhead de pickle + locks |
| `multiprocessing.Pipe` | Alta | Baja | 2 procesos bidireccional | Solo 2 endpoints |
| `mmap` anónimo | Muy alta | Alta | Datos binarios entre padre-hijo | Requiere struct, sin sync |
| `SharedMemory` | Muy alta | Alta | Datos binarios entre procesos sin parentesco | Requiere struct, sin sync, unlink manual |
| `Value` / `Array` | Alta | Baja | Valores simples compartidos | Solo tipos C |
| `Manager.dict()` | Baja | Muy baja | Datos complejos compartidos | IPC overhead significativo |

### Primitivas de Sincronización

| Primitiva | Cuándo usar | Patrón |
|-----------|-------------|--------|
| `Lock` | Exclusión mutua simple (1 thread) | `with lock: modify()` |
| `RLock` | Funciones recursivas que comparten lock | `with rlock: recurse()` |
| `Semaphore(N)` | Limitar acceso a N slots | `with sem: use_resource()` |
| `BoundedSemaphore(N)` | Semaphore + detección de bugs | `with bsem: use_resource()` |
| `Event` | Señal booleana one-shot | `event.wait()` / `event.set()` |
| `Condition` | Espera compleja con predicado | `while not ready: cond.wait()` |
| `Barrier(N)` | Sincronizar inicio de N threads | `barrier.wait()` |

### Proceso vs Thread

| Aspecto | Proceso (`multiprocessing`) | Thread (`threading`) |
|---------|---------------------------|---------------------|
| Memoria | Espacios separados (COW) | Espacio compartido |
| GIL | Cada uno tiene el suyo | Comparten uno |
| CPU-bound | ✅ Paralelismo real | ❌ Serializado por GIL |
| I/O-bound | ✅ Funciona pero pesado | ✅ Ideal (GIL se libera) |
| Creación | ~ms (lenta) | ~μs (rápida) |
| Comunicación | IPC (pipes, queues, shm) | Variables compartidas |
| Crash aislado | ✅ Sí | ❌ No — afecta todo |

### Referencia de Señales

| Señal | Nro | Default | Capturable | Uso común |
|-------|-----|---------|-----------|-----------|
| `SIGHUP` | 1 | Terminar | ✅ | Reload de configuración |
| `SIGINT` | 2 | Terminar | ✅ | Ctrl+C |
| `SIGKILL` | 9 | Terminar | ❌ | Matar forzosamente |
| `SIGUSR1` | 10 | Terminar | ✅ | Custom (dump estado) |
| `SIGUSR2` | 12 | Terminar | ✅ | Custom (toggle feature) |
| `SIGPIPE` | 13 | Terminar | ✅ | Write a pipe roto |
| `SIGALRM` | 14 | Terminar | ✅ | Timer expirado |
| `SIGTERM` | 15 | Terminar | ✅ | Terminación amable |
| `SIGCHLD` | 17 | Ignorar | ✅ | Hijo cambió estado |
| `SIGCONT` | 18 | Continuar | ✅ | Reanudar proceso |
| `SIGSTOP` | 19 | Pausar | ❌ | Pausar forzosamente |

### Archivos de `/proc`

| Path | Contenido | Formato |
|------|-----------|---------|
| `/proc/[pid]/stat` | Estado compacto del proceso | Línea con campos separados por espacio |
| `/proc/[pid]/status` | Estado legible del proceso | `Clave:\tValor` por línea |
| `/proc/[pid]/cmdline` | Línea de comando original | Args separados por `\0` |
| `/proc/[pid]/maps` | Mapeados de memoria | Rangos de direcciones por línea |
| `/proc/[pid]/fd/` | File descriptors abiertos | Symlinks a archivos/sockets/pipes |
| `/proc/[pid]/task/` | Threads (LWPs) del proceso | Subdirectorio por TID |
| `/proc/stat` | CPU del sistema | Ticks user/nice/system/idle |
| `/proc/meminfo` | Memoria del sistema | `MemTotal`, `MemFree`, etc. |
| `/proc/loadavg` | Load average | 3 floats + procesos activos |

### Funciones `os` para procesos

| Función | Descripción |
|---------|-------------|
| `os.fork()` | Duplica proceso. Retorna 0 (hijo) o PID hijo (padre) |
| `os.exec*(...)` | Reemplaza imagen del proceso. No retorna si éxito |
| `os.wait()` | Espera a cualquier hijo. Retorna `(pid, status)` |
| `os.waitpid(pid, opts)` | Espera a hijo específico. `WNOHANG` = no bloquear |
| `os._exit(code)` | Sale sin cleanup (para hijos forkeados) |
| `os.kill(pid, sig)` | Envía señal a un proceso |
| `os.pipe()` | Crea pipe. Retorna `(read_fd, write_fd)` |
| `os.dup2(old, new)` | Redirige `new` hacia `old` |
| `os.mkfifo(path)` | Crea named pipe (FIFO) |
| `os.getpid()` | PID del proceso actual |
| `os.getppid()` | PID del proceso padre |

### Patrones clave

**Fork-Exec-Wait:**
```python
pid = os.fork()
if pid == 0:
    os.execlp('cmd', 'cmd', 'arg1')
    os._exit(1)  # Solo si exec falla
os.waitpid(pid, 0)
```

**Self-Pipe (señales seguras):**
```python
r, w = os.pipe()  # Non-blocking w
signal.set_wakeup_fd(w)
signal.signal(signal.SIGTERM, lambda s, f: None)
# Main loop: select([r, ...]) → read(r) → process signal
```

**Producer-Consumer (Condition):**
```python
with condition:
    while not data_available:
        condition.wait()
    item = buffer.pop()
# Producer: buffer.append(x); condition.notify()
```

**Graceful Shutdown (Event):**
```python
stop = multiprocessing.Event()
signal.signal(signal.SIGTERM, lambda s, f: stop.set())
while not stop.is_set():
    do_work()
    stop.wait(timeout=interval)
```

**Comandos Docker esenciales:**
```bash
docker build -t app .              # Construir imagen
docker run -d -p 8080:80 app       # Ejecutar en background
docker compose up -d               # Levantar servicios
docker compose down                # Bajar servicios
docker exec -it container bash     # Shell interactivo
docker logs -f container           # Logs en tiempo real
docker system prune -a             # Limpiar todo
```

## Clase 07 — MMAP y Memoria Compartida

#### Conceptos Clave

##### Memory-mapped I/O
El mapeo de memoria (`mmap`) proyecta el contenido de un archivo (o un espacio de memoria anónimo) directamente en el espacio de direcciones virtuales de un proceso. El sistema operativo maneja las transferencias de disco bajo demanda utilizando la paginación. Esto evita las llamadas al sistema `read()` y `write()` y el copiado extra de memoria ("zero-copy"), permitiendo accesos muy eficientes tratándolo como un simple array de bytes.

##### `mmap.mmap()` en Python
Se puede mapear un archivo abierto o pedir memoria anónima respaldada por la swap.
- **File-backed**: `mmap.mmap(fileno, length, access=...)`. Modificar la memoria modifica el archivo.
- **Anonymous**: `mmap.mmap(-1, size)`. Se crea con file descriptor `-1`. Al usarse antes de un `fork()`, el padre y los hijos comparten las mismas páginas físicas, lo que lo hace un mecanismo IPC excelente y muy rápido.

##### Modos de Acceso
- `ACCESS_READ`: Solo lectura, produce error si se intenta escribir.
- `ACCESS_WRITE`: Lectura y escritura. Las escrituras modifican el buffer subyacente.
- `ACCESS_COPY`: Copy-On-Write (COW). Las escrituras afectan solo la memoria del proceso local y no se reflejan en el archivo ni a otros procesos.

##### Módulo `struct`
Como `mmap` expone bytes en crudo, es necesario un mecanismo para estructurar los datos binarios. El módulo `struct` empaca y desempaca tipos básicos de Python en representación de C.
- Caracteres de formato: `i` (int), `d` (double), `f` (float), `Q` (unsigned long long), `s` (bytes/string).
- Orden de bytes (Endianness): `<` (Little Endian), `>` (Big Endian), `!` (Network/Big Endian).
Para compartir datos, se suele diseñar un layout fijo: un bloque inicial ("header") seguido de bloques de registros ("fixed-size records").

##### `multiprocessing.shared_memory` (Python 3.8+)
Proporciona memoria compartida persistente con nombre (POSIX shared memory). A diferencia de mmap anónimo que requiere relación de parentesco, SharedMemory permite conectar procesos totalmente independientes por nombre. Reside típicamente en `/dev/shm` en Linux.
- `.close()`: cierra el acceso local.
- `.unlink()`: marca el segmento para eliminación en el OS. Si no se invoca, la memoria queda ocupada (fuga).

##### `multiprocessing.Value` y `Array`
Envolturas sobre memoria compartida con soporte incorporado de bloqueos (Locks). Son útiles para valores individuales o arreglos simples limitados a tipos de C, pero al tener locks internos tienen un overhead de rendimiento en escenarios de alta concurrencia.

##### Sincronización
La memoria compartida plana (`mmap` o `SharedMemory`) NO incluye sincronización implícita. Si varios procesos leen y escriben simultáneamente sin un Lock o Semáforo explícito, ocurrirá corrupción de datos (race conditions).

#### Ejemplo

```python
import mmap
import os
import struct

# Record layout: [Status: int] [Value: double] -> 4 bytes + 8 bytes = 12 bytes
RECORD_FORMAT = "<id"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)

# Create an anonymous mmap before fork
mem = mmap.mmap(-1, RECORD_SIZE)

# Pack initial values
mem.write(struct.pack(RECORD_FORMAT, 1, 0.0))

pid = os.fork()

if pid == 0:
    # Child process
    mem.seek(0)
    # Read, update and pack back (Warning: no lock here, just for example)
    status, val = struct.unpack(RECORD_FORMAT, mem.read(RECORD_SIZE))
    mem.seek(0)
    mem.write(struct.pack(RECORD_FORMAT, status, val + 42.5))
    os._exit(0)
else:
    # Parent process
    os.waitpid(pid, 0)
    mem.seek(0)
    status, final_val = struct.unpack(RECORD_FORMAT, mem.read(RECORD_SIZE))
    print(f"Parent reads: {final_val}")  # Will print 42.5
    mem.close()
```

#### Errores Típicos

**❌ Olvidar sincronización en memoria compartida:**
```python
# MAL - Race condition al actualizar contador
val = struct.unpack('<i', mem[:4])[0]
mem[:4] = struct.pack('<i', val + 1)
```

**✅ Proteger acceso con un mecanismo adecuado:**
```python
# BIEN - Mutex para asegurar atomicidad
with lock:
    val = struct.unpack('<i', mem[:4])[0]
    mem[:4] = struct.pack('<i', val + 1)
```

**❌ Confundir `close()` y `unlink()` en SharedMemory:**
Si usas `multiprocessing.shared_memory`, llamar solo a `close()` deja el archivo en `/dev/shm`. El último proceso debe llamar a `unlink()` para liberar los recursos del sistema operativo.

#### 📌 Conexión con tu TP1

En tu TP1, utilizaste de manera avanzada `mmap` anónimo estructurado con el módulo `struct` para almacenar contadores estadísticos muy rápidos que los analyzers llenan. Además, empleaste `multiprocessing.Value('d')` para compartir las variables simples como los intervalos de refresco con acceso seguro, aprovechando la versatilidad de la API para mantener los paneles de la TUI actualizados de forma coordinada.

#### Preguntas de Examen

1. **¿Qué ventaja de rendimiento ofrece `mmap` respecto a un archivo regular leído con `read()` y `write()`?**
   <details><summary>Respuesta</summary>
   `mmap` utiliza "zero-copy". Al llamar `read()`, los datos se copian del disco a un buffer del kernel y luego al espacio del proceso. Con `mmap`, el OS mapea las páginas del archivo directamente en la RAM virtual del proceso. El proceso accede como un array en memoria sin llamadas al sistema (`syscalls`) repetitivas, mejorando el rendimiento para lecturas aleatorias o acceso intensivo.
   </details>

2. **¿Por qué un `mmap` anónimo funciona para IPC entre padre e hijo pero no entre procesos independientes?**
   <details><summary>Respuesta</summary>
   El `mmap` anónimo (`fd=-1`) se asigna en la memoria del proceso padre. Al hacer `fork()`, el hijo hereda los descriptores y el mapa de memoria. Las páginas marcadas como compartidas permiten la comunicación entre ellos. Como no existe en el filesystem ni tiene un nombre global, procesos sin parentesco no tienen manera de localizar o adjuntarse a ese bloque de memoria.
   </details>

3. **¿Cuál es la función del caracter `<` al usar `struct.pack('<i', valor)`?**
   <details><summary>Respuesta</summary>
   Determina el Endianness (orden de bytes) de los datos, en este caso Little Endian (el byte menos significativo va primero). Es fundamental fijar un Endianness explícito al compartir datos a bajo nivel o guardar en archivos binarios, para asegurar que el proceso lector interprete los bits de la misma forma, independientemente de la arquitectura del procesador.
   </details>

4. **Si uso memoria compartida para variables críticas, ¿puedo confiar en que una asignación simple no tendrá problemas?**
   <details><summary>Respuesta</summary>
   No. La memoria plana no provee aislamiento ni sincronización atómica. Operaciones como leer-modificar-escribir pueden ser interrumpidas por el scheduler del sistema operativo, resultando en race conditions si dos procesos acceden a la vez. Siempre requiere primitivas de sincronización adicionales, como un Lock o Semáforo.
   </details>

---

## Clase 08 — Multiprocessing Fundamentos

#### Conceptos Clave

##### El GIL (Global Interpreter Lock) y la Concurrencia
En CPython, el GIL asegura que un solo thread ejecute bytecode de Python a la vez. Esto impide escalar en múltiples núcleos para tareas intensivas en CPU (CPU-bound). `multiprocessing` sortea el GIL creando múltiples procesos completos del sistema operativo, cada uno con su propio intérprete Python y su propia memoria, logrando verdadero paralelismo a expensas de mayor uso de recursos.

##### `multiprocessing.Process`
La unidad fundamental para ejecutar código en otro proceso.
- `start()`: lanza el proceso.
- `join(timeout)`: bloquea el proceso actual hasta que el hijo termine.
- `is_alive()`: devuelve True si sigue en ejecución.
- `terminate()`/`kill()`: termina forzosamente al proceso.

##### Start Methods (fork, spawn, forkserver)
El mecanismo de creación de procesos varía según el SO y configuración:
- `fork` (Default en Linux antiguo): clona el proceso usando el fork de POSIX. Rápido y aprovecha el COW, pero problemático si hay threads corriendo en el padre, pudiendo causar deadlocks internos.
- `spawn` (Default en Windows/macOS, Python 3.14+ en Linux): Inicia un intérprete de Python fresco desde cero. Todo debe ser importado y serializado. Es más seguro pero más lento. Exige que el entrypoint del módulo esté protegido con `if __name__ == '__main__':`.
- `forkserver`: un servidor que realiza el fork a demanda. Seguro y relativamente rápido.

##### Demonios (`daemon=True`)
Un proceso Python configurado como demonio se cerrará automáticamente en el momento en que el proceso padre termine, sin requerir una espera limpia. Atención: este concepto en Python es distinto a un demonio de Unix. Los procesos daemon de Python no pueden spawnear hijos.

##### Mecanismos de Comunicación Básicos
Al no compartir memoria por defecto, `multiprocessing` provee estructuras abstraídas:
- `Queue`: Cola FIFO segura para IPC (serializa internamente con Pickle). Se usan los métodos `put()` y `get()`. El patrón de cierre seguro utiliza un valor "centinela" (sentinel o Poison Pill).
- `Pipe`: Retorna dos extremos de conexión (`conn1`, `conn2`). Mucho más rápido para comunicación punto-a-punto estricta (2 procesos). Utiliza `send()` y `recv()`.

##### El Guardia `__main__` y Pickling
Con `spawn`, Python vuelve a importar el archivo principal. Sin `if __name__ == '__main__':`, se crearía un bucle recursivo infinito de creación de procesos. Además, todos los argumentos pasados a un `Process` o IPC deben ser *picklable* (serializables). Lambdas, sockets, o archivos abiertos (`file handles`) fallarán al ser serializados.

#### Ejemplo

```python
import multiprocessing
import time

def worker(task_queue, result_queue):
    """Worker loop processing tasks until poison pill (None) is found."""
    while True:
        task = task_queue.get()
        if task is None:  # Sentinel value (poison pill)
            break
        
        # Simulate CPU work
        result = task * task
        result_queue.put((task, result))

if __name__ == '__main__':
    # Mandatory guard for 'spawn' method
    tasks = multiprocessing.Queue()
    results = multiprocessing.Queue()
    
    # Start a daemon process
    p = multiprocessing.Process(target=worker, args=(tasks, results), daemon=True)
    p.start()
    
    # Enqueue work
    for i in range(5):
        tasks.put(i)
        
    # Send poison pill to stop worker cleanly
    tasks.put(None)
    
    # Collect results
    p.join()
    while not results.empty():
        print(f"Result: {results.get()}")
```

#### Errores Típicos

**❌ Olvidar el guardia `if __name__ == '__main__':`:**
```python
# MAL - Falla en Windows/macOS (spawn mode) y causará una explosión de procesos
p = multiprocessing.Process(target=func)
p.start() 
```

**❌ Pasar objetos no serializables:**
```python
# MAL - Los file objects o sockets no se pueden picklear
f = open("log.txt", "w")
p = multiprocessing.Process(target=func, args=(f,))
p.start() # Raise TypeError: cannot pickle '_io.TextIOWrapper' object
```

#### 📌 Conexión con tu TP1

Tu monitor del TP1 debía hacer parseo constante y estructurado de los pseudoarchivos en `/proc` (archivos como `/proc/[pid]/stat`). Esta tarea requiere un parsing intensivo a nivel CPU (split, formateo de números, procesamiento de secuencias string). Para evitar el cuello de botella del GIL en tu aplicación de curses interactiva, decidiste lanzar tus 7 analizadores mediante `multiprocessing.Process` marcados como `daemon=True`, logrando que la TUI fluya perfectamente independiente del trabajo duro que pasa en el background, superando las limitaciones naturales del GIL y parando el análisis con un simple `stop_event` de multiprocessing.

#### Preguntas de Examen

1. **¿Por qué `multiprocessing` es necesario en Python para ganar rendimiento en tareas CPU-bound?**
   <details><summary>Respuesta</summary>
   Debido al GIL (Global Interpreter Lock), los threads de Python no pueden ejecutar código Python en paralelo real, solo turnarse. `multiprocessing` sortea el GIL creando procesos completamente separados en el OS, donde cada uno tiene su propio GIL e intérprete de memoria y de ese modo aprovechan los múltiples núcleos físicos del procesador.
   </details>

2. **¿Qué significa que un start method sea `spawn` en vez de `fork` y qué implicancias tiene?**
   <details><summary>Respuesta</summary>
   `spawn` crea un proceso desde cero, carga el intérprete y ejecuta el script principal sin copiar la memoria del padre. Esto implica que es thread-safe y cross-platform, pero es más lento. Demanda estrictamente que el código global esté protegido por un bloque `if __name__ == '__main__':` para evitar que las re-importaciones lancen infinitos procesos recursivos. `fork` clona el estado de memoria con COW (más rápido), pero puede causar desastres si existen threads previos en el proceso padre.
   </details>

3. **¿Cuál es el patrón seguro para terminar un worker que lee de una `Queue`?**
   <details><summary>Respuesta</summary>
   Usar un valor centinela (Sentinel o "Poison Pill", comúnmente `None`). El worker contiene un loop que llama a `queue.get()`. Si el dato es la píldora envenenada, sale del bucle (`break`) y finaliza limpiamente su ejecución, lo que permite al padre invocar `join()` de forma segura, a diferencia de matarlo de golpe con `.terminate()`.
   </details>

4. **Si marco un proceso con `daemon=True`, ¿necesito llamar a `join()` obligatoriamente para limpiarlo?**
   <details><summary>Respuesta</summary>
   No. Un proceso daemon en Python se cerrará automáticamente de manera abrupta en el momento que el programa principal finalice (todos los hilos no-demonios hayan muerto). Es útil cuando su tarea de fondo ya no importa si la app cerró (fire-and-forget), aunque no hará limpiezas (flushing buffers) a su salida. 
   </details>

---

## Clase 09 — Multiprocessing Avanzado

#### Conceptos Clave

##### `multiprocessing.Pool`
Para ejecutar cientos de tareas en un número fijo de procesos (workers). La abstracción del pool maneja la creación de hijos y el balanceo.
- `Pool(N)`: Inicia un pool de N workers.
- `map(func, iterable)`: bloquea hasta terminar, retorna resultados en orden.
- `imap`/`imap_unordered`: iteradores perezosos (lazy), útil para grandes flujos de datos.
- `apply_async(func, args, callback=...)`: despacha una única tarea de manera asincrónica, retorna un objeto `AsyncResult` que permite consultar el estado o llamar `.get()` para recoger la respuesta.
- `maxtasksperchild`: recicla el worker después de ciertas tareas para prevenir fugas de memoria, forzando un reinicio limpio en cada iteración establecida.

##### `concurrent.futures.ProcessPoolExecutor`
API moderna estándar y de alto nivel.
- Usa `submit()` que devuelve un objeto `Future`.
- Proporciona utilidades como `as_completed(futures)` para procesar retornos al instante en que terminan en vez del orden en que se despacharon.

##### `multiprocessing.Manager`
Un Manager crea un **proceso servidor independiente** que mantiene las estructuras de datos, exponiéndolas a través de objetos "Proxy". Los demás procesos se comunican por red/sockets IPC con el Manager.
- Permite compartir `dict()`, `list()`, y `Namespace()`.
- Tiene un costo de serialización muy alto.
- **Nested Mutability Gotcha:** Si creás objetos anidados (`d['usuario']['edad'] = 25`), el proxy del Manager a menudo no detectará que la estructura interna fue modificada y el cambio no se replicará. El patrón correcto es reasignar: `tmp = d['usuario']; tmp['edad'] = 25; d['usuario'] = tmp`.

##### Primitivas de Sincronización Avanzadas
Son versiones apoyadas en Semáforos nombrados del OS para IPC:
- `Lock`: Exclusión mutua (mutex).
- `RLock`: Lock reentrante (el proceso que lo retiene puede volver a llamarlo sin bloquearse a sí mismo).
- `Semaphore(N)` / `BoundedSemaphore(N)`: Permite N accesos simultáneos.
- `Event`: Una bandera booleana global. `wait()` bloquea hasta que otro proceso invoque `set()`.
- `Condition`: Combinación de un Lock y una señal (Notificación), clave para modelos de Productor-Consumidor.
- `Barrier`: Detiene a un grupo de procesos hasta que N procesos lleguen a la barrera, y ahí los libera a todos a la vez.

#### Ejemplo

```python
import multiprocessing

def worker(shared_dict, key, lock):
    """Update a Manager dict protecting complex operations with a Lock."""
    with lock:
        # Dictionary from Manager is a proxy, changes are synced
        current = shared_dict.get(key, 0)
        # Re-assignment is safe for Manager proxies
        shared_dict[key] = current + 1

if __name__ == '__main__':
    # Context managers help with safe teardown
    with multiprocessing.Manager() as manager:
        d = manager.dict()
        lock = manager.Lock()
        
        processes = []
        for i in range(10):
            p = multiprocessing.Process(target=worker, args=(d, 'visits', lock))
            processes.append(p)
            p.start()
            
        for p in processes:
            p.join()
            
        print(f"Final count: {d['visits']}") # Expected: 10
```

#### Errores Típicos

**❌ Modificación Anidada en Manager:**
```python
# MAL - El Proxy de dict no detecta modificaciones profundas
d = manager.dict({'stats': {'cpu': 0}})
d['stats']['cpu'] = 100  # Se pierde, los otros procesos no lo ven
```

**✅ Reasignación explícita para Proxies Anidados:**
```python
# BIEN - Extraer, modificar local y reasignar
d = manager.dict({'stats': {'cpu': 0}})
tmp = d['stats']
tmp['cpu'] = 100
d['stats'] = tmp  # Dispara la sincronización del proxy
```

#### 📌 Conexión con tu TP1

La gran magia detrás de tu dashboard (TUI) para actualizar las métricas dinámicas fue tu uso intensivo de `Manager.dict()`. Almacenaste el Snapshot gigante con información clave del OS parseada simultáneamente. Esto permitió un dict complejo global, accesible para lectura asincrónica de la UI, con una decisión consciente de aceptar el overhead del Manager (red interna/Pickle) a favor de su facilidad de uso por la API dict familiar, combinándolo impecablemente con un `Event` atómico para el control maestro de detención (`stop_event`) cuando llegaba un SIGINT.

#### Preguntas de Examen

1. **¿Qué sucede al modificar un diccionario anidado dentro de un `Manager.dict()` y cómo se evita la falla?**
   <details><summary>Respuesta</summary>
   El Manager de Python devuelve "proxies" (referencias remotas), y su interceptación de operaciones `__setitem__` suele abarcar solo el primer nivel. Si mutás un valor interno (ej. `proxy_dict['key']['subkey'] = value`), la modificación no dispara el evento de sincronización a través del IPC, y los cambios se pierden. Debe resolverse extrayendo el dict interno, mutándolo en una variable temporal local y reasignando el valor al nivel superior (`proxy_dict['key'] = temporal`).
   </details>

2. **¿Cuándo usarías `Pool.imap_unordered` frente a un `Pool.map` normal?**
   <details><summary>Respuesta</summary>
   `Pool.map` bloquea al proceso llamador hasta que todos los elementos han sido procesados y devuelve la lista en el orden exacto de los argumentos. `imap_unordered` es un iterador (lazy). Cede los valores al instante en que cada sub-proceso termina su trabajo individual, lo que es ideal cuando el orden final no importa, los tiempos de procesamiento son asimétricos, o el dataset es tan grande que guardar la lista completa desbordaría la RAM.
   </details>

3. **¿Cómo funciona un `Manager` internamente a nivel de procesos y red?**
   <details><summary>Respuesta</summary>
   El `multiprocessing.Manager()` lanza un nuevo proceso subyacente independiente (el servidor) y levanta un socket o un pipe de red interna. Todos los otros procesos que reciben los objetos "proxy" envían mensajes serializados (Pickle) mediante IPC cada vez que acceden a ellos. El servidor atiende esos mensajes, realiza el acceso/escritura local y retorna una respuesta de la misma forma. 
   </details>

4. **Si solo necesito saber si una condición cambió, ¿debería usar SharedMemory o un Event?**
   <details><summary>Respuesta</summary>
   Un `Event`. La memoria compartida se diseña para grandes bloques de bytes, pero para banderas binarias (True/False) la primitiva `multiprocessing.Event` es limpia, eficiente y tiene la semántica correcta (`wait()` suspendiendo al SO en vez de hacer while/polling gastando ciclos CPU).
   </details>

---

## Clase 10 — Threading

#### Conceptos Clave

##### Threads vs Procesos
Un Thread (hilo) comparte el mismo proceso del sistema operativo.
- Comparten: Heap (memoria general), variables globales, archivos abiertos, descriptores y entorno.
- Separan: Stack de llamadas (variables locales), puntero de instrucción, estado de registros.
- Ventajas: Creación barata y rápida (poca memoria local del sistema), comunicación IPC gratuita sin serialización puesto que comparten memoria de manera natural.

##### El Impacto Real del GIL (Nuevamente)
El Global Interpreter Lock en CPython protege el recolector de referencias en la gestión de memoria interna.
- En tareas CPU-bound (Cálculos): **Threads no aceleran**. Pierden rendimiento por el overhead de adquirir/soltar el GIL a cada iteración del intérprete.
- En tareas I/O-bound (Red, Disco, DB, sleeps): **Threads brillan fuertemente**. Durante operaciones bloqueantes del sistema, Python SUELTA el GIL. Los demás threads pueden aprovechar el CPU eficientemente mientras el otro espera I/O.
*(Nota: Python 3.13+ introduce soporte nativo Free-Threaded (No GIL), que cambia la dinámica radicalmente)*.

##### `threading.Thread`
API prácticamente idéntica a `multiprocessing`.
- Constructor con `target`, `args`.
- `name` y `ident` para rastrear quién ejecuta, `start()`, `join()`.

##### `queue.Queue` vs `multiprocessing.Queue`
Para los hilos se utiliza el módulo `queue` (no `multiprocessing`). Es una cola hilo-segura basada en Locks para paso de mensajes:
- Tiene variantes útiles: `LifoQueue` (pila), `PriorityQueue` (heap priorizado).
- Métodos integrados para coordinación: `task_done()` para indicar finalización de un objeto procesado y `.join()` para que el publicador bloquee hasta que todo en la cola se resolviera (útil en pool workers de hilo).

##### Atomicidad
Una regla de oro: EN PYTHON CASI NADA ES ATÓMICO. Algo tan simple como `counter += 1` o `var.append(val)` (si se usa `+=`) son desensamblados a varios códigos (LOAD, ADD, STORE). El GIL suelta el control de manera arbitraria tras ciertas instrucciones de bytecode. Si varios threads escriben o leen mutando estados a la vez, se producirán **condiciones de carrera** sin importar el GIL.

##### `threading.local()`
Almacenamiento por hilo (Thread Local Storage - TLS). Permite crear atributos globales que mantienen valores aislados y diferentes para cada thread activo. Útil para mantener IDs de transacción, conexiones separadas a DB o contextos web específicos del worker actual.

#### Ejemplo

```python
import threading
import time
from queue import Queue

def network_fetcher(work_queue, results_list, lock):
    """Simulates an IO bound task using threads."""
    while True:
        task = work_queue.get()
        if task is None:
            work_queue.task_done()
            break
            
        print(f"[{threading.current_thread().name}] Fetching URL {task}...")
        time.sleep(0.5) # Simulates Network I/O (GIL is released!)
        
        # We need a lock for appending to a shared structure securely
        with lock:
            results_list.append(f"Data from {task}")
            
        work_queue.task_done()

# Setup
q = Queue()
results = []
lock = threading.Lock()
threads = []

# Start pool
for i in range(3):
    t = threading.Thread(target=network_fetcher, args=(q, results, lock), name=f"Thread-{i}")
    t.start()
    threads.append(t)

# Load queue
for i in range(10):
    q.put(i)

# Wait for queue to process
q.join()

# Terminate cleanly
for _ in threads:
    q.put(None)
for t in threads:
    t.join()
    
print("All items fetched!")
```

#### Errores Típicos

**❌ Asumir protección por el GIL:**
```python
# MAL - Race Condition severa
contador = 0
def increment_bad():
    global contador
    for _ in range(1000000):
        contador += 1 # Son 3 bytecodes, el GIL puede alternar hilos acá y perder el incremento
```

**❌ Confundir colas:**
No se usa `multiprocessing.Queue` en threading. Su uso inyecta un proceso Pickler que daña el rendimiento I/O y es obsoleto puesto que se comparte RAM local. En su lugar se debe usar el paquete puro de memoria `queue`.

#### 📌 Conexión con tu TP1

Decidiste usar multiprocessing porque leer frenéticamente un loop gigante por las carpetas iterables de PID y TASK `(/proc/[pid]/task/)` y estructurarlo, era muy intensivo computacionalmente en Python. Si hubieras usado `threading`, el procesamiento pesado de un analyzer le secuestraría el GIL al thread principal del TUI `curses`, volviendo la pantalla "lenta", saltarina o bloqueada para comandos de teclado.

#### Preguntas de Examen

1. **¿Qué tipo de operaciones se benefician de `threading` en CPython y cuáles no?**
   <details><summary>Respuesta</summary>
   Las tareas I/O-bound (solicitudes de red, lecturas/escrituras en disco lentas, consultas a DB, demoras con `time.sleep()`) se benefician mucho, ya que Python libera explícitamente el GIL en llamadas bloqueantes del kernel. Las tareas CPU-bound (matemáticas pesadas, parseos locales de bucles for, criptografía en código Python) no ganan aceleración y hasta corren más lento por la pelea de retención del hilo del GIL (context-switches).
   </details>

2. **¿Por qué la operación `counter += 1` causa un Race Condition aunque exista un GIL?**
   <details><summary>Respuesta</summary>
   El GIL garantiza que un solo código de bytes (`bytecode`) se ejecute simultáneamente. El problema es que `counter += 1` se compila en múltiples operaciones (1. Leer de memoria, 2. Sumar valor localmente, 3. Escribir valor final en memoria). Si el intérprete interrumpe la ejecución e intercambia threads entre la lectura y la escritura, ambos leerán el mismo número y sobrescribirán perdiendo la información real del progreso (interleaving).
   </details>

3. **¿Cuál es el beneficio y la diferencia de usar `queue.Queue` en threading?**
   <details><summary>Respuesta</summary>
   Maneja toda la exclusión mutua interna por ti. Los métodos `.put()` y `.get()` bloquean y protegen automáticamente el acceso, lo que la hace completamente segura para coordinar trabajadores en patrones de Productor-Consumidor. Además, a diferencia de `multiprocessing.Queue`, no realiza serialización por `Pickle`, ya que los objetos de RAM son pasados mediante simples referencias.
   </details>

4. **¿Cuál es el propósito del Thread Local Storage (`threading.local()`)?**
   <details><summary>Respuesta</summary>
   Proveer un almacén de memoria global donde los atributos que un hilo asigna al objeto solo son visibles por dicho hilo. Se utiliza para almacenar contextos sin tener que pasarlos manualmente (context variables, DB connections globales pero con sesiones únicas) evitando fugas cruzadas de estado en entornos multi-thread de frameworks web.
   </details>

---

## Clase 11 — Sincronización

#### Conceptos Clave

##### Condiciones de Carrera y Sección Crítica
Una **condición de carrera (race condition)** ocurre cuando el comportamiento final de un sistema concurrente depende de un orden particular y no determinista de eventos/ejecución (el scheduler).
Una **sección crítica** es cualquier bloque de código donde se accede (lectura/escritura) de manera concurrente a estado compartido mutable, y debe protegerse.

##### Locks
- **`threading.Lock` / `multiprocessing.Lock`**: Primitiva base de Exclusión Mutua.
  - `acquire(blocking=True, timeout=-1)`
  - `release()`
  - Su uso ideal es a través del context manager `with lock:` asegurando limpieza frente a excepciones.
- **`RLock` (Reentrant Lock)**: Si una función adquiere un Lock y llama a otra función que adquiere el *mismo* lock, un Lock común hará deadlock eterno. Un RLock guarda la cuenta de retenciones para que el *mismo* hilo que lo tiene pueda volver a entrar; liberándose cuando haga los `release()` correspondientes.

##### Semáforos
Un Semáforo mantiene un contador interno. Controla el límite máximo de hilos paralelos que acceden a un recurso acotado.
- `Semaphore(N)`: Inicia en N. `acquire()` resta 1 (bloquea si llega a 0). `release()` suma 1.
- `BoundedSemaphore(N)`: Es igual pero previene fallos humanos. Lanza un `ValueError` si invocas `release()` más veces que N (superando el límite lógico de diseño).

##### Condiciones (Condition Variable)
Son la primitiva por excelencia para el modelo Productor-Consumidor. Envuelve un lock subyacente.
Permite a un hilo liberar el candado y dormir esperando una alerta externa:
- `wait()`: suelta el lock interno y duerme.
- `notify()`/`notify_all()`: despierta a los que aguardan.
- **ALERTA CRÍTICA**: Siempre, siempre debe verificarse el estado en un bucle `while not ...: cond.wait()`. Los SO's y APIs experimentan "Spurious Wakeups" (despertares espurios por señales u otros factores), si se usara un simple bloque `if`, el programa procedería con memoria corrompida sin estar la condición realmente lograda.

##### Barreras
`threading.Barrier(N)` detiene y suspende todo hilo que llame a `.wait()` hasta que exactamente `N` hilos invoquen la acción. Útil en simulación paralela donde las fases (ticks o rondas) obligan a esperar que todos hayan computado un paso antes de proseguir a la fusión de datos.

##### Deadlock, Livelock y Starvation
- **Deadlock**: Hilos que se bloquean infinitamente esperando los candados mutuos (El abrazo de la muerte).
  - *Prevenciones típicas:* orden jerárquico fijo de locks, el uso de timeouts en `acquire()`, tratar de evitar bloquear más de una estructura por vez (Try-Lock).
- **Condiciones de Coffman**: Para un deadlock se precisan las 4 juntas: Exclusión Mutua (recursos exclusivos), Retención y Espera (Lock A retenido mientras espera Lock B), No-Expropiación (no se puede arrebatar el candado) y Espera Circular (A espera B, B espera A).
- **Livelock**: Hilos ceden el paso o modifican su estado en bucle infinito reaccionando al otro sin progresar, quemando CPU, pero nunca se "bloquean".
- **Starvation**: Hilos de baja jerarquía jamás entran al candado porque un constante desfile de altos hilos los saturan eternamente.

#### Ejemplo

```python
import threading
import time

# Classical Producer-Consumer with Condition Variable
buffer = []
MAX_ITEMS = 5
condition = threading.Condition() # Contains implicit lock

def producer():
    for i in range(10):
        with condition:
            # CRITICAL: Always use while for conditions!
            while len(buffer) >= MAX_ITEMS:
                condition.wait() # Sleeps and releases the internal lock
            buffer.append(i)
            print(f"Produced: {i}")
            condition.notify_all() # Wake up waiting consumers
        time.sleep(0.1)

def consumer():
    for _ in range(10):
        with condition:
            while not buffer:
                condition.wait()
            item = buffer.pop(0)
            print(f"Consumed: {item}")
            condition.notify_all() # Wake up waiting producers
        time.sleep(0.2)

t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start()
t2.start()
t1.join()
t2.join()
```

#### Errores Típicos

**❌ Deadlock por Excepciones (NO usar with):**
```python
# MAL - Si ocurre un error, release no se llama y queda estancado
lock.acquire()
hacer_operacion_peligrosa() # raise Exception
lock.release() 
```

**❌ Spurious Wakeup Trap (No usar while):**
```python
# MAL - Si se despierta aleatoriamente, hará pop de lista vacía crasheando
with condicion:
    if len(cola) == 0:
        condicion.wait()
    item = cola.pop()
```

#### 📌 Conexión con tu TP1

En todo el trabajo, orquestaste el diseño concurrente evitando mutaciones entrelazadas directas para evitar Data-Races sucios. Tu `Event` para la bandera universal de la señal del teclado, con su respectivo `is_set()` fue perfecto para transmitir comandos asíncronos limpios para orquestar la terminación y unirse fluidamente con el loop principal.

#### Preguntas de Examen

1. **Definí claramente qué es un Deadlock y nombre dos estrategias básicas para mitigarlo.**
   <details><summary>Respuesta</summary>
   Un deadlock sucede cuando dos o más hilos/procesos se quedan bloqueados de forma permanente, ya que cada uno espera un candado que retiene el otro (Espera circular/Deadly Embrace). Estrategias: (1) Adquirir múltiples locks siempre en un orden predefinido (ej. Id numérico ascendente), previniendo los ciclos. (2) Usar la firma `acquire(timeout=5)`, permitiendo al hilo soltar los suyos, dormir y reintentar un tiempo aleatorio para disolver el choque.
   </details>

2. **¿En qué situación específica se vuelve mandatorio usar un `RLock` frente a un `Lock` estándar?**
   <details><summary>Respuesta</summary>
   Cuando una función o método que adquiere un Lock de instancia debe a su vez invocar otra función interna de la misma clase u API pública que exige poseer ese *mismo* lock. Un `Lock` convencional ocasionará que el propio hilo espere a que él mismo lo suelte (self-deadlock). El reentrante verifica si quien pide el candado ya lo tiene, contabilizando un nivel más de profundidad en sus llamadas.
   </details>

3. **Explicá la diferencia entre usar un BoundedSemaphore(5) y crear 5 workers en un Pool/ThreadPool.**
   <details><summary>Respuesta</summary>
   Un BoundedSemaphore acota el ingreso concurrente de *cualquier número masivo de hilos existentes* a cierta sección crítica. Un ThreadPoolExecutor directamente nace con 5 workers fijos encargados de vaciar el flujo de tareas desde la cola. El pool previene problemas de memoria de sistema desde la raíz al no engendrar cientos de hilos, siendo generalmente una arquitectura superior y más limpia.
   </details>

4. **Por qué la primitiva `Condition.wait()` *debe* ejecutarse con el Lock interno adquirido y qué hace con este lock cuando la invocas.**
   <details><summary>Respuesta</summary>
   Debe estar retenido porque la lógica evalúa estado mutable antes de llamar `.wait()`. La clave mágica de `wait()` es que **de forma atómica** pausa el hilo actual y libera/relaja el lock para que otro hilo (ej. productor) pueda operar el área. Cuando finalmente recibe `.notify()`, el kernel despertará a `wait()`, quien reconquista el candado antes de proseguir de manera segura la siguiente línea de ejecución.
   </details>

5. **Explicá la diferencia entre las fallas de tipo "Livelock" y "Starvation" (Inanición).**
   <details><summary>Respuesta</summary>
   Livelock refiere a un conjunto de threads que fallan al progresar su tarea porque modifican constantemente sus estados en respuesta mutua a algoritmos de evasión (como dos personas esquivándose eternamente en el mismo pasillo) - no bloquean el CPU, lo sobre-consumen con futilidad. Starvation, en cambio, implica que hilos sanos jamás consiguen acceso al recurso ya que el programador/SO les dio prioridad baja y hilos golosos (de alta prioridad/agresivos) adquieren el Lock eternamente no dejando hueco alguno en medio.
   </details>

---

## Cheat Sheet Final

#### Mecanismos IPC

| Mecanismo | Velocidad | Complejidad | Casos de uso | Limitaciones |
|-----------|-----------|-------------|--------------|--------------|
| **Pipes (`os.pipe`)** | Alta | Media | Streaming entre Padre-Hijo. Unidireccional. | Requiere parentesco, datos en bytes (requiere serialización propia). |
| **`mmap` Anónimo** | Máxima | Alta | IPC ultra-rápida (Zero-copy). | Memoria plana, requiere manual struct y sincronización extra. Parentesco. |
| **Queue (MP)** | Media | Baja | Patrón standard Productor-Consumidor IPC. | Overhead alto por Pickle interproceso. Solo una vía si no hay idas/vueltas. |
| **SharedMemory** | Muy Alta| Media | Datos estables a grandes procesos huérfanos. | Reside OS (/dev/shm). Precisa recolección (`unlink`) y locks manuales. |
| **Manager Proxy** | Baja | Baja | Datos anidados y colecciones abstractas Python. | Alta contención, red socket, serialización en cada call. Costoso en updates chicos. |

#### Primitivas de Sincronización

| Primitiva | Cuándo usar | Patrón típico |
|-----------|-------------|---------------|
| **Lock** | Protección genérica del estado compartido. | Exclusion Mutua. |
| **RLock** | Operaciones anidadas, recursividad o APIs complejas. | Clases Thread-Safe completas. |
| **Semaphore** | Limitar accesos (Throttling) a red/archivos. | Limites API Rate (Pools caseros). |
| **BoundedSemaphore**| Igual, previniendo bugs lógicos humanos. | Manejo robusto a prueba de fallos. |
| **Event** | Enviar bandera asíncrona ("Ya terminé"/"Detenerse"). | Control de cierre (`stop_event.is_set()`). |
| **Condition** | Comunicar progreso o llenado sobre listas mutables. | Productor/Consumidor nativo (`while not:` / `wait`). |
| **Barrier** | Forzar sincronía temporal múltiple coordinada. | Procesos de Simulaciones por Fases Temporales. |

#### Proceso vs Thread

| Característica | Proceso (`multiprocessing`) | Thread (`threading`) |
|----------------|-----------------------------|----------------------|
| **Memoria** | Independiente y Aislada. (Se clona o spawnea). | Compartida por todos (Mismo proceso OS). |
| **GIL (CPython)**| Cada proceso tiene un GIL aparte (Multicore total). | Bloqueados bajo 1 solo GIL activo. |
| **Costo Creación**| Elevado (PCB, Tabla Mem, PID, FDs, Startup). | Ligero y veloz. |
| **Comunicación** | Obliga IPC (Pipes, Sockets, Mmaps, Serialización). | IPC es gratuito (punteros/referencias). |
| **Caso de Uso** | CPU-bound (Cálculos puros intensos, Regex masivo). | I/O-bound (Requests Web, Base de Datos, Disco IO). |

#### Referencia de Señales

| Señal | Número | Acción Default | Capturable | Uso común |
|-------|--------|----------------|------------|-----------|
| **SIGTERM**| 15 | Terminar | ✅ Sí | Solicitud limpia para Cerrar programas OS/Docker. |
| **SIGINT** | 2 | Terminar | ✅ Sí | Emitida en terminal al presionar `CTRL+C`. |
| **SIGKILL**| 9 | Terminar forzoso | ❌ Nunca | Asesino silencioso. Matanza inmediata por OS (`kill -9`). |
| **SIGCHLD**| 17 | Ignorar | ✅ Sí | Despertador kernel avisando que Hijo muere (Prevención Zombie).|
| **SIGHUP** | 1 | Terminar | ✅ Sí | Cierre de Terminal SSH // o Notificación a Daemons de Recargar Config. |

#### Comandos Docker Básicos

| Comando | Acción |
|---------|--------|
| `docker build -t <nombre> .` | Construye una imagen y la empaqueta local. |
| `docker run -it --rm <img_name>`| Ejecuta el contenedor, engancha la shell `it` y auto-borra con `rm`. |
| `docker exec -it <id> bash` | Entrar con terminal en crudo adentro a un proceso corriendo background. |
| `docker ps` / `ps -a` | Mostrar activos / Todos los apilados apagados en disco. |
| `docker logs -f <id>` | Observa STDOUT (las prints del proceso) fluir del daemon en tiempo real. |

#### Archivos de `/proc` (Linux)

| Path | Contenido | Formato |
|------|-----------|---------|
| `/proc/[pid]/stat` | Estado General CPU/Hilos del Proceso. | Línea enorme delimitada por espacios, parseo posicional (ej. pid, comm). |
| `/proc/[pid]/status` | Versión descriptiva legible. | Key-Value Pairs multilínea (Name, State, VmRSS, SigIgn). |
| `/proc/[pid]/fd/` | Directorio (symlinks). | Contiene todos los file descriptors del proceso, listables en SO. |
| `/proc/[pid]/task/` | Directorio con sub-pids LWP. | Los LWPs reales para el kernel demostrando hilos del proceso nativo. |
| `/proc/stat` | Datos de la CPU Global OS entera. | Sistema, Idle total, IRQ. |

#### Funciones de `os` para procesos

| Función | Descripción corta |
|---------|-------------------|
| `os.fork()` | Clona PCB del proceso y bifurca el programa. (Padre=PID, Hijo=0). |
| `os.exec*` | Sobrescribe memoria del hilo actual e inyecta ejecutable con `C`. Nunca regresa. |
| `os.waitpid(p, c)`| Espera estado Zombie; limpia PCB kernel. Flag `-1` (Wait-any) y `WNOHANG` asincrónico. |
| `os._exit(N)` | Mata al proceso OS sin triggear el Intérprete Python (`atexit`/Flush IO). Regla de oro en el Hijo. |
| `os.kill(pid, S)` | Dispara señales a PID específico. Interrumpe ejecución por kernel. |
| `os.pipe()` | Aloja memoria de Pipe Anónimo (64KB buffer), devuelve dos FDs de Kernel directos unidireccionales. |
| `os.dup2(old, n)`| Renombra/re-mapea un File Descriptor hacia otro (Ej: Enganchar Pipa a FD 1 (STDOUT)). |

#### Patrones Clave (Esqueletos)

**Fork-Exec-Wait**
```python
pid = os.fork()
if pid == 0:
    os.execlp('ls', 'ls', '-l') # No retorna
else:
    os.waitpid(pid, 0) # Previene zombie
```

**Graceful Shutdown (Event)**
```python
stop = threading.Event()
def task():
    while not stop.is_set():
        do_work(timeout=1)
        
signal.signal(signal.SIGTERM, lambda s, f: stop.set())
```

**Productor-Consumidor (Queue Segura)**
```python
def worker(q):
    while (item := q.get()) is not None: # Sentinel Check
        process(item)
        q.task_done()

for task in range(10): q.put(task)
q.join() # Bloquea al final
for w in workers: q.put(None)
```
