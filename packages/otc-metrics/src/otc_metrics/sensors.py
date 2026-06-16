import time
from smbus2 import SMBus


class TLA2024_impl:
    # Register map
    REG_CONV = 0x00
    REG_CONF = 0x01

    def __init__(self, bus: int = 1, address: int = 0x48, vdd: float = 3.3):
        self.bus_num = bus
        self.addr = address
        self._bus: SMBus | None = None

    def __enter__(self) -> "TLA2024_impl":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _to_u16(self, lo: int, hi: int) -> int:
        return (lo << 8) | hi

    def read_u8(self, reg: int) -> int:
        assert self._bus is not None
        return self._bus.read_byte_data(self.addr, reg)

    def write_u8(self, reg: int, value: int) -> None:
        assert self._bus is not None
        self._bus.write_byte_data(self.addr, reg, value & 0xFF)

    def read_block(self, start_reg: int, length: int) -> list[int]:
        assert self._bus is not None
        return list(self._bus.read_i2c_block_data(self.addr, start_reg, length))

    def write_u16_be(self, reg: int, val: int) -> None:
        assert self._bus is not None
        val &= 0xFFFF
        self._bus.write_i2c_block_data(self.addr, reg, [(val >> 8) & 0xFF, val & 0xFF])

    def read_u16_be(self, reg: int) -> int:
        assert self._bus is not None
        data = self._bus.read_i2c_block_data(self.addr, reg, 2)
        return (data[0] << 8) | data[1]

    def open(self):
        self._bus = SMBus(self.bus_num)

    def close(self) -> None:
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def build_config(self, chn: int):
        if chn not in (0, 1, 2, 3):
            raise ValueError("Channel must be 0..3")

        mux = (0b100 | chn) & 0b111
        cfg = 0
        cfg |= 0b1 << 15 | mux << 12 | 0b001 << 9 | 1 << 8 | 0b000 << 5 | 0b11
        return cfg

    def read_channel(self, chn: int):
        cfg = self.build_config(chn)
        self.write_u16_be(self.REG_CONF, cfg)

        while True:
            cfg = self.read_u16_be(self.REG_CONF)
            if (cfg >> 15) & 1:
                break
            time.sleep(0.001)

        raw16 = self.read_u16_be(self.REG_CONV)
        raw16s = raw16 - 0x10000 if (raw16 & 0x8000) else raw16
        raw12 = raw16s >> 4
        if raw12 < 0:
            raw12 = 0
        return raw12 * (4.096 / 2048)

    def is_open(self) -> bool:
        return self._bus is not None


class LIS2DW12_impl:
    # Register map
    WHO_AM_I = 0x0F
    CTRL1 = 0x20
    CTRL6 = 0x25
    OUT_X_L = 0x28
    OUT_T_L = 0x0D

    def __init__(self, bus: int = 1, address: int = 0x19, fs_g: int = 2):
        self.bus_num = bus
        self.addr = address
        self.fs_g = fs_g
        self._bus: SMBus | None = None

    def __enter__(self) -> "LIS2DW12_impl":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _to_int16(self, lo: int, hi: int) -> int:
        v = (hi << 8) | lo
        return v - 65536 if v & 0x8000 else v

    def read_u8(self, reg: int) -> int:
        assert self._bus is not None
        return self._bus.read_byte_data(self.addr, reg)

    def write_u8(self, reg: int, value: int) -> None:
        assert self._bus is not None
        self._bus.write_byte_data(self.addr, reg, value & 0xFF)

    def read_block(self, start_reg: int, length: int) -> list[int]:
        assert self._bus is not None
        return list(self._bus.read_i2c_block_data(self.addr, start_reg, length))

    def open(self):
        self._bus = SMBus(self.bus_num)
        who = self.read_u8(self.WHO_AM_I)
        if who != 0x44:
            raise RuntimeError("LIS2DW12 WHO_AM_I mismatch")

        self.write_u8(self.CTRL6, 0)
        self.write_u8(self.CTRL1, (0b0001 << 4 | 0b01 << 2 | 0b00))
        time.sleep(0.05)

    def close(self) -> None:
        self.write_u8(self.CTRL1, 0)
        time.sleep(0.05)
        if self._bus is not None:
            self._bus.close()
            self._bus = None

    def read_acc(self) -> tuple[float, float, float]:
        data = self.read_block(self.OUT_X_L, 6)
        x = self._to_int16(data[0], data[1]) >> 2
        y = self._to_int16(data[2], data[3]) >> 2
        z = self._to_int16(data[4], data[5]) >> 2
        s = 0.244 / 1000
        return s * x, s * y, s * z

    def read_temp(self):
        data = self.read_block(self.OUT_T_L, 2)
        raw = self._to_int16(data[0], data[1]) >> 4
        return 25.0 + (raw / 16.0)

    def is_open(self) -> bool:
        return self._bus is not None
