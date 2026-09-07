"""¿Los datos de hoy se parecen a aquellos con los que se entrenó?

    uv run python -m trips.monitoring.check_drift

Compara dos conjuntos y decide si hay drift. Por defecto usa el mismo corte
temporal del entrenamiento: los primeros 25 días de julio como referencia y
los últimos 6 como "lo que está llegando". Cuando exista el archivo de agosto
se le pasa con --actual y la comparación pasa a ser entre meses de verdad.

Tres salidas, cada una para un lector distinto:

- JSON: para CI y para el próximo programa que lo lea.
- HTML (Evidently): para una persona que quiere ver las distribuciones.
- Métricas en MLflow: para tener la serie histórica y ver la tendencia.

Y un código de salida, que es lo que un orquestador entiende:
0 = sin alerta, 1 = drift detectado, 2 = no evaluable.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import mlflow
import pandas as pd

from trips.config import (
    EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
    PROCESSED_DATA_PATH,
    PROJECT_ROOT,
    TARGET_COLUMN,
    TEST_SIZE,
)
from trips.features import add_features
from trips.monitoring.estadistico import (
    CRAMER_MINIMO,
    PSI_MODERADO,
    cramers_v,
    jensen_shannon,
    ks,
    linea_base_nula,
    psi,
)

# Columnas a vigilar: las que el modelo usa, más el objetivo.
COLUMNAS_NUMERICAS = ["distancia_km", TARGET_COLUMN]
COLUMNAS_CATEGORICAS = ["member_casual", "rideable_type", "hora", "dia_semana"]

# Umbral a nivel del conjunto: una columna movida es ruido; un tercio de las
# columnas movidas es otro mes.
FRACCION_COLUMNAS_PARA_ALERTAR = 0.30

# Por debajo de esto no se concluye nada: "no evaluable" y "sin drift" son
# cosas distintas, y confundirlas es cómo se pierde la confianza en el sistema.
MINIMO_FILAS = 1_000

SALIDA = PROJECT_ROOT / "reports"


def _particion_temporal(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """El mismo corte del entrenamiento: pasado como referencia, reciente como actual."""
    df = df.sort_values("started_at")
    corte = int(len(df) * (1 - TEST_SIZE))
    return df.iloc[:corte], df.iloc[corte:]


def evaluar_columna_numerica(referencia: pd.Series, actual: pd.Series) -> dict:
    r, a = referencia.to_numpy(), actual.to_numpy()
    base = linea_base_nula(r)
    estadistico_ks, p_ks = ks(r, a)

    # El umbral efectivo: el de la industria, salvo que el ruido medido sea
    # mayor — en cuyo caso manda el ruido. Nunca se alerta por debajo del
    # movimiento que el propio estadístico produce sin drift.
    umbral = max(PSI_MODERADO, 5 * base["psi_p99"])
    valor_psi = psi(r, a)

    return {
        "tipo": "numerica",
        "psi": round(valor_psi, 5),
        "umbral_psi": round(umbral, 5),
        "psi_ruido_p99": round(base["psi_p99"], 5),
        "ks": round(estadistico_ks, 5),
        "ks_p_valor": float(f"{p_ks:.3e}"),
        "jensen_shannon": round(jensen_shannon(r, a), 5),
        "mediana_referencia": round(float(referencia.median()), 2),
        "mediana_actual": round(float(actual.median()), 2),
        "drift": bool(valor_psi >= umbral),
        # El dato incómodo: qué diría el p-valor por su cuenta.
        "p_valor_diria_drift": bool(p_ks < 0.05),
    }


def evaluar_columna_categorica(referencia: pd.Series, actual: pd.Series) -> dict:
    v, p = cramers_v(referencia.astype(str), actual.astype(str))
    return {
        "tipo": "categorica",
        "cramers_v": round(v, 5),
        "umbral_cramers_v": CRAMER_MINIMO,
        "chi2_p_valor": float(f"{p:.3e}"),
        "drift": bool(v >= CRAMER_MINIMO),
        "p_valor_diria_drift": bool(p < 0.05),
    }


def comparar(referencia: pd.DataFrame, actual: pd.DataFrame) -> dict:
    columnas = {}
    for col in COLUMNAS_NUMERICAS:
        if col in referencia.columns and col in actual.columns:
            columnas[col] = evaluar_columna_numerica(referencia[col], actual[col])
    for col in COLUMNAS_CATEGORICAS:
        if col in referencia.columns and col in actual.columns:
            columnas[col] = evaluar_columna_categorica(referencia[col], actual[col])

    con_drift = [c for c, r in columnas.items() if r["drift"]]
    fraccion = len(con_drift) / len(columnas) if columnas else 0.0
    por_p_valor = [c for c, r in columnas.items() if r["p_valor_diria_drift"]]

    return {
        "fecha": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_referencia": len(referencia),
        "n_actual": len(actual),
        "columnas": columnas,
        "columnas_con_drift": con_drift,
        "fraccion_columnas_con_drift": round(fraccion, 3),
        "umbral_fraccion": FRACCION_COLUMNAS_PARA_ALERTAR,
        "alerta": bool(fraccion >= FRACCION_COLUMNAS_PARA_ALERTAR),
        "columnas_que_alertaria_el_p_valor": por_p_valor,
    }


def reporte_evidently(
    referencia: pd.DataFrame, actual: pd.DataFrame, destino: Path
) -> bool:
    """El HTML para mirar con ojos. Si falla, no tumba el chequeo."""
    try:
        from evidently import DataDefinition, Dataset, Report
        from evidently.presets import DataDriftPreset

        columnas = COLUMNAS_NUMERICAS + COLUMNAS_CATEGORICAS
        definicion = DataDefinition(
            numerical_columns=list(COLUMNAS_NUMERICAS),
            categorical_columns=list(COLUMNAS_CATEGORICAS),
        )
        snapshot = Report([DataDriftPreset()]).run(
            Dataset.from_pandas(actual[columnas].copy(), data_definition=definicion),
            Dataset.from_pandas(
                referencia[columnas].copy(), data_definition=definicion
            ),
        )
        snapshot.save_html(str(destino))
        return True
    except Exception as error:  # noqa: BLE001
        print(f"Aviso - no se pudo generar el HTML de Evidently: {error}")
        return False


def registrar_en_mlflow(resultado: dict, html: Path | None) -> None:
    """La serie histórica: una corrida por chequeo, para ver la tendencia."""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)
        with mlflow.start_run(run_name="drift"):
            mlflow.set_tag("tipo", "monitoreo")
            mlflow.log_metric(
                "fraccion_columnas_con_drift", resultado["fraccion_columnas_con_drift"]
            )
            mlflow.log_metric("n_actual", resultado["n_actual"])
            for col, datos in resultado["columnas"].items():
                if datos["tipo"] == "numerica":
                    mlflow.log_metric(f"psi_{col}", datos["psi"])
                else:
                    mlflow.log_metric(f"cramers_v_{col}", datos["cramers_v"])
            if html and html.exists():
                mlflow.log_artifact(str(html))
    except Exception as error:  # noqa: BLE001
        print(f"Aviso - no se pudo registrar en MLflow: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chequeo de drift de datos")
    parser.add_argument(
        "--referencia",
        type=Path,
        default=None,
        help="Parquet de referencia. Por defecto, los primeros 25 días de julio.",
    )
    parser.add_argument(
        "--actual",
        type=Path,
        default=None,
        help="Parquet a evaluar. Por defecto, los últimos 6 días de julio.",
    )
    parser.add_argument("--sin-mlflow", action="store_true")
    args = parser.parse_args()

    if args.referencia and args.actual:
        referencia = add_features(pd.read_parquet(args.referencia))
        actual = add_features(pd.read_parquet(args.actual))
    else:
        if not PROCESSED_DATA_PATH.exists():
            print(f"No encuentro {PROCESSED_DATA_PATH}. Corre antes 'make data'.")
            return 2
        referencia, actual = _particion_temporal(
            add_features(pd.read_parquet(PROCESSED_DATA_PATH))
        )

    if len(referencia) < MINIMO_FILAS or len(actual) < MINIMO_FILAS:
        print(
            f"No evaluable: {len(referencia)} y {len(actual)} filas "
            f"(se necesitan al menos {MINIMO_FILAS} en cada lado)."
        )
        return 2

    resultado = comparar(referencia, actual)

    SALIDA.mkdir(parents=True, exist_ok=True)
    json_path = SALIDA / "drift.json"
    json_path.write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    html_path = SALIDA / "drift.html"
    hay_html = reporte_evidently(referencia, actual, html_path)

    if not args.sin_mlflow:
        registrar_en_mlflow(resultado, html_path if hay_html else None)

    print(
        f"Referencia: {resultado['n_referencia']:,} viajes | Actual: {resultado['n_actual']:,}"
    )
    print("-" * 78)
    for col, d in resultado["columnas"].items():
        if d["tipo"] == "numerica":
            medida = f"PSI {d['psi']:.4f} (umbral {d['umbral_psi']:.4f}, ruido {d['psi_ruido_p99']:.4f})"
        else:
            medida = (
                f"V de Cramér {d['cramers_v']:.4f} (umbral {d['umbral_cramers_v']})"
            )
        print(f"{col:<16} {'DRIFT' if d['drift'] else 'ok   '}  {medida}")
    print("-" * 78)
    print(
        f"Columnas con drift: {len(resultado['columnas_con_drift'])}/{len(resultado['columnas'])} "
        f"({resultado['fraccion_columnas_con_drift']:.0%}; se alerta desde "
        f"{FRACCION_COLUMNAS_PARA_ALERTAR:.0%})"
    )
    if resultado["columnas_que_alertaria_el_p_valor"]:
        print(
            f"Con p < 0,05 se habrían alertado {len(resultado['columnas_que_alertaria_el_p_valor'])} "
            f"columnas: {', '.join(resultado['columnas_que_alertaria_el_p_valor'])}"
        )
    print(f"Reporte: {json_path}" + (f" y {html_path}" if hay_html else ""))

    if resultado["alerta"]:
        print("\nALERTA: los datos actuales no se parecen a los de entrenamiento.")
        return 1
    print("\nSin alerta: el modelo sigue viendo el mundo con el que aprendió.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
