#!/usr/bin/env bash
# TFlow - Native Linux Installer
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================="
echo "          TFlow - System Installer            "
echo "=============================================="

if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges to install system udev rules and binaries."
    echo "Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

# 1. Install udev rules for passwordless hardware access
echo "[1/3] Installing udev rules..."
cat << 'EOF' > /etc/udev/rules.d/99-asus-fan.rules
# Allow user to control ASUS fan, thermal policy, CPU turbo, RAPL, and EPP
ACTION=="add|change", SUBSYSTEM=="platform", DRIVERS=="asus-nb-wmi", RUN+="/bin/chmod 0666 /sys/devices/platform/asus-nb-wmi/fan_boost_mode /sys/devices/platform/asus-nb-wmi/throttle_thermal_policy"
ACTION=="add|change", SUBSYSTEM=="hwmon", ATTR{name}=="asus", RUN+="/bin/sh -c \"chmod 0666 /sys/devices/platform/asus-nb-wmi/hwmon/hwmon*/pwm1* 2>/dev/null || true\""
ACTION=="add", SUBSYSTEM=="cpu", RUN+="/bin/chmod 0666 /sys/devices/system/cpu/intel_pstate/no_turbo /sys/devices/system/cpu/intel_pstate/max_perf_pct /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"
ACTION=="add", SUBSYSTEM=="powercap", RUN+="/bin/chmod 0666 /sys/class/powercap/intel-rapl:0/constraint_*_power_limit_uw"
EOF

udevadm control --reload-rules && udevadm trigger || true

# Apply immediate permissions
chmod 0666 /sys/devices/platform/asus-nb-wmi/fan_boost_mode 2>/dev/null || true
chmod 0666 /sys/devices/platform/asus-nb-wmi/throttle_thermal_policy 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/intel_pstate/no_turbo 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/intel_pstate/max_perf_pct 2>/dev/null || true
chmod 0666 /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference 2>/dev/null || true
chmod 0666 /sys/class/powercap/intel-rapl:0/constraint_*_power_limit_uw 2>/dev/null || true

# 2. Check / Install asus-fan-control-ec
if ! command -v asus-fan-control-ec >/dev/null 2>&1; then
    echo "[2/3] Building asus-fan-control-ec from source..."
    TMP_BUILD=$(mktemp -d)
    git clone --depth 1 https://github.com/Keyitdev/asus-fan-control-ec.git "$TMP_BUILD"
    (cd "$TMP_BUILD" && make clean && make && cp asus-fan-control-ec /usr/local/bin/ && chmod 4755 /usr/local/bin/asus-fan-control-ec)
    rm -rf "$TMP_BUILD"
else
    echo "[2/3] asus-fan-control-ec already installed."
    chmod 4755 /usr/local/bin/asus-fan-control-ec || true
fi

# 3. Create global CLI and desktop shortcuts
echo "[3/3] Creating global shortcuts..."
ln -sfn "$DIR/main.py" /usr/local/bin/tflow
chmod +x /usr/local/bin/tflow

SUDO_USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
if [ -n "$SUDO_USER_HOME" ]; then
    mkdir -p "$SUDO_USER_HOME/.local/share/applications"
    cat << EOF > "$SUDO_USER_HOME/.local/share/applications/tflow.desktop"
[Desktop Entry]
Name=TFlow
Comment=Modern Hardware & Fan Performance Manager for Gaming Laptops
Exec=$DIR/run.sh
Icon=preferences-system-power-management
Terminal=false
Type=Application
Categories=Settings;System;HardwareSettings;
Keywords=fan;rpm;ghelper;turbo;temperature;cooling;tflow;
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
echo " Run 'tflow' or launch from your desktop menu."
echo "=============================================="
