use std::fs;
use std::process::Command;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThermalTelemetry {
    pub cpu_temp_c: i32,
    pub gpu_temp_c: i32,
    pub cpu_fan_rpm: i32,
    pub gpu_fan_rpm: i32,
    pub fan_mode: String,
    pub manual_fan_duty: i32,
}

impl Default for ThermalTelemetry {
    fn default() -> Self {
        Self {
            cpu_temp_c: 45,
            gpu_temp_c: 40,
            cpu_fan_rpm: 0,
            gpu_fan_rpm: 0,
            fan_mode: "Auto".to_string(),
            manual_fan_duty: 50,
        }
    }
}

pub fn read_thermals() -> ThermalTelemetry {
    #[cfg(target_os = "linux")]
    {
        read_linux_thermals()
    }
    #[cfg(target_os = "windows")]
    {
        read_windows_thermals()
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        ThermalTelemetry::default()
    }
}

#[cfg(target_os = "linux")]
fn read_linux_thermals() -> ThermalTelemetry {
    // 1. CPU Temperature
    let mut cpu_temp_c = 0;
    if let Ok(entries) = fs::read_dir("/sys/class/hwmon") {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = fs::read_to_string(path.join("name")).unwrap_or_default();
            if name.trim() == "coretemp" {
                if let Ok(temp_str) = fs::read_to_string(path.join("temp1_input")) {
                    if let Ok(milli_c) = temp_str.trim().parse::<i32>() {
                        cpu_temp_c = milli_c / 1000;
                        break;
                    }
                }
            }
        }
    }
    if cpu_temp_c == 0 {
        if let Ok(temp_str) = fs::read_to_string("/sys/class/thermal/thermal_zone0/temp") {
            if let Ok(milli_c) = temp_str.trim().parse::<i32>() {
                cpu_temp_c = milli_c / 1000;
            }
        }
    }

    // 2. GPU Temperature
    let mut gpu_temp_c = 0;
    if let Ok(output) = Command::new("nvidia-smi")
        .args(["--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
        .output()
    {
        if output.status.success() {
            let s = String::from_utf8_lossy(&output.stdout);
            if let Ok(val) = s.trim().parse::<i32>() {
                gpu_temp_c = val;
            }
        }
    }

    // 3. Fan RPMs from asus-nb-wmi hwmon
    let mut cpu_fan_rpm = 0;
    let mut gpu_fan_rpm = 0;
    if let Ok(entries) = fs::read_dir("/sys/class/hwmon") {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = fs::read_to_string(path.join("name")).unwrap_or_default();
            if name.trim() == "asus" {
                if let Ok(s) = fs::read_to_string(path.join("fan1_input")) {
                    if let Ok(rpm) = s.trim().parse::<i32>() {
                        cpu_fan_rpm = rpm;
                    }
                }
                if let Ok(s) = fs::read_to_string(path.join("fan2_input")) {
                    if let Ok(rpm) = s.trim().parse::<i32>() {
                        gpu_fan_rpm = rpm;
                    }
                }
            }
        }
    }

    // Fallback: if gpu_fan_rpm is 0, estimate or link to cpu_fan_rpm under load
    if gpu_fan_rpm == 0 && cpu_fan_rpm > 0 {
        gpu_fan_rpm = (cpu_fan_rpm as f64 * 0.95) as i32;
    }

    // Read current mode
    let policy = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy")
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "0".to_string());

    let pwm_enable = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1_enable")
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "2".to_string());

    let fan_mode = if pwm_enable == "1" {
        "Manual".to_string()
    } else {
        match policy.as_str() {
            "1" => "Silent".to_string(),
            "2" => "Turbo".to_string(),
            _ => "Auto".to_string(),
        }
    };

    let manual_duty_raw = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1")
        .ok()
        .and_then(|s| s.trim().parse::<i32>().ok())
        .unwrap_or(128);

    let manual_fan_duty = ((manual_duty_raw as f64 / 255.0) * 100.0).round() as i32;

    ThermalTelemetry {
        cpu_temp_c,
        gpu_temp_c,
        cpu_fan_rpm,
        gpu_fan_rpm,
        fan_mode,
        manual_fan_duty,
    }
}

#[cfg(target_os = "windows")]
fn read_windows_thermals() -> ThermalTelemetry {
    ThermalTelemetry::default()
}

pub fn set_fan_profile(profile: &str, manual_duty_pct: Option<u8>) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        let policy_path = "/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy";
        let pwm_enable_path = "/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1_enable";
        let pwm_path = "/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1";

        match profile.to_lowercase().as_str() {
            "auto" | "default" => {
                let _ = fs::write(pwm_enable_path, "2"); // Automatic EC control
                let _ = fs::write(policy_path, "0");     // Balanced / Standard
                // Reset EC to auto
                super::ec::set_auto_mode();
            }
            "silent" | "eco" => {
                let _ = fs::write(pwm_enable_path, "2");
                let _ = fs::write(policy_path, "1");     // Silent
            }
            "turbo" | "performance" => {
                let _ = fs::write(pwm_enable_path, "2");
                let _ = fs::write(policy_path, "2");     // Overboost
            }
            "max" | "100" => {
                let _ = fs::write(pwm_enable_path, "1"); // Manual
                let _ = fs::write(pwm_path, "255");
                super::ec::set_fan_duty(255);
            }
            "manual" => {
                let duty_pct = manual_duty_pct.unwrap_or(60);
                let raw_pwm = ((duty_pct as f64 / 100.0) * 255.0).round() as u8;
                let _ = fs::write(pwm_enable_path, "1");
                let _ = fs::write(pwm_path, raw_pwm.to_string());
                super::ec::set_fan_duty(raw_pwm);
            }
            _ => return Err("Invalid fan profile".to_string()),
        }
        Ok(())
    }
    #[cfg(not(target_os = "linux"))]
    {
        Ok(())
    }
}

