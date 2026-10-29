"""Waste finder: report (and optionally clean up) orphaned AWS resources.

Finds three kinds of waste that keep billing after nobody uses them:
  * EBS volumes in the "available" state (attached to nothing)
  * EBS snapshots older than N days that no AMI of yours uses
  * Elastic IPs that are not associated with anything

Safe by default: DRY_RUN=true only reports. Even with DRY_RUN=false a resource
is deleted ONLY if it carries the tag  finops:cleanup = approved  (a human
decision), and the IAM policy enforces the same condition.

The cost functions are pure so they can be unit tested and reused by the
local demo (demo/run_demo.py).
"""
import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone

# Approximate monthly USD prices. They differ by Region; override with env vars.
DEFAULT_PRICES = {
    "gp3": 0.08, "gp2": 0.10, "io1": 0.125, "io2": 0.125, "st1": 0.045,
    "sc1": 0.015, "standard": 0.05,     # per GB-month
    "snapshot": 0.05,                    # per GB-month (upper bound: snapshots are incremental)
    "eip_hour": 0.005,                   # per hour for an idle public IPv4 address
}
APPROVE_TAG = ("finops:cleanup", "approved")


def prices():
    p = dict(DEFAULT_PRICES)
    raw = os.environ.get("PRICE_OVERRIDES")
    if raw:
        p.update(json.loads(raw))
    return p


def volume_monthly_cost(size_gb, volume_type, iops=0, price=None):
    price = price or prices()
    cost = size_gb * price.get(volume_type, price["gp3"])
    if volume_type in ("io1", "io2") and iops:
        cost += iops * 0.065          # provisioned IOPS, approximate
    return round(cost, 2)


def snapshot_monthly_cost(size_gb, price=None):
    price = price or prices()
    return round(size_gb * price["snapshot"], 2)


def eip_monthly_cost(price=None):
    price = price or prices()
    return round(price["eip_hour"] * 730, 2)


def tags_of(resource):
    return {t["Key"]: t["Value"] for t in resource.get("Tags", []) or []}


def is_approved(resource):
    return tags_of(resource).get(APPROVE_TAG[0]) == APPROVE_TAG[1]


# ---------- pure classifiers (input = describe_* output dicts) ----------
def classify_volumes(volumes, price=None):
    out = []
    for v in volumes:
        if v.get("State") != "available":
            continue
        out.append({
            "kind": "ebs_volume", "id": v["VolumeId"], "size_gb": v["Size"],
            "detail": f'{v.get("VolumeType")} in {v.get("AvailabilityZone")}',
            "created": str(v.get("CreateTime", "")),
            "monthly_usd": volume_monthly_cost(v["Size"], v.get("VolumeType", "gp3"), v.get("Iops", 0), price),
            "owner": tags_of(v).get("Owner", "(untagged)"),
            "approved": is_approved(v),
        })
    return out


def classify_snapshots(snapshots, ami_snapshot_ids, older_than_days, now=None, price=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=older_than_days)
    out = []
    for s in snapshots:
        start = s.get("StartTime")
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if s["SnapshotId"] in ami_snapshot_ids or start is None or start > cutoff:
            continue
        out.append({
            "kind": "ebs_snapshot", "id": s["SnapshotId"], "size_gb": s.get("VolumeSize", 0),
            "detail": f'{(now - start).days} days old, from {s.get("VolumeId", "?")}',
            "created": start.isoformat(),
            "monthly_usd": snapshot_monthly_cost(s.get("VolumeSize", 0), price),
            "owner": tags_of(s).get("Owner", "(untagged)"),
            "approved": is_approved(s),
        })
    return out


def classify_addresses(addresses, price=None):
    out = []
    for a in addresses:
        if a.get("AssociationId"):
            continue
        out.append({
            "kind": "elastic_ip", "id": a.get("AllocationId", a.get("PublicIp")), "size_gb": 0,
            "detail": f'{a.get("PublicIp")} not associated', "created": "",
            "monthly_usd": eip_monthly_cost(price),
            "owner": tags_of(a).get("Owner", "(untagged)"),
            "approved": is_approved(a),
        })
    return out


def summarize(findings):
    total = round(sum(f["monthly_usd"] for f in findings), 2)
    by_kind = {}
    for f in findings:
        k = by_kind.setdefault(f["kind"], {"count": 0, "monthly_usd": 0.0})
        k["count"] += 1
        k["monthly_usd"] = round(k["monthly_usd"] + f["monthly_usd"], 2)
    return {"total_monthly_usd": total, "total_yearly_usd": round(total * 12, 2), "by_kind": by_kind,
            "approved_for_cleanup": sum(1 for f in findings if f["approved"])}


def to_csv(findings):
    buf = io.StringIO()
    cols = ["region", "kind", "id", "size_gb", "detail", "created", "monthly_usd", "owner", "approved"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for f in findings:
        w.writerow(f)
    return buf.getvalue()


# ---------- AWS side (only runs inside Lambda) ----------
def _paginate(client, op, key, **kw):
    for page in client.get_paginator(op).paginate(**kw):
        yield from page.get(key, [])


def scan_region(ec2, older_than_days):
    vols = list(_paginate(ec2, "describe_volumes", "Volumes",
                          Filters=[{"Name": "status", "Values": ["available"]}]))
    snaps = list(_paginate(ec2, "describe_snapshots", "Snapshots", OwnerIds=["self"]))
    images = ec2.describe_images(Owners=["self"]).get("Images", [])
    ami_snaps = {bdm["Ebs"]["SnapshotId"] for img in images
                 for bdm in img.get("BlockDeviceMappings", []) if "Ebs" in bdm and "SnapshotId" in bdm["Ebs"]}
    addrs = ec2.describe_addresses().get("Addresses", [])
    return classify_volumes(vols) + classify_snapshots(snaps, ami_snaps, older_than_days) + classify_addresses(addrs)


def cleanup(ec2, findings):
    done = []
    for f in findings:
        if not f["approved"]:
            continue
        if f["kind"] == "ebs_volume":
            ec2.delete_volume(VolumeId=f["id"])
        elif f["kind"] == "ebs_snapshot":
            ec2.delete_snapshot(SnapshotId=f["id"])
        elif f["kind"] == "elastic_ip":
            ec2.release_address(AllocationId=f["id"])
        done.append(f["id"])
    return done


def lambda_handler(event, context):
    import boto3  # available in the Lambda runtime
    regions = [r.strip() for r in os.environ.get("REGIONS", os.environ.get("AWS_REGION", "us-east-1")).split(",") if r.strip()]
    days = int(os.environ.get("SNAPSHOT_MAX_AGE_DAYS", "90"))
    dry_run = os.environ.get("DRY_RUN", "true").lower() != "false"
    findings, deleted = [], []
    for region in regions:
        ec2 = boto3.client("ec2", region_name=region)
        found = scan_region(ec2, days)
        for f in found:
            f["region"] = region
        findings += found
        if not dry_run:
            deleted += cleanup(ec2, found)

    summary = summarize(findings)
    summary.update({"dry_run": dry_run, "deleted": deleted, "regions": regions,
                    "generated_at": datetime.now(timezone.utc).isoformat()})
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bucket = os.environ.get("REPORT_BUCKET")
    if bucket:
        s3 = boto3.client("s3")
        s3.put_object(Bucket=bucket, Key=f"waste-reports/{stamp}/findings.csv", Body=to_csv(findings).encode())
        s3.put_object(Bucket=bucket, Key=f"waste-reports/{stamp}/summary.json", Body=json.dumps(summary, indent=2).encode())
    topic = os.environ.get("SNS_TOPIC_ARN")
    if topic:
        lines = [f"Waste finder {stamp} ({'dry run' if dry_run else 'cleanup mode'})",
                 f"Estimated waste: ${summary['total_monthly_usd']}/month (${summary['total_yearly_usd']}/year)"]
        lines += [f"- {k}: {v['count']} items, ${v['monthly_usd']}/month" for k, v in summary["by_kind"].items()]
        lines.append(f"Tagged {APPROVE_TAG[0]}={APPROVE_TAG[1]}: {summary['approved_for_cleanup']}  | deleted: {len(deleted)}")
        boto3.client("sns").publish(TopicArn=topic, Subject=f"FinOps waste report {stamp}", Message="\n".join(lines))
    return summary
