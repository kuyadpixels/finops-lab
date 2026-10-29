"""Generate SYNTHETIC billing data in a FOCUS-like shape (AWS + Azure), so the
whole pipeline can be shown without a real bill.  Every number it produces is
made up.  Output: demo/data/focus_sample.csv and demo/data/inventory.json
"""
import csv
import json
import os
import random
from datetime import date, timedelta

random.seed(42)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data")
os.makedirs(OUT, exist_ok=True)

TEAMS = ["orders", "payments", "data", "platform"]
ENVS = ["prod", "staging", "dev"]
# provider, service, category, base daily list cost, commitment-eligible
SERVICES = [
    ("AWS", "Amazon Elastic Compute Cloud", "Compute", 120, True),
    ("AWS", "Amazon Relational Database Service", "Databases", 60, False),
    ("AWS", "Amazon Simple Storage Service", "Storage", 18, False),
    ("AWS", "Amazon Elastic Kubernetes Service", "Compute", 15, False),
    ("AWS", "AWS Lambda", "Compute", 6, True),
    ("AWS", "Amazon CloudWatch", "Management and Governance", 9, False),
    ("Microsoft", "Virtual Machines", "Compute", 55, True),
    ("Microsoft", "Azure SQL Database", "Databases", 30, False),
    ("Microsoft", "Storage", "Storage", 8, False),
]
START, END = date(2026, 8, 1), date(2026, 10, 31)


def month_start(d):
    return d.replace(day=1)


rows = []
d = START
while d <= END:
    growth = 1 + (d - START).days * 0.002            # slow growth over 3 months
    for provider, svc, cat, base, eligible in SERVICES:
        for team in TEAMS:
            share = {"orders": .35, "payments": .25, "data": .25, "platform": .15}[team]
            for env in ENVS:
                env_share = {"prod": .65, "staging": .2, "dev": .15}[env]
                list_cost = base * share * env_share * growth * random.uniform(.85, 1.15)
                # a cost spike: data team ran a big job on 14-16 Oct
                if team == "data" and env == "prod" and svc == "Amazon Elastic Compute Cloud" and date(2026, 10, 14) <= d <= date(2026, 10, 16):
                    list_cost *= 10
                untagged = random.random() < 0.18
                tags = {} if untagged else {"CostCenter": team, "Environment": env, "Owner": f"{team}-lead"}
                committed = eligible and env == "prod" and random.random() < 0.55
                pricing = "Committed" if committed else "Standard"
                effective = list_cost * (0.72 if committed else 1.0)   # ~28% Savings Plan discount
                rows.append({
                    "BillingPeriodStart": month_start(d).isoformat(),
                    "ChargePeriodStart": d.isoformat(),
                    "ProviderName": provider,
                    "SubAccountId": f"{'1111' if provider == 'AWS' else 'sub'}-{env}",
                    "ServiceName": svc,
                    "ServiceCategory": cat,
                    "ResourceId": f"{svc.split()[-1].lower()}-{team}-{env}-{random.randint(1, 3)}",
                    "ChargeCategory": "Usage",
                    "PricingCategory": pricing,
                    "CommitmentDiscountType": ("Savings Plan" if provider == "AWS" else "Reservation") if committed else "",
                    "ListCost": round(list_cost, 4),
                    "EffectiveCost": round(effective, 4),
                    "BilledCost": round(effective, 4),
                    "Tags": json.dumps(tags),
                })
    d += timedelta(days=1)

with open(os.path.join(OUT, "focus_sample.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# synthetic "describe_*" output for the waste finder demo
inventory = {
    "Volumes": [
        {"VolumeId": "vol-0a1b2c3d", "Size": 500, "VolumeType": "gp2", "State": "available", "AvailabilityZone": "ap-southeast-1a", "Tags": [{"Key": "Owner", "Value": "data-lead"}]},
        {"VolumeId": "vol-0e4f5a6b", "Size": 200, "VolumeType": "gp3", "State": "available", "AvailabilityZone": "ap-southeast-1b"},
        {"VolumeId": "vol-0c7d8e9f", "Size": 100, "VolumeType": "io2", "Iops": 3000, "State": "available", "AvailabilityZone": "ap-southeast-1a", "Tags": [{"Key": "finops:cleanup", "Value": "approved"}]},
        {"VolumeId": "vol-0inuse01", "Size": 80, "VolumeType": "gp3", "State": "in-use", "AvailabilityZone": "ap-southeast-1a"},
    ],
    "Snapshots": [{"SnapshotId": f"snap-{i:04d}", "VolumeSize": random.choice([30, 50, 100, 250]),
                   "StartTime": (date(2026, 11, 1) - timedelta(days=random.randint(10, 400))).isoformat() + "T00:00:00+00:00",
                   "VolumeId": f"vol-old{i}"} for i in range(40)],
    "AmiSnapshotIds": ["snap-0001", "snap-0002", "snap-0003"],
    "Addresses": [{"AllocationId": "eipalloc-01", "PublicIp": "203.0.113.10"},
                  {"AllocationId": "eipalloc-02", "PublicIp": "203.0.113.11", "AssociationId": "eipassoc-9"},
                  {"AllocationId": "eipalloc-03", "PublicIp": "203.0.113.12"}],
}
with open(os.path.join(OUT, "inventory.json"), "w") as f:
    json.dump(inventory, f, indent=2)
print(f"wrote {len(rows)} billing rows and a sample inventory to {OUT}")
