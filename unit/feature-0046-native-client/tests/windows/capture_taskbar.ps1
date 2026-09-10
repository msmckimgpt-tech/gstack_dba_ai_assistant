param([Parameter(Mandatory=$true)][string]$OutputDir)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Accessibility
Add-Type -ReferencedAssemblies ([Accessibility.IAccessible].Assembly.Location) @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using Accessibility;
public class DqaTaskbarProbe {
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")]
    public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")]
    public static extern uint GetDpiForWindow(IntPtr hwnd);
    [StructLayout(LayoutKind.Sequential)]
    struct Point { public int x, y; }
    [DllImport("user32.dll")]
    static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")]
    static extern IntPtr GetAncestor(IntPtr hwnd, uint flags);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    static extern int GetClassName(IntPtr hwnd, StringBuilder name, int length);
    public static IntPtr RootAt(int x, int y) {
        return GetAncestor(WindowFromPoint(new Point {x=x, y=y}), 2);
    }
    public static string WindowClass(IntPtr hwnd) {
        var name = new StringBuilder(256);
        GetClassName(hwnd, name, name.Capacity);
        return name.ToString();
    }
    [DllImport("oleacc.dll")]
    static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint objectId, ref Guid iid,
        [MarshalAs(UnmanagedType.Interface)] out IAccessible accessible);
    public class Entry { public string name; public int left, top, width, height; }
    public static Entry[] Read(IntPtr hwnd) {
        IAccessible accessible;
        Guid iid = new Guid("618736e0-3c3d-11cf-810c-00aa00389b71");
        int hr = AccessibleObjectFromWindow(hwnd, 0xfffffffc, ref iid, out accessible);
        if (hr < 0) Marshal.ThrowExceptionForHR(hr);
        var result = new List<Entry>();
        Visit(accessible, result, 0);
        return result.ToArray();
    }
    static void Visit(IAccessible accessible, List<Entry> result, int depth) {
        if (depth > 3) return;
        for (int i = 1; i <= accessible.accChildCount; i++) {
            try {
                string name = accessible.get_accName(i);
                if (name != null && (name.IndexOf("DQA", StringComparison.OrdinalIgnoreCase) >= 0
                    || name.IndexOf("Python", StringComparison.OrdinalIgnoreCase) >= 0)) {
                    int left, top, width, height;
                    accessible.accLocation(out left, out top, out width, out height, i);
                    if (width > 0 && height > 0)
                        result.Add(new Entry { name=name, left=left, top=top, width=width, height=height });
                }
                var child = accessible.get_accChild(i) as IAccessible;
                if (child != null) Visit(child, result, depth + 1);
            } catch (COMException) { }
        }
    }
}
"@
[void](New-Item -ItemType Directory -Force -Path $OutputDir)
$dpiAwareness = 'per-monitor-v2'
try {
    $previousDpi = [DqaTaskbarProbe]::SetThreadDpiAwarenessContext([IntPtr](-4))
    if ($previousDpi -eq [IntPtr]::Zero) { throw 'Per-monitor DPI awareness was not available' }
} catch {
    [void][DqaTaskbarProbe]::SetProcessDPIAware()
    $dpiAwareness = 'system-aware-fallback'
}
$hwnd = [DqaTaskbarProbe]::FindWindow('Shell_TrayWnd', $null)
if ($hwnd -eq [IntPtr]::Zero) { throw 'Windows taskbar was not found' }
$taskbar = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
$all = $taskbar.FindAll([System.Windows.Automation.TreeScope]::Descendants,
                       [System.Windows.Automation.Condition]::TrueCondition)
$candidates = @()
foreach ($element in $all) {
    if ($element.Current.Name -match '(DQA|Python)') {
        $rect = $element.Current.BoundingRectangle
        if (-not $element.Current.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0) {
            $candidates += @{name=$element.Current.Name;left=[int]$rect.X;top=[int]$rect.Y;
                             width=[int]$rect.Width;height=[int]$rect.Height;provider='UIA'}
        }
    }
}
$legacyError = $null
try {
    $taskList = $taskbar.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ClassNameProperty, 'MSTaskListWClass')))
    if ($taskList) {
        foreach ($entry in [DqaTaskbarProbe]::Read([IntPtr]$taskList.Current.NativeWindowHandle)) {
            $candidates += @{name=$entry.name;left=$entry.left;top=$entry.top;
                             width=$entry.width;height=$entry.height;provider='MSAA'}
        }
    }
} catch { $legacyError = $_.Exception.Message }
$seen = @{}
$captures = @()
$failures = @()
foreach ($entry in $candidates) {
    $key = "$($entry.left),$($entry.top),$($entry.width),$($entry.height)"
    if ($seen.ContainsKey($key)) { continue }
    $seen[$key] = $true
    # MSAA still reports taskbar coordinates while the lock screen covers it.
    $points = @(
        @(([int]($entry.left + $entry.width / 2)), ([int]($entry.top + $entry.height / 2))),
        @(($entry.left + 1), ($entry.top + 1)),
        @(($entry.left + $entry.width - 2), ($entry.top + 1)),
        @(($entry.left + 1), ($entry.top + $entry.height - 2)),
        @(($entry.left + $entry.width - 2), ($entry.top + $entry.height - 2))
    )
    $occluded = $false
    foreach ($point in $points) {
        $rootAtPoint = [DqaTaskbarProbe]::RootAt($point[0], $point[1])
        if ($rootAtPoint -ne $hwnd) {
            $failures += @{name=$entry.name;rect=$key;reason='taskbar-occluded';
                           coveringClass=[DqaTaskbarProbe]::WindowClass($rootAtPoint)}
            $occluded = $true
            break
        }
    }
    if ($occluded) { continue }
    $image = Join-Path $OutputDir ('taskbar-button-' + $captures.Count + '.png')
    $bitmap = New-Object System.Drawing.Bitmap($entry.width, $entry.height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($entry.left, $entry.top, 0, 0, $bitmap.Size)
        $firstPixel = $bitmap.GetPixel(0, 0).ToArgb()
        $uniform = $true
        for ($y = 0; $y -lt $bitmap.Height -and $uniform; $y++) {
            for ($x = 0; $x -lt $bitmap.Width; $x++) {
                if ($bitmap.GetPixel($x, $y).ToArgb() -ne $firstPixel) { $uniform = $false; break }
            }
        }
        if ($uniform) {
            $failures += @{name=$entry.name;rect=$key;reason='uniform-pixels'}
            continue
        }
        $bitmap.Save($image)
    } finally { $graphics.Dispose(); $bitmap.Dispose() }
    $captures += @{name=$entry.name;provider=$entry.provider;image=$image;
                   rect=@($entry.left,$entry.top,$entry.width,$entry.height)}
}
$status = if ($captures.Count -gt 0 -and $failures.Count -eq 0) { 'CAPTURED' } else { 'BLOCKED' }
@{taskbarHandle=$hwnd.ToInt64();uiaDescendantCount=$all.Count;legacyError=$legacyError;
  dpiAwareness=$dpiAwareness;taskbarDpi=[DqaTaskbarProbe]::GetDpiForWindow($hwnd);
  captureStatus=$status;failures=$failures;buttonCaptures=$captures} | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath (Join-Path $OutputDir 'taskbar.json') -Encoding UTF8
if ($status -ne 'CAPTURED') {
    [Console]::Error.WriteLine('Taskbar capture blocked; inspect taskbar.json for occlusion or empty pixels.')
    exit 2
}
