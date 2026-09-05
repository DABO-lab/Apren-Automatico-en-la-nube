"""API que sirve el modelo de duración de viajes.

    uv run uvicorn trips.api.main:app --reload --port 8000

Documentación interactiva en http://127.0.0.1:8000/docs (la genera FastAPI
sola a partir de los schemas).

Requisito: el servidor de MLflow debe estar arriba, porque el modelo se carga
del registry al iniciar.
"""

import logging
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException

from trips.api.modelo import ALIAS, ModeloServido, cargar_modelo
from trips.api.schemas import (
    LoteRequest,
    LoteResponse,
    ModeloResponse,
    PrediccionResponse,
    SaludResponse,
    ViajeRequest,
)
from trips.config import FEATURE_COLUMNS, TARGET_COLUMN

log = logging.getLogger("trips.api")

# El modelo se carga UNA vez al arrancar, no en cada petición: cargarlo
# tarda segundos y una API que lo hiciera por petición sería inservible.
estado: dict[str, ModeloServido | None] = {"modelo": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga el modelo al arrancar y lo suelta al apagar.

    Si MLflow no responde, la API arranca igual pero sin modelo: /health
    seguirá contestando (para que el orquestador sepa que el proceso vive) y
    /predict devolverá 503. Un servicio que no arranca no se puede
    diagnosticar; uno que arranca degradado, sí.
    """
    try:
        estado["modelo"] = cargar_modelo()
        log.info("Modelo cargado: versión %s", estado["modelo"].version)
    except Exception as error:  # noqa: BLE001
        log.error("No se pudo cargar el modelo del registry: %s", error)
        estado["modelo"] = None
    yield
    estado["modelo"] = None


app = FastAPI(
    title="Duración de viajes Citi Bike",
    description=(
        "Predice cuántos minutos va a durar un viaje en bicicleta pública "
        "de Jersey City y Hoboken."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _modelo() -> ModeloServido:
    modelo = estado["modelo"]
    if modelo is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "El modelo no está disponible. Verifica que MLflow esté corriendo "
                f"y que exista el alias '{ALIAS}'."
            ),
        )
    return modelo


@app.get("/health", response_model=SaludResponse)
def health() -> SaludResponse:
    """Señal de vida. Responde 200 aunque el modelo no haya cargado."""
    return SaludResponse(estado="ok", modelo_cargado=estado["modelo"] is not None)


@app.get("/modelo", response_model=ModeloResponse)
def info_modelo() -> ModeloResponse:
    """Qué modelo se está sirviendo exactamente, para quien opere el servicio."""
    modelo = _modelo()
    return ModeloResponse(
        nombre=modelo.nombre,
        version=modelo.version,
        uri=modelo.uri,
        alias=ALIAS,
        variables=FEATURE_COLUMNS,
        objetivo=f"log1p({TARGET_COLUMN}) — la respuesta va en minutos",
    )


@app.post("/predict", response_model=PrediccionResponse)
def predict(viaje: ViajeRequest) -> PrediccionResponse:
    """Predice la duración de un viaje."""
    modelo = _modelo()
    resultado = modelo.predecir(pd.DataFrame([viaje.model_dump()])).iloc[0]
    return PrediccionResponse(
        duracion_min=float(resultado["duracion_min"]),
        distancia_km=float(resultado["distancia_km"]),
        modelo=modelo.nombre,
        version=modelo.version,
    )


@app.post("/predict/batch", response_model=LoteResponse)
def predict_batch(lote: LoteRequest) -> LoteResponse:
    """Predice varios viajes en una sola llamada.

    Mil viajes en una petición cuestan mucho menos que mil peticiones: el
    modelo se invoca una vez sobre todo el lote.
    """
    modelo = _modelo()
    viajes = pd.DataFrame([v.model_dump() for v in lote.viajes])
    resultados = modelo.predecir(viajes)
    return LoteResponse(
        predicciones=[
            PrediccionResponse(
                duracion_min=float(fila["duracion_min"]),
                distancia_km=float(fila["distancia_km"]),
                modelo=modelo.nombre,
                version=modelo.version,
            )
            for _, fila in resultados.iterrows()
        ]
    )
