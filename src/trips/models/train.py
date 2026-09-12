"""Entrena, compara y registra modelos en MLflow.

    uv run python -m trips.models.train

Tres decisiones salen del EDA (docs/guia-del-proyecto.md):

1. Se predice el LOGARITMO de la duración. Con asimetría 31,6, sin transformar,
   un viaje de 1.300 minutos pesa más que cientos de viajes normales.
2. La partición 80/20 es TEMPORAL: lo viejo entrena, lo reciente evalúa. Un
   modelo que va a predecir el futuro no puede entrenarse con datos posteriores
   a los que evalúa.
3. `velocidad_kmh` no aparece: contiene la respuesta (fuga de información).

Y una decisión de operación: el mejor modelo de la corrida queda marcado como
**`candidate`**, no como `champion`. La promoción a producción tiene su propia
compuerta en `scripts/promote.py`.
"""

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from trips.config import (
    ALIAS_CANDIDATO,
    CATEGORICAL_FEATURES,
    EXPERIMENT_NAME,
    FEATURE_COLUMNS,
    MLFLOW_TRACKING_URI,
    NUMERIC_FEATURES,
    PROCESSED_DATA_PATH,
    RANDOM_SEED,
    REGISTERED_MODEL_NAME,
    TARGET_COLUMN,
    TEST_SIZE,
)
from trips.features import add_features

# Las configuraciones a comparar: 1 baseline + 7 de Ridge + 12 de
# HistGradientBoosting = 20 corridas. La primera no aprende nada: siempre
# predice la mediana. Es la vara de medir — cualquier modelo que no le gane
# no está aportando información, solo consumiendo electricidad.
#
# Son 20 corridas "planas" (un run por configuración), no runs anidados
# (parent/child con mlflow.start_run(nested=True)): cuando el flujo de
# Prefect las lanza en paralelo con .submit(), varias corridas comparten
# hilo al mismo tiempo y anidar por contexto de proceso es una condición de
# carrera -un hijo puede terminar registrado bajo el padre equivocado-. En
# su lugar, todas quedan agrupadas por la etiqueta `grupo_busqueda` (o
# `prefect_run_id` cuando las lanza el flujo), que es segura entre hilos y
# se puede filtrar igual en la UI de MLflow.
CONFIGS = [
    {"model_family": "baseline_mediana", "params": {"strategy": "median"}},
    *[
        {"model_family": "ridge", "params": {"alpha": alpha}}
        for alpha in [0.01, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0]
    ],
    *[
        {
            "model_family": "hist_gradient_boosting",
            "params": {"max_iter": max_iter, "learning_rate": learning_rate},
        }
        for max_iter in (100, 300, 500)
        for learning_rate in (0.03, 0.1, 0.3, 0.5)
    ],
]


def construir_modelo(familia: str, params: dict):
    """Del nombre de la familia al estimador, con la semilla fija puesta."""
    if familia == "baseline_mediana":
        return DummyRegressor(**params)
    if familia == "ridge":
        return Ridge(**params, random_state=RANDOM_SEED)
    if familia == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(**params, random_state=RANDOM_SEED)
    raise ValueError(f"Familia de modelo desconocida: {familia}")


def split_temporal(df: pd.DataFrame, test_size: float = TEST_SIZE):
    """Parte el DataFrame por fecha: lo viejo entrena, lo reciente evalúa."""
    df = df.sort_values("started_at")
    corte = int(len(df) * (1 - test_size))
    return df.iloc[:corte], df.iloc[corte:]


def construir_preprocesador() -> ColumnTransformer:
    """El preprocesamiento viaja DENTRO del modelo.

    Quien cargue el modelo del registry le pasa los datos tal cual: el pipeline
    completo es lo que se guarda.
    """
    return ColumnTransformer(
        transformers=[
            (
                "categoricas",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
            ("numericas", "passthrough", NUMERIC_FEATURES),
        ]
    )


def evaluar(y_test_min, pred_log) -> dict:
    """Métricas en MINUTOS, no en logaritmos.

    El modelo aprende sobre el logaritmo, pero nadie entiende "0,42 de error
    logarítmico": se deshace la transformación antes de reportar.
    """
    pred_min = np.expm1(pred_log)
    return {
        "mae_min": mean_absolute_error(y_test_min, pred_min),
        "rmse_min": float(np.sqrt(mean_squared_error(y_test_min, pred_min))),
        "mediana_error_min": float(np.median(np.abs(y_test_min - pred_min))),
        "r2_log": r2_score(np.log1p(y_test_min), pred_log),
    }


def cargar_datos_de_entrenamiento():
    """Parquet limpio + variables derivadas, partido en el tiempo."""
    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"No encuentro {PROCESSED_DATA_PATH}. Corre antes 'make data'."
        )
    return split_temporal(add_features(pd.read_parquet(PROCESSED_DATA_PATH)))


def entrenar_configuracion(
    familia: str, params: dict, tags: dict | None = None
) -> dict:
    """Entrena UNA configuración, la registra y devuelve sus métricas.

    Está separada de `main()` para que el flujo de Prefect pueda llamarla una
    vez por configuración, en paralelo y con caché propia.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    train, test = cargar_datos_de_entrenamiento()
    X_train, X_test = train[FEATURE_COLUMNS], test[FEATURE_COLUMNS]
    y_train_log = np.log1p(train[TARGET_COLUMN])
    y_test_min = test[TARGET_COLUMN].to_numpy()
    corte = test["started_at"].min()

    with mlflow.start_run(run_name=familia) as run:
        pipeline = Pipeline(
            [
                ("preprocesamiento", construir_preprocesador()),
                ("modelo", construir_modelo(familia, params)),
            ]
        )
        pipeline.fit(X_train, y_train_log)
        metricas = evaluar(y_test_min, pipeline.predict(X_test))

        mlflow.log_params(params)
        mlflow.log_metrics(metricas)
        mlflow.set_tag("model_family", familia)
        mlflow.set_tag("split", "temporal_80_20")
        mlflow.set_tag("target", "log1p(duracion_min)")
        for clave, valor in (tags or {}).items():
            mlflow.set_tag(clave, valor)
        mlflow.log_param("corte_temporal", f"{corte:%Y-%m-%d %H:%M}")
        mlflow.log_param("n_train", len(train))
        mlflow.log_param("n_test", len(test))

        # signature = el contrato de entrada/salida del modelo.
        mlflow.sklearn.log_model(
            pipeline,
            name="model",
            signature=infer_signature(X_train, pipeline.predict(X_train)),
            input_example=X_train.head(5),
        )

        version = mlflow.register_model(
            model_uri=f"runs:/{run.info.run_id}/model",
            name=REGISTERED_MODEL_NAME,
        )

    return {
        "modelo": familia,
        "params": params,
        "version": version.version,
        "run_id": run.info.run_id,
        **metricas,
    }


def main() -> None:
    train, test = cargar_datos_de_entrenamiento()
    print(
        f"Entrenamiento: {len(train):,} viajes hasta "
        f"{test['started_at'].min():%Y-%m-%d %H:%M}"
    )
    print(f"Prueba:        {len(test):,} viajes desde esa fecha\n")

    # Agrupa las 20 corridas de esta búsqueda sin usar runs anidados (ver el
    # comentario junto a CONFIGS): un id compartido que se puede filtrar en
    # la UI de MLflow, igual que 'prefect_run_id' cuando corre por el flujo.
    grupo_busqueda = f"busqueda-{pd.Timestamp.now():%Y%m%d-%H%M%S}"
    resultados = [
        entrenar_configuracion(
            c["model_family"],
            c["params"],
            tags={"grupo_busqueda": grupo_busqueda, "trial": str(i)},
        )
        for i, c in enumerate(CONFIGS)
    ]
    for r in resultados:
        print(
            f"{r['modelo']:<24} MAE {r['mae_min']:>5.2f} min | "
            f"RMSE {r['rmse_min']:>6.2f} | R2(log) {r['r2_log']:>6.3f} | "
            f"versión {r['version']}"
        )

    mejor = min(resultados, key=lambda r: r["mae_min"])

    # El alias 'candidate' es una propuesta, no un ascenso. Quién sirve en
    # producción lo decide scripts/promote.py comparando con el campeón.
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    MlflowClient().set_registered_model_alias(
        REGISTERED_MODEL_NAME, ALIAS_CANDIDATO, mejor["version"]
    )

    print(
        f"\nCandidato: versión {mejor['version']} de '{REGISTERED_MODEL_NAME}' "
        f"(MAE {mejor['mae_min']:.2f} minutos)"
    )
    print("Para evaluarlo contra el campeón: uv run python scripts/promote.py")


if __name__ == "__main__":
    main()
