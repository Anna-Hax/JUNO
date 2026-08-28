# After: gh auth refresh -h github.com -s project,read:project
# Ensures JUNO Roadmap project exists, links open issues, prints board URL.
# Idempotent: reuses an existing open "JUNO Roadmap" project instead of creating a duplicate.

$ErrorActionPreference = "Stop"
$owner = "Anna-Hax"
$repo = "Anna-Hax/JUNO"
$title = "JUNO Roadmap"

$list = gh project list --owner $owner --limit 100 --format json | ConvertFrom-Json
$projects = @($list.projects)
$existing = $projects |
  Where-Object { $_.title -eq $title -and -not $_.closed } |
  Sort-Object number |
  Select-Object -First 1

if ($null -eq $existing) {
  $created = gh project create --owner $owner --title $title --format json | ConvertFrom-Json
  $number = $created.number
  Write-Host "Created project #$number"
} else {
  $number = $existing.number
  Write-Host "Reusing project #$number ($($existing.url))"
}

# Add open issues (ignore failures — often means already on the board)
$issues = gh issue list --repo $repo --state open --limit 100 --json url,number | ConvertFrom-Json
foreach ($i in $issues) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  gh project item-add $number --owner $owner --url $i.url 2>&1 | Out-Null
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -eq 0) {
    Write-Host "added #$($i.number)"
  } else {
    Write-Host "skip #$($i.number) (already on board or add failed)"
  }
}

Write-Host "Open: https://github.com/users/$owner/projects/$number"
Write-Host "Status field: Todo / In Progress / Done (customize in the project UI if you want Ready/Blocked/etc)."
Write-Host "CI auto-add: repo secrets PROJECT_PAT (token with project scope) + PROJECT_NUMBER=$number"
Write-Host "  Workflow: .github/workflows/project-automation.yml"
