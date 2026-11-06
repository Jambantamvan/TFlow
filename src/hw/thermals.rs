use std::fs;
use std::path::PathBuf;
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
pub fn get_asus_hwmon_dir() -> Option<PathBuf> {
    if let Ok(entries) = fs::read_dir("/sys/devices/platform/asus-nb-wmi/hwmon") {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.file_name().unwrap_or_default().to_string_lossy().starts_with("hwmon") {
                return Some(path);
            }
        }
    }
    None
}

#[cfg(target_os = "linux")]
fn read_acpi_gpu_temp() -> Option<i32> {
    if let Ok(entries) = fs::read_dir("/sys/class/thermal") {
        let mut b0d4_temp = None;
        let mut sen2_temp = None;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.file_name().unwrap_or_default().to_string_lossy().starts_with("thermal_zone") {
                if let Ok(ztype) = fs::read_to_string(path.join("type")) {
                    let ztype_trim = ztype.trim();
                    if ztype_trim == "B0D4" {
                        if let Ok(s) = fs::read_to_string(path.join("temp")) {
                            if let Ok(milli) = s.trim().parse::<i32>() {
                                if milli > 10000 && milli < 120000 {
                                    b0d4_temp = Some(milli / 1000);
                                }
                            }
                        }
                    } else if ztype_trim == "SEN2" {
                        if let Ok(s) = fs::read_to_string(path.join("temp")) {
                            if let Ok(milli) = s.trim().parse::<i32>() {
                                if milli > 10000 && milli < 120000 {
                                    sen2_temp = Some(milli / 1000);
                                }
                            }
                        }
                    }
                }
            }
        }
        b0d4_temp.or(sen2_temp)
    } else {
        None
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

    // 2. GPU Temperature (via nvidia-smi with fallback to ACPI discrete GPU sensors)
    let mut gpu_temp_c = 0;
    if let Ok(output) = Command::new("nvidia-smi")
        .args(["--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
        .output()
    {
        if output.status.success() {
            let s = String::from_utf8_lossy(&output.stdout);
            if let Ok(val) = s.trim().parse::<i32>() {
                if val > 0 && val < 120 {
                    gpu_temp_c = val;
                }
            }
        }
    }

    // Fallback 1: Query dynamic ACPI discrete GPU sensors (B0D4 or SEN2)
    if gpu_temp_c == 0 {
        if let Some(temp) = read_acpi_gpu_temp() {
            gpu_temp_c = temp;
        }
    }

    // Fallback 2: Proportional estimation based on CPU package temp
    if gpu_temp_c == 0 && cpu_temp_c > 0 {
        gpu_temp_c = (cpu_temp_c - 4).max(35);
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

    // Fallback: If asus-fan-control-ec returned 0, try dynamic sysfs hwmon
    if cpu_fan_rpm == 0 {
        if let Some(hwmon) = get_asus_hwmon_dir() {
            if let Ok(s) = fs::read_to_string(hwmon.join("fan1_input")) {
                if let Ok(rpm) = s.trim().parse::<i32>() {
                    if rpm > 0 { cpu_fan_rpm = rpm; }
                }
            }
            if let Ok(s) = fs::read_to_string(hwmon.join("fan2_input")) {
                if let Ok(rpm) = s.trim().parse::<i32>() {
                    if rpm > 0 { gpu_fan_rpm = rpm; }
                }
            }
        }
    }

    if gpu_fan_rpm == 0 && cpu_fan_rpm > 0 {
        gpu_fan_rpm = cpu_fan_rpm;
    }

    // Read current ASUS fan boost mode:
    // TUF FX506: 0 = Normal, 1 = Overboost, 2 = Silent
    let boost = fs::read_to_string("/sys/devices/platform/asus-nb-wmi/fan_boost_mode")
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "0".to_string());

    let pwm_path = get_asus_hwmon_dir().map(|h| h.join("pwm1"));
    let duty_str = pwm_path
        .and_then(|p| fs::read_to_string(p).ok())
        .unwrap_or_default();
    let duty_num = duty_str.trim().parse::<u8>().unwrap_or(0);

    let pwm_enable_str = get_asus_hwmon_dir()
        .and_then(|h| fs::read_to_string(h.join("pwm1_enable")).ok())
        .unwrap_or_default();
    let pwm_enable_is_manual = pwm_enable_str.trim() == "1";

    let fan_mode = if ec_mode_is_manual || pwm_enable_is_manual {
        if duty_num >= 240 {
            "Max".to_string()
        } else if duty_num <= 75 && boost == "2" {
            "Silent".to_string()
        } else if duty_num >= 190 && duty_num <= 220 && boost == "1" {
            "Turbo".to_string()
        } else {
            "Manual".to_string()
        }
    } else {
        match boost.as_str() {
            "2" => "Silent".to_string(), // TUF: 2 is Silent fan boost
            "1" => "Turbo".to_string(),  // TUF: 1 is Overboost fan boost
            _ => "Auto".to_string(),     // TUF: 0 is Normal/Auto fan boost
        }
    };

    let manual_duty_raw = duty_str
        .trim()
        .parse::<i32>()
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
    super::windows::read_windows_thermals()
}

pub fn set_fan_profile(profile: &str, manual_duty_pct: Option<u8>) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        let boost_path = "/sys/devices/platform/asus-nb-wmi/fan_boost_mode";
        let hwmon_dir = get_asus_hwmon_dir();
        let pwm_enable_path = hwmon_dir.as_ref().map(|h| h.join("pwm1_enable"));
        let pwm_path = hwmon_dir.as_ref().map(|h| h.join("pwm1"));
        let ec_tool = get_ec_tool_path();

        match profile.to_lowercase().as_str() {
            "auto" | "default" | "balance" => {
                if let Some(p) = pwm_enable_path { let _ = fs::write(p, "2"); }
                let _ = fs::write(boost_path, "0");
                let _ = Command::new(ec_tool).args(["set", "-1"]).output();
            }
            "silent" | "quiet" | "eco" => {
                // Whisper-quiet mode: clamp fans to 25% (~1500 RPM)
                if let Some(p) = pwm_enable_path { let _ = fs::write(p, "1"); }
                if let Some(p) = pwm_path { let _ = fs::write(p, "64"); }
                let _ = fs::write(boost_path, "2"); // 2 is Silent fan boost
                let _ = Command::new(ec_tool).args(["setp", "25", "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", "25", "--fan", "1", "--no-verify"]).output();
            }
            "turbo" | "performance" => {
                // High-performance thermal boost: clamp fans to 80% (~3600 RPM)
                if let Some(p) = pwm_enable_path { let _ = fs::write(p, "1"); }
                if let Some(p) = pwm_path { let _ = fs::write(p, "204"); }
                let _ = fs::write(boost_path, "1"); // 1 is Overboost fan boost
                let _ = Command::new(ec_tool).args(["setp", "80", "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", "80", "--fan", "1", "--no-verify"]).output();
            }
            "max" | "100" | "100% max" => {
                // High-performance fan overdrive without altering CPU power policy
                let _ = fs::write(boost_path, "1");
                if let Some(p) = pwm_enable_path { let _ = fs::write(p, "1"); }
                if let Some(p) = pwm_path { let _ = fs::write(p, "255"); }
                let _ = Command::new(ec_tool).args(["setp", "100", "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", "100", "--fan", "1", "--no-verify"]).output();
            }
            "manual" => {
                let duty_pct = manual_duty_pct.unwrap_or(60).clamp(20, 100);
                let raw_pwm = ((duty_pct as f64 / 100.0) * 255.0).round() as u8;
                if let Some(p) = pwm_enable_path { let _ = fs::write(p, "1"); }
                if let Some(p) = pwm_path { let _ = fs::write(p, raw_pwm.to_string()); }
                if duty_pct >= 85 {
                    let _ = fs::write(boost_path, "1");
                } else if duty_pct <= 35 {
                    let _ = fs::write(boost_path, "2");
                } else {
                    let _ = fs::write(boost_path, "0");
                }
                let _ = Command::new(ec_tool).args(["setp", &duty_pct.to_string(), "--fan", "0", "--no-verify"]).output();
                let _ = Command::new(ec_tool).args(["setp", &duty_pct.to_string(), "--fan", "1", "--no-verify"]).output();
            }
            _ => return Err("Invalid fan profile".to_string()),
        }
        Ok(())
    }
    #[cfg(target_os = "windows")]
    {
        super::windows::set_windows_fan_profile(profile, manual_duty_pct)
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    {
        let _ = (profile, manual_duty_pct);
        Ok(())
    }
}
