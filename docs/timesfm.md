# TimesFM-3: licencia, datos de preentrenamiento y riesgo de contaminación (#23)

Nota de trabajo para la metodología y las limitaciones. Revisada el 2026-10-02 contra las
fuentes primarias que se listan al final. Antes de llevar a la tesina cualquier afirmación de
esta nota, Marco debe verificarla y agregar la fuente a Zotero.

## Modelo y versión

- Checkpoint: `google/timesfm-3.0-pytorch` en Hugging Face, fijado a la revisión
  `43046b85ec22d584a13f8098c2ed39c889e129c2` (`tesina.models.foundation.REVISION`).
  Archivo de pesos: `model.safetensors`, de 1.32 GB.
- Código: paquete `timesfm` 3.0.2 de PyPI (Apache-2.0), con el backend MLX para Apple
  Silicon, que se instala con `uv sync --extra timesfm`. El README del repositorio dice
  que este backend reproduce al de PyTorch con un error máximo del orden de 1e-6.
- Publicación: 31 de agosto de 2026, según el blog de Google Research.
- Arquitectura (ficha del modelo): unos 330 millones de parámetros y 20 capas. Admite
  contextos de hasta 16k pasos.
- Salidas: la mediana y 9 cuantiles (del 0.1 al 0.9) en cada paso del horizonte. **No
  entrega trayectorias muestreadas.** Por eso el adaptador construye la distribución de
  cada activo a partir de sus deciles y une a los activos con una cópula gaussiana.

## Licencia

- Los **pesos** de TimesFM 3.0 se distribuyen bajo la *TimesFM Non-Commercial License
  v1.0*. Los de las versiones 2.5 y anteriores, igual que el código, son Apache-2.0.
- **Uso en la tesina.** La licencia define el uso no comercial e incluye de forma
  explícita la investigación académica, siempre que los resultados no se usen en
  decisiones comerciales, entregables a clientes ni productos de pago.
- **Publicación de resultados.** Las predicciones (*Outputs*) no cuentan como trabajos
  derivados, así que pueden aparecer en la tesina.
- **Prohibido redistribuir los pesos.** Nunca se suben al repositorio: se descargan a la
  caché de Hugging Face del usuario, fuera del repo.
- **Aceptación.** Descargar los pesos implica aceptar la licencia a título personal. Lo
  decide Marco antes de la primera descarga.

## Datos de preentrenamiento

Según la ficha del modelo, el preentrenamiento usó:

1. *GiftEvalPretrain*, sin los conjuntos que se traslapan con fev-bench.
2. Pageviews de Wikipedia hasta noviembre de 2023.
3. Las consultas más buscadas de Google Trends hasta finales de 2022.
4. Datos sintéticos y aumentados, sin más detalle.

El blog habla de "más de un billón de puntos". No hay reporte técnico de la versión 3: la
ficha cita el paper original de TimesFM (arXiv:2310.10688) y remite a "el paper" para los
detalles de Wikipedia y Trends.

**Lo que se revisó de GiftEvalPretrain:** el listado de sus carpetas en Hugging Face, al
2026-10-02.
- No aparece ningún conjunto de precios de acciones ni de ETFs individuales.
- Las series cercanas a lo financiero son:
  - `bitcoin_with_missing`;
  - `fred_md`, que es macroeconómica;
  - M1 y M3, series antiguas y anonimizadas;
  - `godaddy`.
- No verifiqué las fechas que cubre cada conjunto.

## Riesgo de contaminación con los periodos de evaluación

| Fuente | Cubre | Periodo 1 (mar 2022 – feb 2023) | Periodo 2 (mar 2023 – corte) |
|---|---|---|---|
| Precios de los activos del M6 | No hay evidencia de que estén en el preentrenamiento | Riesgo bajo, sin poder descartarlo | Riesgo bajo, sin poder descartarlo |
| Pageviews de Wikipedia | Hasta nov 2023 | **Se traslapa** (atención a empresas, no precios) | Se traslapa hasta nov 2023 |
| Google Trends | Hasta fin de 2022 | **Se traslapa** con 10 de los 12 meses | No |
| Sintéticos y aumentados | No se describen | Desconocido | Desconocido |
| Selección del checkpoint con benchmarks (GIFT-Eval, fev-bench, TIME), hasta 2026 | No se reportan controles de contaminación | Indirecto y desconocido | Indirecto y desconocido |

**Lectura:** no hay evidencia de que TimesFM-3 haya visto los precios de los activos del M6,
pero la documentación no permite descartarlo. Además vio series de atención (Wikipedia y
Trends) que se traslapan con el periodo 1.

**Consecuencias para el análisis:**
- El desempeño de TimesFM-3 en el periodo 1 se reporta con esta advertencia.
- El periodo 2 posterior a noviembre de 2023 es la parte menos expuesta. Conviene
  reportarlo también por separado, como un análisis más, que se cuenta en las
  comparaciones múltiples.
- Ninguna conclusión de RQ1 o RQ2 debe depender solo de este modelo.
- **RQ5:** si se usan pageviews de Wikipedia, TimesFM-3 no debe pronosticarlas, porque
  esas series sí estuvieron en su preentrenamiento hasta noviembre de 2023.

## Fuentes primarias, para agregar a Zotero

- Ficha del modelo: https://huggingface.co/google/timesfm-3.0-pytorch (revisión arriba).
- Licencia: https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE
- Repositorio: https://github.com/google-research/timesfm (README, sección de TimesFM 3.0).
- Blog: https://research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/
  (Jain y Sen, 31 de agosto de 2026).
- Das, Kong, Sen y Zhou, *A decoder-only foundation model for time-series forecasting*,
  ICML 2024, arXiv:2310.10688.
- Aksu et al., *GIFT-Eval: A Benchmark for General Time Series Forecasting Model
  Evaluation*, arXiv:2410.10393. Conjunto: https://huggingface.co/datasets/Salesforce/GiftEvalPretrain
