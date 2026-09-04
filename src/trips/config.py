"""Única fuente de verdad del proyecto.

Todas las rutas, nombres de columnas y números "mágicos" viven aquí. Si un
script y un notebook necesitan el mismo valor, los dos lo importan de este
archivo: así nunca se desincronizan.
"""

import os
from pathlib import Path

# Raíz del repo: dos niveles arriba de este archivo (src/trips/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# --- Rutas de datos -------------------------------------------------------
# El CSV crudo de Citi Bike (julio de 2026, Jersey City y Hoboken) vive fuera
# del repo porque pesa demasiado para versionarlo. Cada integrante puede
# apuntar a su propia copia con la variable de entorno TRIPS_RAW_DATA;
# si no la define, se usa la ruta por defecto.
DEFAULT_RAW_DATA = r"C:\Users\andre\Documents\JC-202607-citibike-tripdata.csv"
RAW_DATA_PATH = Path(os.getenv("TRIPS_RAW_DATA", DEFAULT_RAW_DATA))

# Los datos ya limpios sí quedan dentro del proyecto (formato parquet:
# conserva los tipos y ocupa mucho menos que un CSV).
PROCESSED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "viajes_limpio.parquet"

# Semilla fija: cualquiera que ejecute este código obtiene EXACTAMENTE el
# mismo split y los mismos muestreos. Sin esto no hay reproducibilidad.
RANDOM_SEED = 42

# --- Esquema del dataset --------------------------------------------------
# Columnas tal como las publica Citi Bike (13 en total).
DATE_COLUMNS = ["started_at", "ended_at"]

EXPECTED_COLUMNS = [
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "start_station_name",
    "start_station_id",
    "end_station_name",
    "end_station_id",
    "start_lat",
    "start_lng",
    "end_lat",
    "end_lng",
    "member_casual",
]

# El archivo NO trae la duración: se construye a partir de las marcas de
# tiempo. Este es el nombre que usaremos para la variable objetivo.
TARGET_COLUMN = "duracion_min"
ID_COLUMN = "ride_id"

# --- Reglas de limpieza -----------------------------------------------------
# Los umbrales NO son inventados: salen del diagnóstico de los datos crudos
# (ver la sección de calidad en notebooks/01-carga-y-eda.ipynb).

# Un viaje de más de 24 horas no es un viaje: es una bicicleta no devuelta.
MAX_DURACION_MIN = 24 * 60

# Sacar la bici, ver que está dañada y devolverla en el mismo sitio produce un
# "viaje" de menos de 2 minutos que empieza y termina en la misma estación.
UMBRAL_FALSO_VIAJE_MIN = 2

# Columnas que describen dónde terminó el viaje. Si falta alguna, no sabemos
# a dónde llegó la bicicleta.
END_COLUMNS = ["end_station_id", "end_station_name", "end_lat", "end_lng"]

# --- MLflow -----------------------------------------------------------------
# Puerto 5001 y no 5000: en macOS AirPlay ocupa el 5000 y responde un 403 que
# parece un error de MLflow (y no lo es). Usamos el mismo del curso.
MLFLOW_PORT = 5001
MLFLOW_TRACKING_URI = f"http://127.0.0.1:{MLFLOW_PORT}"
EXPERIMENT_NAME = "duracion-viajes"
REGISTERED_MODEL_NAME = "duracion-regressor"

# --- Modelado ---------------------------------------------------------------
# Partición 80/20 con lógica temporal: se ordena por fecha de inicio y el 20%
# más reciente queda para prueba. Predecir el pasado con datos del futuro es
# hacer trampa, aunque el reloj no aparezca en ninguna columna.
TEST_SIZE = 0.2

# Las variables que salieron del EDA (ver docs/guia-del-proyecto.md, sección 7).
NUMERIC_FEATURES = ["distancia_km"]

# `hora` y `dia_semana` son números pero NO son cantidades: la hora 23 no es
# "mayor" que la 1, es su vecina. Se tratan como categorías para que el modelo
# lineal pueda capturar la forma de U que mostró el EDA.
# `es_finde` no entra: es redundante con `dia_semana` una vez codificado.
CATEGORICAL_FEATURES = ["member_casual", "rideable_type", "hora", "dia_semana"]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
