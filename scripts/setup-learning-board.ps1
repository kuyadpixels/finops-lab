# Creates milestones, labels and one issue per lab from docs/labs.json.
# Needs the GitHub CLI signed in (gh auth login). Safe to run twice: existing items are skipped.
$ErrorActionPreference = "Stop"
$labs = Get-Content -Raw -Encoding UTF8 "docs/labs.json" | ConvertFrom-Json

foreach ($m in @("Inform", "Optimize", "Operate")) {
    $exists = gh api "repos/{owner}/{repo}/milestones?state=all" --jq ".[] | select(.title==\`"$m\`") | .number"
    if (-not $exists) { gh api "repos/{owner}/{repo}/milestones" -f title="$m" | Out-Null; Write-Host "milestone $m" }
}

gh label create "lab"            --color "0E8A16" --description "A learning lab" --force | Out-Null
gh label create "phase:inform"   --color "1D76DB" --force | Out-Null
gh label create "phase:optimize" --color "FBCA04" --force | Out-Null
gh label create "phase:operate"  --color "B60205" --force | Out-Null

$existing = gh issue list --state all --limit 200 --json title --jq ".[].title"
foreach ($l in $labs) {
    $title = "Lab {0:D2}: {1}" -f $l.id, $l.title
    if ($existing -contains $title) { Write-Host "skip $title"; continue }
    $body = "**Phase:** $($l.phase)  `n**FinOps capability:** $($l.capability)  `n**FOCP topic:** $($l.focp)`n`n### Steps`n"
    foreach ($s in $l.steps) { $body += "- [ ] $s`n" }
    $body += "`n### Done when`n"
    foreach ($d in $l.done) { $body += "- [ ] $d`n" }
    $body += "`nBranch: lab/{0:D2}-..., PR body: Closes #<this issue>" -f $l.id
    gh issue create --title $title --body $body --label "lab" --label ("phase:" + $l.phase.ToLower()) --milestone $l.phase | Out-Null
    Write-Host "created $title"
}
Write-Host "Done. Add the issues to a GitHub Project board (Projects -> New project -> Board)."
