"""El detector de drift: detecta cuando hay y calla cuando no.

Las dos mitades importan igual. Un detector que alerta siempre es tan inútil
como uno que nunca alerta, y más caro: enseña al equipo a ignorar alertas.
"""

import numpy as np
import pandas as pd
import pytest

from trips.monitoring.check_drift import comparar, evaluar_columna_numerica
from trips.monitoring.estadistico import (
    cramers_v,
    jensen_shannon,
    ks,
    linea_base_nula,
    psi,
)


@pytest.fixture
def normal() -> np.ndarray:
    return np.random.default_rng(1).normal(10, 2, 5_000)


def test_psi_es_casi_cero_entre_dos_muestras_de_lo_mismo(normal):
    otra = np.random.default_rng(2).normal(10, 2, 5_000)
    assert psi(normal, otra) < 0.05


def test_psi_crece_cuando_la_distribucion_se_desplaza(normal):
    assert psi(normal, normal + 5) > 0.25


def test_jensen_shannon_esta_acotada(normal):
    assert 0 <= jensen_shannon(normal, normal + 3) <= 1


def test_ks_devuelve_estadistico_y_p_valor(normal):
    estadistico, p = ks(normal, normal + 5)
    assert estadistico > 0.5 and p < 0.01


def test_cramers_v_es_bajo_con_las_mismas_proporciones():
    a = pd.Series(["x"] * 700 + ["y"] * 300)
    b = pd.Series(["x"] * 690 + ["y"] * 310)
    v, _ = cramers_v(a, b)
    assert v < 0.1


def test_cramers_v_sube_cuando_cambian_las_proporciones():
    a = pd.Series(["x"] * 700 + ["y"] * 300)
    b = pd.Series(["x"] * 300 + ["y"] * 700)
    v, _ = cramers_v(a, b)
    assert v > 0.3


def test_la_linea_base_nula_mide_ruido_pequeno(normal):
    """Sin drift real, el PSI debe quedarse en el orden de la milésima."""
    base = linea_base_nula(normal, repeticiones=10)
    assert base["psi_p99"] < 0.05
    assert base["ks_p99"] < 0.2


def test_el_p_valor_alerta_aunque_el_efecto_sea_minusculo():
    """La razón de ser de todo este módulo, como prueba ejecutable.

    Dos muestras casi idénticas pero enormes: el p-valor dice que hay
    diferencia, el tamaño de efecto dice que no importa. Con 108 mil viajes
    reales nos pasa exactamente esto.
    """
    rng = np.random.default_rng(0)
    referencia = pd.Series(rng.normal(10, 2, 100_000))
    actual = pd.Series(rng.normal(10.05, 2, 100_000))  # 0,05 de diferencia

    resultado = evaluar_columna_numerica(referencia, actual)
    assert resultado["p_valor_diria_drift"] is True
    assert resultado["drift"] is False


def _df(n, semilla=0, factor=1.0):
    rng = np.random.default_rng(semilla)
    return pd.DataFrame(
        {
            "duracion_min": rng.lognormal(1.85, 0.75, n) * factor,
            "distancia_km": rng.lognormal(0, 0.5, n),
            "member_casual": rng.choice(["member", "casual"], n, p=[0.72, 0.28]),
            "rideable_type": rng.choice(["classic_bike", "electric_bike"], n),
            "hora": rng.integers(0, 24, n),
            "dia_semana": rng.integers(0, 7, n),
        }
    )


def test_sin_drift_no_hay_alerta():
    assert comparar(_df(5_000, 1), _df(5_000, 2))["alerta"] is False


def test_con_drift_generalizado_hay_alerta():
    """Los viajes se triplican y cambian los usuarios: eso sí es otro mes."""
    actual = _df(5_000, 2, factor=3.0)
    actual["member_casual"] = "casual"
    actual["rideable_type"] = "classic_bike"

    resultado = comparar(_df(5_000, 1), actual)
    assert resultado["alerta"] is True
    assert "duracion_min" in resultado["columnas_con_drift"]
