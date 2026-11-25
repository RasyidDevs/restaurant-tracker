"""Data gabungan dari fitur tim -> satu struktur `TeamSignals` untuk rule engine.

Sumber:
  tables      core TableState (orang, lama duduk, lama kosong, piring, gelas)
              -> fitur Firnas (okupansi, durasi) & Rasyid (piring tertinggal)
  waiting     WaitingTimeFeature (Rasyid)
  outside     OutsideFoodFeature (Thoriq)
  reservations, parking
              fitur Micheal; backend-nya belum ada, jadi lewat provider
              (lihat providers.py). Mode simulasi memakai provider MOCK.

Semua field berupa data biasa (tanpa referensi ke objek live), jadi bisa
dibuat di dalam lock hub lalu diproses di luar lock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ...core.perception import Perception


@dataclass
class TableSignal:
    id: str
    name: str
    seats: int
    people: int
    plates: int
    glasses: int
    occupied_s: float
    empty_s: float


@dataclass
class WaitingSignal:
    table: str
    session_id: str
    waiting_s: float
    status: str  # menunggu | sebagian
    people: int
    plates_served: int
    glasses_served: int


@dataclass
class OutsideSignal:
    table: str
    alert_id: str
    label: str
    category: str
    confidence: float
    since_s: float
    source: str


@dataclass
class ReservationSignal:
    table: str
    guest: str
    at: float  # epoch
    party_size: int


@dataclass
class ParkingSignal:
    slot: str
    kind: str  # mobil | motor
    plate: str
    duration_min: float
    limit_min: float


@dataclass
class TeamSignals:
    now: float
    tables: list[TableSignal] = field(default_factory=list)
    waiting: list[WaitingSignal] = field(default_factory=list)
    outside: list[OutsideSignal] = field(default_factory=list)
    reservations: list[ReservationSignal] = field(default_factory=list)
    parking: list[ParkingSignal] = field(default_factory=list)
    data_sources: dict[str, str] = field(default_factory=dict)  # nama data -> "cv" | "mock" | "tidak_ada"

    def table(self, tid: str) -> TableSignal | None:
        return next((t for t in self.tables if t.id == tid), None)

    @property
    def occupancy(self) -> float:
        return sum(1 for t in self.tables if t.people > 0) / len(self.tables) if self.tables else 0.0


class ReservationProvider(Protocol):
    source: str

    def reservations(self, now: float, tables: list[TableSignal]) -> list[ReservationSignal]: ...


class ParkingProvider(Protocol):
    source: str

    def parking(self, now: float) -> list[ParkingSignal]: ...


def build_signals(
    perception: Perception,
    waiting_snapshot: dict[str, Any] | None,
    outside_active: list[dict[str, Any]],
    outside_source: str,
    reservations: ReservationProvider,
    parking: ParkingProvider,
) -> TeamSignals:
    now = perception.now
    tables = [
        TableSignal(
            id=ts.id,
            name=ts.zone.name,
            seats=ts.zone.seats,
            people=ts.people,
            plates=ts.plates,
            glasses=ts.glasses,
            occupied_s=ts.occupied_for_s(now),
            empty_s=ts.empty_for_s(now),
        )
        for ts in perception.tables.values()
    ]
    waiting = [
        WaitingSignal(
            table=s["table_id"],
            session_id=s["id"],
            waiting_s=s["waiting_s"],
            status=s["status"],
            people=s["people_peak"],
            plates_served=s["plates_served"],
            glasses_served=s["glasses_served"],
        )
        for s in (waiting_snapshot or {}).get("active", [])
    ]
    outside = [
        OutsideSignal(
            table=a["table"],
            alert_id=a["id"],
            label=a["label"],
            category=a["category"],
            confidence=a["confidence"],
            since_s=now - a["first_seen"],
            source=a["source"],
        )
        for a in outside_active
    ]
    return TeamSignals(
        now=now,
        tables=tables,
        waiting=waiting,
        outside=outside,
        reservations=reservations.reservations(now, tables),
        parking=parking.parking(now),
        data_sources={
            "meja": "cv" if outside_source == "cv" else "simulasi",
            "waiting_time": "cv" if outside_source == "cv" else "simulasi",
            "makanan_luar": outside_source,
            "reservasi": reservations.source,
            "parkir": parking.source,
        },
    )
