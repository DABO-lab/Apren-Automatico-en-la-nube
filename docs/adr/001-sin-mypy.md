# ADR 001 — No se usa mypy (ni otro *type checker* estático)

**Estado:** aceptado
**Fecha:** septiembre de 2026
**Autores:** equipo del proyecto, con apoyo de un asistente de Claude

## Contexto

El curso deja abierta la elección de herramientas de calidad de código más
allá de un `linter`/`formatter` (`ruff`, ya en uso — ver ADR 000). Python no
obliga a anotar tipos ni a verificarlos: las anotaciones de este proyecto
(`def add_features(df: pd.DataFrame) -> pd.DataFrame`, los `dataclass` de
`trips/api/modelo.py`, los modelos de Pydantic en `trips/api/schemas.py`) son
en su mayoría documentación para quien lee el código, no una garantía
verificada en CI.

Ese hueco no es teórico: el bug real que motivó esta ADR fue
`ModeloServido.version` declarado como `str`, mientras que
`MlflowClient().get_model_version_by_alias(...).version` empezó a devolver
`int` en MLflow 3.15. La anotación de tipo decía una cosa, el valor real
decía otra, y nadie lo vio hasta que `/predict` respondía `500` con un
modelo real cargado (ver el commit `fix(api): normalizar version del modelo
a str...`). Un `type checker` que revisara los límites entre `trips.api.modelo`
y `trips.api.schemas` lo habría marcado en rojo antes de llegar a producción.

## Decisión

**No se agrega `mypy` (ni `pyright`) al proyecto.**

En su lugar, el gap que un *type checker* habría atrapado se cierra con dos
pruebas de comportamiento (`tests/api/test_modelo.py`,
`tests/api/test_main.py`) que golpean el código real con `TestClient` y con
mocks de MLflow, en vez de con una verificación estática de tipos.

## Alternativas consideradas

- **`mypy` en modo estricto sobre todo `src/`.** Es lo que pide el nivel 5 de
  la dimensión de ingeniería en la rúbrica del instructor. Se descartó por
  tiempo: el proyecto mezcla `pandas.DataFrame` (con tipado dinámico de
  columnas, mal soportado por `mypy` sin *stubs* adicionales), `pandera`
  (que tiene su propio sistema de tipos para `DataFrameModel`) y los
  objetos de MLflow (parcialmente tipados, como demuestra el propio bug de
  esta ADR). Ponerlo en verde de forma honesta —sin `# type: ignore` a
  granel, que sería peor que no tenerlo— tomaba más tiempo del que quedaba
  para las demás dimensiones, y el `checklist` de MVP del curso
  (`proyecto/mvp-minimo-aprobable.md`) es explícito en que ninguna dimensión
  vale más del 15 % y que cubrir las siete a nivel razonable gana sobre
  perfeccionar una.
- **`mypy` solo sobre `trips/api/`.** Alcance reducido, evaluado como
  segunda opción. Se descartó por la misma razón de tiempo, aunque es la
  opción más barata si el equipo decide retomarlo: es exactamente el módulo
  donde ya apareció un bug de tipos real.

## Consecuencias

- Los contratos entre módulos (como `ModeloServido.version: str`) dependen
  de pruebas de comportamiento para detectarse, no de una verificación
  estática. Una prueba nueva cuesta más que una anotación revisada
  automáticamente, pero también documenta el caso concreto que falló —ver
  el comentario en `tests/api/test_modelo.py`— de una forma que un error de
  `mypy` no deja por escrito.
- Si el equipo retoma este proyecto después del curso, `trips/api/` es el
  candidato natural para instrumentar primero: ya tiene el incidente
  concreto que justifica el esfuerzo.
- Esta ADR es en sí misma la evidencia que pide la rúbrica cuando dice que
  "justificar por escrito por qué no usan" una herramienta adicional cuenta
  en la dimensión de ingeniería, aunque la herramienta en sí no esté.
