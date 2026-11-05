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
            manual_fan_duty: 60,
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
fn get_ec_tool_path() -> &'static str {
    if std::path::Path::new("/usr/local/bin/asus-fan-control-ec").exists() {
        "/usr/local/bin/asus-fan-control-ec"
    } else if std::path::Path::new("/usr/bin/asus-fan-control-ec").exists() {
        "/usr/bin/asus-fan-control-ec"
    } else {
        "asus-fan-control-ec"
    }
}

#[cfg(target_os = "linux")]
fn extract_rpm_from_line(line: &str) -> Option<i32> {
    let parts: Vec<&str> = line.split_whitespace().collect();
    for (i, part) in parts.iter().enumerate() {
        if part.eq_ignore_ascii_case("rpm") && i > 0 {
            if let Ok(val) = parts[i - 1].parse::<i32>() {
                if val >= 0 && val < 20000 {
                    return Some(val);
                }
            }
        }
    }
    None
}

#[cfg(target_os = "linux")]
fn read_linux_thermals() -> ThermalTelemetry {
    // 1. CPU Temperature (via coretemp or thermal_zone)
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

    // 2. GPU Temperature (via nvidia-smi)
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

    // 3. Fan RPMs & EC Status via asus-fan-control-ec
    let mut cpu_fan_rpm = 0;
    let mut gpu_fan_rpm = 0;
    let mut ec_mode_is_manual = false;

    let ec_tool = get_ec_tool_path();
    if let Ok(output) = Command::new(ec_tool).arg("fan-speed").output() {
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                let lower = line.to_lowercase();
                if lower.contains("fan control:") {
                    if lower.contains("manual") {
                        ec_mode_is_manual = true;
                    }
                } else if lower.contains("fan 0:") {
                    if let Some(rpm) = extract_rpm_from_line(line) {
                        cpu_fan_rpm = rpm;
                    }
                } else if lower.contains("fan 1:") {
                    if let Some(rpm) = extract_rpm_from_line(line) {
                        gpu_fan_rpm = rpm;
                    }
                }
            }
        }
    }

    // Fallback: If asus-fan-control-ec returned 0, try sysfs hwmon
    if cpu_fan_rpm == 0 {
        if let Ok(entries) = fs::read_dir("/sys/class/hwmon") {
            for entry in entries.flatten() {
                let path = entry.path();
                let name = fs::read_to_string(path.join("name")).unwrap_or_default();
                if name.trim() == "asus" {
                    if let Ok(s) = fs::read_to_string(path.join("fan1_input")) {
                        if let Ok(rpm) = s.trim().parse::<i32>() {
                            if rpm > 0 {
                                cpu_fan_rpm = rpm;
                            }
                        }
                    }
                    if let Ok(s) = fs::read_to_string(path.join("fan2_input")) {
                        if let Ok(rpm) = s.trim().parse::<i32>() {
                            if rpm > 0 {
                                gpu_fan_rpm = rpm;
                            }
                        }
                    }
                }
            }
        }
    }

    // If only one fan was reported but fans are linked, sync GPU fan
    if gpu_fan_rpm == 0 && cpu_fan_rpm > 0 {
        gpu_fan_rpm = cpu_fan_rpm;
    }

    // Read current thermal policy (0=Standard, 1=Silent, 2=Turbo)
    let policy = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/throttle_thermal_policy")
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "0".to_string());

    let fan_mode = if ec_mode_is_manual {
        let duty_str = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1")
            .unwrap_or_default();
        if duty_str.trim() == "255" {
            "Max".to_string()
        } else {
            "Manual".to_string()
        }
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
        .unwrap_or(153);

    let manual_fan_duty = ((manual_duty_raw as f64 / 255.0) * 100.0).round() as i32;

    ThermalTelemetry {
        cpu_temp_c,
        gpu_temp_c,
        cpu_fan_rpm,
        gpu_fan_rpm,
        fan_mode,
        manual_fan_duty: manual_fan_duty.clamp(20, 100),
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
        let boost_path = "/sys/devices/platform/asus-nb-wmi/fan_boost_mode";
        let pwm_enable_path = "/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1_enable";
        let pwm_path = "/sys/devices/platform/asus-nb-wmi/hwmon/hwmon8/pwm1";
        let ec_tool = get_ec_tool_path();

        match profile.to_lowercase().as_str() {
            "auto" | "default" => {
                let _ = fs::write(pwm_enable_path, "2");
                let _ = fs::write(policy_path, "0");
                let _ = fs::write(boost_path, "0");
                let _ = Command::new("asusctl").args(["profile", "set", "Balanced"]).output();
                let _ = Command::new(ec_tool).args(["set", "-1"]).output();
            }
            "silent" | "eco" => {
                let _ = fs::write(pwm_enable_path, "2");
                let _ = fs::write(policy_path, "1");
                let _ = fs::write(boost_path, "2");
                let _ = Command::new("asusctl").args(["profile", "set", "Quiet"]).output();
                let _ = Command::new(ec_tool).args(["set", "-1"]).output();
            }
            "turbo" | "performance" => {
                let _ = fs::write(pwm_enable_path, "2");
                let _ = fs::write(policy_path, "2");
                let _ = fs::write(boost_path, "1"); // Overboost
                let _ = Command::new("asusctl").args(["profile", "set", "Performance"]).output();
                let _ = Command::new(ec_tool).args(["set", "-1"]).output();
            }
            "max" | "100" | "100% max" => {
                // 1. Activate ASUS Overboost & Performance profile
                let _ = fs::write(boost_path, "1");
                let _ = fs::write(policy_path, "2");
                let _ = Command::new("asusctl").args(["profile", "set", "Performance"]).output();
                // 2. Sysfs PWM to 255
                let _ = fs::write(pwm_enable_path, "1");
                let _ = fs::write(pwm_path, "255");
                // 3. Write direct 100% (255) to each fan channel
                let _ = Command::new(ec_tool).args(["setp", "100", "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", "100", "--fan", "1", "--no-verify"]).output();
            }
            "manual" => {
                let duty_pct = manual_duty_pct.unwrap_or(60).clamp(20, 100);
                let raw_pwm = ((duty_pct as f64 / 100.0) * 255.0).round() as u8;
                let _ = fs::write(pwm_enable_path, "1");
                let _ = fs::write(pwm_path, raw_pwm.to_string());
                if duty_pct >= 85 {
                    let _ = fs::write(boost_path, "1");
                    let _ = fs::write(policy_path, "2");
                }
                let _ = Command::new(ec_tool).args(["setp", &duty_pct.to_string(), "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", &duty_pct.to_string(), "--fan", "1", "--no-verify"]).output();
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
