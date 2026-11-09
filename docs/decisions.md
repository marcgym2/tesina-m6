# Registro de decisiones metodológicas

Cada entrada registra una decisión de Marco sobre un issue `decision`: el contexto, la opción elegida y cómo se aplica en el código. Las entradas no se reescriben. Si una decisión cambia, se agrega una entrada nueva que reemplaza a la anterior.

---

## D1 — IR con varianza cero: reportar ambos criterios (#42)

- **Fecha:** 2026-09-29 · **Decidió:** Marco · **Issue:** #42 · **Origen:** hallazgo del #9 (PR #41)
- **Contexto:** en M10–M12 del periodo 1, el equipo `bc4b0314` (MarcoGorelli, *wound-ignite*) asignó el 100% del peso a DRE. DRE está congelado desde su fusión con Prologis (último precio: 2022-11-28), así que el portafolio tiene rendimiento diario 0 y el IR queda 0/0. El código oficial publicado (`RPS and IR calculation.R/.py`) da `NaN`. El leaderboard oficial (`summary_leaderboard.xlsx`) muestra IR = 1.0, una regla que no está en el código.
- **Decisión:** reportar ambos.
  - **Reproducción del M6 (#10):** IR = 1.0, como en el leaderboard, para comparar contra lo publicado.
  - **Análisis propios (RQ1, RQ4 y periodo 2):** IR = `NaN`, como en el código. El mes se excluye del agregado y la exclusión se reporta.
  - En la tesina se explica el caso como ejemplo de artefacto de evaluación: un activo deslistado que funcionó como efectivo sin riesgo.
- **Implementación:** `tesina.evaluation.ir.information_ratio(..., zero_variance=...)`. El default es `NaN` (código oficial); `zero_variance=1.0` reproduce el leaderboard. Todo resultado que use 1.0 lo indica en su tabla.

---

## D2 — Política de universo en el periodo 2: opción D, híbrida (#11)

- **Fecha:** 2026-09-29 · **Decidió:** Marco · **Issue:** #11 (opciones y fuentes en el comentario del issue)
- **Contexto:** desde marzo de 2023, dos activos del universo M6 dejan de existir: DRE (adquirida por Prologis; su último precio en los datos oficiales es del 2022-11-28) y WRK (fusión con Smurfit Kappa, fuera del NYSE desde el 2024-07-05; se pagó 1 acción de SW + US$5 por acción). RE cambió su ticker a EG el 2023-07-10, pero es la misma acción.
- **Decisión (opción D):**
  - **DRE** queda excluido desde el inicio del periodo 2, porque ya estaba muerto cuando empezó el periodo.
  - **WRK** se mantiene con su último precio (regla del M6) **solo durante el periodo de 4 semanas en que desaparece**, y queda excluido desde el periodo siguiente.
  - **RE → EG** se mapea como el mismo activo.
  - Cuando el universo tiene menos de 100 activos, los quintiles objetivo usan umbrales proporcionales (`k·n/5`): `quintile_targets(..., n_assets_rule="proportional")`. Esto se aparta del código oficial, que fija los umbrales en 20/40/60/80, y se declara como tal en la tesina.
  - Todo cambio de universo se aplica desde la fecha del evento, sin usar información posterior (regla 5 de CLAUDE.md).
- **Pendiente de confirmar:** Claude recomendó correr la opción C (congelar a los deslistados al último precio durante todo el periodo, como hizo el M6) como análisis de sensibilidad del periodo 2.
- **Consecuencias:** el código de los ganadores (#17–#20) debe aceptar universos de 99 y 98 activos.

---

## D3 — Fecha de corte del periodo 2 (#12)

- **Fecha:** 2026-09-29 · **Decidió:** Marco · **Issue:** #12
- **Decisión:** la fecha de corte es el cierre del **último periodo completo de 4 semanas anterior a la fecha de descarga** del snapshot de precios. Los periodos siguen el calendario del M6, que se construye en el #14.
- **Implementación:** la fecha de descarga y la fecha de corte resultante se guardan en `data/manifest.json` junto con el snapshot (#12). Los datos posteriores a la fecha de corte no se usan en ningún experimento.

---

## D4 — Sensibilidad del universo del periodo 2 con la regla oficial del M6 (#11)

- **Fecha:** 2026-10-01 · **Decidió:** Claude, por delegación explícita de Marco ("tu decide") · **Issue:** #11 · **Completa:** el punto pendiente de D2.
- **Decisión:** además del análisis principal con la opción D (D2), el periodo 2 se recalcula con la **opción C** (regla del M6: los deslistados quedan en el universo congelados a su último precio durante todo el periodo) como **análisis de sensibilidad**.
- **Motivo:** la diferencia entre D y C mide cuánto del desempeño depende del tratamiento de los activos que desaparecen. Ese es un insumo directo para RQ4, y en el periodo 1 esta regla produjo un artefacto (D1). Cuesta poco: el harness ya implementa ambas políticas (`universe_policy = "d2"` y `"official"`).
- **Cómo se reporta:** la opción D va en las tablas principales y la opción C en una tabla de robustez o en un anexo. Las corridas con C cuentan en el número total de configuraciones probadas (regla de comparaciones múltiples de CLAUDE.md).

---

## D5 — Modelo y alcance de la cascada de sesgos, RQ4 (#24, #25, #52)

- **Fecha:** 2026-10-02 · **Decidió:** Marco · **Issues:** #24, #25, #52
- **Decisión:**
  - **El modelo de la cascada es el gradient boosting propio (#21).** Se mantiene fijo y en cada escalón se inyecta o se corrige un sesgo. El último escalón es el mismo GBM limpio que se evalúa en RQ2.
  - **No se replica la red neuronal (FFNN + meta-modelo) de 2024**, ni siquiera como anexo.
  - **La tesina 2024 no se cita ni se usa como antecedente**, porque no se concluyó ni se publicó. La justificación de cada sesgo de la cascada viene de la literatura (`[CITA PENDIENTE]` hasta que esté en Zotero, #30). `docs/pipeline_2024.md` queda como nota interna.
- **Pendiente en #52:** el universo de la cascada. La recomendación es el del M6.
- **Consecuencia:** el orden de trabajo es #12 → #21 → #24/#25.

---

## D6 — Universo de la cascada de sesgos, RQ4 (#52)

- **Fecha:** 2026-10-02 · **Decidió:** Marco · **Issue:** #52 · **Completa:** D5
- **Decisión:** la cascada se hace sobre el **universo del M6**.
  - El escalón sesgado usa un universo elegido después de los hechos: solo los activos que siguen cotizando hoy, con los deslistados sustituidos por sus sucesores (DRE→PLD, WRK→SW). Es el sesgo de supervivencia.
  - La corrección usa el universo point-in-time con la política D2.
- **Motivo:** es coherente con el resto de la tesina (mismos datos, misma evaluación) y no requiere listas históricas de componentes de otro índice.

---

## D7 — Modelo fundacional de #23: TimesFM-3

- **Fecha:** 2026-10-02 · **Decidió:** Marco · **Issue:** #23
- **Decisión:** el modelo fundacional zero-shot es **TimesFM-3** de Google (`google/timesfm-3.0-pytorch`). El checkpoint queda fijado a una revisión de Hugging Face y se usa tal cual, sin fine-tuning ni búsqueda de hiperparámetros.
- **Cómo se adapta:**
  - TimesFM-3 entrega deciles por activo, no trayectorias. Las probabilidades de quintil salen de esos deciles unidos con una cópula gaussiana, cuya correlación es la EWMA de #22 con una vida media fija de 126 días.
  - Los detalles están en `src/tesina/models/foundation.py`.
- **Condiciones:**
  - Los pesos tienen licencia no comercial. La investigación académica está permitida, pero los pesos no se redistribuyen, y descargarlos implica que Marco acepta esa licencia.
  - El riesgo de contaminación del preentrenamiento con los periodos 1 y 2 está documentado en `docs/timesfm.md` y se reporta junto con los resultados.

---

## D8 — Configuración de wound-ignite en el periodo 2 (#61)

- **Fecha:** 2026-10-02 · **Decidió:** Marco · **Issue:** #61
- **Decisión (opción A):** en el periodo 2, wound-ignite se corre con la **última configuración que el autor dejó en el repo** (la del "mes 11": 8 estimadores de covarianza, `PORT[0]` y escala 1), congelada para todos los periodos. No se reproduce la selección mensual.
- **Detalles:**
  - No se aplica el encogimiento hacia el uniforme que se observa en el envío del mes 10, porque no está en el código.
  - El IR se calcula con los pesos que produce el propio método (`Decision`).
  - La semilla del Monte Carlo es fija, una adaptación documentada en `vendor/wound-ignite/NOTICE.md`.
- **Motivo:** RQ1 pregunta si el método publicado sigue funcionando. La configuración final lo responde sin agregar decisiones nuestras, como fijar umbrales que el autor movía a mano. La selección mensual puede agregarse después como sensibilidad, con un issue nuevo.
- **Implementación:** `vendor/wound-ignite/run.py` y `experiments/wound_ignite/`. El periodo 1 se corre solo como referencia, porque esa configuración se eligió con datos de 2022.

---

## D9 — AVB: tercer deslistado del universo (#12, #13)

- **Fecha:** 2026-11-09 · **Decidió:** Claude, aplicando la regla D2 ya decidida por Marco · **Issues:** #12, #13
- **Contexto:** el check de calidad del snapshot de EODHD (2026-11-09) mostró que AVB (AvalonBay Communities) no tiene precios después del 2026-08-14; Yahoo tampoco los tiene. AvalonBay se fusionó con Equity Residential, que pasó a llamarse Vivmark Residential (VMRK). Según el 8-K de AvalonBay del 2026-08-17, sus acciones salieron de la bolsa de Nueva York antes de la apertura de ese día y cada acción se canjeó por 2.793 acciones de la nueva empresa.
- **Decisión:** AVB recibe el mismo trato que WRK (D2).
  - Se mantiene con su último precio durante el periodo de 4 semanas en que desaparece.
  - Queda excluido desde el primer periodo cuyo origen es igual o posterior al 2026-08-17.
  - El universo del periodo 2 baja de 98 a 97 activos desde entonces.
- **Implementación:** `tesina.universe.DELISTINGS`. Para el escalón de supervivencia de la cascada (D6), el sucesor de AVB es VMRK; hay que descargarlo cuando se haga el #24.
- **Otros hallazgos del check, sin cambio de reglas:**
  - En EODHD, el último precio de DRE es del 2022-10-03 (cierre de su fusión); los datos oficiales del M6 lo traen hasta el 2022-11-28. No afecta: el periodo 1 usa los datos oficiales y el periodo 2 excluye a DRE.
  - El salto de HIG del 2008-12-05 (+102 %) es un movimiento real, no un split sin ajustar.

---

## D10 — AdaGaussMC: la reimplementación no reproduce los envíos del equipo (#20)

- **Fecha:** 2026-11-09 · **Decidió:** Claude; es un criterio de reporte, no cambia ningún modelo · **Issue:** #20
- **Contexto:** la reimplementación desde el artículo (arXiv:2303.01855) se comparó con los 12 envíos reales del equipo `b1002bc9` (`results/adagaussmc/2026-11-09_17793ac/fidelity.csv`). La correlación media es 0.31 y el RPS medio es 0.1583 contra 0.1569 del equipo. Los envíos reales colocan a los ETFs amplios de renta variable en el quintil central y dejan a los bonos de corto plazo cerca del uniforme; eso refleja dependencia entre activos, mientras que el artículo describe activos independientes para la tarea de pronóstico.
- **Decisión:**
  - El modelo se reporta como "AdaGaussMC según el artículo", no como el método del equipo.
  - No se ajusta para parecerse a los envíos, porque eso sería afinarlo con el periodo 1.
  - En RQ1 su resultado se presenta aparte de FinQBoost y wound-ignite, con esta advertencia.
- **Contraste:** FinQBoost sí queda validado. Su correlación con los envíos de su equipo es 0.96 (0.99 desde el mes 6) y el RPS medio coincide (`results/finqboost/2026-11-09_f70d879/fidelity.csv`).

---

## D11 — Pasos y orden de la cascada de sesgos, RQ4 (#24, #25)

- **Fecha:** 2026-11-09 · **Decidió:** Claude, por delegación explícita de Marco ("no importa el orden, tú defínelo") · **Issues:** #24, #25 · **Completa:** D5 y D6
- **Decisión:** la cascada tiene siete pasos acumulativos sobre el GBM, evaluados en el periodo 2. El orden va de los errores de procedimiento más comunes a los que dependen del mercado, y se fijó antes de correrla.
  0. **Ingenuo:** validación cruzada con filas barajadas sobre toda la muestra; muestras semanales con etiquetas de cuatro semanas traslapadas; variables estandarizadas por activo con estadísticas de toda la muestra; se reporta la mejor configuración del grid sobre los propios periodos de evaluación; universo de supervivientes; sin costos.
  1. **+ split temporal:** en cada origen se entrena solo con muestras cuya fecha base es anterior. Las etiquetas aún no se purgan.
  2. **+ purga:** solo ventanas de cuatro semanas que terminan en el origen o antes.
  3. **+ preprocesamiento solo con el pasado:** las variables pasan a ser rangos transversales del mismo día.
  4. **+ selección honesta:** hiperparámetros elegidos con ventanas pasadas; ya no se elige nada viendo la evaluación.
  5. **+ universo point-in-time** (D2) en lugar del de supervivientes.
  6. **+ costos de transacción** sobre la rotación. Es el GBM limpio de RQ2, neto.
- **Detalles:**
  - Los sesgos "selección y reporte sobre el mismo conjunto" y "búsqueda no reportada" se inyectan juntos: en los pasos 0 a 3 se prueban 12 configuraciones (4 del grid × 3 números de rondas) y se reporta la de mejor RPS en la evaluación. La búsqueda completa se guarda.
  - El universo de supervivientes sustituye DRE→PLD, WRK→SW y AVB→VMRK.
  - Los pesos son siempre la inclinación hacia el quintil esperado, para que el IR y el Sharpe reflejen el pronóstico.
- **Límite de interpretación:** el orden afecta cuánto se atribuye a cada sesgo. La cascada mide el efecto de cada corrección dado que las anteriores ya se hicieron, no el efecto aislado de cada sesgo.
- **Implementación:** `src/tesina/cascade.py` y `experiments/cascade/`.
