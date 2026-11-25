-- None of these titles say "senior". How much experience do they actually ask for?
WITH labeled AS (
    SELECT
        family,
        CASE
            WHEN years_min IS NULL THEN 'Not stated'
            WHEN years_min = 0 THEN 'None'
            WHEN years_min >= 5 THEN '5+ years'
            ELSE years_min || '+ years'
        END AS experience,
        COALESCE(MIN(years_min, 5), 9) AS sort_order
    FROM open_roles
)
SELECT
    experience,
    COUNT(*)                                             AS roles,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_roles
FROM labeled
GROUP BY experience, sort_order
ORDER BY sort_order;
