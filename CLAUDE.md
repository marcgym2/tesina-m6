# CLAUDE.md — Tesina MCD UANL

## Contexto

Tesina de la Maestría en Ciencia de Datos (FCFM, UANL). Autor: Marco Antonio Obregón Flores.
La tesina se redacta en **español**. Código, nombres de variables, commits y comentarios en **inglés**.

**Título tentativo:** "¿Cuánto del alfa es ilusión? Evaluación honesta de pronósticos probabilísticos
de rendimiento relativo con aprendizaje automático: réplica y extensión de la competencia M6"

**Propósito:** medir con rigor qué queda del "alfa" de estrategias de ML cuando se evalúan honestamente.
Audiencia secundaria: inversionistas no profesionales expuestos a promesas de "trading con IA".
Un resultado negativo bien documentado ES un resultado válido. No se persigue un Sharpe alto.

## Preguntas de investigación

- **RQ1 — Persistencia.** ¿Los métodos ganadores del M6 siguen superando al benchmark uniforme fuera del periodo de competencia?
- **RQ2 — Evaluación limpia.** Con validación sin leakage, ¿algún modelo supera al benchmark uniforme en RPS de forma estadísticamente significativa?
- **RQ3 — Pronóstico vs decisión.** ¿Un mejor RPS se traduce en un mejor IR?
- **RQ4 — Cascada de sesgos.** ¿Cuánto del desempeño de un pipeline ingenuo desaparece al corregir leakage, split no temporal, sesgo de supervivencia y costos?
- **RQ5 (opcional).** ¿Los activos con picos de atención (Wikipedia pageviews) tienen peores rendimientos relativos posteriores?

## Diseño

- **Periodo 1 — M6 original (mar 2022 – feb 2023):** modelos propios vs las submissions reales de los equipos (`submissions.csv` oficial).
- **Periodo 2 — M6 extendido (mar 2023 – fecha de corte):** código de ganadores + modelos propios sobre datos que nadie vio durante la competencia.
- **Universo:** 100 activos del M6 (50 acciones del S&P 500 + 50 ETFs internacionales).
- **Horizonte y calendario:** periodos de 4 semanas según las reglas del M6. Verificar en la guía oficial, no asumir.
- **Benchmark de pronóstico:** uniforme (0.2 por quintil). **Benchmark de inversión:** el definido por el M6 (verificar en el repo oficial).

## Fuentes de verdad

- `https://github.com/Mcompetitions/M6-methods`: `assets_m6.csv`, `submissions.csv` y código oficial de evaluación.
  **RPS e IR se implementan siguiendo ese código, NUNCA de memoria.**
- Paper de resultados: Makridakis et al., arXiv 2310.13357.
- Código de participantes: `miguel-data-sc/FinQBoost` (posiblemente R), `sebrad/M6`, `MarcoGorelli/wound-ignite`.
  AdaGaussMC: arXiv 2303.01855 (verificar si hay código público).
- Repo previo del autor: `marcgym2/refactor_r`. Tiene módulos reutilizables. Su universo `mags7` es un ejemplo de sesgo de supervivencia (útil para RQ4).
- Tesina 2024: `thesis/legacy/tesina_2024.docx`. El marco teórico es reutilizable SOLO después de que Marco verifique cada cita.

## Reglas no negociables

### Anti-leakage
1. Todo split es temporal (walk-forward o expanding window). Prohibido KFold aleatorio o shuffle.
2. Todo estadístico (escaladores, imputación, selección de features, hiperparámetros) se ajusta solo con datos ≤ fecha de pronóstico.
3. Los quintiles objetivo se calculan de forma transversal dentro de cada periodo, nunca agrupando periodos.
4. Si las etiquetas se traslapan en el tiempo: purga + embargo.
5. El universo en cada fecha usa solo información disponible en esa fecha. Toda excepción se documenta como sesgo.
6. Cada pipeline nuevo lleva tests en `tests/` que verifican 1–5.

### Evaluación
- Todo modelo reporta RPS vs uniforme e IR vs benchmark M6, por periodo y agregado.
- Significancia: comparación pareada contra el uniforme (bootstrap por bloques o Diebold-Mariano). Reportar cuántos modelos o configuraciones se probaron (comparaciones múltiples).
- Los backtests incluyen costos de transacción (parámetro en bps, configurable) y se reportan con y sin costos.
- Nunca reportar el mejor resultado de una búsqueda sin reportar la búsqueda completa.

### Reproducibilidad
- Los datos crudos se congelan en `data/raw/` como parquet, con la fecha de descarga en el nombre. Nunca se sobrescriben.
  Snapshots < 50 MB van en git; los mayores, vía `data/manifest.json` con hashes.
- Semillas fijas. Cada experimento tiene `experiments/<nombre>/config.toml`. Los outputs van a `results/<nombre>/` junto con la config y el hash del commit.
- Dependencias con `uv`; `uv.lock` en git. Si se necesita R (p. ej. FinQBoost), usar `renv` en `vendor/<método>/`.

### Citas y honestidad académica
- **Nunca inventar** una referencia, una cita textual, un número o un resultado atribuido a un paper.
- Solo se cita con claves existentes en `thesis/references.bib`. Ese archivo lo mantiene Marco con Zotero + Better BibTeX. **Claude no lo edita.**
- Si un párrafo necesita una fuente que no está en el `.bib`: escribir `[CITA PENDIENTE: descripción]` y abrir un issue con label `humano`.
- Por defecto se parafrasea. Solo hay citas textuales si Marco las verificó contra el PDF.
- `scripts/check_citations.py` debe pasar antes de cada commit que toque `thesis/`.
- No subir PDFs de papers al repo.

## Estructura del repo

```
.
├── CLAUDE.md
├── ISSUES.md              # backlog inicial (ya migrado a GitHub Issues)
├── pyproject.toml / uv.lock
├── data/raw/              # snapshots congelados
├── src/tesina/            # data, evaluation (rps, ir), models, backtest, universe
├── vendor/                # código de participantes del M6, adaptado, con su licencia
├── experiments/<nombre>/  # un directorio por experimento: config.toml + run.py
├── results/<nombre>/      # outputs versionados (tablas csv/parquet, figuras)
├── scripts/               # check_citations.py, postprocess_docx.py, utilidades
├── tests/
└── thesis/
    ├── _quarto.yml
    ├── chapters/*.qmd
    ├── references.bib     # generado por Zotero (NO editar)
    ├── apa.csl
    ├── templates/         # uanl_original.docx, reference.docx
    └── legacy/            # tesina_2024.docx
```

## Tesina (Quarto)

- Salida principal: `.docx` con `reference-doc: templates/reference.docx`, derivado de la plantilla UANL.
- Capítulos según la plantilla: 1 Introducción, 2 Delimitación y planteamiento, 3 Justificación, 4 Objetivos,
  5 Marco teórico, 6 Metodología, 7 Resultados y conclusiones; Anexos; Referencias.
- Figuras y tablas se generan desde `results/`. **Ningún número de resultados se escribe a mano en el texto**: se inyecta desde archivos de resultados.
- CSL: APA 7.
- Portada, hoja de firmas e índices: si el `reference-doc` no alcanza, se resuelve en `scripts/postprocess_docx.py` (python-docx). La edición manual del `.docx` solo ocurre en el pase final.
- `quarto render thesis` debe funcionar siempre en `main`.

## Flujo de trabajo

- Tareas en GitHub Issues (milestones M0–M9), gestionadas con `gh`.
- Una rama por issue; los commits referencian `#n`. Al cerrar, comentar en el issue: qué se hizo, resultados clave y HM reales.
- Issues con label `humano` o `decision`: **no se ejecutan**. Se prepara lo necesario (borrador, opciones con pros y contras) y se deja un comentario para Marco.
- Unidades de esfuerzo: **HM** = hora de Claude trabajando; **HH** = hora de Marco.
- Ante ambigüedad metodológica: no decidir en silencio. Abrir un issue `decision`.

## Qué NO hacer

- No "mejorar" resultados cambiando la evaluación, el periodo o el universo.
- No agregar modelos o experimentos fuera del plan sin abrir issue.
- No borrar ni reescribir snapshots de datos ni resultados de experimentos previos.
- No editar `thesis/references.bib`.
