import json

import pandas as pd
import pytest

from tesina.data import m6


def test_snapshot_matches_manifest_hashes():
    m6.verify()


def test_manifest_records_upstream_provenance():
    snap = next(
        s for s in json.loads(m6.MANIFEST.read_text())["snapshots"] if s["name"] == "m6_official"
    )
    assert snap["source"] == "https://github.com/Mcompetitions/M6-methods"
    assert len(snap["commit"]) == 40
    for entry in snap["files"]:
        assert entry["in_git"]
        assert len(entry["upstream_git_blob"]) == 40
        assert (m6.REPO_ROOT / entry["path"]).exists()


def test_assets_universe_and_dates():
    assets = m6.load_assets()
    assert assets["symbol"].nunique() == 100
    assert assets["date"].min() == pd.Timestamp("2022-01-31")
    assert assets["date"].max() == pd.Timestamp("2023-02-17")
    assert assets["price"].gt(0).all()
    assert not assets.duplicated(["symbol", "date"]).any()


def test_submissions_structure():
    subs = m6.load_submissions()
    assert len(subs) == 275_200
    assert subs["Team"].nunique() == 251
    assert set(subs["Evaluation"]) == set(m6.EVALUATIONS)
    assert (subs.groupby(["Team", "Evaluation"])["Symbol"].nunique() == 100).all()
    probs = subs[m6.RANK_COLUMNS].sum(axis=1)
    assert probs.sub(1).abs().max() < 1e-9
    gross = subs.groupby(["Team", "Evaluation"])["Decision"].apply(lambda w: w.abs().sum())
    assert gross.between(0.25 - 1e-9, 1 + 1e-9).all()


def test_submission_symbols_match_asset_universe():
    assert set(m6.load_submissions()["Symbol"]) == set(m6.load_assets()["symbol"])


def test_template_is_uniform_benchmark():
    t = m6.load_template()
    assert len(t) == 100
    assert (t[m6.RANK_COLUMNS] == 0.2).all().all()
    assert (t["Decision"] == 0.01).all()


def test_unknown_snapshot_date_raises():
    with pytest.raises(FileNotFoundError):
        m6.snapshot_files("1999-01-01")
