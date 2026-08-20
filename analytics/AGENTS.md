# GoHMotech Project Context

## Project
GoHMotech: Smart Goat House Monitoring System Using IoT and ML.

## BLE Goat Tracking

BLE beacon model:
- DX-CP101
- Bluetooth Low Energy beacon
- Configuration app: DX-SMART

Test beacon:
- Device name: CP101-3E95
- MAC address: 48:87:2D:9E:3E:95
- Battery tested at 100%

### iBeacon configuration

UUID:
E2C56DB5DFFB48D2B060D0F5A71096E0

Major:
1

Minor:
1

RSSI @ 1 meter:
-57 dBm

Advertising interval:
400 ms

TX Power:
+2.5 dBm

Trigger:
OFF

Identification convention:
- UUID = GoHMotech beacon system
- Major = Farm/herd ID
- Minor = Individual goat ID

Example:
- Major 1 / Minor 1 = Goat 01
- Major 1 / Minor 2 = Goat 02
- Major 1 / Minor 3 = Goat 03

## BLE Architecture

Goat BLE Beacon
    ↓
Raspberry Pi 5 Bluetooth Scanner
    ↓
GoHMotech Backend
    ↓
Database
    ↓
Dashboard

The Raspberry Pi should scan BLE advertisements.
Do not require Bluetooth pairing or bonding with each beacon.

RSSI should only be used for approximate proximity, not exact distance.

## Development Rules

- Analyze the existing project before modifying code.
- Do not modify working features unnecessarily.
- Do not rewrite the existing architecture unless required.
- Integrate BLE tracking into the existing GoHMotech backend.
- Raspberry Pi 5 is the main server/gateway.
- ESP32 should only be used when necessary for sensors/actuators.