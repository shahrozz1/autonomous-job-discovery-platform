-- What does each extra year of required experience pay? Median of each job's midpoint.
-- (SQLite has no MEDIAN, so the middle row or two are picked with window functions.)
WITH pay AS (
    SELECT
        MIN(years_min, 5)           AS years,
        (pay_min + pay_max) / 2.0   AS midpoint
    FROM open_roles
    WHERE pay_min IS NOT NULL AND years_min IS NOT NULL
),
ordered AS (
    SELECT
        years,
        midpoint,
        ROW_NUMBER() OVER (PARTITION BY years ORDER BY midpoint) AS place,
        COUNT(*) OVER (PARTITION BY years)                       AS n
    FROM pay
)
SELECT
    CASE years WHEN 0 THEN 'None' WHEN 5 THEN '5+ years' ELSE years || '+ years' END AS experience,
    n                                                                               AS roles,
    ROUND(AVG(midpoint))                                                            AS median_pay
FROM ordered
WHERE place IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY years, n
ORDER BY years;
