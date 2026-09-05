"""Carga el modelo desde el registry de MLflow, por alias.

La decisión central del despliegue: NO se copia un archivo de modelo dentro
de la imagen. Se pide `models:/duracion-regressor@champion`, donde
`champion` es un alias movible que apunta a una versión inmutable.

Consecuencia práctica: para cambiar el modelo en producción no se
reconstruye la imagen ni se toca el código — se mueve el alias en MLflow y
se reinicia el proceso. Y como cada respuesta incluye la versión, siempre se
puede auditar qué modelo produjo qué predicción.
"""

from dataclasses import dataclass

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient

from trips.config import (
    FEATURE_COLUMNS,
    MLFLOW_TRACKING_URI,
    REGISTERED_MODEL_NAME,
)
from trips.features import add_features

ALIAS = "champion"


@dataclass
class ModeloServido:
    """El modelo cargado y su ficha de identidad."""

    pyfunc: object
    nombre: str
    version: str
    uri: str

    def predecir(self, viajes: pd.DataFrame) -> pd.DataFrame:
        """Devuelve duración en MINUTOS y la distancia que se calculó.

        Dos pasos que no se pueden saltar:

        1. Las variables se construyen con el MISMO `add_features` del
           entrenamiento. Si la API las calculara por su cuenta, cualquier
           diferencia se convertiría en predicciones sutilmente malas que
           nadie detecta.
        2. El modelo predice el LOGARITMO de la duración, así que hay que
           deshacer la transformación con expm1 antes de responder. Sin esto
           la API devolvería "2,1 minutos" para un viaje de 8.
        """
        con_variables = add_features(viajes)
        pred_log = self.pyfunc.predict(con_variables[FEATURE_COLUMNS])
        return pd.DataFrame(
            {
                "duracion_min": np.expm1(pred_log).round(2),
                "distancia_km": con_variables["distancia_km"].round(3),
            }
        )


def cargar_modelo() -> ModeloServido:
    """Trae del registry la versión que tenga el alias 'champion'."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    uri = f"models:/{REGISTERED_MODEL_NAME}@{ALIAS}"

    version = MlflowClient().get_model_version_by_alias(REGISTERED_MODEL_NAME, ALIAS)
    return ModeloServido(
        pyfunc=mlflow.pyfunc.load_model(uri),
        nombre=REGISTERED_MODEL_NAME,
        version=version.version,
        uri=uri,
    )
