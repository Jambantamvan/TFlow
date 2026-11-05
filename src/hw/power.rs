use std::fs;
use std::process::Command;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PowerMode {
    UltraSave,
    Balance,
    Performance,
}

impl PowerMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            PowerMode::UltraSave => "UltraSave",
            PowerMode::Balance => "Balance",
            PowerMode::Performance => "Performance",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().replace(['_', '-', ' '], "").as_str() {
            "ultrasave" | "ultra" | "saver" | "powersaver" | "eco" => Some(PowerMode::UltraSave),
            "balance" | "balanced" | "normal" | "standard" => Some(PowerMode::Balance),
            "performance" | "perf" | "turbo" | "overclock" => Some(PowerMode::Performance),
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
    // ASUS TUF FX506 policy mapping:
    // 0 = Balanced, 1 = Turbo/Overboost, 2 = Silent/Quiet
    let (pl1_uw, pl2_uw, no_turbo, max_perf, epp, thermal_policy, boost_mode, asus_profile) = match mode {
        PowerMode::UltraSave => (
            10_000_000, // 10W deep battery clamp
            12_000_000, // 12W burst cap
            "1",        // Turbo disabled to prevent battery drain spikes
            "50",       // 50% max clock speed (~800MHz - 1.2GHz)
            "power",    // Energy performance preference: maximum power savings
            "2",        // ASUS TUF: 2 is Silent policy
            "2",        // ASUS TUF: 2 is Silent fan boost
            "Quiet",
        ),
        PowerMode::Balance => (
            28_000_000, // 28W balanced sustained limit
            45_000_000, // 45W dynamic burst limit
            "0",        // Turbo enabled
            "100",      // 100% clock speed
            "balance_performance",
            "0",        // ASUS TUF: 0 is Balanced policy
            "0",        // ASUS TUF: 0 is Normal fan boost
            "Balanced",
        ),
        PowerMode::Performance => (
            45_000_000, // 45W max sustained TDP for Intel Core i5-10300H
            70_000_000, // 70W high peak burst limit
            "0",        // Full Turbo Boost up to 4.50 GHz
            "100",      // 100% full scale
            "performance", // Immediate ramp, lowest latency
            "1",        // ASUS TUF: 1 is Turbo / Overboost policy
            "1",        // ASUS TUF: 1 is Overboost fan boost
            "Performance",
        ),
    };

    // 1. Intel RAPL Power Limits
    let rapl_pl1 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw";
    let rapl_pl2 = "/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw";
    let _ = fs::write(rapl_pl1, pl1_uw.to_string());
    let _ = fs::write(rapl_pl2, pl2_uw.to_string());

    // 2. Intel P-State Turbo & Max Performance
    let pstate_turbo = "/sys/devices/system/cpu/intel_pstate/no_turbo";
    let pstate_max_perf = "/sys/devices/system/cpu/intel_pstate/max_perf_pct";
    let _ = fs::write(pstate_turbo, no_turbo);
    let _ = fs::write(pstate_max_perf, max_perf);

    // 3. Energy Performance Preference (EPP) across all CPU cores
    if let Ok(entries) = fs::read_dir("/sys/devices/system/cpu") {
        for entry in entries.flatten() {
            let path = entry.path();
            let epp_path = path.join("cpufreq/energy_performance_preference");
            if epp_path.exists() {
                let _ = fs::write(epp_path, epp);
            }
        }
    }

    // 4. ASUS ACPI Thermal Policy & Fan Boost Mode (0=Standard, 1=Turbo, 2=Silent on TUF)
    let asus_policy_path = "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy";
    let asus_boost_path = "/sys/devices/platform/asus-nb-wmi/fan_boost_mode";
    let _ = fs::write(asus_policy_path, thermal_policy);
    let _ = fs::write(asus_boost_path, boost_mode);
    let _ = Command::new("asusctl").args(["profile", "set", asus_profile]).output();

    // 5. NVIDIA GPU Power Optimization
    use std::process::Stdio;
    match mode {
        PowerMode::UltraSave => {
            let _ = Command::new("nvidia-smi")
                .args(["-lgc", "300,300"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
        PowerMode::Balance => {
            let _ = Command::new("nvidia-smi")
                .args(["-rgc"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
        PowerMode::Performance => {
            let _ = Command::new("nvidia-smi")
                .args(["-rgc"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
            let _ = Command::new("nvidia-smi")
                .args(["-pm", "1"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status();
        }
    }

    Ok(())
}

#[cfg(target_os = "windows")]
fn apply_windows_power_mode(mode: PowerMode) -> Result<(), String> {
    super::windows::apply_windows_power_mode(mode)
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

        let pl1 = fs::read_to_string("/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw")
            .ok()
            .and_then(|s| s.trim().parse::<u64>().ok())
            .unwrap_or(28_000_000);

        let policy = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy")
            .map(|s| s.trim().to_string())
            .unwrap_or_default();

        if (turbo_disabled && max_perf <= 60) || pl1 <= 15_000_000 {
            PowerMode::UltraSave
        } else if policy == "1" || pl1 >= 40_000_000 {
            // On TUF FX506: 1 is Turbo/Overboost
            PowerMode::Performance
        } else {
            PowerMode::Balance
        }
    }
    #[cfg(target_os = "windows")]
    {
        super::windows::get_windows_power_mode()
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        PowerMode::Balance
    }
}
