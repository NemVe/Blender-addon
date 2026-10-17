param(
    [string]$Script,
    [string]$Log,
    [int]$TimeoutSec = 420
)
# Runs an After Effects script in a fresh instance and waits for it to finish and quit by itself.
# It refuses to start if After Effects is already running (it may be NemVe3D's own).
$ae = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
$running = Get-Process -Name AfterFX -ErrorAction SilentlyContinue
if ($running) {
    Write-Output "REFUSED: After Effects is already running (pid $($running.Id -join ','))"
    exit 2
}
if (Test-Path $Log) { Remove-Item $Log -Force }
$started = Get-Date
Start-Process -FilePath $ae -ArgumentList @("-r", $Script)
$deadline = $started.AddSeconds($TimeoutSec)
$done = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    if (Test-Path $Log) {
        $text = Get-Content $Log -Raw -ErrorAction SilentlyContinue
        if ($text -match "SCRIPT END") { $done = $true; break }
    }
}
if ($done) {
    # let it quit by itself; never kill it
    $quitDeadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $quitDeadline -and (Get-Process -Name AfterFX -ErrorAction SilentlyContinue)) { Start-Sleep -Seconds 2 }
}
Write-Output ("elapsed {0:N0} s, finished={1}, AfterFX still running={2}" -f ((Get-Date) - $started).TotalSeconds, $done, [bool](Get-Process -Name AfterFX -ErrorAction SilentlyContinue))
if (Test-Path $Log) { Get-Content $Log }
else { Write-Output "no log file" }
