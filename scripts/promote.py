"""La compuerta de promoción: ¿el candidato entra a producción?

    uv run python scripts/promote.py            # decide y promueve si procede
    uv run python scripts/promote.py --dry-run  # solo dice qué haría

Este script existe separado del entrenamiento a propósito. Un pipeline que
entrena y se autopromueve no tiene control de calidad: el día que los datos
lleguen mal, el modelo malo entra a producción solo y nadie se entera hasta que
alguien reclama.

La regla: el candidato reemplaza al campeón solo si lo mejora por un margen
claro. Empatar no basta — cambiar el modelo en producción tiene un costo (hay
que revalidar, puede haber sorpresas) y un empate no lo justifica.
"""

import argparse
import math
import sys

import mlflow
from mlflow import MlflowClient

from trips.config import (
    ALIAS_CAMPEON,
    ALIAS_CANDIDATO,
    MARGEN_DE_MEJORA,
    METRICA_DE_PROMOCION,
    MLFLOW_TRACKING_URI,
    REGISTERED_MODEL_NAME,
)


def decidir(
    mae_candidato: float, mae_campeon: float | None, margen: float = MARGEN_DE_MEJORA
) -> tuple[bool, str]:
    """Compara y explica. Devuelve (promover, razón).

    Función pura y sin efectos: se puede probar sin MLflow, y es la única parte
    del script donde vive la política.
    """
    if mae_campeon is None:
        return True, "no hay campeón vigente: el candidato ocupa el puesto"

    mejora = (mae_campeon - mae_candidato) / mae_campeon
    if mejora >= margen:
        return True, (
            f"mejora del {mejora:.1%} en {METRICA_DE_PROMOCION} "
            f"({mae_campeon:.3f} -> {mae_candidato:.3f}), por encima del "
            f"margen {margen:.0%}"
        )
    if mejora > 0:
        return False, (
            f"mejora del {mejora:.1%}, por debajo del margen exigido {margen:.0%}: "
            "no compensa cambiar el modelo en producción"
        )
    # El empate merece su propio mensaje: suele ser el mismo modelo reentrenado
    # sobre los mismos datos, no un candidato malo. Decir "es peor" ahí sería
    # incorrecto y confundiría a quien lee el registro de la decisión.
    if math.isclose(mejora, 0.0, abs_tol=1e-9):
        return False, (
            f"empate exacto ({mae_candidato:.3f}): probablemente el mismo modelo "
            "reentrenado. Se queda el campeón vigente"
        )
    return False, (
        f"el candidato es peor ({mae_candidato:.3f} contra {mae_campeon:.3f} "
        "del campeón)"
    )


def _metrica_de(client: MlflowClient, alias: str) -> tuple[str | None, float | None]:
    """Versión y métrica del modelo que tenga ese alias, si existe."""
    try:
        version = client.get_model_version_by_alias(REGISTERED_MODEL_NAME, alias)
    except Exception:  # noqa: BLE001 — el alias todavía no existe
        return None, None
    run = client.get_run(version.run_id)
    return version.version, run.data.metrics.get(METRICA_DE_PROMOCION)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compuerta de promoción del modelo")
    parser.add_argument("--dry-run", action="store_true", help="decide sin mover nada")
    args = parser.parse_args()

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()

    version_candidato, mae_candidato = _metrica_de(client, ALIAS_CANDIDATO)
    if version_candidato is None:
        print(
            f"No hay ningún modelo con el alias '{ALIAS_CANDIDATO}'. "
            "Corre antes el flujo de entrenamiento."
        )
        return 2
    if mae_candidato is None:
        print(
            f"La versión {version_candidato} no tiene la métrica "
            f"'{METRICA_DE_PROMOCION}'."
        )
        return 2

    version_campeon, mae_campeon = _metrica_de(client, ALIAS_CAMPEON)

    print(
        f"Candidato: versión {version_candidato} | "
        f"{METRICA_DE_PROMOCION} = {mae_candidato:.3f}"
    )
    if version_campeon:
        print(
            f"Campeón:   versión {version_campeon} | "
            f"{METRICA_DE_PROMOCION} = {mae_campeon:.3f}"
        )
    else:
        print("Campeón:   ninguno todavía")

    promover, razon = decidir(mae_candidato, mae_campeon)
    print(f"\nDecisión: {'PROMOVER' if promover else 'NO promover'} — {razon}")

    if not promover:
        return 1
    if args.dry_run:
        print("(--dry-run: no se movió el alias)")
        return 0

    client.set_registered_model_alias(
        REGISTERED_MODEL_NAME, ALIAS_CAMPEON, version_candidato
    )
    print(f"\n'{ALIAS_CAMPEON}' ahora apunta a la versión {version_candidato}.")
    print("La API lo tomará al reiniciarse: no hay que reconstruir nada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
