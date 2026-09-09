# Política de reentrenamiento

## Qué dispara un reentrenamiento (`trigger`)

Cualquiera de estos tres, no hace falta que se den los tres a la vez:

1. **Drift detectado.** `make drift` (o el chequeo dentro de `make flow`)
   sale con código 1: al menos el 30 % de las columnas vigiladas
   (`FRACCION_COLUMNAS_PARA_ALERTAR` en
   `src/trips/monitoring/check_drift.py`) se movió más allá del umbral
   calibrado. Ver `docs/dataset-card.md` y la sección 6.9 del informe de
   estado para cómo se calibró ese umbral.
2. **Calendario.** Cuando Citi Bike publique un nuevo mes de datos (por
   ejemplo agosto), se reentrena aunque el chequeo de drift no haya
   alertado — un mes nuevo es información nueva, no hay que esperar a que
   duela.
3. **Manual.** Cualquier integrante del equipo puede decidir reentrenar si
   sospecha un problema (por ejemplo, un cambio de esquema del proveedor que
   `ViajesCrudos` no captura pero un vistazo manual sí).

**Lo que NO dispara un reentrenamiento:** que pase más tiempo del esperado.
No hay una regla tipo `cron="0 0 1 * *"` que reentrene solo porque cambió el
mes en el calendario sin datos nuevos de por medio — eso sería reentrenar con
la misma información y arriesgar un modelo distinto por puro ruido de
muestreo (el mismo problema que ya evitó la compuerta en el caso real de la
sección 6.7 del informe de estado, cuando dos entrenamientos con datos
idénticos dieron MAE igual y no se promovió el "nuevo" modelo).

## Con qué datos se reentrena

El parquet procesado más reciente (`data/processed/viajes_limpio.parquet`),
regenerado con `make data` a partir del CSV crudo más nuevo disponible. Nunca
se reentrena con una muestra recortada a mano "para que ande más rápido": la
partición sigue siendo temporal (sección 6.4 del informe) sobre el dataset
completo.

## Quién aprueba la promoción

**Nadie la aprueba a mano, y eso es intencional.** La promoción la decide
`scripts/promote.py` (la compuerta), comparando el candidato contra el
`champion` vigente y exigiendo una mejora de al menos el 2 % en MAE
(`MARGEN_DE_MEJORA`). El pipeline de entrenamiento (`make flow`) **nunca**
mueve el alias `champion` por sí mismo — solo marca `candidate`. Un humano
del equipo es quien decide **correr** `make promote` (o dejar que el job de
CI en `main` lo corra automáticamente, ver `.github/workflows/ci.yml`), pero
la decisión de promover o no la toma siempre la misma regla, no un juicio caso
por caso. Esto es deliberado: un pipeline que se autopromueve no tiene
control de calidad (sección 6.7 del informe de estado).

## Mecanismo de rollback

Cambiar el modelo en producción es mover un alias, así que deshacerlo también
lo es: **no hay que reconstruir ni redeployar nada**.

```python
from mlflow import MlflowClient
from trips.config import REGISTERED_MODEL_NAME, ALIAS_CAMPEON

client = MlflowClient()
# volver a la versión anterior conocida (ej. la 3, si la 4 resultó mala)
client.set_registered_model_alias(REGISTERED_MODEL_NAME, ALIAS_CAMPEON, 3)
```

Después de mover el alias, reiniciar la API (`make api` o `docker restart`
en producción): el modelo se carga del registry al arrancar
(`src/trips/api/main.py`, función `lifespan`), así que el próximo arranque
sirve la versión correcta sin ningún otro cambio.

## Qué queda registrado

- **En MLflow:** cada corrida de entrenamiento (parámetros, métricas,
  artefacto del modelo, versión registrada) y cada corrida del chequeo de
  drift (`run_name="drift"`, con las métricas de PSI/V de Cramér de esa
  ejecución) — así queda una serie histórica, no solo el último número.
- **En el log de `scripts/promote.py`:** la decisión completa con su motivo
  ("mejora del X %...", "empate exacto...", "el candidato es peor..."),
  impresa en cada corrida y visible en los logs de GitHub Actions cuando
  corre en CI.
- **En git:** qué versión del código produjo cada modelo, vía el tag
  `prefect_run_id` que el flujo agrega a cada corrida de MLflow (sección 6.10
  del informe de estado) — desde una métrica se puede volver a la corrida de
  Prefect exacta que la produjo, y de ahí al commit.

Lo que **no** queda registrado todavía, y es una limitación conocida: no hay
un log separado de "quién decidió reentrenar y por qué" cuando el disparador
es manual — solo el mensaje del commit que trae los datos nuevos. Ver
`docs/riesgos.md`.
