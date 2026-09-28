# ISSUES.md — Backlog inicial

## Instrucciones para Claude Code

1. Crear los labels: `maquina`, `humano`, `decision`, `setup`, `datos`, `evaluacion`, `modelos`, `analisis`, `escritura`, `opcional`.
2. Crear los milestones M0–M9 con los nombres de abajo.
3. Crear un issue por cada entrada. Título = encabezado sin el número.
   Cuerpo = descripción + "**Hecho cuando:**" + línea `Estimado: HM x | HH y`.
4. Crear un GitHub Project "Tesina" con columnas Backlog / En curso / Esperando a Marco / Hecho, y agregar todos los issues.
5. No ejecutar issues `humano` ni `decision`: solo preparar insumos y comentar.

Unidades: **HM** = hora de Claude · **HH** = hora de Marco.

---

## M0 — Propuesta

### 1. Borrador del one-pager para el director
- Labels: `escritura`, `maquina` · HM 1 | HH 0.5
- `thesis/propuesta.qmd` que renderice a docx: título, propósito, RQ1–RQ5, diseño de dos periodos, alcance y lo que NO se hará.
- **Hecho cuando:** Marco lo revisó y está listo para enviar.

### 2. Revisión y aprobación del director
- Labels: `humano` · HH 1.5
- **Hecho cuando:** el director aprueba el tema o se registran los cambios pedidos.

## M1 — Setup

### 3. Esqueleto del repo
- Labels: `setup`, `maquina` · HM 1 | HH 0.5
- Estructura según CLAUDE.md, `uv init`, pytest, ruff, pre-commit, `.gitignore` (excluir PDFs), README mínimo.
- **Hecho cuando:** `uv run pytest` pasa con un test dummy y pre-commit corre.

### 4. Proyecto Quarto con plantilla UANL
- Labels: `setup`, `escritura`, `maquina` · HM 2 | HH 1
- Derivar `reference.docx` de `templates/uanl_original.docx`. Capítulos vacíos, portada, hoja de firmas, índices de contenido/tablas/figuras, APA 7.
- Si algo no sale con reference-doc: `scripts/postprocess_docx.py`.
- **Hecho cuando:** `quarto render thesis` genera un docx que Marco aprueba visualmente contra la plantilla.

### 5. Instalar Zotero + Better BibTeX
- Labels: `humano`, `setup` · HH 0.5
- Auto-export a `thesis/references.bib` (formato Better BibLaTeX o BibTeX, "keep updated").
- Agregar primeros papers: Makridakis et al. (M6), FinQBoost, AdaGaussMC, "role of luck" (arXiv 2412.04490), Schneider et al. (arXiv 2406.19105).
- **Hecho cuando:** el `.bib` se actualiza solo al agregar un paper.

### 6. Script de verificación de citas
- Labels: `setup`, `maquina` · HM 0.5
- `scripts/check_citations.py`: toda `@clave` en `.qmd` existe en el `.bib`; lista los `[CITA PENDIENTE]`. Hook de pre-commit.
- **Hecho cuando:** falla con una clave inexistente y pasa con claves válidas.

### 7. Project board y convenciones
- Labels: `setup`, `maquina` · HM 0.5 | HH 0.25
- **Hecho cuando:** todos los issues están en el board.

## M2 — Reproducir el M6

### 8. Descargar datos oficiales del M6
- Labels: `datos`, `maquina` · HM 0.5
- `assets_m6.csv`, `submissions.csv`, archivo de evaluación de ejemplo → `data/raw/` con fecha + manifest.
- **Hecho cuando:** los archivos están congelados y documentados.

### 9. Implementar RPS e IR según el código oficial
- Labels: `evaluacion`, `maquina` · HM 1.5 | HH 0.5
- Traducir el código oficial (R/Python) de M6-methods. Tests contra el ejemplo de evaluación oficial.
- **Hecho cuando:** los tests reproducen el ejemplo oficial exactamente.

### 10. Reproducir el leaderboard global
- Labels: `evaluacion`, `maquina` · HM 1 | HH 1
- Calcular RPS e IR por equipo con `submissions.csv`. Comparar contra los valores publicados en el paper (benchmark RPS = 0.16, top teams).
- **Hecho cuando:** coincide con lo publicado dentro de tolerancia, o las discrepancias están explicadas.

## M3 — Datos del periodo 2

### 11. DECISIÓN: política de universo para el periodo 2
- Labels: `decision`, `humano` · HM 0.5 | HH 0.5
- Activos deslistados o fusionados (p. ej. DRE, RE, WRK). Opciones: excluir, sustituir por sucesor, cerrar la posición al último precio. Claude prepara las opciones con pros y contras.
- **Hecho cuando:** Marco elige y queda documentado en `docs/decisions.md`.

### 12. Snapshot de precios del universo M6 hasta la fecha de corte
- Labels: `datos`, `maquina` · HM 1 | HH 0.5
- **Hecho cuando:** hay un parquet congelado + manifest y la fecha de corte está fijada.

### 13. Checks de calidad de datos
- Labels: `datos`, `maquina` · HM 1
- Splits, huecos, saltos anómalos, discrepancias vs `assets_m6.csv` en el periodo traslapado.
- **Hecho cuando:** hay un reporte en `results/data_quality/` y los problemas están resueltos o documentados.

### 14. Calendario de periodos de 4 semanas para el periodo 2
- Labels: `datos`, `maquina` · HM 0.5
- Replicar las reglas de calendario del M6 (verificar en la guía oficial).
- **Hecho cuando:** hay una tabla de periodos con tests.

## M4 — Baselines y ganadores del M6

### 15. Harness walk-forward genérico
- Labels: `evaluacion`, `maquina` · HM 2 | HH 0.5
- Interfaz: `model.forecast(history_up_to_t) -> probs[activo, quintil]` + pesos. Tests anti-leakage automáticos.
- **Hecho cuando:** un modelo dummy corre en ambos periodos y los tests de leakage pasan.

### 16. Baselines: uniforme y frecuencia histórica
- Labels: `modelos`, `maquina` · HM 0.5
- **Hecho cuando:** el uniforme da RPS = 0.16 en el periodo 1.

### 17. FinQBoost en el periodo 2
- Labels: `modelos`, `maquina` · HM 2 | HH 0.5
- Adaptar en `vendor/finqboost/` (posiblemente R + renv). Primero verificar que reproduce su score del periodo 1.
- **Hecho cuando:** hay pronósticos para ambos periodos y el periodo 1 coincide con su submission.

### 18. sebrad/M6 en el periodo 2
- Labels: `modelos`, `maquina` · HM 1.5
- **Hecho cuando:** igual que #17.

### 19. wound-ignite en el periodo 2
- Labels: `modelos`, `maquina` · HM 1.5
- **Hecho cuando:** igual que #17.

### 20. AdaGaussMC
- Labels: `modelos`, `maquina` · HM 2 | HH 0.5
- Buscar código público; si no existe, reimplementar desde arXiv 2303.01855 y documentar la fidelidad.
- **Hecho cuando:** hay pronósticos para ambos periodos y la reimplementación está validada.

## M5 — Modelos propios

### 21. GBM multiclase (LightGBM o CatBoost)
- Labels: `modelos`, `maquina` · HM 1.5
- **Hecho cuando:** hay pronósticos en ambos periodos con hiperparámetros elegidos solo con datos pasados.

### 22. Simulación desde covarianzas
- Labels: `modelos`, `maquina` · HM 1.5
- Estimar la distribución conjunta de rendimientos, simular escenarios y derivar probabilidades de quintil.
- **Hecho cuando:** igual que #21.

### 23. Modelo fundacional zero-shot (Chronos o TimesFM)
- Labels: `modelos`, `maquina` · HM 2
- Muestras de trayectorias → probabilidades de quintil.
- **Hecho cuando:** igual que #21 y está documentado qué datos vio el modelo en su preentrenamiento (riesgo de contaminación con el periodo 1).

## M6 — Cascada de sesgos (RQ4)

### 24. Pipeline ingenuo (réplica de la tesina 2024)
- Labels: `modelos`, `maquina` · HM 1.5
- Split aleatorio, escalado e imputación globales, universo fijo de ganadores, sin costos.
- **Hecho cuando:** reporta su métrica "inflada".

### 25. Corregir sesgo por sesgo + figura de cascada
- Labels: `analisis`, `maquina` · HM 2 | HH 1
- Un paso por sesgo; medir RPS, IR y Sharpe en cada paso.
- **Hecho cuando:** existe la figura de cascada en `results/cascade/`.

## M7 — Análisis

### 26. Significancia vs uniforme
- Labels: `analisis`, `maquina` · HM 1.5 | HH 1
- Tests pareados por periodo (bootstrap por bloques / Diebold-Mariano) + ajuste por comparaciones múltiples.
- **Hecho cuando:** hay una tabla de p-values ajustados para todos los modelos.

### 27. RPS vs IR (RQ3)
- Labels: `analisis`, `maquina` · HM 1
- Relación entre equipos en el periodo 1 y entre modelos en el periodo 2.
- **Hecho cuando:** hay figura + estadístico de correlación con intervalo.

### 28. Persistencia de ganadores (RQ1)
- Labels: `analisis`, `maquina` · HM 1 | HH 0.5
- **Hecho cuando:** hay una tabla del periodo 1 vs periodo 2 por método con conclusión explícita.

## M8 — Redacción

### 29. Verificar citas del marco teórico 2024
- Labels: `humano`, `escritura` · HH 4
- Cada cita contra su PDF: se conserva, se corrige o se elimina.
- **Hecho cuando:** hay una lista de citas válidas en Zotero.

### 30. Literatura nueva a Zotero
- Labels: `humano`, `escritura` · HH 3
- Papers del M6 y sus críticas, Gu, Kelly & Xiu (2020), López de Prado (backtest overfitting), literatura de atención (si se hace RQ5).
- **Hecho cuando:** todos están en Zotero con PDF.

### 31. Capítulos 1–4
- Labels: `escritura`, `maquina` · HM 2 | HH 2
- **Hecho cuando:** check_citations pasa y Marco aprueba.

### 32. Capítulo 5: marco teórico
- Labels: `escritura`, `maquina` · HM 2 | HH 2
- **Hecho cuando:** igual que #31.

### 33. Capítulo 6: metodología
- Labels: `escritura`, `maquina` · HM 1.5 | HH 1
- **Hecho cuando:** igual que #31.

### 34. Capítulo 7: resultados y conclusiones
- Labels: `escritura`, `maquina` · HM 2 | HH 2
- Todos los números inyectados desde `results/`.
- **Hecho cuando:** igual que #31.

### 35. Pase final de formato + revisión del director
- Labels: `escritura`, `humano` · HM 1 | HH 2
- **Hecho cuando:** hay versión entregable aprobada.

## M9 — Opcional: atención (RQ5)

### 36. Wikipedia pageviews y rendimientos posteriores
- Labels: `opcional`, `datos`, `analisis`, `maquina` · HM 6 | HH 3
- API de pageviews de Wikimedia (desde 2015). Si el cron de discovery de `refactor_r` tiene historia, usarla como validación.
- **Hecho cuando:** hay un análisis completo o la decisión documentada de descartarlo.

---

**Total núcleo (M0–M8):** ~41 HM | ~27 HH · **Opcional (M9):** +6 HM | +3 HH
