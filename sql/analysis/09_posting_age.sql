-- How long have these jobs been up? Old postings are often evergreen listings or already filled.
WITH aged AS (
    SELECT
        JULIANDAY((SELECT MAX(run_date) FROM runs)) - JULIANDAY(posted_at) AS days
    FROM open_roles
    WHERE posted_at IS NOT NULL
)
SELECT
    CASE
        WHEN days <= 7 THEN '1 week or less'
        WHEN days <= 30 THEN '1 to 4 weeks'
        WHEN days <= 90 THEN '1 to 3 months'
        WHEN days <= 180 THEN '3 to 6 months'
        ELSE 'Over 6 months'
    END                                                  AS age,
    COUNT(*)                                             AS roles,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS pct_of_roles
FROM aged
GROUP BY age
ORDER BY MIN(days);
