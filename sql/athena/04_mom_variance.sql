-- Month-over-month variance by service: the table Finance (FP&A) asks for.
WITH m AS (
  SELECT servicename, billingperiodstart AS bp, sum(effectivecost) AS cost
  FROM finops.focus
  GROUP BY 1, 2
)
SELECT
  cur.servicename,
  round(prev.cost, 2)                                   AS prev_month,
  round(cur.cost, 2)                                    AS this_month,
  round(cur.cost - prev.cost, 2)                        AS change,
  round(100 * (cur.cost - prev.cost) / nullif(prev.cost, 0), 1) AS change_pct
FROM m cur
JOIN m prev
  ON cur.servicename = prev.servicename
 AND cur.bp  = timestamp '2026-10-01 00:00:00'
 AND prev.bp = timestamp '2026-09-01 00:00:00'
ORDER BY abs(cur.cost - prev.cost) DESC
LIMIT 15;
