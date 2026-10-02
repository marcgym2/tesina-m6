# AdaGaussMC: AdaVol (vendored) and reimplementation from the paper

- **Team:** AdaGaussMC_STU, M6 team `b1002bc9` (Joseph de Vilmarest and Nicklas Werge).
  - Leaderboard: 5th in the forecasting task, 42nd in decisions and 7th overall
    (`data/raw/m6_official/summary_leaderboard_*`). These match section 5 of the paper.
- **Paper:** de Vilmarest and Werge, arXiv:2303.01855v2 (2024-06-03), sections 2 and 4.
  - The published version is in IJF. A link to ScienceDirect with identifier (pii)
    `S0169207024000554` turned up.
    <!-- Marco: confirm the DOI against that page when adding it to Zotero; it was not verified. -->
- **Public code.** The team's pipeline for the M6 was not published. The paper only links
  to the implementation of AdaVol, the volatility model the method uses:
  <https://github.com/nicklaswerge/AdaVol>, commit
  `2c4db572980401f2ea5a341ce69aa6761a6dff3d` (2024-01-03), license GPL-3.0 (`LICENSE`).

## `adavol.py` (GPL-3.0)

The functions `adavol`, `proj_l1ball`, `euclidean_proj_l1ball` and
`euclidean_proj_simplex` were extracted from that commit's notebook. Modifications:

1. Plotting and data download removed.
2. NumPy 2 compatibility: `np.alltrue` → `np.all`, and `.item()` when assigning
   `sigma2_hat[0]`.
3. **Simplex projection fixed.** The notebook copies a gist that divides the threshold by
   `rho` (a 0-based index) instead of `rho + 1`, the number of positive components, as in
   Duchi et al. (2008), which the gist itself cites.
   - With a single positive component it divides by zero and the parameters collapse to
     zero.
   - The fix makes it the Euclidean projection that the AdaVol paper specifies.
   - `tests/test_adagaussmc.py` checks it.
4. `adavol` also returns the next-day variance forecast. The notebook computes it but does
   not return it.

The AdaVol recursion is unchanged.

## Reimplementation (`src/tesina/models/adagaussmc.py`)

| Step | Paper | Here |
|---|---|---|
| Classes | Table 1: stocks, ETF equities, fixed income, commodities, volatility (VXX) | Same, by symbol |
| Mean | Mean daily log return of the class, 2015–2020 (sec. 2, 4.1) | Same, fixed |
| Volatility | AdaVol on the returns minus the class mean; σ held fixed over the horizon (sec. 4.1) | GARCH(1,1), η = 0.1, θ₀ = (0.05, 0.90) (notebook values), from 2015 to the origin |
| VXX | "Empirical distribution of its past returns" (sec. 4.1) | Sum of 20 daily returns drawn from 2015 to the origin |
| Joint distribution | Independent assets for the forecasting task (sec. 4.1) | Same |
| Probabilities | ADAM on the expected RPS (sec. 4.2) | Monte Carlo frequencies of the quintiles. The RPS is quadratic, so the optimum of the expected RPS is the expected outcome (sec. 2); ADAM converges to that point |
| Weights | Correlated Gaussian returns and ADAM on the expected IR (sec. 4.1–4.2) | **Not reproduced**: the paper does not give the correlation estimator or the optimiser settings. 1/n benchmark |

**Fidelity gaps:**
- p = q = 1 and θ₀: the paper says "in its simplest form, AdaVol is GARCH-like". We used
  the notebook's values (p = q = 1, θ₀ = (0.05, 0.90)).
- The start of AdaVol's history: we used 2015, the year the class-mean window starts.
- The VXX window: section 4.1 does not fix it. We used everything from 2015 to the origin.
- Fallbacks for short histories (fewer than 20 returns): the class's median variance; for
  VXX, the largest variance.

Fidelity against the team's submissions is checked in period 1 with
`experiments/adagaussmc/`. That needs the 2015–2021 prices from #12.
