-- The five most requested skills in each job family.
WITH family_size AS (
    SELECT family, COUNT(*) AS roles
    FROM open_roles
    GROUP BY family
),
counted AS (
    SELECT r.family, s.skill, COUNT(*) AS n
    FROM open_roles AS r
    JOIN posting_skills AS s USING (posting_id)
    GROUP BY r.family, s.skill
),
ranked AS (
    SELECT
        c.family,
        c.skill,
        ROUND(100.0 * c.n / f.roles, 0)                                       AS pct_of_family,
        ROW_NUMBER() OVER (PARTITION BY c.family ORDER BY c.n DESC, c.skill)  AS place
    FROM counted AS c
    JOIN family_size AS f USING (family)
)
SELECT family, place, skill, pct_of_family
FROM ranked
WHERE place <= 5
ORDER BY family, place;
