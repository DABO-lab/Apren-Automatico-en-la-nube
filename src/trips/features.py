"""Construye las variables derivadas que usa el modelo.

Estas variables no vienen en el archivo crudo de Citi Bike: hay que
construirlas a partir de las columnas que sí trae. Vivían en
notebooks/02-eda.ipynb mientras se exploraban; ahora viven aquí, porque si
el entrenamiento las recalcula por su cuenta, tarde o temprano se cuela una
diferencia entre lo que se exploró y lo que ve el modelo, y ese tipo de
error no avisa (ver docs/guia-del-proyecto.md, sección 11).

Uso desde un notebook o un script de entrenamiento:
    from trips.features import add_features
    df = add_features(df)

Uso desde la terminal (para una revisión rápida):
    uv run python -m trips.features
"""

import numpy as np
import pandas as pd


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia en línea recta sobre la superficie terrestre, en kilómetros.

    Fórmula de haversine: distancia entre dos puntos sobre una esfera a
    partir de sus coordenadas. Ojo: es la línea recta entre estaciones, no
    la recorrida por la bicicleta en las calles, así que siempre subestima
    un poco (ver guia-del-proyecto.md, sección 6.5).
    """
    radio_tierra_km = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * radio_tierra_km * np.arcsin(np.sqrt(a))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega al DataFrame las variables candidatas que dejó el EDA.

    Las cuatro que hay que construir (guia-del-proyecto.md, sección 7):
    `hora`, `dia_semana`, `es_finde` y `distancia_km`. `member_casual` y
    `rideable_type` ya vienen en el archivo crudo, no hay que tocarlas.

    A propósito NO calcula `velocidad_kmh`: se construye dividiendo
    distancia entre duración, es decir, contiene la respuesta. Es fuga de
    información (data leakage) y solo sirve como diagnóstico exploratorio en
    el notebook, nunca como variable del modelo (guia-del-proyecto.md,
    sección 6.7).
    """
    return df.assign(
        hora=df["started_at"].dt.hour,
        dia_semana=df["started_at"].dt.dayofweek,
        es_finde=df["started_at"].dt.dayofweek >= 5,
        distancia_km=haversine_km(
            df["start_lat"], df["start_lng"], df["end_lat"], df["end_lng"]
        ),
    )


def main() -> None:
    from trips.config import PROCESSED_DATA_PATH

    if not PROCESSED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"No encuentro {PROCESSED_DATA_PATH}. Corre primero "
            "'uv run python -m trips.data.clean'."
        )

    df = pd.read_parquet(PROCESSED_DATA_PATH)
    df = add_features(df)

    nuevas = ["hora", "dia_semana", "es_finde", "distancia_km"]
    print(f"Filas: {len(df):,}")
    print(f"Variables agregadas: {', '.join(nuevas)}")
    print("---")
    print(df[nuevas].describe(include="all").round(2))


if __name__ == "__main__":
    main()
