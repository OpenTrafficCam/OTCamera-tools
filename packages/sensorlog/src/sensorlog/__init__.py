import csv
import logging
from abc import abstractmethod
from collections.abc import Callable, Collection
from contextlib import AbstractContextManager
from datetime import date, datetime
from pathlib import Path
from threading import Event, Thread

lib_logger = logging.getLogger(__name__)


class CsvLogger(AbstractContextManager):
    @abstractmethod
    def write(self, row: dict, timestamp: None | str = None): ...


class FileCsvLogger(CsvLogger):
    """Log sensor values to a csv-file.

    Usage:

    ```
    with FileCsvLogger(file_path="sensors.csv", fieldnames=["sensor_a", "sensor_b"]) as logger:
        logger.write({"sensor_a": 0.1, "sensor_b": 0.2})
        logger.write({"sensor_a": 0.15, "sensor_b": 0.21})
    ```

    The current date and time will always be prependend automatically.
    The above code will result in the following file:

    datetime,sensor_a,sensor_b\n
    2025-12-02T12:00:00,0.1,0.2\n
    2025-12-02T12:00:01,0.15,0.21\n

    The name and content of the first column can be influenced by modifying the `time_func` and `time_column_name`
    parameters.
    """

    def __init__(
        self,
        file_path: Path,
        fieldnames: Collection[str] | None = None,
        time_func: Callable[[], str] = lambda: datetime.now().isoformat(),
        time_column_name: str = "datetime",
    ):
        """Initializes a new FileSensorLogger.

        Args:
            file_path (Path): Path to the file to log to.
            fieldnames:
        """
        self.time_column_name = time_column_name
        self.fieldnames = list(fieldnames) if fieldnames is not None else None

        self.time_func = time_func

        self._file_path = file_path

        self._file_handle = None
        self._writer = None

    def _open(self):
        if self._file_handle is not None:
            self._file_handle.close()

        is_new = False
        if not self._file_path.exists() or self._file_path.stat().st_size == 0:
            is_new = True

        self._file_handle = open(self._file_path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._file_handle, fieldnames=[self.time_column_name] + self.fieldnames
        )

        if is_new:
            self._writer.writeheader()

    def close(self) -> None:
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

    def write(self, row: dict, timestamp: str | None = None) -> None:
        if self._writer is None:
            if self.fieldnames is None:
                self.fieldnames = list(row.keys())
            self._open()

        row_to_write = {self.time_column_name: timestamp or self.time_func(), **row}

        self._writer.writerow(row_to_write)
        self._file_handle.flush()

    def __exit__(self, exc_type, exc, tb):
        self.close()


class DailyRotationCsvLogger(FileCsvLogger):
    def __init__(
        self,
        directory: Path,
        prefix: str,
        fieldnames: Collection[str] | None = None,
        time_func: Callable[[], str] = lambda: datetime.today().isoformat(),
        time_column_name: str = "datetime",
    ):

        # keep track of the current day
        self._day = date.today()

        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

        self.prefix = prefix

        self._file_path = self._get_file_path()

        super().__init__(
            file_path=self._file_path,
            fieldnames=fieldnames,
            time_func=time_func,
            time_column_name=time_column_name,
        )

    def _get_file_path(self) -> Path:
        return self.directory / f"{self.prefix}_{self._day.isoformat()}.csv"

    def write(self, row: dict, timestamp: str | None = None):
        today = date.today()
        if today != self._day:
            self._day = today
            self._file_path = self._get_file_path()

            if self._file_handle is not None:
                self._file_handle.close()
                self._file_handle = None

            self._writer = None

        super().write(row=row, timestamp=timestamp)


class SensorLogger(Thread):
    def __init__(
        self,
        logger: CsvLogger,
        sensors: dict[str, Callable[[], float | int]],
        wait: float,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._logger = logger
        self._sensors = sensors
        self._wait = wait
        self._shutdown = Event()

    def run(self) -> None:
        with self._logger as logger:
            while True:
                try:
                    logger.write({name: read() for name, read in self._sensors.items()})
                except Exception as e:
                    lib_logger.warning(f"Exception while getting sensor data: {e}")
                if self._shutdown.wait(timeout=self._wait):
                    break

    def stop(self) -> None:
        self._shutdown.set()
