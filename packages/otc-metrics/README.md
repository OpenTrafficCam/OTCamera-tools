# otc-metrics

A small utility package for collecting system and hardware metrics on OTCamera v2 and writing them to daily-rotating CSV files.

Each logger runs as a background thread and appends one row per interval to a file named `<prefix>_YYYY-MM-DD.csv`. Files rotate automatically at midnight. All loggers are enabled by default.

## Installation

From the repository root:

```bash
uv sync
```

## Loggers

### OS Logger

Collects standard operating system metrics via `psutil`.

| Column | Description |
|---|---|
| `datetime` | ISO 8601 timestamp |
| `cpu_perc` | CPU usage (%) |
| `ram_perc` | RAM usage (%) |
| `ram_available` | Available RAM (MB) |
| `disk_perc_root` | Disk usage on `/` (%) |
| `disk_free_mb_root` | Free disk space on `/` (MB) |
| `cpu_temp` | CPU temperature (°C); omitted if sensor unavailable |

| Variable | Default | Description |
|---|---|---|
| `OTC_OS_LOGS_ENABLED` | `1` | Set to `0`, `false`, or `no` to disable |
| `OTC_OS_LOGS_DIR` | `/var/log/otc_metrics` | Output directory |
| `OTC_OS_LOGS_PREFIX` | `otc_os_logs` | Filename prefix |
| `OTC_OS_LOGS_WAIT` | `5` | Collection interval (seconds) |

---

### Sensor Logger

Reads voltage and temperature from a TLA2024 analog-to-digital converter and acceleration/temperature from a LIS2DW12 IMU over I2C. Only runs on Raspberry Pi.

| Column | Description |
|---|---|
| `datetime` | ISO 8601 timestamp |
| `usb_voltage` | USB supply voltage (V) |
| `external_voltage` | External supply voltage (V) |
| `battery_voltage` | Battery voltage (V) |
| `adc_temp` | ADC temperature (°C) |
| `acc_temp` | Accelerometer die temperature (°C) |
| `acc_x` / `acc_y` / `acc_z` | Acceleration on each axis (g) |

| Variable | Default | Description |
|---|---|---|
| `OTC_SENSOR_LOGS_ENABLED` | `1` | Set to `0`, `false`, or `no` to disable |
| `OTC_SENSOR_LOGS_DIR` | `/var/log/otc_metrics` | Output directory |
| `OTC_SENSOR_LOGS_PREFIX` | `otc_sensor_logs` | Filename prefix |
| `OTC_SENSOR_LOGS_WAIT` | `60` | Collection interval (seconds) |

---

### NTP Logger

Measures the system clock offset against an NTP server using `ntplib`.

| Column | Description |
|---|---|
| `datetime` | ISO 8601 timestamp |
| `ntp_offset` | Clock offset from NTP server (seconds) |

| Variable | Default | Description |
|---|---|---|
| `OTC_NTP_LOGS_ENABLED` | `1` | Set to `0`, `false`, or `no` to disable |
| `OTC_NTP_LOGS_DIR` | `/var/log/otc_metrics` | Output directory |
| `OTC_NTP_LOGS_PREFIX` | `otc_ntp_logs` | Filename prefix |
| `OTC_NTP_LOGS_WAIT` | `60` | Collection interval (seconds) |
| `OTC_NTP_LOGS_SERVER` | `de.pool.ntp.org` | NTP server address |

---

### LTE Logger

Queries modem signal strength and GPS location via `mmcli` (ModemManager). Only runs on Raspberry Pi.

Before starting the logger, signal collection and GPS must be activated once on the modem. First verify the modem index with:

```bash
mmcli -L
```

Then enable signal reporting and GPS (replace `0` with the actual modem index if different):

```bash
sudo mmcli -m 0 --signal-setup 60
sudo mmcli -m 0 --location-enable-gps-nmea
```

| Column | Description |
|---|---|
| `datetime` | ISO 8601 timestamp |
| `rsrp` | Reference Signal Received Power (dBm) |
| `rsrq` | Reference Signal Received Quality (dB) |
| `rssi` | Received Signal Strength Indicator (dBm) |
| `snr` | Signal-to-Noise Ratio (dB) |
| `cell_id` | Serving cell tower ID |
| `gps_time` | GPS fix timestamp; `N/A` if no fix |
| `gps_lat` | GPS latitude; `N/A` if no fix |
| `gps_lon` | GPS longitude; `N/A` if no fix |

| Variable | Default | Description |
|---|---|---|
| `OTC_LTE_LOGS_ENABLED` | `1` | Set to `0`, `false`, or `no` to disable |
| `OTC_LTE_LOGS_DIR` | `/var/log/otc_metrics` | Output directory |
| `OTC_LTE_LOGS_PREFIX` | `otc_lte_logs` | Filename prefix |
| `OTC_LTE_LOGS_WAIT` | `60` | Collection interval (seconds) |
| `OTC_LTE_LOGS_MODEM_ID` | `0` | ModemManager modem index |

---

## Usage

Run the service directly:

```bash
otc-metrics
```

The process blocks until it receives `SIGTERM` or `SIGINT`, then shuts down all loggers cleanly. On non-Raspberry Pi hosts the sensor and LTE loggers are skipped automatically.
