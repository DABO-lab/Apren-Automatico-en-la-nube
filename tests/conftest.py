"""Fixtures generados en código, no archivos CSV.

Un CSV de prueba se desactualiza y nadie se entera; un generador con semilla
fija produce siempre los mismos datos y se lee como documentación de qué
esperamos. Cada fixture roto reproduce una degradación real, no un caso
imposible.
"""

import numpy as np
import pandas as pd
import pytest

SEMILLA = 42
N = 2_000


def _viajes_validos(n: int = N, semilla: int = SEMILLA) -> pd.DataFrame:
    """Un lote que se parece a julio: cola larga, mediana cerca de 6 minutos."""
    rng = np.random.default_rng(semilla)
    inicio = pd.Timestamp("2026-07-01") + pd.to_timedelta(
        rng.integers(0, 31 * 24 * 60, n), unit="m"
    )
    duracion = np.clip(rng.lognormal(1.85, 0.75, n), 1.0, 1439)
    return pd.DataFrame(
        {
            "ride_id": [f"R{i:07d}" for i in range(n)],
            "rideable_type": rng.choice(["classic_bike", "electric_bike"], n),
            "started_at": inicio,
            "ended_at": inicio + pd.to_timedelta(duracion, unit="m"),
            "start_station_name": rng.choice(["Grove St PATH", "Hamilton Park"], n),
            "start_station_id": rng.choice(["JC001", "JC002"], n),
            "end_station_name": rng.choice(["Newark Ave", "River St"], n),
            "end_station_id": rng.choice(["JC003", "JC004"], n),
            "start_lat": 40.72 + rng.normal(0, 0.01, n),
            "start_lng": -74.04 + rng.normal(0, 0.01, n),
            "end_lat": 40.73 + rng.normal(0, 0.01, n),
            "end_lng": -74.03 + rng.normal(0, 0.01, n),
            "member_casual": rng.choice(["member", "casual"], n, p=[0.72, 0.28]),
        }
    )


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
