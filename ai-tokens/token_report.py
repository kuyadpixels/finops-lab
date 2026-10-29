"""AI token FinOps: allocate token spend to teams, check budgets, forecast the
month and point at the cheapest optimizations.

Input: a usage CSV with one row per day/team/app/model:
  date,team,app,model,input_tokens,output_tokens,cached_input_tokens
Most AI gateways and provider usage exports can be shaped into this.

  python ai-tokens/token_report.py --sample            # make synthetic data and report
  python ai-tokens/token_report.py usage.csv           # your own data
"""
import argparse
import calendar
import csv
import json
import os
import random
from collections import defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))


def make_sample(path, month=date(2026, 10, 1), days=24):
    random.seed(7)
    apps = {"support-bot": ("chat-assistant", ["model-medium", "model-large"]),
            "doc-search": ("rag-search", ["model-small", "model-medium"]),
            "dev-tools": ("code-review", ["model-large", "model-medium"]),
            "analytics": ("report-summarizer", ["model-small"])}
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "team", "app", "model", "input_tokens", "output_tokens", "cached_input_tokens"])
        for i in range(days):
            d = month + timedelta(days=i)
            for team, (app, models) in apps.items():
                for m in models:
                    scale = {"model-large": 0.6, "model-medium": 2.5, "model-small": 6}[m]
                    inp = int(random.uniform(.7, 1.3) * scale * 1_000_000)
                    cached = int(inp * (0.05 if team == "dev-tools" else random.uniform(.2, .5)))
                    out = int(inp * random.uniform(.15, .35))
                    w.writerow([d.isoformat(), team, app, m, inp - cached, out, cached])
    return path


def cost_of(row, prices):
    p = prices[row["model"]]
    return (int(row["input_tokens"]) * p["input"] + int(row["output_tokens"]) * p["output"]
            + int(row["cached_input_tokens"]) * p["cached_input"]) / 1_000_000


def report(usage_csv, prices, budgets):
    rows = list(csv.DictReader(open(usage_csv)))
    by_team, by_model, by_app = defaultdict(float), defaultdict(float), defaultdict(float)
    tok_in, tok_cached = defaultdict(int), defaultdict(int)
    days = set()
    for r in rows:
        c = cost_of(r, prices)
        by_team[r["team"]] += c
        by_model[r["model"]] += c
        by_app[(r["team"], r["app"])] += c
        tok_in[r["team"]] += int(r["input_tokens"]) + int(r["cached_input_tokens"])
        tok_cached[r["team"]] += int(r["cached_input_tokens"])
        days.add(r["date"])
    first = date.fromisoformat(min(days))
    month_days = calendar.monthrange(first.year, first.month)[1]
    elapsed = len(days)
    total = sum(by_team.values())

    lines = [f"# AI token spend report · {first:%B %Y}", "",
             f"Data covers {elapsed} of {month_days} days. Prices from prices file (check they are current).", "",
             f"**Month to date:** ${total:,.2f} · **Forecast for the month:** ${total / elapsed * month_days:,.2f}", "",
             "## Budget by team", "", "| Team | Month to date | Forecast | Budget | Forecast vs budget | Cache hit |",
             "|---|---:|---:|---:|---:|---:|"]
    alerts = []
    for team, c in sorted(by_team.items(), key=lambda x: -x[1]):
        fc = c / elapsed * month_days
        b = budgets.get(team)
        pct = f"{100 * fc / b:.0f}%" if b else "no budget"
        hit = 100 * tok_cached[team] / max(tok_in[team], 1)
        lines.append(f"| {team} | ${c:,.2f} | ${fc:,.2f} | {'$%s' % b if b else '-'} | {pct} | {hit:.0f}% |")
        if b and fc > b:
            alerts.append(f"- **{team}** is forecast at ${fc:,.0f}, {100 * fc / b - 100:.0f}% over its ${b} budget.")
        if hit < 15:
            alerts.append(f"- **{team}** caches only {hit:.0f}% of input tokens. Prompt caching for its fixed system prompt is the cheapest fix.")
    lines += ["", "## Spend by model", "", "| Model | Cost | Share |", "|---|---:|---:|"]
    for m, c in sorted(by_model.items(), key=lambda x: -x[1]):
        lines.append(f"| {m} | ${c:,.2f} | {100 * c / total:.0f}% |")
    large = by_model.get("model-large", 0)
    if large / max(total, 1) > 0.4:
        alerts.append(f"- The largest model is {100 * large / total:.0f}% of spend. Route simple requests to a smaller model and test quality.")
    lines += ["", "## Top apps", "", "| Team | App | Cost |", "|---|---|---:|"]
    for (t, a), c in sorted(by_app.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"| {t} | {a} | ${c:,.2f} |")
    lines += ["", "## Alerts and actions", ""] + (alerts or ["- Nothing over budget."])
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("usage", nargs="?")
    ap.add_argument("--sample", action="store_true", help="generate synthetic usage first")
    ap.add_argument("--prices", default=os.path.join(HERE, "prices.example.json"))
    ap.add_argument("--budgets", default=os.path.join(HERE, "budgets.example.json"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "reports", "ai-token-report.md"))
    a = ap.parse_args()
    usage = a.usage or os.path.join(HERE, "sample_usage.csv")
    if a.sample or not os.path.exists(usage):
        make_sample(usage)
    prices = {k: v for k, v in json.load(open(a.prices)).items() if not k.startswith("_")}
    budgets = {k: v for k, v in json.load(open(a.budgets)).items() if not k.startswith("_")}
    md = report(usage, prices, budgets)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(md)
    print(md)


if __name__ == "__main__":
    main()
