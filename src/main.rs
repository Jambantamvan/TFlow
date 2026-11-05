mod hw;
mod config;
mod cli;

use clap::Parser;
use cli::{CliArgs, handle_cli_commands};
use hw::battery::{read_battery_telemetry, set_charge_limit};
use hw::power::{apply_power_mode, get_current_power_mode, PowerMode};
use hw::thermals::{read_thermals, set_fan_profile};
use config::AppConfig;
use slint::{ComponentHandle, SharedString, Timer, TimerMode};
use std::time::Duration;

slint::include_modules!();

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = CliArgs::parse();

    // Check if CLI executed a one-off command
    if handle_cli_commands(&args) && !args.daemon {
        return Ok(());
    }

    if args.daemon {
        println!("[TFlow] Running in daemon telemetry mode. Press Ctrl+C to stop.");
        loop {
            let bat = read_battery_telemetry();
            let therm = read_thermals();
            println!(
                "[TFlow Daemon] Bat: {}% ({:.1}W) | CPU: {}°C ({} RPM) | GPU: {}°C ({} RPM)",
                bat.capacity_pct, bat.power_w, therm.cpu_temp_c, therm.cpu_fan_rpm, therm.gpu_temp_c, therm.gpu_fan_rpm
            );
            std::thread::sleep(Duration::from_secs(3));
        }
    }

    // Launch Slint GUI
    let _ = AppConfig::load();
    let app = AppWindow::new()?;

    // Sync initial state
    sync_ui_telemetry(&app);

    // Set callbacks
    let app_weak = app.as_weak();
    app.on_set_power_mode(move |mode_str| {
        if let Some(app) = app_weak.upgrade() {
            if let Some(mode) = PowerMode::from_str(&mode_str) {
                let _ = apply_power_mode(mode);
                let mut cfg = AppConfig::load();
                cfg.power_mode = mode_str.to_string();
                let _ = cfg.save();
                app.set_power_mode(SharedString::from(mode_str));
                sync_ui_telemetry(&app);
            }
        }
    });

    let app_weak = app.as_weak();
    app.on_set_charge_limit(move |limit| {
        if let Some(app) = app_weak.upgrade() {
            let _ = set_charge_limit(limit as u32);
            let mut cfg = AppConfig::load();
            cfg.charge_limit = limit as u32;
            let _ = cfg.save();
            app.set_charge_limit(limit);
            sync_ui_telemetry(&app);
        }
    });

    let app_weak = app.as_weak();
    app.on_set_fan_mode(move |mode_str| {
        if let Some(app) = app_weak.upgrade() {
            let _ = set_fan_profile(&mode_str, None);
            let mut cfg = AppConfig::load();
            cfg.fan_mode = mode_str.to_string();
            let _ = cfg.save();
            app.set_fan_mode(SharedString::from(mode_str));
            sync_ui_telemetry(&app);
        }
    });

    let app_weak = app.as_weak();
    app.on_set_manual_duty(move |duty| {
        if let Some(app) = app_weak.upgrade() {
            let duty_u8 = duty.clamp(20.0, 100.0) as u8;
            let _ = set_fan_profile("manual", Some(duty_u8));
            let mut cfg = AppConfig::load();
            cfg.manual_fan_duty = duty_u8 as i32;
            let _ = cfg.save();
            app.set_manual_fan_duty(duty);
            sync_ui_telemetry(&app);
        }
    });

    let app_weak = app.as_weak();
    app.on_refresh_telemetry(move || {
        if let Some(app) = app_weak.upgrade() {
            sync_ui_telemetry(&app);
        }
    });

    // Background timer for real-time live telemetry (1000ms)
    let timer = Timer::default();
    let app_weak = app.as_weak();
    timer.start(
        TimerMode::Repeated,
        Duration::from_millis(1000),
        move || {
            if let Some(app) = app_weak.upgrade() {
                sync_ui_telemetry(&app);
            }
        },
    );

    app.run()?;
    Ok(())
}

fn sync_ui_telemetry(app: &AppWindow) {
    let bat = read_battery_telemetry();
    let therm = read_thermals();
    let mode = get_current_power_mode();

    // Mode
    let mode_str = match mode {
        PowerMode::Normal => "Normal",
        PowerMode::PowerSaver => "PowerSaver",
        PowerMode::UltraSaver => "UltraSaver",
    };
    app.set_power_mode(SharedString::from(mode_str));

    // AC status & wattage
    app.set_is_ac_online(bat.ac_connected);
    app.set_ac_status(SharedString::from(if bat.ac_connected { "Plugged In" } else { "On Battery" }));
    app.set_power_wattage(SharedString::from(format!("{:.1} W", bat.power_w)));

    // Battery values
    app.set_battery_level(SharedString::from(format!("{}%", bat.capacity_pct)));
    app.set_battery_pct(bat.capacity_pct as f32 / 100.0);
    app.set_battery_health(SharedString::from(format!("{:.1}%", bat.health_pct)));
    app.set_battery_capacity(SharedString::from(format!("{:.1} / {:.1} Wh", bat.charge_full_wh, bat.charge_design_wh)));

    // Runtimes
    if bat.remaining_mins >= 0 {
        let hrs = bat.remaining_mins / 60;
        let mins = bat.remaining_mins % 60;
        app.set_remaining_time(SharedString::from(format!("{}h {}m", hrs, mins)));
    } else {
        app.set_remaining_time(SharedString::from("Connected (AC)"));
    }

    if bat.full_charge_runtime_mins >= 0 {
        let hrs = bat.full_charge_runtime_mins / 60;
        let mins = bat.full_charge_runtime_mins % 60;
        app.set_full_runtime(SharedString::from(format!("{}h {}m", hrs, mins)));
    } else {
        app.set_full_runtime(SharedString::from("N/A"));
    }

    app.set_charge_limit(bat.charge_limit as i32);

    // Thermals
    app.set_cpu_temp(SharedString::from(format!("{}°C", therm.cpu_temp_c)));
    app.set_gpu_temp(SharedString::from(format!("{}°C", therm.gpu_temp_c)));
    app.set_cpu_fan(SharedString::from(format!("{} RPM", therm.cpu_fan_rpm)));
    app.set_gpu_fan(SharedString::from(format!("{} RPM", therm.gpu_fan_rpm)));
    app.set_fan_mode(SharedString::from(therm.fan_mode));
    app.set_manual_fan_duty(therm.manual_fan_duty as f32);
}
