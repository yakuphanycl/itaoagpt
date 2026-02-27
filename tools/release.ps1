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

# 4) Editable install mi? (site-packages'ten release etme)
$pkgPath = (python -c "import itaoagpt; print(itaoagpt.__file__)" 2>&1 | Out-String).Trim()
if ($pkgPath -match "\\site-packages\\") {
  throw "Refusing release: itaoagpt imports from site-packages: $pkgPath (run: pip install -e .)"
}

# 5) Release var mi? (*> $null: stdout+stderr yut, sadece exit code'a bak)
gh release view $Tag *> $null
$exists = ($LASTEXITCODE -eq 0)

# 6) Create veya edit — ciktiyi serbest birak, hatalar gorunsun
if ($exists) {
  gh release edit $Tag -t $Title -n $Notes
  if ($LASTEXITCODE -ne 0) { throw "gh release edit failed (rc=$LASTEXITCODE)" }
  Write-Host "[OK] Updated release: $Tag"
} else {
  gh release create $Tag -t $Title -n $Notes
  if ($LASTEXITCODE -ne 0) { throw "gh release create failed (rc=$LASTEXITCODE)" }
  Write-Host "[OK] Created release: $Tag"
}

# 7) Son hali goster
gh release view $Tag
