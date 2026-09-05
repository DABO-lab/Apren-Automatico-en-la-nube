.PHONY: setup data features mlflow train api docker-build docker-run test lint notebook

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

# Entrena los 3 modelos, los registra y marca el mejor como 'champion'
train:
	uv run python -m trips.models.train

# Levanta la API que sirve el modelo champion (MLflow debe estar arriba)
api:
	uv run uvicorn trips.api.main:app --host 127.0.0.1 --port 8000 --reload

# Construye la imagen de la API
docker-build:
	docker build -t trips-api .

# Corre la API en un contenedor (MLflow debe estar arriba en la maquina anfitriona)
docker-run:
	docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway trips-api

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
