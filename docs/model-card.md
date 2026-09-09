# Model card — duración de viajes de Citi Bike

> Generada a mano a partir de la última promoción conocida (versión 3,
> alias `champion`). A partir de ahora se regenera con `make model-card`
> (`scripts/model_card.py`), que la reescribe leyendo el `champion` vigente
> del registry — así el archivo nunca queda desactualizado respecto al
> modelo que realmente sirve la API.

## Qué hace el modelo

Predice cuántos minutos va a durar un viaje en bicicleta pública de Jersey
City/Hoboken, usando solo lo que se sabe **al empezar** el viaje: estación y
hora de salida, tipo de bicicleta, tipo de usuario y distancia en línea recta
hacia el destino declarado.

**No hace:** predecir la disponibilidad de bicicletas, recomendar rutas, ni
generalizar a otras ciudades o estaciones fuera de Jersey City/Hoboken.

## Detalles técnicos

| | |
|---|---|
| Familia | `HistGradientBoostingRegressor` (scikit-learn) dentro de un `Pipeline` con `ColumnTransformer` |
| Objetivo de entrenamiento | `log1p(duracion_min)` |
| Variables de entrada | `distancia_km` (numérica); `member_casual`, `rideable_type`, `hora`, `dia_semana` (categóricas, `OneHotEncoder`) |
| Preprocesamiento | Dentro del artefacto de MLflow (el mismo objeto `Pipeline` que se registra) — no hay un archivo de preprocesamiento aparte que mantener sincronizado a mano |
| Semilla | 42 (`RANDOM_SEED` en `src/trips/config.py`) |
| Partición | Temporal 80/20, corte en 2026-07-25 22:11 (86.789 filas entrenan, 21.698 evalúan) |
| Registrado como | `duracion-regressor` en el Model Registry de MLflow, por **alias** (`@candidate` / `@champion`), no por `stage` (la API de `stages` está deprecada desde MLflow 2.9) |

## Métricas (conjunto de prueba temporal, en minutos)

| Modelo | MAE | Error mediano | RMSE | R²(log) |
|---|---:|---:|---:|---:|
| Baseline (mediana) | 5.85 | 2.68 | — | −0.013 |
| Ridge | 4.79 | 1.86 | — | 0.300 |
| **HistGradientBoosting (champion)** | **4.06** | **1.33** | 24.43 | 0.530 |

La cifra que más importa para operar el servicio es el **error mediano**: la
mitad de las predicciones se equivocan por menos de 1.33 minutos. El RMSE se
reporta también, pero está secuestrado por la cola larga de viajes atípicos
(sección 6.6 del informe de estado) y no es la métrica de decisión.

No hay una desagregación por subgrupo (`member` vs `casual`, `classic_bike`
vs `electric_bike`) en esta versión de la `model card` — queda declarado como
pendiente, no omitido en silencio (ver `docs/riesgos.md`, riesgo de sesgo por
subgrupo).

## Cómo se decide promover un modelo

`scripts/promote.py` compara el candidato de la corrida más reciente contra
el `champion` vigente por MAE, y solo reemplaza el alias si el candidato
mejora por **al menos 2 %** (`MARGEN_DE_MEJORA` en `config.py`). Un empate no
promueve: ya ocurrió una vez (versión 4 empatada en MAE 4.055 con la versión
3 vigente) y la compuerta se negó con el mensaje "empate exacto: probablemente
el mismo modelo reentrenado, se queda el campeón vigente" — evidencia de que
el `gate` sí puede rechazar un candidato, no es un trámite que siempre aprueba.

## Limitaciones conocidas

- Entrenado con datos de un solo mes (julio de 2026) y dos municipios: no se
  ha validado contra otra estación del año ni otra ciudad (ver
  `docs/dataset-card.md`).
- `velocidad_kmh` se excluye deliberadamente por fuga de información — el
  modelo no "sabe" qué tan rápido va la bicicleta, solo la distancia en línea
  recta, así que subestima sistemáticamente viajes con rutas muy indirectas.
- No hay intervalos de predicción, solo un punto estimado.

## Cómo se sirve

`GET /modelo` en la API expone la versión exacta que está cargada; `GET
/health` confirma si el modelo cargó. El modelo se carga del registry por
alias al arrancar el proceso — cambiarlo en producción es mover el alias
`champion` y reiniciar la API, no reconstruir ni redeployar nada.
