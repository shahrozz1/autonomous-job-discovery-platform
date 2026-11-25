-- Which skills do these jobs ask for, and how often is each one a must rather than a nice-to-have?
SELECT
    s.skill,
    COUNT(*)                                                         AS roles,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM open_roles), 1)   AS pct_of_roles,
    ROUND(100.0 * AVG(s.level = 'required'), 0)                      AS pct_required
FROM open_roles AS r
JOIN posting_skills AS s USING (posting_id)
GROUP BY s.skill
ORDER BY roles DESC, s.skill;
