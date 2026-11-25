-- severity: error
-- More than 20 years usually means the rules read a company's age as a requirement.
SELECT posting_id, title, years_min
FROM postings
WHERE years_min NOT BETWEEN 0 AND 20;
