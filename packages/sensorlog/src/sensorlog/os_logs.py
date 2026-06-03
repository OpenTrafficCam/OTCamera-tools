import time
from pathlib import Path

from sensorlog import DailyRotationSensorLogger
import psutil


def main():
    psutil.cpu_percent()
    with DailyRotationSensorLogger(
        Path("/tmp"), "os_logs", fieldnames=["cpu_perc", "ram_perc", "disk_perc"]
    ) as logger:
        for _ in range(10):
            cpu_perc = psutil.cpu_percent()
            ram_perc = psutil.virtual_memory().percent
            disk_perc = psutil.disk_usage("/").percent
            logger.write(
                {"cpu_perc": cpu_perc, "ram_perc": ram_perc, "disk_perc": disk_perc}
            )
            print("Updated logs")

            time.sleep(1)


if __name__ == "__main__":
    main()
