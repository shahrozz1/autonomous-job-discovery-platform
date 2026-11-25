-- Which skills travel together? Lift compares how often two skills appear in the same posting with
-- how often that would happen by chance (1.0 = chance, 3.0 = three times as often).
WITH totals AS (
    SELECT COUNT(*) AS roles FROM open_roles
),
skill_count AS (
    SELECT s.skill, COUNT(*) AS n
    FROM open_roles AS r
    JOIN posting_skills AS s USING (posting_id)
    GROUP BY s.skill
),
pairs AS (
    SELECT a.skill AS skill_a, b.skill AS skill_b, COUNT(*) AS together
    FROM open_roles AS r
    JOIN posting_skills AS a USING (posting_id)
    JOIN posting_skills AS b ON b.posting_id = a.posting_id AND b.skill > a.skill
    GROUP BY a.skill, b.skill
    HAVING COUNT(*) >= 10
)
SELECT
    p.skill_a,
    p.skill_b,
    p.together                                              AS roles,
    ROUND(1.0 * p.together * t.roles / (a.n * b.n), 1)      AS lift
FROM pairs AS p
JOIN skill_count AS a ON a.skill = p.skill_a
JOIN skill_count AS b ON b.skill = p.skill_b
CROSS JOIN totals AS t
ORDER BY lift DESC, roles DESC
LIMIT 15;
