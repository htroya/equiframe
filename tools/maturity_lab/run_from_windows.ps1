# Existing OpenSSH and Python only. No global configuration or credential copying.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$KitPath,
    [Parameter(Mandatory=$true)][string]$KitSha256,
    [Parameter(Mandatory=$true)][string]$KeyPath,
    [Parameter(Mandatory=$true)][string]$KnownHostsPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][string]$Operator,
    [Parameter(Mandatory=$true)][string]$SshHost,
    [string]$SshUser = 'hernan',
    [string]$PythonPath = 'python',
    [int]$TimeoutSeconds = 86400
)
$ErrorActionPreference = 'Stop'
$Tool = Join-Path $PSScriptRoot 'scripts/transport_vm.py'
# Array arguments preserve spaces. KeyPath is used only by the local SSH client.
$Arguments = @($Tool, 'transport', '--kit', $KitPath, '--sha256', $KitSha256,
    '--key', $KeyPath, '--known-hosts', $KnownHostsPath, '--output', $OutputPath,
    '--operator', $Operator, '--host', $SshHost, '--user', $SshUser,
    '--timeout', [string]$TimeoutSeconds)
& $PythonPath @Arguments
exit $LASTEXITCODE
