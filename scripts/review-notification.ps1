param([Parameter(Mandatory)][string]$Message, [switch]$Probe)
if (-not [Environment]::UserInteractive) {
    if ($Probe) { Write-Output 'Non-interactive Windows session' }
    exit 0
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notification = [Windows.Forms.NotifyIcon]::new()
$notification.Icon = [Drawing.SystemIcons]::Information
$notification.Visible = $true
$script:shown = $false
$notification.add_BalloonTipShown({ $script:shown = $true })
$notification.BalloonTipTitle = 'JobForge AI'
$notification.BalloonTipText = $Message
$notification.add_BalloonTipClicked({
    Start-Process 'http://127.0.0.1:8000/approvals'
    [Windows.Forms.Application]::ExitThread()
})
$timer = [Windows.Forms.Timer]::new()
$timer.Interval = 15000
$timer.add_Tick({ [Windows.Forms.Application]::ExitThread() })
try {
    $notification.ShowBalloonTip(9000)
    $timer.Start()
    [Windows.Forms.Application]::Run()
    if ($Probe) {
        if ($script:shown) { Write-Output 'Windows reported BalloonTipShown' }
        else { Write-Output 'Windows did not report BalloonTipShown' }
    }
} finally {
    $timer.Dispose()
    $notification.Dispose()
}
