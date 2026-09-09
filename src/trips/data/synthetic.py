"""Generador de viajes sintéticos: la misma fuente que usan las pruebas.

No es un sustituto de los datos reales de julio. Sirve para dos cosas que SÍ
necesitan datos con la forma correcta pero no necesitan que sean reales:

1. Los fixtures de `tests/conftest.py` (las siete degradaciones y los tres
   lotes válidos de control negativo salen todos de aquí).
2. El job de CI que corre el pipeline completo en cada push a `main`
   (ver `scripts/generar_datos_ci.py`): el CSV crudo real no está en el
   repositorio -pesa demasiado y no se versiona (sección 1.5 del informe de
   estado)-, así que sin esto GitHub Actions no tendría nada que procesar.

Vivir en un solo lugar es la razón de ser de este módulo: si cambia el
esquema de columnas, se cambia aquí y tanto las pruebas como el CI lo heredan
automáticamente, en vez de mantener dos generadores que tarde o temprano se
desincronizan (mismo principio que `config.py`, sección 4 del informe).
"""

import numpy as np
import pandas as pd


def generar_viajes_sinteticos(n: int = 2_000, semilla: int = 42) -> pd.DataFrame:
    """Un lote que se parece a julio: cola larga, mediana cerca de 6 minutos.

    La duración sale de una lognormal (mu=1.85, sigma=0.75 en escala log): esa
    combinación da una mediana de ~6.3 minutos, dentro del rango 3-15 que
    exige el contrato `ViajesLimpios` después de limpiar (ver
    `src/trips/data/contract.py`).
    """
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
