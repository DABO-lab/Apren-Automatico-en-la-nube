# ============================================================================
# Imagen de la API que sirve el modelo de duración de viajes.
#
# Construcción en dos etapas (multi-stage): la primera instala dependencias y
# la segunda se queda solo con lo necesario para ejecutar. Así el uv, las
# cachés y las herramientas de construcción no viajan en la imagen final.
# ============================================================================

# ---------------------------------------------------------------------------
# Etapa 1 — construir el entorno virtual
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# El binario de uv se copia de su imagen oficial: más simple y reproducible
# que instalarlo con un script.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# UV_COMPILE_BYTECODE: precompila los .pyc para que el arranque sea más rápido.
# UV_LINK_MODE=copy: evita los enlaces duros, que no funcionan entre capas.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Las dependencias EXACTAS del lock, sin las de desarrollo.
# --frozen: falla si el lock no coincide con el pyproject; nada de resolver
# de nuevo dentro de la imagen, que es justo lo que rompe la reproducibilidad.
# --no-dev: sin jupyter, ruff ni pre-commit — dentro del contenedor no se desarrolla.
# README.md va aquí porque pyproject.toml lo declara como 'readme':
# sin él, hatchling falla al construir el paquete.
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Etapa 2 — la imagen que se ejecuta
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Usuario sin privilegios. Si alguien logra ejecutar código a través de la
# API, se encuentra con una cuenta que no puede instalar nada ni tocar el
# sistema. Correr contenedores como root es el descuido más común y el más
# innecesario.
RUN useradd --create-home --uid 1000 apiuser

WORKDIR /app

# Solo llega el entorno ya construido y el código: ni uv, ni cachés, ni el lock.
COPY --from=builder --chown=apiuser:apiuser /app/.venv /app/.venv
COPY --chown=apiuser:apiuser src/ src/

# Dentro del contenedor, 127.0.0.1 es el contenedor mismo. host.docker.internal
# apunta a la máquina que lo hospeda, que es donde corre el servidor de MLflow.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    MLFLOW_TRACKING_URI=http://host.docker.internal:5001

USER apiuser

EXPOSE 8000

# Docker consulta /health periódicamente. Un contenedor que arrancó no es lo
# mismo que un contenedor que está sirviendo: esto distingue las dos cosas.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# --host 0.0.0.0: escuchar hacia fuera del contenedor. Con 127.0.0.1 la API
# funcionaría solo dentro y no podrías llamarla desde tu navegador.
CMD ["uvicorn", "trips.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
