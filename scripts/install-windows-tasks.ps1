[CmdletBinding()]
param(
    [switch]$Boot,
    [switch]$Plan,
    [switch]$Start,
    [switch]$Repair,
    [System.Management.Automation.PSCredential]$Credential
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Run scripts\setup.ps1 before building the JobForge tasks.'
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$names = @{ api = 'JobForge AI Dashboard'; worker = 'JobForge AI Worker' }
if ($Boot -and $Repair) { throw 'Repair preserves the existing logon principal. Boot requires a new installation.' }
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$definitions = @{}
foreach ($role in @('api', 'worker')) {
    $action = New-ScheduledTaskAction -Execute $python -WorkingDirectory $root `
        -Argument "-u -m jobforge.windows $role"
    $trigger = if ($Boot) { New-ScheduledTaskTrigger -AtStartup } else { New-ScheduledTaskTrigger -AtLogOn -User $identity.Name }
    $watchdog = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $logon = if ($Boot) { 'Password' } else { 'Interactive' }
    $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType $logon -RunLevel Limited
    $definitions[$role] = New-ScheduledTask -Action $action -Trigger @($trigger, $watchdog) `
        -Settings $settings -Principal $principal -Description "Runs the local JobForge AI $role."
}

if ($Plan) {
    foreach ($role in @('api', 'worker')) {
        $definition = $definitions[$role]
        [pscustomobject]@{
            Name = $names[$role]; Execute = $definition.Actions.Execute
            Arguments = $definition.Actions.Arguments; WorkingDirectory = $definition.Actions.WorkingDirectory
            Trigger = if ($Boot) { 'Boot' } else { 'Logon' }
            LogonType = $definition.Principal.LogonType
            RestartCount = $definition.Settings.RestartCount
            RestartInterval = $definition.Settings.RestartInterval
            WatchdogInterval = $definition.Triggers[1].Repetition.Interval
            MultipleInstances = $definition.Settings.MultipleInstances
            StartWhenAvailable = $definition.Settings.StartWhenAvailable
        }
    }
    return
}

if ($Repair) {
    foreach ($role in @('api', 'worker')) {
        $existing = Get-ScheduledTask -TaskName $names[$role]
        if ($existing.Actions.Count -ne 1 -or $existing.Actions[0].Execute -ine $python -or
            $existing.Actions[0].Arguments -ne "-u -m jobforge.windows $role" -or
            $existing.Principal.LogonType.ToString() -ne 'Interactive') {
            throw "The task '$($names[$role])' does not match this workspace's interactive installation."
        }
    }
    foreach ($role in @('api', 'worker')) {
        Set-ScheduledTask -TaskName $names[$role] -Trigger $definitions[$role].Triggers -Settings $settings | Out-Null
        if ($Start -and (Get-ScheduledTask -TaskName $names[$role]).State -ne 'Running') {
            Start-ScheduledTask -TaskName $names[$role]
        }
    }
    Get-ScheduledTask -TaskName $names.Values
    return
}

if ($Boot) {
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Boot task registration requires an elevated PowerShell for this installation.'
    }
    if (-not $Credential) {
        $Credential = Get-Credential -UserName $identity.Name -Message 'JobForge boot tasks need this Windows account password to use its cache and network access.'
    }
    if (-not $Credential -or $Credential.UserName -ine $identity.Name) {
        throw 'Use the same Windows account that provisioned JobForge and Tectonic.'
    }
}

foreach ($name in $names.Values) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        throw "A task named '$name' already exists. Inspect it before replacing it."
    }
}
$created = @()
try {
    foreach ($role in @('api', 'worker')) {
        $name = $names[$role]
        if ($Boot) {
            Register-ScheduledTask -TaskName $name -InputObject $definitions[$role] `
                -User $Credential.UserName -Password $Credential.GetNetworkCredential().Password | Out-Null
        } else {
            Register-ScheduledTask -TaskName $name -InputObject $definitions[$role] | Out-Null
        }
        $created += $name
    }
} catch {
    foreach ($name in $created) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    throw
}

if ($Start) {
    foreach ($role in @('api', 'worker')) { Start-ScheduledTask -TaskName $names[$role] }
}
Get-ScheduledTask -TaskName $created
