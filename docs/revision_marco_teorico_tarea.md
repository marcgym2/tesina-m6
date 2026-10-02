# Revisión de la tarea "Marco teórico y referencias" (#29, #32)

Nota interna. El documento que se revisó es la tarea de marco teórico que Marco
entregó: `Solo Marco Teorico Y Referencias.docx`, de 5,500 palabras, que no está en el
repo. Su tema original es la predicción de rendimientos en el sector de semiconductores.
Aquí se registra qué se reutilizó en el capítulo 5 y en qué estado están sus
referencias. La revisión es del 2026-10-02.

**Cómo se reutilizó:** no se copió texto. Se reutilizaron la estructura y las ideas,
reescritas y parafraseadas. El documento tiene muchas citas textuales entre comillas, y
la tesina solo admite citas textuales verificadas contra el PDF (CLAUDE.md). Además,
varias de esas "citas" parecen traducciones libres o paráfrasis presentadas como cita
textual. Por ejemplo, la frase atribuida a Fama (1970) sobre el camino aleatorio no
parece ser una cita literal de ese artículo.

## Qué se rescató, por sección

| Sección de la tarea | Decisión | Motivo |
|---|---|---|
| 5.1.1–5.1.4 HME, anomalías, HMA | **Se rescata** como 5.1 del capítulo 5, reescrita | Es central para la tesina (eficiencia, persistencia y RQ1) |
| 5.1.5 Aplicación a semiconductores | Se descarta | Otro universo |
| 5.2.1 RSI y volatilidad (de Mattos Neto, gases ideales) | Se descarta | No se usa el RSI. La analogía física no aporta. La volatilidad se trata con GARCH, EWMA y AdaVol |
| 5.2.2 Efecto mensual (Xiao, Boudreaux) | Se descarta | El horizonte de 4 semanas lo fija la M6, no la estacionalidad |
| 5.2.3 Quintiles | Se rescata la idea (5.2.3 del cap. 5) con otras fuentes | Las atribuciones de la tarea son dudosas (ver abajo) |
| 5.3 Ensambles, árboles y random forest | Se rescata la idea, condensada | Faltaba Breiman (2001). Izza et al. trata de explicabilidad, no de los fundamentos de los árboles |
| 5.4 Gradient boosting (XGBoost, CatBoost, comparación tabular) | **Se rescata**, condensada, y se agrega LightGBM | Sustenta el GBM propio (#21) y la cascada |
| 5.5 Ingeniería de características (Vaiz y Ramaswami) | Se descarta | La fuente es débil y los indicadores no se usan |
| 5.6 Construcción de portafolios | — | Secciones vacías |
| 5.7.2 Sharpe e IR (Sharma, 2018) | Se rescata el concepto con fuentes primarias | Sharma (2018) no es una publicación arbitrada. Además, el IR de la M6 difiere del clásico |
| 5.7.1, 5.7.3, 5.7.4 y 5.8 | — | Secciones vacías o del sector de semiconductores |

## Estado de las referencias de la tarea

La consulta se hizo en Crossref (`api.crossref.org`), con una búsqueda bibliográfica por
título y autores. **Que una referencia exista no implica que diga lo que se le
atribuye.** Eso se verifica contra el PDF (#29).

| Referencia de la tarea | ¿Existe? | Observación | ¿Se usa en el cap. 5? |
|---|---|---|---|
| Fama (1970), *J. Finance* 25(2) | Sí, DOI 10.2307/2325486 | — | Sí (pendiente) |
| Fama (1998), *JFE* 49(3) | Sí (Crossref devuelve la versión de SSRN de 1997) | — | Sí (pendiente) |
| Daniel, Hirshleifer y Subrahmanyam (1998), *J. Finance* 53(6) | Sí, DOI 10.1111/0022-1082.00077 | — | Sí (pendiente) |
| Lo (2004) | Sí | La tarea dice "Forthcoming". Es *J. Portfolio Management* 30(5); falta confirmar el DOI | Sí (pendiente) |
| Leigh, Purvis y Ragusa (2002), *DSS* 32(4) | Sí, DOI 10.1016/s0167-9236(01)00121-x | — | No |
| Wang et al. (2011), *ESWA* 38(11) | Sí, DOI 10.1016/j.eswa.2011.04.222 | Es un trabajo de redes neuronales; no es una fuente adecuada para definir la HME | No |
| Ţăran-Moroşan (2011), *African J. Business Management* | No está en Crossref | Sin verificar | No |
| Gumparthi (2017), *IJAER* | No está en Crossref | En el texto dice "Gumparthi et al." y en la lista hay un solo autor | No |
| de Mattos Neto et al. (2011), *Physica A* 390(20) | Sí, DOI 10.1016/j.physa.2011.04.031 | — | No |
| Xiao (2016), *IJFR* 7(2) | Sí, DOI 10.5430/ijfr.v7n2p11 | — | No |
| Boudreaux (1995), *JFSD* 8(1) | No está en Crossref | Sin verificar | No |
| Barber, Lin y Odean (2023), *JFQA* | Sí (versión de SSRN de 2021, DOI 10.2139/ssrn.3783492) | Clasifica por desbalance de órdenes, no por rendimientos | No |
| Goetzmann, Watanabe y Watanabe (2024), NBER w32509 | Sí, DOI 10.3386/w32509 | En el texto dice 2023 y en la lista 2024. La afirmación de que "los quintiles capturan dinámicas no lineales" no parece ser el argumento de ese trabajo | No |
| Ang, Hodrick, Xing y Zhang (2006), *J. Finance* 61(1) | Sí (Crossref devuelve el working paper de NBER) | Es útil para la relación entre volatilidad y rendimientos | Sí (pendiente) |
| Izza, Ignatiev y Marques-Silva (2020), arXiv:2010.11034 | Sí | En el texto dice 2021 y en la lista 2020. Trata de explicabilidad | No |
| Shwartz-Ziv y Armon (2022), *Information Fusion* 81 | Sí, DOI 10.1016/j.inffus.2021.11.011 | En el texto dice 2021 y en la lista 2022 | Sí (pendiente) |
| Chen y Guestrin (2016), KDD | Sí, DOI 10.1145/2939672.2939785 | — | Sí (pendiente) |
| Prokhorenkova et al. (2018), NeurIPS 31 | NeurIPS no está en Crossref; el trabajo es conocido | — | Sí (pendiente) |
| Sharma (2018), "Academia.edu" | No se encontró | No es una publicación arbitrada. Se reemplaza por Sharpe y por Grinold y Kahn | No |
| Vaiz y Ramaswami (2016), *AJER* | No se encontró | Fuente débil | No |

**Citadas en el texto pero ausentes de la lista de la tarea:**
- **De Bondt y Thaler (1985):** existe, DOI 10.2307/2327804, y se usa.
- **Friedman (2001):** existe, DOI 10.1214/aos/1013203451, y se usa.
- **No se usan:** Kelley y Tetlock (2013), Barber et al. (2021), Grinold y Kahn (1999),
  Kidd (2011), Blatt (2004), Wilder (1978) y Sharpe (1964). Grinold y Kahn sí se usa,
  pero hay que confirmar la edición.

## Fuentes nuevas que pide el capítulo 5

Además de las listadas en el #30 para los capítulos 1–4 y 6, el capítulo 5 pide:
- Jegadeesh y Titman (1993);
- Gneiting y Raftery (2007);
- Sharpe (1966, 1994);
- Grinold y Kahn;
- Lo (2002);
- Gu, Kelly y Xiu (2020);
- Breiman (2001);
- Ke et al. (2017);
- Engle (1982) y Bollerslev (1986);
- Werge y Wintenberger (2022);
- Ansari et al. (2024, Chronos);
- White (2000);
- Novy-Marx y Velikov (2016);
- Barber y Odean (2008), Da, Engelberg y Gao (2011) y Moat et al. (2013), para RQ5;
- una referencia sobre portafolios por ordenamiento;
- las competencias M (M1, M3, M4 y M5).
