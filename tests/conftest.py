"""Fixtures basados en el generador de `trips.data.synthetic`.

El generador vive en el paquete (no aquí) para que el job de CI que corre el
pipeline completo en `main` use exactamente los mismos datos sintéticos que
estas pruebas, en vez de mantener dos generadores que tarde o temprano se
desincronizan (ver `src/trips/data/synthetic.py`).

Cada fixture roto reproduce una degradación real, no un caso imposible.
"""

import pandas as pd
import pytest

from trips.data.synthetic import generar_viajes_sinteticos

SEMILLA = 42
N = 2_000


def _viajes_validos(n: int = N, semilla: int = SEMILLA) -> pd.DataFrame:
    return generar_viajes_sinteticos(n=n, semilla=semilla)


@pytest.fixture
def df_crudo_valido() -> pd.DataFrame:
    return _viajes_validos()


@pytest.fixture
def tres_lotes_validos() -> list[pd.DataFrame]:
    """Control negativo: si el contrato rechaza estos tres, es que rechaza todo.

    Un contrato demasiado estricto es tan inútil como uno ausente, y falla de
    una forma más molesta: bloquea el pipeline con datos buenos.
    """
    return [_viajes_validos(semilla=s) for s in (1, 2, 3)]


@pytest.fixture
def df_crudo_zona_invalida() -> pd.DataFrame:
    """Coordenadas fuera de Jersey City: el proveedor mezcló otra ciudad."""
    df = _viajes_validos()
    df.loc[:20, "start_lat"] = 6.24  # Medellín
    df.loc[:20, "start_lng"] = -75.58
    return df


@pytest.fixture
def df_crudo_viaje_al_reves() -> pd.DataFrame:
    """Fin antes que inicio: reloj desincronizado en una estación."""
    df = _viajes_validos()
    df.loc[5, "ended_at"] = df.loc[5, "started_at"] - pd.Timedelta(minutes=10)
    return df


@pytest.fixture
def df_crudo_truncado() -> pd.DataFrame:
    """La descarga se cortó: 50 filas perfectas de un archivo de 109 mil."""
    return _viajes_validos().head(50)


@pytest.fixture
def df_crudo_sin_destino() -> pd.DataFrame:
    """El 30% sin destino registrado: en julio fue el 0,3%."""
    df = _viajes_validos()
    df.loc[: int(len(df) * 0.3), "end_station_id"] = None
    return df


@pytest.fixture
def df_crudo_categoria_nueva() -> pd.DataFrame:
    """Citi Bike agregó un tipo de bicicleta que el modelo nunca vio."""
    df = _viajes_validos()
    df.loc[:10, "rideable_type"] = "cargo_bike"
    return df


@pytest.fixture
def df_crudo_con_nulos() -> pd.DataFrame:
    """Falta la marca de tiempo de inicio: sin eso no hay duración posible."""
    df = _viajes_validos()
    df.loc[:5, "started_at"] = pd.NaT
    return df
