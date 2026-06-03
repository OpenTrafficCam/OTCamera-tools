from abc import ABC, abstractmethod
from collections.abc import Collection, Callable
import csv
from datetime import date, datetime
from pathlib import Path


class SensorLogger(ABC):
    @abstractmethod
    def write(self, measures: dict, datetime: str | None): ...


class FileSensorLogger(SensorLogger):
    """Log sensor values to a csv-file.

    Usage:

    ```
    with FileSensorLogger(file_path="sensors.csv", fieldnames=["sensor_a", "sensor_b"]) as logger:
        logger.write({"sensor_a": 0.1, "sensor_b": 0.2})
        logger.write({"sensor_a": 0.15, "sensor_b": 0.21})
    ```

    The current date and time will always be prependend automatically.
    The above code will result in the following file:

    datetime,sensor_a,sensor_b\n
    2025-12-02T12:00:00,0.1,0.2\n
    2025-12-02T12:00:01,0.15,021\n

    The name and content of the first column can be influenced by modifying the `time_func` and `time_column_name`
    parameters.
    """

    def __init__(
        self,
        file_path: Path,
        fieldnames: Collection[str],
        time_func: Callable[[], str] = lambda: datetime.now().isoformat(),
        time_column_name: str = "datetime",
    ):
        """Initializes a new FileSensorLogger.

        Args:
            file_path (Path): Path to the file to log to.
            fieldnames:
        """
        self.time_column_name = time_column_name
        self.fieldnames = [time_column_name] + list(fieldnames)

        self.time_func = time_func

        self._file_path = file_path

        self._file_handle = None
        self._writer = None

        self._init_writer()

    def _init_writer(self):
        if self._file_handle is not None:
            self._file_handle.close()

        is_new = False
        if not self._file_path.exists() or self._file_path.stat().st_size == 0:
            is_new = True

        self._file_handle = open(self._file_path, "a")
        self._writer = csv.DictWriter(self._file_handle, fieldnames=self.fieldnames)

        if is_new:
            self._writer.writeheader()

    def close(self) -> None:
        self._file_handle.close()
        self._file_handle = None

    def write(self, measures: dict, datetime: str | None = None) -> None:
        if datetime is not None:
            measures[self.time_column_name] = datetime
        else:
            measures[self.time_column_name] = self.time_func()

        self._writer.writerow(measures)

    def __enter__(self) -> "FileSensorLogger":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class DailyRotationSensorLogger(FileSensorLogger):
    def __init__(
        self,
        directory: Path,
        prefix: str,
        fieldnames: Collection[str],
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

    def write(self, measures: dict, datetime: str | None = None):
        today = date.today()
        if today != self._day:
            self._day = today
            self._file_path = self._get_file_path()
            self._init_writer()

        super().write(measures=measures, datetime=datetime)
