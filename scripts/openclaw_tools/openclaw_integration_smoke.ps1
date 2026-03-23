param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [string]$Token = "openclaw233",
    [string]$Provider = "feishu",
    [string]$ExternalUserId,
    [string]$Mode = "daily-brief",
    [string]$Date = (Get-Date -Format "yyyy-MM-dd")
)

if (-not $ExternalUserId) {
    throw "Missing -ExternalUserId"
}

$scriptPath = Join-Path $PSScriptRoot "openclaw_api_smoke.py"
$arguments = @(
    $scriptPath,
    "--base-url", $BaseUrl,
    "--token", $Token,
    "--provider", $Provider,
    "--external-user-id", $ExternalUserId,
    $Mode,
    "--date", $Date
)

python @arguments
