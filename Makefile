.PHONY: setup data features mlflow train flow flow-serve promote prefect-ui api docker-build docker-run drift test lint notebook model-card smoke

# Instala las dependencias exactas del uv.lock y activa el hook de pre-commit
setup:
	uv sync
	uv run pre-commit install

# Lee el CSV crudo, muestra su ficha tecnica y lo limpia: raw -> processed
data:
	uv run python -m trips.data.load
	uv run python -m trips.data.clean

# Agrega las variables derivadas y muestra un resumen (requiere el parquet limpio)
features:
	uv run python -m trips.features

# Levanta el servidor de MLflow en el puerto 5001 (queda en primer plano; usa otra terminal).
# --host 0.0.0.0: escuchar tambien hacia fuera del equipo. Con 127.0.0.1 el
# contenedor de la API no puede alcanzarlo, porque para el somos otra maquina.
# --workers 1: en Windows, varios procesos compartiendo el mismo socket fallan
# con WinError 10022. Con uno solo sobra para desarrollo.
mlflow:
	uv run python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 0.0.0.0 --port 5001 --workers 1 --allowed-hosts "localhost:5001,127.0.0.1:5001,host.docker.internal:5001"

# Entrena las 20 configuraciones (1 baseline + 7 ridge + 12 histgb), las
# registra y marca la mejor como 'candidate'
train:
	uv run python -m trips.models.train

# Corre el pipeline completo orquestado con Prefect, UNA vez:
# datos -> variables -> drift -> modelos en paralelo -> candidato
# La segunda corrida sobre los mismos datos sale de cache (~40 s -> ~1 s)
flow:
	uv run python -m trips.flows.training

# Deja el flujo corriendo con un schedule (3 a.m. todos los dias), visible
# en la pestana Deployments de http://127.0.0.1:4200. Requiere 'make
# prefect-ui' arriba. Queda en primer plano: usa otra terminal.
flow-serve:
	uv run python -m trips.flows.training --serve

# La compuerta: promueve el candidato a champion solo si mejora lo suficiente
promote:
	uv run python scripts/promote.py

# Tablero de Prefect en http://127.0.0.1:4200 (queda en primer plano)
prefect-ui:
	uv run prefect server start

# Levanta la API que sirve el modelo champion (MLflow debe estar arriba)
api:
	uv run uvicorn trips.api.main:app --host 127.0.0.1 --port 8000 --reload

# Construye la imagen de la API
docker-build:
	docker build -t trips-api .

# Corre la API en un contenedor (MLflow debe estar arriba en la maquina anfitriona)
docker-run:
	docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway trips-api

# Chequeo de drift: compara los datos recientes con los de entrenamiento
# Codigos de salida: 0 sin alerta, 1 drift detectado, 2 no evaluable
drift:
	uv run python -m trips.monitoring.check_drift

# Corre la suite de pruebas (contrato de datos, limpieza, variables y API)
test:
	uv run pytest

# Revisa y formatea el codigo con ruff
lint:
	uv run ruff check .
	uv run ruff format .

# Abre Jupyter Lab en el entorno del proyecto
notebook:
	uv run jupyter lab

# Reescribe docs/model-card.md desde el alias @champion vigente en MLflow
model-card:
	uv run python scripts/model_card.py

# Diagnostica el entorno (uv, paquetes, puertos, hooks) antes de tocar nada mas.
# Sale con codigo != 0 si algo falta.
smoke:
	uv run python scripts/smoke.py
