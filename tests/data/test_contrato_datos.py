"""Los datos buenos pasan y los rotos fallan.

Sin la segunda mitad, un contrato se degrada sin que nadie lo note: basta que
alguien relaje un rango un viernes para desactivarlo.
"""

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from trips.data.contract import ViajesCrudos, ViajesLimpios

ERRORES = (SchemaError, SchemaErrors)


# --- Control negativo: el contrato NO puede rechazar datos buenos ---
def test_datos_validos_pasan(df_crudo_valido: pd.DataFrame):
    ViajesCrudos.validate(df_crudo_valido)


def test_tres_lotes_independientes_pasan(tres_lotes_validos: list[pd.DataFrame]):
    for lote in tres_lotes_validos:
        ViajesCrudos.validate(lote)


# --- Nivel 1: por fila ---
def test_coordenadas_fuera_de_la_zona_fallan(df_crudo_zona_invalida: pd.DataFrame):
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_zona_invalida)


def test_tipo_de_bicicleta_desconocido_falla(df_crudo_categoria_nueva: pd.DataFrame):
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_categoria_nueva)


def test_marca_de_tiempo_nula_falla(df_crudo_con_nulos: pd.DataFrame):
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_con_nulos)


# --- Nivel 2: por distribución ---
def test_archivo_truncado_falla(df_crudo_truncado: pd.DataFrame):
    """Cada fila es perfecta; el archivo entero no lo es."""
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_truncado)


def test_exceso_de_destinos_sin_registrar_falla(df_crudo_sin_destino: pd.DataFrame):
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_sin_destino)


# --- Nivel 3: entre columnas ---
def test_viaje_que_termina_antes_de_empezar_falla(
    df_crudo_viaje_al_reves: pd.DataFrame,
):
    """Ninguna columna por separado tiene nada malo."""
    with pytest.raises(ERRORES):
        ViajesCrudos.validate(df_crudo_viaje_al_reves)


# --- El contrato de salida ---
def _limpiar_minimo(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        duracion_min=(df["ended_at"] - df["started_at"]).dt.total_seconds() / 60
    )


def test_datos_limpios_pasan(df_crudo_valido: pd.DataFrame):
    ViajesLimpios.validate(_limpiar_minimo(df_crudo_valido))


def test_duracion_incoherente_falla(df_crudo_valido: pd.DataFrame):
    """Alguien 'corrige' la duración sin tocar las marcas de tiempo."""
    limpio = _limpiar_minimo(df_crudo_valido)
    limpio.loc[3, "duracion_min"] = 999.0
    with pytest.raises(ERRORES):
        ViajesLimpios.validate(limpio)


def test_distribucion_desplazada_falla(df_crudo_valido: pd.DataFrame):
    """Todos los viajes se cuadruplican: cada fila es válida, el mes no."""
    limpio = _limpiar_minimo(df_crudo_valido)
    limpio["ended_at"] = limpio["started_at"] + pd.to_timedelta(
        limpio["duracion_min"] * 4, unit="m"
    )
    limpio["duracion_min"] = limpio["duracion_min"] * 4
    with pytest.raises(ERRORES):
        ViajesLimpios.validate(limpio)
