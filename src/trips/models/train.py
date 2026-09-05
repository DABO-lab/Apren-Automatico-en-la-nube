"""Entrena tres modelos, los registra en MLflow y marca el mejor como 'champion'.

Tres decisiones de este script salen del EDA (docs/guia-del-proyecto.md):

1. Se predice el LOGARITMO de la duración, no la duración. La distribución
   tiene asimetría 31,6: sin transformar, un viaje de 1.300 minutos pesa más
   en el entrenamiento que cientos de viajes normales.
2. La partición 80/20 es TEMPORAL: se ordena por fecha y el 20% más reciente
   queda para prueba. Un modelo que va a predecir viajes futuros no puede
   entrenarse con datos posteriores a los que evalúa.
3. `velocidad_kmh` no aparece por ninguna parte: se calcula dividiendo la
   distancia entre la duración, así que contiene la respuesta (fuga de
   información, sección 6.7 de la guía).

    uv run python -m trips.models.train
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

# Las 3 configuraciones a comparar. La primera no aprende nada: siempre
# predice la mediana. Es la vara de medir — cualquier modelo que no le gane
# no está aportando información, solo consumiendo electricidad.
CONFIGS = [
    {
        "model_family": "baseline_mediana",
        "params": {"strategy": "median"},
        "build": lambda p: DummyRegressor(**p),
    },
    {
        "model_family": "ridge",
        "params": {"alpha": 1.0},
        "build": lambda p: Ridge(**p, random_state=RANDOM_SEED),
    },
    {
        "model_family": "hist_gradient_boosting",
        "params": {"max_iter": 300, "learning_rate": 0.1, "max_depth": None},
        "build": lambda p: HistGradientBoostingRegressor(**p, random_state=RANDOM_SEED),
    },
]


def split_temporal(df: pd.DataFrame, test_size: float = TEST_SIZE):
    """Parte el DataFrame por fecha: lo viejo entrena, lo reciente evalúa."""
    df = df.sort_values("started_at")
    corte = int(len(df) * (1 - test_size))
    return df.iloc[:corte], df.iloc[corte:]


def construir_preprocesador() -> ColumnTransformer:
    """El preprocesamiento viaja DENTRO del modelo.

    Quien cargue el modelo del registry le pasa los datos tal cual, sin
    preprocesar nada aparte: el pipeline completo es el que se guarda.
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
    logarítmico". Se deshace la transformación con expm1 y se reporta en la
    unidad en que la gente piensa.
    """
    pred_min = np.expm1(pred_log)
    return {
        "mae_min": mean_absolute_error(y_test_min, pred_min),
        "rmse_min": float(np.sqrt(mean_squared_error(y_test_min, pred_min))),
        "mediana_error_min": float(np.median(np.abs(y_test_min - pred_min))),
        "r2_log": r2_score(np.log1p(y_test_min), pred_log),
    }


def main() -> None:
    # 1. Conectarse al servidor de MLflow y elegir el experimento.
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()

    # 2. Datos limpios + variables derivadas (las mismas del EDA, del paquete).
    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"No encuentro {PROCESSED_DATA_PATH}. Corre antes 'make data'."
        )
    df = add_features(pd.read_parquet(PROCESSED_DATA_PATH))

    train, test = split_temporal(df)
    X_train, X_test = train[FEATURE_COLUMNS], test[FEATURE_COLUMNS]
    y_train_log = np.log1p(train[TARGET_COLUMN])
    y_test_min = test[TARGET_COLUMN].to_numpy()

    corte = test["started_at"].min()
    print(f"Entrenamiento: {len(train):,} viajes hasta {corte:%Y-%m-%d %H:%M}")
    print(f"Prueba:        {len(test):,} viajes desde esa fecha\n")

    mejor_version, mejor_mae = None, float("inf")

    for config in CONFIGS:
        with mlflow.start_run(run_name=config["model_family"]) as run:
            pipeline = Pipeline(
                [
                    ("preprocesamiento", construir_preprocesador()),
                    ("modelo", config["build"](config["params"])),
                ]
            )
            pipeline.fit(X_train, y_train_log)
            metricas = evaluar(y_test_min, pipeline.predict(X_test))

            mlflow.log_params(config["params"])
            mlflow.log_metrics(metricas)
            mlflow.set_tag("model_family", config["model_family"])
            mlflow.set_tag("split", "temporal_80_20")
            mlflow.set_tag("target", "log1p(duracion_min)")
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
            print(
                f"{config['model_family']:<24} "
                f"MAE {metricas['mae_min']:>5.2f} min | "
                f"RMSE {metricas['rmse_min']:>6.2f} | "
                f"R2(log) {metricas['r2_log']:>6.3f} | "
                f"versión {version.version}"
            )

            if metricas["mae_min"] < mejor_mae:
                mejor_mae = metricas["mae_min"]
                mejor_version = version.version

    # El alias 'champion' es un post-it movible: señala la versión que está
    # "en producción" sin tocar el código que la consume. Nunca stages:
    # están deprecados; el curso gobierna con aliases y tags.
    client.set_registered_model_alias(REGISTERED_MODEL_NAME, "champion", mejor_version)

    runs = mlflow.search_runs(
        experiment_names=[EXPERIMENT_NAME], order_by=["metrics.mae_min ASC"]
    )
    columnas = [
        "tags.model_family",
        "metrics.mae_min",
        "metrics.rmse_min",
        "metrics.mediana_error_min",
        "metrics.r2_log",
    ]
    print("\nComparación de runs (mejor arriba):")
    print(runs[columnas].round(3).to_string(index=False))
    print(
        f"\nChampion: versión {mejor_version} de '{REGISTERED_MODEL_NAME}' "
        f"(MAE {mejor_mae:.2f} minutos)"
    )


if __name__ == "__main__":
    main()
