"""Reproduction of the official M6 leaderboard (period 1).

Sources (Mcompetitions/M6-methods, commit 10c553f):

- ``IJF paper/Baseline for evaluating the hypotheses.R``: only active teams
  (``IsActive == 1``); monthly scores per team; DRE added at its last price when a
  window has 99 assets; global scores only for teams with a 1st-submission score,
  RPS = mean of the monthly RPS, IR = sum/sd of the pooled daily log returns.
- ``IJF paper/summary_leaderboard.xlsx``: quarterly scores follow the global rules
  over three months; teams enter a quarter when they are scored in its first month.
- Ranks, inferred from the leaderboard and matching it for every month, quarter and
  the global table: RPS rounded to 6 decimals, both ranks with ties averaged (R's
  default ``rank``), overall rank (OR) = mean of the two ranks, position = rank of
  OR with ties sharing the lowest position.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from tesina.evaluation.ir import information_ratio, portfolio_log_returns
from tesina.evaluation.prices import period_prices, period_returns
from tesina.evaluation.rps import quintile_targets, rps_per_asset


def _suffix(n: int) -> str:
    return {1: "st", 2: "nd", 3: "rd"}.get(n, "th")


MONTHS = [f"{n}{_suffix(n)} Submission" for n in range(1, 13)]
QUARTERS = {q: MONTHS[3 * (q - 1) : 3 * q] for q in range(1, 5)}
RPS_RANK_DECIMALS = 6


@dataclass
class Scores:
    """Per team and evaluation: RPS and the daily portfolio log returns."""

    rps: dict[tuple[str, str], float]
    log_returns: dict[tuple[str, str], pd.Series]
    fresh: dict[tuple[str, str], bool]  # submission made for this evaluation (not carried)

    def teams(self, evaluation: str) -> list[str]:
        return sorted(t for (t, e) in self.rps if e == evaluation)


def score_submissions(
    submissions: pd.DataFrame, prices: pd.DataFrame, calendar: pd.DataFrame
) -> Scores:
    """Score every active team in every evaluation of ``calendar``."""
    active = submissions[submissions["IsActive"] == 1]
    rps, log_returns, fresh = {}, {}, {}
    for period in calendar.itertuples():
        wide = period_prices(prices, period.base_date, period.end_date)
        targets = quintile_targets(period_returns(wide))
        subs = active[active["Evaluation"] == period.evaluation]
        for team, sub in subs.groupby("Team"):
            sub = sub.set_index("Symbol")
            key = (team, period.evaluation)
            rps[key] = float(rps_per_asset(sub, targets).mean())
            log_returns[key] = portfolio_log_returns(wide, sub["Decision"])
            fresh[key] = bool((sub["Submission"] == period.evaluation).all())
    return Scores(rps, log_returns, fresh)


def summarize(
    scores: Scores, evaluations: Sequence[str], zero_variance: float = np.nan
) -> pd.DataFrame:
    """Scores over one or several evaluations for the teams scored in the first one.

    Returns ``team``, ``rps`` (mean of the monthly RPS), ``ir`` (pooled daily log
    returns), ``returns`` (sum of daily log returns) and ``risk`` (their sd), the last
    two as in ``IR_calculation`` of the paper's baseline script.
    """
    rows = []
    for team in scores.teams(evaluations[0]):
        keys = [(team, e) for e in evaluations]
        if any(k not in scores.rps for k in keys):
            raise ValueError(f"team {team} is missing evaluations in {list(evaluations)}")
        pooled = pd.concat([scores.log_returns[k] for k in keys])
        rows.append(
            {
                "team": team,
                "rps": float(np.mean([scores.rps[k] for k in keys])),
                "ir": information_ratio(pooled, zero_variance=zero_variance),
                "returns": float(pooled.sum()),
                "risk": float(pooled.std(ddof=1)),
            }
        )
    return pd.DataFrame(rows)


def rank(table: pd.DataFrame) -> pd.DataFrame:
    """Add the official ranks: ``rps_rank``, ``ir_rank``, ``overall_rank``, ``position``."""
    out = table.copy()
    out["rps_rank"] = out["rps"].round(RPS_RANK_DECIMALS).rank(method="average")
    out["ir_rank"] = (-out["ir"]).rank(method="average")
    out["overall_rank"] = (out["rps_rank"] + out["ir_rank"]) / 2
    out["position"] = out["overall_rank"].rank(method="min").astype(int)
    return out.sort_values(["position", "team"]).reset_index(drop=True)


def leaderboard(
    scores: Scores, level: str, zero_variance: float = 1.0, ranked: bool = True
) -> pd.DataFrame:
    """Leaderboard for ``level`` in {"month", "quarter", "global"}.

    ``zero_variance=1.0`` reproduces the official leaderboard (decision D1); with
    ``np.nan`` (published code) some IR are NaN, so use ``ranked=False``. Month and
    quarter tables carry a ``period`` column (1-12 or 1-4).
    """
    finish = rank if ranked else (lambda table: table)
    if level == "global":
        return finish(summarize(scores, MONTHS, zero_variance))
    if level == "month":
        groups = {i: [e] for i, e in enumerate(MONTHS, start=1)}
    elif level == "quarter":
        groups = QUARTERS
    else:
        raise ValueError(f"unknown level {level!r}")
    tables = [
        finish(summarize(scores, evals, zero_variance)).assign(period=period)
        for period, evals in groups.items()
    ]
    return pd.concat(tables, ignore_index=True)


BENCHMARK_TEAM = "32cdcc24"  # organisers' benchmark submission (``Better than the benchmark.R``)


def paper_table4(
    scores: Scores, compare_to: str = "global", benchmark: str = BENCHMARK_TEAM
) -> pd.DataFrame:
    """Table 4 of Makridakis et al. (benchmark vs teams: returns, risk, IR).

    Follows ``IJF paper/Hypothesis1.R``: the teams are those of the global
    leaderboard whose global IR differs from the benchmark's (148 teams), IR with
    zero variance is NaN and ignored in means. With ``compare_to="global"`` (what the
    script does) each period's shares of teams "better than the benchmark" are
    computed against the benchmark's *global* returns, risk and IR, while the
    benchmark columns show the period's values. It also inherits an R quirk:
    ``tmp[tmp$IR > x, ]`` keeps rows where ``IR`` is NA, so a team with NaN IR counts
    as "better" (team bc4b0314, months 10-12). ``compare_to="period"`` compares each
    period with the benchmark of that same period and leaves NaN IR out of the share.
    """
    if compare_to not in ("global", "period"):
        raise ValueError(f"unknown compare_to {compare_to!r}")
    glob = summarize(scores, MONTHS).set_index("team")
    bench_global = glob.loc[benchmark]
    eligible = glob.index[~np.isclose(glob["ir"], bench_global["ir"], rtol=0, atol=1e-12)]
    rows = []
    for period in [*MONTHS, "Global"]:
        if period == "Global":
            table, bench = glob.loc[eligible], bench_global
        else:
            table = summarize(scores, [period]).set_index("team")
            table = table.loc[table.index.intersection(eligible)]
            bench = summarize(scores, [period]).set_index("team").loc[benchmark]
        ref = bench_global if compare_to == "global" else bench
        if compare_to == "global":
            better_ir = ((table["ir"] > ref["ir"]) | table["ir"].isna()).mean()
        else:
            better_ir = (table["ir"].dropna() > ref["ir"]).mean()
        rows.append(
            {
                "period": period,
                "n_teams": len(table),
                "better_returns_pct": 100 * float((table["returns"] > ref["returns"]).mean()),
                "better_risk_pct": 100 * float((table["risk"] < ref["risk"]).mean()),
                "better_ir_pct": 100 * float(better_ir),
                "bench_returns": bench["returns"],
                "bench_risk": bench["risk"],
                "bench_ir": bench["ir"],
                "mean_returns": table["returns"].mean(),
                "sd_returns": table["returns"].std(ddof=1),
                "mean_risk": table["risk"].mean(),
                "sd_risk": table["risk"].std(ddof=1),
                "mean_ir": table["ir"].mean(skipna=True),
                "sd_ir": table["ir"].std(ddof=1, skipna=True),
            }
        )
    return pd.DataFrame(rows)
