"""El contrato de la API rechaza lo que el modelo no puede responder."""

import pytest
from pydantic import ValidationError

from trips.api.schemas import ViajeRequest

VIAJE = {
    "started_at": "2026-08-04T08:15:00",
    "start_lat": 40.7215,
    "start_lng": -74.0365,
    "end_lat": 40.7375,
    "end_lng": -74.0295,
    "member_casual": "member",
    "rideable_type": "electric_bike",
}


def test_viaje_valido_se_acepta():
    assert ViajeRequest(**VIAJE).member_casual == "member"


def test_coordenadas_de_otra_ciudad_se_rechazan():
    with pytest.raises(ValidationError):
        ViajeRequest(**{**VIAJE, "start_lat": 6.24, "start_lng": -75.58})


def test_tipo_de_usuario_inventado_se_rechaza():
    with pytest.raises(ValidationError):
        ViajeRequest(**{**VIAJE, "member_casual": "invitado"})


def test_campo_desconocido_se_rechaza():
    """Un campo mal escrito debe fallar, no ignorarse en silencio."""
    with pytest.raises(ValidationError):
        ViajeRequest(**{**VIAJE, "distancia_km": 2.0})


def test_fecha_con_zona_horaria_se_rechaza():
    """El modelo aprendió con hora local; convertir en silencio es un error mudo."""
    with pytest.raises(ValidationError):
        ViajeRequest(**{**VIAJE, "started_at": "2026-08-04T08:15:00+00:00"})
