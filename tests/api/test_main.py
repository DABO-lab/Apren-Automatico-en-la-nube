"""Pruebas de integración de la API: golpean los endpoints reales con
`TestClient`, usando un modelo falso en vez de un servidor de MLflow -así no
dependen de infraestructura levantada-.

Sin pruebas a este nivel, un problema de contrato entre `trips.api.modelo`
y `trips.api.schemas` (dos tipos que no coinciden) pasa las pruebas
unitarias y solo se ve al correr el servicio de verdad. Es justo lo que ya
nos pasó una vez (ver `tests/api/test_modelo.py` para el caso concreto).
"""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from trips.api import main
from trips.api.modelo import ModeloServido

VIAJE = {
    "started_at": "2026-08-04T08:15:00",
    "start_lat": 40.7215,
    "start_lng": -74.0365,
    "end_lat": 40.7375,
    "end_lng": -74.0295,
    "member_casual": "member",
    "rideable_type": "electric_bike",
}


class _PyfuncFalso:
    """Sustituye al modelo real: predice log1p(6 minutos) para cualquier fila."""

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.full(len(X), np.log1p(6.0))


@pytest.fixture
def cliente(monkeypatch) -> TestClient:
    """Reemplaza cargar_modelo() por un modelo falso ANTES de que arranque
    el lifespan: el TestClient lo carga igual que la API real, solo que sin
    depender de un tracking server de MLflow levantado."""

    def _cargar_modelo_falso() -> ModeloServido:
        return ModeloServido(
            pyfunc=_PyfuncFalso(),
            nombre="duracion-regressor",
            version="3",
            uri="models:/duracion-regressor@champion",
        )

    monkeypatch.setattr(main, "cargar_modelo", _cargar_modelo_falso)
    with TestClient(main.app) as client:
        yield client


def test_health_responde_ok_con_modelo_cargado(cliente: TestClient):
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["modelo_cargado"] is True


def test_info_modelo_incluye_version_y_alias(cliente: TestClient):
    respuesta = cliente.get("/modelo")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["version"] == "3"
    assert cuerpo["alias"] == "champion"


def test_predict_devuelve_duracion_en_minutos(cliente: TestClient):
    respuesta = cliente.post("/predict", json=VIAJE)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["duracion_min"] > 0
    assert cuerpo["version"] == "3"


def test_predict_rechaza_viaje_fuera_de_la_zona(cliente: TestClient):
    """Coordenadas de Medellín: el contrato de la API debe rechazarlas
    antes de que lleguen al modelo (ver trips/api/schemas.py)."""
    viaje_invalido = {**VIAJE, "start_lat": 6.24, "start_lng": -75.58}
    respuesta = cliente.post("/predict", json=viaje_invalido)
    assert respuesta.status_code == 422


def test_predict_batch_devuelve_una_prediccion_por_viaje(cliente: TestClient):
    respuesta = cliente.post("/predict/batch", json={"viajes": [VIAJE, VIAJE]})
    assert respuesta.status_code == 200
    assert len(respuesta.json()["predicciones"]) == 2


def test_health_ok_pero_predict_503_si_no_hay_modelo(monkeypatch):
    """Un MLflow caído no debe tumbar la API: /health sigue en 200 (el
    proceso vive) y /predict responde 503 con un mensaje, no un 500 mudo."""

    def _cargar_modelo_que_falla() -> ModeloServido:
        raise RuntimeError("MLflow no responde")

    monkeypatch.setattr(main, "cargar_modelo", _cargar_modelo_que_falla)
    with TestClient(main.app) as client:
        salud = client.get("/health")
        assert salud.status_code == 200
        assert salud.json()["modelo_cargado"] is False

        prediccion = client.post("/predict", json=VIAJE)
        assert prediccion.status_code == 503
