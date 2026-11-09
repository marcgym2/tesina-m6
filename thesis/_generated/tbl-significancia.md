| Modelo | Dif. RPS, periodo 1 | p (Holm) | Dif. RPS, periodo 2 | IC 95 % bootstrap | Periodos mejores | p (Holm)  |
|---|---:|---:|---:|---:|---:|---:|
| Frecuencia histórica | −0.00152 | 0.507 | −0.00365 | [−0.00514, −0.00212] | 73 % | < 0.001 |
| FinQBoost | −0.00348 | < 0.001 | −0.00441 | [−0.00478, −0.00402] | 100 % | < 0.001 |
| wound-ignite | −0.00214 | 0.106 | −0.00422 | [−0.00476, −0.00367] | 98 % | < 0.001 |
| AdaGaussMC (según el artículo) | −0.00175 | 0.223 | −0.00375 | [−0.00468, −0.00275] | 84 % | < 0.001 |
| GBM multiclase | −0.00269 | 0.057 | −0.00406 | [−0.00489, −0.00324] | 90 % | < 0.001 |
| Simulación desde covarianzas | −0.00402 | < 0.001 | −0.00485 | [−0.00542, −0.00424] | 98 % | < 0.001 |
| TimesFM-3 | 0.00884 | 0.953 | 0.00345 | [0.00112, 0.00609] | 33 % | 0.994 |

: Diferencia media de RPS de cada modelo contra el pronóstico uniforme (negativa = mejor que el uniforme), con la prueba de Diebold y Mariano ajustada por Holm. {#tbl-significancia}
