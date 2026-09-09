"""El pipeline completo, orquestado: datos -> variables -> modelos -> drift.

    uv run python -m trips.flows.training

Lo que aporta Prefect sobre encadenar comandos en un Makefile:

- **Caché con huella de archivo.** Cada paso guarda su resultado y no lo
  recalcula si sus entradas no cambiaron. La segunda corrida sobre los mismos
  datos pasa de 40 segundos a 1.
- **Reintentos donde tienen sentido.** Leer un archivo puede fallar por causas
  pasajeras; una división entre dos, no. Solo los pasos de entrada/salida
  reintentan.
- **Linaje.** El identificador de la corrida de Prefect queda como etiqueta en
  cada corrida de MLflow, así que desde una métrica se puede volver al flujo
  que la produjo.
- **Observabilidad.** `uv run prefect server start` abre un tablero en
  http://127.0.0.1:4200 con el grafo, los tiempos y qué salió de caché.

Una decisión de diseño importante: este flujo registra el mejor modelo con el
alias **`candidate`**, NO lo promueve a `champion`. Un pipeline que se
autopromueve no tiene compuerta: cualquier reentrenamiento con datos malos
entraría a producción solo. La promoción vive en `scripts/promote.py`.
"""

from datetime import timedelta
from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient
from prefect import flow, get_run_logger, task
from prefect.cache_policies import INPUTS, TASK_SOURCE
from prefect.context import get_run_context

from trips.config import (
    ALIAS_CANDIDATO,
    MLFLOW_TRACKING_URI,
    PROCESSED_DATA_PATH,
    RAW_DATA_PATH,
    REGISTERED_MODEL_NAME,
)

# La política de caché: las entradas de la tarea Y el código de la tarea.
# Incluir el código importa — si alguien cambia una regla de limpieza, el
# resultado viejo deja de ser válido aunque el archivo de entrada sea el mismo.
CACHE = INPUTS + TASK_SOURCE
VIGENCIA = timedelta(hours=12)


def huella(ruta: Path) -> str:
    """Identifica un archivo por su estado, sin leerlo entero.

    Tamaño y fecha de modificación bastan y son instantáneos. Pasar la ruta
    sola no serviría: el nombre no cambia cuando el archivo sí.
    """
    if not ruta.exists():
        return "ausente"
    estado = ruta.stat()
    return f"{ruta.name}:{estado.st_size}:{int(estado.st_mtime)}"


# --------------------------------------------------------------------------
# Tareas
# --------------------------------------------------------------------------
@task(
    name="cargar-y-limpiar",
    cache_policy=CACHE,
    cache_expiration=VIGENCIA,
    # Leer del disco puede fallar por causas pasajeras (el archivo se está
    # copiando, el antivirus lo tiene tomado). Vale la pena reintentar.
    retries=2,
    retry_delay_seconds=[5, 15],
)
def cargar_y_limpiar(huella_crudo: str) -> str:
    """Del CSV crudo al parquet limpio, con los dos contratos de por medio."""
    from trips.data.clean import clean_trips
    from trips.data.contract import ViajesLimpios
    from trips.data.load import load_trips

    log = get_run_logger()
    df = load_trips()
    log.info("Crudos cargados y validados: %s viajes", f"{len(df):,}")

    limpio = clean_trips(df)
    ViajesLimpios.validate(limpio, lazy=True)

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    limpio.to_parquet(PROCESSED_DATA_PATH, index=False)
    log.info("Limpios: %s viajes -> %s", f"{len(limpio):,}", PROCESSED_DATA_PATH.name)
    return huella(PROCESSED_DATA_PATH)


@task(name="construir-variables", cache_policy=CACHE, cache_expiration=VIGENCIA)
def construir_variables(huella_limpio: str) -> dict:
    """Agrega las variables derivadas y devuelve un resumen para el registro."""
    from trips.features import add_features

    log = get_run_logger()
    df = add_features(pd.read_parquet(PROCESSED_DATA_PATH))
    log.info("Variables construidas sobre %s viajes", f"{len(df):,}")
    return {
        "n_filas": len(df),
        "distancia_mediana_km": round(float(df["distancia_km"].median()), 3),
    }


@task(name="entrenar", cache_policy=CACHE, cache_expiration=VIGENCIA)
def entrenar(huella_limpio: str, nombre_config: str, params: dict) -> dict:
    """Entrena UNA configuración y la registra como una versión del modelo.

    Es una tarea por configuración a propósito: Prefect las corre en paralelo,
    cachea cada una por separado y, si una falla, las demás siguen.

    El identificador de la corrida se lee del CONTEXTO, no se recibe como
    argumento: si entrara por parámetro, cambiaría en cada corrida y la clave
    de caché nunca coincidiría — la tarea volvería a entrenar siempre, y el
    caché existiría sin servir para nada.
    """
    from trips.models.train import entrenar_configuracion

    log = get_run_logger()
    run_prefect = str(get_run_context().task_run.flow_run_id)
    resultado = entrenar_configuracion(
        nombre_config, params, tags={"prefect_run_id": run_prefect}
    )
    log.info(
        "%s -> MAE %.3f min (versión %s)",
        nombre_config,
        resultado["mae_min"],
        resultado["version"],
    )
    return resultado


@task(name="chequear-drift", cache_policy=CACHE, cache_expiration=VIGENCIA)
def chequear_drift(huella_limpio: str) -> dict:
    """El mismo chequeo del módulo de monitoreo, ahora dentro del flujo."""
    from trips.features import add_features
    from trips.monitoring.check_drift import _particion_temporal, comparar

    log = get_run_logger()
    referencia, actual = _particion_temporal(
        add_features(pd.read_parquet(PROCESSED_DATA_PATH))
    )
    resultado = comparar(referencia, actual)
    log.info(
        "Drift: %s de %s columnas (%.0f%%)",
        len(resultado["columnas_con_drift"]),
        len(resultado["columnas"]),
        resultado["fraccion_columnas_con_drift"] * 100,
    )
    return resultado


@task(name="marcar-candidato")
def marcar_candidato(resultados: list[dict]) -> dict:
    """Señala la mejor versión con el alias `candidate`. NO toca `champion`.

    Ese alias es una propuesta: "esta es la mejor de esta corrida". Quién pasa
    a producción lo decide la compuerta de promoción, comparando contra el
    campeón vigente.
    """
    log = get_run_logger()
    mejor = min(resultados, key=lambda r: r["mae_min"])

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    MlflowClient().set_registered_model_alias(
        REGISTERED_MODEL_NAME, ALIAS_CANDIDATO, mejor["version"]
    )
    log.info(
        "Candidato: versión %s (%s, MAE %.3f min)",
        mejor["version"],
        mejor["modelo"],
        mejor["mae_min"],
    )
    return mejor


# --------------------------------------------------------------------------
# El flujo
# --------------------------------------------------------------------------
@flow(name="entrenamiento-viajes", log_prints=True)
def flujo_entrenamiento(configuraciones: list[dict] | None = None) -> dict:
    """Encadena el pipeline completo y devuelve el resumen de la corrida."""
    from trips.models.train import CONFIGS

    log = get_run_logger()
    run_prefect = str(get_run_context().flow_run.id)
    log.info("Corrida de Prefect %s", run_prefect)

    configuraciones = configuraciones or CONFIGS

    # La huella del CSV es la que dispara (o no) el recálculo de todo lo demás.
    huella_limpio = cargar_y_limpiar(huella(RAW_DATA_PATH))
    resumen_variables = construir_variables(huella_limpio)
    drift = chequear_drift(huella_limpio)

    # .submit() las lanza en paralelo; .result() espera a que terminen.
    futuros = [
        entrenar.submit(huella_limpio, c["model_family"], c["params"])
        for c in configuraciones
    ]
    resultados = [f.result() for f in futuros]

    mejor = marcar_candidato(resultados)

    resumen = {
        "prefect_run_id": run_prefect,
        "n_configuraciones": len(resultados),
        "candidato": mejor,
        "drift_alerta": drift["alerta"],
        "variables": resumen_variables,
    }
    log.info(
        "Listo. Candidato v%s con MAE %.3f min. Promoción: 'make promote'.",
        mejor["version"],
        mejor["mae_min"],
    )
    return resumen


if __name__ == "__main__":
    flujo_entrenamiento()
