from pathlib import Path

import pandas as pd
import pytest

import collect
import quality
import transform

ROOT = Path(__file__).resolve().parents[1]


def raw_table(n=1200, **overrides):
    """A fake API answer with n stations (same columns as the real CSV)."""
    df = pd.DataFrame({
        "stationcode": [str(10000 + i) for i in range(n)],
        "name": [f"Station {i}" for i in range(n)],
        "is_installed": "OUI", "capacity": 20, "numdocksavailable": 12, "numbikesavailable": 8,
        "mechanical": 5, "ebike": 3, "is_renting": "OUI", "is_returning": "OUI",
        "duedate": "2026-01-15T10:00:00+00:00", "coordonnees_geo": "48.85, 2.35",
        "nom_arrondissement_communes": "Paris", "code_insee_commune": 75056, "station_opening_hours": None,
    })
    for k, v in overrides.items():
        df[k] = v
    return df


def snapshot(ts="2026-01-15T10:05:30+00:00", **overrides):
    return collect.normalise(raw_table(**overrides), snapshot_time=ts)


# ---------------------------------------------------------------- collect
def test_normalise_types_and_time():
    s = snapshot()
    assert s["snapshot_time"].iloc[0] == pd.Timestamp("2026-01-15 10:05:00+00:00")     # floored to the minute
    assert s["is_installed"].dtype == bool and s["is_installed"].all()
    assert s["lat"].iloc[0] == pytest.approx(48.85) and s["lon"].iloc[0] == pytest.approx(2.35)
    assert pd.api.types.is_string_dtype(s["stationcode"])


def test_oui_non_become_booleans():
    raw = raw_table()
    raw.loc[0, "is_renting"] = "NON"
    s = collect.normalise(raw, snapshot_time="2026-01-15T10:00:00+00:00")
    assert not s.loc[0, "is_renting"] and s.loc[1, "is_renting"]


def test_append_snapshot_is_idempotent_and_accumulates(tmp_path):
    a = snapshot("2026-01-15T10:00:00+00:00")
    b = snapshot("2026-01-15T11:00:00+00:00")
    p = collect.append_snapshot(a, tmp_path)
    collect.append_snapshot(a, tmp_path)                      # same snapshot twice -> no duplicates
    collect.append_snapshot(b, tmp_path)
    out = pd.read_parquet(p)
    assert out["snapshot_time"].nunique() == 2
    assert len(out) == 2 * len(a)
    assert p.name == "snapshots_2026-01-15.parquet"


# ---------------------------------------------------------------- quality
def test_quality_passes_on_good_data():
    report = quality.run_checks(snapshot())
    assert not quality.has_critical_failure(report)


def test_quality_catches_a_truncated_download():
    report = quality.run_checks(collect.normalise(raw_table(n=50), snapshot_time="2026-01-15T10:00:00+00:00"))
    assert quality.has_critical_failure(report)
    assert not report.set_index("check").loc["enough_stations", "ok"]


def test_quality_catches_nulls_and_negative_counts():
    s = snapshot()
    s.loc[0, "capacity"] = None
    assert quality.has_critical_failure(quality.run_checks(s))
    s2 = snapshot()
    s2.loc[3, "numbikesavailable"] = -1
    assert quality.has_critical_failure(quality.run_checks(s2))


def test_quality_only_warns_for_known_imperfections():
    s = snapshot()
    s.loc[0, "numbikesavailable"] = 25            # more bikes than capacity (happens in the real data)
    report = quality.run_checks(s)
    assert not quality.has_critical_failure(report)
    assert not report.set_index("check").loc["bikes_not_above_capacity", "ok"]


# ---------------------------------------------------------------- transform (SQL)
@pytest.fixture()
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    # Wednesday 10:00 and 11:00 in Paris (UTC+1), then a Saturday at 10:00
    for ts, bikes in [("2026-01-14T09:00:00+00:00", 0), ("2026-01-14T10:00:00+00:00", 20),
                      ("2026-01-17T09:00:00+00:00", 10)]:
        s = snapshot(ts)
        s.loc[0, "numbikesavailable"] = bikes
        s.loc[0, "numdocksavailable"] = 20 - bikes
        s.loc[1, "is_renting"] = False                         # station 1 is out of service
        s.loc[2, "capacity"] = 0                               # station 2 has a broken capacity
        collect.append_snapshot(s, d)
    return d


def test_staging_removes_out_of_service_and_broken_stations(raw_dir):
    con = transform.build(raw_dir)
    codes = {r[0] for r in con.execute("SELECT DISTINCT stationcode FROM stg_snapshots").fetchall()}
    assert "10001" not in codes and "10002" not in codes and "10000" in codes


def test_staging_uses_paris_local_time_and_weekend_flag(raw_dir):
    con = transform.build(raw_dir)
    rows = con.execute("SELECT local_hour, is_weekend FROM stg_snapshots WHERE stationcode = '10000' "
                       "ORDER BY snapshot_time").fetchall()
    assert rows == [(10, False), (11, False), (10, True)]


def test_reliability_shares(raw_dir):
    con = transform.build(raw_dir)
    r = con.execute("SELECT n_obs, share_empty, share_full, enough_data FROM mart_station_reliability "
                    "WHERE stationcode = '10000'").fetchone()
    assert r[0] == 3
    assert r[1] == pytest.approx(1 / 3) and r[2] == pytest.approx(1 / 3)
    assert r[3] is False                                       # only 3 observations -> flagged


def test_hour_profile_splits_weekday_and_weekend(raw_dir):
    con = transform.build(raw_dir)
    weekend = con.execute("SELECT avg_occupancy FROM mart_station_hour_profile WHERE stationcode = '10000' "
                          "AND is_weekend").fetchone()[0]
    assert weekend == pytest.approx(0.5)


def test_network_hourly_counts_snapshots(raw_dir):
    con = transform.build(raw_dir)
    n = con.execute("SELECT SUM(n_snapshots) FROM mart_network_hourly").fetchone()[0]
    assert n == 3


def test_marts_are_written_as_csv(raw_dir, tmp_path):
    transform.build(raw_dir, tmp_path / "marts")
    assert {p.name for p in (tmp_path / "marts").iterdir()} == {m + ".csv" for m in transform.MARTS}


def test_missing_raw_folder_gives_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        transform.build(tmp_path)


def test_dashboard_runs_on_the_sample_snapshot():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert len(at.metric) == 4
