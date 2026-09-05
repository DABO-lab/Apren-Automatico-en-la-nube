"""El contrato de la API: qué entra y qué sale.

Pydantic valida ANTES de que el modelo vea nada. Los rangos no son
decorativos: salen de los datos con los que se entrenó (ver
docs/guia-del-proyecto.md). Un viaje fuera de esos rangos no es un caso
difícil, es un caso que el modelo nunca vio — y es mejor rechazarlo con un
mensaje claro que devolver un número inventado con cara de certeza.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Caja aproximada de Jersey City y Hoboken. Un viaje en Medellín no lo puede
# predecir este modelo, y conviene decirlo en vez de responder cualquier cosa.
LAT_MIN, LAT_MAX = 40.65, 40.80
LNG_MIN, LNG_MAX = -74.12, -73.95


class ViajeRequest(BaseModel):
    """Un viaje que empieza. Lo que se sabe ANTES de que termine."""

    # extra="forbid": si el cliente manda un campo que no existe, es un error.
    # Explícito mejor que implícito: un campo mal escrito debe fallar, no
    # ignorarse en silencio.
    model_config = ConfigDict(extra="forbid")

    started_at: datetime = Field(description="Inicio del viaje, sin zona horaria")
    start_lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    start_lng: float = Field(ge=LNG_MIN, le=LNG_MAX)
    end_lat: float = Field(ge=LAT_MIN, le=LAT_MAX)
    end_lng: float = Field(ge=LNG_MIN, le=LNG_MAX)
    member_casual: Literal["member", "casual"]
    rideable_type: Literal["classic_bike", "electric_bike"]

    @field_validator("started_at")
    @classmethod
    def sin_zona_horaria(cls, valor: datetime) -> datetime:
        """Rechaza fechas con zona horaria.

        El modelo aprendió con horas locales de Nueva Jersey. Aceptar una
        fecha con zona horaria significaría convertirla en silencio, y una
        conversión silenciosa es un error que nadie ve hasta que las
        predicciones de la madrugada salen raras.
        """
        if valor.tzinfo is not None:
            raise ValueError(
                "started_at debe ir sin zona horaria (hora local del sistema de bicicletas)"
            )
        return valor


class PrediccionResponse(BaseModel):
    """La predicción y de dónde salió."""

    duracion_min: float = Field(description="Duración estimada en minutos")
    distancia_km: float = Field(description="Distancia en línea recta calculada")
    modelo: str
    version: str


class LoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    viajes: list[ViajeRequest] = Field(min_length=1, max_length=1000)


class LoteResponse(BaseModel):
    predicciones: list[PrediccionResponse]


class SaludResponse(BaseModel):
    estado: str
    modelo_cargado: bool


class ModeloResponse(BaseModel):
    """Para quien opera el servicio: qué está sirviendo exactamente."""

    nombre: str
    version: str
    uri: str
    alias: str
    variables: list[str]
    objetivo: str
