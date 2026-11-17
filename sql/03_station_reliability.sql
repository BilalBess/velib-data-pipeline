-- Mart 2: how often is each station empty (no bike to take) or full (no dock to return a bike)?
-- Ranked inside its commune with a window function. Stations with few observations are flagged, not hidden.

CREATE OR REPLACE TABLE mart_station_reliability AS
WITH per_station AS (
    SELECT
        stationcode,
        ANY_VALUE(name)                          AS name,
        ANY_VALUE(commune)                       AS commune,
        ANY_VALUE(lat)                           AS lat,
        ANY_VALUE(lon)                           AS lon,
        ANY_VALUE(capacity)                      AS capacity,
        COUNT(*)                                 AS n_obs,
        AVG(CAST(is_empty AS INTEGER))           AS share_empty,
        AVG(CAST(is_full AS INTEGER))            AS share_full,
        AVG(occupancy)                           AS avg_occupancy
    FROM stg_snapshots
    GROUP BY stationcode
)
SELECT
    *,
    n_obs >= 24                                                       AS enough_data,
    RANK() OVER (PARTITION BY commune ORDER BY share_empty DESC)      AS rank_empty_in_commune,
    RANK() OVER (PARTITION BY commune ORDER BY share_full DESC)       AS rank_full_in_commune
FROM per_station;
