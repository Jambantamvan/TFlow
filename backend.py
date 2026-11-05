"""
TFlow v2.0 - Hardware Abstraction Layer
Cross-platform support (Linux & Windows) for ASUS TUF Gaming laptops.
"""

import sys
import os
import platform
import subprocess
import glob
import re
import json

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
WIN_BIN_DIR = os.path.join(PROJECT_DIR, "windows_bin")

class HardwareBackend:
    def __init__(self):
        self.os_type = "Windows" if IS_WINDOWS else "Linux"
        self._init_paths()

    def _init_paths(self):
        if IS_LINUX:
            self.ec_tool = "/usr/local/bin/asus-fan-control-ec"
            self.platform_dir = "/sys/devices/platform/asus-nb-wmi"
            self.no_turbo_path = "/sys/devices/system/cpu/intel_pstate/no_turbo"
        else:
            self.afc_exe = os.path.join(WIN_BIN_DIR, "AsusFanControl.exe")
            self.psexec_exe = os.path.join(WIN_BIN_DIR, "PsExec.exe")
            if not os.path.exists(self.afc_exe):
                alt_path = r"C:\Users\abrar\AsusFanControl\AsusFanControl.exe"
                if os.path.exists(alt_path):
                    self.afc_exe = alt_path
                    self.psexec_exe = r"C:\Users\abrar\AsusFanControl\PsExec.exe"

    def _run_silent(self, cmd, capture_output=True, timeout=2):
        """Execute subprocess silently without triggering any console popup windows on Windows."""
        cflags = 0x08000000 if IS_WINDOWS else 0
        startupinfo = None
        if IS_WINDOWS:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
        if capture_output:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=cflags,
                startupinfo=startupinfo
            )
        else:
            return subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                creationflags=cflags,
                startupinfo=startupinfo
            )

    # ------------------ THERMAL TELEMETRY ------------------

    def get_cpu_temp(self) -> float:
        if IS_LINUX:
            temps = []
            for hwmon in glob.glob("/sys/devices/platform/coretemp.*/hwmon/hwmon*"):
                for t_file in glob.glob(os.path.join(hwmon, "temp*_input")):
                    try:
                        with open(t_file, "r") as f:
                            val = f.read().strip()
                            if val.isdigit():
                                temps.append(int(val) / 1000.0)
                    except Exception:
                        pass
            return max(temps) if temps else 45.0
        else:
            # Windows path 1: AsusFanControl.exe --get-cpu-temp (needs SYSTEM via PsExec)
            try:
                cmd = [self.psexec_exe, "-accepteula", "-s", self.afc_exe, "--get-cpu-temp"]
                res = self._run_silent(cmd, capture_output=True, timeout=5)
                val = res.stdout.strip()
                if res.returncode == 0 and val.replace(".", "", 1).lstrip("-").isdigit():
                    t = float(val)
                    if 10.0 < t < 120.0:
                        return t
            except Exception:
                pass
            # Windows path 2: WMI MSAcpi_ThermalZoneTemperature (needs admin, works when run.bat elevates)
            try:
                ps = (
                    "try {"
                    "$tz = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop;"
                    "$max = ($tz | ForEach-Object { ($_.CurrentTemperature - 2732) / 10 } | Measure-Object -Maximum).Maximum;"
                    "Write-Output ([math]::Round($max, 1))"
                    "} catch { Write-Output '0' }"
                )
                res = self._run_silent(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                    capture_output=True, timeout=4
                )
                val = res.stdout.strip()
                if val.replace(".", "", 1).lstrip("-").isdigit():
                    t = float(val)
                    if 10.0 < t < 120.0:
                        return t
            except Exception:
                pass
            return 0.0  # Indicate unavailable — UI should show "N/A"

    def get_gpu_temp(self):
        try:
            cmd = ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"]
            res = self._run_silent(cmd, capture_output=True, timeout=3)
            if res.returncode == 0:
                out = res.stdout.strip()
                # nvidia-smi returns plain integer e.g. "47"
                if out.isdigit():
                    return float(out)
                # Sometimes has extra whitespace or newline — try after strip
                out_clean = re.sub(r"[^\d]", "", out)
                if out_clean:
                    return float(out_clean)
        except Exception:
            pass
        return 0.0  # Indicate unavailable — UI should show "N/A"

    # ------------------ FAN CONTROL & RPM ------------------

    def get_fan_speeds(self):
        """Returns (cpu_rpm, gpu_rpm, mode_str)"""
        if IS_LINUX:
            try:
                res = subprocess.run([self.ec_tool, "fan-speed"], capture_output=True, text=True, timeout=2)
                cpu_rpm = "0"
                gpu_rpm = "0"
                mode = "Auto"
                for line in res.stdout.splitlines():
                    if "Fan control:" in line:
                        mode = line.split(":", 1)[1].strip()
                    elif "fan 0:" in line:
                        m = re.search(r"(\d+)\s*rpm", line)
                        if m: cpu_rpm = m.group(1)
                    elif "fan 1:" in line:
                        m = re.search(r"(\d+)\s*rpm", line)
                        if m: gpu_rpm = m.group(1)
                return cpu_rpm, gpu_rpm, mode
            except Exception:
                return "0", "0", "Auto"
        else:
            # Windows: Try PsExec (SYSTEM) first, then direct (admin), parse "XXXX, YYYY" digits
            def _parse_fan_output(text):
                speeds = [s.strip() for s in re.split(r"[,\s]+", text) if s.strip().isdigit()]
                return (speeds[0], speeds[1]) if len(speeds) >= 2 else None

            # Attempt 1: PsExec -> SYSTEM privilege (works when launched via run.bat as admin)
            try:
                cmd = [self.psexec_exe, "-accepteula", "-s", self.afc_exe, "--get-fan-speeds"]
                res = self._run_silent(cmd, capture_output=True, timeout=5)
                result = _parse_fan_output(res.stdout)
                if result:
                    return result[0], result[1], "Auto"
            except Exception:
                pass

            # Attempt 2: Direct AsusFanControl (sometimes works with admin-only, no SYSTEM)
            try:
                cmd = [self.afc_exe, "--get-fan-speeds"]
                res = self._run_silent(cmd, capture_output=True, timeout=3)
                result = _parse_fan_output(res.stdout)
                if result:
                    return result[0], result[1], "Auto"
            except Exception:
                pass

            return "0", "0", "Auto"

    def set_fan_speed(self, percent: int):
        """Set fan speed (0-100%). percent=0 means return to Auto/EC default."""
        percent = max(0, min(100, int(percent)))
        if IS_LINUX:
            if percent <= 0:
                subprocess.run([self.ec_tool, "set", "-1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([self.ec_tool, "setp", str(percent), "--fan", "0", "--no-verify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run([self.ec_tool, "setp", str(percent), "--fan", "1", "--no-verify"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Windows: Uses AsusFanControl.exe --set-fan-speeds=N silently
            try:
                cmd = [self.psexec_exe, "-accepteula", "-s", self.afc_exe, f"--set-fan-speeds={percent}"]
                self._run_silent(cmd, capture_output=False)
            except Exception:
                try:
                    self._run_silent([self.afc_exe, f"--set-fan-speeds={percent}"], capture_output=False)
                except Exception:
                    pass

    # ------------------ BATTERY TELEMETRY & CARE ------------------

    def set_charge_threshold(self, limit: int):
        """Set hardware battery charge limit (60%, 80%, or 100%)."""
        limit = 60 if limit <= 60 else (80 if limit <= 80 else 100)
        if IS_LINUX:
            thresh_path = "/sys/class/power_supply/BAT1/charge_control_end_threshold"
            self._write_sysfs(thresh_path, str(limit))
        else:
            try:
                cmd = [
                    "reg", "add",
                    r"HKLM\SOFTWARE\ASUS\ASUS System Control Interface\AsusOptimization\ASUSLink",
                    "/v", "BatteryHealthCharging",
                    "/t", "REG_DWORD",
                    "/d", str(limit),
                    "/f"
                ]
                self._run_silent(cmd, capture_output=False)
            except Exception:
                pass

    def get_charge_threshold(self) -> int:
        """Read hardware battery charge limit (returns 60, 80, or 100)."""
        if IS_LINUX:
            thresh_path = "/sys/class/power_supply/BAT1/charge_control_end_threshold"
            try:
                with open(thresh_path, "r") as f:
                    return int(f.read().strip())
            except Exception:
                return 80
        else:
            try:
                cmd = [
                    "reg", "query",
                    r"HKLM\SOFTWARE\ASUS\ASUS System Control Interface\AsusOptimization\ASUSLink",
                    "/v", "BatteryHealthCharging"
                ]
                res = self._run_silent(cmd, capture_output=True, timeout=2)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "BatteryHealthCharging" in line:
                            parts = line.split()
                            val_str = parts[-1]
                            return int(val_str, 16) if val_str.startswith("0x") else int(val_str)
            except Exception:
                pass
            return 80

    def get_battery_telemetry(self):
        """Returns dict with capacity_pct, health_pct, power_w, remaining_time, full_runtime, is_ac"""
        if IS_LINUX:
            bat_dir = "/sys/class/power_supply/BAT1"
            acad_path = "/sys/class/power_supply/ACAD/online"
            is_ac = True
            try:
                with open(acad_path, "r") as f:
                    is_ac = f.read().strip() == "1"
            except Exception:
                pass

            capacity_pct = 100
            try:
                with open(os.path.join(bat_dir, "capacity"), "r") as f:
                    capacity_pct = int(f.read().strip())
            except Exception:
                pass

            charge_full = 1.0
            charge_design = 1.0
            try:
                with open(os.path.join(bat_dir, "charge_full"), "r") as f:
                    charge_full = float(f.read().strip())
                with open(os.path.join(bat_dir, "charge_full_design"), "r") as f:
                    charge_design = float(f.read().strip())
            except Exception:
                pass
            health_pct = min(100.0, (charge_full / max(1.0, charge_design)) * 100.0)

            power_w = 0.0
            try:
                with open(os.path.join(bat_dir, "voltage_now"), "r") as f:
                    v = float(f.read().strip())
                with open(os.path.join(bat_dir, "current_now"), "r") as f:
                    i = float(f.read().strip())
                power_w = (v * i) / 1e12
            except Exception:
                pass

            remaining_time = "Connected (AC)" if is_ac else "2h 30m"
            full_runtime = "2h 45m"
            return {
                "capacity_pct": capacity_pct,
                "health_pct": round(health_pct, 1),
                "power_w": round(power_w, 1),
                "remaining_time": remaining_time,
                "full_runtime": full_runtime,
                "is_ac": is_ac
            }
        else:
            # Windows: Combine ctypes (fast AC/%) + WMI BatteryStatus (real power/health)
            is_ac = True
            capacity_pct = 100
            rem_str = "Connected (AC)"

            # --- Step 1: AC status + battery % via ctypes (0 ms, no subprocess) ---
            try:
                import ctypes
                from ctypes import wintypes
                class SPS(ctypes.Structure):
                    _fields_ = [
                        ('ACLineStatus', wintypes.BYTE),
                        ('BatteryFlag', wintypes.BYTE),
                        ('BatteryLifePercent', wintypes.BYTE),
                        ('Reserved', wintypes.BYTE),
                        ('BatteryLifeTime', wintypes.DWORD),
                        ('BatteryFullLifeTime', wintypes.DWORD),
                    ]
                sps = SPS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                    is_ac = (sps.ACLineStatus == 1)
                    if sps.BatteryLifePercent <= 100:
                        capacity_pct = int(sps.BatteryLifePercent)
                    if not is_ac and sps.BatteryLifeTime != 0xFFFFFFFF and sps.BatteryLifeTime > 0:
                        mins = sps.BatteryLifeTime // 60
                        rem_str = f"{mins // 60}h {mins % 60}m"
            except Exception:
                pass

            # --- Step 2: Real WMI BatteryStatus + BatteryFullChargedCapacity (no admin needed) ---
            design_mwh = 48000  # FX506LH spec: 48 Wh = 48000 mWh
            full_mwh = 0
            remaining_mwh = 0
            discharge_mw = 0
            charge_mw = 0

            try:
                ps = (
                    "$b = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue | Select-Object -First 1;"
                    "$f = Get-CimInstance -Namespace root/wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue | Select-Object -First 1;"
                    "if ($b -and $f) {"
                    "  $obj = @{"
                    "    PowerOnline=$b.PowerOnline;"
                    "    RemainingCapacity=$b.RemainingCapacity;"
                    "    DischargeRate=$b.DischargeRate;"
                    "    ChargeRate=$b.ChargeRate;"
                    "    Voltage=$b.Voltage;"
                    "    FullChargedCapacity=$f.FullChargedCapacity"
                    "  };"
                    "  ConvertTo-Json $obj -Compress"
                    "}"
                )
                res = self._run_silent(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                    capture_output=True, timeout=5
                )
                if res.returncode == 0 and res.stdout.strip().startswith("{"):
                    data = json.loads(res.stdout.strip())
                    full_mwh = int(data.get("FullChargedCapacity", 0))
                    remaining_mwh = int(data.get("RemainingCapacity", 0))
                    discharge_mw = int(data.get("DischargeRate", 0))
                    charge_mw = int(data.get("ChargeRate", 0))
                    # PowerOnline from WMI is more reliable than ctypes for AC detection
                    is_ac = bool(data.get("PowerOnline", is_ac))
            except Exception:
                pass

            # --- Step 3: Calculate derived metrics ---
            health_pct = round((full_mwh / design_mwh) * 100.0, 1) if full_mwh > 0 else 0.0

            # Power draw: positive = discharging, negative = charging
            if is_ac:
                power_w = round(charge_mw / 1000.0, 1) if charge_mw > 0 else 0.0
            else:
                power_w = round(discharge_mw / 1000.0, 1) if discharge_mw > 0 else 0.0

            # Remaining runtime from WMI data (more accurate than ctypes)
            if not is_ac and discharge_mw > 0 and remaining_mwh > 0:
                mins = int((remaining_mwh / discharge_mw) * 60)
                rem_str = f"{mins // 60}h {mins % 60}m"
            elif is_ac:
                rem_str = "Connected (AC)"

            # Full battery runtime at current discharge rate
            full_runtime = "N/A"
            if discharge_mw > 0 and full_mwh > 0:
                mins = int((full_mwh / discharge_mw) * 60)
                full_runtime = f"{mins // 60}h {mins % 60}m"
            elif full_mwh > 0:
                # Estimate using typical 15W idle draw
                mins = int((full_mwh / 15000) * 60)
                full_runtime = f"~{mins // 60}h {mins % 60}m"

            return {
                "capacity_pct": capacity_pct,
                "health_pct": health_pct,
                "power_w": power_w,
                "remaining_time": rem_str,
                "full_runtime": full_runtime,
                "is_ac": is_ac
            }

    # ------------------ POWER PROFILES ------------------

    def set_power_profile(self, profile: str):
        """
        Profiles: 'UltraSave', 'Balance', 'Performance'
        """
        if IS_LINUX:
            asus_map = {"UltraSave": "Quiet", "Balance": "Balanced", "Performance": "Performance"}
            prof_name = asus_map.get(profile, "Balanced")
            try:
                subprocess.run(["asusctl", "profile", "set", prof_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            policy_map = {"UltraSave": "2", "Balance": "0", "Performance": "1"}
            val = policy_map.get(profile, "0")
            self._write_sysfs(os.path.join(self.platform_dir, "throttle_thermal_policy"), val)
            self._write_sysfs(os.path.join(self.platform_dir, "fan_boost_mode"), val)

            rapl_base = "/sys/class/powercap/intel-rapl/intel-rapl:0"
            if profile == "UltraSave":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "10000000") # 10W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "12000000") # 12W
                self._write_sysfs(self.no_turbo_path, "1")
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "50")
            elif profile == "Balance":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "28000000") # 28W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "45000000") # 45W
                self._write_sysfs(self.no_turbo_path, "0")
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "100")
            elif profile == "Performance":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "45000000") # 45W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "70000000") # 70W
                self._write_sysfs(self.no_turbo_path, "0")
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "100")
        else:
            # Windows Power Schemes via powercfg
            cflags = 0x08000000 if IS_WINDOWS else 0
            guid_sub = "54533251-82be-4824-96c1-47b60b740d00"
            guid_setting = "be337238-0d82-4146-a960-4f3749d470c7"
            p_lower = profile.lower()
            if "ultra" in p_lower or "silent" in p_lower or "saver" in p_lower:
                scheme = "a1841308-3541-4fab-bc81-f71556f20b4a" # Power Saver
                boost_idx = "0" # Disable CPU Boost
            elif "perf" in p_lower or "turbo" in p_lower or "high" in p_lower:
                scheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" # High Performance
                boost_idx = "2" # Aggressive Boost
            else:
                scheme = "381b4222-f694-41f0-9685-ff5bb260df2e" # Balanced
                boost_idx = "4" # Dynamic Boost

            try:
                self._run_silent(["powercfg", "/setactive", scheme], capture_output=False)
                self._run_silent(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", guid_sub, guid_setting, boost_idx], capture_output=False)
                self._run_silent(["powercfg", "/setactive", "SCHEME_CURRENT"], capture_output=False)
            except Exception:
                pass

    def get_power_profile(self) -> str:
        if IS_LINUX:
            try:
                with open("/sys/firmware/acpi/platform_profile", "r") as f:
                    v = f.read().strip().lower()
                    if "quiet" in v: return "UltraSave"
                    elif "performance" in v: return "Performance"
                    else: return "Balance"
            except Exception:
                return "Balance"
        else:
            try:
                res = self._run_silent(["powercfg", "/getactivescheme"])
                out = res.stdout.lower()
                if "a1841308" in out:
                    return "UltraSave"
                elif "8c5e7fda" in out:
                    return "Performance"
                else:
                    return "Balance"
            except Exception:
                return "Balance"

    def _write_sysfs(self, path: str, value: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "w") as f:
                f.write(value)
        except Exception:
            pass
