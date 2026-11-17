-- Staging: clean snapshots, one row per station and snapshot, with local Paris time and simple flags.
-- {{RAW_GLOB}} is replaced by the path of the parquet files.

CREATE OR REPLACE TABLE stg_snapshots AS
SELECT
    snapshot_time,
    CAST(snapshot_time AT TIME ZONE 'Europe/Paris' AS TIMESTAMP)           AS local_time,
    CAST(CAST(snapshot_time AT TIME ZONE 'Europe/Paris' AS TIMESTAMP) AS DATE) AS local_date,
    HOUR(CAST(snapshot_time AT TIME ZONE 'Europe/Paris' AS TIMESTAMP))     AS local_hour,
    ISODOW(CAST(snapshot_time AT TIME ZONE 'Europe/Paris' AS TIMESTAMP)) >= 6 AS is_weekend,
    stationcode,
    name,
    commune,
    lat,
    lon,
    capacity,
    numbikesavailable                                                      AS bikes,
    numdocksavailable                                                      AS docks,
    mechanical,
    ebike,
    numbikesavailable = 0                                                  AS is_empty,
    numdocksavailable = 0                                                  AS is_full,
    LEAST(numbikesavailable * 1.0 / capacity, 1.0)                         AS occupancy
FROM read_parquet('{{RAW_GLOB}}')
WHERE is_installed
  AND is_renting
  AND is_returning                      -- a station that is closed is not "empty", it is out of service
  AND capacity > 0
  AND numbikesavailable <= capacity + 2 -- a few stations report more bikes than docks
  AND numbikesavailable >= 0
  AND numdocksavailable >= 0;
