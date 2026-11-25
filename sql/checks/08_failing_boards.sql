-- severity: warning
-- Boards that have failed three runs in a row have probably moved and should be fixed or removed.
SELECT company, platform, board, failures
FROM boards
WHERE active = 1 AND failures >= 3;
