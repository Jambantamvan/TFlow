use std::fs;
use std::path::PathBuf;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub power_mode: String,
    pub charge_limit: u32,
    pub fan_mode: String,
    pub manual_fan_duty: i32,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            power_mode: "Normal".to_string(),
            charge_limit: 80,
            fan_mode: "Auto".to_string(),
            manual_fan_duty: 50,
        }
    }
}

impl AppConfig {
    pub fn config_path() -> PathBuf {
        let home = std::env::var("HOME").unwrap_or_else(|_| "/home/abrar".to_string());
        PathBuf::from(home).join(".config/tflow/config.json")
    }

    pub fn load() -> Self {
        let path = Self::config_path();
        if let Ok(data) = fs::read_to_string(&path) {
            if let Ok(cfg) = serde_json::from_str::<AppConfig>(&data) {
                return cfg;
            }
        }
        let default = Self::default();
        let _ = default.save();
        default
    }

    pub fn save(&self) -> Result<(), std::io::Error> {
        let path = Self::config_path();
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let json = serde_json::to_string_pretty(self)?;
        fs::write(path, json)
    }
}

