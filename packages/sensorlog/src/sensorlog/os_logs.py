import argparse
import logging
import shutil
from collections.abc import Callable, Collection
from pathlib import Path

from sensorlog import DailyRotationCsvLogger, SensorLogger
import psutil


logging.basicConfig(level="DEBUG")


SENSORS: dict[str, Callable[[], int | float]] = {
    "cpu_perc": psutil.cpu_percent,
    "ram_perc": lambda: psutil.virtual_memory().percent,
    "ram_available": lambda: psutil.virtual_memory().available / (1024 * 1024),
    "disk_perc_root": lambda: psutil.disk_usage("/").percent,
    "disk_free_mb_root": lambda: shutil.disk_usage("/").free / (1024 * 1024),
}


def write_os_logs(
    output_folder: Path, output_file_prefix: str, sensors: Collection[str], wait: int
):

    sensors_to_log: dict[str, Callable[[], int | float]] = {}

    for m in sensors:
        try:
            sensors_to_log[m] = SENSORS[m]
        except KeyError as e:
            avail = ", ".join(SENSORS.keys())
            raise ValueError(f"Unknown metric `{e.args[0]}`, must be one of: {avail}")

    logging.info(
        "Start writing metrics {} to {}".format(
            ", ".join(sensors_to_log), output_folder
        )
    )

    sensor_logger = SensorLogger(
        logger=DailyRotationCsvLogger(
            output_folder,
            output_file_prefix,
        ),
        sensors=sensors_to_log,
        wait=wait,
    )

    sensor_logger.start()
    try:
        sensor_logger.join()
    except KeyboardInterrupt:
        print("Shutting down logger ...")
        sensor_logger.stop()
        sensor_logger.join()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-s",
        "--sensors",
        nargs="+",
        default=list(SENSORS.keys()),
        help="Select sensors to write.",
    )
    parser.add_argument("-w", "--wait", required=True, type=int)
    parser.add_argument(
        "-d", "--directory", required=True, type=Path, help="Output directory."
    )
    parser.add_argument("-p", "--prefix", default="os_logs", help="File prefix to use.")

    args = parser.parse_args()

    write_os_logs(
        output_folder=args.directory,
        output_file_prefix=args.prefix,
        sensors=args.sensors,
        wait=args.wait,
    )


if __name__ == "__main__":
    main()
