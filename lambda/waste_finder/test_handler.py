"""Unit tests for the pure parts of the waste finder.  Run:  python -m unittest discover lambda/waste_finder"""
import unittest
from datetime import datetime, timedelta, timezone

import handler as h

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


class TestWasteFinder(unittest.TestCase):
    def test_only_available_volumes_count(self):
        vols = [{"VolumeId": "vol-a", "Size": 100, "VolumeType": "gp3", "State": "available"},
                {"VolumeId": "vol-b", "Size": 50, "VolumeType": "gp2", "State": "in-use"}]
        out = h.classify_volumes(vols)
        self.assertEqual([f["id"] for f in out], ["vol-a"])
        self.assertEqual(out[0]["monthly_usd"], 8.0)

    def test_snapshot_used_by_ami_is_kept(self):
        old = NOW - timedelta(days=200)
        snaps = [{"SnapshotId": "snap-ami", "VolumeSize": 30, "StartTime": old},
                 {"SnapshotId": "snap-old", "VolumeSize": 30, "StartTime": old},
                 {"SnapshotId": "snap-new", "VolumeSize": 30, "StartTime": NOW - timedelta(days=5)}]
        out = h.classify_snapshots(snaps, {"snap-ami"}, 90, now=NOW)
        self.assertEqual([f["id"] for f in out], ["snap-old"])

    def test_associated_eip_is_not_waste(self):
        addrs = [{"AllocationId": "eipalloc-1", "PublicIp": "1.2.3.4", "AssociationId": "eipassoc-1"},
                 {"AllocationId": "eipalloc-2", "PublicIp": "5.6.7.8"}]
        out = h.classify_addresses(addrs)
        self.assertEqual([f["id"] for f in out], ["eipalloc-2"])
        self.assertEqual(out[0]["monthly_usd"], 3.65)

    def test_approval_tag_required(self):
        v = {"VolumeId": "vol-x", "Size": 10, "VolumeType": "gp3", "State": "available",
             "Tags": [{"Key": "finops:cleanup", "Value": "approved"}]}
        self.assertTrue(h.classify_volumes([v])[0]["approved"])
        v["Tags"] = [{"Key": "finops:cleanup", "Value": "yes"}]
        self.assertFalse(h.classify_volumes([v])[0]["approved"])

    def test_summary_totals(self):
        f = [{"kind": "ebs_volume", "monthly_usd": 8.0, "approved": False},
             {"kind": "elastic_ip", "monthly_usd": 3.65, "approved": True}]
        s = h.summarize(f)
        self.assertEqual(s["total_monthly_usd"], 11.65)
        self.assertEqual(s["approved_for_cleanup"], 1)


if __name__ == "__main__":
    unittest.main()
