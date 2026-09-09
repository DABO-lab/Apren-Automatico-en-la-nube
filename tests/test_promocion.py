"""La política de promoción, probada sin tocar MLflow."""

import sys
from pathlib import Path

# scripts/ no es un paquete: se agrega al path para poder importarlo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from promote import decidir


def test_sin_campeon_el_candidato_entra():
    promover, razon = decidir(mae_candidato=4.0, mae_campeon=None)
    assert promover is True
    assert "no hay campeón" in razon


def test_una_mejora_grande_promueve():
    promover, _ = decidir(mae_candidato=3.5, mae_campeon=4.0)  # 12,5%
    assert promover is True


def test_una_mejora_marginal_no_promueve():
    """0,5% de mejora no justifica cambiar el modelo en producción."""
    promover, razon = decidir(mae_candidato=3.98, mae_campeon=4.0)
    assert promover is False
    assert "margen" in razon


def test_un_candidato_peor_no_promueve():
    promover, razon = decidir(mae_candidato=4.5, mae_campeon=4.0)
    assert promover is False
    assert "peor" in razon


def test_el_empate_no_promueve():
    """Empatar no es mejorar: ante la duda, se queda el que ya está."""
    promover, razon = decidir(mae_candidato=4.0, mae_campeon=4.0)
    assert promover is False
    # Y el motivo tiene que decir "empate", no "es peor": suele ser el mismo
    # modelo reentrenado, y el registro de la decisión debe reflejarlo.
    assert "empate" in razon
