"""Bias cascade building blocks (issues #24, #25): each naive step leaks as intended and
the corrected ones do not."""

import numpy as np
import pandas as pd

from tesina import cascade as cs
from tesina.data import m6
from tesina.models.gbm import FEATURES

GRID = {"num_leaves": [3], "min_data_in_leaf": [20]}


def prices(n_assets=12, seed=0, end="2021-12-31"):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2019-01-01", end)
    symbols = [f"S{i:02d}" for i in range(n_assets)]
    paths = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(days), n_assets)), axis=0))
    df = pd.DataFrame(paths, index=days, columns=symbols)
    long = df.rename_axis("date").reset_index().melt(id_vars="date", var_name="symbol")
    return long.rename(columns={"value": "price"}), symbols


def test_survivors_universe_swaps_delisted_assets_for_their_successors():
    assets = sorted(m6.load_template()["ID"])
    survivors = cs.survivors_universe(assets)
    assert len(survivors) == 99
    assert {"PLD", "VMRK"} <= set(survivors)
    assert not {"DRE", "WRK", "AVB", "SW"} & set(survivors)


def test_naive_features_depend_on_the_future_and_clean_ones_do_not():
    p, symbols = prices()
    wide = cs.to_wide(p, symbols)
    date = pd.Timestamp("2020-06-01")
    later = wide.copy()
    later.loc[later.index > "2021-01-01"] *= 3
    a, b = cs.naive_features(wide), cs.naive_features(later)
    assert not np.allclose(a["ret_20"].loc[date], b["ret_20"].loc[date])
    c, d = cs.cross_sectional_features(wide), cs.cross_sectional_features(later)
    pd.testing.assert_series_equal(c["ret_20"].loc[date], d["ret_20"].loc[date])


def test_weekly_labels_overlap_and_can_run_past_an_origin():
    p, symbols = prices()
    wide = cs.to_wide(p, symbols)
    origin = pd.Timestamp("2021-06-04")
    data = cs.weekly_dataset(wide, cs.naive_features(wide), [origin])
    before = data[data["base"] < origin]
    assert (before["end"] > origin).any()  # s1: unpurged labels use prices after the origin
    assert origin in set(data["base"])
    windows = cs.window_dataset(wide, cs.cross_sectional_features(wide), origin)
    assert (windows["end"] <= origin).all()  # s2: purged


def test_kfold_gives_every_origin_asset_an_out_of_fold_forecast():
    p, symbols = prices()
    wide = cs.to_wide(p, symbols)
    origins = [pd.Timestamp("2021-06-04"), pd.Timestamp("2021-07-02")]
    data = cs.weekly_dataset(wide, cs.naive_features(wide), origins)
    out = cs.kfold_forecasts(data, origins, grid=GRID, k=3, threads=1)
    assert set(out) == {(0, r) for r in cs.ROUNDS}
    for o in origins:
        probs = out[(0, cs.ROUNDS[0])][o]
        assert sorted(probs.index) == symbols
        np.testing.assert_allclose(probs.sum(axis=1), 1)


def test_walk_forward_forecasts_and_ex_post_selection():
    p, symbols = prices()
    wide = cs.to_wide(p, symbols)
    clean = cs.cross_sectional_features(wide)
    origins = [pd.Timestamp("2021-06-04")]
    out = cs.walk_forward_forecasts(
        lambda o: cs.window_dataset(wide, clean, o),
        lambda o: cs.origin_rows(clean, o, symbols),
        origins,
        grid=GRID,
        threads=1,
    )
    assert list(out[(0, 50)][origins[0]].index) == symbols
    scores = {(0, 50): 0.17, (0, 100): 0.15, (0, 200): 0.16}
    best, table = cs.select_ex_post(out, lambda f: scores[next(k for k in out if out[k] is f)])
    assert best == (0, 100) and len(table) == 3
    assert list(cs.origin_rows(clean, origins[0], symbols).columns) == ["symbol", *FEATURES]
