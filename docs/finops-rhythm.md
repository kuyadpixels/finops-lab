# FinOps operating rhythm and taxonomy

## Tagging taxonomy (both clouds)

| Key | Example values | Why |
|---|---|---|
| `CostCenter` | orders, payments, data, platform | Showback / chargeback to a team or product |
| `Environment` | prod, staging, dev, lab | Separate production cost from everything else |
| `Owner` | orders-lead | A person to ask about the resource |
| `finops:cleanup` | approved | Human approval for automatic deletion |

Rules: tag at creation through IaC (Terraform `default_tags`), detect gaps with AWS Config / Azure Policy, report untagged cost weekly, target under 5%.

## Rhythm

| When | What | Output |
|---|---|---|
| Daily | Anomaly alerts (Cost Anomaly Detection, budget forecast) | Ticket to the owning team when impact > threshold |
| Weekly | Waste report, untagged cost by account, top 20 resources | Action list with owner and due date |
| Monthly | Variance vs last month and vs budget, forecast for next 3 months with FP&A | One-page variance note explaining the top 5 changes |
| Quarterly | Commitment review: coverage, utilization, expiring SPs/RIs, new purchases | Purchase or renewal proposal with payback period |

## Commitment governance

- Buy only for steady baseline usage (look at the lowest 30-day usage, not the average).
- Coverage target 70–80% of eligible compute; utilization target above 95%.
- Prefer Compute Savings Plans over EC2 Instance SPs when the fleet changes often.
- Every purchase gets an approval with: amount, term, expected savings, breakeven month.

## AI token management

- Allocate: every AI call carries team + app (gateway header or API key per app).
- Budget: monthly budget per team, forecast daily, alert at 80% forecast.
- Optimize: prompt caching for fixed system prompts, route simple tasks to smaller models, cap max output tokens, batch non-urgent work.
- Unit metric: cost per resolved ticket / per search / per review, not just total spend.
