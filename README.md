<div style="font-family: Arial;">
<img src="https://udemedellin.edu.co/wp-content/uploads/2022/10/logo_udemedellin2.png" width="30%">
<h3 style="text-align: center;">
<b>ESPECIALIZACIÓN EN CIENCIA DE DATOS E INGELIGENCIA ARTIFICIAL</b>
</h3>
<h3 style="text-align: center; color:  #C2262B;"> <!--Color institucional-->
<strong>Aprendizaje de MLOps<strong>
</h3>
<h3>
<b>Tema:</b> Proyecto inicial para Ciencia de Datos
</h3>
<hr style="width:100%; border:1px solid withe;">
<h6 style="text-align: rigth; margin-bottom: 5px">
<b>INTEGRANTES:</b> Bueno Osorno Dubian Andres
- Ceballos Bedoya Catherine - Rivera Guzman Yesenia - Salazar Seguro Maria Jimena
 <br><b>FECHA:</b> 08-2026<br>
</h6>
</div>

---

## ¿De qué se trata nuestro proyecto?

Decidimos trabajar con datos de Citibike (un sistema de transporte de bicicletas compartidas). La idea principal es resolver un problema muy común en logística urbana: **predecir cuánto tiempo va a durar el viaje de un usuario**.

Es un problema de **regresión**: la variable a predecir es continua (minutos). Un detalle importante del encuadre: el archivo no trae una columna de duración, hay que **construirla** a partir de las marcas de tiempo. Esa construcción de variables es parte del análisis, no un trámite previo.

## Los datos que vamos a usar

Estamos utilizando el dataset **JC-202607-citibike-tripdata.csv** que corresponde a los viajes de julio de 2026 en Jersey City y Hoboken (109.095 registros × 13 columnas). Este archivo nos entrega información clave como:

* La fecha y hora exacta en la que empieza y termina cada viaje
* Las estaciones de origen y destino con sus respectivas coordenadas
* El tipo de bicicleta (por ejemplo si es eléctrica)
* Si la persona que alquila es miembro suscrito o un usuario casual

> **Nota:** El archivo CSV original no está subido directamente a este repositorio para no saturar el peso y mantener las buenas prácticas de Git.

## Nuestro verdadero reto

Más allá de lograr un modelo matemático con una precisión perfecta, lo que queremos en este proyecto es poner a prueba el ciclo de vida completo de machine learning. Básicamente vamos a construir un pipeline que incluya:

* **Experimentación:** Entrenar el modelo y guardar los resultados con herramientas de tracking
* **Orquestación:** Automatizar la limpieza de datos y el entrenamiento
* **Despliegue:** Poner el modelo a funcionar (posiblemente a través de una API local)
* **Monitoreo:** Estar pendientes de que el modelo no pierda rendimiento cuando lleguen datos nuevos

## Estructura del repositorio

La estructura sigue una versión reducida de
[Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/):
datos crudos separados de datos procesados, el código como paquete instalable en
`src/` y los notebooks numerados para que el orden de lectura no deje dudas.

```
data/raw/          datos como llegan (no se versionan)
data/processed/    datos ya limpios (viajes_limpio.parquet)
notebooks/         01-carga-y-limpieza.ipynb  -> qué tienen de malo los datos
                   02-eda.ipynb               -> qué explica la duración
src/trips/         el mismo trabajo, como paquete -> ejecuta
  config.py        única fuente de verdad: rutas, semilla, columnas
  data/load.py     lectura y validación del CSV crudo
  data/clean.py    variable objetivo y reglas de limpieza
  features.py      variables derivadas: hora, día, distancia
  models/train.py  entrena 3 modelos, los compara y registra en MLflow
  api/             API que sirve el modelo champion (FastAPI)
Dockerfile         imagen de la API, en dos etapas y sin root
Makefile           los comandos del proyecto
```

Los notebooks explican y el paquete ejecuta: ninguno duplica la lógica del otro.

📘 **[Guía del proyecto](docs/guia-del-proyecto.md)** — qué hicimos, por qué cada
decisión y qué encontramos en los datos. Es el documento para ponerse al día.

🚀 **[Cómo empezar](docs/como-empezar.md)** — clonar, montar el entorno y trabajar en tu
propia rama desde VS Code. Empieza por aquí si es tu primera vez en el proyecto.

## Puesta en marcha

```bash
make setup     # uv sync + hook de pre-commit
make data      # lee el CSV crudo, lo describe y lo limpia: raw -> processed
make mlflow    # levanta el servidor de MLflow en http://127.0.0.1:5001
make train     # entrena, compara y registra los modelos (MLflow debe estar arriba)
make api       # levanta la API en http://127.0.0.1:8000/docs
make docker-build   # construye la imagen de la API
make docker-run     # corre la API en un contenedor
make notebook  # abre Jupyter Lab
```

Si no tienes `make` (Windows), los comandos equivalentes son:

```bash
uv sync
uv run pre-commit install
uv run python -m trips.data.load
uv run python -m trips.data.clean
uv run python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5001
uv run python -m trips.models.train
uv run jupyter lab
```

### Dónde está el CSV

Como el archivo crudo no se versiona, cada integrante trabaja con su propia copia.
La ruta por defecto está en `src/trips/config.py`; para apuntar a la tuya, define
la variable de entorno `TRIPS_RAW_DATA` antes de ejecutar:

```powershell
$env:TRIPS_RAW_DATA = "C:\ruta\a\JC-202607-citibike-tripdata.csv"
```

## Servir el modelo

La API carga el modelo del registry **por alias**, no desde un archivo:
`models:/duracion-regressor@champion`. Para cambiar el modelo en producción no
se reconstruye nada — se mueve el alias en MLflow y se reinicia el proceso.

Necesita MLflow arriba. Con `--host 0.0.0.0` para que el contenedor lo alcance:

```bash
make mlflow    # terminal 1
make api       # terminal 2 (sin contenedor)
```

En contenedor:

```bash
make docker-build
make docker-run
```

Documentación interactiva en http://127.0.0.1:8000/docs. Endpoints: `/predict`,
`/predict/batch`, `/health` y `/modelo`.

## Lo que sigue

- [x] Entorno reproducible con `uv` (`pyproject.toml` + `uv.lock`)
- [x] Estructura del repositorio y paquete instalable en `src/`
- [x] Carga y validación de los datos crudos (`trips.data.load`)
- [x] Limpieza y variable objetivo `duracion_min` (`trips.data.clean`) — 108.487 viajes válidos (99,44%)
- [x] EDA completo — variables derivadas y relación con el objetivo (`notebooks/02-eda.ipynb`)
- [x] Ingeniería de variables en el paquete (`trips.features`)
- [x] Entrenamiento y tracking con MLflow — 3 modelos comparados, mejor: árboles
      (MAE 4,06 min · error mediano 1,33 min · R² 0,53 sobre el logaritmo)
- [x] Despliegue — API con FastAPI y contenedor Docker (imagen multi-etapa, sin root)
- [ ] Monitoreo y reporte de drift
- [ ] Orquestación del pipeline
- [ ] Validación de datos y pruebas
