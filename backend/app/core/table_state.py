"""Status inti satu meja: sumber kebenaran bersama untuk semua fitur meja.

Yang dihitung di sini (sekali, dipakai semua fitur):
  people          jumlah orang yang menetap di meja (sudah disaring dari waiter/orang lewat)
  plates/glasses  jumlah piring & gelas di permukaan meja (sudah dihaluskan)
  seats_occupied  kursi yang terisi (kalau layout kursi tersedia)
  occupied_since  sejak kapan meja terisi (dimundurkan ke orang pertama terlihat)
  empty_since     sejak kapan meja kosong (dimundurkan ke orang terakhir terlihat)
  history         riwayat (t, orang, piring, gelas) 10 menit terakhir

Event inti yang dikirim ke fitur:
  occupied  meja mulai terisi          (t = orang pertama terlihat)
  emptied   meja menjadi kosong        (t = orang terakhir terlihat)
  people    jumlah orang berubah
  plates    jumlah piring berubah      (t dimundurkan ke saat angka baru pertama muncul)
  glasses   jumlah gelas berubah
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .smoothing import StableCount
from .tracks import DwellTracker
from .zones import TableObs, TableZone


@dataclass
class CoreRules:
    seated_min_s: float = 30.0  # orang dianggap menetap setelah selama ini di zona meja
    lost_grace_s: float = 15.0  # track orang hilang lebih lama dari ini dianggap pergi
    count_window_s: float = 3.0  # jendela modus penghalus hitungan
    count_hold_s: float = 3.0  # angka baru harus stabil selama ini
    history_s: float = 600.0

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "CoreRules":
        d = d or {}
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CoreEvent:
    type: str  # occupied | emptied | people | plates | glasses
    table: str
    t: float
    old: int = 0
    new: int = 0


class TableState:
    def __init__(self, zone: TableZone, rules: CoreRules):
        self.zone = zone
        self.rules = rules
        self.dwell = DwellTracker(rules.seated_min_s, rules.lost_grace_s)
        mk = lambda: StableCount(window_s=rules.count_window_s, hold_s=rules.count_hold_s)  # noqa: E731
        self._people = mk()
        self._plates = mk()
        self._glasses = mk()
        self.history: deque[tuple[float, int, int, int]] = deque()
        self.occupied_since: float | None = None
        self.empty_since: float | None = None
        self.seat_flags: list[bool] = [False] * len(zone.chairs)
        self.raw = TableObs()
        self.last_t = 0.0

    # ----------------------------------------------------------- properti
    @property
    def id(self) -> str:
        return self.zone.id

    @property
    def people(self) -> int:
        return self._people.value

    @property
    def plates(self) -> int:
        return self._plates.value

    @property
    def glasses(self) -> int:
        return self._glasses.value

    @property
    def seats_occupied(self) -> int:
        return sum(self.seat_flags)

    def occupied_for_s(self, now: float | None = None) -> float:
        if self.occupied_since is None or self.people == 0:
            return 0.0
        return (now if now is not None else self.last_t) - self.occupied_since

    def empty_for_s(self, now: float | None = None) -> float:
        if self.empty_since is None or self.people > 0:
            return 0.0
        return (now if now is not None else self.last_t) - self.empty_since

    def min_items_since(self, t0: float) -> tuple[int, int]:
        """Jumlah piring & gelas paling sedikit sejak t0 (untuk baseline)."""
        window = [(p, g) for ts, _, p, g in self.history if ts >= t0] or [(self.plates, self.glasses)]
        return min(p for p, _ in window), min(g for _, g in window)

    # ------------------------------------------------------------- update
    def update(self, t: float, obs: TableObs) -> list[CoreEvent]:
        self.last_t = t
        self.raw = obs
        if len(obs.seat_flags) == len(self.seat_flags):
            self.seat_flags = list(obs.seat_flags)
        events: list[CoreEvent] = []

        self.dwell.update(t, obs.person_ids)
        settled = self.dwell.settled()

        ch = self._people.update(t, len(settled))
        if ch:
            if ch.old == 0 and ch.new > 0:
                start = min(settled.values()) if settled else ch.at
                self.occupied_since = start
                self.empty_since = None
                events.append(CoreEvent("occupied", self.id, start, ch.old, ch.new))
            elif ch.new == 0:
                last = self.dwell.last_seen_any
                self.empty_since = min(last, t) if last is not None else ch.at
                events.append(CoreEvent("emptied", self.id, self.empty_since, ch.old, ch.new))
            events.append(CoreEvent("people", self.id, ch.at, ch.old, ch.new))

        for name, counter, raw in (("plates", self._plates, obs.plates), ("glasses", self._glasses, obs.glasses)):
            ch = counter.update(t, raw)
            if ch:
                events.append(CoreEvent(name, self.id, ch.at, ch.old, ch.new))

        self.history.append((t, self.people, self.plates, self.glasses))
        while self.history and t - self.history[0][0] > self.rules.history_s:
            self.history.popleft()
        return events

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.zone.id,
            "name": self.zone.name,
            "seats": self.zone.seats,
            "people": self.people,
            "people_raw": len(self.raw.person_ids),
            "plates": self.plates,
            "glasses": self.glasses,
            "seats_occupied": self.seats_occupied if self.zone.chairs else None,
            "seat_flags": self.seat_flags if self.zone.chairs else None,
            "occupied_since": self.occupied_since if self.people else None,
            "occupied_s": round(self.occupied_for_s(), 1),
            "empty_since": self.empty_since if not self.people else None,
            "empty_s": round(self.empty_for_s(), 1),
        }
