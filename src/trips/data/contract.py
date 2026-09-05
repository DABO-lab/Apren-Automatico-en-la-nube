"""El contrato de los datos: qué forma deben tener para que el resto funcione.

Dos contratos, no uno:

- `ViajesCrudos` valida el CSV tal como llega de Citi Bike, con rangos anchos.
  Es la aduana: si el proveedor cambia algo, nos enteramos al cargar.
- `ViajesLimpios` valida lo que sale de clean.py, con cotas estrictas. Es la
  garantía de que nuestras propias reglas hicieron lo que dicen.

Tres niveles de validación, porque cada uno atrapa una clase distinta de error:

1. Por fila (`pa.Field`): un valor imposible en un registro suelto.
2. Por distribución (`@pa.dataframe_check` sobre agregados): el archivo llegó
   completo pero cambió de forma.
3. Entre columnas: incoherencias que ninguna columna revela por separado, como
   un viaje que termina antes de empezar.

Los umbrales salen del EDA (docs/guia-del-proyecto.md), no del aire.
"""

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series

# Caja geográfica de Jersey City y Hoboken, con holgura.
LAT_MIN, LAT_MAX = 40.60, 40.85
LNG_MIN, LNG_MAX = -74.20, -73.90

# Volumen mínimo esperado: julio tuvo 109 mil viajes. Un archivo de 200 filas
# no es "pocos datos", es un archivo truncado en la descarga.
MIN_FILAS = 1_000


class ViajesCrudos(pa.DataFrameModel):
    """El CSV tal como lo publica Citi Bike."""

    ride_id: Series[str] = pa.Field(unique=True, nullable=False)
    rideable_type: Series[str] = pa.Field(isin=["classic_bike", "electric_bike"])
    started_at: Series[pd.Timestamp] = pa.Field(nullable=False)
    ended_at: Series[pd.Timestamp] = pa.Field(nullable=False)

    start_station_name: Series[str] = pa.Field(nullable=True)
    start_station_id: Series[str] = pa.Field(nullable=True)
    # El destino SÍ puede faltar: son los 330 viajes sin devolución registrada.
    end_station_name: Series[str] = pa.Field(nullable=True)
    end_station_id: Series[str] = pa.Field(nullable=True)

    start_lat: Series[float] = pa.Field(ge=LAT_MIN, le=LAT_MAX, nullable=False)
    start_lng: Series[float] = pa.Field(ge=LNG_MIN, le=LNG_MAX, nullable=False)
    end_lat: Series[float] = pa.Field(ge=LAT_MIN, le=LAT_MAX, nullable=True)
    end_lng: Series[float] = pa.Field(ge=LNG_MIN, le=LNG_MAX, nullable=True)

    member_casual: Series[str] = pa.Field(isin=["member", "casual"])

    class Config:
        strict = False  # columnas nuevas del proveedor no rompen la carga
        coerce = True

    @pa.dataframe_check(name="volumen_minimo")
    def hay_suficientes_filas(cls, df: pd.DataFrame) -> bool:
        """Un archivo truncado pasa todas las validaciones por fila."""
        return len(df) >= MIN_FILAS

    @pa.dataframe_check(name="el_viaje_termina_despues_de_empezar")
    def orden_temporal(cls, df: pd.DataFrame) -> bool:
        return bool((df["ended_at"] > df["started_at"]).all())

    @pa.dataframe_check(name="destino_incompleto_es_excepcional")
    def pocos_destinos_faltantes(cls, df: pd.DataFrame) -> bool:
        """En julio fue el 0,3%. Si un mes llega al 5%, algo cambió en el
        sistema y hay que mirarlo antes de entrenar con esos datos."""
        return df["end_station_id"].isna().mean() < 0.05


class ViajesLimpios(pa.DataFrameModel):
    """Lo que sale de clean.py: ya con duración y sin filas imposibles."""

    ride_id: Series[str] = pa.Field(unique=True, nullable=False)
    rideable_type: Series[str] = pa.Field(isin=["classic_bike", "electric_bike"])
    started_at: Series[pd.Timestamp] = pa.Field(nullable=False)
    ended_at: Series[pd.Timestamp] = pa.Field(nullable=False)
    member_casual: Series[str] = pa.Field(isin=["member", "casual"])

    # Después de limpiar, el destino ya no puede faltar: esas filas se eliminan.
    end_station_name: Series[str] = pa.Field(nullable=False)
    end_station_id: Series[str] = pa.Field(nullable=False)
    end_lat: Series[float] = pa.Field(ge=LAT_MIN, le=LAT_MAX, nullable=False)
    end_lng: Series[float] = pa.Field(ge=LNG_MIN, le=LNG_MAX, nullable=False)

    # Piso: Citi Bike ya descarta los viajes de menos de un minuto.
    # Techo: 24 horas, la regla del paso 3 de clean.py.
    duracion_min: Series[float] = pa.Field(ge=1.0, le=24 * 60, nullable=False)

    class Config:
        strict = False
        coerce = True

    @pa.dataframe_check(name="volumen_minimo")
    def hay_suficientes_filas(cls, df: pd.DataFrame) -> bool:
        return len(df) >= MIN_FILAS

    @pa.dataframe_check(name="la_duracion_coincide_con_las_marcas_de_tiempo")
    def duracion_coherente(cls, df: pd.DataFrame) -> bool:
        """`duracion_min` es una columna derivada: si alguien la modifica sin
        tocar las marcas de tiempo, este check lo atrapa."""
        esperada = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60
        return bool((esperada - df["duracion_min"]).abs().max() < 0.01)

    @pa.dataframe_check(name="la_mayoria_de_viajes_son_cortos")
    def forma_de_la_distribucion(cls, df: pd.DataFrame) -> bool:
        """En julio, el 91,7% duró menos de 20 minutos y la mediana fue 6,4.
        Si la mediana se sale de este rango, el mes que llegó no se parece al
        que entrenó el modelo — y eso hay que verlo ANTES de reentrenar."""
        return 3.0 <= df["duracion_min"].median() <= 15.0
