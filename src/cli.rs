use clap::Parser;
use crate::hw::battery::{read_battery_telemetry, set_charge_limit};
use crate::hw::power::{apply_power_mode, get_current_power_mode, PowerMode};
use crate::hw::thermals::{read_thermals, set_fan_profile};

#[derive(Parser, Debug)]
#[command(
    name = "tflow",
    version = "2.1.0",
    about = "TFlow: Hardware, Power, and Battery Telemetry Center for ASUS Gaming Laptops"
)]
pub struct CliArgs {
    /// Print live hardware telemetry status and exit
    #[arg(short, long)]
    pub status: bool,

    /// Set power profile: ultrasave, balance, performance
    #[arg(short, long)]
    pub mode: Option<String>,

    /// Set battery care charge limit: 60, 80, 100
    #[arg(short = 'c', long)]
    pub charge_limit: Option<u32>,

    /// Set fan profile: auto, silent, turbo, max, manual
    #[arg(short = 'f', long)]
    pub fan: Option<String>,

    /// Set manual fan duty cycle percentage (20 to 100)
    #[arg(long)]
    pub fan_duty: Option<u8>,

    /// Run as headless background monitoring daemon
    #[arg(short, long)]
    pub daemon: bool,
}

pub fn handle_cli_commands(args: &CliArgs) -> bool {
    let mut handled = false;

    if let Some(mode_str) = &args.mode {
        if let Some(mode) = PowerMode::from_str(mode_str) {
            match apply_power_mode(mode) {
                Ok(_) => {
                    let default_fan = match mode {
                        PowerMode::UltraSave => "Silent",
                        PowerMode::Balance => "Auto",
                        PowerMode::Performance => "Turbo",
                    };
                    let _ = set_fan_profile(default_fan, None);
                    println!("[TFlow] Power profile applied: {} (Fan default: {})", mode.as_str(), default_fan);
                }
                Err(e) => eprintln!("[TFlow] Error applying power profile: {}", e),
            }
        } else {
            eprintln!("[TFlow] Unknown power mode: {}. Use ultrasave, balance, or performance.", mode_str);
        }
        handled = true;
    }

    if let Some(limit) = args.charge_limit {
        match set_charge_limit(limit) {
            Ok(_) => println!("[TFlow] Battery charge limit set to: {}%", limit),
            Err(e) => eprintln!("[TFlow] Error setting battery charge limit: {}", e),
        }
        handled = true;
    }

    if let Some(fan_mode) = &args.fan {
        match set_fan_profile(fan_mode, args.fan_duty) {
            Ok(_) => println!("[TFlow] Fan mode applied: {}", fan_mode),
            Err(e) => eprintln!("[TFlow] Error applying fan mode: {}", e),
        }
        handled = true;
    }

    if args.status {
        print_telemetry_table();
        handled = true;
    }

    handled
}

pub fn print_telemetry_table() {
    let bat = read_battery_telemetry();
    let therm = read_thermals();
    let current_mode = get_current_power_mode();

    println!("============================================================");
    println!("  TFlow v2.1.0 - Hardware & Power Telemetry Dashboard");
    println!("============================================================");
    println!("  Power & Battery Subsystem:");
    println!("    Active Profile      : {}", current_mode.as_str());
    println!("    AC Adapter Status   : {}", if bat.ac_connected { "Connected (AC Power)" } else { "Disconnected (Battery)" });
    println!("    Battery State       : {}", bat.status);
    println!("    Current Charge      : {}%", bat.capacity_pct);
    println!("    Discharge / Power   : {:.1} W ({:.2} V, {:.2} A)", bat.power_w, bat.voltage_v, bat.current_a);
    println!("    Battery Health      : {:.1}% ({:.1} Wh / {:.1} Wh)", bat.health_pct, bat.charge_full_wh, bat.charge_design_wh);
    
    if bat.remaining_mins >= 0 {
        let hrs = bat.remaining_mins / 60;
        let mins = bat.remaining_mins % 60;
        println!("    Remaining Runtime   : {}h {}m", hrs, mins);
    } else {
        println!("    Remaining Runtime   : N/A (Plugged In / Full)");
    }

    if bat.full_charge_runtime_mins >= 0 {
        let hrs = bat.full_charge_runtime_mins / 60;
        let mins = bat.full_charge_runtime_mins % 60;
        println!("    Est. Full Runtime   : {}h {}m", hrs, mins);
    } else {
        println!("    Est. Full Runtime   : N/A");
    }

    println!("    Charge Threshold    : {}% Max", bat.charge_limit);
    println!("------------------------------------------------------------");
    println!("  Thermal & Cooling Subsystem:");
    println!("    CPU Temperature     : {}°C", therm.cpu_temp_c);
    println!("    CPU Fan Speed       : {} RPM", therm.cpu_fan_rpm);
    println!("    GPU Temperature     : {}°C", therm.gpu_temp_c);
    println!("    GPU Fan Speed       : {} RPM", therm.gpu_fan_rpm);
    println!("    Fan Profile Mode    : {}", therm.fan_mode);
    println!("    Manual Duty Cycle   : {}%", therm.manual_fan_duty);
    println!("============================================================");
}
