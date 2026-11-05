#!/usr/bin/env bash
# TFlow v2.0 - Native Linux Installer
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "      TFlow v2.0 - Native System Installer    "
echo "=============================================="

if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges to install system udev rules and binaries."
    echo "Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

# 1. Install udev rules for passwordless hardware & battery access
echo "[1/4] Installing hardware & battery udev rules..."
cat << 'EOF' > /etc/udev/rules.d/99-tflow.rules
# TFlow hardware permissions: ASUS fan, thermal policy, CPU turbo, RAPL, EPP, and Battery charge threshold
ACTION=="add|change", SUBSYSTEM=="platform", DRIVERS=="asus-nb-wmi", RUN+="/bin/chmod 0666 /sys/devices/platform/asus-nb-wmi/fan_boost_mode /sys/devices/platform/asus-nb-wmi/throttle_thermal_policy"
ACTION=="add|change", SUBSYSTEM=="hwmon", ATTR{name}=="asus", RUN+="/bin/sh -c \"chmod 0666 /sys/devices/platform/asus-nb-wmi/hwmon/hwmon*/pwm1* 2>/dev/null || true\""
ACTION=="add", SUBSYSTEM=="cpu", RUN+="/bin/chmod 0666 /sys/devices/system/cpu/intel_pstate/no_turbo /sys/devices/system/cpu/intel_pstate/max_perf_pct /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"
ACTION=="add", SUBSYSTEM=="powercap", RUN+="/bin/chmod 0666 /sys/class/powercap/intel-rapl:0/constraint_*_power_limit_uw"
ACTION=="add|change", SUBSYSTEM=="power_supply", ATTR{type}=="Battery", RUN+="/bin/chmod 0666 /sys/class/power_supply/BAT1/charge_control_end_threshold"
EOF

udevadm control --reload-rules && udevadm trigger || true

# Apply immediate permissions
chmod 0666 /sys/devices/platform/asus-nb-wmi/fan_boost_mode 2>/dev/null || true
chmod 0666 /sys/devices/platform/asus-nb-wmi/throttle_thermal_policy 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/intel_pstate/max_perf_pct 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference 2>/dev/null || true
chmod 0666 /sys/class/powercap/intel-rapl:0/constraint_*_power_limit_uw 2>/dev/null || true
chmod 0666 /sys/class/power_supply/BAT1/charge_control_end_threshold 2>/dev/null || true

# 2. Build and install TFlow Rust release binary
echo "[2/4] Installing TFlow native executable..."
if [ -f "$DIR/target/release/tflow" ]; then
    cp "$DIR/target/release/tflow" /usr/local/bin/tflow
    chmod 755 /usr/local/bin/tflow
else
    echo "Pre-built binary not found, checking cargo..."
    if command -v cargo >/dev/null 2>&1; then
        (cd "$DIR" && cargo build --release && cp target/release/tflow /usr/local/bin/)
    else
        echo "Cargo not installed. Linking python launcher fallback..."
        ln -sfn "$DIR/run.sh" /usr/local/bin/tflow
    fi
fi
chmod +x /usr/local/bin/tflow

# 3. Check / Install asus-fan-control-ec helper
echo "[3/4] Checking low-level EC helper..."
if ! command -v asus-fan-control-ec >/dev/null 2>&1; then
    TMP_BUILD=$(mktemp -d)
    if git clone --depth 1 https://github.com/Keyitdev/asus-fan-control-ec.git "$TMP_BUILD" 2>/dev/null; then
        (cd "$TMP_BUILD" && make clean && make && cp asus-fan-control-ec /usr/local/bin/ && chmod 4755 /usr/local/bin/asus-fan-control-ec) || true
        rm -rf "$TMP_BUILD"
    fi
else
    chmod 4755 /usr/local/bin/asus-fan-control-ec 2>/dev/null || true
fi

# 4. Create desktop shortcuts
echo "[4/4] Creating application shortcuts..."
SUDO_USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
if [ -n "$SUDO_USER_HOME" ]; then
    mkdir -p "$SUDO_USER_HOME/.local/share/applications"
    cat << EOF > "$SUDO_USER_HOME/.local/share/applications/tflow.desktop"
[Desktop Entry]
Name=TFlow
Comment=Hardware, Power & Battery Telemetry Manager for ASUS Laptops
Exec=/usr/local/bin/tflow
Icon=preferences-system-power-management
Terminal=false
Type=Application
Categories=Settings;System;HardwareSettings;
Keywords=fan;rpm;ghelper;turbo;battery;power;cooling;tflow;
StartupNotify=true
EOF
    chown "$SUDO_USER":"$SUDO_USER" "$SUDO_USER_HOME/.local/share/applications/tflow.desktop"
    if [ -d "$SUDO_USER_HOME/Desktop" ]; then
        cp "$SUDO_USER_HOME/.local/share/applications/tflow.desktop" "$SUDO_USER_HOME/Desktop/"
        chmod +x "$SUDO_USER_HOME/Desktop/tflow.desktop"
        chown "$SUDO_USER":"$SUDO_USER" "$SUDO_USER_HOME/Desktop/tflow.desktop"
    fi
fi

echo "=============================================="
echo " Installation Complete!                       "
echo " Run 'tflow' or 'tflow --status' in terminal. "
echo "=============================================="
