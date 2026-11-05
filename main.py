#!/usr/bin/env python3
"""
TFlow - Main Entry Point
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
        print("Penggunaan CLI TFlow:")
        print("  python main.py                  -> Buka antarmuka GUI (G-Helper style)")
        print("  python main.py status           -> Cek suhu & status kipas saat ini")
        print("  python main.py max              -> Paksa kipas 100% maksimal")
        print("  python main.py set <persen>     -> Atur kecepatan kipas (misal: 80)")
        print("  python main.py auto             -> Kembalikan kendali kipas ke Auto BIOS")
        print("  python main.py cold <on|off>    -> Nyalakan / matikan Mode Dingin (CPU Boost Limit)")
        print("  python main.py profile <Silent|Balanced|Turbo> -> Ubah profil performa")
        return

    cmd = sys.argv[1].lower()
    if cmd == "status":
        c_temp = backend.get_cpu_temp()
        g_temp = backend.get_gpu_temp()
        cpu_rpm, gpu_rpm, mode = backend.get_fan_speeds()
        cold = backend.get_cold_mode()
        prof = backend.get_power_profile()
        print("========================================")
        print("             TFLOW - STATUS             ")
        print("========================================")
        print(f"OS Platform     : {backend.os_type}")
        print(f"Suhu CPU        : {c_temp:.1f} °C")
        print(f"Suhu GPU        : {g_temp if g_temp is not None else 'Standby'} °C")
        print(f"Putaran Kipas   : CPU {cpu_rpm} RPM | GPU {gpu_rpm} RPM ({mode})")
        print(f"Profil Daya     : {prof}")
        print(f"Mode Dingin CPU : {'AKTIF (Dingin)' if cold else 'MATI (Boost)'}")
        print("========================================")
    elif cmd in ["max", "full", "100"]:
        backend.set_fan_speed(100)
        print("🚀 Kipas berhasil dipaksa 100% maksimal!")
    elif cmd == "set" and len(sys.argv) >= 3:
        pct = int(sys.argv[2])
        backend.set_fan_speed(pct)
        print(f"⚙️  Kipas diatur ke {pct}%.")
    elif cmd in ["auto", "normal"]:
        backend.set_fan_speed(0)
        print("🔄 Kendali kipas dikembalikan ke Auto (EC).")
    elif cmd == "cold" and len(sys.argv) >= 3:
        enable = sys.argv[2].lower() in ["on", "1", "true", "aktif"]
        backend.set_cold_mode(enable)
        print(f"❄️ Mode Dingin CPU: {'AKTIF (Maks. ~70°C)' if enable else 'NONAKTIF (Full Boost)'}")
    elif cmd == "profile" and len(sys.argv) >= 3:
        backend.set_power_profile(sys.argv[2].capitalize())
        print(f"⚡ Profil performa diatur ke {sys.argv[2].capitalize()}.")
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

