# Hallazgos sobre la evaluación oficial del M6 (periodo 1)

Notas de trabajo para los capítulos 6 y 7. Cada hallazgo indica su evidencia en el repo. Los números provienen de `results/m6_leaderboard/2026-09-29_4de5c39/checks.json` y de los tests; no se escriben a mano en la tesina.

1. **Los scripts oficiales en R y en Python no son equivalentes** (`RPS and IR calculation.R` / `.py`, commit upstream `10c553f`).
   - Cuando un empate de rendimientos cruza la frontera entre dos quintiles, el Python lo asigna a un solo quintil (`elif`), y el objetivo deja de sumar 1.
   - El R solo rellena precios dentro de la ventana; el Python rellena con todo el historial.
   - Se implementó la regla del R para los empates y la del Python para el relleno, que es la que reproduce el leaderboard. Ver `src/tesina/evaluation/rps.py` y `prices.py`.
2. **DRE, un activo deslistado, se evaluó con su último precio.** Su último precio es del 2022-11-28. El script del paper (`Baseline for evaluating the hypotheses.R`, bloque "Handle DRE") lo agrega explícitamente cuando la ventana tiene 99 activos. En M11 y M12, DRE tiene rendimiento y varianza cero.
3. **Un equipo destacado usó a DRE como efectivo sin riesgo.** En M10–M12, el equipo `bc4b0314` (MarcoGorelli, *wound-ignite*) puso el 100% del peso en DRE. El IR queda 0/0: el código publicado da NaN y el leaderboard publica 1.0. Esa regla no está en el código. Decisión D1: se reportan ambos criterios.
4. **Reglas del ranking oficial**, que no están documentadas y se infirieron hasta reproducir el 100% de los rangos:
   - el RPS se redondea a 6 decimales antes de ordenar;
   - los empates de rango se promedian (el `rank` por defecto de R);
   - la posición es el rango mínimo del Overall Rank.
   - Solo entran los equipos activos (`IsActive = 1`). Un agregado exige tener puntaje en su primer mes: el global tiene 163 equipos, los trimestres tienen 163 / 197 / 208 / 223.
5. **La Tabla 4 del paper (arXiv:2310.13357v1) compara cada mes contra el benchmark global.** En `Hypothesis1.R`, los porcentajes mensuales de equipos "mejores que el benchmark" usan `bench` (valores globales) en lugar de `bench_tmp` (valores del mes), aunque las columnas del benchmark muestran los valores del mes. Con la comparación correcta, los porcentajes mensuales cambian mucho. Ver `results/m6_leaderboard/2026-09-29_4de5c39/paper_table4_corrected.csv`.
6. **Un comportamiento de R infla la Tabla 4.** `tmp[tmp$IR > x, ]` incluye las filas con NA, así que el equipo con IR NaN (hallazgo 3) cuenta como "mejor que el benchmark" en M10–M12.
7. **Población de la Tabla 4:** son 148 equipos, los 163 del global menos los 15 cuyo IR global es idéntico al del benchmark (cuenta `32cdcc24`). Las cifras del texto (38 / 47 / 11) sí usan los 163 equipos.

> Nota para las citas: estas cifras se verificaron contra el **preprint arXiv v1**. El `.bib` cita la versión publicada en IJF (2025), que no se revisó. Antes de citar números del paper en la tesina hay que confirmarlos contra la versión publicada o agregar el preprint a Zotero.
