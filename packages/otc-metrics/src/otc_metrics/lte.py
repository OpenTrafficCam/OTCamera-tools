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
class Location:
    cell_id: str


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
        ids = [s.split("/")[-1] for s in modem_list["modem-list"]]

        if modem_id not in ids:
            raise ValueError(f"no modem with id {modem_id} registered.")

    def get_signal_strenght(self) -> SignalStrength:
        c = subprocess.run(
            ("mmcli", "-m", str(self.modem_id), "--get-signal", "--json-output"),
            text=True,
            encoding="utf8",
            check=True,
            capture_output=True,
        )
        signal_values = json.loads(c.stdout)

        return SignalStrength(
            rsrp=float(signal_values["rsrp"]),
            rsrq=float(signal_values["rsrq"]),
            rssi=float(signal_values["rssi"]),
            snr=float(signal_values["snr"]),
        )

    def get_location_info(self) -> Location:
        c = subprocess.run(
            ("mmcli", "-m", str(self.modem_id), "--get-location", "--json-output"),
            text=True,
            encoding="utf8",
            check=True,
            capture_output=True,
        )
        signal_values = json.loads(c.stdout)

        return Location(cell_id=signal_values["modem"]["location"]["3gpp"]["cid"])
