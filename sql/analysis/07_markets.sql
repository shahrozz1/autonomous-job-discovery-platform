-- Where the jobs are, how many are within reach, and whether companies there show pay.
-- A job listed in several places counts in each one.
WITH role_markets AS (
    SELECT DISTINCT p.role_id, m.market
    FROM postings AS p
    JOIN posting_markets AS m USING (posting_id)
    WHERE p.closed_at IS NULL
)
SELECT
    m.market,
    COUNT(*)                                                                AS roles,
    SUM(r.years_min <= 2)                                                   AS two_years_or_less,
    ROUND(100.0 * AVG(r.pay_min IS NOT NULL), 0)                            AS pct_show_pay,
    SUM(r.posted_at >= DATE((SELECT MAX(run_date) FROM runs), '-14 days'))  AS posted_last_14_days
FROM open_roles AS r
JOIN role_markets AS m USING (role_id)
GROUP BY m.market
ORDER BY roles DESC;
