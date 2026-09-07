"""Los estadísticos de drift, implementados a mano.

Cuatro medidas, y una idea que las gobierna a todas: **con muchos datos, el
p-valor deja de servir**. Con 108 mil viajes, una diferencia de dos puntos
porcentuales sale con p = 10⁻¹⁴ — "significativa" y a la vez irrelevante.

Por eso cada función devuelve un TAMAÑO DE EFECTO (cuánto se movió) además del
p-valor (qué tan improbable es el azar). La decisión se toma con el primero;
el segundo solo acompaña.
"""

import numpy as np
import pandas as pd
from scipy import stats

# PSI: umbrales de la industria (crédito y riesgo), donde nació la medida.
PSI_MODERADO = 0.10
PSI_ALTO = 0.25

# V de Cramér: 0,1 es el piso de "efecto pequeño" en la convención de Cohen.
CRAMER_MINIMO = 0.10


def psi(referencia: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index: cuánto se movió una distribución numérica.

    Corta la referencia en deciles y compara qué fracción cae en cada tramo.
    Es asimétrico por naturaleza (mide "actual respecto a referencia"), que es
    justo lo que queremos: la referencia es el mundo con el que se entrenó.
    """
    cortes = np.quantile(referencia, np.linspace(0, 1, bins + 1))
    cortes[0], cortes[-1] = -np.inf, np.inf

    p_ref = np.histogram(referencia, cortes)[0] / len(referencia)
    p_act = np.histogram(actual, cortes)[0] / len(actual)
    # Sin este piso, un tramo vacío haría log(0) = -inf
    p_ref = np.clip(p_ref, 1e-6, None)
    p_act = np.clip(p_act, 1e-6, None)

    return float(np.sum((p_act - p_ref) * np.log(p_act / p_ref)))


def jensen_shannon(referencia: np.ndarray, actual: np.ndarray, bins: int = 20) -> float:
    """Divergencia de Jensen-Shannon: simétrica y acotada entre 0 y 1.

    Útil cuando ninguna de las dos distribuciones es "la de referencia".
    """
    lo = min(referencia.min(), actual.min())
    hi = max(referencia.max(), actual.max())
    borde = np.linspace(lo, hi, bins + 1)

    p = np.clip(np.histogram(referencia, borde)[0] / len(referencia), 1e-12, None)
    q = np.clip(np.histogram(actual, borde)[0] / len(actual), 1e-12, None)
    m = (p + q) / 2
    return float((stats.entropy(p, m) + stats.entropy(q, m)) / 2)


def ks(referencia: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    """Kolmogorov-Smirnov. Devuelve (estadístico, p-valor).

    El estadístico es la máxima distancia vertical entre las dos acumuladas:
    ESE es el tamaño de efecto. El p-valor, con n grande, tiende a cero aunque
    la distancia sea insignificante.
    """
    resultado = stats.ks_2samp(referencia, actual)
    return float(resultado.statistic), float(resultado.pvalue)


def cramers_v(referencia: pd.Series, actual: pd.Series) -> tuple[float, float]:
    """Chi-cuadrado para categóricas, reportado como V de Cramér.

    El chi-cuadrado crudo crece con el tamaño de la muestra; la V de Cramér lo
    normaliza a un valor entre 0 y 1 que no depende de cuántas filas haya.
    Devuelve (V, p-valor).
    """
    tabla = pd.crosstab(
        pd.Series(["ref"] * len(referencia) + ["act"] * len(actual)),
        pd.concat([referencia, actual], ignore_index=True),
    )
    chi2, p, _, _ = stats.chi2_contingency(tabla)
    n = len(referencia) + len(actual)
    grados = min(tabla.shape) - 1
    return float(np.sqrt(chi2 / (n * grados))), float(p)


def linea_base_nula(
    valores: np.ndarray, repeticiones: int = 30, semilla: int = 42
) -> dict:
    """Cuánto se mueve el estadístico cuando NO hay drift.

    Parte la referencia en dos mitades aleatorias y mide PSI y KS entre ellas,
    muchas veces. Por construcción no hay drift: lo que sale es el ruido del
    propio estadístico con este tamaño de muestra.

    Sin esta calibración, los umbrales son folclore. Con ella se puede decir
    "el umbral es cien veces el ruido de fondo" y defenderlo con números.
    """
    rng = np.random.default_rng(semilla)
    psis, kss, p_significativos = [], [], 0

    for _ in range(repeticiones):
        idx = rng.permutation(len(valores))
        mitad = len(idx) // 2
        a, b = valores[idx[:mitad]], valores[idx[mitad : 2 * mitad]]
        psis.append(psi(a, b))
        estadistico, p = ks(a, b)
        kss.append(estadistico)
        p_significativos += int(p < 0.05)

    return {
        "psi_p50": float(np.median(psis)),
        "psi_p99": float(np.quantile(psis, 0.99)),
        "ks_p50": float(np.median(kss)),
        "ks_p99": float(np.quantile(kss, 0.99)),
        # Cuántas veces el p-valor gritó "drift" comparando datos idénticos.
        "fraccion_p_menor_005": p_significativos / repeticiones,
    }
