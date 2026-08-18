# Registers a Windows Task Scheduler task that launches Hydration Reminder
# automatically when you log in. This is fully optional and fully under
# your control - you can disable or remove it anytime.
#
# Run this from an elevated (Administrator) PowerShell window, from inside
# the hydration-reminder folder:
#     .\register_autostart.ps1
#
# To remove it later:
#     Unregister-ScheduledTask -TaskName "HydrationReminder" -Confirm:$false

$ScriptDir = $PSScriptRoot
$PythonwPath = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonwPath) {
    Write-Host "Could not find pythonw.exe on PATH. Make sure Python is installed and added to PATH."
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonwPath -Argument "`"$ScriptDir\main.py`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "HydrationReminder" -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Starts the Hydration Reminder app at login. Manage or remove this anytime in Task Scheduler." -Force

Write-Host "Done. 'HydrationReminder' is now registered in Task Scheduler (Task Scheduler Library)."
Write-Host "You can view, disable, or delete it there, or run: Unregister-ScheduledTask -TaskName HydrationReminder"
