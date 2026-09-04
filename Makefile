.PHONY: setup data features mlflow train lint notebook

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

# Levanta el servidor de MLflow en el puerto 5001 (queda en primer plano; usa otra terminal)
mlflow:
	uv run python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5001

# Entrena los 3 modelos, los registra y marca el mejor como 'champion'
train:
	uv run python -m trips.models.train

# Revisa y formatea el codigo con ruff
lint:
	uv run ruff check .
	uv run ruff format .

# Abre Jupyter Lab en el entorno del proyecto
notebook:
	uv run jupyter lab
