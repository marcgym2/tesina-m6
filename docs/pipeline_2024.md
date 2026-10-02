# El pipeline de la tesina 2024: qué hacía y qué sesgos tenía

Insumo para el #24 (pipeline ingenuo) y el #25 (cascada de sesgos, RQ4). Fuentes:
`thesis/legacy/tesina_2024.docx` (cap. 6) y el código del autor en
[marcgym2/refactor_r](https://github.com/marcgym2/refactor_r):

- versión R en el commit `a81d3ff` (2026-02-12): `03_FeatureEngineering.R`, `04_Train_Quantile_Models.R` y helpers;
- versión Python en `03ee892`: `pipeline/train.py`, `training_utils.py` y `features.py`.

## Qué hacía

| Paso | Tesina 2024 (docx) | Código (R `a81d3ff` / Python `03ee892`) |
|---|---|---|
| Universo | 32 acciones de semiconductores (holdings de SOXX), 2004–2024 | ETFs sectoriales (R); `mags7`, `m6` y otros (Python). En el modo `m6` se reemplaza DRE→PLD, RE→EG y WRK→SW |
| Datos | Yahoo (quantmod): OHLCV ajustado | Igual |
| Huecos | Interpolación con ruido aleatorio | `noisyInterpolation` (R) |
| Intervalos | — | Malla de 28 días con **4 desplazamientos** (`shifts = 0, 7, 14, 21` días) |
| Features | Retornos y volatilidad con rezagos 1–7, IsETF, 49 indicadores técnicos | Igual. Se agregan por intervalo y se rezagan 1 intervalo |
| Objetivo | Quintil del retorno futuro | Quintil del retorno **del intervalo**, transversal por intervalo |
| Imputación | Mediana | **Mediana de todo el dataset** (train + test + validación) |
| Estandarización | Media 0, sd 1 | Por intervalo, transversal, sin fuga |
| Split | 80 / 10 / 10 | **Temporal** por intervalos (no aleatorio) |
| Modelos | FFNN (32-8-5) + meta-modelo por ticker | Igual |
| Selección | — | Base: early stopping en test. **Meta: early stopping en validación, y la pérdida reportada es la de esa misma validación** |
| Ajuste de hiperparámetros | — | 12 commits `exp:` del 2026-03-25 que ajustan el meta-modelo (dropout, paciencia, capas, inicialización) mirando la pérdida de validación |
| Costos | — | No se modelan |

## Sesgos identificados (candidatos para la cascada del #25)

1. **Imputación global:** la mediana usa observaciones de test y validación. Probablemente el efecto es pequeño, pero es fuga.
2. **Selección sobre el conjunto que se reporta:** el meta-modelo se detiene (early stopping) con el conjunto de validación y luego se reporta la pérdida en ese mismo conjunto.
3. **Búsqueda de configuraciones no reportada:** las variantes `exp:` se eligieron mirando la validación. Es sobreajuste a la validación por búsqueda.
4. **Etiquetas traslapadas sin purga ni embargo:** con 4 mallas desplazadas 7 días, intervalos de train y de test se traslapan hasta 21 días alrededor de cada frontera.
5. **Universo elegido después de los hechos:** los holdings de SOXX en 2024 o las "mags7" son empresas que ya sabemos que les fue bien. En el modo `m6`, los deslistados se sustituyen por sus sucesores.
6. **Sin costos de transacción.**
7. **Interpolación con ruido aleatorio:** introduce aleatoriedad no controlada por semilla en los datos de entrada.

Lo que **no** tenía el código: split aleatorio, estandarización global y quintiles agrupando periodos (rule 3).

## Implicaciones de datos
El pipeline necesita OHLCV y varios años de historia (7 rezagos de 28 días más indicadores de hasta 100 días). Los datos oficiales del M6 (solo cierre ajustado, 13 meses) no alcanzan, así que el #24 depende del snapshot del #12.
