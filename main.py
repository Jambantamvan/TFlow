#!/usr/bin/env python3
"""
TFlow v2.0 - Main Entry Point
Cross-platform Hardware & Power Telemetry Center for ASUS Gaming Laptops
Can be launched in GUI mode (default) or CLI mode.
"""

import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from backend import HardwareBackend

def run_cli():
    backend = HardwareBackend()
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print("Penggunaan CLI TFlow v2.0:")
        print("  python main.py                              -> Buka antarmuka GUI (G-Helper style)")
        print("  python main.py status                       -> Cek suhu, kipas, baterai, & daya")
        print("  python main.py profile <UltraSave|Balance|Performance> -> Ubah profil performa")
        print("  python main.py charge <60|80|100>           -> Atur batas pengisian baterai (Battery Care)")
        print("  python main.py fan <auto|silent|turbo|max>  -> Atur profil kipas")
        print("  python main.py set <persen>                 -> Atur manual kecepatan kipas (20-100%)")
        print("  python main.py auto                         -> Kembalikan kendali kipas ke Auto BIOS/EC")
        return

    cmd = sys.argv[1].lower().strip("-")
    if cmd == "status":
        c_temp = backend.get_cpu_temp()
        g_temp = backend.get_gpu_temp()
        cpu_rpm, gpu_rpm, mode = backend.get_fan_speeds()
        prof = backend.get_power_profile()
        bat = backend.get_battery_telemetry()
        charge_lim = backend.get_charge_threshold()
        print("============================================================")
        print("  TFlow v2.0 - Hardware & Power Telemetry Dashboard")
        print("============================================================")
        print(f"  Platform OS           : {backend.os_type}")
        print("  Power & Battery Subsystem:")
        print(f"    Active Profile      : {prof}")
        print(f"    AC Adapter Status   : {'Connected (AC Power)' if bat['is_ac'] else 'Disconnected (Battery)'}")
        print(f"    Battery Capacity    : {bat['capacity_pct']}%")
        print(f"    Discharge / Power   : {bat['power_w']:.1f} W")
        print(f"    Battery Health      : {bat['health_pct']:.1f}%")
        print(f"    Remaining Time      : {bat['remaining_time']}")
        print(f"    Battery Care Limit  : {charge_lim}%")
        print("  Thermal & Cooling Subsystem:")
        print(f"    CPU Temperature     : {c_temp:.1f} °C")
        print(f"    GPU Temperature     : {g_temp if g_temp is not None else 'Standby'} °C")
        print(f"    Dual Fan Tachometer : CPU {cpu_rpm} RPM | GPU {gpu_rpm} RPM ({mode})")
        print("============================================================")
    elif cmd in ["profile", "mode"] and len(sys.argv) >= 3:
        p_arg = sys.argv[2]
        backend.set_power_profile(p_arg)
        p_lower = p_arg.lower()
        if "ultra" in p_lower or "silent" in p_lower or "saver" in p_lower:
            backend.set_fan_speed(35)
            p_name = "UltraSave (Silent Fan)"
        elif "perf" in p_lower or "turbo" in p_lower or "high" in p_lower:
            backend.set_fan_speed(85)
            p_name = "Performance (Turbo Fan)"
        else:
            backend.set_fan_speed(0)
            p_name = "Balance (Auto Fan)"
        print(f"⚡ Profil performa diatur ke {p_name}.")
    elif cmd in ["charge", "charge-limit", "limit"] and len(sys.argv) >= 3:
        try:
            lim = int(sys.argv[2])
            backend.set_charge_threshold(lim)
            print(f"🔋 Battery Care limit diatur ke {lim}%.")
        except ValueError:
            print("Nilai batas pengisian tidak valid. Gunakan 60, 80, atau 100.")
    elif cmd in ["fan"] and len(sys.argv) >= 3:
        f_arg = sys.argv[2].lower()
        if f_arg in ["auto", "default", "balance"]:
            backend.set_fan_speed(0)
            print("🔄 Kendali kipas dikembalikan ke Auto (EC).")
        elif f_arg in ["silent", "quiet"]:
            backend.set_fan_speed(35)
            print("🤫 Kipas diatur ke mode Silent (35%).")
        elif f_arg in ["turbo", "perf", "performance"]:
            backend.set_fan_speed(85)
            print("🚀 Kipas diatur ke mode Turbo (85%).")
        elif f_arg in ["max", "100"]:
            backend.set_fan_speed(100)
            print("🚀 Kipas dipaksa 100% maksimal!")
        elif f_arg.isdigit():
            pct = int(f_arg)
            backend.set_fan_speed(pct)
            print(f"⚙️  Kipas diatur ke {pct}%.")
        else:
            print("Profil kipas tidak dikenal. Gunakan auto, silent, turbo, max, atau persentase.")
    elif cmd in ["max", "full", "100"]:
        backend.set_fan_speed(100)
        print("🚀 Kipas berhasil dipaksa 100% maksimal!")
    elif cmd == "set" and len(sys.argv) >= 3:
        try:
            pct = int(sys.argv[2])
            backend.set_fan_speed(pct)
            print(f"⚙️  Kipas diatur ke {pct}%.")
        except ValueError:
            print("Nilai persentase tidak valid.")
    elif cmd in ["auto", "normal"]:
        backend.set_fan_speed(0)
        print("🔄 Kendali kipas dikembalikan ke Auto (EC).")
    else:
        print("Perintah tidak dikenali. Jalankan 'python main.py --help' untuk panduan.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] not in ["--gui", "-g"]:
        run_cli()
    else:
        import tkinter as tk
        from gui import TFlowApp
        root = tk.Tk()
        app = TFlowApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
