param([int]$Width = 2560, [int]$Height = 1440)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
  [DllImport("user32.dll")] public static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern IntPtr SetWindowLongPtr(IntPtr h, int i, IntPtr v);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
"@
$p = Get-Process blender -ErrorAction Stop | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
$h = $p.MainWindowHandle
$GWL_STYLE = -16
$style = [Int64]([Win]::GetWindowLongPtr($h, $GWL_STYLE))
# Off: caption (title bar), thick frame (resize border), min/max boxes.
$style = $style -band (-bnot 0x00C00000) -band (-bnot 0x00040000) -band (-bnot 0x00020000) -band (-bnot 0x00010000)
[void][Win]::SetWindowLongPtr($h, $GWL_STYLE, [IntPtr]$style)
# SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOACTIVATE
[void][Win]::SetWindowPos($h, [IntPtr]::Zero, 0, 0, $Width, $Height, 0x0020 -bor 0x0004 -bor 0x0010)
$r = New-Object Win+RECT
[void][Win]::GetClientRect($h, [ref]$r)
"CLIENT {0}x{1}" -f ($r.R - $r.L), ($r.B - $r.T)
