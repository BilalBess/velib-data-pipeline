"""Data quality checks on a snapshot, written as code.
Critical checks stop the pipeline (the snapshot is not saved); warnings are only reported."""
import pandas as pd

MIN_STATIONS = 1000            # the network has about 1,500 stations
MAX_STALE_MINUTES = 60         # station data older than this is suspicious


def _row(name, level, ok, detail):
    return {"check": name, "level": level, "ok": bool(ok), "detail": detail}


def run_checks(df):
    rows = []
    rows.append(_row("enough_stations", "critical", len(df) >= MIN_STATIONS, f"{len(df)} stations"))
    dup = int(df.duplicated(["snapshot_time", "stationcode"]).sum())
    rows.append(_row("no_duplicate_station_per_snapshot", "critical", dup == 0, f"{dup} duplicates"))
    for col in ["stationcode", "capacity", "numbikesavailable", "numdocksavailable"]:
        n = int(df[col].isna().sum())
        rows.append(_row(f"no_nulls_in_{col}", "critical", n == 0, f"{n} nulls"))
    neg = int(((df["numbikesavailable"] < 0) | (df["numdocksavailable"] < 0)).sum())
    rows.append(_row("no_negative_counts", "critical", neg == 0, f"{neg} rows"))

    # warnings: known imperfections of the real data
    over = int((df["numbikesavailable"] > df["capacity"]).sum())
    rows.append(_row("bikes_not_above_capacity", "warning", over == 0, f"{over} stations"))
    zero_cap = int((df["capacity"] <= 0).sum())
    rows.append(_row("capacity_is_positive", "warning", zero_cap == 0, f"{zero_cap} stations"))
    gap = (df["numbikesavailable"] + df["numdocksavailable"] - df["capacity"]).abs()
    rows.append(_row("bikes_plus_docks_close_to_capacity", "warning", (gap > 3).mean() < 0.05,
                     f"{(gap > 3).mean():.1%} of stations differ by more than 3"))
    if "duedate" in df and df["duedate"].notna().any():
        age = (df["snapshot_time"].max() - df["duedate"].max()).total_seconds() / 60
        rows.append(_row("data_is_fresh", "warning", age <= MAX_STALE_MINUTES, f"newest station update {age:.0f} min old"))
    return pd.DataFrame(rows)


def has_critical_failure(report):
    return bool(((report["level"] == "critical") & (~report["ok"])).any())
