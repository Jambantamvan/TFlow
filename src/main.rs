mod hw;
mod config;
mod cli;

use clap::Parser;
use cli::{CliArgs, handle_cli_commands};
use hw::battery::{read_battery_telemetry, set_charge_limit, BatteryTelemetry};
use hw::power::{apply_power_mode, get_current_power_mode, PowerMode};
use hw::thermals::{read_thermals, set_fan_profile, ThermalTelemetry};
use config::AppConfig;
use slint::{ComponentHandle, SharedString};
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::time::Duration;

slint::include_modules!();

// Debounce state for manual fan slider
static PENDING_MANUAL_DUTY: AtomicU8 = AtomicU8::new(0);
static HAS_PENDING_DUTY: AtomicBool = AtomicBool::new(false);

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Default to reliable native software rendering on Linux Wayland/X11 if not explicitly set
    if std::env::var("SLINT_BACKEND").is_err() {
        std::env::set_var("SLINT_BACKEND", "winit-software");
    }

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

    // Sync initial state synchronously once at launch
    let initial_bat = read_battery_telemetry();
    let initial_therm = read_thermals();
    let initial_mode = get_current_power_mode();
    sync_ui_telemetry(&app, &initial_bat, &initial_therm, initial_mode);

    // 1. Worker thread for debouncing manual fan slider
    std::thread::spawn(|| {
        loop {
            std::thread::sleep(Duration::from_millis(150));
            if HAS_PENDING_DUTY.swap(false, Ordering::SeqCst) {
                let duty = PENDING_MANUAL_DUTY.load(Ordering::SeqCst);
                if duty >= 20 {
                    let _ = set_fan_profile("manual", Some(duty));
                }
            }
        }
    });

    // 2. Set UI Callbacks (Non-blocking: immediate UI feedback + background execution)
    let app_weak = app.as_weak();
    app.on_set_power_mode(move |mode_str| {
        if let Some(app) = app_weak.upgrade() {
            if let Some(mode) = PowerMode::from_str(&mode_str) {
                // Immediate UI feedback
                app.set_power_mode(SharedString::from(mode.as_str()));

                let default_fan = match mode {
                    PowerMode::UltraSave => "Silent",
                    PowerMode::Balance => "Auto",
                    PowerMode::Performance => "Turbo",
                };
                app.set_fan_mode(SharedString::from(default_fan));

                // Execute hardware tuning in background thread to never block UI
                std::thread::spawn(move || {
                    let _ = apply_power_mode(mode);
                    let _ = set_fan_profile(default_fan, None);
                    let mut cfg = AppConfig::load();
                    cfg.power_mode = mode.as_str().to_string();
                    cfg.fan_mode = default_fan.to_string();
                    let _ = cfg.save();
                });
            }
        }
    });

    let app_weak = app.as_weak();
    app.on_set_charge_limit(move |limit| {
        if let Some(app) = app_weak.upgrade() {
            app.set_charge_limit(limit);
            std::thread::spawn(move || {
                let _ = set_charge_limit(limit as u32);
                let mut cfg = AppConfig::load();
                cfg.charge_limit = limit as u32;
                let _ = cfg.save();
            });
        }
    });

    let app_weak = app.as_weak();
    app.on_set_fan_mode(move |mode_str| {
        if let Some(app) = app_weak.upgrade() {
            // Immediate UI feedback
            app.set_fan_mode(SharedString::from(mode_str.clone()));

            let mode_string = mode_str.to_string();
            std::thread::spawn(move || {
                let _ = set_fan_profile(&mode_string, None);
                let mut cfg = AppConfig::load();
                cfg.fan_mode = mode_string;
                let _ = cfg.save();
            });
        }
    });

    let app_weak = app.as_weak();
    app.on_set_manual_duty(move |duty| {
        if let Some(app) = app_weak.upgrade() {
            let duty_u8 = duty.clamp(20.0, 100.0) as u8;
            // Immediate UI feedback on slider & duty text
            app.set_manual_fan_duty(duty);
            app.set_fan_mode(SharedString::from("Manual"));

            // Debounced hardware dispatch via background worker
            PENDING_MANUAL_DUTY.store(duty_u8, Ordering::SeqCst);
            HAS_PENDING_DUTY.store(true, Ordering::SeqCst);
        }
    });

    let app_weak = app.as_weak();
    app.on_refresh_telemetry(move || {
        let app_weak_clone = app_weak.clone();
        std::thread::spawn(move || {
            let bat = read_battery_telemetry();
            let therm = read_thermals();
            let mode = get_current_power_mode();
            let _ = slint::invoke_from_event_loop(move || {
                if let Some(app) = app_weak_clone.upgrade() {
                    sync_ui_telemetry(&app, &bat, &therm, mode);
                }
            });
        });
    });

    // 3. Dedicated Background Telemetry Poller (Runs in background thread, invokes UI safely)
    let app_weak = app.as_weak();
    std::thread::spawn(move || {
        // Short grace period before polling starts
        std::thread::sleep(Duration::from_millis(500));
        loop {
            let bat = read_battery_telemetry();
            let therm = read_thermals();
            let mode = get_current_power_mode();

            let app_weak_clone = app_weak.clone();
            let _ = slint::invoke_from_event_loop(move || {
                if let Some(app) = app_weak_clone.upgrade() {
                    sync_ui_telemetry(&app, &bat, &therm, mode);
                }
            });

            std::thread::sleep(Duration::from_millis(1500));
        }
    });

    app.run()?;
    Ok(())
}

fn sync_ui_telemetry(app: &AppWindow, bat: &BatteryTelemetry, therm: &ThermalTelemetry, mode: PowerMode) {
    // Mode
    app.set_power_mode(SharedString::from(mode.as_str()));

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

    // Thermals & Fans
    app.set_cpu_temp(SharedString::from(format!("{}°C", therm.cpu_temp_c)));
    app.set_gpu_temp(SharedString::from(format!("{}°C", therm.gpu_temp_c)));
    app.set_cpu_fan(SharedString::from(format!("{} RPM", therm.cpu_fan_rpm)));
    app.set_gpu_fan(SharedString::from(format!("{} RPM", therm.gpu_fan_rpm)));

    // Only update fan mode if not currently dragging in manual mode
    if !HAS_PENDING_DUTY.load(Ordering::Relaxed) {
        app.set_fan_mode(SharedString::from(&therm.fan_mode));
        app.set_manual_fan_duty(therm.manual_fan_duty as f32);
    }
}
