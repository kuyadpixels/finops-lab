#!/usr/bin/env bash
# Same as setup-learning-board.ps1, for macOS / Linux. Needs gh and jq. Works with macOS bash 3.2.
set -euo pipefail
for m in Inform Optimize Operate; do
  gh api "repos/{owner}/{repo}/milestones?state=all" --jq ".[].title" | grep -qx "$m" || gh api "repos/{owner}/{repo}/milestones" -f title="$m" >/dev/null
done
gh label create lab --color 0E8A16 --force >/dev/null
for p in inform:1D76DB optimize:FBCA04 operate:B60205; do gh label create "phase:${p%%:*}" --color "${p##*:}" --force >/dev/null; done
existing=$(gh issue list --state all --limit 200 --json title --jq '.[].title')
jq -c '.[]' docs/labs.json | while read -r l; do
  id=$(jq -r .id <<<"$l"); t=$(printf "Lab %02d: %s" "$id" "$(jq -r .title <<<"$l")"); ph=$(jq -r .phase <<<"$l")
  grep -qxF "$t" <<<"$existing" && { echo "skip $t"; continue; }
  body=$(jq -r '"**Phase:** \(.phase)  \n**FinOps capability:** \(.capability)  \n**FOCP topic:** \(.focp)\n\n### Steps\n" + ([.steps[] | "- [ ] " + .] | join("\n")) + "\n\n### Done when\n" + ([.done[] | "- [ ] " + .] | join("\n"))' <<<"$l")
  gh issue create --title "$t" --body "$body" --label lab --label "phase:$(printf %s "$ph" | tr "[:upper:]" "[:lower:]")" --milestone "$ph" >/dev/null && echo "created $t"
done
