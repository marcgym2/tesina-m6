import numpy as np
import pytest

from tesina.analysis.correlation import correlation


def test_detects_negative_association():
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = -x + rng.normal(scale=0.5, size=200)
    r = correlation(x, y, n_boot=2000, n_perm=2000)
    assert r["estimate"] < -0.7
    assert r["ci_low"] < r["estimate"] < r["ci_high"] < 0
    assert r["p_perm"] < 0.01


def test_zero_correlation_has_interval_covering_zero():
    # Symmetric parabola: no monotonic association.
    x = np.linspace(-1, 1, 101)
    r = correlation(x, x**2, n_boot=2000, n_perm=2000)
    assert abs(r["estimate"]) < 0.01  # ties in x**2 shift Spearman slightly
    assert r["ci_low"] < 0 < r["ci_high"]
    assert r["p_perm"] > 0.5


def test_reproducible_and_drops_missing_pairs():
    x = np.array([1.0, 2, 3, 4, 5, 6, np.nan])
    y = np.array([2.0, 1, 4, 3, 6, 5, 7])
    a = correlation(x, y, n_boot=500, n_perm=500, seed=3)
    b = correlation(x, y, n_boot=500, n_perm=500, seed=3)
    assert a == b and a["n"] == 6


def test_pearson_and_validation():
    x = np.arange(10.0)
    assert correlation(x, 2 * x, "pearson", n_boot=200, n_perm=200)["estimate"] == pytest.approx(1)
    with pytest.raises(ValueError):
        correlation(x, x, "kendall")
    with pytest.raises(ValueError):
        correlation(x[:3], x[:3])
