"""Kubernetes cost allocation: split node cost to teams and find over-requested pods.

Model (the same idea OpenCost uses, simplified):
  1. Each node's hourly price is split into a price per CPU core-hour and per GiB-hour.
  2. A pod is charged for max(request, usage) of CPU and memory: you pay for what you
     reserve, and for anything you burst above it.
  3. Node capacity nobody reserved or used is IDLE cost (a platform problem to fix).
  4. System namespaces (kube-system, monitoring, ...) are SHARED cost, spread over
     teams in proportion to their direct cost.

Usage:
  python k8s/allocate.py                                # synthetic sample snapshot
  python k8s/allocate.py --kubectl-dir snapshot/        # real cluster (see collect_snapshot.sh)
"""
import argparse
import json
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CPU_WEIGHT = 0.65            # share of a node's price assigned to CPU (rest to memory). An assumption: tune it.
SHARED_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "monitoring", "opencost", "kyverno", "cert-manager", "ingress-nginx"}
HOURS_PER_MONTH = 730


# ---------- quantity parsing ----------
def cpu_cores(q):
    if q is None or q == "":
        return 0.0
    q = str(q)
    if q.endswith("n"):
        return float(q[:-1]) / 1e9
    if q.endswith("u"):
        return float(q[:-1]) / 1e6
    if q.endswith("m"):
        return float(q[:-1]) / 1000
    return float(q)


_MEM = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "k": 1e3}


def mem_gib(q):
    if q is None or q == "":
        return 0.0
    m = re.fullmatch(r"([0-9.eE+-]+)([A-Za-z]*)", str(q))
    if not m:
        raise ValueError(f"bad memory quantity {q!r}")
    num, unit = float(m.group(1)), m.group(2)
    return num * _MEM.get(unit, 1) / 2**30


# ---------- core model (pure) ----------
def unit_prices(node):
    """$ per core-hour and $ per GiB-hour for one node."""
    return (node["hourly_usd"] * CPU_WEIGHT / node["cpu_cores"],
            node["hourly_usd"] * (1 - CPU_WEIGHT) / node["mem_gib"])


def allocate(snapshot):
    nodes = {n["name"]: n for n in snapshot["nodes"]}
    direct = defaultdict(float)
    used_capacity = defaultdict(lambda: [0.0, 0.0])
    pods_out = []
    for p in snapshot["pods"]:
        node = nodes.get(p["node"])
        if not node:
            continue
        cpu_price, mem_price = unit_prices(node)
        cpu = max(p["cpu_req"], p["cpu_used"])
        mem = max(p["mem_req_gib"], p["mem_used_gib"])
        cost = cpu * cpu_price + mem * mem_price
        used_capacity[p["node"]][0] += cpu
        used_capacity[p["node"]][1] += mem
        owner = "(shared)" if p["namespace"] in SHARED_NAMESPACES else (p.get("labels", {}).get("team") or f"ns:{p['namespace']}")
        direct[owner] += cost
        pods_out.append({**p, "owner": owner, "hourly_usd": cost,
                         "cpu_eff": p["cpu_used"] / p["cpu_req"] if p["cpu_req"] else None,
                         "mem_eff": p["mem_used_gib"] / p["mem_req_gib"] if p["mem_req_gib"] else None})
    idle = 0.0
    for name, n in nodes.items():
        cpu_price, mem_price = unit_prices(n)
        c, m = used_capacity[name]
        idle += max(n["cpu_cores"] - c, 0) * cpu_price + max(n["mem_gib"] - m, 0) * mem_price
    shared = direct.pop("(shared)", 0.0)
    team_total = sum(direct.values()) or 1
    teams = {t: {"direct": c, "shared": shared * c / team_total, "total": c + shared * c / team_total} for t, c in direct.items()}
    cluster = sum(n["hourly_usd"] for n in nodes.values())
    return {"cluster_hourly": cluster, "idle_hourly": idle, "shared_hourly": shared, "teams": teams, "pods": pods_out}


def rightsizing(pods, min_ratio=2.0, headroom=1.3):
    """Pods whose request is more than min_ratio x usage. Suggest usage x headroom."""
    out = []
    for p in pods:
        for res, req, used in (("cpu", p["cpu_req"], p["cpu_used"]), ("memory", p["mem_req_gib"], p["mem_used_gib"])):
            if req and used and req / used >= min_ratio:
                out.append({"pod": f'{p["namespace"]}/{p["name"]}', "owner": p["owner"], "resource": res,
                            "request": req, "used": used, "suggest": round(used * headroom, 3)})
    return sorted(out, key=lambda x: -(x["request"] - x["suggest"]))


# ---------- kubectl JSON -> snapshot ----------
def from_kubectl(d, price_file):
    prices = {k: v for k, v in json.load(open(price_file, encoding="utf-8-sig")).items() if not k.startswith("_")}
    nodes_j = json.load(open(os.path.join(d, "nodes.json"), encoding="utf-8-sig"))
    pods_j = json.load(open(os.path.join(d, "pods.json"), encoding="utf-8-sig"))
    metrics_j = json.load(open(os.path.join(d, "metrics.json"), encoding="utf-8-sig"))
    usage = {}
    for item in metrics_j.get("items", []):
        key = (item["metadata"]["namespace"], item["metadata"]["name"])
        usage[key] = (sum(cpu_cores(c["usage"]["cpu"]) for c in item["containers"]),
                      sum(mem_gib(c["usage"]["memory"]) for c in item["containers"]))
    nodes = []
    for n in nodes_j["items"]:
        itype = n["metadata"].get("labels", {}).get("node.kubernetes.io/instance-type", "unknown")
        cap = n["status"]["allocatable"]
        nodes.append({"name": n["metadata"]["name"], "instance_type": itype, "hourly_usd": prices.get(itype, prices.get("default", 0.1)),
                      "cpu_cores": cpu_cores(cap["cpu"]), "mem_gib": mem_gib(cap["memory"])})
    pods = []
    for p in pods_j["items"]:
        if p["status"].get("phase") != "Running":
            continue
        req_cpu = sum(cpu_cores(c.get("resources", {}).get("requests", {}).get("cpu")) for c in p["spec"]["containers"])
        req_mem = sum(mem_gib(c.get("resources", {}).get("requests", {}).get("memory")) for c in p["spec"]["containers"])
        u = usage.get((p["metadata"]["namespace"], p["metadata"]["name"]), (0.0, 0.0))
        pods.append({"namespace": p["metadata"]["namespace"], "name": p["metadata"]["name"], "node": p["spec"].get("nodeName"),
                     "labels": p["metadata"].get("labels", {}), "cpu_req": req_cpu, "mem_req_gib": req_mem,
                     "cpu_used": u[0], "mem_used_gib": u[1]})
    return {"nodes": nodes, "pods": pods}


def render(res, rs):
    m = HOURS_PER_MONTH
    L = ["# Kubernetes cost allocation", "",
         f"Cluster: **${res['cluster_hourly'] * m:,.0f}/month** · idle: **${res['idle_hourly'] * m:,.0f}/month "
         f"({100 * res['idle_hourly'] / res['cluster_hourly']:.0f}%)** · shared system cost: ${res['shared_hourly'] * m:,.0f}/month", "",
         "## Cost by team (direct + share of system namespaces)", "", "| Team | Direct | Shared | Total / month |", "|---|---:|---:|---:|"]
    for t, v in sorted(res["teams"].items(), key=lambda x: -x[1]["total"]):
        L.append(f"| {t} | ${v['direct'] * m:,.0f} | ${v['shared'] * m:,.0f} | **${v['total'] * m:,.0f}** |")
    L += ["", "Idle cost is not charged to teams here. Show it separately: it is the platform team's target (bin-packing, smaller nodes, Karpenter consolidation).", "",
          "## Over-requested pods (request ≥ 2× usage)", "", "| Pod | Team | Resource | Request | Used | Suggested request |", "|---|---|---|---:|---:|---:|"]
    for r in rs[:15]:
        unit = "cores" if r["resource"] == "cpu" else "GiB"
        L.append(f"| {r['pod']} | {r['owner']} | {r['resource']} | {r['request']:.2f} {unit} | {r['used']:.2f} | {r['suggest']:.2f} |")
    unlabeled = sorted({p["namespace"] for p in res["pods"] if p["owner"].startswith("ns:")})
    if unlabeled:
        L += ["", f"Namespaces with pods missing the `team` label: {', '.join(unlabeled)}. The Kyverno policy in k8s/policies stops new ones."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kubectl-dir")
    ap.add_argument("--prices", default=os.path.join(HERE, "node_prices.example.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "reports", "k8s-allocation.md"))
    a = ap.parse_args()
    snap = from_kubectl(a.kubectl_dir, a.prices) if a.kubectl_dir else json.load(open(os.path.join(HERE, "sample_snapshot.json")))
    res = allocate(snap)
    md = render(res, rightsizing(res["pods"]))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
