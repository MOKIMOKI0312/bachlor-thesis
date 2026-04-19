# Resume E1-R2b training workers (was suspended via NtSuspendProcess).
# Usage: powershell -ExecutionPolicy Bypass -File tools\resume_suspended_training.ps1

Add-Type -Name NM -Namespace Win32 -MemberDefinition @'
[DllImport("ntdll.dll")] public static extern int NtResumeProcess(IntPtr h);
[DllImport("kernel32.dll")] public static extern IntPtr OpenProcess(int a, bool i, int p);
[DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
'@

$access = 0x0800 -bor 0x0400  # SUSPEND_RESUME | QUERY_INFORMATION

$targets = Get-Process python,energyplus -ErrorAction SilentlyContinue
Write-Host ("Resuming " + $targets.Count + " processes...")

foreach ($p in $targets) {
    $h = [Win32.NM]::OpenProcess($access, $false, $p.Id)
    if ($h -eq [IntPtr]::Zero) { Write-Host (" FAIL open pid=" + $p.Id); continue }
    $r = [Win32.NM]::NtResumeProcess($h)
    [Win32.NM]::CloseHandle($h) | Out-Null
    Write-Host (" resumed pid=" + $p.Id + " name=" + $p.ProcessName + " rc=" + $r)
}
Write-Host ""
Write-Host "Done. Training should continue from where it paused."
Write-Host "To re-arm hourly monitor, tell Claude: /loop 1h <monitor prompt>"
