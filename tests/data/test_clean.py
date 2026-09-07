"""Las cuatro reglas de limpieza, una por una."""

import pandas as pd

from trips.data.clean import clean_trips


def _viaje(ride_id, inicio, minutos, origen="A", destino="B", con_destino=True):
    inicio = pd.Timestamp(inicio)
    return {
        "ride_id": ride_id,
        "rideable_type": "classic_bike",
        "started_at": inicio,
        "ended_at": inicio + pd.Timedelta(minutes=minutos),
        "start_station_name": origen,
        "start_station_id": "S1",
        "end_station_name": destino if con_destino else None,
        "end_station_id": "S2" if con_destino else None,
        "start_lat": 40.72,
        "start_lng": -74.04,
        "end_lat": 40.73 if con_destino else None,
        "end_lng": -74.03 if con_destino else None,
        "member_casual": "member",
    }


def test_construye_la_duracion():
    df = pd.DataFrame([_viaje("R1", "2026-07-01 08:00", 7.5)])
    assert clean_trips(df)["duracion_min"].iloc[0] == 7.5


def test_elimina_viajes_sin_destino():
    df = pd.DataFrame(
        [
            _viaje("R1", "2026-07-01 08:00", 10),
            _viaje("R2", "2026-07-01 09:00", 10, con_destino=False),
        ]
    )
    assert list(clean_trips(df)["ride_id"]) == ["R1"]


def test_elimina_viajes_de_mas_de_24_horas():
    df = pd.DataFrame(
        [
            _viaje("R1", "2026-07-01 08:00", 10),
            _viaje("R2", "2026-07-01 09:00", 25 * 60),
        ]
    )
    assert list(clean_trips(df)["ride_id"]) == ["R1"]


def test_elimina_falsos_viajes_en_la_misma_estacion():
    """Menos de 2 minutos y devuelta donde se sacó: bici dañada, no viaje."""
    df = pd.DataFrame(
        [
            _viaje("R1", "2026-07-01 08:00", 1.5, origen="A", destino="A"),
            _viaje("R2", "2026-07-01 09:00", 10),
        ]
    )
    assert list(clean_trips(df)["ride_id"]) == ["R2"]


def test_conserva_los_paseos_de_ida_y_vuelta():
    """Misma estación pero duración normal: es un paseo real, se queda.

    La regla necesita las DOS condiciones; con una sola se llevaría viajes
    legítimos por delante.
    """
    df = pd.DataFrame([_viaje("R1", "2026-07-01 08:00", 25, origen="A", destino="A")])
    assert list(clean_trips(df)["ride_id"]) == ["R1"]
