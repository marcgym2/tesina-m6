# FinQBoost (vendored)

- **Upstream:** <https://github.com/miguel-data-sc/FinQBoost>, commit
  `107416ada472a1cde38f3aa72e8665edc4ca9116` (2023-02-20).
- **Author:** Miguel Pérez Michaus. M6 team `38c7fc7b` ("MP - Miguel Pérez Michaus"),
  2nd place in the forecasting track.
- **License:** GPL-3.0 (`upstream/LICENSE`). The files in `upstream/` are verbatim copies;
  any modification would be listed here.
- **Modifications:** none to the upstream code. `run.R` is a thin adapter written for
  this thesis that reproduces `MakeForecast.R` (origin date, DRE frozen from 2022-09-01)
  and runs `upstream/src/preprocess-and-forecast.R` in a temporary copy of the folder
  layout it expects.
- **R environment:** `renv.lock` (R 4.2.1). The author recommends data.table 1.14.4,
  roll 1.1.6, TTR 0.24.3 and xgboost 1.7.3.1 (`upstream/recommended_sessionInfo.txt`);
  building those exact versions from source failed here (RcppArmadillo, needed by
  roll, requires gfortran), so the lockfile pins the closest installed versions:
  data.table 1.17.0, roll 1.1.7, TTR 0.24.3, xgboost 1.7.7.1. Whether this changes the
  forecasts is checked against the team's actual submissions (issue #17).

## Notes relevant to the evaluation (from the upstream README and code)

- Needs adjusted daily closes **since 2007** (training uses all weekly data from
  2007-01-01) and VIXY prices in place of VXX (the author overwrote VXX with VIXY).
- Produces forecasts only; investment decisions were made by hand during the
  competition (all decisions are 0 in the output).
- The published feature set is the final one: the RSI feature was added from
  competition month 5 and the feature selection was tuned during 2022. Re-running it
  on period 1 therefore uses information from that same period (look-ahead); period 2
  is the clean out-of-sample test.
