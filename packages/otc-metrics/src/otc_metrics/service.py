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
from typing import TYPE_CHECKING, Any, Literal

import ntplib
import psutil

from otc_metrics import DailyRotationCsvLogger, MetricsLogger
from otc_metrics.lte import LteStatus

shutdown_event = threading.Event()

OTC_I2C_LOCKFILE = "/tmp/otc_i2c.lock"


@contextlib.contextmanager
def i2c_lock():
    with open(OTC_I2C_LOCKFILE, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _handle_signal(signum, frame):
    logging.info(f"Received signal {signum}, initiating shutdown ...")
    shutdown_event.set()


if TYPE_CHECKING:
    from otc_metrics import sensors

DEFAULT_LOG_DIR = "/var/log/otc_metrics"


# best-effort to assess whether we are running on Raspberry Pi
def _is_raspberry_pi() -> bool:
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


def init_os_logger() -> MetricsLogger:
    os_logs_output_dir = Path(os.environ.get("OTC_OS_LOGS_DIR", DEFAULT_LOG_DIR))
    os_logs_prefix = os.environ.get("OTC_OS_LOGS_PREFIX", "otc_os_logs")
    os_logs_wait_time = int(os.environ.get("OTC_OS_LOGS_WAIT", 5))

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
) -> MetricsLogger:
    sensor_logs_output_dir = Path(
        os.environ.get("OTC_SENSOR_LOGS_DIR", DEFAULT_LOG_DIR)
    )
    sensor_logs_prefix = os.environ.get("OTC_SENSOR_LOGS_PREFIX", "otc_sensor_logs")
    sensor_logs_wait_time = int(os.environ.get("OTC_SENSOR_LOGS_WAIT", 60))

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

    def read_imu_acc() -> tuple[float, float, float]:
        with i2c_lock():
            return imu.read_acc()

    sensor_metrics = {
        "usb_voltage": lambda: read_adc_channel(0) * 2,
        "external_voltage": lambda: read_adc_channel(1) * 2,
        "battery_voltage": lambda: read_adc_channel(2) * (1000 + 510) / 510,
        "adc_temp": read_adc_temp,
        "acc_temp": read_imu_temp,
        "acc_x": lambda: read_imu_acc()[0],
        "acc_y": lambda: read_imu_acc()[1],
        "acc_z": lambda: read_imu_acc()[2],
    }

    return init_daily_rotating_metrics_logger(
        output_folder=sensor_logs_output_dir,
        output_file_prefix=sensor_logs_prefix,
        metrics=sensor_metrics,
        interval=sensor_logs_wait_time,
    )


def init_ntp_logger() -> MetricsLogger:

    ntp_logs_output_dir = Path(os.environ.get("OTC_NTP_LOGS_DIR", DEFAULT_LOG_DIR))
    ntp_logs_prefix = os.environ.get("OTC_NTP_LOGS_PREFIX", "otc_ntp_logs")
    ntp_logs_wait_time = int(os.environ.get("OTC_NTP_LOGS_WAIT", 60))
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


def init_lte_logger() -> MetricsLogger:

    lte_logs_output_dir = Path(os.environ.get("OTC_LTE_LOGS_DIR", DEFAULT_LOG_DIR))
    lte_logs_prefix = os.environ.get("OTC_LTE_LOGS_PREFIX", "otc_lte_logs")
    lte_logs_wait_time = int(os.environ.get("OTC_LTE_LOGS_WAIT", 60))
    lte_logs_modem_id = int(os.environ.get("OTC_LTE_LOGS_MODEM_ID", 0))

    lte_status = LteStatus(modem_id=lte_logs_modem_id)

    def get_gps_info(value: Literal["time", "lon", "lat"]):
        loc_info = lte_status.get_location_info()

        if loc_info.gps is None:
            return None

        return getattr(loc_info, value)

    lte_metrics = {
        "rsrp": lambda: lte_status.get_signal_strenght().rsrp,
        "rsrq": lambda: lte_status.get_signal_strenght().rsrq,
        "rssi": lambda: lte_status.get_signal_strenght().rssi,
        "snr": lambda: lte_status.get_signal_strenght().snr,
        "cell_id": lambda: lte_status.get_location_info().cell_id,
        "gps_time": lambda: get_gps_info("time") or "N/A",
        "gps_lon": lambda: get_gps_info("lon") or "N/A",
        "gps_lat": lambda: get_gps_info("lat") or "N/A",
    }

    return init_daily_rotating_metrics_logger(
        output_folder=lte_logs_output_dir,
        output_file_prefix=lte_logs_prefix,
        metrics=lte_metrics,
        interval=lte_logs_wait_time,
    )


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    loggers = []

    imu = adc = None

    loggers.append(init_os_logger())
    loggers.append(init_ntp_logger())

    # write sensor & lte metrics only if running on Pi
    if IS_PI:
        from otc_metrics import sensors

        imu = sensors.LIS2DW12_impl()
        adc = sensors.TLA2024_impl()

        imu.open()
        adc.open()

        loggers.append(init_sensor_logger(imu=imu, adc=adc))

        loggers.append(init_lte_logger())
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
