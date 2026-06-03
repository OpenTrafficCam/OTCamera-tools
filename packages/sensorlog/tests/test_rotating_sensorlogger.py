import tempfile
from datetime import date
from pathlib import Path

from unittest.mock import patch

import sensorlog


def test_rotating_sensorlogger():

    with tempfile.TemporaryDirectory() as tmpdir, patch("sensorlog.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 1)

        logger = sensorlog.DailyRotationSensorLogger(
            directory=Path(tmpdir), prefix="test", fieldnames=["log_a", "log_b"]
        )
        logger.write({"log_a": 1, "log_b": 2})

        logger.close()

        dir_iter = Path(tmpdir).iterdir()

        assert next(dir_iter).name == "test_2026-06-01.csv"


def test_rotating_sensorlogger_can_handle_date_change():
    with tempfile.TemporaryDirectory() as tmpdir, patch("sensorlog.date") as mock_date:
        mock_date.today.side_effect = [
            date(2026, 6, 1),
            date(2026, 6, 1),
            date(2026, 6, 2),
        ]

        logger = sensorlog.DailyRotationSensorLogger(
            directory=Path(tmpdir), prefix="test", fieldnames=["log_a", "log_b"]
        )
        logger.write({"log_a": 1, "log_b": 2})
        logger.write({"log_a": 3, "log_b": 4})

        logger.close()

        assert len(mock_date.today.mock_calls) == 3

        assert {p.name for p in Path(tmpdir).iterdir()} == {
            "test_2026-06-01.csv",
            "test_2026-06-02.csv",
        }
