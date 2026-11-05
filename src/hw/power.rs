use std::fs;
use std::process::Command;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PowerMode {
    Normal,
    PowerSaver,
    UltraSaver,
}

impl PowerMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            PowerMode::Normal => "Normal (Balanced)",
            PowerMode::PowerSaver => "Power Saver (Eco)",
            PowerMode::UltraSaver => "Ultra Battery Saver",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "normal" | "balanced" | "standard" => Some(PowerMode::Normal),
            "powersaver" | "power_saver" | "eco" | "saver" => Some(PowerMode::PowerSaver),
            "ultrasaver" | "ultra_saver" | "ultra" => Some(PowerMode::UltraSaver),
            _ => None,
        }
    }
}

pub fn apply_power_mode(mode: PowerMode) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        apply_linux_power_mode(mode)
    }
    #[cfg(target_os = "windows")]
    {
        apply_windows_power_mode(mode)
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        Ok(())
    }
}

#[cfg(target_os = "linux")]
fn apply_linux_power_mode(mode: PowerMode) -> Result<(), String> {
    let (pl1_uw, pl2_uw, no_turbo, max_perf, epp) = match mode {
        PowerMode::Normal => (
            25_000_000, // 25W
            35_000_000, // 35W
            "0",        // Turbo enabled
            "100",      // 100% clock speed
            "balance_performance",
        ),
        PowerMode::PowerSaver => (
            15_000_000, // 15W
            20_000_000, // 20W
            "1",        // Turbo disabled (base clock 2.5 GHz)
            "70",       // 70% clock speed
            "power",
        ),
        PowerMode::UltraSaver => (
            10_000_000, // 10W (deep clamp)
            12_000_000, // 12W
            "1",        // Turbo disabled
            "50",       // 50% max clock (~800MHz - 1.2GHz)
            "power",
        ),
    };

    // 1. Intel RAPL Power Limits
    let rapl_pl1 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw";
    let rapl_pl2 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw";
    let _ = fs::write(rapl_pl1, pl1_uw.to_string());
    let _ = fs::write(rapl_pl2, pl2_uw.to_string());

    // 2. Intel P-State
    let pstate_turbo = "/sys/devices/system/cpu/intel_pstate/no_turbo";
    let pstate_max_perf = "/sys/devices/system/cpu/intel_pstate/max_perf_pct";
    let _ = fs::write(pstate_turbo, no_turbo);
    let _ = fs::write(pstate_max_perf, max_perf);

    // 3. Energy Performance Preference (EPP)
    if let Ok(entries) = fs::read_dir("/sys/devices/system/cpu") {
        for entry in entries.flatten() {
            let path = entry.path();
            let epp_path = path.join("cpufreq/energy_performance_preference");
            if epp_path.exists() {
                let _ = fs::write(epp_path, epp);
            }
        }
    }

    // 4. ASUS ACPI Thermal Policy (0=Standard, 1=Silent, 2=Overboost)
    let asus_policy = match mode {
        PowerMode::Normal => "0",
        PowerMode::PowerSaver | PowerMode::UltraSaver => "1", // Silent
    };
    let asus_policy_path = "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy";
    let _ = fs::write(asus_policy_path, asus_policy);

    // 5. NVIDIA GPU Power Optimization
    use std::process::Stdio;
    if mode == PowerMode::UltraSaver {
        // Lower GPU clock to min state (300 MHz)
        let _ = Command::new("nvidia-smi")
            .args(["-lgc", "300,300"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    } else {
        // Reset GPU clocks
        let _ = Command::new("nvidia-smi")
            .args(["-rgc"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }

    Ok(())
}

#[cfg(target_os = "windows")]
fn apply_windows_power_mode(mode: PowerMode) -> Result<(), String> {
    // Windows power scheme setting via powercfg
    let guid = match mode {
        PowerMode::Normal => "381b4222-f694-41f0-9685-ff5bb260df2e", // Balanced
        PowerMode::PowerSaver | PowerMode::UltraSaver => "a1841308-3541-4fab-bc81-f71556f20b4a", // Power Saver
    };
    let _ = Command::new("powercfg")
        .args(["/setactive", guid])
        .status();
    Ok(())
}

pub fn get_current_power_mode() -> PowerMode {
    #[cfg(target_os = "linux")]
    {
        let turbo_disabled = fs::read_to_string("/sys/devices/system/cpu/intel_pstate/no_turbo")
            .map(|s| s.trim() == "1")
            .unwrap_or(false);

        let max_perf = fs::read_to_string("/sys/devices/system/cpu/intel_pstate/max_perf_pct")
            .ok()
            .and_then(|s| s.trim().parse::<u32>().ok())
            .unwrap_or(100);

        if turbo_disabled && max_perf <= 55 {
            PowerMode::UltraSaver
        } else if turbo_disabled {
            PowerMode::PowerSaver
        } else {
            PowerMode::Normal
        }
    }
    #[cfg(not(target_os = "linux"))]
    {
        PowerMode::Normal
    }
}

