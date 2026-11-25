"""Pusat persepsi: deteksi -> zona -> status meja -> event inti -> fitur.

Alur per frame:
  1. Detector.track(frame)         -> list[Detection]        (core.detection)
  2. ZoneMap.assign(detections)    -> TableObs per meja      (core.zones)
  3. TableState.update(obs)        -> CoreEvent              (core.table_state)
  4. feature.on_step(...)          -> event fitur (alert, sesi selesai, dll.)

Fitur hanya membaca TableState dan CoreEvent; fitur tidak menghitung ulang
orang/piring/gelas sendiri, jadi semua fitur memakai angka yang sama.
"""

from __future__ import annotations

from typing import Any, Protocol

from .detection import Detection
from .table_state import CoreEvent, CoreRules, TableState
from .zones import TableObs, TableZone, ZoneMap


class Feature(Protocol):
    name: str

    def on_step(self, t: float, perception: "Perception", events: list[CoreEvent]) -> list[dict[str, Any]]:
        """Dipanggil setiap langkah setelah status meja diperbarui. Kembalikan event fitur."""
        ...

    def snapshot(self, perception: "Perception") -> dict[str, Any]: ...


class Perception:
    def __init__(self, tables: list[TableZone], rules: CoreRules, features: list[Feature] | None = None):
        self.zones = ZoneMap(tables)
        self.tables: dict[str, TableState] = {t.id: TableState(t, rules) for t in tables}
        self.features: dict[str, Feature] = {f.name: f for f in (features or [])}
        self.now = 0.0

    def add_feature(self, feature: Feature) -> None:
        self.features[feature.name] = feature

    def step_detections(self, t: float, dets: list[Detection]) -> list[dict[str, Any]]:
        return self.step(t, self.zones.assign(dets))

    def step(self, t: float, obs: dict[str, TableObs]) -> list[dict[str, Any]]:
        self.now = t
        core_events: list[CoreEvent] = []
        for tid, state in self.tables.items():
            core_events += state.update(t, obs.get(tid) or TableObs(seat_flags=[False] * len(state.zone.chairs)))
        out: list[dict[str, Any]] = []
        for f in self.features.values():
            out += f.on_step(t, self, core_events)
        return out

    def snapshot(self) -> dict[str, Any]:
        return {"now": self.now, "tables": [s.snapshot() for s in self.tables.values()]}
