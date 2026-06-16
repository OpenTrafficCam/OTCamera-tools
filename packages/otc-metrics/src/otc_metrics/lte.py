import json
import subprocess
import shutil
from dataclasses import dataclass


@dataclass
class SignalStrength:
    rsrp: float
    rsrq: float
    rssi: float
    snr: float


@dataclass
class GPS:
    lat: float
    lon: float
    time: float


@dataclass
class Location:
    cell_id: str
    gps: GPS | None


class LteStatus:
    def __init__(self, modem_id: int):
        if not shutil.which("mmcli"):
            raise RuntimeError("need 'mmcli' to get LTE metrics.")

        self.modem_id = modem_id

        c = subprocess.run(
            ("mmcli", "-L", "--output-json"),
            text=True,
            encoding="utf8",
            check=True,
            capture_output=True,
        )
        modem_list = json.loads(c.stdout)
        ids = [int(s.split("/")[-1]) for s in modem_list["modem-list"]]

        if modem_id not in ids:
            raise ValueError(f"no modem with id {modem_id} registered.")

    def get_signal_strenght(self) -> SignalStrength:
        c = subprocess.run(
            ("mmcli", "-m", str(self.modem_id), "--signal-get", "--output-json"),
            text=True,
            encoding="utf8",
            check=True,
            capture_output=True,
        )
        signal_values = json.loads(c.stdout)["modem"]["signal"]["lte"]

        return SignalStrength(
            rsrp=float(signal_values["rsrp"]),
            rsrq=float(signal_values["rsrq"]),
            rssi=float(signal_values["rssi"]),
            snr=float(signal_values["snr"]),
        )

    def get_location_info(self) -> Location:
        c = subprocess.run(
            ("mmcli", "-m", str(self.modem_id), "--location-get", "--output-json"),
            text=True,
            encoding="utf8",
            check=True,
            capture_output=True,
        )
        signal_values = json.loads(c.stdout)

        nmea = signal_values["modem"]["gps"]["nmea"]

        gps = self._parse_nmea(nmea)

        return Location(
            cell_id=signal_values["modem"]["location"]["3gpp"]["cid"], gps=gps
        )

    def _parse_nmea(self, nmea: list[str]) -> GPS | None:
        for s in nmea:
            if s.startswith("$GPGGA"):
                values = s.split(",")

                time = float(values[1])
                lat = float(values[2])
                lon = float(values[3])

                return GPS(lat, lon, time)

        return None
