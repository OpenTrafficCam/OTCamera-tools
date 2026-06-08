import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from sensorlog import DailyRotationCsvLogger, MetricsLogger
import psutil


logging.basicConfig(level="INFO")


OS_LOG_METRICS: dict[str, Callable[[], int | float]] = {
    "cpu_perc": psutil.cpu_percent,
    "ram_perc": lambda: psutil.virtual_memory().percent,
    "ram_available": lambda: psutil.virtual_memory().available / (1024 * 1024),
    "disk_perc_root": lambda: psutil.disk_usage("/").percent,
    "disk_free_mb_root": lambda: shutil.disk_usage("/").free / (1024 * 1024),
}


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


def main():

    os_logs_output_dir = Path(os.environ.get("OTC_OS_LOGS_DIR", "/tmp/"))
    os_logs_prefix = os.environ.get("OTC_OS_LOGS_PREFIX", "otc_os_logs")
    os_logs_wait_time = int(os.environ.get("OTC_OS_LOGS_WAIT", 5))

    loggers = []

    os_metrics_logger = init_daily_rotating_metrics_logger(
        output_folder=os_logs_output_dir,
        output_file_prefix=os_logs_prefix,
        metrics=OS_LOG_METRICS,
        interval=os_logs_wait_time,
    )

    loggers.append(os_metrics_logger)

    test_logger = init_daily_rotating_metrics_logger(
        output_folder=Path("/tmp/test_logger"),
        output_file_prefix="test",
        metrics={"foo": lambda: 123},
        interval=10,
    )

    loggers.append(test_logger)

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
