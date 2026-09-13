"""API que sirve el modelo de duración de viajes.

    uv run uvicorn trips.api.main:app --reload --port 8000

Documentación interactiva en http://127.0.0.1:8000/docs (la genera FastAPI
sola a partir de los schemas).

Requisito: el servidor de MLflow debe estar arriba, porque el modelo se carga
del registry al iniciar.
"""

import logging
import time
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

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

# Métricas del SERVICIO: cuántas peticiones llegan, qué tan rápido responde,
# qué está prediciendo. Esto es distinto de lo que mide
# `trips.monitoring.check_drift` (el reporte de `make drift`), que compara
# la distribución de los DATOS de entrada contra la de entrenamiento.
# Prometheus vigila si la API está sana; el reporte de drift vigila si el
# mundo todavía se parece a lo que aprendió el modelo. Las dos preguntas son
# necesarias y ninguna sustituye a la otra: la API puede responder rápido y
# sano mientras predice sobre datos que ya no se parecen a julio.
PREDICCIONES_TOTAL = Counter(
    "trips_predicciones_total",
    "Peticiones a /predict y /predict/batch, por resultado.",
    ["resultado"],
)
PREDICCION_LATENCIA_SEGUNDOS = Histogram(
    "trips_prediccion_latencia_segundos",
    "Tiempo que tarda una predicción individual en resolverse.",
)
PREDICCION_DURACION_MIN = Histogram(
    "trips_prediccion_duracion_min",
    "Distribución de las duraciones que predice el modelo, en minutos.",
    buckets=(1, 2, 5, 10, 15, 20, 30, 45, 60, 90, 120),
)

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
    modelo = estado["modelo"]
    return SaludResponse(
        estado="ok",
        modelo_cargado=modelo is not None,
        version_modelo=modelo.version if modelo is not None else None,
    )


@app.get("/metrics")
def metrics() -> Response:
    """Métricas del servicio en formato Prometheus. Ver el comentario junto
    a las métricas más arriba: esto mide el servicio, no los datos."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    inicio = time.perf_counter()
    try:
        resultado = modelo.predecir(pd.DataFrame([viaje.model_dump()])).iloc[0]
    except Exception:
        PREDICCIONES_TOTAL.labels(resultado="error").inc()
        raise
    PREDICCION_LATENCIA_SEGUNDOS.observe(time.perf_counter() - inicio)
    PREDICCION_DURACION_MIN.observe(float(resultado["duracion_min"]))
    PREDICCIONES_TOTAL.labels(resultado="ok").inc()
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
    inicio = time.perf_counter()
    try:
        viajes = pd.DataFrame([v.model_dump() for v in lote.viajes])
        resultados = modelo.predecir(viajes)
    except Exception:
        PREDICCIONES_TOTAL.labels(resultado="error").inc(len(lote.viajes))
        raise
    PREDICCION_LATENCIA_SEGUNDOS.observe(time.perf_counter() - inicio)
    PREDICCIONES_TOTAL.labels(resultado="ok").inc(len(resultados))
    for duracion in resultados["duracion_min"]:
        PREDICCION_DURACION_MIN.observe(float(duracion))
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
