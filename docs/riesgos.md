# Riesgos

Cinco riesgos concretos del sistema tal como está hoy, con cómo se detectaría
cada uno si ocurre (o por qué todavía no se puede detectar).

## 1. Estacionalidad: el modelo nunca vio un mes distinto a julio

**Qué pasa si ocurre:** a partir de agosto (otoño boreal, menos luz, quizás
menos ciclismo casual), las duraciones típicas cambian de forma que el
modelo no aprendió, y las predicciones se degradan en silencio porque nada
en el sistema compara julio contra agosto todavía.

**Detección:** hoy, ninguna — el chequeo de drift compara particiones dentro
del mismo julio (sección 9.4 del informe de estado, pendiente). En cuanto
exista el archivo de agosto, `make drift --actual data/processed/agosto_limpio.parquet`
lo detectaría si el movimiento supera el umbral calibrado.

**Mitigación mientras tanto:** el umbral de la partición temporal actual ya
alertó sobre `dia_semana` por una razón entendida (sección 6.9 del informe:
los últimos 6 días de julio no cubren la semana completa), lo que confirma
que el chequeo sí es sensible a cambios reales de composición temporal —
solo falta el dato de un mes distinto para probarlo entre meses de verdad.

## 2. Sesgo por subgrupo sin desagregar

**Qué pasa si ocurre:** el MAE global (4.06 min) puede esconder que el
modelo predice peor para un subgrupo -por ejemplo, viajes `casual` en
`electric_bike`, que el EDA ya señaló como el grupo con la interacción más
fuerte (sección 6.6 del informe: la eléctrica recorta la mediana de 11.0 a
7.6 minutos para casuales, de 5.9 a 5.7 para miembros). Si ese subgrupo
tiene menos datos, el modelo podría ajustarse peor ahí sin que el MAE
agregado lo muestre.

**Detección:** ninguna hoy — `evaluar()` en `src/trips/models/train.py`
calcula las métricas sobre todo el conjunto de prueba, no por subgrupo.

**Mitigación propuesta, no implementada:** desagregar `evaluar()` por
`member_casual` × `rideable_type` (4 combinaciones) y registrar esas
métricas también en MLflow como tags o métricas con sufijo. Es la brecha más
barata de cerrar de esta lista si sobra tiempo.

## 3. Dependencia de servicios externos corriendo en la máquina local

**Qué pasa si ocurre:** la API arranca "degradada" si MLflow no responde
(`lifespan` en `api/main.py` captura la excepción y sigue sin modelo,
devolviendo 503 en `/predict`), lo cual es la decisión correcta, pero
significa que un olvido operativo (alguien cierra la Terminal 1 sin querer)
tumba las predicciones sin que nadie lo note hasta que un cliente se queja.

**Detección:** `GET /health` distingue "el proceso vive" de "el modelo está
servido" (`modelo_cargado: bool`), así que un chequeo externo periódico a
`/health` sí lo detectaría — pero hoy nada corre ese chequeo automáticamente
fuera de Docker (`HEALTHCHECK` del Dockerfile solo actúa dentro del
contenedor).

**Mitigación:** documentado como limitación; fuera del contenedor, correr la
API bajo un supervisor de procesos (o el `HEALTHCHECK` de `docker compose`)
sería el siguiente paso.

## 4. Reentrenamiento con datos que pasan el contrato pero tienen un error sistemático

**Qué pasa si ocurre:** `ViajesCrudos` y `ViajesLimpios` atrapan filas
inválidas y archivos truncados (sección 6.8 del informe), pero no atrapan un
error sistemático que sea internamente consistente -por ejemplo, si Citi
Bike cambiara la zona horaria de `started_at`/`ended_at` sin avisar, cada
fila seguiría siendo válida por separado (tipos correctos, rangos correctos,
`ended_at > started_at`), y el modelo se reentrenaría con horas desplazadas
sin que ningún `check` actual lo note.

**Detección parcial:** el chequeo de drift sobre `hora` sí se movería si el
desplazamiento es de varias horas, pero solo se ejecuta si alguien corre
`make flow` o `make drift` después del cambio, no antes de aceptar los datos
nuevos.

**Mitigación propuesta:** agregar una regla de contrato entre columnas que
compare la distribución de `hora` del archivo nuevo contra un rango esperado
conocido (por ejemplo, que la moda de viajes esté en horas pico razonables),
en vez de depender solo del chequeo de drift posterior al entrenamiento.

## 5. Secreto o credencial expuesta en el repositorio

**Qué pasa si ocurre:** es la única falla de la rúbrica que resta puntos de
forma no recuperable (−15, y no se arregla borrando el archivo en el
siguiente commit: el secreto queda en el historial de git y hay que rotar la
credencial). Este proyecto no usa credenciales de servicios en la nube hoy
(MLflow y Prefect corren local, sin autenticación), pero la variable de
entorno `MLFLOW_TRACKING_URI` sí podría apuntar a un servidor remoto con
credenciales embebidas si alguien la exportara mal en el futuro.

**Detección:** desde el PR #16, `gitleaks` corre como hook de
`.pre-commit-config.yaml` — en cada commit local, y también en CI dentro del
paso `uv run pre-commit run --all-files` de `.github/workflows/ci.yml`. Lo que
sigue sin existir es un chequeo retroactivo del historial ya escrito: un
secreto que ya estuviera en un commit viejo (de antes del PR #16) no lo
detecta un hook que solo mira el commit que se está creando.

**Mitigación:** si alguna vez se sospecha que algo se coló antes de tener el
hook, correr `gitleaks detect` (sin `--staged`, sobre todo el historial) es
el siguiente paso — no está automatizado todavía.
