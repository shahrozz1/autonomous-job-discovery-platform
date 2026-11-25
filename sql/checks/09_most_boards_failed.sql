-- severity: error
-- If more than one board in five failed, the last run can't be trusted.
SELECT run_id, run_date, boards_failed, boards_read, boards_same
FROM runs
WHERE run_id = (SELECT MAX(run_id) FROM runs)
  AND boards_failed > 0.2 * (boards_failed + boards_read + boards_same);
