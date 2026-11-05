# TFlow

A lightweight, cross-platform hardware management utility and thermal controller designed for gaming laptops, specifically tailored for ASUS TUF and ROG platforms with dual-boot support across Linux and Windows.

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-lightgrey.svg)](#supported-hardware)
[![Language](https://img.shields.io/badge/Language-Python%203-yellow.svg)](#prerequisites)

---

## Overview

Modern gaming laptops frequently encounter thermal constraints, firmware fan-curve locks, and unoptimized boost algorithms. On models such as the ASUS TUF Gaming F15 (FX506 series), standard ACPI sysfs interfaces (`pwm1`) often act as non-functional stubs ignored by the Embedded Controller (EC). Consequently, users are unable to customize fan speeds or manage aggressive sustained CPU boost profiles natively without relying on heavy OEM background suites.

TFlow provides a unified, zero-bloat abstraction layer that interfaces directly with laptop hardware registers on both Linux and Windows, offering:

- Direct low-level Embedded Controller (EC) fan PWM control via private I/O ports.
- Dynamic thermal profiles with configurable CPU power envelopes (Intel RAPL PL1/PL2).
- Clockspeed and boost management to eliminate thermal throttling spikes.
- GPU frequency control via NVIDIA Management Library interfaces.
- Unified graphical dashboard (Tkinter) and headless Command Line Interface (CLI).
- OCI containerization support (Docker / Podman) for multi-distribution portability.

---

## Architecture and Operating Modes

TFlow decouples platform-dependent hardware access through an abstraction layer (`backend.py`) that transparently selects the appropriate hardware bridge at runtime.

```
                  +-----------------------------------+
                  |        TFlow User Interface       |
                  |     (gui.py / CLI via main.py)    |
                  +-----------------+-----------------+
                                    |
                  +-----------------v-----------------+
                  |      Hardware Abstraction Layer   |
                  |            (backend.py)           |
                  +--------+-----------------+--------+
                           |                 |
        [ Linux Platform ] |                 | [ Windows Platform ]
                           v                 v
        +-----------------------+   +-----------------------+
        | - EC Port I/O (0x25C) |   | - WinIO64 Driver      |
        | - Intel RAPL (sysfs)  |   | - powercfg API / GUID |
        | - intel_pstate        |   | - nvidia-smi          |
        | - nvidia-smi          |   +-----------------------+
        +-----------------------+
```

### Hardware Control Mechanisms

#### 1. Embedded Controller Fan Interface
- **I/O Ports:** Data Port `0x25C`, Command/Status Port `0x25D`.
- **Protocol:** Commands are dispatched through Table 2 (`0xDD` transaction). Register `0x35` controls the 8-bit PWM duty cycle (`0x00` to `0xFF` / 0–255), while register `0x31` toggles manual override and BIOS automatic control.
- **Tachometer Readout:** Physical RPM is acquired directly from hardware counters on Table 2 registers `0x33` (Low Byte) and `0x34` (High Byte), mapped through the BIOS frequency scalar (`2,156,250 / Period`).

#### 2. CPU Power and Thermal Profiles
- **Silent Profile:** PL1 capped at 25W, PL2 capped at 35W, Turbo Boost disabled (base frequency locked), Energy Performance Preference set to `power`, GPU clocks locked to 1200 MHz.
- **Balanced Profile:** PL1 configured to 35W, PL2 to 50W, Turbo scaling capped at 85% (~3.5 GHz), EPP set to `balance_performance`, GPU clocks bounded at 1450 MHz.
- **Turbo Profile:** Full sustained power limits (PL1 50W, PL2 78W), Turbo scaling uncapped (100%), EPP set to `performance`, GPU clock limitations fully released.

#### 3. Cold Mode (Anti-Throttling)
Eliminates aggressive, short-lived CPU temperature spikes (reaching 90°C–95°C) caused by unconstrained burst multipliers during moderate workloads:
- **Linux:** Enforced via `/sys/devices/system/cpu/intel_pstate/no_turbo`.
- **Windows:** Configured using the native hidden power setting GUID `be337238-0d82-4146-a960-4f3749d470c7` (Processor Performance Boost Mode) via `powercfg`.

---

## Supported Hardware

- **Validated Models:** ASUS TUF Gaming F15 (FX506LH, FX506LU, FX506HE, FX506HM), TUF Gaming A15 (FA506 series), and related ASUS laptops utilizing the ITE/ENE Embedded Controller architecture.
- **Operating Systems:**
  - Linux: Kernel 5.15+ (Arch Linux, CachyOS, Ubuntu, Debian, Fedora, openSUSE).
  - Windows: Windows 10 / Windows 11 (64-bit).

---

## Installation and Deployment

### Linux: Native Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Jambantamvan/TFlow.git
   cd TFlow
   ```

2. Run the automated installer with root privileges:
   ```bash
   chmod +x install.sh
   sudo ./install.sh
   ```
   *The installer deploys udev permission rules for sysfs endpoints, compiles the helper binary (`asus-fan-control-ec`) with setuid root for unprivileged port I/O execution, and creates system-wide desktop shortcuts.*

3. Launch the application:
   ```bash
   # Launch GUI
   tflow

   # Or run via launcher script
   ./run.sh
   ```

### Linux: Containerized Deployment (Docker / Podman)

For distributions where building local drivers is undesirable, TFlow provides a fully containerized runtime with X11 display forwarding and raw device passthrough:

```bash
# Automated container build and execution
./docker-run.sh
```

Alternatively, deploy using Docker Compose:

```bash
docker compose up
```

### Windows: Native Installation

1. Clone or download the repository to your Windows filesystem.
2. Navigate to the project directory:
   ```cmd
   cd TFlow
   ```
3. Run the Windows launcher:
   ```cmd
   run.bat
   ```
   *Note: Administrative elevation is requested automatically to permit the WinIO driver to access motherboard I/O ports.*

---

## Command Line Interface (CLI)

TFlow supports headless operation for automated scripts, gaming mode hooks, or remote control:

```
Usage: tflow [command] [options]

Commands:
  status                 Display real-time hardware status, temperatures, and fan speeds
  max                    Force all cooling fans to 100% PWM (Duty 255)
  auto                   Hand fan speed control back to the BIOS / EC automatic curve
  set <percentage>       Set manual fan speed to an integer between 0 and 100
  profile <name>         Apply hardware power profile: Silent | Balanced | Turbo
  cold <on|off>          Enable or disable Cold Mode (Processor Boost Throttling Prevention)
```

### Examples

```bash
# Query hardware telemetry
tflow status

# Engage full cooling performance prior to launching heavy workloads
tflow max

# Lock CPU to base clock for quiet, low-temperature operation
tflow cold on

# Switch to Balanced profile
tflow profile Balanced
```

---

## Project Structure

```
TFlow/
|-- backend.py             # Cross-platform hardware communication layer
|-- gui.py                 # Tkinter-based dark dashboard
|-- main.py                # Entrypoint supporting both GUI and CLI invocations
|-- run.sh                 # Linux native launcher
|-- run.bat                # Windows native launcher
|-- install.sh             # Linux setup script (udev rules, compilation, shortcuts)
|-- Dockerfile             # OCI container build configuration
|-- docker-compose.yml     # Compose file for hardware and display passthrough
|-- docker-run.sh          # One-click Docker/Podman executor
|-- windows_bin/           # Pre-compiled Windows Ring-0 access tools
|   |-- AsusFanControl.exe
|   |-- AsusWinIO64.dll
|   `-- PsExec.exe
|-- requirements.txt       # Environment notes
|-- LICENSE                # GNU General Public License v3.0
`-- README.md              # Technical documentation
```

---

## Security and Privileges

Direct hardware access on modern operating systems requires strict permission handling:

- **Port Access on Linux:** Motherboard I/O ports `0x25C` and `0x25D` require `iopl(3)` privileges or `CAP_SYS_RAWIO`. TFlow utilizes a dedicated, audited C binary (`asus-fan-control-ec`) configured with setuid root (`chmod 4755`) so that the main GUI and CLI run securely as unprivileged user processes.
- **Sysfs Access on Linux:** The provided udev rule (`99-asus-fan.rules`) explicitly grants read/write permissions only to specific platform nodes (`throttle_thermal_policy`, `fan_boost_mode`, Intel RAPL constraints, and `intel_pstate`), preventing broad root execution.
- **Windows Driver Security:** Windows requires administrative privileges to load `AsusWinIO64.dll` into kernel address space for port read/write cycles.

---

## License

This software is licensed under the [GNU General Public License v3.0](LICENSE).  
Embedded controller communication logic is adapted from the open-source `asus-fan-control-ec` project by Keyitdev (GPL-3.0).

---

## Contributing

Contributions, bug reports, and hardware validation reports across additional laptop revisions are welcome. Please submit pull requests or open an issue on the GitHub repository tracker.
