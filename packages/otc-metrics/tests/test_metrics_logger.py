import csv
import tempfile
import time
from pathlib import Path

from otc_metrics import DailyRotationCsvLogger, MetricsLogger


def _read_rows(tempdir: str) -> list[dict]:
    csv_file = next(Path(tempdir).glob("*.csv"))
    return list(csv.DictReader(csv_file.read_text().splitlines()))


def test_sensorlogger():
    with tempfile.TemporaryDirectory() as tempdir:
        sensor_logger = MetricsLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            metrics={"test": lambda: 1.0},
            interval=0.1,
        )

        sensor_logger.start()
        time.sleep(0.5)
        sensor_logger.stop()
        sensor_logger.join()


def test_dict_callable_expands_to_columns():
    with tempfile.TemporaryDirectory() as tempdir:
        logger = MetricsLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            metrics={"imu": lambda: {"acc_x": 1.0, "acc_y": 2.0, "acc_z": 3.0}},
            interval=0.1,
        )
        logger.start()
        time.sleep(0.3)
        logger.stop()
        logger.join()

        rows = _read_rows(tempdir)
        assert len(rows) >= 1
        assert rows[0]["acc_x"] == "1.0"
        assert rows[0]["acc_y"] == "2.0"
        assert rows[0]["acc_z"] == "3.0"
        assert "imu" not in rows[0]


def test_dict_callable_mixed_with_scalar():
    with tempfile.TemporaryDirectory() as tempdir:
        logger = MetricsLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            metrics={
                "cpu": lambda: 42.0,
                "imu": lambda: {"acc_x": 1.0, "acc_y": 2.0, "acc_z": 3.0},
            },
            interval=0.1,
        )
        logger.start()
        time.sleep(0.3)
        logger.stop()
        logger.join()

        rows = _read_rows(tempdir)
        assert len(rows) >= 1
        assert rows[0]["cpu"] == "42.0"
        assert rows[0]["acc_x"] == "1.0"
        assert rows[0]["acc_y"] == "2.0"
        assert rows[0]["acc_z"] == "3.0"


def test_dict_callable_exception_falls_back_to_na():
    calls = 0

    def failing_imu():
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("sensor failure")
        return {"acc_x": 1.0, "acc_y": 2.0}

    with tempfile.TemporaryDirectory() as tempdir:
        logger = MetricsLogger(
            logger=DailyRotationCsvLogger(directory=Path(tempdir), prefix="test"),
            metrics={"cpu": lambda: 42.0, "imu": failing_imu},
            interval=0.1,
        )
        logger.start()
        time.sleep(0.5)
        logger.stop()
        logger.join()

        rows = _read_rows(tempdir)
        assert len(rows) >= 2
        assert rows[0]["acc_x"] == "1.0"
        assert rows[0]["acc_y"] == "2.0"
        # after the callable starts failing, expanded keys fall back to N/A
        assert all(row["cpu"] == "42.0" for row in rows)
        assert rows[1]["acc_x"] == "N/A"
        assert rows[1]["acc_y"] == "N/A"
