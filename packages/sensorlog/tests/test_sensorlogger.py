from sensorlog import SensorLogger, DailyRotationCsvLogger
import tempfile
import random
from pathlib import Path
import time


def test_sensorlogger():
    with tempfile.TemporaryDirectory() as tempdir:
        sensor_logger = SensorLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            sensors={"test": lambda: random.random()},
            wait=0.1,
        )

        sensor_logger.start()
        time.sleep(1)
        sensor_logger.stop()
        sensor_logger.join()
