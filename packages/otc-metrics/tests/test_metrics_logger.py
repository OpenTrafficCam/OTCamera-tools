from otc_metrics import MetricsLogger, DailyRotationCsvLogger
import tempfile
import random
from pathlib import Path
import time


def test_sensorlogger():
    with tempfile.TemporaryDirectory() as tempdir:
        sensor_logger = MetricsLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            metrics={"test": lambda: random.random()},
            interval=0.1,
        )

        sensor_logger.start()
        time.sleep(1)
        sensor_logger.stop()
        sensor_logger.join()
