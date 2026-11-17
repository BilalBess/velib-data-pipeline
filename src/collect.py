"""Collect one snapshot of the Velib' network (all stations) and append it to a daily parquet file.

Source: Paris open data, dataset "velib-disponibilite-en-temps-reel" (updated about every minute).
Run:  python src/collect.py --out data/raw
"""
import argparse
import io
import sys
from pathlib import Path

import pandas as pd
import requests

import quality

URL = ("https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
       "velib-disponibilite-en-temps-reel/exports/csv?delimiter=%2C")

KEEP = ["snapshot_time", "stationcode", "name", "capacity", "numbikesavailable", "numdocksavailable",
        "mechanical", "ebike", "is_installed", "is_renting", "is_returning", "lat", "lon", "commune", "duedate"]


def fetch_csv(url=URL, timeout=60):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content))


def normalise(raw, snapshot_time=None):
    """Raw API table -> clean typed table with one row per station and a snapshot timestamp (UTC)."""
    df = raw.copy()
    snapshot_time = pd.Timestamp.now(tz="UTC") if snapshot_time is None else pd.Timestamp(snapshot_time)
    df["snapshot_time"] = snapshot_time.tz_convert("UTC").floor("min")
    for col in ["is_installed", "is_renting", "is_returning"]:
        df[col] = df[col].astype(str).str.upper().eq("OUI")       # "OUI" / "NON" -> True / False
    ll = df["coordonnees_geo"].astype(str).str.split(",", expand=True)
    df["lat"], df["lon"] = pd.to_numeric(ll[0], errors="coerce"), pd.to_numeric(ll[1], errors="coerce")
    df["commune"] = df["nom_arrondissement_communes"]
    df["duedate"] = pd.to_datetime(df["duedate"], utc=True, errors="coerce")
    df["stationcode"] = df["stationcode"].astype(str)
    return df[KEEP].drop_duplicates(["snapshot_time", "stationcode"]).reset_index(drop=True)


def append_snapshot(df, out_dir):
    """Add the snapshot to the parquet file of its day (one file per day keeps files small)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = df["snapshot_time"].iloc[0].strftime("%Y-%m-%d")
    path = out_dir / f"snapshots_{day}.parquet"
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df = df.drop_duplicates(["snapshot_time", "stationcode"], keep="last").sort_values(["snapshot_time", "stationcode"])
    df.to_parquet(path, index=False)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw", help="folder for the daily parquet files")
    args = ap.parse_args(argv)

    snap = normalise(fetch_csv())
    report = quality.run_checks(snap)
    print(report.to_string(index=False))
    if quality.has_critical_failure(report):
        print("Critical data quality failure: snapshot NOT saved.", file=sys.stderr)
        return 1
    path = append_snapshot(snap, args.out)
    print(f"saved {len(snap)} stations at {snap['snapshot_time'].iloc[0]} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
