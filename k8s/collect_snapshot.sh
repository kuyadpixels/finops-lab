#!/usr/bin/env bash
# Capture a point-in-time snapshot of a cluster for k8s/allocate.py (read-only).
set -euo pipefail
OUT="${1:-snapshot}"; mkdir -p "$OUT"
kubectl config current-context
kubectl get nodes -o json > "$OUT/nodes.json"
kubectl get pods -A -o json > "$OUT/pods.json"
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods > "$OUT/metrics.json"
echo "Now run: python k8s/allocate.py --kubectl-dir $OUT"
