-- severity: error
-- Every open posting needs a title, a link, a location and a description.
SELECT posting_id, title, url
FROM postings
WHERE closed_at IS NULL
  AND (TRIM(title) = '' OR TRIM(url) = '' OR TRIM(location) = '' OR COALESCE(TRIM(description), '') = '');
