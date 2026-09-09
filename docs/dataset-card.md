# Dataset card — viajes de Citi Bike (Jersey City y Hoboken, julio de 2026)

## Procedencia

**Fuente:** Citi Bike System Data, publicado por Lyft/Motivate (operador de
Citi Bike). Archivo `JC-202607-citibike-tripdata.csv`, correspondiente a los
viajes que empezaron o terminaron en estaciones de Jersey City y Hoboken en
julio de 2026.

**Descarga:** https://citibikenyc.com/system-data (los archivos mensuales por
ciudad se listan ahí; los de Jersey City/Hoboken llevan el prefijo `JC-`).

**Licencia:** [NYCBS Data Use Policy](https://www.citibikenyc.com/data-sharing-policy).
Puntos que importan para este proyecto:

- Está permitido reproducir, analizar y usar los datos como insumo de
  "análisis, reportes o estudios", incluso integrados en un producto propio
  (como la API de este repositorio). Lo que la política prohíbe explícitamente
  es "host, stream, publish, distribute, sublicense, or sell the Data as a
  stand-alone dataset" — es decir, no podemos redistribuir el CSV tal cual.
  Por eso `data/raw/` no se versiona (ver también la sección 1.5 del informe
  de estado): no es solo una decisión de tamaño, es una condición de la
  licencia.
- Prohíbe correlacionar los datos con nombres, direcciones o identidad de
  clientes — no aplica aquí, el dataset ya viene sin esa información (ver
  "Población representada" abajo).
- Los datos se entregan "AS IS", sin garantías, y con responsabilidad del
  proveedor limitada a USD 100. No hay SLA de calidad: las cuatro reglas de
  limpieza de `clean.py` existen justamente porque no se puede asumir que el
  archivo llega perfecto.

**No se versiona en este repositorio:** ni el CSV crudo, ni el parquet
procesado. Ambos se regeneran localmente (`make data`). El motivo es doble:
pesan demasiado para Git, y la licencia prohíbe redistribuirlos como dataset
independiente.

## Qué contiene

109.095 filas, 13 columnas, un viaje por fila. Después de limpiar (sección
6.2 del informe de estado): 108.487 filas (99,44 % del crudo).

| Columna | Unidad / tipo | Nulos | Por qué (si los hay) |
|---|---|---|---|
| `ride_id` | texto, identificador único | No | — |
| `rideable_type` | categórica: `classic_bike` / `electric_bike` | No | — |
| `started_at` | timestamp, hora local de Nueva Jersey | No | — |
| `ended_at` | timestamp, hora local de Nueva Jersey | No | — |
| `start_station_name`, `start_station_id` | texto | Sí (raro) | Estaciones temporales o retiradas sin catalogar |
| `end_station_name`, `end_station_id` | texto | Sí (0,3 % del crudo) | La bicicleta no se devolvió con normalidad; se elimina en la limpieza (regla 2) |
| `start_lat`, `start_lng`, `end_lat`, `end_lng` | grados decimales (WGS84) | Sí en destino cuando falta la estación | Misma causa que el nombre de estación |
| `member_casual` | categórica: `member` / `casual` | No | — |
| `duracion_min` (derivada) | minutos, `ended_at - started_at` | No | El archivo no la trae; se construye en `clean.py` |

**Estrategia de nulos, declarada:** los únicos nulos relevantes son los de
destino (estación y coordenadas de llegada). No se imputan: las filas se
eliminan (regla 2 de `clean.py`), porque no hay forma honesta de inventar
dónde terminó un viaje. `ViajesCrudos` (el contrato de entrada) los tolera
como nulos legítimos; `ViajesLimpios` (el contrato de salida) exige que ya
no existan — es la garantía de que la regla se aplicó.

## Población representada

Viajes de bicicleta pública en dos municipios de Nueva Jersey (Jersey City y
Hoboken) durante un solo mes (julio de 2026). **No representa:** viajes en
Manhattan/Brooklyn/Queens/Bronx (esos son archivos `JC-` vs los que empiezan
distinto en el mismo portal), otras estaciones de temporada, ni meses fuera
de julio. Un modelo entrenado aquí no debería usarse para predecir viajes en
otra ciudad o en invierno sin volver a evaluar drift (ver
`docs/politica-de-reentrenamiento.md`).

No hay datos personales: el dataset no identifica usuarios individuales, solo
el tipo de membresía (`member`/`casual`).

## Sesgos y limitaciones conocidas

- **Estacionalidad:** julio es verano en el hemisferio norte. La duración y el
  volumen de viajes en invierno son distintos; el modelo no ha visto esa
  distribución (sección 9.4 del informe: el chequeo de drift contra agosto
  real sigue pendiente).
- **Filtrado previo del proveedor:** Citi Bike ya descarta viajes de menos de
  60 segundos antes de publicar (sección 6.1 del informe: la duración mínima
  del crudo es exactamente 1,00 minuto y no hay filas duplicadas). El dataset
  no es una muestra cruda del sistema, es una muestra ya curada por el
  proveedor — el modelo hereda ese filtro implícitamente.
- **Desbalance conocido:** los usuarios `casual` son ~28 % del total; las
  interacciones que el modelo aprende para ese grupo se apoyan en menos datos
  que para `member` (72 %).

## Las tres formas de fuga de información, descartadas por escrito

1. **Variables derivadas del futuro:** `velocidad_kmh` (distancia entre
   duración) se calcula solo para el EDA, nunca entra al modelo — contiene la
   respuesta. Blindado con un test (`test_add_features_no_calcula_velocidad`).
2. **Partición temporal, no aleatoria:** el split train/test respeta el orden
   cronológico (sección 6.4 del informe). Una partición aleatoria dejaría que
   el modelo "viera" el futuro respecto a filas de prueba anteriores en el
   tiempo.
3. **El objetivo no se cuela como feature:** `duracion_min` no aparece entre
   `FEATURE_COLUMNS` (`src/trips/config.py`); las variables de entrada son
   solo las que se conocen **antes** de que el viaje termine (estación, hora,
   tipo de bici y de usuario, distancia en línea recta entre estaciones).
