# DIC Visualisierung

Local simulation and visualization tool for the Formula Student Driver Information Center (DIC).

The application compiles and executes the original C firmware on the host computer and displays the resulting LCD output, LEDs and CAN data in a browser.

The firmware is loaded from a separate local repository and is not modified by the simulator.

## Features

- Live preview of the 20x4 LCD, including custom characters
- Simulation of LEDs and warning indicators
- Adjustable vehicle data and sensor values
- CAN message simulation and raw byte overrides
- AMS and IMD fault simulation
- Display page selection
- Automatic recompilation when firmware files change
- Support for local Git branches
- Display of outgoing CAN messages
- Local browser interface

## Requirements

- Python 3.10+
- C compiler (Clang or GCC)
- Modern web browser
- Local DIC firmware repository containing `DIC_23`
- Git (optional, required for selecting Git revisions)

No additional Python packages are required.

## Installation

Clone or download this repository.

The visualization and firmware should be stored in separate directories.

### macOS

Install Python 3.10 or newer.

Install the Apple Command Line Tools if they are not already available:

```bash
xcode-select --install
```

Start the application by double-clicking:

```text
Start_macOS.command
```

Alternatively, run:

```bash
python3 start.py
```

If the start script is not executable:

```bash
chmod +x Start_macOS.command
```

### Windows

Windows x64 requires Python 3.10+ and a compatible GCC installation.

The recommended compiler is MSYS2 UCRT64 GCC.

#### Automatic setup

Extract the downloaded repository and run:

```text
Einrichtung_Windows.bat
```

The setup checks the required components and can install missing dependencies using `winget`.

After setup, start the application using:

```text
Start_Windows.bat
```

The setup only needs to be completed once.

#### Manual setup

Install Python from:

https://www.python.org/downloads/windows/

Install MSYS2:

https://www.msys2.org/

Open the **MSYS2 UCRT64** terminal and update the installation:

```bash
pacman -Syu
```

Restart the MSYS2 terminal if requested and repeat the update until it completes.

Install GCC:

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-gcc
```

Verify the installation:

```bash
gcc --version
```

The application automatically detects GCC when MSYS2 is installed in its default location:

```text
C:\msys64\ucrt64\bin\gcc.exe
```

Start the visualization using `Start_Windows.bat`.

**Note:** Windows support has not yet been validated on a physical Windows system. Windows ARM is not officially supported.

## Usage

Start the application and open the local browser interface.

By default, the server runs at:

```text
http://127.0.0.1:8766/
```

If the port is unavailable, another free local port is selected automatically.

### Firmware selection

1. Open the `Quelle` tab.
2. Select the local firmware directory.
3. Choose the firmware source or Git branch.
4. Wait for the firmware to compile.

The selected directory must contain the required DIC firmware files.

The application supports both the repository root and its `DIC_23` subdirectory.

### Live preview

The simulator executes the original firmware logic and renders the resulting display output.

Vehicle values can be adjusted in the `Beispielwerte` tab.

Available inputs include:

- Vehicle speed and GPS data
- Battery voltage and state of charge
- Motor and inverter temperatures
- Brake pressure and pedal sensors
- Steering angle
- AMS and IMD states
- Fusebox and SDC data
- Steering wheel controls
- CAN messages

Raw CAN data can be entered to test specific messages independently of the predefined input fields.

### Firmware changes

The application checks the selected firmware directory for changes approximately once per second.

When a source file changes, the simulator recompiles the firmware automatically.

Changes must be saved in the editor before they become visible.

The original firmware files are never modified.

### Git revisions

The simulator supports:

- Current working directory and active branch
- Local Git branches
- Remote-tracking branches
- `TY26_Test` reference

Selecting another Git revision does not change the checked-out branch or modify the working directory.

Uncommitted changes are only included when using the current working directory.

## Architecture

The simulator uses the original C implementation instead of recreating the display logic in JavaScript.

```text
DIC Firmware
    |
    v
Source files
    |
    v
Host compilation (Clang / GCC)
    |
    v
Firmware execution
    |
    v
Simulated CAN / GPIO / SPI
    |
    v
LCD and LED output
    |
    v
Browser interface
```

The host build replaces hardware-specific AVR interfaces with simulation adapters.

Generated files and compiled binaries are stored in temporary directories outside the firmware repository.

The simulator currently targets the existing DIC firmware structure. Additional source files, libraries or hardware interfaces may require changes to the host adapter.

## Project Structure

```text
DIC_Visualisierung/
├── server.py
├── settings.py
├── choose_folder.py
├── start.py
├── Start_macOS.command
├── Start_Windows.bat
├── Einrichtung_Windows.bat
├── windows.ps1
├── web/
│   └── index.html
├── tests/
│   ├── test_local.py
│   ├── test_windows.ps1
│   └── integration.py
├── .gitignore
├── VERSION
└── README.md
```

## Testing

Run the local unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the firmware integration tests:

```bash
python3 tests/integration.py "/path/to/DIC_Firmware"
```

The integration tests require a local firmware repository with the expected Git references.

On Windows, use `py -3` instead of `python3`.

Windows setup tests can be executed with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_windows.ps1
```

## Configuration

The selected firmware directory is stored locally.

| Platform | Configuration path |
|----------|-------------------|
| macOS | `~/Library/Application Support/DIC_Visualisierung/settings.json` |
| Windows | `%LOCALAPPDATA%\DIC_Visualisierung\settings.json` |
| Linux | `~/.config/DIC_Visualisierung/settings.json` |

Linux is not currently a validated target platform.

Additional startup options:

```bash
python3 start.py --port 8766
python3 start.py --no-browser
python3 start.py --config-dir "/path/to/config"
```

A custom C compiler can be specified using the `DIC_CC` environment variable.

## Limitations

The application is intended for firmware development and testing.

It does not provide a complete emulation of the AT90CAN128 microcontroller.

The following components are simulated or simplified:

- CAN communication
- GPIO and SPI interfaces
- Hardware timing
- Electrical behavior
- LCD and LED hardware

Each simulation request executes a separate firmware run. The application is not a continuous real-time CAN emulator.

The simulator does not replace testing on the actual DIC hardware.

## Security

The server runs locally and listens only on `127.0.0.1`.

No cloud connection or telemetry is required.

The application compiles and executes C code from the selected firmware repository. Only use firmware sources from trusted repositories.

The firmware repository remains read-only during simulation.