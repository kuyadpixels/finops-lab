"""Run:  python -m unittest discover k8s"""
import unittest

import allocate as a


class TestAllocate(unittest.TestCase):
    def test_quantities(self):
        self.assertAlmostEqual(a.cpu_cores("250m"), 0.25)
        self.assertAlmostEqual(a.cpu_cores("2"), 2.0)
        self.assertAlmostEqual(a.cpu_cores("1500000000n"), 1.5)
        self.assertAlmostEqual(a.mem_gib("512Mi"), 0.5)
        self.assertAlmostEqual(a.mem_gib("1Gi"), 1.0)
        self.assertAlmostEqual(a.mem_gib(str(2**30)), 1.0)

    def snap(self):
        return {"nodes": [{"name": "n1", "hourly_usd": 1.0, "cpu_cores": 4, "mem_gib": 16}],
                "pods": [{"namespace": "shop", "name": "web", "node": "n1", "labels": {"team": "orders"},
                          "cpu_req": 1, "mem_req_gib": 4, "cpu_used": 0.2, "mem_used_gib": 1},
                         {"namespace": "kube-system", "name": "dns", "node": "n1", "labels": {},
                          "cpu_req": 0.5, "mem_req_gib": 0, "cpu_used": 0.1, "mem_used_gib": 0.5}]}

    def test_costs_add_up(self):
        r = a.allocate(self.snap())
        total = sum(t["total"] for t in r["teams"].values()) + r["idle_hourly"]
        self.assertAlmostEqual(total, r["cluster_hourly"], places=6)

    def test_shared_goes_to_teams(self):
        r = a.allocate(self.snap())
        self.assertIn("orders", r["teams"])
        self.assertGreater(r["teams"]["orders"]["shared"], 0)

    def test_burst_above_request_is_charged(self):
        s = self.snap()
        s["pods"][0]["cpu_used"] = 2   # bursts above its 1-core request
        r = a.allocate(s)
        cpu_price = 1.0 * a.CPU_WEIGHT / 4
        self.assertAlmostEqual(r["teams"]["orders"]["direct"], 2 * cpu_price + 4 * (1 - a.CPU_WEIGHT) / 16)

    def test_rightsizing_flags_over_request(self):
        r = a.allocate(self.snap())
        rs = a.rightsizing(r["pods"])
        self.assertTrue(any(x["pod"] == "shop/web" and x["resource"] == "cpu" for x in rs))


if __name__ == "__main__":
    unittest.main()
