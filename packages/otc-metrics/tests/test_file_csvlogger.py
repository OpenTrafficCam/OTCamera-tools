import otc_metrics
import tempfile
from pathlib import Path
from unittest.mock import Mock


def test_file_log():
    with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
        fp.close()

        time_mock = Mock()
        time_mock.return_value = "2026-06-01"

        logger = otc_metrics.FileCsvLogger(
            file_path=Path(fp.name), fieldnames=["log_a", "log_b"], time_func=time_mock
        )
        logger.write({"log_a": 1, "log_b": 2})
        logger.close()

        with open(fp.name, "r") as f:
            contents = f.read()

        assert contents == "datetime,log_a,log_b\n2026-06-01,1,2\n"


def test_file_log_only_writes_header_on_new_files():
    with tempfile.NamedTemporaryFile(delete_on_close=False) as fp:
        fp.close()

        time_mock = Mock()
        time_mock.side_effect = ["2026-06-01T12:00", "2026-06-01T13:00"]

        logger = otc_metrics.FileCsvLogger(
            file_path=Path(fp.name), fieldnames=["log_a", "log_b"], time_func=time_mock
        )
        logger.write({"log_a": 1, "log_b": 2})
        logger.close()

        logger = otc_metrics.FileCsvLogger(
            file_path=Path(fp.name), fieldnames=["log_a", "log_b"], time_func=time_mock
        )
        logger.write({"log_a": 3, "log_b": 4})
        logger.close()

        with open(fp.name, "r") as f:
            contents = f.read()

        assert (
            contents
            == "datetime,log_a,log_b\n2026-06-01T12:00,1,2\n2026-06-01T13:00,3,4\n"
        )
