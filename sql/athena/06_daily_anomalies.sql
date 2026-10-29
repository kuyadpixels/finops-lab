-- Simple anomaly check: days more than 30% above the 14-day trailing average.
-- AWS Cost Anomaly Detection (terraform/aws) does this with ML; this query explains the idea.
WITH d AS (
  SELECT date_trunc('day', chargeperiodstart) AS day, sum(effectivecost) AS cost
  FROM finops.focus
  GROUP BY 1
), s AS (
  SELECT day, cost,
         avg(cost) OVER (ORDER BY day ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS baseline
  FROM d
)
SELECT day, round(cost, 2) AS cost, round(baseline, 2) AS baseline_14d,
       round(100 * (cost - baseline) / baseline, 0) AS above_pct
FROM s
WHERE baseline IS NOT NULL AND cost > baseline * 1.3
ORDER BY day;
