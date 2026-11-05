$tz = (Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation -ErrorAction SilentlyContinue | Select-Object -First 1).HighPrecisionTemperature
$b = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1
$f = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object -First 1
$res = @{
    CpuTemp = if ($tz) { [math]::Round(($tz - 2732) / 10, 1) } else { 0 }
    FullCharged = if ($f) { $f.FullChargedCapacity } else { 0 }
    Remaining = if ($b) { $b.RemainingCapacity } else { 0 }
    Discharge = if ($b) { $b.DischargeRate } else { 0 }
    Charge = if ($b) { $b.ChargeRate } else { 0 }
    PowerOnline = if ($b) { $b.PowerOnline } else { $true }
}
ConvertTo-Json $res -Compress