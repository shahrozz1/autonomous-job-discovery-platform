-- severity: error
-- Duplicates are only ever grouped within one company.
SELECT p.role_id, COUNT(DISTINCT LOWER(b.company)) AS companies
FROM postings AS p
JOIN boards AS b USING (board_id)
GROUP BY p.role_id
HAVING COUNT(DISTINCT LOWER(b.company)) > 1;
