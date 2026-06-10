import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import ntplib
import psutil

from otc_metrics import DailyRotationCsvLogger, MetricsLogger

logging.basicConfig(level="INFO")


def init_daily_rotating_metrics_logger(
    output_folder: Path,
    output_file_prefix: str,
    metrics: dict[str, Callable[[], int | float]],
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
    os_logs_output_dir = Path(os.environ.get("OTC_OS_LOGS_DIR", "/var/log"))
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
        return psutil.sensors_tempertaures()["cpu_thermal"][0].current

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


def init_ntp_logger() -> MetricsLogger:

    ntp_logs_output_dir = Path(os.environ.get("OTC_NTP_LOGS_DIR", "/var/log"))
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


def main():

    loggers = []

    loggers.append(init_os_logger())
    loggers.append(init_ntp_logger())

    for logger in loggers:
        logger.start()

    try:
        for logger in loggers:
            logger.join()
    except KeyboardInterrupt:
        print("Shutting down loggers ...")
        for logger in loggers:
            logger.stop()
            logger.join()


if __name__ == "__main__":
    main()
