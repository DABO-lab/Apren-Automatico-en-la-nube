"""Las variables derivadas: lo único que el modelo ve además de lo que llega."""

import pandas as pd

from trips.features import add_features, haversine_km


def test_haversine_contra_una_distancia_conocida():
    """Grove St PATH a Hoboken Terminal: ~1,9 km en línea recta.

    Una fórmula de distancia mal implementada no falla: devuelve números
    plausibles pero equivocados. Por eso se contrasta con un valor real.
    """
    km = haversine_km(40.7196, -74.0431, 40.7360, -74.0277)
    assert 1.8 < km < 2.3


def test_haversine_es_cero_en_el_mismo_punto():
    assert haversine_km(40.72, -74.04, 40.72, -74.04) == 0.0


def test_haversine_es_simetrica():
    ida = haversine_km(40.72, -74.04, 40.74, -74.02)
    vuelta = haversine_km(40.74, -74.02, 40.72, -74.04)
    assert abs(ida - vuelta) < 1e-9


def test_add_features_agrega_las_cuatro_variables(df_crudo_valido: pd.DataFrame):
    resultado = add_features(df_crudo_valido)
    for columna in ["hora", "dia_semana", "es_finde", "distancia_km"]:
        assert columna in resultado.columns


def test_add_features_no_calcula_velocidad(df_crudo_valido: pd.DataFrame):
    """velocidad_kmh se construye con la duración: es fuga de información.

    Si alguien la agrega al paquete "porque es útil", esta prueba lo detiene.
    """
    assert "velocidad_kmh" not in add_features(df_crudo_valido).columns


def test_add_features_no_modifica_el_original(df_crudo_valido: pd.DataFrame):
    columnas_antes = list(df_crudo_valido.columns)
    add_features(df_crudo_valido)
    assert list(df_crudo_valido.columns) == columnas_antes


def test_es_finde_marca_sabado_y_domingo():
    df = pd.DataFrame(
        {
            "started_at": pd.to_datetime(["2026-07-04", "2026-07-05", "2026-07-06"]),
            "start_lat": [40.72] * 3,
            "start_lng": [-74.04] * 3,
            "end_lat": [40.73] * 3,
            "end_lng": [-74.03] * 3,
        }
    )
    assert list(add_features(df)["es_finde"]) == [True, True, False]
