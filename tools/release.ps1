param(
  [Parameter(Mandatory=$true)]
  [string]$Tag,

  [Parameter(Mandatory=$true)]
  [string]$Title,

  [Parameter(Mandatory=$true)]
  [string]$Notes
)

$ErrorActionPreference = "Stop"

# 1) Tag var mi? (release tag'siz olmaz)
$tagExists = git tag -l $Tag
if (-not $tagExists) {
  throw "Tag not found: $Tag (run: git tag $Tag)"
}

# 2) Working tree temiz mi?
$dirty = git status --porcelain
if ($dirty) {
  throw "Working tree is dirty. Commit or stash changes before releasing."
}

# 3) Tag ile package version uyusuyor mu?
$pkgVersion = (Select-String -Path "$PSScriptRoot\..\pyproject.toml" -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$expectedTag = "v$pkgVersion"
if ($Tag -ne $expectedTag) {
  throw "Tag '$Tag' does not match pyproject.toml version '$pkgVersion' (expected tag: $expectedTag)"
}

# 4) Release var mi?
$exists = $true
try { gh release view $Tag | Out-Null } catch { $exists = $false }

# 5) Create veya edit
if ($exists) {
  gh release edit $Tag -t $Title -n $Notes | Out-Null
  Write-Host "[OK] Updated release: $Tag"
} else {
  gh release create $Tag -t $Title -n $Notes | Out-Null
  Write-Host "[OK] Created release: $Tag"
}

# 6) Son hali goster
gh release view $Tag
