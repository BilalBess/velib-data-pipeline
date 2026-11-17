"""Draw the latest snapshot as a map (used in the README)."""
from pathlib import Path

import matplotlib.pyplot as plt

import transform

ROOT = Path(__file__).resolve().parents[1]


def main(raw=ROOT / "data" / "sample"):
    con = transform.build(raw)
    d = con.execute("SELECT * FROM stg_snapshots WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM stg_snapshots)").df()
    d = d[(d.lat.between(48.80, 48.92)) & (d.lon.between(2.22, 2.47))]        # Paris + inner suburbs
    fig, ax = plt.subplots(figsize=(7, 6))
    sc = ax.scatter(d.lon, d.lat, c=d.occupancy, s=d.capacity / 2, cmap="RdYlGn", vmin=0, vmax=1, alpha=0.8)
    plt.colorbar(sc, label="Share of docks with a bike")
    ax.set_aspect(1 / 0.66)
    ax.set_title("Velib' stations: bike availability (one snapshot)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    fig.tight_layout()
    out = ROOT / "reports" / "figures" / "snapshot_map.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    print("saved", out)


if __name__ == "__main__":
    main()
