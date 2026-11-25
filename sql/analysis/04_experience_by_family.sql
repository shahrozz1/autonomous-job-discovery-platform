-- Which job families are the most open to someone with two years of experience or less?
SELECT
    family,
    COUNT(*)                                                       AS roles,
    COUNT(years_min)                                               AS state_a_number,
    ROUND(100.0 * AVG(years_min <= 2), 0)                          AS pct_two_years_or_less,
    ROUND(100.0 * AVG(years_min >= 3), 0)                          AS pct_three_or_more
FROM open_roles
GROUP BY family
ORDER BY pct_two_years_or_less DESC;
