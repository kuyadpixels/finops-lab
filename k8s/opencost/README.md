# OpenCost on a cluster

OpenCost (a CNCF project) does continuously what `k8s/allocate.py` does once: it prices
every pod from node prices and allocates by namespace, label and controller.

```bash
# Prometheus first (OpenCost reads metrics from it). Skip if you already run one.
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/prometheus -n monitoring --create-namespace

helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
helm install opencost opencost/opencost -n opencost --create-namespace
kubectl port-forward -n opencost svc/opencost 9090:9090   # UI on http://localhost:9090
```

Check the chart's values for the Prometheus address if yours is not the default
(`helm show values opencost/opencost`).

## AWS-native alternative: split cost allocation data for EKS

Turn on **Split cost allocation data** for Amazon EKS in Billing preferences. AWS then adds
pod-level cost (by namespace, workload and Kubernetes labels you activate) to the cost
and usage data, so the same Athena / FOCUS pipeline in this repo can report per team.
Activate the Kubernetes labels you use (team, cost-center) as cost allocation tags.

## Which one?

| | OpenCost | EKS split cost allocation |
|---|---|---|
| Where it runs | In the cluster | In AWS billing, nothing to run |
| Freshness | Minutes | Daily, with the billing data |
| Works on | Any Kubernetes (EKS, AKS, kind) | EKS (and ECS) |
| Prices | List prices or custom pricing | Your real billed rates |
