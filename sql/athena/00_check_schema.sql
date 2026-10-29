-- Run first. The Glue crawler names the table after the S3 folder and lowercases columns.
-- Replace finops.focus below if your table name differs.
SHOW COLUMNS IN finops.focus;

-- How do tag keys look in YOUR export? (e.g. 'CostCenter' vs 'user:CostCenter')
-- Edit the key in the other queries to match what you see here.
SELECT DISTINCT k
FROM finops.focus
CROSS JOIN UNNEST(map_keys(tags)) AS t(k)
LIMIT 50;
