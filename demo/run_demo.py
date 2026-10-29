"""Run the FinOps analysis on the synthetic data with DuckDB and write a
self-contained HTML report to reports/finops-report.html.

The SQL here mirrors sql/athena/*.sql (same logic, DuckDB syntax for tags).
"""
import html
import json
import os
import sys
from datetime import datetime, timezone

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "lambda", "waste_finder"))
import handler as waste  # noqa: E402

DATA = os.path.join(HERE, "data", "focus_sample.csv")
OUT = os.path.join(ROOT, "reports", "finops-report.html")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

con = duckdb.connect()
con.execute(f"CREATE VIEW focus AS SELECT *, json_extract_string(Tags, '$.CostCenter') AS team, "
            f"json_extract_string(Tags, '$.Environment') AS env FROM read_csv_auto('{DATA}')")

def q(sql):
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    return cols, cur.fetchall()

monthly = q("""SELECT strftime(CAST(BillingPeriodStart AS DATE), '%Y-%m') AS month, ProviderName AS provider,
  round(sum(EffectiveCost), 2) AS effective_cost FROM focus GROUP BY 1, 2 ORDER BY 1, 2""")

allocation = q("""SELECT coalesce(team, '(untagged)') AS team, round(sum(EffectiveCost), 2) AS effective_cost,
  round(100 * sum(EffectiveCost) / sum(sum(EffectiveCost)) OVER (), 1) AS pct
  FROM focus WHERE BillingPeriodStart = '2026-10-01' GROUP BY 1 ORDER BY 2 DESC""")

untagged = q("""SELECT ProviderName AS provider, round(100 * sum(CASE WHEN team IS NULL THEN EffectiveCost ELSE 0 END) / sum(EffectiveCost), 1) AS untagged_pct,
  round(sum(CASE WHEN team IS NULL THEN EffectiveCost ELSE 0 END), 2) AS untagged_cost
  FROM focus WHERE BillingPeriodStart = '2026-10-01' GROUP BY 1 ORDER BY 1""")

coverage = q("""SELECT ProviderName AS provider, ServiceName AS service,
  round(100 * sum(CASE WHEN PricingCategory = 'Committed' THEN ListCost ELSE 0 END) / sum(ListCost), 1) AS coverage_pct,
  round(sum(ListCost - EffectiveCost), 2) AS savings
  FROM focus WHERE BillingPeriodStart = '2026-10-01' AND ServiceName IN ('Amazon Elastic Compute Cloud', 'AWS Lambda', 'Virtual Machines')
  GROUP BY 1, 2 ORDER BY 1, 2""")

variance = q("""WITH m AS (SELECT ServiceName AS service, BillingPeriodStart AS bp, sum(EffectiveCost) AS c FROM focus GROUP BY 1, 2)
  SELECT cur.service, round(prev.c, 2) AS sep, round(cur.c, 2) AS oct, round(cur.c - prev.c, 2) AS change,
  round(100 * (cur.c - prev.c) / prev.c, 1) AS change_pct
  FROM m cur JOIN m prev ON cur.service = prev.service AND cur.bp = '2026-10-01' AND prev.bp = '2026-09-01'
  ORDER BY abs(cur.c - prev.c) DESC LIMIT 6""")

spikes = q("""WITH d AS (SELECT CAST(ChargePeriodStart AS DATE) AS day, sum(EffectiveCost) AS c FROM focus GROUP BY 1),
  s AS (SELECT day, c, avg(c) OVER (ORDER BY day ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING) AS base FROM d)
  SELECT strftime(day, '%Y-%m-%d') AS day, round(c, 2) AS cost, round(base, 2) AS baseline_14d, round(100 * (c - base) / base, 0) AS above_pct
  FROM s WHERE base IS NOT NULL AND c > base * 1.3 ORDER BY day""")

inv = json.load(open(os.path.join(HERE, "data", "inventory.json")))
now = datetime(2026, 11, 1, tzinfo=timezone.utc)
findings = (waste.classify_volumes(inv["Volumes"]) +
            waste.classify_snapshots(inv["Snapshots"], set(inv["AmiSnapshotIds"]), 90, now=now) +
            waste.classify_addresses(inv["Addresses"]))
wsum = waste.summarize(findings)

def table(cols, rows, money=()):
    th = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = ""
    for r in rows:
        tds = ""
        for c, v in zip(cols, r):
            cls = ' class="n"' if isinstance(v, (int, float)) else ""
            txt = f"${v:,.2f}" if c in money else (f"{v}" if v is not None else "")
            tds += f"<td{cls}>{html.escape(txt)}</td>"
        body += f"<tr>{tds}</tr>"
    return f'<div class="t"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'

def bars(rows, label_i, value_i, unit="$"):
    mx = max(r[value_i] for r in rows) or 1
    out = ""
    for r in rows:
        w = 100 * r[value_i] / mx
        out += f'<div class="bar"><span>{html.escape(str(r[label_i]))}</span><i style="width:{w:.1f}%"></i><b>{unit}{r[value_i]:,.0f}</b></div>'
    return out

oct_total = sum(r[2] for r in monthly[1] if r[0] == "2026-10")
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FinOps Lab Report</title><style>
:root{{--bg:#f4f6f8;--card:#fff;--ink:#17212b;--muted:#5b6875;--line:#d7dee5;--acc:#0b6e69;--warn:#b42318}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f151a;--card:#162029;--ink:#e3eaf0;--muted:#9aabb8;--line:#2a3843;--acc:#4fc3b9;--warn:#ff8a7a}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:18px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 60px}} h1{{font-size:2rem;margin:.2em 0}} h2{{margin:1.6em 0 .4em}}
.note{{background:var(--card);border:1px dashed var(--warn);color:var(--warn);padding:10px 14px;border-radius:10px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}} .kpi b{{display:block;font-size:1.6rem;font-variant-numeric:tabular-nums}}
.kpi span{{color:var(--muted);font-size:.9rem}}
.t{{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}} table{{border-collapse:collapse;width:100%;font-size:.95rem}}
th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}} th{{color:var(--muted);font-size:.8rem;text-transform:uppercase}} td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.bar{{display:grid;grid-template-columns:minmax(90px,140px) 1fr 90px;gap:10px;align-items:center;margin:6px 0}} .bar i{{display:block;height:16px;background:var(--acc);border-radius:4px}}
.bar b{{text-align:right;font-variant-numeric:tabular-nums}} p.m{{color:var(--muted)}}
</style></head><body><main>
<p class="note"><b>Synthetic data.</b> Every number in this report comes from demo/generate_sample.py. Run the same queries on your own CUR / FOCUS export for real figures.</p>
<h1>FinOps Lab Report · Oct 2026</h1>
<div class="kpis">
 <div class="kpi"><span>Oct effective cost (AWS + Azure)</span><b>${oct_total:,.0f}</b></div>
 <div class="kpi"><span>Untagged share (AWS)</span><b>{untagged[1][0][1]}%</b></div>
 <div class="kpi"><span>Commitment savings in Oct</span><b>${sum(r[3] for r in coverage[1]):,.0f}</b></div>
 <div class="kpi"><span>Orphaned resources found</span><b>${wsum['total_monthly_usd']:,.0f}/mo</b></div>
</div>
<h2>1. Allocation: who spends what (Oct)</h2><p class="m">Showback by the CostCenter tag. "(untagged)" is the cost nobody owns yet: the first thing to fix.</p>
{bars(allocation[1], 0, 1)}{table(*allocation, money=('effective_cost',))}
<h2>2. Tag compliance</h2>{table(*untagged, money=('untagged_cost',))}
<h2>3. Commitment coverage (compute)</h2><p class="m">Coverage = list cost covered by Savings Plans / reservations ÷ all eligible list cost. Gaps in prod are where a new commitment pays off.</p>{table(*coverage, money=('savings',))}
<h2>4. Month-over-month variance</h2><p class="m">The table FP&A asks for: what moved, by how much, and why.</p>{table(*variance, money=('sep','oct','change'))}
<h2>5. Anomalies (daily cost &gt; 30% above 14-day average)</h2>{table(*spikes, money=('cost','baseline_14d'))}
<h2>6. Waste: orphaned resources</h2><p class="m">${wsum['total_monthly_usd']:,.2f}/month · ${wsum['total_yearly_usd']:,.2f}/year · {wsum['approved_for_cleanup']} tagged finops:cleanup=approved</p>
{table(['kind','id','detail','monthly_usd','owner','approved'], [(f['kind'],f['id'],f['detail'],f['monthly_usd'],f['owner'],f['approved']) for f in sorted(findings, key=lambda x: -x['monthly_usd'])[:15]], money=('monthly_usd',))}
<p class="m">Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by demo/run_demo.py</p>
</main></body></html>"""
open(OUT, "w").write(page)
print("report:", OUT)
print(json.dumps({"oct_total": round(oct_total, 2), "waste_monthly": wsum["total_monthly_usd"], "spike_days": [r[0] for r in spikes[1]]}, indent=1))
