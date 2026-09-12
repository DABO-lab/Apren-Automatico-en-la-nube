# Contrato de la API

Qué entra, qué sale y qué código de estado esperar en cada caso. El contrato real
vive en `src/trips/api/schemas.py` (Pydantic) — este documento es la versión legible
para quien va a consumir la API sin leer el código.

Base local: `http://127.0.0.1:8000`. Documentación interactiva generada por FastAPI:
`http://127.0.0.1:8000/docs`.

---

## `GET /health`

Señal de vida del proceso. Responde `200` **incluso si el modelo no cargó** — a
propósito: un servicio que no arranca no se puede diagnosticar, uno que arranca
degradado sí (ver `docs/riesgos.md`, riesgo 3).

```json
{
  "estado": "ok",
  "modelo_cargado": true,
  "version_modelo": "3"
}
```

`version_modelo` es `null` cuando `modelo_cargado` es `false` (MLflow no respondió al
arrancar, o no existe el alias `champion` todavía).

## `GET /modelo`

Qué modelo se está sirviendo exactamente, para quien opera el servicio o audita una
predicción. Responde `503` si no hay modelo cargado (mismo cuerpo de error que
`/predict`, ver abajo).

```json
{
  "nombre": "duracion-regressor",
  "version": "3",
  "uri": "models:/duracion-regressor@champion",
  "alias": "champion",
  "variables": ["distancia_km", "member_casual", "rideable_type", "hora", "dia_semana"],
  "objetivo": "log1p(duracion_min) — la respuesta va en minutos"
}
```

## `POST /predict`

Predice la duración de un viaje que **todavía no ha terminado**: solo pide lo que se
sabe al momento de sacar la bicicleta.

**Entrada** (`ViajeRequest`, `extra="forbid"` — un campo que no existe es error, no se
ignora en silencio):

| Campo | Tipo | Rango / valores | Por qué ese rango |
|---|---|---|---|
| `started_at` | datetime, sin zona horaria | — | El modelo aprendió con hora local; una zona horaria se rechaza en vez de convertirse en silencio |
| `start_lat` | float | `[40.65, 40.80]` | Caja de Jersey City y Hoboken (ver `docs/dataset-card.md`) |
| `start_lng` | float | `[-74.12, -73.95]` | Misma caja |
| `end_lat` | float | `[40.65, 40.80]` | Misma caja |
| `end_lng` | float | `[-74.12, -73.95]` | Misma caja |
| `member_casual` | string | `"member"` \| `"casual"` | Únicos valores que trae Citi Bike |
| `rideable_type` | string | `"classic_bike"` \| `"electric_bike"` | Únicos valores que trae Citi Bike |

Los rangos de coordenadas son **más estrechos** que los del contrato de datos
(`src/trips/data/contract.py`, `LAT_MIN/MAX` con holgura para el proveedor). Es a
propósito: la API valida contra el rango donde el modelo tiene evidencia real de
entrenamiento, no contra el rango, más ancho, que solo busca detectar que el proveedor
cambió el formato del archivo.

**Salida** (`200`, `PrediccionResponse`):

```json
{
  "duracion_min": 6.42,
  "distancia_km": 1.108,
  "modelo": "duracion-regressor",
  "version": "3"
}
```

**Errores:**

| Código | Cuándo | Cuerpo |
|---|---|---|
| `422` | El viaje no pasa la validación de Pydantic (coordenadas fuera de rango, tipo de bici inventado, campo desconocido, fecha con zona horaria) | El detalle estándar de FastAPI, campo por campo |
| `503` | No hay modelo cargado (MLflow no respondía al arrancar, o no existe el alias `champion`) | `{"detail": "El modelo no está disponible. Verifica que MLflow esté corriendo y que exista el alias 'champion'."}` |

## `POST /predict/batch`

Igual que `/predict`, pero para hasta 1000 viajes en una sola llamada — el modelo se
invoca una vez sobre todo el lote, no una vez por viaje.

**Entrada** (`LoteRequest`):

```json
{ "viajes": [ { "...": "un ViajeRequest" }, { "...": "otro" } ] }
```

**Salida** (`200`, `LoteResponse`):

```json
{ "predicciones": [ { "...": "un PrediccionResponse" }, { "...": "otro" } ] }
```

Si **cualquier** viaje del lote no pasa la validación, toda la petición se rechaza con
`422` — no hay resultados parciales. Es más simple de razonar para quien consume la
API: una respuesta `200` significa que todas las predicciones son válidas.

## `GET /metrics`

Métricas del **servicio**, en formato Prometheus (`text/plain`). No confundir con el
reporte de `drift` (`make drift`, `reports/drift.json`): `/metrics` mide si la API está
sana y qué está prediciendo; el reporte de `drift` mide si los *datos* de entrada
siguen pareciéndose a julio. Son preguntas distintas — ver el comentario junto a las
métricas en `src/trips/api/main.py` y `docs/politica-de-reentrenamiento.md`.

Expone, entre otras:

- `trips_predicciones_total{resultado="ok"|"error"}` — contador de peticiones.
- `trips_prediccion_latencia_segundos` — histograma de latencia de una predicción.
- `trips_prediccion_duracion_min` — histograma de las duraciones que el modelo está
  prediciendo. Si esta distribución se corre respecto a lo esperado (ver
  `docs/guia-del-proyecto.md`, sección 6.1), es una señal temprana de que algo cambió,
  incluso antes de correr el reporte de `drift` formal.

Un dashboard de referencia, versionado, está en
`observabilidad/grafana/dashboards/api-modelo.json`.

---

## Por qué el contrato no incluye `velocidad_kmh` ni ninguna variable calculada a partir
del destino

Todo lo que pide `ViajeRequest` es información que existe **antes** de que el viaje
termine. Cualquier campo calculado con `end_lat`/`end_lng` **y** la duración real sería
fuga de información — ver `docs/guia-del-proyecto.md`, sección 6.7, y
`docs/riesgos.md`, riesgo 4.
