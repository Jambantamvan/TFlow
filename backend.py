"""
TUF Control Center - Hardware Abstraction Layer
Supports both Linux and Windows for ASUS TUF Gaming FX506LH
"""

import sys
import os
import platform
import subprocess
import glob
import re

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
            # Fallback to C:\Users\abrar\AsusFanControl if windows_bin is moved
            if not os.path.exists(self.afc_exe):
                alt_path = r"C:\Users\abrar\AsusFanControl\AsusFanControl.exe"
                if os.path.exists(alt_path):
                    self.afc_exe = alt_path
                    self.psexec_exe = r"C:\Users\abrar\AsusFanControl\PsExec.exe"

    # ------------------ SUHU (TEMPERATURES) ------------------

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
            return max(temps) if temps else 0.0
        else:
            # Windows: Try AsusFanControl.exe --get-cpu-temp
            try:
                cmd = [self.afc_exe, "--get-cpu-temp"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip().replace(".", "", 1).isdigit():
                    return float(res.stdout.strip())
            except Exception:
                pass
            return 0.0

    def get_gpu_temp(self) -> float:
        try:
            cmd = ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                out = res.stdout.strip()
                if out.isdigit():
                    return float(out)
        except Exception:
            pass
        return None

    # ------------------ KIPAS (FAN CONTROL & RPM) ------------------

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
                return "0", "0", "Unknown"
        else:
            # Windows
            try:
                cmd = [self.afc_exe, "--get-fan-speeds"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                # Output might be "4150, 3700" or similar
                speeds = [s.strip() for s in res.stdout.split(",") if s.strip().isdigit()]
                if len(speeds) >= 2:
                    return speeds[0], speeds[1], "Active"
                elif len(speeds) == 1:
                    return speeds[0], speeds[0], "Active"
            except Exception:
                pass
            return "N/A", "N/A", "Windows"

    def set_fan_speed(self, percent: int):
        """Set fan speed (0-100%). percent=0 means return to Auto/EC default."""
        percent = max(0, min(100, int(percent)))
        if IS_LINUX:
            if percent <= 0:
                # Release to EC
                subprocess.run([self.ec_tool, "set", "-1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run([self.ec_tool, "setp", str(percent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Windows: Uses AsusFanControl.exe --set-fan-speeds=N
            # If using PsExec: PsExec.exe -accepteula -s AsusFanControl.exe --set-fan-speeds=N
            try:
                cmd = [self.psexec_exe, "-accepteula", "-s", self.afc_exe, f"--set-fan-speeds={percent}"]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000 if IS_WINDOWS else 0)
            except Exception:
                try:
                    subprocess.run([self.afc_exe, f"--set-fan-speeds={percent}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

    # ------------------ PROFIL DAYA (POWER PROFILES) ------------------

    def set_power_profile(self, profile: str):
        """
        profile: 'Silent', 'Balanced', 'Turbo'
        Melakukan tuning menyeluruh pada CPU dan GPU:
        - Silent   : CPU PL1 25W/PL2 35W, Turbo OFF, EPP power, GPU max 1200 MHz
        - Balanced : CPU PL1 35W/PL2 50W, Turbo ON (cap 85%), EPP balance_performance, GPU max 1450 MHz
        - Turbo    : CPU PL1 50W/PL2 78W, Turbo ON (100%), EPP performance, GPU full boost (1785 MHz)
        """
        if IS_LINUX:
            # 1. ASUS Platform Profile & Hotkey Sync
            asus_map = {"Silent": "Quiet", "Balanced": "Balanced", "Turbo": "Performance"}
            prof_name = asus_map.get(profile, profile)
            try:
                subprocess.run(["asusctl", "profile", "set", prof_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

            policy_map = {"Silent": "2", "Balanced": "0", "Turbo": "1"}
            val = policy_map.get(profile, "0")
            self._write_sysfs(os.path.join(self.platform_dir, "fan_boost_mode"), val)
            self._write_sysfs(os.path.join(self.platform_dir, "throttle_thermal_policy"), val)

            # 2. CPU & GPU Hardware Tuning
            rapl_base = "/sys/class/powercap/intel-rapl:0"
            if profile == "Silent":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "25000000") # 25W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "35000000") # 35W
                self._write_sysfs(self.no_turbo_path, "1") # Turbo OFF
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "60")
                self._set_cpu_epp("power")
                self._set_gpu_clock_limit(300, 1200)

            elif profile == "Balanced":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "35000000") # 35W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "50000000") # 50W
                self._write_sysfs(self.no_turbo_path, "0") # Turbo ON
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "85") # ~3.5 GHz cap
                self._set_cpu_epp("balance_performance")
                self._set_gpu_clock_limit(300, 1450)

            elif profile == "Turbo":
                self._write_sysfs(os.path.join(rapl_base, "constraint_0_power_limit_uw"), "50000000") # 50W
                self._write_sysfs(os.path.join(rapl_base, "constraint_1_power_limit_uw"), "78000000") # 78W
                self._write_sysfs(self.no_turbo_path, "0") # Turbo ON Full
                self._write_sysfs("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "100") # 4.2 GHz full
                self._set_cpu_epp("performance")
                self._reset_gpu_clock_limit()
        else:
            # Windows: Mengatur Power Scheme dan CPU Boost Mode
            guid_sub = "54533251-82be-4824-96c1-47b60b740d00"
            guid_setting = "be337238-0d82-4146-a960-4f3749d470c7"
            if profile == "Silent":
                boost_idx = "0"
                scheme = "a1841308-3541-4fab-bc81-f71556f20b4a" # Power Saver
            elif profile == "Balanced":
                boost_idx = "4"
                scheme = "381b4222-f694-41f0-9685-ff5bb260df2e" # Balanced
            else:
                boost_idx = "2"
                scheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" # High Performance

            try:
                subprocess.run(["powercfg", "/setactive", scheme], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", guid_sub, guid_setting, boost_idx], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def _set_cpu_epp(self, pref: str):
        for path in glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
            self._write_sysfs(path, pref)

    def _set_gpu_clock_limit(self, min_clk: int, max_clk: int):
        try:
            subprocess.run(["sudo", "-n", "nvidia-smi", "-lgc", f"{min_clk},{max_clk}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _reset_gpu_clock_limit(self):
        try:
            subprocess.run(["sudo", "-n", "nvidia-smi", "-rgc"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def get_power_profile(self) -> str:
        if IS_LINUX:
            try:
                with open("/sys/firmware/acpi/platform_profile", "r") as f:
                    v = f.read().strip().lower()
                    if "quiet" in v: return "Silent"
                    elif "performance" in v: return "Turbo"
                    else: return "Balanced"
            except Exception:
                return "Balanced"
        else:
            return "Balanced"

    # ------------------ MODE DINGIN (CPU BOOST TUNING) ------------------

    def set_cold_mode(self, enabled: bool):
        """
        Mode Dingin:
        - Linux: intel_pstate/no_turbo (1 = Disable Turbo, 0 = Enable Turbo)
        - Windows: powercfg GUID be337238-0d82-4146-a960-4f3749d470c7 (0 = Disable Boost, 2 = Aggressive)
        """
        if IS_LINUX:
            val = "1" if enabled else "0"
            self._write_sysfs(self.no_turbo_path, val)
        else:
            # Windows powercfg
            idx = "0" if enabled else "2"
            guid_sub = "54533251-82be-4824-96c1-47b60b740d00"
            guid_setting = "be337238-0d82-4146-a960-4f3749d470c7"
            try:
                subprocess.run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", guid_sub, guid_setting, idx],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", guid_sub, guid_setting, idx],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def get_cold_mode(self) -> bool:
        if IS_LINUX:
            try:
                with open(self.no_turbo_path, "r") as f:
                    return f.read().strip() == "1"
            except Exception:
                return False
        else:
            # On Windows, try querying powercfg
            try:
                guid_sub = "54533251-82be-4824-96c1-47b60b740d00"
                guid_setting = "be337238-0d82-4146-a960-4f3749d470c7"
                res = subprocess.run(["powercfg", "/query", "SCHEME_CURRENT", guid_sub, guid_setting],
                                     capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    if "Current AC Power Setting Index:" in line:
                        val = line.split(":", 1)[1].strip()
                        return val.endswith("0x00000000") or val == "0"
            except Exception:
                pass
            return False

    def _write_sysfs(self, path, value):
        try:
            with open(path, "w") as f:
                f.write(str(value) + "\n")
        except Exception:
            pass

