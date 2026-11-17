"""Streamlit dashboard on the Velib' data collected by the pipeline.

Run:  streamlit run app.py                      (uses data/raw if it exists, else the sample snapshot)
      VELIB_RAW=path/to/raw streamlit run app.py
"""
import os
import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
import transform  # noqa: E402

ROOT = Path(__file__).parent
st.set_page_config(page_title="Velib' network", layout="wide")


@st.cache_data(ttl=300)
def load(raw_dir):
    con = transform.build(raw_dir)
    stg = con.execute("SELECT * FROM stg_snapshots").df()
    last = stg["snapshot_time"].max()
    return (stg[stg["snapshot_time"] == last], con.execute("SELECT * FROM mart_station_reliability").df(),
            con.execute("SELECT * FROM mart_station_hour_profile").df(),
            con.execute("SELECT * FROM mart_network_hourly").df(), stg["snapshot_time"].nunique(), last)


raw_dir = Path(os.environ.get("VELIB_RAW", ROOT / "data" / "raw"))
if not list(raw_dir.glob("snapshots_*.parquet")):
    raw_dir = ROOT / "data" / "sample"
now, rel, prof, net, n_snap, last = load(str(raw_dir))

st.title("Velib' network in Paris")
st.caption(f"{n_snap} snapshot(s) collected from the Paris open data API. Last one: "
           f"{last.tz_convert('Europe/Paris'):%d %b %Y %H:%M} (Paris time).")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stations in service", f"{len(now):,}")
c2.metric("Bikes available", f"{int(now['bikes'].sum()):,}", f"{now['ebike'].sum() / now['bikes'].sum():.0%} electric")
c3.metric("Stations empty", f"{now['is_empty'].mean():.1%}")
c4.metric("Stations full", f"{now['is_full'].mean():.1%}")

st.subheader("Where are the bikes right now?")
st.plotly_chart(px.scatter_map(now, lat="lat", lon="lon", color="occupancy", size="capacity", hover_name="name",
                               color_continuous_scale="RdYlGn", range_color=(0, 1), zoom=10.5, height=520),
                width="stretch")

if n_snap < 24:
    st.info(f"Only {n_snap} snapshot(s) so far. Reliability and hourly profiles need a few days of hourly "
            "collection to be meaningful (the GitHub Actions job keeps adding one snapshot per hour).")
else:
    left, right = st.columns(2)
    with left:
        st.subheader("Least reliable stations (often empty)")
        worst = rel[rel["enough_data"]].sort_values("share_empty", ascending=False).head(15)
        st.dataframe(worst[["name", "commune", "capacity", "n_obs", "share_empty", "share_full"]].round(3),
                     hide_index=True)
    with right:
        st.subheader("Network by hour of the day")
        h = net.groupby("local_hour")[["share_stations_empty", "share_stations_full"]].mean().reset_index()
        st.plotly_chart(px.line(h, x="local_hour", y=["share_stations_empty", "share_stations_full"]),
                        width="stretch")
    st.subheader("Typical day of one station")
    station = st.selectbox("Station", sorted(prof["name"].unique()))
    p = prof[prof["name"] == station].copy()
    p["day type"] = p["is_weekend"].map({False: "Weekday", True: "Weekend"})
    st.plotly_chart(px.line(p, x="local_hour", y="avg_occupancy", color="day type", range_y=(0, 1)),
                    width="stretch")
