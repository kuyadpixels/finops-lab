-- Savings Plan / RI coverage for compute: covered list cost / eligible list cost.
-- PricingCategory = 'Committed' marks usage paid by a commitment in FOCUS 1.x.
SELECT
  servicename,
  round(100 * sum(CASE WHEN pricingcategory = 'Committed' THEN listcost ELSE 0 END)
        / nullif(sum(listcost), 0), 1)            AS coverage_pct,
  round(sum(listcost - effectivecost), 2)          AS savings_vs_list
FROM finops.focus
WHERE billingperiodstart = timestamp '2026-10-01 00:00:00'
  AND chargecategory = 'Usage'
  AND servicecategory = 'Compute'
GROUP BY 1
ORDER BY savings_vs_list DESC;
