-- Showback: effective cost per team (CostCenter tag) for one billing month.
-- EffectiveCost = what you really pay after Savings Plans / RIs are amortized.
SELECT
  coalesce(element_at(tags, 'CostCenter'), '(untagged)')              AS team,
  round(sum(effectivecost), 2)                                         AS effective_cost,
  round(100 * sum(effectivecost) / sum(sum(effectivecost)) OVER (), 1) AS pct_of_total
FROM finops.focus
WHERE billingperiodstart = timestamp '2026-10-01 00:00:00'
GROUP BY 1
ORDER BY 2 DESC;
