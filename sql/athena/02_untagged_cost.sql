-- Tag compliance: share of cost with no CostCenter tag, per account.
-- Target: under 5%. The JD asks for 100% attribution.
SELECT
  subaccountid,
  round(sum(CASE WHEN element_at(tags, 'CostCenter') IS NULL THEN effectivecost ELSE 0 END), 2) AS untagged_cost,
  round(100 * sum(CASE WHEN element_at(tags, 'CostCenter') IS NULL THEN effectivecost ELSE 0 END)
        / nullif(sum(effectivecost), 0), 1)                                                    AS untagged_pct
FROM finops.focus
WHERE billingperiodstart = timestamp '2026-10-01 00:00:00'
  AND chargecategory = 'Usage'
GROUP BY 1
ORDER BY untagged_cost DESC;
