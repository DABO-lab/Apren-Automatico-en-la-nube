"""Genera un CSV crudo sintético para que el CI tenga algo que procesar.

El CSV real de julio (`data/raw/JC-202607-citibike-tripdata.csv`) no está en
el repositorio: pesa demasiado y los datos crudos no se versionan (sección
1.5 del informe de estado). Sin él, el job de GitHub Actions que corre el
pipeline completo en cada push a `main` no tendría nada que leer.

Este script NO reemplaza el dataset real ni se usa para entrenar el modelo
que sirve la API -las métricas que salgan de datos sintéticos no significan
nada sobre viajes reales-. Solo existe para que el CI pueda ejercitar el
pipeline de punta a punta (limpieza, variables, entrenamiento, drift,
compuerta de promoción) automáticamente, con datos que tienen la forma
correcta y la misma semilla que los fixtures de `tests/conftest.py`
(`src/trips/data/synthetic.py` es la fuente compartida).

Uso:
    uv run python scripts/generar_datos_ci.py \
        --salida data/raw/JC-202607-citibike-tripdata.csv --filas 5000
"""

import argparse
from pathlib import Path

from trips.data.synthetic import generar_viajes_sinteticos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--salida", type=Path, required=True, help="Ruta del CSV a escribir"
    )
    parser.add_argument(
        "--filas", type=int, default=5_000, help="Número de viajes sintéticos"
    )
    parser.add_argument(
        "--semilla", type=int, default=42, help="Semilla del generador aleatorio"
    )
    args = parser.parse_args()

    df = generar_viajes_sinteticos(n=args.filas, semilla=args.semilla)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.salida, index=False)
    print(f"Escritos {len(df):,} viajes sintéticos en {args.salida}")


if __name__ == "__main__":
    main()
