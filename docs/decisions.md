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
