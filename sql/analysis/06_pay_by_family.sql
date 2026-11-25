-- Pay in each job family: the middle half of midpoints (25th to 75th percentile) and the median.
WITH pay AS (
    SELECT
        family,
        (pay_min + pay_max) / 2.0                                                          AS midpoint,
        PERCENT_RANK() OVER (PARTITION BY family ORDER BY (pay_min + pay_max) / 2.0)       AS pr,
        COUNT(*) OVER (PARTITION BY family)                                                AS n
    FROM open_roles
    WHERE pay_min IS NOT NULL
)
SELECT
    family,
    n                                                   AS roles_with_pay,
    ROUND(MAX(CASE WHEN pr <= 0.25 THEN midpoint END))  AS p25,
    ROUND(MAX(CASE WHEN pr <= 0.50 THEN midpoint END))  AS median_pay,
    ROUND(MAX(CASE WHEN pr <= 0.75 THEN midpoint END))  AS p75
FROM pay
GROUP BY family, n
ORDER BY median_pay DESC;
