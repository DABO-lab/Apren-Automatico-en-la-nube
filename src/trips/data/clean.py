"""Construye la variable objetivo y limpia los viajes.

Lee el CSV crudo (a través de load.py) y guarda el resultado en
data/processed/viajes_limpio.parquet.

Un paso construye, tres eliminan. Cada uno imprime cuántas filas afectó: el
output de la terminal cuenta la historia de qué se arregló y por qué.

Los umbrales viven en config.py y salen del diagnóstico de los datos crudos,
no del criterio de quien escribió este archivo.

    uv run python -m trips.data.clean
"""

import pandas as pd

from trips.config import (
    END_COLUMNS,
    MAX_DURACION_MIN,
    PROCESSED_DATA_PATH,
    TARGET_COLUMN,
    UMBRAL_FALSO_VIAJE_MIN,
)
from trips.data.contract import ViajesLimpios
from trips.data.load import load_trips


def clean_trips(df: pd.DataFrame) -> pd.DataFrame:
    filas_entrada = len(df)

    # Paso 1: construir la variable objetivo. El archivo no trae la duración;
    # es la diferencia entre las dos marcas de tiempo, en minutos.
    df = df.assign(
        **{TARGET_COLUMN: (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60}
    )
    print(
        f"Paso 1 - Construida '{TARGET_COLUMN}' "
        f"(mediana {df[TARGET_COLUMN].median():.1f} min, "
        f"máximo {df[TARGET_COLUMN].max():.0f} min)"
    )

    # Paso 2: viajes sin destino registrado. Podemos calcularles la duración,
    # pero no sabemos dónde terminaron: no hay estación ni coordenadas, así que
    # ninguna variable de destino (distancia incluida) se puede construir.
    # No se van al azar: pesan más en bicicletas eléctricas y usuarios casuales.
    antes = len(df)
    df = df[df[END_COLUMNS].notna().all(axis=1)]
    print(f"Paso 2 - Eliminados {antes - len(df)} viajes sin destino registrado")

    # Paso 3: duraciones imposibles. En los datos crudos NO hay valores
    # negativos ni menores a un minuto (Citi Bike ya los filtra antes de
    # publicar); el problema está en la cola de arriba. Una bicicleta más de
    # un día fuera no es un viaje largo, es una bicicleta no devuelta.
    antes = len(df)
    df = df[df[TARGET_COLUMN] <= MAX_DURACION_MIN]
    print(
        f"Paso 3 - Eliminados {antes - len(df)} viajes de más de "
        f"{MAX_DURACION_MIN // 60} horas"
    )

    # Paso 4: falsos viajes. Menos de 2 minutos y devuelta en la MISMA estación
    # es el patrón de "saqué la bici, estaba dañada, la devolví". Ojo: los
    # viajes de ida y vuelta a la misma estación con duración normal son paseos
    # reales y se quedan.
    antes = len(df)
    falso_viaje = (df["start_station_name"] == df["end_station_name"]) & (
        df[TARGET_COLUMN] < UMBRAL_FALSO_VIAJE_MIN
    )
    df = df[~falso_viaje]
    print(
        f"Paso 4 - Eliminados {antes - len(df)} falsos viajes "
        f"(misma estación, menos de {UMBRAL_FALSO_VIAJE_MIN} min)"
    )

    print("---")
    print(f"Filas de entrada:  {filas_entrada:,}")
    print(f"Filas de salida:   {len(df):,}  ({len(df) / filas_entrada:.2%} del crudo)")
    print(f"Nulos restantes:   {int(df.isna().sum().sum())}")
    print(
        f"Duración (min):    mediana {df[TARGET_COLUMN].median():.1f} | "
        f"p95 {df[TARGET_COLUMN].quantile(0.95):.1f} | "
        f"máximo {df[TARGET_COLUMN].max():.1f}"
    )
    return df


def main() -> None:
    df = load_trips()
    df_limpio = clean_trips(df)

    # El contrato de salida: la garantía de que las reglas de arriba hicieron
    # lo que dicen. Si una falla, el parquet no se escribe — mejor no tener
    # datos procesados que tenerlos mal y no saberlo.
    ViajesLimpios.validate(df_limpio, lazy=True)
    print("Contrato de salida: validado")

    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_limpio.to_parquet(PROCESSED_DATA_PATH, index=False)
    print(f"Guardado en {PROCESSED_DATA_PATH}")


if __name__ == "__main__":
    main()
