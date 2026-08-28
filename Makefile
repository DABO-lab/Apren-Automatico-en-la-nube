.PHONY: setup data lint notebook

# Instala las dependencias exactas del uv.lock y activa el hook de pre-commit
setup:
	uv sync
	uv run pre-commit install

# Lee el CSV crudo, muestra su ficha tecnica y lo limpia: raw -> processed
data:
	uv run python -m trips.data.load
	uv run python -m trips.data.clean

# Revisa y formatea el codigo con ruff
lint:
	uv run ruff check .
	uv run ruff format .

# Abre Jupyter Lab en el entorno del proyecto
notebook:
	uv run jupyter lab
