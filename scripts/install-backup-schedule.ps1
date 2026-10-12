<#
.SYNOPSIS
Schedules a daily backup of the VEXTRO database with Windows Task Scheduler.

.DESCRIPTION
Registers the task "VEXTRO database backup" for the current user. Each day
it runs scripts\db_backup.py with the project's own Python environment,
which writes a verified pg_dump archive to backups\ and keeps the most
recent ones. If the computer was off at the scheduled time, the backup runs
as soon as it is next on.

Nothing is installed and no password is stored: the task runs while this
user is logged in and reads the database account from backend\.env.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\install-backup-schedule.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\install-backup-schedule.ps1 -At 21:30 -Keep 30

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\install-backup-schedule.ps1 -Remove
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    # Time of day the backup runs, 24-hour clock.
    [string]$At = "13:00",

    # How many backups to keep.
    [ValidateRange(1, 365)]
    [int]$Keep = 14,

    # Remove the schedule instead of creating it. Existing backups stay.
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$taskName = "VEXTRO database backup"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot "backend\.venv\Scripts\python.exe"
$backupScript = Join-Path $PSScriptRoot "db_backup.py"

if ($Remove) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        if ($PSCmdlet.ShouldProcess($taskName, "Remove the scheduled task")) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Write-Output "Removed the schedule '$taskName'. Existing backups were left in place."
        }
    }
    else {
        Write-Output "There is no schedule named '$taskName'."
    }
    return
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "VEXTRO Python environment is missing: $pythonPath"
}

$startTime = [datetime]::ParseExact($At, "HH:mm", [cultureinfo]::InvariantCulture)

$action = New-ScheduledTaskAction `
    -Execute $pythonPath `
    -Argument "`"$backupScript`" --keep $Keep" `
    -WorkingDirectory $repositoryRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $startTime

# A laptop is often off or on battery at the scheduled time. Run the missed
# backup when the machine is next available rather than skipping the day.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

if ($PSCmdlet.ShouldProcess($taskName, "Schedule a daily backup at $At keeping $Keep copies")) {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Backs up the VEXTRO PostgreSQL database with scripts\db_backup.py and keeps the last $Keep copies." `
        -Force | Out-Null

    $nextRun = (Get-ScheduledTaskInfo -TaskName $taskName).NextRunTime
    Write-Output "Scheduled '$taskName' daily at $At, keeping $Keep backups."
    Write-Output "Next run: $nextRun"
    Write-Output "Backups and backup_history.log are written to: $(Join-Path $repositoryRoot 'backups')"
    Write-Output "Run it once now with: Start-ScheduledTask -TaskName '$taskName'"
}
