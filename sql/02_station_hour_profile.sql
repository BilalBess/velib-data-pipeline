-- Mart 1: typical occupancy of each station by hour of the day (weekday vs weekend).

CREATE OR REPLACE TABLE mart_station_hour_profile AS
SELECT
    stationcode,
    ANY_VALUE(name)                 AS name,
    ANY_VALUE(lat)                  AS lat,
    ANY_VALUE(lon)                  AS lon,
    is_weekend,
    local_hour,
    COUNT(*)                        AS n_obs,
    ROUND(AVG(occupancy), 3)        AS avg_occupancy,
    ROUND(AVG(bikes), 2)            AS avg_bikes,
    ROUND(AVG(CAST(is_empty AS INTEGER)), 3) AS share_empty,
    ROUND(AVG(CAST(is_full AS INTEGER)), 3)  AS share_full
FROM stg_snapshots
GROUP BY stationcode, is_weekend, local_hour;
