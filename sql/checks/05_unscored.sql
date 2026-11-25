-- severity: error
-- Every open posting gets a score from 0 to 100, a role and at least one market.
SELECT p.posting_id, p.title, p.score, p.role_id
FROM postings AS p
LEFT JOIN posting_markets AS m USING (posting_id)
WHERE p.closed_at IS NULL
GROUP BY p.posting_id
HAVING p.score IS NULL OR p.score NOT BETWEEN 0 AND 100 OR p.role_id IS NULL OR COUNT(m.market) = 0;
