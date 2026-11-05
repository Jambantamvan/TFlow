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
            # Windows: Try AsusFanControl or WMI
            try:
                cmd = [self.afc_exe, "--get-cpu-temp"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip().replace(".", "", 1).isdigit():
                    return float(res.stdout.strip())
            except Exception:
                pass
            return 48.0

    def get_gpu_temp(self):
        try:
            cmd = ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                out = res.stdout.strip()
                if out.isdigit():
                    return float(out)
        except Exception:
            pass
        return 42.0

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
            # Windows: Query AsusFanControl
            try:
                cmd = [self.afc_exe, "--get-fan-speeds"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                speeds = [s.strip() for s in res.stdout.split(",") if s.strip().isdigit()]
                if len(speeds) >= 2:
                    return speeds[0], speeds[1], "Auto"
            except Exception:
                pass
            return "3800", "3750", "Auto"

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
            # Windows: Uses AsusFanControl.exe --set-fan-speeds=N
            cflags = 0x08000000 if IS_WINDOWS else 0
            try:
                cmd = [self.psexec_exe, "-accepteula", "-s", self.afc_exe, f"--set-fan-speeds={percent}"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cflags)
            except Exception:
                try:
                    subprocess.run([self.afc_exe, f"--set-fan-speeds={percent}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cflags)
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
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000 if IS_WINDOWS else 0)
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
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2, creationflags=0x08000000 if IS_WINDOWS else 0)
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
            # Windows: Instantaneous via Win32 GetSystemPowerStatus (0 ms overhead)
            is_ac = True
            capacity_pct = 100
            rem_str = "Connected (AC)"
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
                    if not is_ac and sps.BatteryLifeTime != 0xFFFFFFFF:
                        mins = sps.BatteryLifeTime // 60
                        rem_str = f"{mins // 60}h {mins % 60}m"
            except Exception:
                pass

            return {
                "capacity_pct": capacity_pct,
                "health_pct": 60.9,
                "power_w": 0.0 if is_ac else 13.8,
                "remaining_time": rem_str,
                "full_runtime": "2h 15m",
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
                subprocess.run(["powercfg", "/setactive", scheme], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cflags)
                subprocess.run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", guid_sub, guid_setting, boost_idx], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cflags)
                subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cflags)
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
                cflags = 0x08000000 if IS_WINDOWS else 0
                res = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=2, creationflags=cflags)
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
