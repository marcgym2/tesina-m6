import numpy as np
import pytest
from scipy import stats

from tesina.analysis.significance import adjust_pvalues, block_bootstrap, diebold_mariano


def test_dm_matches_hand_computation_h1():
    d = np.array([-0.01, -0.02, 0.005, -0.015, -0.01, 0.0, -0.02, -0.005])
    n = len(d)
    se = np.sqrt(((d - d.mean()) ** 2).mean() / n)
    hln = np.sqrt((n + 1 - 2) / n)
    expected = d.mean() / se * hln
    r = diebold_mariano(d)
    assert r["dm_stat"] == pytest.approx(expected)
    assert r["p_value"] == pytest.approx(stats.t.cdf(expected, n - 1))
    assert r["p_value"] < 0.05


def test_dm_alternatives_and_zero_differential():
    d = np.array([0.01, 0.02, 0.0, 0.015, 0.01])
    assert diebold_mariano(d, alternative="less")["p_value"] > 0.9
    assert diebold_mariano(d, alternative="greater")["p_value"] < 0.05
    two = diebold_mariano(d, alternative="two-sided")["p_value"]
    assert two == pytest.approx(2 * diebold_mariano(d, alternative="greater")["p_value"])
    zero = diebold_mariano(np.zeros(12))
    assert np.isnan(zero["dm_stat"]) and zero["p_value"] == 1.0


def test_dm_uses_autocovariances_up_to_h_minus_1():
    d = np.array([-0.01, -0.012, -0.008, -0.011, -0.009, -0.013, -0.007, -0.01, -0.012, -0.009])
    assert diebold_mariano(d, h=2)["dm_stat"] != diebold_mariano(d, h=1)["dm_stat"]


def test_block_bootstrap():
    rng = np.random.default_rng(0)
    better = -0.01 + rng.normal(0, 0.005, 24)
    r = block_bootstrap(better, block=2, n_boot=4000, seed=1)
    assert r["p_boot"] < 0.01 and r["ci_high"] < 0
    noise = np.array([0.01, -0.01] * 6)
    assert block_bootstrap(noise, n_boot=4000)["p_boot"] > 0.3
    assert block_bootstrap(np.zeros(12))["p_boot"] == 1.0
    assert block_bootstrap(better, seed=5) == block_bootstrap(better, seed=5)


def test_adjust_pvalues():
    p = np.array([0.01, 0.04, 0.03, 0.005])
    np.testing.assert_allclose(adjust_pvalues(p, "holm"), [0.03, 0.06, 0.06, 0.02])
    np.testing.assert_allclose(adjust_pvalues(p, "bh"), [0.02, 0.04, 0.04, 0.02])
    with pytest.raises(ValueError):
        adjust_pvalues(p, "bonferroni")
