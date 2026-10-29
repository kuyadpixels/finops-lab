# Capture a point-in-time snapshot of a cluster for k8s/allocate.py.
# Needs: kubectl pointed at the right context, and metrics-server installed (kubectl top works).
# Read-only: it only runs get commands.
param([string]$Out = "snapshot")
New-Item -ItemType Directory -Force -Path $Out | Out-Null
kubectl config current-context
kubectl get nodes -o json | Out-File -Encoding utf8 "$Out\nodes.json"
kubectl get pods -A -o json | Out-File -Encoding utf8 "$Out\pods.json"
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods | Out-File -Encoding utf8 "$Out\metrics.json"
Write-Host "Now run: python k8s/allocate.py --kubectl-dir $Out"
