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
