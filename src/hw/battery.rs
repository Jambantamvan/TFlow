use std::fs;
use std::process::Command;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatteryTelemetry {
    pub voltage_v: f64,
    pub current_a: f64,
    pub power_w: f64,
    pub capacity_pct: u32,
    pub health_pct: f64,
    pub charge_now_wh: f64,
    pub charge_full_wh: f64,
    pub charge_design_wh: f64,
    pub ac_connected: bool,
    pub status: String,
    pub remaining_mins: i32,
    pub full_charge_runtime_mins: i32,
    pub charge_limit: u32,
}

impl Default for BatteryTelemetry {
    fn default() -> Self {
        Self {
            voltage_v: 12.0,
            current_a: 0.0,
            power_w: 0.0,
            capacity_pct: 100,
            health_pct: 100.0,
            charge_now_wh: 48.0,
            charge_full_wh: 48.0,
            charge_design_wh: 48.0,
            ac_connected: true,
            status: "Full".to_string(),
            remaining_mins: -1,
            full_charge_runtime_mins: -1,
            charge_limit: 100,
        }
    }
}

pub fn read_battery_telemetry() -> BatteryTelemetry {
    #[cfg(target_os = "linux")]
    {
        read_linux_battery()
    }
    #[cfg(target_os = "windows")]
    {
        read_windows_battery()
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        BatteryTelemetry::default()
    }
}

#[cfg(target_os = "linux")]
fn read_linux_battery() -> BatteryTelemetry {
    let bat_path = "/sys/class/power_supply/BAT1";
    let acad_path = "/sys/class/power_supply/ACAD/online";

    let ac_connected = fs::read_to_string(acad_path)
        .map(|s| s.trim() == "1")
        .unwrap_or(true);

    let read_val = |sub: &str| -> Option<f64> {
        fs::read_to_string(format!("{}/{}", bat_path, sub))
            .ok()
            .and_then(|s| s.trim().parse::<f64>().ok())
    };

    let read_str = |sub: &str| -> String {
        fs::read_to_string(format!("{}/{}", bat_path, sub))
            .map(|s| s.trim().to_string())
            .unwrap_or_else(|_| "Unknown".to_string())
    };

    let status = read_str("status");
    let voltage_u_v = read_val("voltage_now").unwrap_or(12_000_000.0);
    let voltage_v = voltage_u_v / 1_000_000.0;

    let current_u_a = read_val("current_now").unwrap_or(0.0);
    let current_a = current_u_a / 1_000_000.0;

    // Power calculation
    let power_w = if let Some(p_u_w) = read_val("power_now") {
        p_u_w / 1_000_000.0
    } else {
        (voltage_v * current_a).abs()
    };

    let capacity_pct = read_val("capacity").unwrap_or(100.0) as u32;

    // Energy / Charge
    let charge_design_u_ah = read_val("charge_full_design")
        .or_else(|| read_val("energy_full_design"))
        .unwrap_or(4_110_000.0);
    let charge_full_u_ah = read_val("charge_full")
        .or_else(|| read_val("energy_full"))
        .unwrap_or(charge_design_u_ah);
    let charge_now_u_ah = read_val("charge_now")
        .or_else(|| read_val("energy_now"))
        .unwrap_or(charge_full_u_ah);

    let v_nom = voltage_v.max(11.0);
    let charge_design_wh = (charge_design_u_ah / 1_000_000.0) * v_nom;
    let charge_full_wh = (charge_full_u_ah / 1_000_000.0) * v_nom;
    let charge_now_wh = (charge_now_u_ah / 1_000_000.0) * v_nom;

    let health_pct = if charge_design_u_ah > 0.0 {
        ((charge_full_u_ah / charge_design_u_ah) * 100.0).clamp(0.0, 100.0)
    } else {
        100.0
    };

    // Calculate remaining runtime (in minutes)
    let remaining_mins = if !ac_connected && current_a > 0.05 {
        let hrs = charge_now_u_ah / current_u_a;
        (hrs * 60.0).round() as i32
    } else if ac_connected && status == "Charging" && current_a > 0.05 {
        let remaining_u_ah = (charge_full_u_ah - charge_now_u_ah).max(0.0);
        let hrs = remaining_u_ah / current_u_a;
        (hrs * 60.0).round() as i32
    } else {
        -1
    };

    // Calculate full charge runtime at the current discharge rate
    let full_charge_runtime_mins = if current_a > 0.05 {
        let hrs = charge_full_u_ah / current_u_a;
        (hrs * 60.0).round() as i32
    } else {
        // Estimated based on typical 13W baseline load if currently idle on AC
        let est_watts = 13.5;
        let hrs = charge_full_wh / est_watts;
        (hrs * 60.0).round() as i32
    };

    let charge_limit = read_val("charge_control_end_threshold").unwrap_or(100.0) as u32;

    BatteryTelemetry {
        voltage_v,
        current_a,
        power_w,
        capacity_pct,
        health_pct,
        charge_now_wh,
        charge_full_wh,
        charge_design_wh,
        ac_connected,
        status,
        remaining_mins,
        full_charge_runtime_mins,
        charge_limit,
    }
}

#[cfg(target_os = "windows")]
fn read_windows_battery() -> BatteryTelemetry {
    super::windows::read_windows_battery()
}

pub fn set_charge_limit(limit: u32) -> Result<(), String> {
    let limit = match limit {
        60 | 80 | 100 => limit,
        l if l <= 65 => 60,
        l if l <= 85 => 80,
        _ => 100,
    };

    #[cfg(target_os = "linux")]
    {
        let path = "/sys/class/power_supply/BAT1/charge_control_end_threshold";
        if let Ok(_) = fs::write(path, limit.to_string()) {
            return Ok(());
        }

        // Try using pkexec / tee if direct write lacks permission
        let cmd = format!("echo {} | tee {}", limit, path);
        let status = Command::new("pkexec")
            .arg("sh")
            .arg("-c")
            .arg(&cmd)
            .status();

        match status {
            Ok(s) if s.success() => Ok(()),
            _ => Err("Failed to write charge_control_end_threshold via pkexec".to_string()),
        }
    }

    #[cfg(target_os = "windows")]
    {
        super::windows::set_windows_charge_limit(limit)
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        Ok(())
    }
}

