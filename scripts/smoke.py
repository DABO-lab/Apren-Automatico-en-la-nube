"""Smoke test del entorno del proyecto.

Corre esto como PRIMER paso, antes de cualquier otra cosa:

    uv run python scripts/smoke.py

Por qué existe: la única verificación de entorno que había era `uv --version`,
que no prueba nada de lo que realmente falla en la práctica (un puerto
ocupado, el hook de pre-commit sin instalar, una dependencia declarada en el
código pero no en pyproject.toml). Este script diagnostica eso en segundos y
sale con código != 0 si algo falta, para poder usarlo también como paso de
reproducibilidad verificable ('git clone' -> 'make setup' -> 'make smoke').
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata as md
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[93m"
GRIS = "\033[90m"
FIN = "\033[0m"

if os.name == "nt" and not os.getenv("WT_SESSION"):
    VERDE = ROJO = AMARILLO = GRIS = FIN = ""

# (modulo importable, nombre de distribucion) — las que declara pyproject.toml.
PAQUETES: list[tuple[str, str]] = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("sklearn", "scikit-learn"),
    ("pyarrow", "pyarrow"),
    ("mlflow", "mlflow"),
    ("pandera", "pandera"),
    ("evidently", "evidently"),
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("prefect", "prefect"),
    ("matplotlib", "matplotlib"),
    ("seaborn", "seaborn"),
]

PUERTOS = [
    (5001, "MLflow tracking server"),
    (4200, "Prefect server / UI"),
    (8000, "API de inferencia (FastAPI)"),
]

resultados: list[tuple[str, str, str]] = []  # (estado, titulo, detalle)


def ok(titulo: str, detalle: str = "") -> None:
    resultados.append(("OK", titulo, detalle))


def falla(titulo: str, detalle: str) -> None:
    resultados.append(("FAIL", titulo, detalle))


def aviso(titulo: str, detalle: str) -> None:
    resultados.append(("WARN", titulo, detalle))


# =============================================================================
def verificar_python() -> None:
    v = sys.version_info
    detalle = (
        f"{v.major}.{v.minor}.{v.micro} ({platform.system()} {platform.machine()})"
    )
    if (v.major, v.minor) >= (3, 11):
        ok("Python >= 3.11", detalle)
    else:
        falla("Python >= 3.11", f"tienes {detalle}. Corre: uv python install 3.11")


def verificar_herramientas() -> None:
    """Comprueba lo que 'make setup' necesita para poder correr.

    Huevo y gallina: 'make setup' instala el entorno, pero necesita que 'uv'
    ya esté ahí. Este script corre con cualquier Python 3.11+, sin ninguna
    dependencia del proyecto instalada, para diagnosticar la máquina ANTES
    de que exista un entorno que diagnosticar.
    """
    if shutil.which("uv") is None:
        falla(
            "uv instalado",
            "es el gestor de entorno del proyecto y 'make setup' no arranca sin el.\n"
            "         macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
            "         Windows:     winget install astral-sh.uv\n"
            "         Cierra y reabre la terminal despues de instalarlo.",
        )
    else:
        proc = subprocess.run(
            ["uv", "--version"], capture_output=True, text=True, timeout=30, check=False
        )
        ok("uv instalado", proc.stdout.strip() or "responde")

    if shutil.which("make") is None:
        if os.name == "nt":
            aviso(
                "make disponible",
                "no viene en Windows. NO es obligatorio: cada target del Makefile "
                "es un 'uv run ...'.\n         Abre el Makefile y copia el comando, "
                "o instalalo con: winget install GnuWin32.Make",
            )
        else:
            aviso("make disponible", "en macOS se instala con: xcode-select --install")
    else:
        ok("make disponible", "los atajos del Makefile funcionan")

    if shutil.which("docker") is None:
        aviso("Docker disponible", "necesario para 'make docker-build'/'docker-run'")
    else:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            ok("Docker disponible", f"server {proc.stdout.strip()}")
        else:
            aviso("Docker disponible", "instalado pero el daemon no responde")


def verificar_venv() -> None:
    en_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if en_venv:
        ok("Entorno virtual activo", sys.prefix)
    else:
        aviso(
            "Entorno virtual activo",
            "estas usando el Python del sistema. Usa 'uv run ...' o activa .venv",
        )


def verificar_paquetes() -> None:
    faltantes: list[str] = []
    for modulo, dist in PAQUETES:
        try:
            importlib.import_module(modulo)
            try:
                version = md.version(dist)
            except md.PackageNotFoundError:
                version = "?"
            ok(f"import {modulo}", version)
        except ImportError:
            faltantes.append(dist)
            falla(f"import {modulo}", "no instalado")
    if faltantes:
        falla(
            "Dependencias completas",
            "corre `uv sync`. Faltan: " + ", ".join(faltantes),
        )


def verificar_paquete_proyecto() -> None:
    """Prueba el paquete `trips` con datos sinteticos: no requiere red ni el CSV real."""
    sys.path.insert(0, str(RAIZ / "src"))
    try:
        from trips.data.contract import ViajesCrudos
        from trips.data.synthetic import generar_viajes_sinteticos
        from trips.features import add_features
    except ImportError as exc:
        falla("import trips (paquete del proyecto)", f"{exc} — corre `uv sync`")
        return

    ok("import trips (paquete del proyecto)", "config, contract, features, synthetic")

    df = generar_viajes_sinteticos(n=1500, semilla=42)
    try:
        ViajesCrudos.validate(df, lazy=True)
        ok("Contrato ViajesCrudos", "valida un lote sintetico correcto")
    except Exception as exc:  # noqa: BLE001
        falla("Contrato ViajesCrudos", f"{type(exc).__name__}: {exc}")

    try:
        derivado = add_features(df)
        assert "distancia_km" in derivado.columns
        ok("Derivacion de variables", "crea distancia_km, hora y dia_semana")
    except Exception as exc:  # noqa: BLE001
        falla("Derivacion de variables", f"{type(exc).__name__}: {exc}")

    # El contrato debe RECHAZAR un dato roto. Uno que nunca falla no protege nada.
    roto = df.copy()
    roto.loc[:5, "start_lat"] = 6.24  # Medellin: fuera de la caja de Jersey City
    try:
        ViajesCrudos.validate(roto, lazy=True)
        falla(
            "Contrato rechaza datos invalidos",
            "acepto coordenadas fuera de rango — el contrato no protege nada",
        )
    except Exception:  # noqa: BLE001
        ok("Contrato rechaza datos invalidos", "detecta coordenadas fuera de rango")


def verificar_hooks() -> None:
    """Verifica que el hook de pre-commit quedo REALMENTE instalado.

    'make setup' corre 'pre-commit install', pero si alguien clona el repo y
    solo corre 'uv sync' (sin 'make setup' completo), el hook nunca se activa
    y nadie se entera hasta que un notebook con outputs o un secreto llega al
    historial.
    """
    hooks_path = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    ).stdout.strip()

    if hooks_path:
        falla(
            "core.hooksPath sin configurar",
            f"apunta a '{hooks_path}'. pre-commit se niega a instalarse con eso "
            "puesto. Corre: git config --unset-all core.hooksPath && make setup",
        )
    else:
        ok("core.hooksPath sin configurar", "pre-commit es el unico sistema de hooks")

    if os.getenv("CI"):
        aviso(
            "Hook de pre-commit instalado",
            "omitido (CI: el hook vive en la maquina de cada quien, no en el runner)",
        )
        return

    if (RAIZ / ".git" / "hooks" / "pre-commit").exists():
        ok("Hook de pre-commit instalado", "ruff, gitleaks y nbstripout van a correr")
    else:
        falla("Hook de pre-commit instalado", "falta. Corre: make setup")


def verificar_puertos() -> None:
    for puerto, servicio in PUERTOS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.4)
            ocupado = sock.connect_ex(("127.0.0.1", puerto)) == 0
        if ocupado:
            extra = " (en macOS suele ser AirPlay Receiver)" if puerto == 5000 else ""
            aviso(
                f"Puerto {puerto} libre",
                f"ocupado — {servicio} no podra arrancar ahi{extra}",
            )
        else:
            ok(f"Puerto {puerto} libre", servicio)


def verificar_estructura() -> None:
    esperados = [
        "src/trips/config.py",
        "src/trips/data/contract.py",
        "Makefile",
        "pyproject.toml",
        ".pre-commit-config.yaml",
        "docs/dataset-card.md",
        "docs/model-card.md",
    ]
    faltan = [p for p in esperados if not (RAIZ / p).exists()]
    if faltan:
        falla("Estructura del repo", "faltan: " + ", ".join(faltan))
    else:
        ok("Estructura del repo", f"{len(esperados)} rutas clave presentes")


def verificar_mlflow_arranca(rapido: bool) -> None:
    if rapido:
        aviso("CLI de MLflow", "omitido (--rapido)")
        return
    try:
        import mlflow  # noqa: F401
    except ImportError:
        falla("CLI de MLflow", "mlflow no esta instalado")
        return
    proc = subprocess.run(
        [sys.executable, "-m", "mlflow", "--version"],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if proc.returncode == 0:
        ok("CLI de MLflow", proc.stdout.strip() or "responde")
    else:
        falla("CLI de MLflow", proc.stderr.strip()[:200])


def verificar_prefect(rapido: bool) -> None:
    if rapido:
        aviso("Prefect importable", "omitido (--rapido)")
        return
    try:
        import prefect  # noqa: F401
    except ImportError:
        falla("Prefect importable", "prefect no esta instalado")
        return
    ok("Prefect importable", md.version("prefect"))


# =============================================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test del entorno del proyecto")
    parser.add_argument(
        "--rapido",
        action="store_true",
        help="omite las verificaciones que lanzan subprocesos lentos",
    )
    args = parser.parse_args()

    print(f"\n{GRIS}{'=' * 72}{FIN}")
    print("  SMOKE TEST — Prediccion de duracion de viajes Citi Bike")
    print(f"{GRIS}{'=' * 72}{FIN}\n")

    verificar_python()
    verificar_herramientas()
    verificar_venv()
    verificar_paquetes()
    verificar_paquete_proyecto()
    verificar_estructura()
    verificar_hooks()
    verificar_puertos()
    verificar_mlflow_arranca(args.rapido)
    verificar_prefect(args.rapido)

    ancho = max(len(t) for _, t, _ in resultados) + 2
    for estado, titulo, detalle in resultados:
        if estado == "OK":
            marca = f"{VERDE}  OK  {FIN}"
        elif estado == "WARN":
            marca = f"{AMARILLO} WARN {FIN}"
        else:
            marca = f"{ROJO} FAIL {FIN}"
        print(f"[{marca}] {titulo:<{ancho}} {GRIS}{detalle}{FIN}")

    fallos = sum(1 for e, _, _ in resultados if e == "FAIL")
    avisos = sum(1 for e, _, _ in resultados if e == "WARN")

    print(f"\n{GRIS}{'-' * 72}{FIN}")
    if fallos:
        print(f"{ROJO}{fallos} verificacion(es) FALLARON{FIN}, {avisos} aviso(s).")
        print("Arregla los FAIL antes de seguir. Cada linea dice que hacer.")
        print(f"{GRIS}{'-' * 72}{FIN}\n")
        return 1
    print(f"{VERDE}Entorno listo.{FIN} {avisos} aviso(s) — revisalos, no bloquean.")
    print(f"{GRIS}{'-' * 72}{FIN}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
