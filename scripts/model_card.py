"""Genera docs/model-card.md a partir del 'champion' vigente en MLflow.

    uv run python scripts/model_card.py

Por qué existe: una model card escrita a mano se desactualiza en el primer
reentrenamiento y nadie se entera -el mismo problema que resuelve
config.py para las rutas, aplicado a la documentación del modelo. Este
script lee el alias @champion del registry, junto con las corridas
hermanas de la misma búsqueda (baseline, ridge, el resto de configuraciones
de CONFIGS), y reescribe el archivo completo.

Si no hay ningún modelo con el alias 'champion' todavía (proyecto recién
clonado, antes del primer 'make promote'), el script lo dice y sale con
código 1 en vez de escribir una tarjeta con datos inventados.
"""

import sys

import mlflow
from mlflow import MlflowClient

from trips.config import (
    ALIAS_CAMPEON,
    EXPERIMENT_NAME,
    MARGEN_DE_MEJORA,
    METRICA_DE_PROMOCION,
    MLFLOW_TRACKING_URI,
    PROJECT_ROOT,
    RANDOM_SEED,
    REGISTERED_MODEL_NAME,
    TEST_SIZE,
)

DESTINO = PROJECT_ROOT / "docs" / "model-card.md"


def _fila_de_metricas(nombre: str, run) -> str:
    m = run.data.metrics
    mae = m.get("mae_min")
    mediana = m.get("mediana_error_min")
    rmse = m.get("rmse_min")
    r2 = m.get("r2_log")
    negrita = "**" if nombre == "champion" else ""
    return (
        f"| {negrita}{nombre}{negrita} | "
        f"{negrita}{mae:.2f}{negrita} | "
        f"{negrita}{mediana:.2f}{negrita} | "
        f"{rmse:.2f} | "
        f"{r2:.3f} |"
    )


def main() -> int:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    try:
        version_champion = client.get_model_version_by_alias(
            REGISTERED_MODEL_NAME, ALIAS_CAMPEON
        )
    except Exception:  # noqa: BLE001 — todavía no hay champion
        print(
            f"No hay ningún modelo con el alias '{ALIAS_CAMPEON}' en "
            f"'{REGISTERED_MODEL_NAME}'. Corre 'make flow' y 'make promote' "
            "antes de generar la model card."
        )
        return 1

    run_champion = client.get_run(version_champion.run_id)
    familia_champion = run_champion.data.tags.get("model_family", "desconocida")
    corte = run_champion.data.params.get("corte_temporal", "?")
    n_train = run_champion.data.params.get("n_train", "?")
    n_test = run_champion.data.params.get("n_test", "?")

    # Corridas hermanas: mismo experimento, para armar la tabla comparativa.
    # Se toma la mejor corrida (menor MAE) por cada familia de modelo, no
    # cualquiera: puede haber varias corridas de la misma familia si alguien
    # amplió la grilla de hiperparámetros.
    experimento = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
    filas_tabla = []
    if experimento is not None:
        runs = mlflow.search_runs(
            experiment_ids=[experimento.experiment_id],
            filter_string="tags.model_family != ''",
            order_by=["metrics.mae_min ASC"],
            output_format="list",
        )
        vistas = set()
        for run in runs:
            familia = run.data.tags.get("model_family")
            if familia is None or familia in vistas:
                continue
            vistas.add(familia)
            etiqueta = (
                "champion" if run.info.run_id == run_champion.info.run_id else familia
            )
            filas_tabla.append(_fila_de_metricas(etiqueta, run))

    tabla = (
        "\n".join(filas_tabla)
        if filas_tabla
        else _fila_de_metricas("champion", run_champion)
    )

    contenido = f"""# Model card — duración de viajes de Citi Bike

> **Generada automáticamente** por `scripts/model_card.py` a partir del alias
> `@{ALIAS_CAMPEON}` vigente en el Model Registry (`{REGISTERED_MODEL_NAME}`,
> versión {version_champion.version}). No editar a mano: los cambios se
> pierden en la próxima corrida de `make model-card`. Para cambiar el
> contenido narrativo (qué hace, limitaciones), editar las secciones fijas
> más abajo en este mismo script.

## Qué hace el modelo

Predice cuántos minutos va a durar un viaje en bicicleta pública de Jersey
City/Hoboken, usando solo lo que se sabe **al empezar** el viaje: estación y
hora de salida, tipo de bicicleta, tipo de usuario y distancia en línea recta
hacia el destino declarado.

**No hace:** predecir la disponibilidad de bicicletas, recomendar rutas, ni
generalizar a otras ciudades o estaciones fuera de Jersey City/Hoboken.

## Detalles técnicos (versión vigente: {version_champion.version})

| | |
|---|---|
| Familia | `{familia_champion}` dentro de un `Pipeline` con `ColumnTransformer` |
| Objetivo de entrenamiento | `log1p(duracion_min)` |
| Preprocesamiento | Dentro del artefacto de MLflow (mismo objeto `Pipeline` registrado) |
| Semilla | {RANDOM_SEED} |
| Partición | Temporal {int((1 - TEST_SIZE) * 100)}/{int(TEST_SIZE * 100)}, corte en {corte} ({n_train} filas entrenan, {n_test} evalúan) |
| Registrado como | `{REGISTERED_MODEL_NAME}`, por **alias** (`@candidate` / `@{ALIAS_CAMPEON}`), no por `stage` |

## Métricas (conjunto de prueba temporal, en minutos)

| Modelo | MAE | Error mediano | RMSE | R²(log) |
|---|---:|---:|---:|---:|
{tabla}

La cifra que más importa para operar el servicio es el **error mediano**, no
el RMSE: el RMSE eleva los errores al cuadrado y queda secuestrado por la
cola larga de viajes atípicos.

No hay una desagregación por subgrupo (`member` vs `casual`, `classic_bike`
vs `electric_bike`) en esta versión de la model card — queda declarado como
pendiente en `docs/riesgos.md`, no omitido en silencio.

## Cómo se decide promover un modelo

`scripts/promote.py` compara el candidato contra el `{ALIAS_CAMPEON}` vigente
por {METRICA_DE_PROMOCION}, y solo reemplaza el alias si mejora por al menos
{MARGEN_DE_MEJORA:.0%}. Un empate no promueve (ver `docs/informe-estado.md`,
sección 6.7, para el caso real donde esto pasó).

## Limitaciones conocidas

- Entrenado con datos de un solo mes y dos municipios: no validado contra
  otra estación del año ni otra ciudad (ver `docs/dataset-card.md`).
- `velocidad_kmh` se excluye deliberadamente por fuga de información: el
  modelo no "sabe" qué tan rápido va la bicicleta, solo la distancia en línea
  recta, así que subestima sistemáticamente rutas muy indirectas.
- No hay intervalos de predicción, solo un punto estimado.

## Cómo se sirve

`GET /modelo` en la API expone la versión exacta cargada; `GET /health`
confirma si el modelo cargó. Cambiarlo en producción es mover el alias
`{ALIAS_CAMPEON}` y reiniciar la API, no reconstruir ni redeployar nada.
"""

    DESTINO.write_text(contenido, encoding="utf-8")
    print(f"Escrita {DESTINO} a partir de la versión {version_champion.version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
