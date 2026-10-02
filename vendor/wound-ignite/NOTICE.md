# wound-ignite (vendored)

- **Upstream:** <https://github.com/MarcoGorelli/wound-ignite>, commit
  `b06fba58be9c5d7730e268ebbf02c787db80253f` (2023-01-16, last commit). The Kaggle
  notebooks installed the library at commit `8d8e5c6` (2022-11-12). The `precise/` package
  is identical in both commits.
- **Author:** Marco Gorelli. M6 team `bc4b0314`. According to the upstream README, it won
  second place in Q1 (US$6,000).
- **What it is:** a fork of Peter Cotton's `precise` library
  (<https://github.com/microprediction/precise>), plus the Kaggle notebooks the author ran
  every month.
- **License:** MIT (`upstream/LICENSE`, copyright 2021 Peter Cotton).

## What was copied

`upstream/` is a verbatim subset of the commit above, obtained with `git archive`:
- the `precise/` package and `setup.py`;
- the workflow notebooks (`notebooks/`, `cv-results/`, `check-naive-cv/`,
  `find-best-from-cv/`, `combine/`, `submit/`, `final-check/`, `yfinance-data/`);
- `how-to-submit.md`, `generate_dre.py`, `get_tickers.py`, `README.md` and `LICENSE`.

Left out: images, a PDF, the scraping folders and examples unrelated to the M6. No
upstream file was modified.

## Environment

`pyproject.toml` + `uv.lock` (Python 3.12) is separate from the thesis environment:
`uv sync --project vendor/wound-ignite`.

The author ran this in Kaggle in 2022, with versions that were not recorded. With current
versions, ortools (pulled in by `seriate`) loads HiGHS symbols from `highspy`, and only
works with `highspy==1.12.0`.

## The author's method (from the code and `how-to-submit.md`)

Each month:

1. **Backtest.** Over the previous three four-week periods, generate an entry for each
   combination of covariance estimator (`ALL_D0_SKATERS`, 76; 10 excluded), portfolio
   constructor (`PORT`, 23) and weight scaling. Data came from Yahoo through a cache on
   Kaggle.
   - Each entry estimates the covariance with the last **200 daily returns** and
     simulates 5,000 Gaussian scenarios with mean zero. The quintile probabilities are the
     frequencies.
   - The portfolio comes from the constructor.
2. **Selection.** Keep the combinations whose RPS stays below 0.1598 in all three
   periods and whose IR is at least that of a naive portfolio in each of them. The
   notebook itself says the thresholds were adjusted by hand ("tighten or loosen").
3. **Combination.** Average the forecasts and weights of the selected combinations for
   the new period.

The selection results (`final_candidates.csv`) lived on Kaggle and are not in the repo.
The only committed configuration is the last one: "month 11", commit `c26cbc6`, with the
eight skaters `BEST_F = [7, 21, 6, 23, 8, 61, 53, 22]`, portfolio `PORT[0]` and scaling 1.

## Adapter (`run.py`)

`run.py` reproduces that last configuration for a single origin: `m6_competition_entry`
for each skater, followed by the `combine` and `submit` notebooks. The adaptations are:

- **Universe.** `m6_data` hard-codes the 100 tickers and reads per-ticker CSVs from a
  cache. It is replaced by the same logic over the universe passed in (needed for D2's 99
  and 98 assets in period 2). Its padding of short series (repeating prices) is kept.
- **Seed.** The upstream Monte Carlo has no seed. `--seed` makes runs reproducible.
- **DRE.** `--constant-dre` reproduces `generate_dre.py`, which, from month 10, replaced
  DRE by a constant price.

It returns the quintile probabilities and the method's own weights (`Decision`).

## Notes for the evaluation

- **Months where the team did not follow the code.** The submissions
  (`results/wound_ignite_p1/`, `team_months.csv`) show that the method was only used in
  part of period 1:
  - months 7–9, 11 and 12 are uniform or almost uniform;
  - from month 10 the team put 100% of its weight on DRE (decision D1).

  Those months cannot come from the code.
- **Selection not reproducible.** Months 4–10 used the monthly selection, whose results
  are not in the repo. Moreover, months 1–6 need prices from before 2022 (200 daily
  returns plus three backtest periods), which the official M6 data do not have (#12).
- **Period 2.** Which configuration to run (the last committed one, or the monthly
  selection rule) is decided in the `decision` issue opened with this PR.
