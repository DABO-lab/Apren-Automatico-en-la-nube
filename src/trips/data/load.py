"""Carga el CSV crudo de Citi Bike y verifica que llegue como esperamos.

Este módulo hace UNA sola cosa: leer el archivo tal como lo publica Citi Bike
y devolver un DataFrame con los tipos correctos. No limpia, no filtra y no
crea variables nuevas — eso es trabajo de clean.py.

La regla de oro de `data/raw/`: los datos crudos son intocables. Aquí solo
se leen.

Uso desde la terminal:
    uv run python -m trips.data.load

Uso desde un notebook:
    from trips.data.load import load_trips
    df = load_trips()
"""

import pandas as pd

from trips.config import DATE_COLUMNS, EXPECTED_COLUMNS, RAW_DATA_PATH
from trips.data.contract import ViajesCrudos

# Tipos declarados de entrada: pedirle a pandas que lea los identificadores
# como texto evita que convierta "3186" en un número y pierda ceros a la
# izquierda; las categóricas ocupan una fracción de la memoria de un object.
DTYPES = {
    "ride_id": "string",
    "rideable_type": "category",
    "start_station_name": "string",
    "start_station_id": "string",
    "end_station_name": "string",
    "end_station_id": "string",
    "member_casual": "category",
    "start_lat": "float64",
    "start_lng": "float64",
    "end_lat": "float64",
    "end_lng": "float64",
}


def validate_schema(df: pd.DataFrame) -> None:
    """Falla temprano si el archivo no trae las columnas que el proyecto espera.

    Un error aquí es una buena noticia: significa que el contrato de entrada
    cambió y nos enteramos ANTES de entrenar, no después.
    """
    faltantes = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"Al archivo le faltan columnas esperadas: {faltantes}. "
            f"Columnas encontradas: {list(df.columns)}"
        )

    sobrantes = [c for c in df.columns if c not in EXPECTED_COLUMNS]
    if sobrantes:
        print(f"Aviso - columnas nuevas no contempladas en config.py: {sobrantes}")


def load_trips(path=None, validar: bool = True) -> pd.DataFrame:
    """Lee el CSV crudo de viajes y devuelve el DataFrame ya tipado.

    Args:
        path: ruta alternativa al CSV. Por defecto, la de config.RAW_DATA_PATH.
        validar: aplica el contrato `ViajesCrudos`. Se puede desactivar para
            inspeccionar un archivo que justamente sospechamos que está mal.
    """
    ruta = path or RAW_DATA_PATH

    if not ruta.exists():
        raise FileNotFoundError(
            f"No encuentro el archivo de datos en: {ruta}\n"
            "Descarga el CSV de Citi Bike o apunta a tu copia con la variable "
            "de entorno TRIPS_RAW_DATA (ver src/trips/config.py)."
        )

    df = pd.read_csv(ruta, dtype=DTYPES, parse_dates=DATE_COLUMNS)
    validate_schema(df)

    if validar:
        # lazy=True junta TODOS los incumplimientos en un solo informe, en vez
        # de detenerse en el primero. Diagnosticar diez problemas de una vez es
        # mucho más rápido que descubrirlos uno por corrida.
        ViajesCrudos.validate(df, lazy=True)
    return df


def describe_raw(df: pd.DataFrame) -> None:
    """Imprime la ficha técnica del archivo crudo: qué llegó y en qué estado."""
    print(f"Filas x columnas:  {df.shape[0]:,} x {df.shape[1]}")
    print(f"Memoria:           {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
    print(f"Rango de fechas:   {df['started_at'].min()}  ->  {df['started_at'].max()}")
    print(f"ride_id duplicados: {df['ride_id'].duplicated().sum()}")
    print(f"Filas duplicadas:   {df.duplicated().sum()}")

    print("---")
    print("Nulos por columna (solo las que tienen):")
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].sort_values(ascending=False)
    if nulos.empty:
        print("  ninguna columna tiene nulos")
    else:
        for columna, n in nulos.items():
            print(f"  {columna:<20} {n:>7,}  ({n / len(df):.1%})")


def main() -> None:
    print(f"Leyendo {RAW_DATA_PATH}")
    df = load_trips()
    print("---")
    describe_raw(df)


if __name__ == "__main__":
    main()
