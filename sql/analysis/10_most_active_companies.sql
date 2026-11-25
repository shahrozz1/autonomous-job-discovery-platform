-- Companies with the most open jobs asking for two years of experience or less.
SELECT
    company,
    COUNT(*)              AS roles,
    SUM(listings)         AS listings,
    MAX(posted_at)        AS newest
FROM open_roles
WHERE years_min <= 2
GROUP BY company
ORDER BY roles DESC, company
LIMIT 12;
