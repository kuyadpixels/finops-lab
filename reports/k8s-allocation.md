# Kubernetes cost allocation

Cluster: **$809/month** · idle: **$423/month (52%)** · shared system cost: $50/month

## Cost by team (direct + share of system namespaces)

| Team | Direct | Shared | Total / month |
|---|---:|---:|---:|
| orders | $126 | $18 | **$144** |
| data | $104 | $15 | **$119** |
| ns:sandbox | $60 | $9 | **$69** |
| payments | $46 | $7 | **$53** |
| platform | $8 | $1 | **$9** |

Idle cost is not charged to teams here. Show it separately: it is the platform team's target (bin-packing, smaller nodes, Karpenter consolidation).

## Over-requested pods (request ≥ 2× usage)

| Pod | Team | Resource | Request | Used | Suggested request |
|---|---|---|---:|---:|---:|
| etl/spark-driver-0 | data | memory | 6.00 GiB | 2.50 | 3.25 |
| sandbox/test-app-1 | ns:sandbox | memory | 2.00 GiB | 0.84 | 1.09 |
| shop/orders-worker-0 | orders | cpu | 1.00 cores | 0.15 | 0.20 |
| shop/orders-worker-1 | orders | cpu | 1.00 cores | 0.15 | 0.20 |
| sandbox/test-app-0 | ns:sandbox | cpu | 1.00 cores | 0.15 | 0.20 |
| sandbox/test-app-1 | ns:sandbox | cpu | 1.00 cores | 0.15 | 0.20 |
| pay/payments-api-1 | payments | memory | 1.00 GiB | 0.41 | 0.53 |
| shop/orders-api-0 | orders | memory | 1.00 GiB | 0.47 | 0.61 |
| pay/payments-api-0 | payments | memory | 1.00 GiB | 0.48 | 0.63 |
| shop/orders-api-2 | orders | cpu | 0.50 cores | 0.18 | 0.23 |
| pay/payments-api-2 | payments | cpu | 0.50 cores | 0.22 | 0.28 |
| pay/payments-api-0 | payments | cpu | 0.50 cores | 0.24 | 0.31 |

Namespaces with pods missing the `team` label: sandbox. The Kyverno policy in k8s/policies stops new ones.
