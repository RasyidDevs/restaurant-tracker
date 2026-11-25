"""State bersama antara thread worker CV dan API (thread-safe)."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from .config import Config
from .core.detection import Detection
from .core.perception import Perception
from .core.zones import TableObs
from .features.table_occupancy import OccupancyRules, TableOccupancyFeature
from .features.waiting_time import WaitingRules, WaitingTimeFeature


class Hub:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.perception = Perception(cfg.tables, cfg.core)
        # Daftarkan fitur di sini. Fitur baru cukup ditambah satu baris.
        self.waiting = WaitingTimeFeature(self.perception, WaitingRules.from_dict(cfg.features.get("waiting_time")))
        self.perception.add_feature(self.waiting)
        self.occupancy = TableOccupancyFeature(self.perception, OccupancyRules.from_dict(cfg.features.get("table_occupancy")))
        self.perception.add_feature(self.occupancy)

        self.events: deque[dict[str, Any]] = deque(maxlen=500)
        self.source_status: dict[str, Any] = {"state": "starting", "detail": ""}
        self.latest_jpeg: bytes | None = None

    # dipanggil worker --------------------------------------------------
    def step(self, t: float, obs: dict[str, TableObs]) -> None:
        with self.lock:
            self.events.extend(self.perception.step(t, obs))

    def step_detections(self, t: float, dets: list[Detection]) -> None:
        with self.lock:
            self.events.extend(self.perception.step_detections(t, dets))

    def set_status(self, state: str, detail: str = "") -> None:
        with self.lock:
            self.source_status = {"state": state, "detail": detail}

    # dipanggil API -----------------------------------------------------
    def core_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.perception.snapshot(), "source": dict(self.source_status)}

    def waiting_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.waiting.snapshot(self.perception), "source": dict(self.source_status)}

    def occupancy_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.occupancy.snapshot(self.perception), "source": dict(self.source_status)}

    def confirm_waiting(self, session_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.waiting.confirm(session_id, self.perception.now)
