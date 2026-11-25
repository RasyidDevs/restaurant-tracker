"""Provider data reservasi & parkir (fitur Micheal).

Backend reservasi dan parkir belum ada, jadi:
  - NoReservations / NoParking : dipakai saat sumber video/CCTV asli (tidak ada data)
  - MockReservations / MockParking : dipakai di mode simulasi, source="mock"

Begitu fitur Micheal tersedia, cukup buat class dengan method yang sama
(`reservations(now, tables)` / `parking(now)`) dan pasang di hub.py.
"""

from __future__ import annotations

from .signals import ParkingSignal, ReservationSignal, TableSignal

_GUESTS = ["Bpk. Andi", "Ibu Sari", "Keluarga Wijaya", "Bpk. Rudi", "Ibu Nina"]


class NoReservations:
    source = "tidak_ada"

    def reservations(self, now: float, tables: list[TableSignal]) -> list[ReservationSignal]:
        return []


class NoParking:
    source = "tidak_ada"

    def parking(self, now: float) -> list[ParkingSignal]:
        return []


class MockReservations:
    """MOCK: tiap blok 30 menit, satu meja (bergiliran) punya reservasi di akhir blok."""

    source = "mock"

    def __init__(self, block_s: float = 1800):
        self.block_s = block_s

    def reservations(self, now: float, tables: list[TableSignal]) -> list[ReservationSignal]:
        if not tables:
            return []
        block = int(now // self.block_s)
        out = []
        for b in (block, block + 1):
            t = tables[b % len(tables)]
            out.append(ReservationSignal(t.id, _GUESTS[b % len(_GUESTS)], (b + 1) * self.block_s, min(t.seats, 2 + b % 3)))
        return out


class MockParking:
    """MOCK: beberapa kendaraan dengan waktu datang tetap relatif terhadap start."""

    source = "mock"

    _SLOTS = [  # slot, jenis, plat, datang (menit sebelum start), batas (menit)
        ("C-01", "mobil", "B 1234 XYZ", 170, 180),
        ("C-02", "mobil", "B 8812 TRA", 60, 180),
        ("M-03", "motor", "D 4567 AB", 105, 120),
        ("M-07", "motor", "B 9012 IK", 20, 120),
    ]

    def __init__(self) -> None:
        self.start: float | None = None

    def parking(self, now: float) -> list[ParkingSignal]:
        if self.start is None:
            self.start = now
        out = []
        for slot, kind, plate, before_min, limit in self._SLOTS:
            dur = (now - self.start) / 60 + before_min
            out.append(ParkingSignal(slot, kind, plate, round(dur % 300, 1), limit))  # berputar tiap 5 jam
        return out
