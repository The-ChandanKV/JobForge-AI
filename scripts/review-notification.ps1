param([Parameter(Mandatory)][string]$Message)
if (-not [Environment]::UserInteractive) { exit 0 }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notification = [Windows.Forms.NotifyIcon]::new()
$notification.Icon = [Drawing.SystemIcons]::Information
$notification.Visible = $true
$notification.BalloonTipTitle = 'JobForge AI'
$notification.BalloonTipText = $Message
$notification.add_BalloonTipClicked({
    Start-Process 'http://127.0.0.1:8000/#approvals'
    [Windows.Forms.Application]::ExitThread()
})
$timer = [Windows.Forms.Timer]::new()
$timer.Interval = 15000
$timer.add_Tick({ [Windows.Forms.Application]::ExitThread() })
try {
    $notification.ShowBalloonTip(9000)
    $timer.Start()
    [Windows.Forms.Application]::Run()
} finally {
    $timer.Dispose()
    $notification.Dispose()
}
