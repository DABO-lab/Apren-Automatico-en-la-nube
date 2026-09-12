# ADR 002 — La búsqueda de 20 corridas usa runs "planos", no anidados

**Estado:** aceptado
**Fecha:** septiembre de 2026
**Autores:** equipo del proyecto, con apoyo de un asistente de Claude

## Contexto

El nivel 5 de la dimensión de `tracking` en la rúbrica del instructor pide
"≥20 runs comparables de una búsqueda estructurada (anidados: `parent` +
`child` por `trial`)". El proyecto pasó de 3 configuraciones (un baseline,
un Ridge, un HistGradientBoosting) a 20 (1 baseline + 7 de Ridge + 12 de
HistGradientBoosting) en `src/trips/models/train.py`.

El patrón estándar de MLflow para agrupar una búsqueda es un run "padre"
(`with mlflow.start_run() as padre:`) que contiene runs "hijo" abiertos con
`mlflow.start_run(nested=True)` dentro del mismo bloque. Ese patrón depende
de una variable de contexto por hilo: MLflow guarda cuál es el run activo
usando un estado global (`mlflow.active_run()`), y `nested=True` es lo que
le dice "cuélgate del run activo actual, no abras uno independiente".

El proyecto entrena las 20 configuraciones **en paralelo**: el flujo de
Prefect (`src/trips/flows/training.py`, `flujo_entrenamiento`) lanza cada
`entrenar_configuracion` con `entrenar.submit(...)`, y Prefect ejecuta esos
`submit` en hilos (o procesos, según el `task runner`) distintos.

## Decisión

**Las 20 corridas se registran como runs independientes ("planos"), no como
`parent`/`child` anidados.** Se agrupan en la UI de MLflow con una etiqueta
compartida en vez de con jerarquía real:

- `grupo_busqueda` (un id con marca de tiempo) cuando la búsqueda corre por
  `uv run python -m trips.models.train` (fuera de Prefect).
- `prefect_run_id` (el id de la corrida del flujo) cuando corre orquestada.
- `trial` (el índice de la configuración dentro de `CONFIGS`) en los dos casos.

Cualquiera de las dos etiquetas se puede filtrar en la UI de MLflow
(`tags.grupo_busqueda = '...'` o `tags.prefect_run_id = '...'`) para ver
las 20 corridas de una búsqueda juntas, que es el mismo resultado práctico
que ofrece la vista de un run padre con hijos.

## Alternativas consideradas y descartadas

- **`mlflow.start_run(nested=True)` con un run padre abierto en
  `flujo_entrenamiento` y las 20 tareas anidándose dentro.** Se descartó
  porque `active_run()` es estado compartido por proceso: si dos tareas de
  Prefect corren de verdad al mismo tiempo (dos hilos, o dos procesos con
  memoria compartida vía `fork`), una puede leer como "run activo" el run
  hijo que abrió *otra* tarea, y terminar registrando sus métricas colgadas
  del run equivocado — una condición de carrera silenciosa: no truena, deja
  un experimento con datos cruzados que nadie nota hasta que compara
  métricas y no cuadran.
- **Correr las 20 configuraciones en serie (sin `.submit()`), para poder
  anidar sin riesgo de condición de carrera.** Se descartó porque tira la
  paralelización que ya daba el `caching` medido de Prefect (ver
  `docs/informe-estado.md`, sección 6.10): pasar de 3 a 20 configuraciones
  en serie multiplica por ~7 el tiempo de la corrida completa, a cambio de
  una jerarquía que las etiquetas ya resuelven para el caso de uso real
  (filtrar y comparar en la UI).

## Consecuencias

- La UI de MLflow no muestra un árbol `parent`/`child` nativo para esta
  búsqueda: hay que filtrar por `tags.grupo_busqueda` o `tags.prefect_run_id`
  para agrupar visualmente. Es un paso extra (escribir el filtro) contra la
  jerarquía automática que da `nested=True`.
- A cambio, el entrenamiento paralelo del flujo de Prefect sigue siendo
  seguro entre hilos sin coordinación adicional: cada `entrenar_configuracion`
  abre y cierra su propio run de principio a fin, sin depender de un estado
  global compartido con las otras 19 tareas que corren al mismo tiempo.
- Si en el futuro el equipo deja de paralelizar el entrenamiento (por
  ejemplo, si una sola configuración empieza a tardar tanto que conviene
  correrlas todas en un único proceso secuencial), esta decisión se puede
  revertir sin tocar la lógica de entrenamiento: bastaría con envolver el
  bucle de `CONFIGS` en un run padre y pasar `nested=True` en
  `entrenar_configuracion`.
