# Guía del proyecto — Predicción de duración de viajes Citi Bike

> **Para qué sirve este documento.** Explica qué hay en el repositorio, cómo correrlo y
> **por qué** se tomó cada decisión. Está escrito para dos lectores: una persona del
> equipo que necesita ponerse al día, y un asistente de IA al que se le pega este
> archivo completo para darle contexto del proyecto.
>
> **Curso:** Aprendizaje Automático en la nube — Especialización en Ciencia de Datos e
> Inteligencia Artificial, Universidad de Medellín.
> **Equipo:** Bueno Osorno Dubian Andrés · Ceballos Bedoya Catherine · Rivera Guzmán
> Yesenia · Salazar Seguro María Jimena.
> **Repositorio:** `DABO-lab/Apren-Automatico-en-la-nube`
> **Estado a la fecha:** carga, limpieza y EDA terminados. Falta modelado.

---

## 1. El problema

**Predecir cuánto va a durar un viaje en bicicleta**, en minutos.

Es un problema de **regresión**: la variable a predecir es continua. No es
clasificación (no estamos diciendo "corto/largo") ni agrupamiento.

Los datos son los viajes publicados por Citi Bike para Jersey City y Hoboken en julio
de 2026: **109.095 viajes, 13 columnas**, en el archivo
`JC-202607-citibike-tripdata.csv`.

Un detalle de encuadre que condiciona todo el trabajo: **el archivo no trae una columna
de duración**. Hay que construirla restando las dos marcas de tiempo. Lo mismo pasa con
la distancia, la hora y el día de la semana. Esa construcción de variables es parte del
análisis, no un trámite previo.

### Las 13 columnas originales

| Columna | Qué es |
|---|---|
| `ride_id` | Identificador único del viaje |
| `rideable_type` | `classic_bike` o `electric_bike` |
| `started_at`, `ended_at` | Marcas de tiempo de inicio y fin |
| `start_station_name`, `start_station_id` | Estación de origen |
| `end_station_name`, `end_station_id` | Estación de destino |
| `start_lat`, `start_lng` | Coordenadas de origen |
| `end_lat`, `end_lng` | Coordenadas de destino |
| `member_casual` | `member` (suscrito) o `casual` (ocasional) |

---

## 2. Cómo está organizado el repositorio

La estructura es una versión reducida de
[Cookiecutter Data Science](https://cookiecutter-data-science.drivendata.org/), el
estándar comunitario para proyectos de datos. Es la misma que usa el repositorio de
recapitulación del profesor (`mlops-recap-lab`).

```
data/raw/          datos como llegan (no se versionan)
data/processed/    datos ya limpios (viajes_limpio.parquet)
notebooks/         01-carga-y-limpieza.ipynb  -> qué tienen de malo los datos
                   02-eda.ipynb               -> qué explica la duración
src/trips/         el mismo trabajo, como paquete instalable
  config.py        única fuente de verdad: rutas, semilla, columnas, umbrales
  data/load.py     lectura y validación del CSV crudo
  data/clean.py    variable objetivo y reglas de limpieza
scratch/           análisis desechables (no se versionan)
Makefile           los comandos del proyecto
.pre-commit-config.yaml   el hook de ruff
```

### Los tres principios que explican esa estructura

**1. Los notebooks explican, el paquete ejecuta.** Ninguno duplica la lógica del otro.
El notebook 02 no reimplementa la limpieza: importa `clean_trips` del paquete y la
llama. Si alguien cambia una regla en `clean.py`, el notebook cambia con ella. Cuando
la lógica vive en los dos lados, tarde o temprano se desincronizan y nadie se entera.

**2. `config.py` es la única fuente de verdad.** Todas las rutas, la semilla aleatoria,
los nombres de columnas y los umbrales de limpieza viven ahí. Si un script y un notebook
necesitan el mismo valor, los dos lo importan del mismo archivo.

**3. `data/raw/` es intocable.** Los datos crudos nunca se modifican. Todo lo que se
arregla se escribe en `data/processed/`. Así siempre se puede volver al punto de
partida y rehacer el proceso completo.

### Dónde está el CSV

El archivo crudo **no está en el repositorio** porque pesa demasiado. Cada integrante
trabaja con su propia copia. La ruta por defecto está en `src/trips/config.py`; para
apuntar a la tuya, define una variable de entorno antes de ejecutar:

```powershell
$env:TRIPS_RAW_DATA = "C:\ruta\a\JC-202607-citibike-tripdata.csv"
```

---

## 3. Cómo correrlo

```bash
make setup     # instala dependencias exactas del uv.lock + activa el hook
make data      # lee el CSV crudo, lo describe y lo limpia: raw -> processed
make notebook  # abre Jupyter Lab
```

Sin `make` (típico en Windows), los equivalentes:

```powershell
uv sync
uv run pre-commit install
uv run python -m trips.data.load    # ficha técnica del archivo crudo
uv run python -m trips.data.clean   # limpieza -> genera el parquet
uv run python -m jupyterlab         # o abrir el .ipynb en VS Code
```

### Qué es cada herramienta

- **uv** — gestor de entornos y dependencias. `uv.lock` fija las versiones exactas, así
  que las cuatro obtenemos el mismo entorno. Eso es reproducibilidad: la diferencia
  entre "a mí me funcionó" y que le funcione a todo el mundo.
- **ruff** — revisa y formatea el código. Corre solo en cada `git commit` a través del
  hook de pre-commit.
- **pre-commit** — el "portero" de los commits. Si ruff reformatea algo, **aborta el
  commit** y deja los archivos corregidos. Hay que volver a hacer `git add .` y
  commitear otra vez. No es un error: es el hook trabajando.
- **parquet** — formato de archivo para los datos limpios. Conserva los tipos de las
  columnas (un CSV no) y ocupa mucho menos.

---

## 4. El flujo de datos, paso a paso

```
CSV crudo → load.py (lee y valida) → clean.py (construye y filtra) → parquet limpio → EDA
```

### 4.1 `trips.data.load` — leer sin tocar

Hace tres cosas y ninguna más:

1. **Lee** el CSV desde la ruta de `config.py`.
2. **Declara los tipos al leer**: los identificadores como texto (para no perder ceros
   a la izquierda), `rideable_type` y `member_casual` como categorías (ocupan una
   fracción de la memoria), y las fechas parseadas.
3. **Valida el esquema**: si el archivo no trae las 13 columnas esperadas, falla de
   inmediato.

Esa validación es a propósito. Enterarse de que el archivo cambió al cargarlo es
barato; enterarse al entrenar, no.

### 4.2 `trips.data.clean` — construir y filtrar

Un paso construye y tres eliminan. Cada uno imprime cuántas filas afectó.

| Paso | Qué hace | Filas | Por qué |
|---|---|---|---|
| 1 | Construye `duracion_min` | — | El archivo no la trae |
| 2 | Elimina viajes sin destino registrado | −330 | No sabemos dónde terminaron |
| 3 | Elimina duraciones > 24 h | −0 | Una bici más de un día fuera no volvió |
| 4 | Elimina falsos viajes | −278 | Misma estación y menos de 2 min |

**Resultado: 108.487 viajes (99,44% del original), cero nulos.**

---

## 5. Lo que encontramos en los datos (y por qué cada regla)

Esta sección es la más importante para defender el trabajo. Ninguno de los umbrales se
eligió a ojo: todos salen de mirar los datos primero.

### 5.1 Los datos no son crudos — Citi Bike ya los filtró

Dos evidencias:

- **Cero filas duplicadas y cero `ride_id` repetidos** en 109.095 viajes.
- **La duración mínima es exactamente 1,00 minutos.** Cero negativas, cero ceros, cero
  por debajo de un minuto.

Un piso así de limpio no ocurre en datos capturados de verdad: siempre hay errores.
Citi Bike descarta los viajes de menos de 60 segundos antes de publicar. Consecuencia
práctica: **no tenemos un paso de "eliminar duplicados"** como el repositorio del
profesor, y los problemas no están en el piso de la distribución sino en el techo.

### 5.2 Los 330 viajes sin destino

Nulos solo en las columnas del final del viaje, y con conteos distintos entre ellas
(330 / 329 / 299), lo que significa que no hay un solo patrón. Al cruzarlas:

| Patrón | Viajes |
|---|---|
| Falta todo el destino | 298 |
| Nombre de estación, pero sin id ni coordenadas | 31 |
| Coordenadas, pero sin estación | 1 |

La hipótesis inicial era que fueran bicicletas eléctricas dejadas fuera de estación
(tendrían coordenadas pero no estación). **Resultó falsa: solo 1 viaje encaja.** Lo que
hay son devoluciones que el sistema no registró.

No se reparten al azar: fallan el 0,43% de las eléctricas contra el 0,10% de las
clásicas, y el 0,57% de los casuales contra el 0,20% de los miembros. Se eliminan
—son el 0,3%— pero eso hay que decirlo: al quitarlas perdemos algo más de eléctricas y
de casuales que del resto.

### 5.3 Las dos anomalías que eran una sola

En los datos crudos había 44 viajes de más de 24 horas (el máximo: 25 horas). Al correr
la limpieza, el paso 3 —el que los elimina— **eliminó cero filas**, y sin embargo el
máximo bajó de 1.500 a 1.382 minutos.

La explicación: **los 44 viajes larguísimos estaban todos dentro de las 330 filas sin
destino**, así que el paso 2 ya se los había llevado. Es el mismo fenómeno visto por dos
lados — una bicicleta que no se devolvió bien no tiene estación de destino y además
acumula una duración absurda.

La regla se dejó igual, como **barrera de seguridad**: si el mes que viene aparece un
viaje de 30 horas *con* destino registrado, el paso 3 lo atrapa. Una regla que no
dispara hoy no es inútil: es una que todavía no ha hecho falta.

### 5.4 Los falsos viajes

4.480 viajes vuelven a la estación de origen. La mayoría son paseos reales, con
duración normal. Pero 278 duran menos de dos minutos: es el patrón de "saqué la bici,
estaba dañada, la devolví".

La regla necesita **las dos condiciones juntas** —misma estación *y* menos de dos
minutos— porque cualquiera de las dos por separado se llevaría viajes legítimos.

### 5.5 El borde del mes

10 viajes empezaron la noche del 30 de junio, aunque el archivo se llame "202607".
**Se conservan.** Borrar datos válidos solo para que la etiqueta cuadre es peor que
explicar el borde en una línea.

---

## 6. Lo que encontramos en el EDA

### 6.1 La duración hay que modelarla en logaritmo

| Medida | Valor | Referencia |
|---|---|---|
| Asimetría (skew) | **31,6** | Una distribución normal: 0 |
| Curtosis | **1.515** | Una distribución normal: 3 |
| Asimetría de `log(1+duración)` | **1,02** | — |
| Viajes de menos de 20 min | 91,7% | — |

La distribución vive casi entera pegada al origen, con una cola que se estira hasta las
23 horas. **Eso no es cosmético:** la mayoría de modelos de regresión minimizan el error
cuadrático, y con esta cola un solo viaje de 1.300 minutos pesa más en el entrenamiento
que cientos de viajes normales.

**Decisión: predecir `log(1 + duracion_min)`, no la duración cruda.**

### 6.2 Tipo de usuario: la variable que más separa

| Grupo | Viajes | Mediana | p95 |
|---|---|---|---|
| `casual` | 29.975 (27,6%) | 8,61 min | 43,2 min |
| `member` | 78.512 (72,4%) | 5,77 min | 20,9 min |

Es la diferencia entre pasear y desplazarse. Y no solo cambia el centro: cambia la
dispersión, que es lo que muestra el diagrama de cajas del notebook. Los casuales en
bicicleta clásica son **el grupo más impredecible del conjunto** — el que más le va a
costar al modelo.

### 6.3 La interacción entre tipo de usuario y tipo de bicicleta

Comparadas sin más, las bicicletas casi no se diferencian: 6,92 min la clásica contra
6,22 la eléctrica. Menos de un minuto. Pero al cruzar con el tipo de usuario:

| | clásica | eléctrica | diferencia |
|---|---|---|---|
| **miembro** | 5,92 min | 5,68 min | −0,24 |
| **casual** | 10,98 min | 7,64 min | **−3,34** |

Eso se llama una **interacción**: el efecto de una variable depende del valor de otra.
El promedio general la escondía por completo.

¿Por qué? La velocidad implícita lo explica: **12,8 km/h la eléctrica contra 9,2 la
clásica, un 39% más rápida**. El miembro que va quince cuadras hasta la estación del
PATH llega igual de rápido con cualquiera, porque su viaje es corto y está lleno de
semáforos. El casual que se da una vuelta larga sí nota el motor en el reloj.

**Consecuencia para el modelado:** un modelo lineal solo captura esta interacción si
alguien le escribe explícitamente el término; los modelos de árboles la encuentran
solos. Es un argumento concreto para probar árboles.

### 6.4 La hora del día indica el propósito del viaje

- **Volumen:** pico a las 8 de la mañana (7.537 viajes) y otro mayor entre las 5 y las
  7 de la tarde (cerca de 9.900 por hora). La forma clásica del desplazamiento laboral.
- **Duración:** mínimo de **4,6 minutos a las 6 de la mañana**, máximo de **8,6 en la
  madrugada**.

Las horas de más tráfico son las de los viajes más cortos. Nadie pasea a las seis de la
mañana. Fin de semana: **7,7 minutos contra 6,1** en días laborables.

La hora es **cíclica** (las 23 y las 0 son vecinas), así que al modelar hay que decidir
si se codifica como categoría o con senos y cosenos.

### 6.5 La distancia, y por qué Pearson casi nos hace descartarla

Distancia en línea recta entre estaciones, calculada con la **fórmula de haversine**
(distancia sobre una esfera a partir de latitudes y longitudes). Mediana 1,10 km,
p95 3,00 km.

| Forma de medir la correlación con la duración | Valor |
|---|---|
| Pearson sobre los valores crudos | **0,19** |
| Spearman (sobre los rangos) | **0,71** |
| Pearson sobre los logaritmos | 0,62 |

**Es el mismo par de variables y los mismos datos.** Pearson mide relación *lineal* y la
cola de la distribución lo destroza; Spearman trabaja sobre los rangos —quién es más
largo que quién— y los extremos no lo distorsionan.

Si el análisis se hubiera quedado con el `df.corr()` por defecto, habríamos descartado
la mejor variable del conjunto.

Dos limitaciones de esta variable:

- Es la distancia **en línea recta**, no la recorrida: siempre subestima, y más donde
  hay que rodear un parque o cruzar un puente.
- **4.202 viajes (3,9%) tienen distancia cero** porque vuelven al origen. Por debajo de
  200 metros la duración mediana incluso *sube*: son paseos largos que terminan cerca de
  donde empezaron, y ahí la línea recta miente descaradamente.

### 6.6 Un cero en la matriz de correlación no es permiso para descartar

`hora` y `dia_semana` salen con correlaciones cercanas a cero (0,09 y 0,12). **No hay
que creerles.** Son números que no son cantidades: la hora 23 no es "mayor" que la 1, es
su vecina. Una correlación mide si al subir una variable sube la otra, y eso no tiene
sentido en una escala que da la vuelta.

La gráfica del perfil horario demostró que la hora sí explica la duración — con una
forma de U que ninguna correlación lineal puede capturar.

### 6.7 La variable que hay que dejar fuera: fuga de información

`velocidad_kmh` fue útil para entender el efecto de las eléctricas, pero **no puede
entrar al modelo**: se calcula dividiendo la distancia entre la duración, es decir,
**contiene la respuesta**.

Un modelo que la reciba tendrá un desempeño espectacular en las pruebas y será inútil en
la realidad, porque el día que haya que predecir un viaje que todavía no ha terminado,
esa velocidad no existe.

Eso se llama **fuga de información** (*data leakage*), y es de los errores más caros en
proyectos de machine learning precisamente porque **no se manifiesta como un error: se
manifiesta como un resultado demasiado bueno**. Si un modelo da resultados sospechosamente
buenos, lo primero que hay que revisar es si alguna variable está mirando el futuro.

---

## 7. Variables candidatas para el modelo

| Variable | Tipo | Por qué entra |
|---|---|---|
| `distancia_km` | numérica | Spearman 0,71 — la relación más fuerte |
| `member_casual` | categórica | Separa dos comportamientos: 8,6 contra 5,8 min |
| `rideable_type` | categórica | Poco sola, mucho en interacción con la anterior |
| `hora` | cíclica | Indica el propósito del viaje |
| `dia_semana` / `es_finde` | categórica | Fin de semana: 7,7 contra 6,1 min |

**Objetivo:** `log(1 + duracion_min)`
**Fuera del modelo:** `velocidad_kmh` (fuga de información)

---

## 8. Decisiones sobre las gráficas

Estas también son parte del trabajo y valen para cualquier informe:

**La paleta se validó contra daltonismo.** La original (gris para bicicleta clásica,
verde para eléctrica) tenía una separación perceptual de 14,5 cuando el mínimo
aceptable es 15: incluso con visión normal costaba distinguirlas, y con deuteranopia
eran el mismo color. Los pares actuales —azul/rojo para el tipo de usuario, verde
azulado/morado para el tipo de bici— sí pasan.

**Nada de doble eje vertical.** El volumen de viajes por hora y la duración mediana van
en dos paneles apilados que comparten el eje horizontal, no en una sola gráfica con dos
escalas. Con dos ejes verticales, las curvas se cruzan donde uno decida poner los
límites y la relación que uno "ve" es un artefacto del dibujo.

**Los histogramas no acumulan en el borde.** Al recortar el eje a 60 minutos hay que
*excluir* los viajes más largos y decir cuántos quedaron fuera, no amontonarlos en el
último bin — eso crea un pico falso.

**La matriz de correlación oculta el triángulo superior y la diagonal.** La mitad
superior es un espejo de la inferior y la diagonal es la correlación de cada variable
consigo misma: información cero, pero es lo que más pesa visualmente.

---

## 9. Cómo trabajamos con git

El flujo que pide el profesor (`docs/03-pull-requests.md` de su repositorio):

1. **`main` no se toca directo.** Todo entra por rama y pull request.
2. **Una rama por entrega**, con nombre `tipo/descripcion-corta`:
   `feature/eda-completo`, `fix/nulos-destino`, `docs/guia-del-proyecto`.
3. La rama **nace de `main` actualizado**, vive lo que dura el PR, y **se borra tras el
   merge**. Reusar una rama indefinidamente es lo que produce conflictos en cada entrega.

```powershell
git switch main
git pull
git switch -c feature/lo-que-sigue
# ... trabajo, commits ...
git push -u origin feature/lo-que-sigue
```

### Cosas que nos han pasado

- **El hook aborta el primer commit casi siempre.** Ruff reformatea y rechaza. Se
  vuelve a hacer `git add .` y `git commit`, y entra. No es un error.
- **Conflictos en el README.** Pasaron tres veces, siempre por la misma causa: dos ramas
  editando el mismo archivo. Se resuelven trayendo `main` a la rama
  (`git merge origin/main`), arreglando el archivo y commiteando.
- **No editar un notebook desde dos lados.** Si el `.ipynb` está abierto en VS Code y
  alguien lo modifica en disco, el siguiente guardado de VS Code sobreescribe el cambio.
  Los notebooks no se fusionan solos.

### Entorno Windows

- **"Una directiva de Control de aplicaciones bloqueó este archivo"** al importar
  pandas: `Get-ChildItem .venv -Recurse -Include *.pyd,*.dll | Unblock-File`.
- El mismo error con `jupyter lab` **no** se arregla así, porque bloquea el ejecutable.
  Se esquiva llamando al módulo: `uv run python -m jupyterlab`, o se trabaja el notebook
  en VS Code.

---

## 10. Estado y qué sigue

- [x] Entorno reproducible con `uv` (`pyproject.toml` + `uv.lock`)
- [x] Estructura del repositorio y paquete instalable en `src/`
- [x] Carga y validación de los datos crudos (`trips.data.load`)
- [x] Limpieza y variable objetivo `duracion_min` (`trips.data.clean`)
- [x] EDA completo (`notebooks/02-eda.ipynb`)
- [ ] **Ingeniería de variables en el paquete (`trips.features`)** ← lo que sigue
- [ ] Entrenamiento y tracking con MLflow
- [ ] Despliegue y monitoreo

### Lo primero de la siguiente entrega

Las variables derivadas (haversine, hora, día de la semana) viven hoy **dentro del
notebook 02**, porque se construyeron para explorar. Antes de entrenar hay que moverlas
a `src/trips/features.py`. Si el entrenamiento las recalcula por su cuenta, tarde o
temprano se cuela una diferencia entre lo que exploramos y lo que ve el modelo, y ese
tipo de error no avisa.

---

## 11. Glosario

**Asimetría (skew)** — Qué tan inclinada está una distribución. Cero es simétrica;
positiva significa cola hacia la derecha. La nuestra: 31,6.

**Curtosis** — Qué tan pesadas son las colas. Una normal tiene 3. La nuestra: 1.515.

**Fuga de información (data leakage)** — Cuando una variable del entrenamiento contiene,
directa o indirectamente, la respuesta. Produce resultados excelentes en pruebas y
modelos inútiles en producción.

**Haversine** — Fórmula para calcular la distancia entre dos puntos sobre una esfera a
partir de sus coordenadas.

**Interacción** — Cuando el efecto de una variable depende del valor de otra. Los
modelos de árboles las capturan solos; los lineales necesitan que se las escriban.

**Parquet** — Formato de archivo columnar que conserva los tipos de datos y comprime
mucho mejor que un CSV.

**Pearson vs Spearman** — Pearson mide relación lineal sobre los valores; Spearman mide
relación monótona sobre los rangos. Con colas largas, Pearson subestima.

**Percentil 95 (p95)** — El valor por debajo del cual está el 95% de los datos. Más
robusto que el máximo para describir "lo alto" de una distribución.

**Variable objetivo (target)** — Lo que el modelo predice. Aquí: `duracion_min`, y en el
entrenamiento su logaritmo.
