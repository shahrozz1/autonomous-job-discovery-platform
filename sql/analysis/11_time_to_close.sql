-- How long postings stay up before the company takes them down. Fills in as runs accumulate.
WITH closed AS (
    SELECT
        family,
        JULIANDAY(closed_at) - JULIANDAY(posted_at) AS days
    FROM postings
    WHERE closed_at IS NOT NULL AND posted_at IS NOT NULL
),
ordered AS (
    SELECT
        family,
        days,
        ROW_NUMBER() OVER (PARTITION BY family ORDER BY days) AS place,
        COUNT(*) OVER (PARTITION BY family)                   AS n
    FROM closed
)
SELECT family, n AS closed_postings, ROUND(AVG(days)) AS median_days_open
FROM ordered
WHERE place IN ((n + 1) / 2, (n + 2) / 2)
GROUP BY family, n
ORDER BY median_days_open;
