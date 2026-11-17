-- Mart 3: network-level view by day and hour (what the operator would watch on a dashboard).

CREATE OR REPLACE TABLE mart_network_hourly AS
SELECT
    local_date,
    local_hour,
    COUNT(DISTINCT snapshot_time)                          AS n_snapshots,
    COUNT(DISTINCT stationcode)                            AS n_stations,
    ROUND(AVG(bikes), 2)                                   AS avg_bikes_per_station,
    ROUND(SUM(ebike) * 1.0 / NULLIF(SUM(bikes), 0), 3)     AS ebike_share,
    ROUND(AVG(CAST(is_empty AS INTEGER)), 4)               AS share_stations_empty,
    ROUND(AVG(CAST(is_full AS INTEGER)), 4)                AS share_stations_full,
    ROUND(AVG(occupancy), 4)                               AS avg_occupancy
FROM stg_snapshots
GROUP BY local_date, local_hour
ORDER BY local_date, local_hour;
