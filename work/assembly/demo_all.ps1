# One-key demo (C-4) Windows entry:
#   double-click, or run:
#     powershell -ExecutionPolicy Bypass -File work/assembly/demo_all.ps1 --rounds 3
#
# This wrapper only forwards all arguments to:
#   python work/assembly/demo_all.py
# Exit codes: 0 = all steps OK; 2 = blocked (recorded honestly, NOT M1-6 pass); 1 = failed.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads UTF-8 files without BOM as ANSI,
# so non-ASCII text here would be garbled / can break parsing. The Python script prints UTF-8 itself.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# repo root = parent of parent of work/assembly
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
Set-Location $RepoRoot

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Python) {
    Write-Host "[error] python not found in PATH (phase-1 demo uses Python 3.12)" -ForegroundColor Red
    exit 1
}

Write-Host "repo root: $RepoRoot" -ForegroundColor Cyan
Write-Host "run: python work/assembly/demo_all.py $args" -ForegroundColor Cyan
& $Python.Source "work/assembly/demo_all.py" @args
exit $LASTEXITCODE
