# ADR 000 — Elección del stack

**Estado:** aceptado
**Fecha:** julio de 2026
**Autores:** Bueno Osorno Dubian Andrés, Ceballos Bedoya Catherine, Rivera
Guzmán Yesenia, Salazar Seguro María Jimena

## Contexto

El proyecto tiene que cubrir las siete dimensiones de la rúbrica del curso
(reproducibilidad, datos, tracking/registry, pipeline, deployment, monitoreo,
ingeniería) con un problema de regresión de tamaño moderado (109 mil filas).
Cuatro personas necesitan que el entorno sea idéntico en máquinas distintas
(todas con Windows), y el curso especifica algunas herramientas (MLflow,
`uv`) mientras deja otras abiertas (orquestador, framework de API, validación
de datos).

## Decisión

| Pieza | Elegido | Para qué |
|---|---|---|
| Gestor de entorno y paquetes | `uv` | Fijado por el curso. Resuelve e instala Python 3.11 + dependencias exactas desde `uv.lock`, sin depender de que cada quien tenga la misma versión de Python preinstalada |
| Validación de datos | `pandera` | Contratos declarativos (`DataFrameModel`) en vez de `if`/`assert` sueltos; se leen como documentación y producen un solo reporte con **todos** los incumplimientos (`lazy=True`), no el primero que truena |
| Tracking y registry | MLflow | Fijado por el curso. Aliases (`@candidate`/`@champion`) en vez de `stages` (deprecados desde MLflow 2.9) |
| Orquestación | Prefect | `Tasks` con caché por huella de archivo + código (`INPUTS + TASK_SOURCE`), reintentos configurables por tarea, y un tablero que muestra qué salió de caché sin instrumentación adicional |
| Modelos | scikit-learn (`Ridge`, `HistGradientBoostingRegressor`, `DummyRegressor` como baseline) | El problema (109 mil filas, variables tabulares) no necesita boosting distribuido ni deep learning; scikit-learn permite meter el preprocesamiento **dentro** del mismo `Pipeline` que se registra en MLflow, así el artefacto es autocontenido |
| API | FastAPI | Genera la documentación interactiva (`/docs`) sola a partir de los `schemas` de Pydantic; el patrón `lifespan` (no `@app.on_event`, deprecado desde FastAPI 0.93) para cargar el modelo una sola vez al arrancar |
| Monitoreo de drift | Evidently + estadísticos propios (PSI, KS, V de Cramér, Jensen-Shannon) | Evidently da el HTML para inspección visual; el cálculo de PSI/V de Cramér es propio porque el umbral de alerta necesitaba calibrarse contra el ruido de fondo del propio estadístico (ver `docs/guia-del-proyecto.md`, sección 9), algo que una librería genérica no hace por defecto |
| Contenedor | Docker, `build` multi-etapa | Separar la etapa que instala dependencias (con `uv`, herramientas de compilación) de la etapa que ejecuta (solo el `.venv` ya construido y el código) reduce el tamaño de la imagen final y la superficie de ataque |
| CI | GitHub Actions | Ya integrado con el repositorio; sin infraestructura propia que mantener |
| Calidad de código | `ruff` (lint + format) vía `pre-commit` | Un solo binario para lint y formato, más rápido que mantener `flake8` + `black` + `isort` por separado |

## Alternativas consideradas y descartadas

- **XGBoost/LightGBM en vez de `HistGradientBoostingRegressor`.** Se descartó
  por costo de dependencia adicional sin beneficio claro: la rúbrica no
  premia la calidad del modelo (solo que el proceso alrededor de él sea
  sólido), y `HistGradientBoostingRegressor` ya viene con scikit-learn, que
  el proyecto necesita de todas formas para el preprocesamiento.
- **Airflow en vez de Prefect.** Airflow exige un `scheduler` y una base de
  datos propios incluso para un flujo que corre bajo demanda; Prefect corre
  local con un solo comando (`prefect server start`) y el mismo modelo de
  `tasks` alcanza para las cinco etapas del pipeline.
- **Great Expectations en vez de Pandera.** Great Expectations apunta a
  suites de validación más grandes con su propio formato de configuración;
  para contratos que viven junto al código Python del proyecto, `pandera`
  (contratos como clases, con `pa.Field` y tipos) encaja mejor con el
  principio de "una sola fuente de verdad" que ya sigue `config.py`.
- **Un `feature store` (Feast).** Descartado explícitamente: con un solo
  modelo, un solo pipeline batch y sin necesidad de features en tiempo real,
  un `feature store` es infraestructura que no resuelve ningún problema que
  el equipo tenga hoy. `src/trips/features.py` alcanza.
- **Kubernetes para el despliegue.** Un solo contenedor con `docker compose`
  cumple el requisito de la rúbrica (un despliegue local bien hecho vale
  igual que uno en la nube); Kubernetes agregaría complejidad operativa sin
  un caso de uso que la justifique (no hay necesidad de escalar horizontalmente
  ni de múltiples servicios).

## Consecuencias

- El equipo depende de que las cuatro máquinas tengan `uv`, `docker` y `git`
  instalados vía `winget` (documentado en `docs/como-empezar.md`); no hay una
  imagen de desarrollo (`devcontainer`) que evite esa instalación local.
- Usar `pandera` en vez de escribir los `if`/`assert` a mano cuesta una curva
  de aprendizaje inicial (la sintaxis de `DataFrameModel` y los
  `@pa.dataframe_check`), pero paga esa curva en la sección 6.8 del informe
  de estado: los contratos atrapan errores en tres niveles distintos con
  poco código nuevo.
- Elegir Prefect en vez de encadenar comandos de `Makefile` significa que el
  equipo tiene que tener el servidor de Prefect corriendo para ver el
  tablero (sección 5 del informe de estado, Terminal 2) — una pieza más para
  explicar en la sustentación, a cambio de caché medible y reintentos
  configurables.
