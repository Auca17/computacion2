# Dudas

Preguntas que me quedaron abiertas durante el TP.

## Sobre las mediciones

1. **¿Por qué `hashear` se degrada más que linealmente entre 8 y 16 tareas?**
   Con `WORKERS=16`, 8 tareas tardan 3,3 s y 16 tardan 13,2 s: el doble de
   tareas cuesta el cuádruple de tiempo. Mi hipótesis es que las 8 CPU lógicas
   son 4 núcleos físicos con hyperthreading, más el límite de CPU de la VM de
   Docker Desktop. También influye que, como el hash va en bloques, las 16
   tareas se intercalan en los 8 procesos y terminan casi todas juntas al
   final. ¿Hay alguna forma de separar estos efectos?

2. **¿Por qué `descargar` con N=64 y 16 workers tarda 5,2 s si esperaba ~2,5 s?**
   ¿El cuello de botella es el servidor `lento`, que es un solo proceso con 160
   conexiones a la vez, o la red de Docker?

3. **¿Conviene medir cada experimento varias veces y reportar promedio y
   desvío?** Corrí cada uno una sola vez.

## Sobre el diseño

4. **¿Cuántos procesos debería tener el `ProcessPoolExecutor`?** Hoy usa
   `os.cpu_count()` y no está coordinado con `WORKERS`. Si hay más tareas
   `hashear` que procesos, los bloques de distintas tareas se intercalan.
   ¿Sería mejor limitar las tareas CPU con un `Semaphore` del tamaño del pool?

5. **¿`429` o `503` cuando la cola está llena?** Usé `429 Too Many Requests`
   para la cola llena y para el rate limit, y reservé `503` para el apagado. En
   la clase 21 se sugiere `503`. ¿Cuál es más correcto cuando el problema es la
   capacidad del servidor y no un cliente en particular?

6. **Apagado con uvicorn**: descubrí que uvicorn cierra el socket y espera a
   las conexiones abiertas *antes* de correr el `lifespan`, así que mi `503`
   de "no acepto tareas" casi nunca se ve. ¿Lo correcto sería manejar la señal
   yo mismo con `loop.add_signal_handler` (en Linux) y recién después delegar
   en uvicorn?

7. **Reintentos**: ¿cómo se distingue en la práctica un error transitorio (una
   red que se cortó) de uno permanente (una URL que no existe), para no
   reintentar lo que siempre va a fallar?
