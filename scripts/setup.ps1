# Bootstrap on Windows: install uv if missing (Claude Code needs it for the hook
# and the MCP server). With -Daemon, also set up, start and check the daemon here;
# without it, run scripts/setup.sh on the daemon host (e.g. inside WSL).
# Usage: powershell -ExecutionPolicy ByPass -File scripts\setup.ps1 [-Daemon]
param([switch]$Daemon)
$ErrorActionPreference = 'Stop'

Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv not found, installing (https://docs.astral.sh/uv/)'
    powershell -NoProfile -ExecutionPolicy ByPass -Command 'irm https://astral.sh/uv/install.ps1 | iex'
    # The installer puts uv in ~\.local\bin; make it visible in this session.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv installed but not on PATH; open a new terminal'
    }
}
uv --version

if ($Daemon) {
    uv run --script bin/laya_setup.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run --script bin/laya_daemon.py start
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv run --script bin/laya_doctor.py
    exit $LASTEXITCODE
}
Write-Host 'uv ready. Run scripts/setup.sh on the daemon host (inside WSL), or rerun with -Daemon to host it here.'
