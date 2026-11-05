"""
TFlow - Modern Hardware & Fan Performance Manager
Written in pure Python Tkinter with a sleek dark aesthetic.
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from backend import HardwareBackend

# Color Theme (G-Helper / Dark TUF Style)
BG_MAIN = "#121215"
BG_CARD = "#1a1a22"
BG_CARD_HOVER = "#22222c"
BORDER_COLOR = "#2a2a36"
ACCENT_RED = "#e63946"
ACCENT_BLUE = "#3b82f6"
TEXT_WHITE = "#f3f4f6"
TEXT_MUTED = "#9ca3af"
GREEN_BADGE = "#10b981"
AMBER_BADGE = "#f59e0b"
RED_BADGE = "#ef4444"

class TFlowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TFlow")
        self.root.geometry("440x680")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)

        self.backend = HardwareBackend()
        self.running = True

        self._setup_styles()
        self._build_ui()

        # Start live background polling
        self.poll_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.poll_thread.start()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Configure horizontal scale slider
        self.style.configure(
            "TFlow.Horizontal.TScale",
            troughcolor="#22222c",
            background=ACCENT_RED,
            sliderlength=22,
            sliderthickness=14
        )

    def _build_ui(self):
        main_container = tk.Frame(self.root, bg=BG_MAIN, padx=16, pady=16)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ---------------- HEADER ----------------
        header_frame = tk.Frame(main_container, bg=BG_MAIN)
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_lbl = tk.Label(
            header_frame,
            text="⚡ TFLOW",
            font=("Segoe UI", 14, "bold"),
            fg=TEXT_WHITE,
            bg=BG_MAIN
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            header_frame,
            text=f"Thermal & Performance Manager • {self.backend.os_type} Edition",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_MAIN
        )
        sub_lbl.pack(anchor="w")

        # Badges (Live CPU & GPU Temp)
        badge_frame = tk.Frame(header_frame, bg=BG_MAIN)
        badge_frame.pack(fill=tk.X, pady=(8, 0))

        self.cpu_badge = tk.Label(
            badge_frame,
            text="CPU: -- °C",
            font=("Segoe UI", 10, "bold"),
            bg="#2a2a36",
            fg=GREEN_BADGE,
            padx=10,
            pady=4
        )
        self.cpu_badge.pack(side=tk.LEFT, padx=(0, 8))

        self.gpu_badge = tk.Label(
            badge_frame,
            text="GPU: -- °C",
            font=("Segoe UI", 10, "bold"),
            bg="#2a2a36",
            fg=GREEN_BADGE,
            padx=10,
            pady=4
        )
        self.gpu_badge.pack(side=tk.LEFT)

        # ---------------- CARD 1: PERFORMANCE PROFILES ----------------
        card1 = self._create_card(main_container, "⚡ PROFIL PERFORMA")

        prof_btn_frame = tk.Frame(card1, bg=BG_CARD)
        prof_btn_frame.pack(fill=tk.X, pady=6)

        self.btn_silent = self._create_flat_button(prof_btn_frame, "🤫 Silent", lambda: self._on_profile_click("Silent"))
        self.btn_silent.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_balanced = self._create_flat_button(prof_btn_frame, "⚖️ Balanced", lambda: self._on_profile_click("Balanced"))
        self.btn_balanced.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_turbo = self._create_flat_button(prof_btn_frame, "🚀 Turbo", lambda: self._on_profile_click("Turbo"))
        self.btn_turbo.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.prof_desc_lbl = tk.Label(
            card1,
            text="⚖️ Balanced: CPU 35W (Cap 85%), GPU 1450MHz. Optimal Game (65-72°C).",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            justify=tk.LEFT
        )
        self.prof_desc_lbl.pack(anchor="w", pady=(2, 0))

        # ---------------- CARD 2: MODE DINGIN (CPU BOOST TUNING) ----------------
        card2 = self._create_card(main_container, "❄️ TUNING SUHU DINGIN (CPU BOOST)")

        c2_top = tk.Frame(card2, bg=BG_CARD)
        c2_top.pack(fill=tk.X, pady=(2, 4))

        c2_desc = tk.Label(
            c2_top,
            text="Mode Dingin menonaktifkan Turbo Boost agresif.\nSuhu turun 15°C - 20°C (65-72°C saat main game)\ndan bebas lag stutter throttling.",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_CARD,
            justify=tk.LEFT
        )
        c2_desc.pack(side=tk.LEFT, anchor="w")

        self.cold_btn = tk.Button(
            card2,
            text="❄️ MODE DINGIN: AKTIF",
            font=("Segoe UI", 10, "bold"),
            bg="#064e3b",
            fg="#6ee7b7",
            activebackground="#047857",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=8,
            command=self._on_toggle_cold_mode
        )
        self.cold_btn.pack(fill=tk.X, pady=(6, 2))

        # ---------------- CARD 3: KONTROL KIPAS & RPM ----------------
        card3 = self._create_card(main_container, "🌪️ KONTROL KIPAS & RPM REAL-TIME")

        # Live Tachometer readout
        tach_frame = tk.Frame(card3, bg=BG_CARD)
        tach_frame.pack(fill=tk.X, pady=(0, 8))

        self.cpu_rpm_lbl = tk.Label(
            tach_frame,
            text="CPU Fan : ---- RPM",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_WHITE,
            bg="#22222c",
            padx=10,
            pady=6
        )
        self.cpu_rpm_lbl.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        self.gpu_rpm_lbl = tk.Label(
            tach_frame,
            text="GPU Fan : ---- RPM",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_WHITE,
            bg="#22222c",
            padx=10,
            pady=6
        )
        self.gpu_rpm_lbl.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))

        # Slider header
        slider_info = tk.Frame(card3, bg=BG_CARD)
        slider_info.pack(fill=tk.X, pady=(4, 0))

        tk.Label(
            slider_info,
            text="Kecepatan Kipas Manual:",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_CARD
        ).pack(side=tk.LEFT)

        self.slider_val_lbl = tk.Label(
            slider_info,
            text="100%",
            font=("Segoe UI", 10, "bold"),
            fg=ACCENT_RED,
            bg=BG_CARD
        )
        self.slider_val_lbl.pack(side=tk.RIGHT)

        # Scale slider
        self.fan_slider = ttk.Scale(
            card3,
            from_=20,
            to=100,
            orient=tk.HORIZONTAL,
            style="TFlow.Horizontal.TScale",
            command=self._on_slider_move
        )
        self.fan_slider.set(100)
        self.fan_slider.pack(fill=tk.X, pady=(4, 8))
        self.fan_slider.bind("<ButtonRelease-1>", lambda e: self._apply_slider_speed())

        # Quick preset buttons
        preset_frame = tk.Frame(card3, bg=BG_CARD)
        preset_frame.pack(fill=tk.X, pady=(2, 4))

        self.btn_auto = self._create_flat_button(preset_frame, "Auto (BIOS)", lambda: self._on_preset_click(0))
        self.btn_auto.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_50 = self._create_flat_button(preset_frame, "50%", lambda: self._on_preset_click(50))
        self.btn_50.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self.btn_75 = self._create_flat_button(preset_frame, "75%", lambda: self._on_preset_click(75))
        self.btn_75.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # Big Max Force Button
        self.max_btn = tk.Button(
            card3,
            text="🔥 PAKSA KIPAS 100% (MAKSIMAL)",
            font=("Segoe UI", 10, "bold"),
            bg="#991b1b",
            fg="#fecaca",
            activebackground="#b91c1c",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            padx=12,
            pady=8,
            command=lambda: self._on_preset_click(100)
        )
        self.max_btn.pack(fill=tk.X, pady=(8, 2))

        # Status text footer
        self.status_lbl = tk.Label(
            main_container,
            text="Status: Hardware connected & ready.",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_MAIN
        )
        self.status_lbl.pack(side=tk.BOTTOM, anchor="w", pady=(8, 0))

    def _create_card(self, parent, title):
        card = tk.Frame(parent, bg=BG_CARD, padx=12, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 10))

        title_lbl = tk.Label(
            card,
            text=title,
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD
        )
        title_lbl.pack(anchor="w", pady=(0, 4))
        return card

    def _create_flat_button(self, parent, text, command):
        btn = tk.Button(
            parent,
            text=text,
            font=("Segoe UI", 9, "bold"),
            bg="#262633",
            fg=TEXT_WHITE,
            activebackground="#323244",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            cursor="hand2",
            padx=8,
            pady=6,
            command=command
        )
        return btn

    # ---------------- EVENT HANDLERS ----------------

    def _on_profile_click(self, profile):
        self.status_lbl.config(text=f"Menerapkan profil {profile}...")
        threading.Thread(target=self._apply_profile_bg, args=(profile,), daemon=True).start()

    def _apply_profile_bg(self, profile):
        self.backend.set_power_profile(profile)
        self._highlight_profile(profile)
        self.root.after(0, lambda: self.status_lbl.config(text=f"Profil aktif: {profile}"))

    def _highlight_profile(self, profile):
        buttons = {"Silent": self.btn_silent, "Balanced": self.btn_balanced, "Turbo": self.btn_turbo}
        desc_map = {
            "Silent": "🤫 Silent: CPU 25W (Tanpa Boost), GPU Max 1200MHz. Hening & Dingin (45-55°C).",
            "Balanced": "⚖️ Balanced: CPU 35W (Cap 85%), GPU Max 1450MHz. Optimal Game (65-72°C).",
            "Turbo": "🚀 Turbo: CPU 50W (Full 4.2GHz), GPU Full Boost (1785MHz). Performa Maksimal."
        }
        for name, btn in buttons.items():
            if name == profile:
                btn.config(bg=ACCENT_RED, fg="#ffffff")
            else:
                btn.config(bg="#262633", fg=TEXT_WHITE)
        if hasattr(self, "prof_desc_lbl") and profile in desc_map:
            self.prof_desc_lbl.config(text=desc_map[profile])

    def _on_toggle_cold_mode(self):
        cur = self.backend.get_cold_mode()
        new_val = not cur
        self.backend.set_cold_mode(new_val)
        self._update_cold_mode_ui(new_val)

    def _update_cold_mode_ui(self, is_cold):
        if is_cold:
            self.cold_btn.config(
                text="❄️ MODE DINGIN: AKTIF (Maks. ~70°C)",
                bg="#064e3b",
                fg="#6ee7b7"
            )
        else:
            self.cold_btn.config(
                text="🔥 MODE DINGIN: MATI (Full Turbo Boost)",
                bg="#3f3f46",
                fg="#d4d4d8"
            )

    def _on_slider_move(self, val):
        pct = int(float(val))
        self.slider_val_lbl.config(text=f"{pct}%")

    def _apply_slider_speed(self):
        pct = int(self.fan_slider.get())
        self.status_lbl.config(text=f"Mengatur kipas ke {pct}%...")
        threading.Thread(target=self._apply_fan_speed_bg, args=(pct,), daemon=True).start()

    def _on_preset_click(self, pct):
        self.fan_slider.set(pct if pct > 0 else 50)
        self.slider_val_lbl.config(text=f"{pct}%" if pct > 0 else "Auto")
        self.status_lbl.config(text=f"Menerapkan kecepatan {pct}%..." if pct > 0 else "Mengembalikan kendali ke Auto...")
        threading.Thread(target=self._apply_fan_speed_bg, args=(pct,), daemon=True).start()

    def _apply_fan_speed_bg(self, pct):
        self.backend.set_fan_speed(pct)
        time.sleep(1)
        self.root.after(0, lambda: self.status_lbl.config(text=f"Kecepatan kipas diatur: {pct}%" if pct > 0 else "Kipas dikembalikan ke Auto (EC)."))

    # ---------------- POLLING LOOP ----------------

    def _update_loop(self):
        while self.running:
            try:
                c_temp = self.backend.get_cpu_temp()
                g_temp = self.backend.get_gpu_temp()
                cpu_rpm, gpu_rpm, mode = self.backend.get_fan_speeds()
                is_cold = self.backend.get_cold_mode()
                prof = self.backend.get_power_profile()

                self.root.after(0, self._render_live_data, c_temp, g_temp, cpu_rpm, gpu_rpm, is_cold, prof)
            except Exception:
                pass
            time.sleep(1.5)

    def _render_live_data(self, c_temp, g_temp, cpu_rpm, gpu_rpm, is_cold, prof):
        # Update CPU badge
        c_color = GREEN_BADGE if c_temp < 68 else (AMBER_BADGE if c_temp < 80 else RED_BADGE)
        self.cpu_badge.config(text=f"CPU: {c_temp:.0f}°C", fg=c_color)

        # Update GPU badge
        if g_temp is not None:
            g_color = GREEN_BADGE if g_temp < 68 else (AMBER_BADGE if g_temp < 80 else RED_BADGE)
            self.gpu_badge.config(text=f"GPU: {g_temp:.0f}°C", fg=g_color)
        else:
            self.gpu_badge.config(text="GPU: Standby", fg=TEXT_MUTED)

        # Update Tachometers
        self.cpu_rpm_lbl.config(text=f"CPU Fan : {cpu_rpm} RPM")
        self.gpu_rpm_lbl.config(text=f"GPU Fan : {gpu_rpm} RPM")

        # Update Cold mode & Profile highlights
        self._update_cold_mode_ui(is_cold)
        self._highlight_profile(prof)

def main():
    root = tk.Tk()
    app = TFlowApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

