"""
TFlow v2.0 - Hardware & Fan Performance Manager
Tkinter Fallback GUI for Windows & Linux
High-density G-Helper inspired dark aesthetic (#0b0d13).
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from backend import HardwareBackend

# Color Theme (G-Helper Dark Aesthetic)
BG_MAIN = "#0b0d13"
BG_CARD = "#12151e"
BG_CARD_HOVER = "#181d2a"
BORDER_COLOR = "#1e2433"
ACCENT_BLUE = "#38bdf8"
ACCENT_GREEN = "#10b981"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"
ACCENT_PURPLE = "#c084fc"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#8b9bb4"
TEXT_SUB = "#64748b"

class TFlowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TFlow - ASUS Hardware & Power Manager")
        self.root.geometry("480x750")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)

        self.backend = HardwareBackend()
        self.running = True

        self.power_mode = "Balance"
        self.fan_mode = "Auto"
        self.charge_limit = 80

        self._setup_styles()
        self._build_ui()

        # Start live background polling (non-blocking)
        self.poll_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.poll_thread.start()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(
            "TFlow.Horizontal.TScale",
            troughcolor="#1e2433",
            background=ACCENT_BLUE,
            sliderlength=20,
            sliderthickness=14
        )

    def _build_ui(self):
        main_container = tk.Frame(self.root, bg=BG_MAIN, padx=14, pady=12)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ---------------- HEADER ----------------
        header_frame = tk.Frame(main_container, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        title_box = tk.Frame(header_frame, bg=BG_MAIN)
        title_box.pack(side=tk.LEFT)

        title_row = tk.Frame(title_box, bg=BG_MAIN)
        title_row.pack(anchor="w")

        tk.Label(title_row, text="TFlow", font=("Segoe UI", 14, "bold"), fg=TEXT_WHITE, bg=BG_MAIN).pack(side=tk.LEFT)
        tk.Label(title_row, text=" v2.0 ", font=("Segoe UI", 8, "bold"), fg=ACCENT_BLUE, bg="#1e293b").pack(side=tk.LEFT, padx=6)

        tk.Label(title_box, text=f"ASUS TUF FX506LH • {self.backend.os_type} Edition", font=("Segoe UI", 8), fg=TEXT_SUB, bg=BG_MAIN).pack(anchor="w")

        # Top Pills (AC Status & Wattage)
        pill_box = tk.Frame(header_frame, bg=BG_MAIN)
        pill_box.pack(side=tk.RIGHT)

        self.ac_pill = tk.Label(pill_box, text="Plugged In", font=("Segoe UI", 9, "bold"), fg=ACCENT_GREEN, bg="#064e3b", padx=8, pady=2)
        self.ac_pill.pack(side=tk.LEFT, padx=(0, 6))

        self.watt_pill = tk.Label(pill_box, text="0.0 W", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg="#111827", padx=8, pady=2)
        self.watt_pill.pack(side=tk.LEFT)

        # ---------------- SECTION 1: POWER & BATTERY PROFILE ----------------
        sec1 = self._create_card(main_container, "POWER & BATTERY PROFILE", "Active: Balance")
        self.sec1_hdr_right = sec1[1]
        sec1_body = sec1[0]

        p_btn_frame = tk.Frame(sec1_body, bg=BG_CARD)
        p_btn_frame.pack(fill=tk.X, pady=(6, 4))

        self.btn_ultra = self._create_seg_btn(p_btn_frame, "UltraSave", lambda: self.set_power("UltraSave"))
        self.btn_balance = self._create_seg_btn(p_btn_frame, "Balance", lambda: self.set_power("Balance"), active=True)
        self.btn_perf = self._create_seg_btn(p_btn_frame, "Performance", lambda: self.set_power("Performance"))

        self.btn_ultra.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_balance.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_perf.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.power_desc = tk.Label(
            sec1_body,
            text="Balanced daily profile: dynamic turbo boost, standard governor, Auto fan.",
            font=("Segoe UI", 8),
            fg=TEXT_SUB,
            bg=BG_CARD
        )
        self.power_desc.pack(anchor="w")

        # ---------------- SECTION 2: BATTERY TELEMETRY & HEALTH ----------------
        sec2 = self._create_card(main_container, "BATTERY TELEMETRY & HEALTH")
        sec2_body = sec2[0]

        # Row 1: Charge, Health, Power Draw
        b_row1 = tk.Frame(sec2_body, bg=BG_CARD)
        b_row1.pack(fill=tk.X, pady=(4, 6))

        self.badge_charge = self._create_badge(b_row1, "BATTERY CHARGE", "100%", ACCENT_BLUE)
        self.badge_health = self._create_badge(b_row1, "BATTERY HEALTH", "60.9%", ACCENT_GREEN)
        self.badge_power = self._create_badge(b_row1, "POWER DRAW", "0.0 W", ACCENT_GREEN)

        self.badge_charge.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.badge_health.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.badge_power.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Row 2: Runtimes
        b_row2 = tk.Frame(sec2_body, bg=BG_CARD)
        b_row2.pack(fill=tk.X, pady=(0, 6))

        self.badge_rem = self._create_badge(b_row2, "REMAINING RUNTIME", "Connected (AC)", TEXT_WHITE)
        self.badge_full = self._create_badge(b_row2, "FULL BATTERY RUNTIME", "2h 15m", "#a5b4fc")

        self.badge_rem.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.badge_full.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Charge Limit Controls
        c_limit_box = tk.Frame(sec2_body, bg=BG_CARD)
        c_limit_box.pack(fill=tk.X, pady=(4, 0))

        tk.Label(c_limit_box, text="Battery Care Charge Limit: 80% Max", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")

        c_btn_frame = tk.Frame(c_limit_box, bg=BG_CARD)
        c_btn_frame.pack(fill=tk.X, pady=(4, 0))

        self.btn_c60 = self._create_seg_btn(c_btn_frame, "60% (Desk)", lambda: self.set_charge(60))
        self.btn_c80 = self._create_seg_btn(c_btn_frame, "80% (Balanced)", lambda: self.set_charge(80), active=True)
        self.btn_c100 = self._create_seg_btn(c_btn_frame, "100% (Maximum)", lambda: self.set_charge(100))

        self.btn_c60.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_c80.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.btn_c100.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # ---------------- SECTION 3: THERMALS & FANS ----------------
        sec3 = self._create_card(main_container, "THERMALS & FANS", "Fan Mode: Auto")
        self.sec3_hdr_right = sec3[1]
        sec3_body = sec3[0]

        # CPU Row
        t_row1 = tk.Frame(sec3_body, bg=BG_CARD)
        t_row1.pack(fill=tk.X, pady=(4, 6))

        self.badge_cpu_temp = self._create_badge(t_row1, "CPU TEMPERATURE", "48°C", "#f87171")
        self.badge_cpu_fan = self._create_badge(t_row1, "CPU FAN SPEED", "3800 RPM", ACCENT_BLUE)
        self.badge_cpu_temp.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.badge_cpu_fan.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # GPU Row
        t_row2 = tk.Frame(sec3_body, bg=BG_CARD)
        t_row2.pack(fill=tk.X, pady=(0, 6))

        self.badge_gpu_temp = self._create_badge(t_row2, "GPU TEMPERATURE", "42°C", "#34d399")
        self.badge_gpu_fan = self._create_badge(t_row2, "GPU FAN SPEED", "3750 RPM", ACCENT_BLUE)
        self.badge_gpu_temp.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.badge_gpu_fan.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Fan Presets
        f_btn_frame = tk.Frame(sec3_body, bg=BG_CARD)
        f_btn_frame.pack(fill=tk.X, pady=(4, 6))

        self.btn_f_auto = self._create_seg_btn(f_btn_frame, "Auto", lambda: self.set_fan("Auto"), active=True)
        self.btn_f_silent = self._create_seg_btn(f_btn_frame, "Silent", lambda: self.set_fan("Silent"))
        self.btn_f_turbo = self._create_seg_btn(f_btn_frame, "Turbo", lambda: self.set_fan("Turbo"))
        self.btn_f_max = self._create_seg_btn(f_btn_frame, "Max 100%", lambda: self.set_fan("Max"))
        self.btn_f_manual = self._create_seg_btn(f_btn_frame, "Manual", lambda: self.set_fan("Manual"))

        self.btn_f_auto.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        self.btn_f_silent.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        self.btn_f_turbo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        self.btn_f_max.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        self.btn_f_manual.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # Manual Fan Duty Slider
        self.slider_frame = tk.Frame(sec3_body, bg=BG_CARD)
        slider_hdr = tk.Frame(self.slider_frame, bg=BG_CARD)
        slider_hdr.pack(fill=tk.X)
        tk.Label(slider_hdr, text="Manual Fan Duty:", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=BG_CARD).pack(side=tk.LEFT)
        self.slider_val_lbl = tk.Label(slider_hdr, text="60%", font=("Segoe UI", 8, "bold"), fg=ACCENT_PURPLE, bg=BG_CARD)
        self.slider_val_lbl.pack(side=tk.RIGHT)

        self.duty_slider = ttk.Scale(
            self.slider_frame,
            from_=20,
            to=100,
            orient=tk.HORIZONTAL,
            style="TFlow.Horizontal.TScale",
            command=self._on_slider_change
        )
        self.duty_slider.set(60)
        self.duty_slider.pack(fill=tk.X, pady=(2, 0))

        # ---------------- FOOTER ----------------
        footer_frame = tk.Frame(main_container, bg="#0d1017", padx=8, pady=4)
        footer_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Label(footer_frame, text="EC Controller: Active", font=("Segoe UI", 7), fg=TEXT_SUB, bg="#0d1017").pack(side=tk.LEFT)
        tk.Label(footer_frame, text=f"{self.backend.os_type} HAL Core", font=("Segoe UI", 7), fg=TEXT_SUB, bg="#0d1017").pack(side=tk.RIGHT)

    def _create_card(self, parent, title, right_text=None):
        card = tk.Frame(parent, bg=BG_CARD, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=10, pady=8)
        card.pack(fill=tk.X, pady=(0, 10))

        hdr = tk.Frame(card, bg=BG_CARD)
        hdr.pack(fill=tk.X)

        tk.Label(hdr, text=title, font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side=tk.LEFT)
        right_lbl = None
        if right_text:
            right_lbl = tk.Label(hdr, text=right_text, font=("Segoe UI", 8, "bold"), fg=ACCENT_BLUE, bg=BG_CARD)
            right_lbl.pack(side=tk.RIGHT)

        return card, right_lbl

    def _create_badge(self, parent, label, val, color):
        frame = tk.Frame(parent, bg="#141720", highlightbackground="#222938", highlightthickness=1, padx=8, pady=5)
        tk.Label(frame, text=label, font=("Segoe UI", 7, "bold"), fg=TEXT_MUTED, bg="#141720").pack(anchor="w")
        val_lbl = tk.Label(frame, text=val, font=("Segoe UI", 11, "bold"), fg=color, bg="#141720")
        val_lbl.pack(anchor="w")
        frame.val_lbl = val_lbl
        return frame

    def _create_seg_btn(self, parent, text, cmd, active=False):
        bg = "#1e293b" if active else "#11141c"
        fg = TEXT_WHITE if active else TEXT_MUTED
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 8, "bold" if active else "normal"),
            bg=bg,
            fg=fg,
            activebackground="#222938",
            activeforeground=TEXT_WHITE,
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=4,
            command=cmd
        )
        btn.active = active
        return btn

    def set_power(self, mode):
        self.power_mode = mode
        self.sec1_hdr_right.config(text=f"Active: {mode}")

        for b, m in [(self.btn_ultra, "UltraSave"), (self.btn_balance, "Balance"), (self.btn_perf, "Performance")]:
            is_act = m == mode
            b.config(bg="#1e293b" if is_act else "#11141c", fg=TEXT_WHITE if is_act else TEXT_MUTED)

        if mode == "UltraSave":
            self.power_desc.config(text="Ultra battery saving: PL1 10W, CPU capped to 1.2 GHz, Turbo off, Silent fan.")
            self.set_fan("Silent")
        elif mode == "Performance":
            self.power_desc.config(text="Max sustained boost: PL1 45W / PL2 70W, full 4.5 GHz boost, Turbo fan.")
            self.set_fan("Turbo")
        else:
            self.power_desc.config(text="Balanced daily profile: PL1 28W / PL2 45W, dynamic turbo scaling, Auto fan.")
            self.set_fan("Auto")

        threading.Thread(target=lambda: self.backend.set_power_profile(mode), daemon=True).start()

    def set_fan(self, mode):
        self.fan_mode = mode
        self.sec3_hdr_right.config(text=f"Fan Mode: {mode}")

        buttons = [
            (self.btn_f_auto, "Auto"),
            (self.btn_f_silent, "Silent"),
            (self.btn_f_turbo, "Turbo"),
            (self.btn_f_max, "Max"),
            (self.btn_f_manual, "Manual"),
        ]
        for b, m in buttons:
            is_act = m == mode
            b.config(bg="#1e293b" if is_act else "#11141c", fg=TEXT_WHITE if is_act else TEXT_MUTED)

        if mode == "Manual":
            self.slider_frame.pack(fill=tk.X, pady=(4, 0))
        else:
            self.slider_frame.pack_forget()

        def apply_fan():
            if mode == "Auto":
                self.backend.set_fan_speed(0)
            elif mode == "Silent":
                self.backend.set_fan_speed(35)
            elif mode == "Turbo":
                self.backend.set_fan_speed(85)
            elif mode == "Max":
                self.backend.set_fan_speed(100)

        threading.Thread(target=apply_fan, daemon=True).start()

    def set_charge(self, limit):
        self.charge_limit = limit
        for b, l in [(self.btn_c60, 60), (self.btn_c80, 80), (self.btn_c100, 100)]:
            is_act = l == limit
            b.config(bg="#1e293b" if is_act else "#11141c", fg=TEXT_WHITE if is_act else TEXT_MUTED)

    def _on_slider_change(self, val):
        duty = int(float(val))
        self.slider_val_lbl.config(text=f"{duty}%")
        threading.Thread(target=lambda: self.backend.set_fan_speed(duty), daemon=True).start()

    def _update_loop(self):
        while self.running:
            try:
                bat = self.backend.get_battery_telemetry()
                c_temp = self.backend.get_cpu_temp()
                g_temp = self.backend.get_gpu_temp()
                c_fan, g_fan, _ = self.backend.get_fan_speeds()

                def update_labels():
                    # AC & Wattage
                    self.ac_pill.config(
                        text="Plugged In" if bat["is_ac"] else "On Battery",
                        fg=ACCENT_GREEN if bat["is_ac"] else ACCENT_AMBER,
                        bg="#064e3b" if bat["is_ac"] else "#3b1806"
                    )
                    self.watt_pill.config(text=f"{bat['power_w']:.1f} W")

                    # Battery
                    self.badge_charge.val_lbl.config(text=f"{bat['capacity_pct']}%")
                    self.badge_health.val_lbl.config(text=f"{bat['health_pct']:.1f}%")
                    self.badge_power.val_lbl.config(text=f"{bat['power_w']:.1f} W")
                    self.badge_rem.val_lbl.config(text=bat["remaining_time"])
                    self.badge_full.val_lbl.config(text=bat["full_runtime"])

                    # Thermals
                    self.badge_cpu_temp.val_lbl.config(text=f"{int(c_temp)}°C")
                    self.badge_gpu_temp.val_lbl.config(text=f"{int(g_temp)}°C")
                    self.badge_cpu_fan.val_lbl.config(text=f"{c_fan} RPM")
                    self.badge_gpu_fan.val_lbl.config(text=f"{g_fan} RPM")

                self.root.after(0, update_labels)
            except Exception:
                pass
            time.sleep(1.5)
