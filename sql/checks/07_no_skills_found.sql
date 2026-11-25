-- severity: warning
-- A few postings list no tools at all. A lot of them would mean the skill rules broke.
SELECT COUNT(*) AS without_skills, (SELECT COUNT(*) FROM open_roles) AS open_roles
FROM open_roles AS r
WHERE NOT EXISTS (SELECT 1 FROM posting_skills AS s WHERE s.posting_id = r.posting_id)
HAVING COUNT(*) > 0.2 * (SELECT COUNT(*) FROM open_roles);
