from __future__ import annotations

import contextlib
import fcntl
import logging
import math
import os
import platform
import shutil
import signal
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ntplib
import psutil

from otc_metrics import DailyRotationCsvLogger, MetricsLogger
from otc_metrics.lte import LteStatus

shutdown_event = threading.Event()

OTC_I2C_LOCKFILE = "/tmp/otc_i2c.lock"


@contextlib.contextmanager
def i2c_lock():
    """Exclusive file-based lock for I2C bus access across processes."""
    with open(OTC_I2C_LOCKFILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _handle_signal(signum, frame):
    """Set the shutdown event on SIGTERM or SIGINT."""
    logging.info(f"Received signal {signum}, initiating shutdown ...")
    shutdown_event.set()


if TYPE_CHECKING:
    from otc_metrics import sensors

DEFAULT_LOG_DIR = "/var/log/otc_metrics"


def _read_logger_env(
    namespace: str, default_prefix: str, default_wait: int
) -> tuple[Path, str, int, bool]:
    """Read log output directory, file prefix, polling interval, and enabled flag from environment variables.

    Variables follow the pattern ``OTC_<NAMESPACE>_LOGS_{DIR,PREFIX,WAIT,ENABLED}``.
    Set ``OTC_<NAMESPACE>_LOGS_ENABLED=0`` (or ``false``/``no``) to disable a logger entirely.
    """
    ns = namespace.upper()
    enabled = os.environ.get(f"OTC_{ns}_LOGS_ENABLED", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    return (
        Path(os.environ.get(f"OTC_{ns}_LOGS_DIR", DEFAULT_LOG_DIR)),
        os.environ.get(f"OTC_{ns}_LOGS_PREFIX", default_prefix),
        int(os.environ.get(f"OTC_{ns}_LOGS_WAIT", default_wait)),
        enabled,
    )


def _is_raspberry_pi() -> bool:
    """Return True when running on a Raspberry Pi, via best-effort check of /proc/device-tree/model."""
    if platform.machine() not in ("armv7l", "aarch64") or platform.system() != "Linux":
        return False
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False


IS_PI = _is_raspberry_pi()


logging.basicConfig(level="INFO")


def init_daily_rotating_metrics_logger(
    output_folder: Path,
    output_file_prefix: str,
    metrics: dict[str, Callable[[], Any]],
    interval: int,
):
    """Create a `MetricsLogger` backed by a daily-rotating CSV file."""
    logging.info(
        "Start writing metrics {} to {}".format(
            ", ".join(metrics.keys()), output_folder
        )
    )

    return MetricsLogger(
        logger=DailyRotationCsvLogger(
            output_folder,
            output_file_prefix,
        ),
        metrics=metrics,
        interval=interval,
    )


def init_os_logger() -> MetricsLogger | None:
    """Initialize a logger for OS-level metrics: CPU, RAM, disk, and (if available) CPU temperature."""
    os_logs_output_dir, os_logs_prefix, os_logs_wait_time, enabled = _read_logger_env(
        "os", "otc_os_logs", 5
    )
    if not enabled:
        logging.info("OS logger disabled via OTC_OS_LOGS_ENABLED.")
        return None

    os_log_metrics: dict[str, Callable[[], int | float]] = {
        "cpu_perc": psutil.cpu_percent,
        "ram_perc": lambda: psutil.virtual_memory().percent,
        "ram_available": lambda: psutil.virtual_memory().available / (1024 * 1024),
        "disk_perc_root": lambda: psutil.disk_usage("/").percent,
        "disk_free_mb_root": lambda: shutil.disk_usage("/").free / (1024 * 1024),
    }

    def get_cpu_temp():
        return psutil.sensors_temperatures()["cpu_thermal"][0].current

    try:
        get_cpu_temp()
        os_log_metrics["cpu_temp"] = get_cpu_temp
    except (AttributeError, KeyError):
        logging.warning("CPU temp is not available as a metric on this system.")

    return init_daily_rotating_metrics_logger(
        output_folder=os_logs_output_dir,
        output_file_prefix=os_logs_prefix,
        metrics=os_log_metrics,
        interval=os_logs_wait_time,
    )


def init_sensor_logger(
    imu: sensors.LIS2DW12_impl, adc: sensors.TLA2024_impl
) -> MetricsLogger | None:
    """Initialize a logger for hardware sensor metrics: voltages, NTC/IMU temperatures, and accelerometer data."""
    sensor_logs_output_dir, sensor_logs_prefix, sensor_logs_wait_time, enabled = (
        _read_logger_env("sensor", "otc_sensor_logs", 60)
    )
    if not enabled:
        logging.info("Sensor logger disabled via OTC_SENSOR_LOGS_ENABLED.")
        return None

    def read_adc_temp() -> float:
        with i2c_lock():
            v_ntc = adc.read_channel(3)

            vdd = 3.3
            r_fixed = 100000
            ntc_T0 = 298.15
            ntc_b = 3250.0
            r_ntc = r_fixed * v_ntc / (vdd - v_ntc)
            inv_T = (1.0 / ntc_T0) + (1.0 / ntc_b) * math.log(r_ntc / r_fixed)
            T_ntc = 1.0 / inv_T - 273.15
            return T_ntc

    def read_adc_channel(num: int) -> float:
        with i2c_lock():
            return adc.read_channel(num)

    def read_imu_temp() -> float:
        with i2c_lock():
            return imu.read_temp()

    def read_imu_acc() -> dict:
        with i2c_lock():
            x, y, z = imu.read_acc()
            return {"acc_x": x, "acc_y": y, "acc_z": z}

    sensor_metrics = {
        "usb_voltage": lambda: read_adc_channel(0) * 2,
        "external_voltage": lambda: read_adc_channel(1) * 2,
        "battery_voltage": lambda: read_adc_channel(2) * (1000 + 510) / 510,
        "adc_temp": read_adc_temp,
        "acc_temp": read_imu_temp,
        "imu_acc": read_imu_acc,
    }

    return init_daily_rotating_metrics_logger(
        output_folder=sensor_logs_output_dir,
        output_file_prefix=sensor_logs_prefix,
        metrics=sensor_metrics,
        interval=sensor_logs_wait_time,
    )


def init_ntp_logger() -> MetricsLogger | None:
    """Initialize a logger for NTP clock offset against the configured NTP server."""
    ntp_logs_output_dir, ntp_logs_prefix, ntp_logs_wait_time, enabled = (
        _read_logger_env("ntp", "otc_ntp_logs", 60)
    )
    if not enabled:
        logging.info("NTP logger disabled via OTC_NTP_LOGS_ENABLED.")
        return None
    ntp_logs_server = os.environ.get("OTC_NTP_LOGS_SERVER", "de.pool.ntp.org")

    NTP_METRICS = {
        "ntp_offset": lambda: ntplib.NTPClient().request(ntp_logs_server).offset
    }

    return init_daily_rotating_metrics_logger(
        output_folder=ntp_logs_output_dir,
        output_file_prefix=ntp_logs_prefix,
        metrics=NTP_METRICS,
        interval=ntp_logs_wait_time,
    )


def init_lte_logger() -> MetricsLogger | None:
    """Initialize a logger for LTE modem metrics: signal strength and GPS location."""
    lte_logs_output_dir, lte_logs_prefix, lte_logs_wait_time, enabled = (
        _read_logger_env("lte", "otc_lte_logs", 60)
    )
    if not enabled:
        logging.info("LTE logger disabled via OTC_LTE_LOGS_ENABLED.")
        return None
    lte_logs_modem_id = int(os.environ.get("OTC_LTE_LOGS_MODEM_ID", 0))

    lte_status = LteStatus(modem_id=lte_logs_modem_id)

    def get_signal_strength() -> dict:
        sig = lte_status.get_signal_strenght()
        return {"rsrp": sig.rsrp, "rsrq": sig.rsrq, "rssi": sig.rssi, "snr": sig.snr}

    def get_location() -> dict:
        loc_info = lte_status.get_location_info()
        gps = loc_info.gps
        return {
            "cell_id": loc_info.cell_id,
            "gps_time": gps.time if gps else "N/A",
            "gps_lon": gps.lon if gps else "N/A",
            "gps_lat": gps.lat if gps else "N/A",
        }

    lte_metrics = {
        "signal": get_signal_strength,
        "location": get_location,
    }

    return init_daily_rotating_metrics_logger(
        output_folder=lte_logs_output_dir,
        output_file_prefix=lte_logs_prefix,
        metrics=lte_metrics,
        interval=lte_logs_wait_time,
    )


def main():
    """Entry point: start all metric loggers and block until SIGTERM or SIGINT."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    loggers = []

    imu = adc = None

    if logger := init_os_logger():
        loggers.append(logger)
    if logger := init_ntp_logger():
        loggers.append(logger)

    # write sensor & lte metrics only if running on Pi
    if IS_PI:
        from otc_metrics import sensors

        imu = sensors.LIS2DW12_impl()
        adc = sensors.TLA2024_impl()

        imu.open()
        adc.open()

        if logger := init_sensor_logger(imu=imu, adc=adc):
            loggers.append(logger)
        if logger := init_lte_logger():
            loggers.append(logger)
    else:
        logging.warning("Not running on Raspberry Pi, skip logging sensors & lte.")

    for logger in loggers:
        logger.start()

    # block main thread until signal is raised.
    shutdown_event.wait()

    print("Shutting down loggers ...")
    for logger in loggers:
        logger.stop()
    for logger in loggers:
        logger.join()
    if imu:
        imu.close()
    if adc:
        adc.close()


if __name__ == "__main__":
    main()
