# Informe de estado del proyecto — Predicción de duración de viajes Citi Bike

**Fecha:** 9 de septiembre de 2026
**Repositorio:** `DABO-lab/Apren-Automatico-en-la-nube`
**Curso:** Aprendizaje Automático en la nube — Especialización en Ciencia de Datos e
Inteligencia Artificial, Universidad de Medellín
**Equipo:** Bueno Osorno Dubian Andrés · Ceballos Bedoya Catherine ·
Rivera Guzmán Yesenia · Salazar Seguro María Jimena

> **Para qué sirve este documento.** Para que cualquiera del equipo pueda tomar el
> proyecto donde está, entender **por qué** cada cosa está como está, y seguir
> trabajando sin depender de quien la hizo. También sirve como contexto para pegarle
> a un asistente de IA: es markdown plano y se copia completo.
>
> Los otros dos documentos del repositorio se complementan con este:
> `docs/como-empezar.md` (montar el entorno paso a paso) y
> `docs/guia-del-proyecto.md` (la guía de estudio del análisis de datos).

---

## 1. Dónde estamos

**El proyecto funciona de punta a punta.** Hoy se puede: cargar el CSV crudo,
validarlo contra un contrato, limpiarlo, construir variables, entrenar tres modelos,
compararlos, registrarlos con versión, servir el mejor por una API REST dentro de un
contenedor, medir si los datos nuevos se parecen a los de entrenamiento, y orquestar
todo eso en un flujo con caché.

Contra la rúbrica del profesor (7 dimensiones, cada una de 1 a 5):

| Dimensión | Peso | Estado | Dónde vive |
|---|---:|---|---|
| Reproducibilidad | 15% | ✅ | `uv.lock`, `Makefile`, `docs/` |
| Datos | 15% | ✅ | `data/contract.py` + fixtures rotos |
| Tracking y registry | 15% | ✅ | `models/train.py`, MLflow |
| Pipeline | 15% | ✅ | `flows/training.py` (Prefect) |
| Deployment | 15% | ✅ | `api/`, `Dockerfile` |
| Monitoreo | 15% | ✅ | `monitoring/`, umbral calibrado |
| Ingeniería y documentación | 10% | ✅ | 43 pruebas, `docs/`, README |

Lo que queda es refinamiento, no construcción. Está en la sección 8.

---

## 2. El problema

**Predecir cuántos minutos va a durar un viaje en bicicleta pública**, a partir de lo
que se sabe cuando el viaje empieza: de dónde sale, a dónde va, a qué hora, qué tipo
de bicicleta y qué tipo de usuario.

Los datos son los viajes publicados por Citi Bike para Jersey City y Hoboken en julio
de 2026: **109.095 viajes, 13 columnas**. El archivo **no trae la duración**: se
construye restando las marcas de tiempo. Lo mismo la distancia, la hora y el día de
la semana.

Es un problema de **regresión** (la variable a predecir es continua).

---

## 3. Mapa del repositorio

```
data/raw/              el CSV crudo (no se versiona)
data/processed/        viajes_limpio.parquet (no se versiona, se regenera)
notebooks/
  01-carga-y-limpieza.ipynb   qué problemas tenían los datos
  02-eda.ipynb                qué explica la duración
src/trips/
  config.py            ÚNICA fuente de verdad: rutas, semilla, columnas,
                       umbrales, alias, política de promoción
  data/load.py         lee el CSV, declara tipos, valida el contrato de entrada
  data/clean.py        construye duracion_min y aplica 4 reglas de limpieza
  data/contract.py     los dos contratos de datos (Pandera)
  features.py          variables derivadas: hora, día, fin de semana, distancia
  models/train.py      entrena, evalúa, registra versiones y marca el candidato
  api/schemas.py       el contrato de la API (Pydantic)
  api/modelo.py        carga el modelo del registry por alias
  api/main.py          los endpoints
  monitoring/estadistico.py   PSI, KS, chi²/V de Cramér, Jensen-Shannon
  monitoring/check_drift.py   el chequeo, con umbral calibrado y códigos de salida
  flows/training.py    el pipeline orquestado con Prefect
scripts/promote.py     la compuerta de promoción a producción
tests/                 43 pruebas
docs/                  esta guía, la de arranque y la de estudio
Dockerfile             imagen de la API: dos etapas, sin root, con healthcheck
Makefile               todos los comandos del proyecto
```

**Tres principios explican esta estructura**, y conviene respetarlos al agregar cosas:

1. **Los notebooks explican, el paquete ejecuta.** El notebook 02 no reimplementa la
   limpieza: importa `clean_trips` del paquete. Cuando la lógica vive en dos lados,
   tarde o temprano se desincroniza y nadie se entera.
2. **`config.py` es la única fuente de verdad.** Cualquier ruta, umbral o nombre de
   columna nuevo va ahí, no incrustado en el código que lo usa.
3. **`data/raw/` es intocable.** Todo lo que se arregla se escribe en
   `data/processed/`. Siempre se puede volver al punto de partida.

---

## 4. Cómo correrlo todo

Requisitos: Git, VS Code, `uv` y Docker Desktop. El detalle de instalación está en
`docs/como-empezar.md`.

### Primera vez

```bash
uv sync                       # instala las versiones exactas del uv.lock
uv run pre-commit install     # activa el revisor de estilo
```

El **CSV crudo no está en el repositorio**: pídeselo a Dubian y déjalo en
`data/raw/JC-202607-citibike-tripdata.csv`. Si prefieres tenerlo en otro sitio, define
la variable de entorno `TRIPS_RAW_DATA` con la ruta.

### El ciclo completo

Necesitas **tres terminales**, porque dos comandos quedan ocupando la suya.

**Terminal 1 — MLflow** (déjala abierta):

```bash
uv run python -m mlflow server --backend-store-uri sqlite:///mlflow.db \
  --host 0.0.0.0 --port 5001 --workers 1 \
  --allowed-hosts "localhost:5001,127.0.0.1:5001,host.docker.internal:5001"
```

Interfaz en http://127.0.0.1:5001

> `--host 0.0.0.0` no es capricho: con `127.0.0.1` el contenedor de la API no puede
> alcanzarlo, porque para él nuestra máquina es otro equipo en la red.
> `--workers 1` evita un error de Windows (`WinError 10022`) cuando varios procesos
> comparten el mismo socket.

**Terminal 3 — Prefect** (déjala abierta; en Windows el servidor efímero que Prefect
levanta por corrida es inestable y falla con `httpx.ConnectTimeout`):

```bash
uv run prefect server start
```

Una sola vez, para que el cliente use ese servidor en vez de levantar uno temporal:

```bash
uv run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

Tablero en http://127.0.0.1:4200 — ahí se ve el grafo de tareas, los tiempos y cuáles
salieron de caché.

**Terminal 2 — el pipeline:**

```bash
uv run python -m trips.flows.training     # datos -> variables -> drift -> modelos
uv run python scripts/promote.py          # la compuerta: ¿el candidato entra?
```

Corre el flujo **dos veces seguidas**: la segunda debería tardar un segundo en vez de
cuarenta. Eso es el caché de Prefect y es una de las cosas que la rúbrica pide
demostrar.

**Terminal 3 — la API:**

```bash
uv run uvicorn trips.api.main:app --port 8000        # sin contenedor
# o, en contenedor:
docker build -t trips-api .
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway trips-api
```

Documentación interactiva en http://127.0.0.1:8000/docs

### Todos los comandos

| Comando | Qué hace |
|---|---|
| `make setup` | dependencias + hook de estilo |
| `make data` | CSV crudo → parquet limpio (con los dos contratos) |
| `make features` | resumen de las variables derivadas |
| `make mlflow` | levanta el servidor de MLflow |
| `make train` | entrena las tres configuraciones |
| `make flow` | el pipeline completo orquestado |
| `make promote` | la compuerta de promoción |
| `make prefect-ui` | tablero de Prefect en :4200 |
| `make api` | levanta la API |
| `make docker-build` / `make docker-run` | imagen y contenedor |
| `make drift` | chequeo de drift |
| `make test` | las 43 pruebas |
| `make lint` | ruff |
| `make notebook` | Jupyter Lab |

---

## 5. Las decisiones, y por qué

Esta es la sección que hay que leer antes de cambiar algo. Ninguno de estos números
se eligió a ojo.

### 5.1 Los datos vienen pre-filtrados por Citi Bike

Dos evidencias: **cero filas duplicadas** en 109 mil registros, y la duración mínima
es **exactamente 1,00 minutos**. Un piso así de limpio no ocurre en datos capturados
de verdad. Citi Bike descarta los viajes de menos de 60 segundos antes de publicar.

Consecuencia: no tenemos un paso de "eliminar duplicados" y los problemas no están en
el piso de la distribución sino en el techo.

### 5.2 Las cuatro reglas de limpieza

| Paso | Qué elimina | Filas | Por qué |
|---|---|---:|---|
| 1 | (construye `duracion_min`) | — | el archivo no la trae |
| 2 | viajes sin destino registrado | 330 | no sabemos dónde terminaron |
| 3 | duraciones de más de 24 h | 0 | una bici más de un día fuera no volvió |
| 4 | falsos viajes | 278 | misma estación y menos de 2 minutos |

Quedan **108.487 viajes (99,44%)**.

Dos detalles que valen oro en la sustentación:

- **Los 44 viajes de más de 24 horas estaban todos dentro de las 330 sin destino.** Por
  eso el paso 3 elimina cero filas hoy. Es la misma anomalía vista por dos lados: una
  bicicleta que no se devolvió bien no tiene estación de llegada *y* acumula una
  duración absurda. La regla se dejó como **barrera** para datos futuros.
- **La regla 4 necesita las dos condiciones juntas.** Hay 4.480 viajes que vuelven a
  la estación de origen y la mayoría son paseos reales con duración normal. Solo 278
  duran menos de dos minutos, y esos sí son "saqué la bici, estaba dañada, la devolví".

### 5.3 Se modela el logaritmo de la duración

| Medida | Valor | Una normal tiene |
|---|---|---|
| Asimetría | 31,6 | 0 |
| Curtosis | 1.515 | 3 |
| Asimetría de `log(1+duración)` | 1,02 | — |

Sin transformar, un solo viaje de 1.300 minutos pesa más en el entrenamiento que
cientos de viajes normales. **Las métricas se reportan en minutos**, deshaciendo la
transformación: nadie entiende "0,42 de error logarítmico".

### 5.4 La partición es temporal, no aleatoria

Se ordena por fecha y el 20% más reciente queda para prueba (corte: 25 de julio,
22:11 → 86.789 entrenan, 21.698 evalúan). Una partición aleatoria dejaría entrenar con
viajes del 31 de julio para predecir viajes del 3: hacer trampa con el tiempo.

Las métricas salen peores que con partición aleatoria, y eso es correcto.

### 5.5 `velocidad_kmh` no entra al modelo — fuga de información

Se calcula dividiendo distancia entre duración: **contiene la respuesta**. Un modelo
que la reciba tendrá un desempeño espectacular en las pruebas y será inútil el día que
haya que predecir un viaje que todavía no terminó.

Está blindado con una prueba (`test_add_features_no_calcula_velocidad`) para que nadie
la agregue al paquete "porque es útil".

### 5.6 El modelo elegido

| Modelo | MAE | Error mediano | R²(log) |
|---|---|---|---|
| **HistGradientBoosting** | **4,06 min** | **1,33 min** | **0,530** |
| Ridge | 4,79 | 1,86 | 0,300 |
| Baseline (mediana) | 5,85 | 2,68 | −0,013 |

**El baseline existe para que los otros dos números signifiquen algo.** Un modelo que
siempre predice la mediana es la vara de medir: cualquier modelo que no le gane no
está aportando información.

**El salto de R² entre Ridge y árboles (0,30 → 0,53) con las mismas variables** se
explica por una interacción que encontramos en el EDA: para un usuario casual, la
bicicleta eléctrica recorta la mediana de 11,0 a 7,6 minutos; para un miembro, de 5,9
a 5,7. Un modelo lineal no ve esa interacción a menos que se la escriban; los árboles
la encuentran solos. **El EDA lo predijo y el entrenamiento lo confirmó.**

**Cuidado con el RMSE**: pasó de 25,40 a 24,43, apenas un 4%, mientras el error mediano
se redujo a la mitad. El RMSE eleva los errores al cuadrado y queda secuestrado por la
cola. La cifra para contar es el error mediano: **la mitad de los viajes se predicen
con menos de 1,33 minutos de error**.

### 5.7 Entrenar y promover son cosas distintas

El pipeline marca el mejor modelo como **`candidate`**. La promoción a **`champion`**
—el alias que sirve la API— la hace `scripts/promote.py`, y solo si el candidato mejora
el MAE del campeón **en al menos 2%**.

Un pipeline que se autopromueve no tiene control de calidad: el día que los datos
lleguen mal, el modelo malo entra a producción solo. Y empatar no basta, porque
cambiar el modelo en producción tiene un costo.

Para cambiar el modelo en producción no se reconstruye nada: se mueve el alias y se
reinicia la API.

### 5.8 Los contratos de datos

Dos contratos, en dos momentos:

- **`ViajesCrudos`** valida el CSV al cargarlo, con rangos anchos. Es la aduana: si
  Citi Bike cambia algo, nos enteramos ahí.
- **`ViajesLimpios`** valida lo que sale de `clean.py`, con cotas estrictas. Si falla,
  **el parquet no se escribe**: mejor no tener datos procesados que tenerlos mal.

Validan en **tres niveles**, porque cada uno atrapa errores que los otros no ven:

| Nivel | Ejemplo que atrapa |
|---|---|
| Por fila | una coordenada en Medellín, un tipo de bici que no existe |
| Por distribución | un archivo truncado con 50 filas perfectas; 30% sin destino |
| Entre columnas | un viaje que termina antes de empezar |

Las pruebas verifican **las dos direcciones**: siete degradaciones reales deben fallar,
y tres lotes válidos independientes deben pasar (**control negativo**). Sin el control
negativo, un contrato que rechace absolutamente todo pasaría los tests igual — y
bloquearía el pipeline con datos buenos, que es un fallo peor porque parece que funciona.

### 5.9 El umbral de drift está calibrado, no inventado

Con 108 mil filas **el p-valor deja de servir**. Lo medimos: partiendo la referencia en
dos mitades aleatorias treinta veces —donde por construcción no hay drift— el **7% de
las comparaciones ya daba p < 0,05**.

Por eso la decisión se toma con **tamaño de efecto**, y el umbral sale de esa misma
línea base nula: el ruido del PSI es 0,0009, así que alertar en 0,10 es hacerlo a
**cien veces el ruido de fondo**.

El resultado real de julio:

```
Con p < 0,05 se habrían alertado 6 de 6 columnas.
Con tamaño de efecto: 1 de 6 (17%), por debajo del umbral del 30%.
```

La única que se movió es `dia_semana` (V de Cramér = 0,186), y tiene explicación: los
últimos seis días de julio no cubren la semana completa. Es drift real causado por
nuestra partición temporal.

El informe incluye a propósito el campo `p_valor_diria_drift` para dejar esa diferencia
a la vista.

### 5.10 El caché del pipeline, medido

```
Primera corrida:  40,8 s
Segunda corrida:   1,1 s   (36,7x)
```

La política de caché es `INPUTS + TASK_SOURCE`: se invalida si cambian los datos **o el
código de la tarea**. Si alguien modifica una regla de limpieza, el resultado viejo
deja de valer aunque el CSV sea el mismo.

> **Una trampa que ya nos costó y conviene conocer:** en la primera versión, la tarea de
> entrenamiento recibía el identificador de la corrida de Prefect como argumento. Como
> ese identificador cambia cada vez, la clave de caché nunca coincidía y el modelo se
> reentrenaba siempre — **el caché existía pero no servía para nada**. Se arregló
> leyéndolo del contexto en vez de recibirlo. Sin medir los dos tiempos, eso pasa
> desapercibido.

---

## 6. Cómo trabajamos con git

1. **`main` no se toca directo.** Todo entra por rama y pull request.
2. **Una rama por entrega**, con nombre `tipo/descripcion-corta`:
   `feature/eda-completo`, `fix/nulos-destino`, `docs/guia`.
3. La rama **nace de `main` actualizado**, vive lo que dura el PR y **se borra tras el
   merge**. Reusar una rama indefinidamente es lo que produce conflictos en cada entrega.

```bash
git switch main
git pull
git switch -c feature/lo-que-sigue
# ... trabajo, commits ...
git push -u origin feature/lo-que-sigue
```

**Cosas que ya nos pasaron:**

- **El hook aborta el primer commit casi siempre.** Ruff reformatea y rechaza; se
  vuelve a hacer `git add .` y `git commit`, y entra. No es un error.
- **Conflictos en el README**, tres veces, siempre por dos ramas editando el mismo
  archivo. Se resuelven trayendo `main` a la rama (`git merge origin/main`).
- **Un notebook, una persona a la vez.** Los `.ipynb` no se fusionan solos: si dos
  personas editan el mismo, alguien pierde su trabajo. Avisen por el grupo.
- **`git commit` commitea todo lo que esté en el índice**, no solo el último archivo
  agregado. Revisen `git status` antes de confirmar.

---

## 7. Resultados en una tabla

| Qué | Valor |
|---|---|
| Viajes crudos | 109.095 |
| Viajes limpios | 108.487 (99,44%) |
| Partición | temporal, corte 25/07 22:11 (86.789 / 21.698) |
| Objetivo | `log(1 + duracion_min)`, reportado en minutos |
| Mejor modelo | HistGradientBoosting |
| MAE | 4,06 min |
| Error mediano | 1,33 min |
| R² sobre el logaritmo | 0,530 |
| Columnas con drift | 1 de 6 (17%), sin alerta |
| Pruebas | 43, todas en verde |
| Caché del pipeline | 40,8 s → 1,1 s |

---

## 8. Lo que falta, por orden de rendimiento

### 8.1 CI/CD con GitHub Actions — lo más valioso que queda

La rúbrica pide, para el nivel máximo, *"CI completo con gate de promoción"*. La
compuerta ya existe (`scripts/promote.py`); falta el flujo de GitHub Actions que en
cada pull request corra `make lint` y `make test`, y que en `main` corra el pipeline y
llame a la compuerta.

**Ojo con una penalización específica**: usar `|| true` en un paso de CI resta 5 puntos.
Es la trampa de hacer que el CI "pase siempre".

Esfuerzo estimado: una sesión.

### 8.2 Llegar a 20 corridas en MLflow

El nivel 5 de la dimensión de tracking pide **≥20 runs con aliases**. Hoy hay 3 (más
las de drift). Sale casi gratis ampliando la lista `CONFIGS` en `models/train.py` con
más combinaciones de hiperparámetros: el flujo las entrena en paralelo y las registra
todas.

Esfuerzo: media hora, más el tiempo de cómputo.

### 8.3 Limpiar las salidas de los notebooks

Los notebooks se commitean con sus figuras dentro. La rúbrica lo penaliza con **−3
décimas** porque hace los diffs ilegibles. Se arregla con un hook que las limpie
automáticamente.

**Es una decisión del equipo**: sin salidas, el profesor tendría que ejecutar los
notebooks para ver las gráficas. El argumento a favor de limpiarlas es que
`docs/guia-del-proyecto.md` ya cuenta todos los hallazgos con sus números.

### 8.4 Drift contra agosto de verdad

Hoy el chequeo compara los últimos días de julio contra los primeros. Cuando Citi Bike
publique agosto, basta con:

```bash
uv run python -m trips.monitoring.check_drift --referencia data/processed/viajes_limpio.parquet --actual data/processed/agosto_limpio.parquet
```

Ahí se vería drift real entre meses, que es mucho más interesante que el artefacto de
la partición.

### 8.5 Despliegue en la nube (opcional)

La rúbrica dice explícitamente que un despliegue local bien hecho vale igual que uno en
la nube. Con la imagen Docker ya construida, subirla es más un trámite que un reto.

---

## 9. Tropiezos conocidos del entorno (Windows)

| Síntoma | Solución |
|---|---|
| `DLL load failed ... Control de aplicaciones bloqueó este archivo` al importar pandas | `Get-ChildItem .venv -Recurse -Include *.pyd,*.dll \| Unblock-File` |
| Lo mismo al abrir `jupyter lab` | No se arregla igual (bloquea el ejecutable): usar `uv run python -m jupyterlab` o trabajar en VS Code |
| `Docker Desktop is unable to start` | `wsl --update` como administrador y **reiniciar el equipo** |
| `port is already allocated` al correr el contenedor | Queda uno anterior vivo: `docker ps` y `docker stop <nombre>` |
| `Deletion of directory failed` al cambiar de rama | Cerrar VS Code (tiene archivos abiertos); o `git fetch origin main:main` para actualizar sin checkout |
| `Another git process seems to be running` | Borrar `.git\index.lock` |
| MLflow arranca con muchos errores `WinError 10022` | Agregar `--workers 1` |
| El flujo falla con `httpx.ConnectTimeout` al arrancar | El servidor efímero de Prefect no alcanza a levantar: usar uno fijo (`prefect server start`) y `prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api` |
| PowerShell expande `"*"` como nombres de archivo | Nunca pasar `--allowed-hosts "*"`; nombrar los hosts explícitamente |

**Sobre versiones:** MLflow 3 exige `pandas<3`. El proyecto usa pandas 2.3.3 con
mlflow 3.15.2, las mismas versiones del repositorio del profesor. Si alguien sube
pandas a la serie 3, MLflow deja de instalarse y `uv` retrocede hasta una versión de
2022 que ya no funciona.

---

## 10. Glosario

**Alias (`champion` / `candidate`)** — Etiqueta movible que apunta a una versión del
modelo. Cambiar de modelo en producción es mover el alias, no reconstruir nada.

**Asimetría (skew)** — Qué tan inclinada está una distribución. Cero es simétrica. La
nuestra: 31,6.

**Caché de tarea** — Prefect guarda el resultado de cada paso y no lo recalcula si sus
entradas no cambiaron.

**Contrato de datos** — Declaración de qué forma deben tener los datos, que se verifica
automáticamente al cargarlos y al procesarlos.

**Drift** — Que los datos nuevos ya no se parecen a aquellos con los que se entrenó.

**Fuga de información (data leakage)** — Cuando una variable contiene, directa o
indirectamente, la respuesta. Produce resultados excelentes en pruebas y modelos
inútiles en producción.

**Haversine** — Fórmula para la distancia entre dos puntos sobre una esfera, a partir
de coordenadas.

**Interacción** — Cuando el efecto de una variable depende del valor de otra. Los
árboles las capturan solos; los modelos lineales necesitan que se las escriban.

**MAE** — Error absoluto medio: en promedio, cuántos minutos nos equivocamos.

**PSI (Population Stability Index)** — Cuánto se movió una distribución numérica
respecto a la de referencia.

**Tamaño de efecto** — Cuánto cambió algo, a diferencia del p-valor, que solo dice qué
tan improbable es el azar. Con muchos datos, el p-valor alerta por diferencias
irrelevantes.

**V de Cramér** — El equivalente del PSI para variables categóricas, entre 0 y 1.
