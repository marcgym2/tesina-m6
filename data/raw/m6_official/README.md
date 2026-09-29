# Datos oficiales del M6 (snapshot congelado)

**Fuente:** [Mcompetitions/M6-methods](https://github.com/Mcompetitions/M6-methods), commit
`10c553f7a5ffbaf53971ca48ea982b2c0dd952ed`. Es el HEAD de `main` al 2026-09-28; el último push upstream fue el 2024-10-02.
**Descarga:** 2026-09-28 con `scripts/download_m6_official.py`.
**Hashes y procedencia:** `data/manifest.json` guarda, para cada archivo, dos SHA-256 (el del archivo upstream y el del archivo guardado) y el git blob SHA del upstream. Este último se puede verificar contra el árbol del commit.

**Licencia:** el repositorio upstream **no declara licencia**. Los archivos se conservan aquí solo para fines de investigación académica y reproducibilidad, con atribución a los organizadores del M6 (Makridakis et al.). El código oficial de evaluación no se copia a este repo: `src/tesina/evaluation/` lo reimplementa y cita su ruta y commit.

## Archivos

| Archivo | Upstream | Contenido |
|---|---|---|
| `assets_m6_2026-09-28.parquet` | `assets_m6.csv` | Precios de cierre ajustados diarios: `symbol`, `date` (`YYYY/MM/DD`), `price`. 100 activos, del 2022-01-31 al 2023-02-17, 273 fechas. |
| `submissions_2026-09-28.parquet` | `IJF paper/submissions.csv` | Submissions de los equipos: `Team`, `Submission`, `Evaluation`, `Symbol`, `Decision` (peso), `Rank1`–`Rank5` (probabilidad por quintil), `IsActive`, `RpsHashCode`, `IrHashCode`. 275,200 filas, 251 equipos. |
| `template_2026-09-28.parquet` | `template.csv` | Plantilla de submission: probabilidades uniformes (0.2) y pesos de 0.01. |
| `evaluation_example_2026-09-28.xlsx` | `Evaluation - example.xlsx` | Ejemplo oficial del cálculo de RPS e IR con la submission benchmark para Pilot y los meses 1–12, más un resumen trimestral y global. Incluye el calendario de cada periodo. |
| `summary_leaderboard_2026-09-28.xlsx` | `IJF paper/summary_leaderboard.xlsx` | Leaderboard oficial con RPS, IR y OR por equipo, por mes, trimestre y global. |

Los CSV se guardan como parquet con **todas las columnas como texto**, lo que hace la conversión sin pérdida (se verifica celda por celda al descargar). Las columnas se tipan en `tesina.data.m6`. Los `.xlsx` se guardan byte por byte.

## Observaciones

- `Evaluation` indica el mes en que se evaluó la submission. Si un equipo no reenvió, se evalúa su submission anterior (en 149,900 filas `Submission ≠ Evaluation`).
- En todas las submissions las probabilidades suman 1 y Σ|pesos| ∈ [0.25, 1].
- Hay 72 fechas con menos de 100 precios. Por ejemplo, en feriados de EE. UU. solo cotizan 10 activos. El código oficial rellena el precio faltante con el último disponible.
