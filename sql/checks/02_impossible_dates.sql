-- severity: error
-- Nothing is seen before it is first seen, closed before it opened, or posted in the future.
SELECT posting_id, posted_at, first_seen, last_seen, closed_at
FROM postings
WHERE last_seen < first_seen
   OR closed_at < first_seen
   OR posted_at > DATE('now', '+1 day');
