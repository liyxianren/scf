param(
    [Parameter(Mandatory = $true)]
    [string]$ExternalUserId,
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [string]$Token = "openclaw233",
    [string]$Provider = "feishu",
    [string]$Mode = "daily-brief",
    [string]$Date = (Get-Date -Format "yyyy-MM-dd")
)

$scriptPath = Join-Path $PSScriptRoot "openclaw_tools\\openclaw_integration_smoke.ps1"
& $scriptPath -BaseUrl $BaseUrl -Token $Token -Provider $Provider -ExternalUserId $ExternalUserId -Mode $Mode -Date $Date
