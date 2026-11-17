"""Build the analytical tables (marts) from the raw daily parquet files, with DuckDB SQL.

Run:  python src/transform.py --raw data/raw --out data/marts
"""
import argparse
from pathlib import Path

import duckdb

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
MARTS = ["mart_station_hour_profile", "mart_station_reliability", "mart_network_hourly"]


def build(raw_dir, out_dir=None):
    """Run the SQL files in order. Returns the DuckDB connection (tables stay in memory).
    If out_dir is given, each mart is also written as a csv file."""
    raw_dir = Path(raw_dir)
    if not list(raw_dir.glob("snapshots_*.parquet")):
        raise FileNotFoundError(f"no snapshots_*.parquet file in {raw_dir}")
    con = duckdb.connect()
    glob = str(raw_dir / "snapshots_*.parquet")
    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        con.execute(sql_file.read_text().replace("{{RAW_GLOB}}", glob))
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for mart in MARTS:
            con.execute(f"COPY {mart} TO '{out_dir / (mart + '.csv')}' (HEADER, DELIMITER ',')")
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data/marts")
    args = ap.parse_args()
    con = build(args.raw, args.out)
    n_snap = con.execute("SELECT COUNT(DISTINCT snapshot_time) FROM stg_snapshots").fetchone()[0]
    n_rows = con.execute("SELECT COUNT(*) FROM stg_snapshots").fetchone()[0]
    print(f"{n_snap} snapshots, {n_rows} clean station rows -> marts written in {args.out}")


if __name__ == "__main__":
    main()
