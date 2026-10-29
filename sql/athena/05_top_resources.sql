-- The 20 most expensive resources this month, with their owner tag.
SELECT
  resourceid,
  servicename,
  coalesce(element_at(tags, 'Owner'), '(no owner)') AS owner,
  round(sum(effectivecost), 2)                       AS effective_cost
FROM finops.focus
WHERE billingperiodstart = timestamp '2026-10-01 00:00:00'
  AND resourceid IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY effective_cost DESC
LIMIT 20;
