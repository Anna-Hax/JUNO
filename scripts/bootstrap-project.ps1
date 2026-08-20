# After: gh auth refresh -h github.com -s project,read:project
# Creates JUNO Roadmap project and links open issues.

$ErrorActionPreference = "Stop"
$owner = "Anna-Hax"
$repo = "Anna-Hax/JUNO"

$created = gh project create --owner $owner --title "JUNO Roadmap" --format json | ConvertFrom-Json
$number = $created.number
Write-Host "Created project #$number"

# Add open issues
$issues = gh issue list --repo $repo --state open --limit 100 --json url | ConvertFrom-Json
foreach ($i in $issues) {
  gh project item-add $number --owner $owner --url $i.url | Out-Null
  Write-Host "added $($i.url)"
}

Write-Host "Open: https://github.com/users/$owner/projects/$number"
Write-Host "Then: configure Status field (Backlog/Ready/In Progress/In Review/Blocked/Done) in the UI."
Write-Host "Optional: set repo secrets PROJECT_PAT + PROJECT_NUMBER for .github/workflows/project-automation.yml"
