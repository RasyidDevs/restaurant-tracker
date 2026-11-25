"""State bersama antara thread worker CV dan API (thread-safe)."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

from .config import Config
from .core.detection import Detection
from .core.perception import Perception
from .core.zones import TableObs
from .features.outside_food import OutsideFoodFeature, OutsideObs, OutsideRules
from .features.waiting_time import WaitingRules, WaitingTimeFeature


class Hub:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.perception = Perception(cfg.tables, cfg.core)
        # Daftarkan fitur di sini. Fitur baru cukup ditambah satu baris.
        self.waiting = WaitingTimeFeature(self.perception, WaitingRules.from_dict(cfg.features.get("waiting_time")))
        self.perception.add_feature(self.waiting)
        self.outside = OutsideFoodFeature(
            self.perception,
            OutsideRules.from_dict(cfg.features.get("outside_food")),
            source="mock" if cfg.source == "simulate" else "cv",
        )
        self.perception.add_feature(self.outside)

        self.events: deque[dict[str, Any]] = deque(maxlen=500)
        self.source_status: dict[str, Any] = {"state": "starting", "detail": ""}
        self.latest_jpeg: bytes | None = None

    # dipanggil worker --------------------------------------------------
    def step(self, t: float, obs: dict[str, TableObs], outside: dict[str, list[OutsideObs]] | None = None) -> None:
        with self.lock:
            if outside is not None:
                self.outside.observe(outside)
            self.events.extend(self.perception.step(t, obs))

    def step_detections(self, t: float, dets: list[Detection]) -> None:
        with self.lock:
            self.outside.observe_detections(dets)
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

    def confirm_waiting(self, session_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.waiting.confirm(session_id, self.perception.now)

    def outside_snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.outside.snapshot(self.perception), "source_status": dict(self.source_status)}

    def resolve_outside(self, alert_id: str) -> dict[str, Any] | None:
        with self.lock:
            return self.outside.resolve(alert_id, self.perception.now)
