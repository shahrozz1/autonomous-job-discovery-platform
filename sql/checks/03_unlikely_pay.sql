-- severity: error
-- Pay ranges have to be in order and look like a yearly salary.
SELECT posting_id, title, pay_min, pay_max
FROM postings
WHERE pay_min > pay_max
   OR pay_min < 24000
   OR pay_max > 600000
   OR (pay_min IS NULL) <> (pay_max IS NULL);
