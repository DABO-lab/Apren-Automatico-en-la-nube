# Informe de estado y guía de continuación

**Proyecto:** Predicción de la duración de viajes en bicicleta pública (Citi Bike)
**Repositorio:** https://github.com/DABO-lab/Apren-Automatico-en-la-nube
**Fecha:** 9 de septiembre de 2026
**Curso:** Aprendizaje Automático en la nube — Especialización en Ciencia de Datos e
Inteligencia Artificial, Universidad de Medellín
**Equipo:** Bueno Osorno Dubian Andrés · Ceballos Bedoya Catherine ·
Rivera Guzmán Yesenia · Salazar Seguro María Jimena

> **Para qué sirve este documento.** Para tomar el proyecto donde está y continuar sin
> depender de quien lo hizo. Tiene tres partes: **cómo montarlo desde cero** (sección
> 1), **qué hay y por qué está así** (secciones 2 a 7) y **qué falta** (sección 9).
>
> También sirve como contexto para un asistente de IA: es markdown plano, se copia
> completo y trae los números y las decisiones.

---

## 1. Arrancar desde cero

### 1.1 Lo que necesitas instalado

Abre **PowerShell** (tecla Windows → "PowerShell") y verifica:

```powershell
git --version
code --version
uv --version
docker --version
```

Lo que falte:

```powershell
winget install Git.Git
winget install Microsoft.VisualStudioCode
winget install astral-sh.uv
winget install Docker.DockerDesktop
```

**Cierra y vuelve a abrir PowerShell** después de instalar algo, o los comandos nuevos
no aparecen. Docker pide reiniciar el equipo: hazlo.

No necesitas instalar Python — `uv` baja la versión que el proyecto pide (3.11).

Preséntate ante git, una sola vez por computador:

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu@correo.com"
```

### 1.2 Clonar el repositorio

```powershell
cd $HOME\Documents
git clone https://github.com/DABO-lab/Apren-Automatico-en-la-nube.git
cd Apren-Automatico-en-la-nube
code .
```

VS Code te va a sugerir extensiones: **acepta Python y Jupyter** (las de Microsoft).

### 1.3 Crear tu rama

**Nunca trabajes directo sobre `main`.** Cada quien en la suya, y el trabajo entra por
pull request:

```powershell
git switch main
git pull
git switch -c feature/lo-que-vas-a-hacer
```

El orden importa: si creas la rama sin haber hecho `pull`, arrancas desde una versión
vieja y después toca reconciliar.

### 1.4 Montar el entorno

```powershell
uv sync
uv run pre-commit install
```

`uv sync` crea el `.venv` con **las versiones exactas** que usamos las demás (fijadas
en `uv.lock`). Eso es lo que garantiza que a todas nos funcione igual.

En VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter** → el que diga `.venv` y
`3.11`. Sin esto, VS Code usa otro Python y nada funciona.

### 1.5 Conseguir los datos

**El CSV crudo no está en el repositorio** (pesa demasiado y los datos crudos no se
versionan). Pídele a Dubian el archivo `JC-202607-citibike-tripdata.csv` y déjalo en
`data/raw/`.

Si prefieres tenerlo en otra carpeta, define la variable de entorno:

```powershell
[Environment]::SetEnvironmentVariable("TRIPS_RAW_DATA", "C:\ruta\a\tu\archivo.csv", "User")
```

(Con esta opción hay que cerrar y reabrir PowerShell y VS Code.)

### 1.6 Comprobar que todo funciona

```powershell
uv run pytest
```

Deben pasar **43 pruebas**. Si pasan, tu entorno está bien montado y puedes seguir con
la sección 4.

---

## 2. El problema

**Predecir cuántos minutos va a durar un viaje en bicicleta pública**, con lo que se
sabe cuando el viaje empieza: de dónde sale, a dónde va, a qué hora, qué tipo de
bicicleta y qué tipo de usuario.

Datos: los viajes publicados por Citi Bike para Jersey City y Hoboken en julio de 2026
— **109.095 viajes, 13 columnas**. El archivo **no trae la duración**: se construye
restando las marcas de tiempo. Lo mismo la distancia, la hora y el día de la semana.

Es un problema de **regresión**: la variable a predecir es continua.

---

## 3. Dónde estamos

**El proyecto está completo de punta a punta y cubre las siete dimensiones de la
rúbrica.** Hoy funciona: cargar el CSV, validarlo contra un contrato, limpiarlo,
construir variables, entrenar y comparar tres modelos, registrarlos con versión,
proponer un candidato, decidir con una compuerta si entra a producción, servirlo por
una API REST dentro de un contenedor, medir si los datos nuevos se parecen a los de
entrenamiento, y orquestar todo con caché.

| Dimensión | Peso | Estado | Dónde vive |
|---|---:|---|---|
| Reproducibilidad | 15% | ✅ | `uv.lock`, `Makefile`, `docs/` |
| Datos | 15% | ✅ | `data/contract.py` + fixtures rotos |
| Tracking y registry | 15% | ✅ | `models/train.py`, MLflow, alias |
| Pipeline | 15% | ✅ | `flows/training.py` (Prefect) |
| Deployment | 15% | ✅ | `api/`, `Dockerfile` |
| Monitoreo | 15% | ✅ | `monitoring/`, umbral calibrado |
| Ingeniería y documentación | 10% | ✅ | 43 pruebas, `docs/`, README |

Lo que queda es refinamiento, no construcción (sección 9).

---

## 4. Mapa del repositorio

```
data/raw/              el CSV crudo (no se versiona)
data/processed/        viajes_limpio.parquet (no se versiona, se regenera)
notebooks/
  01-carga-y-limpieza.ipynb   qué problemas tenían los datos
  02-eda.ipynb                qué explica la duración
src/trips/
  config.py            ÚNICA fuente de verdad: rutas, semilla, columnas,
                       umbrales, alias y política de promoción
  data/load.py         lee el CSV, declara tipos, valida el contrato de entrada
  data/clean.py        construye duracion_min y aplica 4 reglas de limpieza
  data/contract.py     los dos contratos de datos (Pandera)
  features.py          variables derivadas: hora, día, fin de semana, distancia
  models/train.py      entrena, evalúa, registra versiones, marca el candidato
  api/schemas.py       el contrato de la API (Pydantic)
  api/modelo.py        carga el modelo del registry por alias
  api/main.py          los endpoints
  monitoring/estadistico.py   PSI, KS, chi²/V de Cramér, Jensen-Shannon
  monitoring/check_drift.py   el chequeo, con umbral calibrado y códigos de salida
  flows/training.py    el pipeline orquestado con Prefect
scripts/promote.py     la compuerta de promoción a producción
tests/                 43 pruebas
docs/                  este informe, la guía de arranque y la guía de estudio
Dockerfile             imagen de la API: dos etapas, sin root, con healthcheck
Makefile               todos los comandos del proyecto
```

**Tres principios explican esta estructura.** Respétalos al agregar cosas:

1. **Los notebooks explican, el paquete ejecuta.** El notebook 02 no reimplementa la
   limpieza: importa `clean_trips` del paquete. Cuando la lógica vive en dos lados,
   tarde o temprano se desincroniza y nadie se entera.
2. **`config.py` es la única fuente de verdad.** Cualquier ruta, umbral o nombre de
   columna nuevo va ahí, no incrustado donde se usa.
3. **`data/raw/` es intocable.** Todo lo que se arregla se escribe en
   `data/processed/`. Siempre se puede volver al punto de partida.

---

## 5. Cómo correr el proyecto completo

Necesitas **tres terminales**, porque dos comandos quedan ocupando la suya.

### Terminal 1 — MLflow (déjala abierta)

```powershell
uv run python -m mlflow server --backend-store-uri sqlite:///mlflow.db --host 0.0.0.0 --port 5001 --workers 1 --allowed-hosts "localhost:5001,127.0.0.1:5001,host.docker.internal:5001"
```

Interfaz: http://127.0.0.1:5001

> `--host 0.0.0.0` no es capricho: con `127.0.0.1` el contenedor de la API no puede
> alcanzarlo, porque para él nuestra máquina es otro equipo de la red.
> `--workers 1` evita un error de Windows (`WinError 10022`) cuando varios procesos
> comparten el mismo socket.

### Terminal 2 — Prefect (déjala abierta)

```powershell
uv run prefect server start
```

Tablero: http://127.0.0.1:4200 — ahí se ve el grafo de tareas, los tiempos y cuáles
salieron de caché.

Y **una sola vez**, para que el cliente use este servidor:

```powershell
uv run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

> Sin esto, Prefect levanta un servidor temporal en cada corrida, y en Windows falla de
> forma intermitente con `httpx.ConnectTimeout`.

### Terminal 3 — el trabajo

```powershell
uv run python -m trips.flows.training     # el pipeline completo
uv run python scripts/promote.py          # la compuerta de promoción
uv run uvicorn trips.api.main:app --port 8000   # la API
```

Corre el flujo **dos veces seguidas**: la segunda pasa de ~40 segundos a ~3, con las
cinco tareas en estado `Cached`. Esa es la evidencia del caché que pide la rúbrica.

La API queda en http://127.0.0.1:8000/docs, con la documentación interactiva.

### En contenedor

```powershell
docker build -t trips-api .
docker run --rm -p 8000:8000 --add-host=host.docker.internal:host-gateway trips-api
```

### Todos los comandos

| Comando | Qué hace |
|---|---|
| `make setup` | dependencias + hook de estilo |
| `make data` | CSV crudo → parquet limpio (con los dos contratos) |
| `make features` | resumen de las variables derivadas |
| `make mlflow` | servidor de MLflow |
| `make prefect-ui` | servidor y tablero de Prefect |
| `make flow` | el pipeline orquestado completo |
| `make train` | solo el entrenamiento (sin orquestar) |
| `make promote` | la compuerta de promoción |
| `make api` | la API |
| `make docker-build` / `make docker-run` | imagen y contenedor |
| `make drift` | chequeo de drift |
| `make test` | las 43 pruebas |
| `make lint` | ruff |
| `make notebook` | Jupyter Lab |

---

## 6. Las decisiones, y por qué

Esta es la sección que hay que leer **antes de cambiar algo**. Ninguno de estos números
se eligió a ojo.

### 6.1 Los datos vienen pre-filtrados por Citi Bike

Dos evidencias: **cero filas duplicadas** en 109 mil registros, y la duración mínima es
**exactamente 1,00 minutos**. Un piso así de limpio no ocurre en datos capturados de
verdad: Citi Bike descarta los viajes de menos de 60 segundos antes de publicar.

Consecuencia: no hay paso de "eliminar duplicados", y los problemas no están en el piso
de la distribución sino en el techo.

### 6.2 Las cuatro reglas de limpieza

| Paso | Qué hace | Filas | Por qué |
|---|---|---:|---|
| 1 | construye `duracion_min` | — | el archivo no la trae |
| 2 | elimina viajes sin destino | 330 | no sabemos dónde terminaron |
| 3 | elimina duraciones > 24 h | 0 | una bici más de un día fuera no volvió |
| 4 | elimina falsos viajes | 278 | misma estación y menos de 2 minutos |

Quedan **108.487 viajes (99,44%)**.

Dos detalles que valen oro en la sustentación:

- **Los 44 viajes de más de 24 horas estaban todos dentro de las 330 sin destino.** Por
  eso el paso 3 elimina cero filas hoy. Es la misma anomalía vista por dos lados: una
  bicicleta que no se devolvió bien no tiene estación de llegada *y* acumula una
  duración absurda. La regla se dejó como **barrera** para datos futuros.
- **La regla 4 necesita las dos condiciones juntas.** Hay 4.480 viajes que vuelven a la
  estación de origen y la mayoría son paseos reales. Solo 278 duran menos de dos
  minutos, y esos sí son "saqué la bici, estaba dañada, la devolví".

### 6.3 Se modela el logaritmo de la duración

| Medida | Valor | Una normal tiene |
|---|---|---|
| Asimetría | 31,6 | 0 |
| Curtosis | 1.515 | 3 |
| Asimetría de `log(1+duración)` | 1,02 | — |

Sin transformar, un solo viaje de 1.300 minutos pesa más en el entrenamiento que
cientos de viajes normales. **Las métricas se reportan en minutos**, deshaciendo la
transformación: nadie entiende "0,42 de error logarítmico".

### 6.4 La partición es temporal, no aleatoria

Se ordena por fecha y el 20% más reciente queda para prueba (corte: 25 de julio 22:11
→ 86.789 entrenan, 21.698 evalúan). Una partición aleatoria permitiría entrenar con
viajes del 31 de julio para predecir viajes del 3: hacer trampa con el tiempo.

Las métricas salen peores que con partición aleatoria, y eso es correcto.

### 6.5 `velocidad_kmh` no entra al modelo — fuga de información

Se calcula dividiendo distancia entre duración: **contiene la respuesta**. Un modelo
que la reciba tendrá un desempeño espectacular en pruebas y será inútil el día que haya
que predecir un viaje que todavía no terminó.

Está blindado con una prueba (`test_add_features_no_calcula_velocidad`) para que nadie
la agregue al paquete "porque es útil".

### 6.6 El modelo elegido

| Modelo | MAE | Error mediano | R²(log) |
|---|---|---|---|
| **HistGradientBoosting** | **4,06 min** | **1,33 min** | **0,530** |
| Ridge | 4,79 | 1,86 | 0,300 |
| Baseline (mediana) | 5,85 | 2,68 | −0,013 |

**El baseline existe para que los otros números signifiquen algo.** Un modelo que
siempre predice la mediana es la vara de medir: el que no le gane no aporta información.

**El salto de R² entre Ridge y árboles (0,30 → 0,53) con las mismas variables** se
explica por una interacción del EDA: para un usuario casual, la bicicleta eléctrica
recorta la mediana de 11,0 a 7,6 minutos; para un miembro, de 5,9 a 5,7. Un modelo
lineal no ve esa interacción a menos que se la escriban; los árboles la encuentran
solos. **El EDA lo predijo y el entrenamiento lo confirmó.**

**Cuidado con el RMSE**: bajó apenas 4% (25,40 → 24,43) mientras el error mediano se
redujo a la mitad. El RMSE eleva los errores al cuadrado y queda secuestrado por la
cola. La cifra para contar es: **la mitad de los viajes se predicen con menos de 1,33
minutos de error**.

### 6.7 Entrenar y promover son cosas distintas

El pipeline marca el mejor modelo como **`candidate`**. La promoción a **`champion`**
—el alias que sirve la API— la hace `scripts/promote.py`, y solo si el candidato mejora
el MAE del campeón **en al menos 2%**.

Un pipeline que se autopromueve no tiene control de calidad: el día que los datos
lleguen mal, el modelo malo entra a producción solo. Empatar tampoco basta, porque
cambiar el modelo en producción tiene un costo.

**Ya lo vimos funcionar:** el flujo propuso la versión 4 con MAE 4,055 y el campeón era
la versión 3 con el mismo 4,055 — el mismo modelo reentrenado. La compuerta lo rechazó
con el mensaje *"empate exacto: probablemente el mismo modelo reentrenado, se queda el
campeón vigente"*. Sin compuerta, habríamos reemplazado un modelo en producción por una
copia idéntica: todo el riesgo, cero beneficio.

Para cambiar el modelo en producción no se reconstruye nada: se mueve el alias y se
reinicia la API.

### 6.8 Los contratos de datos

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

Las pruebas verifican **las dos direcciones**: siete degradaciones reales deben fallar y
tres lotes válidos independientes deben pasar (**control negativo**). Sin el control
negativo, un contrato que rechace absolutamente todo pasaría los tests igual — y
bloquearía el pipeline con datos buenos, que es un fallo peor porque parece que funciona.

### 6.9 El umbral de drift está calibrado, no inventado

Con 108 mil filas **el p-valor deja de servir**. Lo medimos: partiendo la referencia en
dos mitades aleatorias treinta veces —donde por construcción no hay drift— el **7% de
las comparaciones ya daba p < 0,05**.

Por eso la decisión se toma con **tamaño de efecto**, y el umbral sale de esa misma
línea base nula: el ruido del PSI es 0,0009, así que alertar en 0,10 es hacerlo a **cien
veces el ruido de fondo**.

El resultado real de julio:

```
Con p < 0,05 se habrían alertado 6 de 6 columnas.
Con tamaño de efecto: 1 de 6 (17%), por debajo del umbral del 30%.
```

La única que se movió es `dia_semana` (V de Cramér = 0,186), y tiene explicación: los
últimos seis días de julio no cubren la semana completa. Es drift real causado por
nuestra partición temporal.

El informe JSON incluye a propósito el campo `p_valor_diria_drift`, para dejar esa
diferencia a la vista.

### 6.10 El caché del pipeline, medido

```
Primera corrida:  ~40 s
Segunda corrida:   ~3 s   (las cinco tareas en estado Cached)
```

La política es `INPUTS + TASK_SOURCE`: el caché se invalida si cambian los datos **o el
código de la tarea**. Si alguien modifica una regla de limpieza, el resultado viejo deja
de valer aunque el CSV sea el mismo.

> **Una trampa que ya nos costó:** en la primera versión, la tarea de entrenamiento
> recibía el identificador de la corrida de Prefect como argumento. Como ese
> identificador cambia cada vez, la clave de caché nunca coincidía y el modelo se
> reentrenaba siempre — **el caché existía pero no servía para nada**. Se arregló
> leyéndolo del contexto en vez de recibirlo. Sin medir los dos tiempos, eso pasa
> desapercibido.

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
| Caché del pipeline | ~40 s → ~3 s |

---

## 8. Cómo trabajamos con git

1. **`main` no se toca directo.** Todo entra por rama y pull request.
2. **Una rama por entrega**, con nombre `tipo/descripcion-corta`: `feature/ci-cd`,
   `fix/umbral-drift`, `docs/glosario`.
3. La rama **nace de `main` actualizado**, vive lo que dura el PR y **se borra tras el
   merge**. Reusar una rama indefinidamente es lo que produce conflictos en cada entrega.

```powershell
git switch main
git pull
git switch -c feature/lo-que-sigue
# ... trabajo ...
git add .
git commit -m "feat: descripción de lo que hiciste"
git push -u origin feature/lo-que-sigue
```

Prefijos: `feat:` algo nuevo · `fix:` corrección · `docs:` documentación ·
`chore:` mantenimiento.

**Cosas que ya nos pasaron:**

- **El hook aborta el primer commit casi siempre.** Ruff reformatea y rechaza; se
  repite `git add .` y `git commit`, y entra. No es un error, es el hook trabajando.
- **Conflictos en el README**, tres veces, siempre por dos ramas editando el mismo
  archivo. Se resuelven trayendo `main` a la rama (`git merge origin/main`).
- **Un notebook, una persona a la vez.** Los `.ipynb` no se fusionan solos: si dos
  personas editan el mismo, alguien pierde su trabajo. Avisen por el grupo.
- **`git commit` commitea todo lo que esté en el índice**, no solo el último archivo
  agregado. Revisen `git status` antes de confirmar.

---

## 9. Lo que falta, por orden de rendimiento

### 9.1 CI/CD con GitHub Actions — lo más valioso que queda

La rúbrica pide, para el nivel máximo, *"CI completo con gate de promoción"*. La
compuerta ya existe (`scripts/promote.py`); falta el flujo de GitHub Actions que:

- en cada pull request corra `make lint` y `make test`;
- en `main` corra el pipeline y llame a la compuerta.

**Ojo con una penalización específica**: usar `|| true` en un paso de CI resta 5 puntos.
Es la trampa de hacer que el CI "pase siempre".

Esfuerzo: una sesión.

### 9.2 Llegar a 20 corridas en MLflow

El nivel 5 de tracking pide **≥20 runs con aliases**. Hoy hay 4 más las de drift. Sale
casi gratis ampliando la lista `CONFIGS` en `src/trips/models/train.py` con más
combinaciones de hiperparámetros: el flujo las entrena en paralelo y las registra todas.

Esfuerzo: media hora, más cómputo.

### 9.3 Limpiar las salidas de los notebooks

Los notebooks se commitean con sus figuras dentro. La rúbrica lo penaliza con **−3
décimas** porque hace los diffs ilegibles. Se arregla con un hook que las limpie.

**Es una decisión del equipo**: sin salidas, el profesor tendría que ejecutarlos para
ver las gráficas. El argumento a favor de limpiarlas es que `docs/guia-del-proyecto.md`
ya cuenta todos los hallazgos con sus números.

### 9.4 Drift contra agosto de verdad

Hoy el chequeo compara los últimos días de julio contra los primeros. Cuando Citi Bike
publique agosto:

```powershell
uv run python -m trips.monitoring.check_drift --referencia data/processed/viajes_limpio.parquet --actual data/processed/agosto_limpio.parquet
```

Ahí se vería drift real entre meses, mucho más interesante que el artefacto de la
partición.

### 9.5 Despliegue en la nube (opcional)

La rúbrica dice explícitamente que un despliegue local bien hecho vale igual que uno en
la nube. Con la imagen ya construida, subirla es más trámite que reto.

---

## 10. Tropiezos conocidos del entorno (Windows)

| Síntoma | Solución |
|---|---|
| `DLL load failed ... Control de aplicaciones bloqueó este archivo` al importar pandas | `Get-ChildItem .venv -Recurse -Include *.pyd,*.dll \| Unblock-File` |
| Lo mismo al abrir `jupyter lab` | No se arregla igual (bloquea el ejecutable): usar `uv run python -m jupyterlab` o trabajar en VS Code |
| `Docker Desktop is unable to start` | `wsl --update` como administrador y **reiniciar el equipo** |
| `port is already allocated` al correr el contenedor | Queda uno anterior vivo: `docker ps` y `docker stop <nombre>` |
| El flujo falla con `httpx.ConnectTimeout` | El servidor efímero de Prefect no alcanza a levantar: usar uno fijo (`prefect server start` + `prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api`) |
| El flujo reintenta contra `127.0.0.1:5001` y falla | MLflow no está corriendo: es la terminal 1 |
| MLflow arranca con muchos errores `WinError 10022` | Agregar `--workers 1` |
| PowerShell expande `"*"` como nombres de archivo | Nunca pasar `--allowed-hosts "*"`; nombrar los hosts explícitamente |
| `Deletion of directory failed` al cambiar de rama | Cerrar VS Code; o `git fetch origin main:main` para actualizar sin checkout |
| `Another git process seems to be running` | Borrar `.git\index.lock` |

**Sobre versiones:** MLflow 3 exige `pandas<3`. El proyecto usa pandas 2.3.3 con mlflow
3.15.2, las mismas versiones del repositorio del profesor. Si alguien sube pandas a la
serie 3, MLflow deja de instalarse y `uv` retrocede hasta una versión de 2022 que ya no
funciona con el protobuf moderno.

---

## 11. Glosario

**Alias (`champion` / `candidate`)** — Etiqueta movible que apunta a una versión del
modelo. Cambiar el modelo en producción es mover el alias, no reconstruir nada.

**Asimetría (skew)** — Qué tan inclinada está una distribución. Cero es simétrica. La
nuestra: 31,6.

**Caché de tarea** — Prefect guarda el resultado de cada paso y no lo recalcula si sus
entradas (y su código) no cambiaron.

**Contrato de datos** — Declaración de qué forma deben tener los datos, verificada
automáticamente al cargarlos y al procesarlos.

**Drift** — Que los datos nuevos ya no se parecen a aquellos con los que se entrenó.

**Fuga de información (data leakage)** — Cuando una variable contiene, directa o
indirectamente, la respuesta. Produce resultados excelentes en pruebas y modelos
inútiles en producción.

**Haversine** — Fórmula para la distancia entre dos puntos sobre una esfera, a partir de
sus coordenadas.

**Interacción** — Cuando el efecto de una variable depende del valor de otra. Los
árboles las capturan solas; los modelos lineales necesitan que se las escriban.

**MAE** — Error absoluto medio: en promedio, cuántos minutos nos equivocamos.

**PSI (Population Stability Index)** — Cuánto se movió una distribución numérica
respecto a la de referencia.

**Tamaño de efecto** — Cuánto cambió algo, a diferencia del p-valor, que solo dice qué
tan improbable es el azar. Con muchos datos, el p-valor alerta por diferencias
irrelevantes.

**V de Cramér** — El equivalente del PSI para variables categóricas, entre 0 y 1.

---

## 12. Los otros documentos

- **`docs/como-empezar.md`** — la guía de arranque en más detalle, paso a paso.
- **`docs/guia-del-proyecto.md`** — la guía de estudio del análisis: qué encontramos en
  los datos y por qué cada decisión de limpieza y modelado.
- **`README.md`** — la entrada del repositorio, con la estructura y los comandos.
