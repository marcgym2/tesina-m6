| Paso | Dif. RPS | p | IR | Sharpe anual | Rotación media |
|---|---:|---:|---:|---:|---:|
| Ingenuo | −0.00264 | < 0.001 | 124.8 | 2.05 | 126 % |
| + split temporal | −0.00172 | < 0.001 | 88.0 | 1.45 | 126 % |
| + purga de etiquetas | −0.00036 | 0.117 | 31.5 | 0.52 | 124 % |
| + preprocesamiento solo con el pasado | −0.00415 | < 0.001 | 59.6 | 0.98 | 87 % |
| + selección honesta | −0.00391 | < 0.001 | 50.8 | 0.84 | 95 % |
| + universo point-in-time | −0.00406 | < 0.001 | 61.2 | 1.01 | 94 % |
| + costos de transacción | −0.00406 | < 0.001 | 51.2 | 0.84 | 94 % |

: Cascada de sesgos sobre el gradient boosting en el periodo 2. Cada paso agrega una corrección a las anteriores. La diferencia de RPS es contra el uniforme en el mismo universo; el último paso es neto de costos. {#tbl-cascada-resultados}
