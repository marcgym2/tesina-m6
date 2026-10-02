# sebrad/M6 (not vendored: fetched at a pinned commit)

- **Upstream:** <https://github.com/sebrad/M6>, commit
  `0c7d0dd41dbd6721a570e9f1dccb5ab0f77e0a86` (2023-03-22).
- **Author:** M6 team `7cb34dbb` ("SebastianR"), 3rd place in the forecasting track
  (upstream README).
- **License:** none declared. The code is therefore **not copied into this repository**;
  `fetch.sh` clones it into `vendor/sebrad/upstream/`, which git ignores.

## Notes relevant to the evaluation (from the upstream README and code)

- The published code is only the **final version**, used for submissions 8-12
  (from September 2022). Months 1-7 were made with earlier versions, so only months
  8-12 of period 1 can be reproduced.
- Point forecasts: a stack of linear models fitted on weekly data of the M6 universe
  **plus several hundred additional NASDAQ stocks and ETFs** (fixed lists in
  `data/*.qs`, compiled after the fact, so the training universe has survivorship bias).
  The author used Alpha Vantage for these during the competition; the published
  version downloads everything from Yahoo.
- Covariances from three years of daily data; 10,000 bootstrap draws of the covariance
  matrix with multivariate-t (4 df) simulation per forecast, which is slow.
- Produces forecasts only (rank probabilities); no investment decisions.
- `generate_rank_probabilities.r` checks the symbol order with `colnames(C)`, but `C`
  is not defined in the script and R resolves it to the base function `stats::C`, so
  the check is vacuous.
- R packages: data.table, matrixcalc, splines, mvtnorm, ISOweek, qs, quantmod, Matrix.
