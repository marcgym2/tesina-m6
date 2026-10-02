"""Models run outside the thesis environment (M6 participants' code in vendor/<method>/).

``RScriptModel`` runs ``Rscript <script> <prices.csv> <origin> <out.csv>`` inside the
method's directory (where ``.Rprofile`` activates its renv); ``PythonScriptModel`` runs
``uv run --project <dir> python <script> ...`` in the method's own uv environment. The
prices file is built only from the history the walk-forward harness passes (dates up to
the origin), so the external code cannot see the future. The script must write a CSV
with columns ``ID`` and ``Rank1``..``Rank5``, and optionally ``Decision``.

Most participants' published code produces forecasts only (their investment decisions
were made by hand), so the weights are the M6 investment benchmark (1/n) unless
``decisions=True`` and the script writes its own ``Decision`` column.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from tesina.models import RANK_COLUMNS, Forecast
from tesina.models.baselines import equal_weights

ROUNDING_TOLERANCE = 1e-3  # residue allowed from rounded outputs (probabilities, weights)


@dataclass
class RScriptModel:
    name: str
    project_dir: Path
    script: str = "run.R"
    # Columns the method replaces with another series, e.g. {"VXX": "VIXY"} for FinQBoost.
    substitutes: dict[str, str] = field(default_factory=dict)
    # Auxiliary series written alongside the universe (e.g. an extended universe).
    extra_symbols: list[str] = field(default_factory=list)
    start: str | None = None  # first date written (e.g. "2007-01-01")
    rscript: str = "Rscript"
    timeout: int = 3600
    args: list[str] = field(default_factory=list)  # extra arguments after <out.csv>
    decisions: bool = False  # use the script's Decision column as weights

    def command(self) -> list[str]:
        if shutil.which(self.rscript) is None:
            raise RuntimeError(f"{self.rscript} not found")
        return [self.rscript, self.script]

    def prices_frame(self, history: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
        """Wide adjusted closes (forward-filled) exactly as handed to the R script."""
        wanted = set(universe) | set(self.substitutes.values()) | set(self.extra_symbols)
        h = history[history["symbol"].isin(wanted)]
        if self.start:
            h = h[h["date"] >= pd.Timestamp(self.start)]
        wide = h.pivot(index="date", columns="symbol", values="price")  # noqa: PD010
        wide = wide.sort_index().ffill()
        for target, source in self.substitutes.items():
            if source not in wide.columns:
                raise ValueError(f"substitute series {source} for {target} not in history")
            wide[target] = wide[source]
        keep = sorted(set(universe) | set(self.extra_symbols))
        return wide[keep]

    def forecast(self, history, universe, origin) -> Forecast:
        command = self.command()
        origin = pd.Timestamp(origin)
        wide = self.prices_frame(history[history["date"] <= origin], universe)
        with tempfile.TemporaryDirectory(prefix=f"{self.name}_") as tmp:
            prices_csv, out_csv = Path(tmp) / "prices.csv", Path(tmp) / "out.csv"
            wide.rename_axis("index").reset_index().to_csv(
                prices_csv, index=False, date_format="%Y-%m-%d"
            )
            subprocess.run(
                [
                    *command,
                    str(prices_csv),
                    origin.strftime("%Y-%m-%d"),
                    str(out_csv),
                    *self.args,
                ],
                cwd=self.project_dir,
                check=True,
                capture_output=True,
                timeout=self.timeout,
            )
            out = pd.read_csv(out_csv)
        out = out.set_index(out["ID"].astype(str))
        probs = out[RANK_COLUMNS].astype(float)
        missing = set(universe) - set(probs.index)
        if missing:
            raise ValueError(f"{self.name} returned no forecast for {sorted(missing)}")
        probs = probs.loc[universe]
        # Outputs are rounded (FinQBoost: 5 decimals); renormalise rounding residue only.
        total = probs.sum(axis=1)
        if np.abs(total - 1).max() > ROUNDING_TOLERANCE:
            raise ValueError(f"{self.name} probabilities do not sum to 1")
        probs = probs.div(total, axis=0)
        if self.decisions:
            weights = out.loc[universe, "Decision"].astype(float)
            gross = weights.abs().sum()
            # Rounded weights (wound-ignite: 5 decimals) can exceed the M6 cap of 1 by a
            # rounding residue; scale that residue away. Larger breaches stay invalid.
            if 1 < gross <= 1 + ROUNDING_TOLERANCE:
                weights = weights / gross
            return Forecast(probs, weights)
        return Forecast(probs, equal_weights(universe))


@dataclass
class PythonScriptModel(RScriptModel):
    """Same protocol as ``RScriptModel``, run with the method's own uv environment."""

    script: str = "run.py"
    uv: str = "uv"

    def command(self) -> list[str]:
        if shutil.which(self.uv) is None:
            raise RuntimeError(f"{self.uv} not found")
        project = str(self.project_dir)
        return [self.uv, "run", "--quiet", "--project", project, "python", self.script]
