#![allow(dead_code)]

use std::fs::OpenOptions;
use std::io::{Read, Seek, SeekFrom, Write};
use std::thread::sleep;
use std::time::Duration;

pub const EC_COMMAND_PORT: u64 = 0x25C;
pub const EC_DATA_PORT: u64 = 0x25D;

const EC_TIMEOUT_MS: u32 = 100;
const EC_FLAG_OBF: u8 = 0x01; // Output buffer full (ready to read)
const EC_FLAG_IBF: u8 = 0x02; // Input buffer full (busy writing)

#[cfg(target_os = "linux")]
fn wait_ec_write(file: &mut std::fs::File) -> bool {
    let mut status = [0u8; 1];
    for _ in 0..EC_TIMEOUT_MS {
        let _ = file.seek(SeekFrom::Start(EC_COMMAND_PORT));
        if file.read_exact(&mut status).is_ok() && (status[0] & EC_FLAG_IBF) == 0 {
            return true;
        }
        sleep(Duration::from_millis(1));
    }
    false
}

#[cfg(target_os = "linux")]
fn wait_ec_read(file: &mut std::fs::File) -> bool {
    let mut status = [0u8; 1];
    for _ in 0..EC_TIMEOUT_MS {
        let _ = file.seek(SeekFrom::Start(EC_COMMAND_PORT));
        if file.read_exact(&mut status).is_ok() && (status[0] & EC_FLAG_OBF) != 0 {
            return true;
        }
        sleep(Duration::from_millis(1));
    }
    false
}

#[cfg(target_os = "linux")]
pub fn write_ec_command(cmd: u8, data: u8) -> bool {
    let mut file = match OpenOptions::new().read(true).write(true).open("/dev/port") {
        Ok(f) => f,
        Err(_) => return false,
    };

    if !wait_ec_write(&mut file) {
        return false;
    }
    let _ = file.seek(SeekFrom::Start(EC_COMMAND_PORT));
    let _ = file.write_all(&[cmd]);

    if !wait_ec_write(&mut file) {
        return false;
    }
    let _ = file.seek(SeekFrom::Start(EC_DATA_PORT));
    let _ = file.write_all(&[data]);

    true
}

#[cfg(target_os = "linux")]
pub fn read_ec_data(cmd: u8) -> Option<u8> {
    let mut file = OpenOptions::new().read(true).write(true).open("/dev/port").ok()?;

    if !wait_ec_write(&mut file) {
        return None;
    }
    let _ = file.seek(SeekFrom::Start(EC_COMMAND_PORT));
    let _ = file.write_all(&[cmd]);

    if !wait_ec_read(&mut file) {
        return None;
    }
    let _ = file.seek(SeekFrom::Start(EC_DATA_PORT));
    let mut data = [0u8; 1];
    if file.read_exact(&mut data).is_ok() {
        Some(data[0])
    } else {
        None
    }
}

#[cfg(not(target_os = "linux"))]
pub fn write_ec_command(_cmd: u8, _data: u8) -> bool {
    false
}

#[cfg(not(target_os = "linux"))]
pub fn read_ec_data(_cmd: u8) -> Option<u8> {
    None
}

pub fn set_fan_duty(duty: u8) {
    // 0x5B = CPU Fan, 0x5D = GPU Fan
    write_ec_command(0x5B, duty);
    write_ec_command(0x5D, duty);
}

pub fn set_auto_mode() {
    // 0x59 0x00 restores EC automatic thermal tables
    write_ec_command(0x59, 0x00);
}

