"""cargar_modelo() debe normalizar el tipo de `version` sin importar qué
tipo devuelva la librería de MLflow instalada. Motivo concreto: entre
versiones de MLflow, `ModelVersion.version` pasó de ser `str` a ser `int`
(así lo entrega MLflow 3.15, que es la que usa este proyecto), y como
`ModeloServido.version` se declara `str` -y toda la API lo asume `str`-,
`/predict` respondía 500 en cuanto había un modelo real cargado. Ver el fix
en `trips/api/modelo.py`.
"""

from unittest.mock import MagicMock, patch

import mlflow.pyfunc

from trips.api.modelo import cargar_modelo


def test_version_del_modelo_siempre_es_str():
    """Sin importar si MLflow entrega `version` como int o como str, lo que
    ve el resto de la API debe ser str.

    `mlflow.pyfunc.load_model` se parchea con `patch.object` sobre el
    submódulo real, no con la ruta en string `trips.api.modelo.mlflow.pyfunc
    .load_model`: `mlflow` resuelve `pyfunc` de forma perezosa, así que un
    patch por string sobre esa ruta modifica una instancia del submódulo que
    el código de verdad no vuelve a mirar, y la llamada real se cuela sin
    avisar -en este proyecto tardaba ~4 minutos en fallar por reintentos de
    red contra un MLflow inexistente-.
    """
    version_falsa = MagicMock()
    version_falsa.version = 3  # como lo entrega MLflow 3.15: un int

    with (
        patch.object(mlflow.pyfunc, "load_model", return_value=object()),
        patch("trips.api.modelo.MlflowClient") as cliente_falso,
    ):
        cliente_falso.return_value.get_model_version_by_alias.return_value = (
            version_falsa
        )
        modelo = cargar_modelo()

    assert modelo.version == "3"
    assert isinstance(modelo.version, str)
