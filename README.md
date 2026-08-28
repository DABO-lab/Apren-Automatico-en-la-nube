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
 <br><b>FECHA:</b> 03-2026<br>
</h6>
</div>

---

## ¿De qué va este proyecto?

Predecir **cuánto va a durar un viaje en bicicleta** con los datos abiertos de
Citi Bike (Jersey City y Hoboken, julio de 2026: 109.095 viajes). Es un problema
de **regresión**: la variable objetivo son minutos.

El archivo no trae la duración: hay que construirla a partir de `started_at` y
`ended_at`. Esa construcción de variables es parte del análisis, no un trámite previo.

## Estructura

La estructura sigue una versión reducida de
[Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/):
datos crudos separados de datos procesados, el código como paquete instalable en
`src/` y los notebooks numerados para que el orden de lectura no deje dudas.

```
data/raw/          datos como llegan (no se versionan)
data/processed/    datos ya limpios (parquet)
notebooks/         01-carga-y-eda.ipynb  -> explica
src/trips/         el mismo trabajo, como paquete -> ejecuta
  config.py        única fuente de verdad: rutas, semilla, columnas
  data/load.py     lectura y validación del CSV crudo
Makefile           los comandos del proyecto
```

Los notebooks explican y el paquete ejecuta: ninguno duplica la lógica del otro.

## Puesta en marcha

```bash
make setup     # uv sync + hook de pre-commit
make data      # lee el CSV crudo y muestra su ficha técnica
make notebook  # abre Jupyter Lab
```

Si no tienes `make` (Windows), los comandos equivalentes son:

```bash
uv sync
uv run pre-commit install
uv run python -m trips.data.load
uv run jupyter lab
```

### Dónde está el CSV

El archivo crudo pesa demasiado para versionarlo, así que vive fuera del repo.
La ruta por defecto está en `src/trips/config.py`; para apuntar a tu propia copia
define la variable de entorno `TRIPS_RAW_DATA` antes de ejecutar:

```powershell
$env:TRIPS_RAW_DATA = "C:\ruta\a\JC-202607-citibike-tripdata.csv"
```

## Estado del proyecto

- [x] Entorno reproducible con `uv` (`pyproject.toml` + `uv.lock`)
- [x] Estructura del proyecto y paquete instalable en `src/`
- [x] Carga y validación de los datos crudos (`trips.data.load`)
- [ ] Limpieza y variable objetivo `duracion_min` (`trips.data.clean`)
- [ ] EDA completo
- [ ] Entrenamiento y tracking con MLflow

